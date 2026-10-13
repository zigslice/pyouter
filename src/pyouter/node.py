"""The runtime that stays up on a physical node.

A node listens before any orchestration arrives. The control process
pushes one layer of the tree to that listener. The runtime starts the
layer's pool and then accepts calls for it. Pushing a new slice replaces
the pool that was serving.

This is not a cluster scheduler. The tree already says which runtime
receives which layer. The runtime only installs the slice it is given and
starts serving.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .balance import normalize_balancer, normalize_workers, start_pool
from .layer import layers_of


class _Service:
    def __init__(self):
        self.lock = threading.Lock()
        self.pool = None
        self.spec = None

    def deploy(self, spec):
        path = spec.get("path")
        kind = spec.get("kind")
        if not isinstance(path, str) or path == "":
            raise ValueError("deploy needs a path")
        if kind not in {"docker", "ssh", "server"}:
            raise ValueError("deploy needs a layer kind")
        balancer = normalize_balancer(spec.get("balancer"))
        workers = normalize_workers(spec.get("workers"))
        pool = start_pool(provider=balancer, workers=workers)
        with self.lock:
            previous = self.pool
            self.pool = pool
            self.spec = {
                "path": path,
                "kind": kind,
                "balancer": balancer,
                "workers": workers,
                "port": pool.port,
            }
        if previous is not None:
            previous.close()
        return dict(self.spec)

    def call(self, payload):
        with self.lock:
            pool = self.pool
        if pool is None:
            raise RuntimeError("node has no deployment")
        return pool.call(payload)

    def health(self):
        with self.lock:
            spec = dict(self.spec) if self.spec else None
        if spec is None:
            return {"ok": True, "deployed": False}
        spec["ok"] = True
        spec["deployed"] = True
        return spec

    def close(self):
        with self.lock:
            pool = self.pool
            self.pool = None
            self.spec = None
        if pool is not None:
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


def serve(port=0):
    """Listen for a slice and serve it. Return the bound port."""
    global _httpd
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), _Handler)
    _httpd = server
    bound = server.server_address[1]
    print(f"node {bound}", flush=True)
    try:
        server.serve_forever()
    finally:
        _service.close()
        server.server_close()
    return bound


def push(url, layer):
    """Push one layer slice to the runtime at ``url``."""
    body = {
        "path": layer.path,
        "kind": layer.kind,
        "balancer": layer.balancer,
        "workers": layer.workers,
    }
    return _post(url, "/deploy", body)


def deploy_tree(router):
    """Push every layer to the runtime named on that layer."""
    sent = []
    for layer in layers_of(router):
        target = _at(router, layer.path)
        url = getattr(target, "runtime", None)
        if not isinstance(url, str) or url == "":
            raise ValueError(f"{layer.path} has no runtime")
        sent.append(push(url, layer))
    return sent


def call(url, payload, timeout=30):
    """Send one call to a runtime that already has a deployment."""
    return _post(url, "/call", payload, timeout=timeout)


def health(url):
    return _post(url, "/health", None, timeout=5, method="GET")


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


def _main(argv):
    parser = argparse.ArgumentParser(prog="pyouter.node")
    parser.add_argument("--port", type=int, default=7710)
    args = parser.parse_args(argv)
    serve(args.port)


if __name__ == "__main__":
    import sys
    _main(sys.argv[1:])
