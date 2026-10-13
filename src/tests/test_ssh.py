import asyncio
import io
import json
import sys
import tempfile
import textwrap
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from pyouter.app import App
from pyouter.context import Context
from pyouter.docker import Command, Container, Service
from pyouter.router import Router, node_kind
from pyouter.ssh import Remote, SSH, ssh_connected, start_ssh
from pyouter.web import WebBridge, build_tree
from pyouter.web_page import render_page


def options(**extra):
    values = dict(
        debug=False,
        view=False,
        tree=False,
        tasks=False,
        actions=None,
        web=False,
    )
    values.update(extra)
    return SimpleNamespace(**values)


class _stdio:
    def __init__(self, stdout, stderr=None):
        self.stdout = stdout
        self.stderr = stderr

    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self.stdout
        if self.stderr is not None:
            sys.stderr = self.stderr
        return self

    def __exit__(self, exc_type, exc, tb):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return False


def write_fake_ssh(directory):
    state = Path(directory) / "state.json"
    script = Path(directory) / "ssh"
    script.write_text(textwrap.dedent(f'''
        #!/usr/bin/env python3
        import json
        import os
        import sys
        import time

        path = {str(state)!r}

        def load():
            if not os.path.exists(path):
                return {{}}
            with open(path) as handle:
                return json.load(handle)

        def save(data):
            with open(path, "w") as handle:
                json.dump(data, handle)

        argv = sys.argv[1:]
        options = {{}}
        flags = set()
        positionals = []
        index = 0
        valued = {{"-S", "-O", "-p", "-i", "-L", "-o"}}
        while index < len(argv):
            item = argv[index]
            if item in valued and index + 1 < len(argv):
                options.setdefault(item, []).append(argv[index + 1])
                index += 2
                continue
            if item.startswith("-"):
                flags.add(item)
                index += 1
                continue
            positionals.append(item)
            index += 1

        def socket_path():
            if options.get("-S"):
                return options["-S"][-1]
            for pair in options.get("-o", []):
                key, _, value = pair.partition("=")
                if key == "ControlPath":
                    return value
            return None

        control = socket_path()
        if not control:
            sys.exit(2)
        data = load()
        sessions = data.setdefault("sessions", {{}})
        if "-N" in flags:
            if sessions.get(control, {{}}).get("running"):
                sys.stderr.write("already connected\\n")
                sys.exit(1)
            sessions[control] = {{
                "running": True,
                "exec": [],
                "forwards": options.get("-L", []),
                "identity": (options.get("-i") or [None])[-1],
                "port": (options.get("-p") or [None])[-1],
                "destination": positionals[0] if positionals else "",
            }}
            save(data)
            while True:
                time.sleep(0.05)
                current = load().get("sessions", {{}}).get(control)
                if not current or not current.get("running"):
                    break
            sys.exit(0)
        operation = (options.get("-O") or [None])[-1]
        if operation == "check":
            info = sessions.get(control)
            sys.exit(0 if info and info.get("running") else 1)
        if operation == "exit":
            sessions.pop(control, None)
            save(data)
            sys.exit(0)
        info = sessions.get(control)
        if not info or not info.get("running"):
            sys.stderr.write("not connected\\n")
            sys.exit(1)
        command = positionals[1:]
        if not command:
            sys.exit(2)
        info["exec"].append(command)
        save(data)
        if command[:1] == ["echo"]:
            sys.stdout.write(" ".join(command[1:]) + "\\n")
        else:
            sys.stdout.write(" ".join(command) + "\\n")
        sys.exit(0)
    ''').lstrip())
    script.chmod(0o755)
    return script, state


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


class running_ssh:
    def __init__(self, node):
        self.node = node
        self.ctx = Context({}, options())
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.task = None
        self.thread = None
        self.failure = None

    def __enter__(self):
        self.thread = threading.Thread(target=self._main, daemon=True)
        self.thread.start()
        if not self.ready.wait(8):
            self._stop()
            raise RuntimeError("timed out waiting for the ssh connection")
        if self.failure is not None:
            self._stop()
            raise self.failure
        if not ssh_connected(self.node):
            self._stop()
            raise RuntimeError("ssh is not connected")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop()
        return False

    def _main(self):
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(start_ssh(self.node, self.ctx))

        async def watch():
            for _ in range(200):
                if self.task.done() or ssh_connected(self.node):
                    return
                await asyncio.sleep(0.025)

        try:
            self.loop.run_until_complete(watch())
            self.ready.set()
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.failure = exc
            self.ready.set()
        finally:
            if self.task is not None and not self.task.done():
                self.task.cancel()
                try:
                    self.loop.run_until_complete(self.task)
                except (asyncio.CancelledError, Exception):
                    pass
            if not self.loop.is_closed():
                self.loop.close()

    def _stop(self):
        self.ctx.cancel()
        loop = self.loop
        if loop.is_running():
            def cancel():
                if self.task is not None and not self.task.done():
                    self.task.cancel()
            loop.call_soon_threadsafe(cancel)
        if self.thread is not None:
            self.thread.join(5)


class SSHTest(unittest.TestCase):
    def test_ssh_host_reaches_a_remote_command(self):
        with tempfile.TemporaryDirectory() as directory:
            binary, state = write_fake_ssh(directory)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            identity = str(Path(directory) / "id_ed25519")
            forward = f"18080:127.0.0.1:{port}"
            try:
                host = SSH(
                    "10.0.0.8",
                    user="deploy",
                    port=22,
                    identity=identity,
                    forwards=(forward,),
                    ssh=str(binary),
                    routes=Router(
                        c=Router(d=Remote("echo", "deep")),
                        api=Service(
                            f"http://127.0.0.1:{port}",
                            health=("GET", "/health"),
                        ),
                    ),
                )
                app = App(config={})
                app.include(Router(a=Router(b=host)))
                self.assertEqual(node_kind(app.router.route["a"].route["b"]), "ssh")
                command = host.route["c"].route["d"]
                self.assertEqual(node_kind(command), "ssh")
                self.assertIs(command.host, host)
                self.assertEqual(sorted(app.router.tasks()), ["a.b.api.health", "a.b.c.d"])
                ctx = Context({}, options())
                with self.assertRaises(RuntimeError) as caught:
                    command.run(ctx)
                self.assertIn("ssh deploy@10.0.0.8 is not connected", str(caught.exception))
                health = host.route["api"].route["health"]
                with self.assertRaises(RuntimeError) as caught:
                    health.run(ctx)
                self.assertIn("not connected", str(caught.exception))

                with running_ssh(host):
                    stdout = io.StringIO()
                    with _stdio(stdout):
                        again = asyncio.run(start_ssh(host, Context({}, options())))
                    self.assertEqual(again, {"status": "connected", "host": "deploy@10.0.0.8"})
                    self.assertIn("ssh already connected: deploy@10.0.0.8", stdout.getvalue())
                    stdout = io.StringIO()
                    with _stdio(stdout):
                        value = command.run(ctx)
                    self.assertEqual(value["output"].strip(), "deep")
                    self.assertEqual(value["host"], "deploy@10.0.0.8")
                    self.assertIn("deep", stdout.getvalue())
                    recorded = json.loads(state.read_text())
                    session = recorded["sessions"][host.socket]
                    self.assertEqual(session["exec"], [["echo", "deep"]])
                    self.assertEqual(session["forwards"], [forward])
                    self.assertEqual(session["identity"], identity)
                    self.assertEqual(session["port"], "22")
                    self.assertEqual(session["destination"], "deploy@10.0.0.8")

                    app.options = options(actions="a.b.api.health")
                    with _stdio(io.StringIO()):
                        app.run()
                    self.assertEqual(app.result.root.value["body"], {"path": "/health"})

                    tree = build_tree(app.router)
                    node = _find(tree, "a.b")
                    self.assertEqual(node["route_type"], "ssh")
                    self.assertEqual(node["target"], "deploy@10.0.0.8")
                    deep = _find(tree, "a.b.c.d")
                    self.assertEqual(deep["kind"], "ssh")
                    self.assertEqual(deep["target"], "echo deep")

                self.assertNotIn(host.socket, json.loads(state.read_text() or "{}").get("sessions", {}))
                with self.assertRaises(RuntimeError) as caught:
                    command.run(ctx)
                self.assertIn("not connected", str(caught.exception))
            finally:
                httpd.shutdown()
                thread.join(3)
                httpd.server_close()

    def test_bridge_runs_a_command_while_the_host_stays_connected(self):
        with tempfile.TemporaryDirectory() as directory:
            binary, _state = write_fake_ssh(directory)
            host = SSH(
                "10.0.0.8",
                user="deploy",
                ssh=str(binary),
                routes=Router(c=Router(d=Remote("echo", "deep"))),
            )
            app = App(config={})
            app.include(Router(a=Router(b=host)))
            app.options = options()
            bridge = WebBridge(app, host="127.0.0.1", port=0, focus="a.b.c.d")
            bridge.install_capture()
            try:
                with running_ssh(host):
                    asyncio.run(bridge.execute_path("a.b.c.d"))
                self.assertEqual(bridge.store.nodes["a.b.c.d"].status, "success")
                messages = [line["message"] for line in bridge.store.nodes["a.b.c.d"].logs]
                self.assertTrue(any("deep" in message for message in messages))
                self.assertEqual(bridge.store.nodes["a.b"].status, "idle")
            finally:
                bridge.close()

    def test_page_names_the_host_and_the_remote_command(self):
        page = render_page({"focus": "", "script": "app.py"})
        self.assertIn("主机", page)
        self.assertIn("远程", page)

    def test_rejects_a_bad_host_and_a_dropped_host_node(self):
        with self.assertRaises(ValueError):
            SSH("user@10.0.0.8")
        with self.assertRaises(ValueError):
            SSH("-bad")
        with self.assertRaises(ValueError):
            SSH("10.0.0.8", port=0)
        with self.assertRaises(ValueError):
            SSH("10.0.0.8", forwards=("8080:80",))
        with self.assertRaises(TypeError):
            SSH("10.0.0.8", routes=Router(ping=Command("echo", "x")))
        nested = SSH("10.0.0.8", routes=Router(box=Container("alpine", command=("sleep", "infinity"))))
        self.assertEqual(nested.route["box"].layer, "docker")
        with self.assertRaises(TypeError):
            SSH("10.0.0.8", routes=Router(jump=SSH("10.0.0.9")))
        with self.assertRaises(ValueError):
            Remote()
        app = App(config={})
        with self.assertRaises(ValueError):
            app.include(SSH("10.0.0.8"))
        with self.assertRaises(RuntimeError) as caught:
            Remote("echo", "x").run(Context({}, options()))
        self.assertIn("not on an SSH host", str(caught.exception))


def _find(node, path):
    if node["path"] == path:
        return node
    for child in node["children"]:
        found = _find(child, path)
        if found is not None:
            return found
    return None


if __name__ == "__main__":
    unittest.main()
