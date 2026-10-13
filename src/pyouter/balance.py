"""Load balancers for one layer.

A layer names a provider. The default provider is ``uvicorn``. Calling code
and the route tree talk about ``balancer`` and ``workers``. The provider is
the only place that knows how the processes are started.

``start_pool`` listens on one port. Concurrent calls are spread across the
pool's processes. ``hold`` seconds in a call occupy that process, which is
how a measurement shows that more workers finish concurrent work sooner.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
import urllib.error
import urllib.request


_PROVIDERS = {}


class Pool:
    """One running balancer."""

    def __init__(self, provider, workers, port, proc):
        self.provider = provider
        self.workers = workers
        self.port = port
        self.proc = proc

    def call(self, payload, timeout=30):
        return call_port(self.port, payload, timeout=timeout)

    def close(self):
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except OSError:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            proc.wait(timeout=5)
        if proc.stderr is not None:
            proc.stderr.close()


def register_provider(name, start):
    """Register ``start(workers, port) -> proc`` under ``name``."""
    if not isinstance(name, str) or name == "":
        raise ValueError("balancer name must be a non-empty string")
    _PROVIDERS[name] = start


def normalize_balancer(name):
    if name is None or name == "":
        return "uvicorn"
    if not isinstance(name, str):
        raise ValueError("balancer must be a provider name")
    return name


def normalize_workers(value):
    if value is None:
        return 1
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("workers must be a positive integer")
    return value


def start_pool(provider="uvicorn", workers=1, port=None):
    """Start ``workers`` processes for ``provider`` and wait until they listen."""
    provider = normalize_balancer(provider)
    workers = normalize_workers(workers)
    start = _PROVIDERS.get(provider)
    if start is None:
        known = ", ".join(sorted(_PROVIDERS)) or "none"
        raise ValueError(f"unknown balancer {provider!r}; known providers: {known}")
    chosen = _free_port() if port is None else int(port)
    proc = start(workers, chosen)
    deadline = time.monotonic() + 20
    last = ""
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            err = ""
            if proc.stderr is not None:
                err = proc.stderr.read().decode("utf-8", "replace")
            raise RuntimeError(f"balancer {provider} exited {proc.returncode}: {err}")
        try:
            body = call_port(chosen, None, path="/health", timeout=0.5)
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            last = str(exc)
            time.sleep(0.05)
            continue
        if body.get("ok"):
            return Pool(provider, workers, chosen, proc)
        time.sleep(0.05)
    raise RuntimeError(f"balancer {provider} did not listen on {chosen}: {last}")


def call_port(port, payload, timeout=30, path="/call"):
    data = b"" if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(port)}{path}",
        data=data if path == "/call" else None,
        method="POST" if path == "/call" else "GET",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(detail or f"balancer returned {exc.code}") from exc
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def boot_argv(node, port=7711):
    """The command a layer runs to start its own balancer."""
    provider = normalize_balancer(getattr(node, "balancer", None))
    workers = normalize_workers(getattr(node, "workers", None))
    return [
        "python",
        "-m",
        "pyouter.balance",
        "--provider",
        provider,
        "--workers",
        str(workers),
        "--port",
        str(int(port)),
    ]


def _start_uvicorn(workers, port):
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pyouter.balance",
            "--provider",
            "uvicorn",
            "--workers",
            str(workers),
            "--port",
            str(port),
        ],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return proc


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def application(scope, receive, send):
    """One call occupies the worker that accepted it."""
    if scope.get("type") != "http":
        return
    path = scope.get("path") or ""
    if path == "/health":
        await _respond(send, 200, {"ok": True, "pid": os.getpid()})
        return
    if path != "/call":
        await _respond(send, 404, {"error": "not found"})
        return
    raw = await _read_body(receive)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    hold = payload.get("hold") or 0
    try:
        hold = float(hold)
    except (TypeError, ValueError):
        hold = 0
    if hold > 0:
        time.sleep(min(hold, 2.0))
    await _respond(send, 200, {"pid": os.getpid(), "path": payload.get("path") or ""})


async def _read_body(receive):
    chunks = []
    while True:
        message = await receive()
        if message.get("type") != "http.request":
            break
        chunk = message.get("body") or b""
        if chunk:
            chunks.append(chunk)
        if not message.get("more_body"):
            break
    return b"".join(chunks)


async def _respond(send, status, payload):
    body = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({"type": "http.response.body", "body": body})


def _main(argv):
    parser = argparse.ArgumentParser(prog="pyouter.balance")
    parser.add_argument("--provider", default="uvicorn")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    provider = normalize_balancer(args.provider)
    workers = normalize_workers(args.workers)
    if provider != "uvicorn":
        raise SystemExit(f"unknown balancer {provider!r}")
    import uvicorn

    uvicorn.run(
        "pyouter.balance:application",
        host="127.0.0.1",
        port=args.port,
        workers=workers,
        log_level="warning",
        access_log=False,
    )


register_provider("uvicorn", _start_uvicorn)


if __name__ == "__main__":
    _main(sys.argv[1:])
