"""A runtime is one peer.

``http://host:port`` is a direct dial. A peer id is reached through the
super nodes this process was given: connect to every one that answers, then
open a stream. A public address already in the peerstore is dialed directly.
Otherwise the stream goes through a super node the peer has joined. Hole
punching runs after that stream exists and does not decide whether the
slice is delivered.

A super node is a runtime started with ``--sn-listen``. Several super nodes
are several entries in the same list. Each runtime connects to every entry
it can reach. The list is not copied onto each layer.

Every peer on that network, the super node and the control process included,
is started with the same ``--net`` secret. A peer that does not have it is
not given a relay slot, and a stream it opens is refused.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import threading
from pathlib import Path

def _quiet_libp2p():
    logging.getLogger("libp2p").setLevel(logging.CRITICAL)

_PEER_ID = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{46,}$")
_PROTOCOL = "/pyouter/node/1.0.0"
_control = None
_control_key = None


def is_peer_id(value):
    """Return whether ``value`` is a libp2p peer id."""
    return isinstance(value, str) and _PEER_ID.fullmatch(value) is not None


def peer_id_of(path):
    """Return the peer id stored at ``path``, creating it on first use."""
    _require_libp2p()
    from libp2p.peer.id import ID

    pair = _load_keypair(Path(path))
    return ID.from_pubkey(pair.public_key).to_base58()


def network_secret(net=None):
    """Return the shared secret for this network.

    An explicit ``net`` wins. Otherwise the value is ``PYOUTER_NET``.
    An empty string means this process was not given one.
    """
    if net is None:
        net = os.environ.get("PYOUTER_NET", "")
    if net is None:
        return ""
    return str(net).strip()


def super_nodes(sn=None):
    """Return the super-node multiaddrs for this control process."""
    if sn is None:
        raw = os.environ.get("PYOUTER_SN", "")
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(sn, str):
        text = sn.strip()
        return [text] if text else []
    return [str(item).strip() for item in sn if str(item).strip()]


def peer_health(peer_id, sn=None, net=None):
    """Ask ``peer_id`` for its health through the super nodes in ``sn``."""
    return _control_request(peer_id, {"op": "health"}, sn, net)


def peer_reachable(peer_id):
    """Return whether the control peer that is already running can reach ``peer_id``.

    This does not start a control peer. A page asking about reachability
    must not boot one.
    """
    peer = _control
    if peer is None or peer._token is None:
        return False
    try:
        body = peer.request(peer_id, {"op": "health"})
    except Exception:
        return False
    return bool(isinstance(body, dict) and body.get("ok"))


def push_peer(peer_id, layer, sn=None, net=None):
    """Push one layer slice to the peer ``peer_id``."""
    body = {
        "op": "deploy",
        "spec": {
            "path": layer.path,
            "kind": layer.kind,
            "balancer": layer.balancer,
            "workers": layer.workers,
        },
    }
    return _control_request(peer_id, body, sn, net)


def close_control():
    """Stop the control peer started by a push, if this process owns one."""
    global _control, _control_key
    peer = _control
    _control = None
    _control_key = None
    if peer is not None:
        peer.close()


class PeerNode:
    """One running peer. A super node is the same object with hop enabled."""

    def __init__(self, identity, sn=(), sn_listen=None, handler=None, net=None):
        self.identity = Path(identity)
        self.sn = list(sn)
        self.sn_listen = sn_listen
        self.handler = handler
        self.net = network_secret(net)
        self.peer_id = ""
        self.listen_addr = ""
        self.joined = []
        self._admitted = set()
        self._thread = None
        self._token = None
        self._ready = threading.Event()
        self._failure = None

    def start(self):
        """Listen and join every reachable super node. Block until ready."""
        if (self.sn or self.sn_listen is not None) and not self.net:
            raise RuntimeError("this network needs --net")
        self._thread = threading.Thread(target=self._thread_main, name="pyouter-peer", daemon=True)
        self._thread.start()
        if not self._ready.wait(20):
            raise RuntimeError("peer did not start")
        if self._failure is not None:
            raise self._failure
        return self

    def request(self, peer_id, message):
        """Send one JSON message to ``peer_id`` and return the JSON reply."""
        import trio

        if self._token is None:
            raise RuntimeError("peer is not running")
        return trio.from_thread.run(self._request, peer_id, message, trio_token=self._token)

    def close(self):
        import trio

        if self._token is None:
            return
        token = self._token
        self._token = None
        try:
            trio.from_thread.run(self._signal_stop, trio_token=token)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(5)

    def _thread_main(self):
        import trio

        try:
            trio.run(self._main)
        except Exception as exc:
            self._failure = exc
            self._ready.set()

    async def _signal_stop(self):
        self._stop.set()

    async def _main(self):
        import multiaddr
        import trio
        from libp2p import new_host
        from libp2p.custom_types import TProtocol
        from libp2p.relay.circuit_v2.config import RelayConfig, RelayRole
        from libp2p.relay.circuit_v2.dcutr import DCUtRProtocol
        from libp2p.relay.circuit_v2.protocol import CircuitV2Protocol
        from libp2p.relay.circuit_v2.resources import RelayLimits
        from libp2p.relay.circuit_v2.transport import CircuitV2Transport
        from libp2p.tools.anyio_service import background_trio_service

        _quiet_libp2p()
        limits = RelayLimits(
            duration=3600,
            data=1024 * 1024 * 1024,
            max_circuit_conns=128,
            max_reservations=128,
        )
        host = new_host(
            key_pair=_load_keypair(self.identity),
            enable_mDNS=False,
            enable_upnp=False,
        )
        self._host = host
        self.peer_id = host.get_id().to_base58()
        host.set_stream_handler(TProtocol(_PROTOCOL), self._on_stream)
        if self.sn_listen:
            listen_host, listen_port = self.sn_listen
            listen = [multiaddr.Multiaddr(f"/ip4/{listen_host}/tcp/{int(listen_port)}")]
            protocol = _guarded_hop(host, limits, self._admitted)
        else:
            listen_host = "127.0.0.1"
            listen = [multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/0")]
            protocol = CircuitV2Protocol(host, limits=limits, allow_hop=False)
        punch = DCUtRProtocol(host)
        roles = RelayRole.CLIENT | RelayRole.STOP
        if self.sn_listen is not None:
            roles = roles | RelayRole.HOP
        self._transport = CircuitV2Transport(host, protocol, RelayConfig(roles=roles, limits=limits))
        self._punch = punch
        self._stop = trio.Event()
        try:
            async with host.run(listen):
                async with background_trio_service(protocol), background_trio_service(punch):
                    self.listen_addr = _chosen_addr(host, listen_host)
                    async with trio.open_nursery() as nursery:
                        self._nursery = nursery
                        self.joined = await self._join(nursery)
                        self._token = trio.lowlevel.current_trio_token()
                        self._ready.set()
                        await self._stop.wait()
                        nursery.cancel_scope.cancel()
        except Exception as exc:
            self._failure = exc
            self._ready.set()
            raise

    async def _join(self, nursery):
        import multiaddr
        import trio
        from libp2p.peer.id import ID
        from libp2p.peer.peerinfo import PeerInfo
        from libp2p.relay.circuit_v2.protocol import PROTOCOL_ID

        joined = []
        for item in self.sn:
            try:
                address = multiaddr.Multiaddr(item)
                sn_text = address.get_peer_id()
                if not sn_text:
                    continue
                sn_id = ID.from_base58(sn_text)
                with trio.fail_after(3):
                    await self._host.connect(PeerInfo(sn_id, [address]))
                    await self._hello(sn_id)
                    stream = await self._host.new_stream(sn_id, [PROTOCOL_ID])
                    ok = await self._transport.reserve(stream, sn_id, nursery)
                if ok:
                    joined.append(sn_id.to_base58())
            except Exception:
                continue
        return joined

    async def _hello(self, sn_id):
        from libp2p.custom_types import TProtocol

        stream = await self._host.new_stream(sn_id, [TProtocol(_PROTOCOL)])
        await _write_message(stream, {"op": "hello", "auth": _proof(self.net)})
        reply = await _read_message(stream)
        await stream.close()
        if not isinstance(reply, dict) or reply.get("error") or not reply.get("ok"):
            raise RuntimeError("refused")

    async def _on_stream(self, stream):
        import trio

        try:
            message = await _read_message(stream)
            if not _accept(self.net, message):
                await _write_message(stream, {"error": "refused"})
                return
            remote = _remote_id(stream)
            if message.get("op") == "hello":
                if remote:
                    self._admitted.add(remote)
                await _write_message(stream, {"ok": True})
                return
            message = {key: value for key, value in message.items() if key != "auth"}
            if self.handler is None:
                reply = {"error": "peer has no handler"}
            else:
                reply = await trio.to_thread.run_sync(self.handler, message)
            await _write_message(stream, reply)
        except Exception as exc:
            try:
                await _write_message(stream, {"error": str(exc)})
            except Exception:
                pass
        finally:
            try:
                await stream.close()
            except Exception:
                pass

    async def _request(self, peer_id, message):
        import trio
        from libp2p.peer.id import ID

        target = ID.from_base58(peer_id)
        last = None
        for _attempt in range(2):
            try:
                await self._reach(target)
                return await self._exchange(target, message)
            except Exception as exc:
                last = exc
                with trio.move_on_after(2):
                    try:
                        await self._host.disconnect(target)
                    except Exception:
                        pass
        raise RuntimeError(f"peer {peer_id} did not answer: {last}")

    async def _exchange(self, target, message):
        import trio
        from libp2p.custom_types import TProtocol

        with trio.fail_after(15):
            stream = await self._host.new_stream(target, [TProtocol(_PROTOCOL)])
            body = dict(message)
            body["auth"] = _proof(self.net)
            await _write_message(stream, body)
            reply = await _read_message(stream)
            await stream.close()
        if not isinstance(reply, dict):
            raise RuntimeError(f"peer {target.to_base58()} returned an empty reply")
        if reply.get("error"):
            raise RuntimeError(str(reply["error"]))
        return reply

    async def _reach(self, target):
        import multiaddr
        import trio
        from libp2p.peer.id import ID
        from libp2p.peer.peerinfo import PeerInfo

        if _connected(self._host, target):
            return
        direct = _direct_addrs(self._host, target)
        if direct:
            try:
                with trio.fail_after(3):
                    await self._host.connect(PeerInfo(target, direct))
                return
            except Exception:
                pass
        last = "peer has not joined a super node"
        for sn_text in self.joined:
            sn_id = ID.from_base58(sn_text)
            relay_addrs = _direct_addrs(self._host, sn_id)
            if not relay_addrs:
                continue
            circuit = multiaddr.Multiaddr(
                f"{relay_addrs[0]}/p2p-circuit/p2p/{target.to_base58()}"
            )
            try:
                with trio.fail_after(8):
                    await self._transport.dial(circuit)
                with trio.move_on_after(2):
                    try:
                        await self._punch.initiate_hole_punch(target)
                    except Exception:
                        pass
                return
            except Exception as exc:
                last = str(exc) or last
        raise RuntimeError(f"peer {target.to_base58()} has not joined a super node: {last}")


def _control_request(peer_id, message, sn, net):
    nodes = super_nodes(sn)
    if not nodes:
        raise RuntimeError(f"peer {peer_id} needs a super node")
    secret = network_secret(net)
    if not secret:
        raise RuntimeError(f"peer {peer_id} needs a network secret")
    peer = _control_peer(nodes, secret)
    return peer.request(peer_id, message)


def _control_peer(nodes, secret):
    global _control, _control_key
    identity = os.environ.get("PYOUTER_PEER_IDENTITY")
    if not identity:
        identity = str(Path.home() / ".pyouter" / "peer" / "identity")
    key = (tuple(nodes), identity, secret)
    if _control is not None and _control_key == key and _control._token is not None:
        return _control
    close_control()
    peer = PeerNode(identity, sn=nodes, handler=_local_handler, net=secret)
    peer.start()
    _control = peer
    _control_key = key
    return peer


def _local_handler(message):
    from .node import _service

    return _dispatch(_service, message)


def _dispatch(service, message):
    op = message.get("op") if isinstance(message, dict) else None
    try:
        if op == "health":
            return service.health()
        if op == "deploy":
            return service.deploy(message.get("spec") or {})
        if op == "call":
            return service.call(message.get("payload") or {})
        if op == "shutdown":
            return {"ok": True}
    except (ValueError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {"error": "not found"}


def _chosen_addr(host, prefer_host):
    addrs = [str(item) for item in host.get_addrs()]
    for addr in addrs:
        if prefer_host and f"/ip4/{prefer_host}/" in addr:
            return addr
    if not addrs:
        raise RuntimeError("peer has no listen address")
    return addrs[0]


def _connected(host, peer_id):
    network = host.get_network()
    conns = (getattr(network, "connections", {}) or {}).get(peer_id, [])
    return bool(conns)


def _direct_addrs(host, peer_id):
    try:
        stored = host.get_peerstore().addrs(peer_id)
    except Exception:
        return []
    found = []
    for addr in stored or []:
        text = str(addr)
        if "p2p-circuit" in text:
            continue
        found.append(addr)
    return found


def _guarded_hop(host, limits, admitted):
    """A super node that relays only peers that presented this network's secret."""
    from libp2p.relay.circuit_v2.protocol import CircuitV2Protocol
    from libp2p.relay.circuit_v2.protocol_buffer import StatusCode

    class _Hop(CircuitV2Protocol):
        def __init__(self):
            super().__init__(host, limits=limits, allow_hop=True)
            self._admitted = admitted

        async def _handle_reserve(self, stream, msg):
            if not _admitted_peer(stream, self._admitted):
                await self._deny(stream)
                return
            await super()._handle_reserve(stream, msg)

        async def _handle_connect(self, stream, msg):
            if not _admitted_peer(stream, self._admitted):
                await self._deny(stream)
                return
            await super()._handle_connect(stream, msg)

        async def _deny(self, stream):
            await self._send_status(stream, StatusCode.PERMISSION_DENIED, "refused")
            try:
                await stream.reset()
            except Exception:
                pass

    return _Hop()


def _admitted_peer(stream, admitted):
    remote = _remote_id(stream)
    return bool(remote) and remote in admitted


def _remote_id(stream):
    conn = getattr(stream, "muxed_conn", None)
    peer = getattr(conn, "peer_id", None)
    if peer is None:
        return ""
    if hasattr(peer, "to_base58"):
        return peer.to_base58()
    return str(peer)


def _proof(secret):
    return hmac.new(secret.encode("utf-8"), b"pyouter", hashlib.sha256).hexdigest()


def _accept(secret, message):
    if not secret or not isinstance(message, dict):
        return False
    given = message.get("auth")
    if not isinstance(given, str):
        return False
    return hmac.compare_digest(given, _proof(secret))


def _load_keypair(path):
    from libp2p.crypto.ed25519 import create_new_key_pair
    from libp2p.identity_utils import load_identity, save_identity

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return load_identity(path)
    pair = create_new_key_pair()
    save_identity(pair, path)
    return pair


def _require_libp2p():
    try:
        import libp2p  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("peer support needs the libp2p package") from exc
    _quiet_libp2p()


async def _read_exact(stream, size):
    buf = b""
    while len(buf) < size:
        chunk = await stream.read(size - len(buf))
        if not chunk:
            raise RuntimeError("peer closed the stream")
        buf += chunk
    return buf


async def _read_message(stream):
    header = await _read_exact(stream, 4)
    size = int.from_bytes(header, "big")
    if size > 8_000_000:
        raise RuntimeError("peer message is too large")
    body = await _read_exact(stream, size)
    message = json.loads(body.decode("utf-8"))
    if not isinstance(message, dict):
        raise RuntimeError("peer message must be an object")
    return message


async def _write_message(stream, message):
    body = json.dumps(message).encode("utf-8")
    await stream.write(len(body).to_bytes(4, "big") + body)
