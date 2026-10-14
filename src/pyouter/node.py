"""The runtime that stays up on a physical node.

The runtime is this package. ``deploy_tree`` installs it on first contact,
then pushes one layer. A listener that already answers ``/health`` is left
running. A loopback ``runtime`` is started on this machine. An SSH host, or
a layer reached through one, receives the package at ``~/.pyouter/runtime``
and the listener is started there. Pushing a new slice replaces the pool
that was serving.

This is not a cluster scheduler. The tree already says which runtime
receives which layer.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .balance import normalize_balancer, normalize_workers, start_pool
from .layer import layers_of


class _Service:
    def __init__(self):
        self.lock = threading.Lock()
        self.pools = {}
        self.specs = {}

    def deploy(self, spec):
        path = spec.get("path")
        kind = spec.get("kind")
        if not isinstance(path, str) or path == "":
            raise ValueError("deploy needs a path")
        if kind not in {"docker", "ssh", "cluster", "server"}:
            raise ValueError("deploy needs a layer kind")
        balancer = normalize_balancer(spec.get("balancer"))
        workers = normalize_workers(spec.get("workers"))
        pool = start_pool(provider=balancer, workers=workers)
        with self.lock:
            previous = self.pools.get(path)
            self.pools[path] = pool
            self.specs[path] = {
                "path": path,
                "kind": kind,
                "balancer": balancer,
                "workers": workers,
                "port": pool.port,
            }
            current = dict(self.specs[path])
        if previous is not None:
            previous.close()
        return current

    def call(self, payload):
        layer = payload.get("layer") if isinstance(payload, dict) else None
        with self.lock:
            if layer and layer in self.pools:
                pool = self.pools[layer]
            elif len(self.pools) == 1:
                pool = next(iter(self.pools.values()))
            else:
                pool = None
        if pool is None:
            raise RuntimeError("node has no deployment")
        return pool.call(payload)

    def health(self):
        with self.lock:
            specs = [dict(self.specs[key]) for key in sorted(self.specs)]
        if not specs:
            return {"ok": True, "deployed": False}
        if len(specs) == 1:
            spec = specs[0]
            spec["ok"] = True
            spec["deployed"] = True
            return spec
        return {
            "ok": True,
            "deployed": True,
            "slices": [{**item, "ok": True, "deployed": True} for item in specs],
        }

    def close(self):
        with self.lock:
            pools = list(self.pools.values())
            self.pools = {}
            self.specs = {}
        for pool in pools:
            pool.close()


_service = _Service()
_httpd = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] != "/health":
            self._send(404, {"error": "not found"})
            return
        self._send(200, _service.health())

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            payload = self._read()
            if path == "/deploy":
                self._send(200, _service.deploy(payload))
                return
            if path == "/call":
                self._send(200, _service.call(payload))
                return
            if path == "/shutdown":
                self._send(200, {"ok": True})
                self._stop()
                return
            self._send(404, {"error": "not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._send(409, {"error": str(exc)})

    def log_message(self, fmt, *args):
        return

    def _read(self):
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise ValueError("deploy body must be json") from exc
        if not isinstance(payload, dict):
            raise ValueError("deploy body must be an object")
        return payload

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stop(self):
        _service.close()
        server = _httpd
        if server is not None:
            threading.Thread(target=server.shutdown, daemon=True).start()


def serve(port=0, host="127.0.0.1", identity=None, sn=(), sn_listen=None):
    """Listen for a slice and serve it. Return the bound port.

    ``sn`` is the list of super-node multiaddrs this runtime joins.
    ``sn_listen`` is ``(host, port)`` when this runtime is itself a super node.
    """
    global _httpd, _node_peer
    server = ThreadingHTTPServer((host, int(port)), _Handler)
    _httpd = server
    bound = server.server_address[1]
    print(f"node {bound}", flush=True)
    peer = None
    if sn or sn_listen is not None:
        from .peer import PeerNode

        identity_path = identity or str(Path.home() / ".pyouter" / "peer" / "identity")
        peer = PeerNode(
            identity_path,
            sn=list(sn),
            sn_listen=sn_listen,
            handler=_node_handler,
        ).start()
        _node_peer = peer
        print(f"peer {peer.peer_id}", flush=True)
        if sn_listen is not None:
            print(f"sn {peer.listen_addr}", flush=True)
        for item in peer.joined:
            print(f"joined {item}", flush=True)
        if sn and not peer.joined:
            print("joined none", flush=True)
    try:
        server.serve_forever()
    finally:
        if peer is not None:
            peer.close()
        _node_peer = None
        _service.close()
        server.server_close()
    return bound


def _node_handler(message):
    from .peer import _dispatch

    return _dispatch(_service, message)


_node_peer = None


def push(url, layer):
    """Push one layer slice to the runtime at ``url``."""
    body = {
        "path": layer.path,
        "kind": layer.kind,
        "balancer": layer.balancer,
        "workers": layer.workers,
    }
    return _post(url, "/deploy", body)


def ensure(node, router=None, path=None):
    """Install the runtime named on ``node`` when nothing is listening yet."""
    url = getattr(node, "runtime", None)
    where = path or "layer"
    if not isinstance(url, str) or url == "":
        raise ValueError(f"{where} has no runtime")
    if _listening(url):
        return {"status": "present", "url": url}
    kind, port = _install_plan(node, router, path)
    if kind == "local":
        return _start_local(node, url, port)
    if kind == "ssh":
        return _place_ssh(_ssh_transport(router, path, node), url, port)
    raise RuntimeError(
        f"{where} runtime at {url} is not listening, "
        "and this layer has no ssh host to install it on"
    )


def deploy_tree(router, sn=None):
    """Install each layer's runtime, then push that layer's slice.

    ``sn`` is the control process's super-node list. A layer whose
    ``runtime`` is a peer id is reached through that list. The list is not
    stored on the layer. A cluster layer builds one image, applies one
    pod, and pushes to that pod's peer. A layer under it with no
    ``runtime`` is pushed to the same peer.
    """
    from .cluster import enclosing_cluster, publish
    from .peer import is_peer_id, push_peer

    sent = []
    peers = {}
    for layer in layers_of(router):
        target = _at(router, layer.path)
        if layer.kind == "cluster":
            sent.append(publish(target, layer.path, sn))
            peers[layer.path] = target.runtime
            continue
        url = getattr(target, "runtime", None)
        if not isinstance(url, str) or url == "":
            owner = enclosing_cluster(router, layer.path)
            if owner is None or owner not in peers:
                raise ValueError(f"{layer.path} has no runtime")
            sent.append(push_peer(peers[owner], layer, sn))
            continue
        if is_peer_id(url):
            sent.append(push_peer(url, layer, sn))
            continue
        ensure(target, router=router, path=layer.path)
        sent.append(push(url, layer))
    return sent


def call(url, payload, timeout=30):
    """Send one call to a runtime that already has a deployment."""
    return _post(url, "/call", payload, timeout=timeout)


def health(url, timeout=5):
    return _post(url, "/health", None, timeout=timeout, method="GET")


def shutdown(url):
    try:
        return _post(url, "/shutdown", {}, timeout=5)
    except OSError:
        return {"ok": True}


def _at(router, path):
    node = router
    for part in path.split("."):
        node = node.route[part]
    return node


def _post(url, path, payload, timeout=30, method=None):
    import urllib.error
    import urllib.request

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + path,
        data=data,
        method="GET" if method == "GET" else "POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(detail or f"runtime returned {exc.code}") from exc
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _install_plan(node, router, path):
    host, port = _split_runtime(node.runtime)
    if host in _LOOPBACK:
        return "local", port
    if _ssh_transport(router, path, node) is not None:
        return "ssh", port
    return "unreachable", port


def _split_runtime(url):
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host or parsed.port is None:
        raise ValueError(f"runtime must be an http url with a port, got {url!r}")
    return host, int(parsed.port)


def _ssh_transport(router, path, node):
    found = None
    if router is not None and path:
        current = router
        for part in path.split("."):
            routes = getattr(current, "route", None)
            if not isinstance(routes, dict) or part not in routes:
                break
            current = routes[part]
            if getattr(current, "origin", None) == "ssh":
                found = current
    if found is not None:
        return found
    if getattr(node, "origin", None) == "ssh":
        return node
    return None


def _listening(url):
    try:
        body = health(url, timeout=0.4)
    except (OSError, RuntimeError, ValueError):
        return False
    return bool(body.get("ok"))


def _wait_until(url, timeout=10):
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            return health(url, timeout=0.4)
        except (OSError, RuntimeError, ValueError) as exc:
            last = str(exc)
            time.sleep(0.05)
    raise RuntimeError(f"runtime at {url} did not start: {last}")


def _start_local(node, url, port):
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "pyouter.node", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    node._runtime_proc = proc
    try:
        _wait_until(url)
    except Exception:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
        raise
    if proc.poll() is not None:
        raise RuntimeError(f"runtime at {url} exited {proc.returncode}")
    return {"status": "installed", "url": url, "pid": proc.pid}


def _place_ssh(node, url, port):
    script = _installer_script(port)
    args = ["-o", "BatchMode=yes"]
    if getattr(node, "port", None) is not None:
        args.extend(["-p", str(node.port)])
    if getattr(node, "identity", None):
        args.extend(["-i", node.identity, "-o", "IdentitiesOnly=yes"])
    args.extend([node.destination, "python3", "-"])
    try:
        completed = subprocess.run(
            [node.ssh, *args],
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run {node.ssh}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).decode("utf-8", "replace").strip()
        message = f"install on {node.destination} failed"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    _wait_until(url)
    return {"status": "installed", "url": url}


def _installer_script(port):
    blob = _package_b64()
    return f"""
import base64, io, os, sys, tarfile, time, urllib.request, subprocess
from pathlib import Path
PORT = {int(port)}
BLOB = {blob!r}
root = Path.home() / ".pyouter" / "runtime"
root.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(base64.b64decode(BLOB)), mode="r") as archive:
    archive.extractall(root, filter="data")
url = "http://127.0.0.1:%d/health" % PORT

def up():
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return response.status == 200
    except Exception:
        return False

if not up():
    log = open(root / "node.log", "ab")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pyouter.node", "--host", "0.0.0.0", "--port", str(PORT)],
        env=env,
        cwd=str(root),
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    (root / "node.pid").write_text(str(proc.pid))
    for _ in range(100):
        if up():
            break
        if proc.poll() is not None:
            sys.stderr.write((root / "node.log").read_text(errors="replace"))
            raise SystemExit(1)
        time.sleep(0.05)
    else:
        sys.stderr.write((root / "node.log").read_text(errors="replace"))
        raise SystemExit("runtime did not listen")
print("installed")
"""


def _package_b64():
    import base64
    import io
    import tarfile

    package = Path(__file__).resolve().parent
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        for path in sorted(package.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            archive.add(path, arcname=str(Path("pyouter") / path.relative_to(package)))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _main(argv):
    parser = argparse.ArgumentParser(prog="pyouter.node")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7710)
    parser.add_argument("--identity", default=None)
    parser.add_argument("--sn", action="append", default=[])
    parser.add_argument("--sn-listen", default=None)
    args = parser.parse_args(argv)
    serve(
        args.port,
        host=args.host,
        identity=args.identity,
        sn=args.sn,
        sn_listen=_sn_listen(args.sn_listen),
    )


def _sn_listen(value):
    if value is None:
        return None
    host, sep, port = str(value).rpartition(":")
    if sep != ":" or not host or not port.isdigit():
        raise ValueError("--sn-listen must look like 0.0.0.0:4001")
    return host, int(port)


if __name__ == "__main__":
    import sys
    _main(sys.argv[1:])
