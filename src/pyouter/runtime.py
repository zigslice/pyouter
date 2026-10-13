"""The process that executes every node.

``python app.py`` starts this process and leaves it running. A later
``python app.py <node>`` does not execute the node itself. It sends the path
to the process that is already running, waits until that node finishes, and
exits. A function, a router, a web service, and a web endpoint all take this
path.
"""

import asyncio
import hashlib
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .errors import NotFound

_writer_var = None


def _writer_context():
    global _writer_var
    if _writer_var is None:
        import contextvars
        _writer_var = contextvars.ContextVar("pyouter_client_writer", default=None)
    return _writer_var


def record_path(script=None):
    """File that records the runtime for ``script``."""
    raw = sys.argv[0] if script is None else script
    resolved = str(Path(raw).resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:20]
    return Path.home() / ".pyouter" / "run" / f"{digest}.json"


def live_record(script=None):
    """Return the runtime record when that process is still alive."""
    path = record_path(script)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = data.get("pid")
    port = data.get("port")
    if not isinstance(port, int) or not _pid_alive(pid):
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return {"pid": pid, "port": port}


def claim_record(port, script=None):
    """Create the runtime record. Return False when one is already live."""
    path = record_path(script)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "port": int(port)}).encode("utf-8")
    for _attempt in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if live_record(script) is not None:
                return False
            try:
                path.unlink()
            except OSError:
                return False
            continue
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        return True
    return False


def release_record(script=None):
    """Remove the runtime record when this process owns it."""
    path = record_path(script)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.get("pid") != os.getpid():
        return
    try:
        path.unlink()
    except OSError:
        pass


def route_cli(app):
    """Handle one command-line entry. Return True when this call is finished.

    Inspecting the tree (``--tasks``, ``--tree``) stays in the command
    process. Every execution goes to the running pyouter process.
    """
    options = app.options
    if getattr(options, "web", False):
        if live_record() is not None:
            print("pyouter already running")
            return True
        Runtime(app).serve(web=True)
        return True
    if getattr(options, "tree", False) or getattr(options, "tasks", False):
        return False
    if options.actions:
        if live_record() is None:
            _not_running()
        code = call(sys.argv[1:])
        if code is None:
            _not_running()
        if code:
            raise SystemExit(code)
        return True
    if live_record() is not None:
        print("pyouter already running")
        return True
    Runtime(app).serve(web=False)
    return True


def call(argv, script=None):
    """Send ``argv`` to the running process. Return the exit code, or None."""
    info = live_record(script)
    if info is None:
        return None
    try:
        sock = socket.create_connection(("127.0.0.1", info["port"]), timeout=5)
    except OSError:
        return None
    try:
        payload = json.dumps({"argv": [str(item) for item in argv]}, ensure_ascii=False)
        sock.sendall((payload + "\n").encode("utf-8"))
        sock.settimeout(None)
        buf = b""
        while True:
            try:
                chunk = sock.recv(65536)
            except OSError:
                return 1
            if not chunk:
                return 1
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line:
                    continue
                try:
                    message = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                if "stdout" in message and message["stdout"]:
                    sys.stdout.write(message["stdout"])
                    sys.stdout.flush()
                if "stderr" in message and message["stderr"]:
                    sys.stderr.write(message["stderr"])
                    sys.stderr.flush()
                if "exit" in message:
                    code = message["exit"]
                    return code if isinstance(code, int) else 1
    finally:
        sock.close()


def _not_running():
    print("pyouter is not running; start it with python app.py", file=sys.stderr)
    raise SystemExit(1)


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class _ClientWriter:
    def __init__(self, conn):
        self.conn = conn
        self.lock = threading.Lock()
        self.closed = False

    def send(self, stream, text):
        if text:
            self._send({stream: text})

    def exit(self, code):
        self._send({"exit": int(code)})

    def _send(self, payload):
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            if self.closed:
                return
            try:
                self.conn.sendall(data)
            except OSError:
                self.closed = True


class _RoutedStream:
    def __init__(self, original, stream_name):
        self.original = original
        self.stream_name = stream_name

    def write(self, data):
        if data is None:
            return 0
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
        if text == "":
            return 0
        writer = _writer_context().get()
        if writer is None:
            written = self.original.write(data)
            return len(text) if written is None else written
        writer.send(self.stream_name, text)
        return len(text)

    def flush(self):
        writer = _writer_context().get()
        if writer is None:
            self.original.flush()

    def isatty(self):
        return False

    def writable(self):
        return True

    def __getattr__(self, name):
        return getattr(self.original, name)


class Runtime:
    """Accept route commands and execute them on one event loop."""

    def __init__(self, app):
        self.app = app
        self.loop = None
        self.loop_thread = None
        self.sock = None
        self.stopped = threading.Event()
        self.tasks = set()
        self.lock = threading.Lock()
        self.root_future = None
        self._stdout = None
        self._stderr = None

    def serve(self, web=False):
        """Bind the command socket and block until Ctrl+C."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(32)
        port = self.sock.getsockname()[1]
        if not claim_record(port):
            self.sock.close()
            print("pyouter already running")
            return

        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(
            target=self._run_loop,
            name="pyouter-runtime",
            daemon=True,
        )
        self.loop_thread.start()
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), self.loop).result(timeout=5)
        self._install_streams()
        bridge = None
        threading.Thread(target=self._accept, name="pyouter-accept", daemon=True).start()
        try:
            if web:
                bridge = self._start_web()
            self._start_root_service()
            print("pyouter running")
            try:
                while not self.stopped.is_set():
                    time.sleep(0.25)
            except KeyboardInterrupt:
                print("\n[pyouter] stopped")
        finally:
            self.stopped.set()
            self._cancel_runs()
            if bridge is not None:
                bridge.close()
            release_record()
            try:
                self.sock.close()
            except OSError:
                pass
            if self.loop is not None and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            if self.loop_thread is not None:
                self.loop_thread.join(timeout=3)
            self._restore_streams()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _install_streams(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = _RoutedStream(self._stdout, "stdout")
        sys.stderr = _RoutedStream(self._stderr, "stderr")

    def _restore_streams(self):
        if self._stdout is not None and isinstance(sys.stdout, _RoutedStream):
            sys.stdout = self._stdout
        if self._stderr is not None and isinstance(sys.stderr, _RoutedStream):
            sys.stderr = self._stderr

    def _start_web(self):
        from .web import WebBridge

        options = self.app.options
        host = getattr(options, "host", "127.0.0.1")
        port = getattr(options, "port", 8765)
        if host not in ("127.0.0.1", "localhost", "::1"):
            print("[pyouter] warning: the web ui can run local tasks from " + host)
        bridge = WebBridge(
            self.app,
            host=host,
            port=port,
            focus=options.actions or "",
        )
        try:
            bridge.start(loop=self.loop)
        except OSError as exc:
            print(f"[pyouter] cannot bind {host}:{port}: {exc}")
            raise SystemExit(1) from exc
        print(f"[pyouter] web ui {bridge.url}")
        print("[pyouter] Ctrl+C to stop")
        if not getattr(options, "no_browser", False):
            try:
                webbrowser.open(bridge.url)
            except Exception:
                pass
        return bridge

    def _start_root_service(self):
        router = self.app.router
        if not getattr(router, "serves", False):
            return
        self.root_future = asyncio.run_coroutine_threadsafe(
            self.app.serve_root(),
            self.loop,
        )
        self.root_future.add_done_callback(_consume_future)

    def _accept(self):
        while not self.stopped.is_set():
            try:
                self.sock.settimeout(0.5)
                conn, _addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            line = _read_line(conn)
            if line is None:
                return
            try:
                request = json.loads(line.decode("utf-8"))
            except ValueError:
                return
            argv = request.get("argv")
            if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
                return
            writer = _ClientWriter(conn)
            holder = {}
            future = asyncio.run_coroutine_threadsafe(
                self._run(argv, writer, holder),
                self.loop,
            )
            watcher = threading.Thread(
                target=_watch_disconnect,
                args=(conn, future, holder, self.loop),
                daemon=True,
            )
            watcher.start()
            try:
                future.result()
            except (asyncio.CancelledError, Exception):
                writer.exit(1)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    async def _run(self, argv, writer, holder):
        token = _writer_context().set(writer)
        task = asyncio.current_task()
        holder["task"] = task
        with self.lock:
            self.tasks.add(task)
        code = 1
        try:
            try:
                options = self.app.opt_parser.parse_args(argv)
            except SystemExit as exc:
                status = exc.code
                code = 0 if status in (None, 0) else (status if isinstance(status, int) else 1)
                return
            try:
                code = await self.app.execute_options(options)
            except NotFound as exc:
                print(exc.message, file=sys.stderr)
                code = 1
            except asyncio.CancelledError:
                print("\n[pyouter] stopped")
                code = 130
            except Exception as exc:
                print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
                code = 1
        finally:
            with self.lock:
                self.tasks.discard(task)
            writer.exit(code)
            _writer_context().reset(token)

    def _cancel_runs(self):
        future = self.root_future
        if future is not None and not future.done():
            future.cancel()
        with self.lock:
            tasks = list(self.tasks)
        loop = self.loop
        if loop is None or not loop.is_running():
            return
        for task in tasks:
            loop.call_soon_threadsafe(task.cancel)
        if tasks or (future is not None and not future.done()):
            time.sleep(0.3)


def _consume_future(done):
    if done.cancelled():
        return
    done.exception()


def _read_line(conn):
    conn.settimeout(5)
    buf = b""
    while b"\n" not in buf:
        try:
            chunk = conn.recv(4096)
        except OSError:
            return None
        if not chunk:
            return None
        buf += chunk
        if len(buf) > 1_000_000:
            return None
    line, _rest = buf.split(b"\n", 1)
    return line


def _watch_disconnect(conn, future, holder, loop):
    """Cancel the running node when the command process goes away."""
    conn.settimeout(0.2)
    while not future.done():
        try:
            data = conn.recv(1)
        except socket.timeout:
            continue
        except OSError:
            break
        if data == b"":
            task = holder.get("task")
            if task is not None and loop is not None and loop.is_running():
                loop.call_soon_threadsafe(task.cancel)
            else:
                future.cancel()
            break
