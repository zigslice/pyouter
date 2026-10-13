"""An SSH host as a pyouter node.

The host is one node. Commands declared under it run on that host, so
``a.b.c.d`` reaches a command on the host named ``b``. Running the host
opens one connection and waits. A command under it uses that connection;
it does not open another one.
"""

import asyncio
import hashlib
import subprocess
import tempfile
import time
from pathlib import Path

from .router import Router


class Remote:
    """One command executed on an SSH host."""

    kind = "ssh"

    def __init__(self, *argv):
        if not argv or any(not isinstance(item, str) or item == "" for item in argv):
            raise ValueError("a remote command needs at least one argument")
        self.argv = tuple(argv)
        self.host = None
        self.__name__ = argv[0]

    def run(self, ctx):
        return exec_remote(self)

    def __repr__(self):
        return f"Remote({' '.join(self.argv)})"


class SSH(Router):
    """One SSH host whose commands are child routes.

    ``routes`` is the next segment, written in Python. Starting this node
    opens that segment. A :class:`Remote` runs on the host.
    A :class:`~pyouter.docker.Service` calls an address reached through a
    local forward. Nested routers add path segments, so ``b.c.d`` is node
    ``d`` under group ``c`` on host ``b``.

    Running this node opens one connection and waits. Stopping it closes
    the connection this call opened. ``forwards`` are ``ssh -L`` values,
    such as ``"8080:127.0.0.1:80"``. ``ssh`` is the ssh executable, so
    tests can substitute a fake. The connection does not ask for a password.
    """

    def __init__(self, host, routes=None, user=None, port=None, identity=None, forwards=None, ssh="ssh"):
        super().__init__()
        self.origin = "ssh"
        self.hostname = _hostname(host)
        self.user = _user(user)
        self.port = _port(port)
        self.identity = _identity(identity)
        self.forwards = _forwards(forwards)
        self.ssh = ssh
        self.destination = f"{self.user}@{self.hostname}" if self.user else self.hostname
        digest = hashlib.sha256(
            f"{id(self)}|{self.destination}|{self.port}|{self.identity}".encode("utf-8")
        ).hexdigest()[:16]
        directory = Path(tempfile.gettempdir()) / "pyouter-ssh"
        directory.mkdir(parents=True, exist_ok=True)
        self.socket = str(directory / f"{digest}.sock")
        self._owns = False
        self._master = None
        if routes is not None:
            self.include(routes)

    def include(self, router, prefix=None, host=None, port=None):
        super().include(router, prefix=prefix, host=host, port=port)
        _bind(self, self)
        return self


def exec_remote(node):
    """Run ``node`` on its SSH host.

    The connection is not opened here.
    """
    host = getattr(node, "host", None)
    if host is None:
        raise RuntimeError("command is not on an SSH host")
    if not ssh_connected(host):
        raise RuntimeError(down_message(host))
    result = _ssh(host, _client_args(host, node.argv))
    if result.out:
        print(result.out, end="" if result.out.endswith("\n") else "\n")
    if result.code != 0:
        detail = (result.err or result.out).strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        message = f"ssh exited {result.code}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    return {
        "host": host.destination,
        "argv": list(node.argv),
        "output": result.out,
    }


def ssh_connected(node):
    """Return whether ``node``'s control connection is up."""
    result = _ssh(
        node,
        ["-S", node.socket, "-O", "check", node.destination],
        check=False,
    )
    return result.code == 0


def down_message(node):
    return (
        f"ssh {node.destination} is not connected; "
        "start it by running the ssh node"
    )


async def start_ssh(node, ctx):
    """Open ``node``'s connection and keep it until cancelled.

    A second call while that connection is already up does not open
    another one. It reports that and returns. Stopping this call closes
    only a connection this call opened.
    """
    if await asyncio.to_thread(ssh_connected, node):
        print(f"ssh already connected: {node.destination}")
        from .segment import host_is_ready
        host_is_ready()
        return {"status": "connected", "host": node.destination}

    node._owns = True
    try:
        await asyncio.to_thread(_clear_socket, node)
        proc = await asyncio.to_thread(_spawn_master, node)
        node._master = proc
        await _wait_until_connected(node, proc)
        print(f"ssh {node.destination}")
        from .segment import host_is_ready
        host_is_ready()
        while await asyncio.to_thread(ssh_connected, node):
            if ctx is not None and getattr(ctx, "cancelled", False):
                break
            if proc.poll() is not None:
                break
            await asyncio.sleep(0.05)
    finally:
        if node._owns:
            await asyncio.to_thread(_disconnect, node)
            node._owns = False
            from .segment import host_is_down
            host_is_down()
    if ctx is not None and getattr(ctx, "cancelled", False):
        raise asyncio.CancelledError()
    return {"status": "stopped", "host": node.destination}


class _Result:
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err


def _ssh(node, args, check=True):
    argv = [node.ssh, *args]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run {node.ssh}") from exc
    result = _Result(completed.returncode, completed.stdout or "", completed.stderr or "")
    if check and result.code != 0:
        detail = (result.err or result.out).strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        message = "ssh failed"
        if detail:
            message = f"{message}: {detail}"
        else:
            message = f"{message} with exit {result.code}"
        raise RuntimeError(message)
    return result


def _spawn_master(node):
    try:
        return subprocess.Popen(
            [node.ssh, *_master_args(node)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run {node.ssh}") from exc


async def _wait_until_connected(node, proc):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            err = _read_finished(proc)
            detail = err.strip()
            message = f"ssh {node.destination} failed"
            if detail:
                message = f"{message}: {detail}"
            else:
                message = f"{message} with exit {code}"
            raise RuntimeError(message)
        if await asyncio.to_thread(ssh_connected, node):
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f"ssh {node.destination} did not connect")


def _read_finished(proc):
    try:
        _out, err = proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        return ""
    return err or ""


def _disconnect(node):
    proc = getattr(node, "_master", None)
    _ssh(node, ["-S", node.socket, "-O", "exit", node.destination], check=False)
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    if proc is not None and proc.stderr is not None and not proc.stderr.closed:
        proc.stderr.close()
    try:
        Path(node.socket).unlink()
    except OSError:
        pass
    node._master = None


def _clear_socket(node):
    try:
        Path(node.socket).unlink()
    except OSError:
        pass


def _common_args(node):
    args = ["-o", "BatchMode=yes"]
    if node.port is not None:
        args.extend(["-p", str(node.port)])
    if node.identity:
        args.extend(["-i", node.identity, "-o", "IdentitiesOnly=yes"])
    return args


def _master_args(node):
    args = [
        "-N",
        "-o", "ControlMaster=yes",
        "-o", f"ControlPath={node.socket}",
        "-o", "ControlPersist=no",
        "-o", "ExitOnForwardFailure=yes",
        *_common_args(node),
    ]
    for spec in node.forwards:
        args.extend(["-L", spec])
    args.append(node.destination)
    return args


def _client_args(node, argv):
    return [
        "-n",
        "-S", node.socket,
        "-o", "ControlMaster=no",
        "-o", f"ControlPath={node.socket}",
        *_common_args(node),
        node.destination,
        *argv,
    ]


def _bind(host, node):
    from .docker import Command, PublishedRoute

    origin = getattr(node, "origin", None)
    if (
        isinstance(node, Router)
        and node is not host
        and origin in {"docker", "compose", "compose-service", "ssh"}
    ):
        raise TypeError("an SSH host cannot contain another host")
    if isinstance(node, Command):
        raise TypeError("use Remote for a command on an SSH host")
    if isinstance(node, Remote):
        node.host = host
        return
    if isinstance(node, PublishedRoute):
        node.container = host
        return
    if isinstance(node, Router):
        for child in node.route.values():
            _bind(host, child)
        return
    raise TypeError("an SSH host contains Remote commands or HTTP routes")


def _hostname(host):
    if not isinstance(host, str) or not host or host.startswith("-") or "@" in host or any(ch.isspace() for ch in host):
        raise ValueError("ssh host must be a hostname or address; pass the user separately")
    return host


def _user(user):
    if user is None:
        return None
    if not isinstance(user, str) or not user or user.startswith("-") or any(ch.isspace() for ch in user):
        raise ValueError("ssh user must be a name without spaces")
    return user


def _port(port):
    if port is None:
        return None
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError("ssh port must be an integer from 1 to 65535")
    return port


def _identity(identity):
    if identity is None:
        return None
    if not isinstance(identity, str) or not identity or identity.startswith("-"):
        raise ValueError("ssh identity must be a file path")
    return identity


def _forwards(forwards):
    if forwards is None:
        return ()
    values = tuple(forwards)
    for item in values:
        if not isinstance(item, str) or item.count(":") != 2:
            raise ValueError(f"forward must look like 8080:127.0.0.1:80, got {item!r}")
        local, remote_host, remote_port = item.split(":")
        if not local.isdigit() or not remote_port.isdigit() or not remote_host or any(ch.isspace() for ch in remote_host):
            raise ValueError(f"forward must look like 8080:127.0.0.1:80, got {item!r}")
    return values
