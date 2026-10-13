"""Local web ui for browsing and running a pyouter router.

Start it from the command line with ``python app.py --web`` or from Python
with ``app.web()``. The page binds to localhost by default.
"""

import asyncio
import contextvars
import inspect
import json
import os
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pyouter.context import Context, Hooks
from pyouter.errors import NotFound, NotInit
from pyouter.router import Router, execute, walk
from pyouter.web_page import render_page

current_log_path = contextvars.ContextVar("pyouter_web_log_path", default=None)


def _console(message):
    stream = sys.__stdout__
    stream.write(message + "\n")
    stream.flush()


def _overlaps(left, right):
    if left == right:
        return True
    if left == "" or right == "":
        return True
    return left.startswith(right + ".") or right.startswith(left + ".")


def describe(node):
    if isinstance(node, Router):
        return {"kind": "router", "target": "Router", "signature": "", "doc": ""}

    if inspect.isfunction(node) or inspect.ismethod(node):
        target = getattr(node, "__name__", "function")
        try:
            signature = str(inspect.signature(node))
        except (TypeError, ValueError):
            signature = ""
        return {
            "kind": "function",
            "target": target,
            "signature": signature,
            "doc": inspect.getdoc(node) or "",
        }

    target = type(node).__name__
    try:
        signature = str(inspect.signature(node.run))
    except (TypeError, ValueError, AttributeError):
        signature = ""
    return {
        "kind": "object",
        "target": target,
        "signature": signature,
        "doc": inspect.getdoc(node) or inspect.getdoc(type(node)) or "",
    }


def build_tree(router):
    def build(node, name, path):
        info = describe(node)
        children = []
        if isinstance(node, Router):
            for key, child in node.route.items():
                child_path = f"{path}.{key}" if path else key
                children.append(build(child, key, child_path))
        return {
            "name": name,
            "path": path,
            "type": "router" if isinstance(node, Router) else "action",
            "kind": info["kind"],
            "target": info["target"],
            "signature": info["signature"],
            "doc": info["doc"],
            "children": children,
        }

    return build(router, "(root)", "")


@dataclass
class NodeState:
    path: str
    status: str = "idle"
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    owner: str | None = None
    logs: list = field(default_factory=list)

    def to_json(self):
        return {
            "path": self.path,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "owner": self.owner,
            "logs": list(self.logs),
        }


class RunStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.nodes = {}
        self.events = []
        self.seq = 0
        self.partial = {}

    def seed(self, router):
        with self.lock:
            for path, _node in walk(router, ""):
                self.nodes[path] = NodeState(path=path)

    def reserve(self, root, paths):
        with self.lock:
            for rec in self.nodes.values():
                if rec.status in ("running", "pending") and _overlaps(rec.path, root):
                    return False
            for path in paths:
                rec = self.nodes[path]
                rec.status = "pending"
                rec.error = None
                rec.started_at = None
                rec.finished_at = None
                rec.owner = root
                rec.logs.clear()
                self.partial.pop((path, "stdout"), None)
                self.partial.pop((path, "stderr"), None)
                self._emit_unlocked({"type": "reset", "path": path})
                self._emit_status_unlocked(rec)
            return True

    def mark_running(self, path):
        with self.lock:
            rec = self.nodes[path]
            rec.status = "running"
            rec.started_at = time.time()
            rec.finished_at = None
            rec.error = None
            self._emit_status_unlocked(rec)

    def mark_done(self, path, status, error):
        with self.lock:
            rec = self.nodes[path]
            rec.status = status
            rec.error = error
            rec.finished_at = time.time()
            if rec.started_at is None:
                rec.started_at = rec.finished_at
            self._emit_status_unlocked(rec)

    def cancel_unfinished(self, root):
        with self.lock:
            for rec in self.nodes.values():
                if rec.owner != root and rec.path != root:
                    continue
                if rec.status in ("running", "pending"):
                    rec.status = "cancelled"
                    rec.finished_at = time.time()
                    if rec.started_at is None:
                        rec.started_at = rec.finished_at
                    self._emit_status_unlocked(rec)

    def fail_if_unfinished(self, root, error):
        with self.lock:
            for rec in self.nodes.values():
                if rec.owner != root and rec.path != root:
                    continue
                if rec.status in ("running", "pending"):
                    rec.status = "error"
                    rec.error = error
                    rec.finished_at = time.time()
                    if rec.started_at is None:
                        rec.started_at = rec.finished_at
                    self._emit_status_unlocked(rec)

    def log(self, path, stream, message):
        text = "" if message is None else str(message)
        lines = text.splitlines() or [""]
        for line in lines:
            self.append_log(path, stream, line)

    def append_log(self, path, stream, message):
        with self.lock:
            self._append_unlocked(path, stream, message)

    def write_chunk(self, path, stream, data):
        with self.lock:
            key = (path, stream)
            buf = self.partial.get(key, "") + data
            lines = buf.split("\n")
            self.partial[key] = lines[-1]
            for line in lines[:-1]:
                self._append_unlocked(path, stream, line)

    def flush_stream(self, path, stream):
        with self.lock:
            key = (path, stream)
            buf = self.partial.pop(key, "")
            if buf:
                self._append_unlocked(path, stream, buf)

    def flush_path(self, path):
        self.flush_stream(path, "stdout")
        self.flush_stream(path, "stderr")

    def owner_of(self, path):
        with self.lock:
            rec = self.nodes.get(path)
            if rec is None:
                return None
            return rec.owner

    def is_active(self, path):
        with self.lock:
            rec = self.nodes.get(path)
            return rec is not None and rec.status in ("running", "pending")

    def snapshot_nodes(self):
        with self.lock:
            return {path: rec.to_json() for path, rec in self.nodes.items()}

    def events_since(self, since):
        with self.lock:
            if self.events and since and since < self.events[0]["seq"] - 1:
                return {"gap": True, "seq": self.seq, "events": []}
            events = [event for event in self.events if event["seq"] > since]
            return {"gap": False, "seq": self.seq, "events": events}

    def _append_unlocked(self, path, stream, message):
        rec = self.nodes.get(path)
        if rec is None:
            rec = NodeState(path=path)
            self.nodes[path] = rec
        rec.logs.append({
            "ts": time.time(),
            "stream": stream,
            "message": message,
        })
        if len(rec.logs) > 2000:
            rec.logs = rec.logs[-2000:]
        self._emit_unlocked({
            "type": "log",
            "path": path,
            "stream": stream,
            "message": message,
        })

    def _emit_status_unlocked(self, rec):
        self._emit_unlocked({
            "type": "status",
            "path": rec.path,
            "status": rec.status,
            "error": rec.error,
            "started_at": rec.started_at,
            "finished_at": rec.finished_at,
            "owner": rec.owner,
        })

    def _emit_unlocked(self, event):
        self.seq += 1
        payload = dict(event)
        payload["seq"] = self.seq
        payload.setdefault("ts", time.time())
        self.events.append(payload)
        if len(self.events) > 5000:
            self.events = self.events[-4000:]


class CaptureStream:
    def __init__(self, store, stream, original):
        self.store = store
        self.stream = stream
        self.original = original

    def write(self, data):
        if data is None:
            return 0
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        else:
            data = str(data)
        if data == "":
            return 0
        path = current_log_path.get()
        if path is None:
            written = self.original.write(data)
            return len(data) if written is None else written
        self.store.write_chunk(path, self.stream, data)
        return len(data)

    def flush(self):
        path = current_log_path.get()
        if path is None:
            self.original.flush()
            return
        self.store.flush_stream(path, self.stream)

    def isatty(self):
        return False

    def writable(self):
        return True

    def __getattr__(self, name):
        return getattr(self.original, name)


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class WebBridge:
    def __init__(self, app, host="127.0.0.1", port=8765, focus=""):
        if getattr(app, "router", None) is None:
            raise NotInit("self.router in App")
        self.app = app
        self.router = app.router
        self.config = app.config
        self.options = app.options
        self.executor = app.executor
        self.host = host
        self.port = port
        self.focus = focus or ""
        self.script = os.path.basename(sys.argv[0]) or "pyouter"
        self.tree = build_tree(self.router)
        self.store = RunStore()
        self.store.seed(self.router)
        self.loop = None
        self.loop_thread = None
        self.httpd = None
        self.http_thread = None
        self.tasks = {}
        self.contexts = {}
        self.cancel_requested = set()
        self.tasks_lock = threading.Lock()
        self.hooks = self._make_hooks()
        self._stdout = None
        self._stderr = None
        self._capture_on = False
        self._closed = False

    def install_capture(self):
        if self._capture_on:
            return
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = CaptureStream(self.store, "stdout", self._stdout)
        sys.stderr = CaptureStream(self.store, "stderr", self._stderr)
        self._capture_on = True

    def restore_capture(self):
        if not self._capture_on:
            return
        if getattr(sys.stdout, "store", None) is self.store:
            sys.stdout = self._stdout
        if getattr(sys.stderr, "store", None) is self.store:
            sys.stderr = self._stderr
        self._capture_on = False

    def resolve(self, path):
        raw = "" if path is None else str(path).strip()
        if raw in ("", ".", "/"):
            return self.router, ""
        node, norm, _hops = self.router.resolve(raw)
        return node, norm

    def _make_hooks(self):
        hooks = Hooks()
        hooks.before.append(self._on_before)
        hooks.after.append(self._on_after)
        return hooks

    def _on_before(self, event):
        if event["role"] not in ("fanout", "action"):
            return
        path = event["path"]
        event["token"] = current_log_path.set(path)
        self.store.mark_running(path)
        node = event["node"]
        if event["role"] == "fanout":
            count = len(node.route) if isinstance(node, Router) else 0
            self.store.log(path, "meta", f"开始执行路由，共 {count} 个子节点")
        else:
            info = describe(node)
            self.store.log(path, "meta", f"开始执行 {info['target']}")

    def _on_after(self, event):
        if event["role"] not in ("fanout", "action"):
            return
        path = event["path"]
        result = event["result"]
        self.store.flush_path(path)
        if result is None:
            status = "error"
            error = "missing result"
        else:
            status = result.status
            error = None if status == "success" else result.error
        if status == "error":
            if event["role"] == "fanout":
                self.store.log(path, "stderr", "" if error is None else str(error))
            else:
                text = event.get("traceback") or ("" if error is None else str(error))
                self.store.log(path, "stderr", text)
            self.store.mark_done(path, "error", None if error is None else str(error))
        elif status == "cancelled":
            self.store.mark_done(path, "cancelled", None)
        else:
            self.store.mark_done(path, status if status in ("success", "error", "cancelled") else "success", error)
        token = event.get("token")
        if token is not None:
            current_log_path.reset(token)
            event["token"] = None

    def snapshot(self):
        return {
            "tree": self.tree,
            "nodes": self.store.snapshot_nodes(),
            "seq": self.store.seq,
            "focus": self.focus,
            "script": self.script,
        }

    def request_run(self, path):
        try:
            node, norm = self.resolve(path)
        except NotFound:
            return 404, {"ok": False, "error": f"路径不存在: {path}"}
        paths = [item_path for item_path, _node in walk(node, norm)]
        if not self.store.reserve(norm, paths):
            return 409, {"ok": False, "error": "该节点或上下级节点正在执行"}
        with self.tasks_lock:
            self.cancel_requested.discard(norm)
        future = asyncio.run_coroutine_threadsafe(
            self._execute_reserved(node, norm),
            self.loop,
        )
        future.add_done_callback(lambda done, owner=norm: self._on_done(owner, done))
        return 202, {"ok": True, "path": norm}

    def request_stop(self, path):
        try:
            _node, norm = self.resolve(path)
        except NotFound:
            return 404, {"ok": False, "error": f"路径不存在: {path}"}
        owner = self.store.owner_of(norm)
        if owner is None:
            owner = norm
        with self.tasks_lock:
            active = self.store.is_active(owner) or self.store.is_active(norm)
            task = self.tasks.get(owner)
            ctx = self.contexts.get(owner)
            if task is None and not active:
                return 409, {"ok": False, "error": "没有正在执行的任务"}
            if task is None:
                self.cancel_requested.add(owner)
        if ctx is not None:
            ctx.cancel()
        if task is not None:
            self.loop.call_soon_threadsafe(task.cancel)
        return 202, {"ok": True, "path": owner}

    async def execute_path(self, path):
        """Run a path on the current event loop. Used by tests and the server."""
        node, norm = self.resolve(path)
        paths = [item_path for item_path, _node in walk(node, norm)]
        if not self.store.reserve(norm, paths):
            raise RuntimeError("该节点或上下级节点正在执行")
        await self._execute_reserved(node, norm)

    async def _execute_reserved(self, node, path):
        with self.tasks_lock:
            if path in self.cancel_requested:
                self.cancel_requested.discard(path)
                cancelled = True
            else:
                self.tasks[path] = asyncio.current_task()
                cancelled = False
        if cancelled:
            self.store.cancel_unfinished(path)
            raise asyncio.CancelledError()
        ctx = Context(self.config, self.options, self.executor, self.hooks)
        with self.tasks_lock:
            self.contexts[path] = ctx
        try:
            result = await execute(node, path, 0, ctx)
            if result.status == "error":
                raise RuntimeError(result.error or "error")
        except asyncio.CancelledError:
            self.store.cancel_unfinished(path)
            raise
        finally:
            with self.tasks_lock:
                current = self.tasks.get(path)
                if current is asyncio.current_task():
                    self.tasks.pop(path, None)
                self.contexts.pop(path, None)

    def _on_done(self, owner, future):
        try:
            future.result()
        except asyncio.CancelledError:
            self.store.cancel_unfinished(owner)
        except Exception as exc:
            self.store.fail_if_unfinished(owner, str(exc))
        finally:
            with self.tasks_lock:
                self.cancel_requested.discard(owner)

    def start(self):
        self.install_capture()
        try:
            self.loop = asyncio.new_event_loop()
            self.loop_thread = threading.Thread(
                target=self._run_loop,
                name="pyouter-web-loop",
                daemon=True,
            )
            self.loop_thread.start()
            asyncio.run_coroutine_threadsafe(asyncio.sleep(0), self.loop).result(timeout=5)
            self.httpd = ReuseHTTPServer((self.host, self.port), partial(Handler, bridge=self))
            self.port = self.httpd.server_address[1]
            self.http_thread = threading.Thread(
                target=self.httpd.serve_forever,
                name="pyouter-web-http",
                daemon=True,
            )
            self.http_thread.start()
        except Exception:
            self.close()
            raise

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def close(self):
        if self._closed:
            self.restore_capture()
            return
        self._closed = True
        with self.tasks_lock:
            tasks = list(self.tasks.values())
            contexts = list(self.contexts.values())
        for ctx in contexts:
            ctx.cancel()
        if self.loop is not None and self.loop.is_running():
            for task in tasks:
                self.loop.call_soon_threadsafe(task.cancel)
        if self.httpd is not None:
            if self.http_thread is not None and self.http_thread.is_alive():
                self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.http_thread is not None:
            self.http_thread.join(timeout=3)
            self.http_thread = None
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.loop_thread is not None:
            self.loop_thread.join(timeout=3)
            self.loop_thread = None
        self.restore_capture()

    @property
    def url(self):
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.port}"

    def page(self):
        return render_page({"focus": self.focus, "script": self.script})


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, bridge=None, **kwargs):
        self.bridge = bridge
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        sys.__stderr__.write("[pyouter] %s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = self.bridge.page().encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return
        if parsed.path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if parsed.path == "/api/snapshot":
            self._send_json(200, self.bridge.snapshot())
            return
        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            raw = query.get("since", ["0"])[0]
            try:
                since = int(raw)
            except ValueError:
                self._send_json(400, {"ok": False, "error": "since 必须是整数"})
                return
            self._send_json(200, self.bridge.store.events_since(since))
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        path = body.get("path", "")
        if not isinstance(path, str):
            self._send_json(400, {"ok": False, "error": "path 必须是字符串"})
            return
        if parsed.path == "/api/run":
            status, payload = self.bridge.request_run(path)
            self._send_json(status, payload)
            return
        if parsed.path == "/api/stop":
            status, payload = self.bridge.request_stop(path)
            self._send_json(status, payload)
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > 65536:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("无效的 JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON 必须是对象")
        return data

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if body:
            self.wfile.write(body)


def serve(app, host="127.0.0.1", port=8765, open_browser=True, focus=None):
    """Bind a local web ui and block until Ctrl+C."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        _console("[pyouter] warning: the web ui can run local tasks from " + host)

    bridge = WebBridge(app, host=host, port=port, focus=focus or "")
    try:
        bridge.start()
    except OSError as exc:
        _console(f"[pyouter] cannot bind {host}:{port}: {exc}")
        raise SystemExit(1) from exc

    url = bridge.url
    _console(f"[pyouter] web ui {url}")
    _console("[pyouter] Ctrl+C to stop")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        while bridge.http_thread is not None and bridge.http_thread.is_alive():
            bridge.http_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        _console("\n[pyouter] web ui stopped")
    finally:
        bridge.close()
