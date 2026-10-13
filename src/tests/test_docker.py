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
from pyouter.docker import Command, Compose, Container, Service, container_running, start_compose, start_container
from pyouter.router import Router, node_kind
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


def write_fake_docker(directory):
    state = Path(directory) / "state.json"
    script = Path(directory) / "docker"
    script.write_text(textwrap.dedent(f'''
        #!/usr/bin/env python3
        import json
        import os
        import sys

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
        if not argv:
            sys.exit(2)
        if argv[0] == "inspect":
            name = argv[-1]
            info = load().get(name)
            if not info:
                sys.stderr.write("no such container\\n")
                sys.exit(1)
            sys.stdout.write("true\\n" if info.get("running") else "false\\n")
            sys.exit(0)
        if argv[0] == "rm":
            name = argv[-1]
            data = load()
            data.pop(name, None)
            save(data)
            sys.exit(0)
        if argv[0] == "run":
            name = argv[argv.index("--name") + 1]
            data = load()
            if data.get(name, {{}}).get("running"):
                sys.stderr.write("name already in use\\n")
                sys.exit(1)
            data[name] = {{"running": True, "exec": []}}
            save(data)
            sys.stdout.write(name + "\\n")
            sys.exit(0)
        if argv[0] == "exec":
            name = argv[1]
            data = load()
            info = data.get(name)
            if not info or not info.get("running"):
                sys.stderr.write("container is not running\\n")
                sys.exit(1)
            info["exec"].append(argv[2:])
            save(data)
            if argv[2:3] == ["echo"]:
                sys.stdout.write(" ".join(argv[3:]) + "\\n")
            else:
                sys.stdout.write(" ".join(argv[2:]) + "\\n")
            sys.exit(0)
        if argv[0] == "compose":
            args = argv[1:]
            project = None
            positionals = []
            index = 0
            while index < len(args):
                if args[index] in ("-f", "-p") and index + 1 < len(args):
                    if args[index] == "-p":
                        project = args[index + 1]
                    index += 2
                    continue
                positionals.append(args[index])
                index += 1
            if not project or not positionals:
                sys.exit(2)
            data = load()
            projects = data.setdefault("projects", {{}})
            command_name = positionals[0]
            if command_name == "up":
                if projects.get(project, {{}}).get("running"):
                    sys.stderr.write("already running\\n")
                    sys.exit(1)
                projects[project] = {{"running": True, "exec": []}}
                save(data)
                sys.stdout.write(project + "\\n")
                sys.exit(0)
            if command_name == "down":
                projects.pop(project, None)
                save(data)
                sys.exit(0)
            if command_name == "ps":
                info = projects.get(project)
                if info and info.get("running"):
                    sys.stdout.write("cid\\n")
                sys.exit(0)
            if command_name == "exec":
                rest = positionals[1:]
                if rest and rest[0] == "-T":
                    rest = rest[1:]
                if not rest:
                    sys.exit(2)
                service = rest[0]
                command = rest[1:]
                info = projects.get(project)
                if not info or not info.get("running"):
                    sys.stderr.write("project is not running\\n")
                    sys.exit(1)
                info["exec"].append([service] + command)
                save(data)
                if command[:1] == ["echo"]:
                    sys.stdout.write(" ".join(command[1:]) + "\\n")
                else:
                    sys.stdout.write(" ".join(command) + "\\n")
                sys.exit(0)
            sys.exit(2)
        sys.stderr.write("unknown\\n")
        sys.exit(2)
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


class running_compose:
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
            raise RuntimeError("timed out waiting for the compose project")
        if self.failure is not None:
            self._stop()
            raise self.failure
        from pyouter.docker import project_running
        if not project_running(self.node):
            self._stop()
            raise RuntimeError("compose project is not running")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop()
        return False

    def _main(self):
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(start_compose(self.node, self.ctx))

        async def watch():
            from pyouter.docker import project_running
            for _ in range(200):
                if self.task.done() or project_running(self.node):
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


class running_container:
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
            raise RuntimeError("timed out waiting for the container")
        if self.failure is not None:
            self._stop()
            raise self.failure
        if not container_running(self.node):
            self._stop()
            raise RuntimeError("container is not running")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop()
        return False

    def _main(self):
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(start_container(self.node, self.ctx))

        async def watch():
            for _ in range(200):
                if self.node.container_name and self.task.done():
                    return
                from pyouter.docker import container_running
                if container_running(self.node):
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


class DockerTest(unittest.TestCase):
    def test_path_reaches_a_command_and_a_service_inside_the_container(self):
        with tempfile.TemporaryDirectory() as directory:
            docker, state = write_fake_docker(directory)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                box = Container(
                    "alpine:3",
                    name="tools",
                    ports=("8080:80",),
                    docker=str(docker),
                    routes=Router(
                        c=Router(
                            d=Command("echo", "deep"),
                        ),
                        api=Service(
                            f"http://127.0.0.1:{port}",
                            health=("GET", "/health"),
                        ),
                    ),
                )
                app = App(config={})
                app.include(Router(a=Router(b=box)))
                self.assertEqual(node_kind(app.router.route["a"].route["b"]), "docker")
                self.assertEqual(node_kind(box.route["c"]), "router")
                self.assertEqual(node_kind(box.route["c"].route["d"]), "docker")
                self.assertEqual(node_kind(box.route["api"]), "web")
                self.assertEqual(node_kind(box.route["api"].route["health"]), "web")
                self.assertEqual(
                    sorted(app.router.tasks()),
                    ["a.b.api.health", "a.b.c.d"],
                )
                self.assertIs(box.route["c"].route["d"].container, box)
                self.assertEqual(box.ports, ("8080:80",))

                command = box.route["c"].route["d"]
                health = box.route["api"].route["health"]
                ctx = Context({}, options())
                with self.assertRaises(RuntimeError) as caught:
                    command.run(ctx)
                self.assertIn("not running", str(caught.exception))
                with self.assertRaises(RuntimeError) as caught:
                    health.run(ctx)
                self.assertIn("not running", str(caught.exception))

                with running_container(box):
                    again = asyncio.run(start_container(box, Context({}, options())))
                    self.assertEqual(again["status"], "running")
                    self.assertEqual(again["container"], "tools")
                    stdout = io.StringIO()
                    with _stdio(stdout):
                        value = command.run(ctx)
                    self.assertEqual(value["output"].strip(), "deep")
                    self.assertIn("deep", stdout.getvalue())
                    recorded = json.loads(state.read_text())
                    self.assertEqual(recorded["tools"]["exec"], [["echo", "deep"]])

                    app.options = options(actions="a.b.api.health")
                    with _stdio(io.StringIO()):
                        app.run()
                    self.assertEqual(app.result.root.value["status"], 200)
                    self.assertEqual(app.result.root.value["body"], {"path": "/health"})

                    tree = build_tree(app.router)
                    container = _find(tree, "a.b")
                    self.assertEqual(container["route_type"], "docker")
                    self.assertEqual(container["target"], "alpine:3")
                    deep = _find(tree, "a.b.c.d")
                    self.assertEqual(deep["kind"], "docker")
                    self.assertEqual(deep["target"], "echo deep")
                    route = _find(tree, "a.b.api.health")
                    self.assertEqual(route["kind"], "web")
                    self.assertEqual(route["rule"], "/health")

                self.assertNotIn("tools", json.loads(state.read_text() or "{}"))
                with self.assertRaises(RuntimeError) as caught:
                    command.run(ctx)
                self.assertIn("not running", str(caught.exception))
            finally:
                httpd.shutdown()
                thread.join(3)
                httpd.server_close()

    def test_page_names_container_and_command(self):
        page = render_page({"focus": "", "script": "app.py"})
        self.assertIn("容器", page)
        self.assertIn("命令", page)
        self.assertIn("编排", page)

    def test_compose_file_becomes_service_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            docker, state = write_fake_docker(directory)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            compose_path = Path(directory) / "compose.yaml"
            compose_path.write_text(textwrap.dedent("""
                name: demo
                services:
                  web:
                    image: nginx:alpine
                    ports:
                      - "8080:80"
                  worker:
                    image: alpine:3
                    command: sleep infinity
                  api:
                    image: python:3
                    ports:
                      - target: 8000
                        published: 9000
            """))
            try:
                stack = Compose(
                    compose_path,
                    project="demo",
                    docker=str(docker),
                    routes=Router(
                        web=Router(ping=Command("echo", "web")),
                        api=Service(
                            f"http://127.0.0.1:{port}",
                            health=("GET", "/health"),
                        ),
                    ),
                )
                app = App(config={})
                app.include(stack, prefix="stack")
                self.assertEqual(node_kind(app.router.route["stack"]), "compose")
                web = app.router.route["stack"].route["web"]
                self.assertEqual(node_kind(web), "docker")
                self.assertEqual(web.image, "nginx:alpine")
                self.assertEqual(web.ports, ("8080:80",))
                self.assertEqual(app.router.route["stack"].route["api"].ports, ("9000:8000",))
                self.assertEqual(node_kind(web.route["ping"]), "docker")
                self.assertEqual(
                    sorted(app.router.tasks()),
                    ["stack.api.health", "stack.web.ping"],
                )
                self.assertIs(web.route["ping"].container, web)

                ping = web.route["ping"]
                ctx = Context({}, options())
                with self.assertRaises(RuntimeError) as caught:
                    ping.run(ctx)
                self.assertIn("compose project demo is not running", str(caught.exception))

                with running_compose(stack):
                    again = asyncio.run(start_compose(stack, Context({}, options())))
                    self.assertEqual(again, {"status": "running", "project": "demo"})
                    stdout = io.StringIO()
                    with _stdio(stdout):
                        value = ping.run(ctx)
                    self.assertEqual(value["output"].strip(), "web")
                    self.assertEqual(value["container"], "demo/web")
                    self.assertIn("web", stdout.getvalue())
                    recorded = json.loads(state.read_text())
                    self.assertEqual(recorded["projects"]["demo"]["exec"], [["web", "echo", "web"]])

                    app.options = options(actions="stack.web")
                    with _stdio(io.StringIO()) as service_out:
                        app.run()
                    self.assertEqual(app.result.root.value["service"], "web")
                    self.assertEqual(service_out.stdout.getvalue().strip(), "compose service web 8080:80")
                    self.assertEqual(
                        json.loads(state.read_text())["projects"]["demo"]["exec"],
                        [["web", "echo", "web"]],
                    )

                    app.options = options(actions="stack.api.health")
                    with _stdio(io.StringIO()):
                        app.run()
                    self.assertEqual(app.result.root.value["body"], {"path": "/health"})

                    tree = build_tree(app.router)
                    project = _find(tree, "stack")
                    self.assertEqual(project["route_type"], "compose")
                    self.assertEqual(project["target"], "demo")
                    service = _find(tree, "stack.web")
                    self.assertEqual(service["route_type"], "docker")
                    self.assertEqual(service["target"], "nginx:alpine 8080:80")

                self.assertNotIn("demo", json.loads(state.read_text()).get("projects", {}))
                with self.assertRaises(RuntimeError) as caught:
                    ping.run(ctx)
                self.assertIn("not running", str(caught.exception))
            finally:
                httpd.shutdown()
                thread.join(3)
                httpd.server_close()

        with tempfile.TemporaryDirectory() as directory:
            dotted = Path(directory) / "compose.yaml"
            dotted.write_text("services:\n  my.web:\n    image: nginx\n")
            with self.assertRaises(ValueError):
                Compose(dotted)
            missing = Path(directory) / "missing.yaml"
            missing.write_text("services:\n  web:\n    image: nginx\n")
            with self.assertRaises(ValueError):
                Compose(missing, routes=Router(gone=Router()))
            app = App(config={})
            with self.assertRaises(ValueError):
                app.include(Compose(missing))

    def test_running_a_compose_service_leaves_its_commands_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            docker, _state = write_fake_docker(directory)
            compose_path = Path(directory) / "compose.yaml"
            compose_path.write_text("name: demo\nservices:\n  web:\n    image: nginx:alpine\n")
            stack = Compose(
                compose_path,
                project="demo",
                docker=str(docker),
                routes=Router(web=Router(ping=Command("echo", "web"))),
            )
            app = App(config={})
            app.include(stack, prefix="stack")
            app.options = options()
            bridge = WebBridge(app, host="127.0.0.1", port=0)
            bridge.install_capture()
            try:
                with running_compose(stack):
                    asyncio.run(bridge.execute_path("stack.web"))
                self.assertEqual(bridge.store.nodes["stack.web"].status, "success")
                self.assertEqual(bridge.store.nodes["stack.web.ping"].status, "idle")
            finally:
                bridge.close()

    def test_bridge_runs_a_command_while_the_container_stays_up(self):
        with tempfile.TemporaryDirectory() as directory:
            docker, _state = write_fake_docker(directory)
            box = Container(
                "alpine:3",
                name="tools",
                docker=str(docker),
                routes=Router(c=Router(d=Command("echo", "deep"))),
            )
            app = App(config={})
            app.include(Router(a=Router(b=box)))
            app.options = options()
            bridge = WebBridge(app, host="127.0.0.1", port=0, focus="a.b.c.d")
            bridge.install_capture()
            try:
                with running_container(box):
                    asyncio.run(bridge.execute_path("a.b.c.d"))
                self.assertEqual(bridge.store.nodes["a.b.c.d"].status, "success")
                messages = [line["message"] for line in bridge.store.nodes["a.b.c.d"].logs]
                self.assertTrue(any("deep" in message for message in messages))
            finally:
                bridge.close()

    def test_rejects_a_bad_name_port_and_route(self):
        with self.assertRaises(ValueError):
            Container("alpine", name="-bad")
        with self.assertRaises(ValueError):
            Container("alpine", ports=("http",))
        with self.assertRaises(ValueError):
            Service("http://127.0.0.1:80", health=("GET", "health"))
        with self.assertRaises(RuntimeError):
            Command("echo", "x").run(Context({}, options()))


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
