import asyncio
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, Flask, abort
from fastapi import APIRouter, FastAPI
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from pyouter.app import App
from pyouter.context import Context
from pyouter.flatten import WebEndpoint, flatten, invoke_endpoint, listening, serve_service
from pyouter.flatten import ServiceAddress
from pyouter.router import Router, node_kind
from pyouter.web import WebBridge, build_tree


def sync_action(config, options):
    return "sync"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class running_service:
    """Keep a flattened service listening on a background loop."""

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
            raise RuntimeError("timed out waiting for the web service")
        if self.failure is not None:
            self._stop()
            raise self.failure
        if not listening(self.node.address):
            self._stop()
            raise RuntimeError("web service is not listening")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop()
        return False

    def _main(self):
        asyncio.set_event_loop(self.loop)
        self.task = self.loop.create_task(serve_service(self.node, self.ctx))

        async def watch():
            for _ in range(200):
                if listening(self.node.address) or self.task.done():
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


def find(node, path):
    if node["path"] == path:
        return node
    for child in node["children"]:
        found = find(child, path)
        if found is not None:
            return found
    return None


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


def flask_service():
    service = Flask("flatten-flask")

    @service.get("/health")
    def health():
        """service is up"""
        return {"ok": True}

    @service.get("/users")
    def list_users():
        return {"users": []}

    @service.post("/users")
    def create_user():
        return {"created": True}

    @service.get("/users/<int:user_id>")
    def read_user(user_id):
        return {"user_id": user_id}

    @service.get("/missing")
    def missing():
        abort(404)

    blueprint = Blueprint("v1", __name__, url_prefix="/v1")

    @blueprint.get("/ping")
    def ping():
        return "pong"

    service.register_blueprint(blueprint)
    return service


class FlattenTest(unittest.TestCase):
    def test_flask_routes_become_typed_nodes(self):
        service = flask_service()
        app = App(config={})
        app.include(Router(job=sync_action))
        app.include(service, prefix="api")

        self.assertEqual(node_kind(app.router), "router")
        self.assertEqual(node_kind(app.router.route["job"]), "cli")
        api = app.router.route["api"]
        self.assertEqual(node_kind(api), "web")
        self.assertEqual(api.framework, "flask")
        self.assertTrue(api.serves)
        self.assertFalse(api.route["users"].serves)
        self.assertEqual(api.address.port, 5000)
        self.assertEqual(api.route["health"].address.base_url, "http://127.0.0.1:5000")
        self.assertNotIn("static", api.route)
        self.assertIsInstance(api.route["health"], WebEndpoint)
        self.assertEqual(api.route["health"].method, "GET")
        self.assertEqual(api.route["health"].rule, "/health")
        users = api.route["users"]
        self.assertEqual(list(users.route), ["get", "post", "user_id"])
        self.assertEqual(users.route["user_id"].rule, "/users/<int:user_id>")
        self.assertEqual(api.route["v1"].route["ping"].rule, "/v1/ping")
        self.assertEqual(
            sorted(app.router.tasks()),
            [
                "api.health",
                "api.missing",
                "api.users.get",
                "api.users.post",
                "api.users.user_id",
                "api.v1.ping",
                "job",
            ],
        )

    def test_flask_invocation_reads_options_config_and_params(self):
        service = flask_service()
        app = App(config={"user_id": 5})
        app.include(service, prefix="api", port=free_port())
        with running_service(app.router.route["api"]):
            app.options = options(actions="api.health")
            stdout = io.StringIO()
            with _stdio(stdout):
                app.run()
            self.assertEqual(app.result.root.value["status"], 200)
            self.assertEqual(app.result.root.value["body"], {"ok": True})
            self.assertIn("/health -> 200", stdout.getvalue())

            app.options = options(actions="api.users.user_id")
            with _stdio(io.StringIO()):
                app.run()
            self.assertEqual(app.result.root.value["body"], {"user_id": 5})

            app.options = options(actions="api.users.user_id", params={"user_id": 9})
            with _stdio(io.StringIO()):
                app.run()
            self.assertEqual(app.result.root.value["body"], {"user_id": 9})

            app.options = options(actions="api.users.user_id", user_id=7)
            with _stdio(io.StringIO()):
                app.run()
            self.assertEqual(app.result.root.value["path"], "/users/7")
            self.assertEqual(app.result.root.value["body"], {"user_id": 7})

    def test_missing_parameter_and_http_error_fail_the_node(self):
        service = flask_service()
        app = App(config={})
        app.include(service, prefix="api", port=free_port())
        app.options = options(actions="api.users.user_id")
        with _stdio(io.StringIO(), io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                app.run()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("user_id", app.result.root.error)

        app.options = options(actions="api.missing")
        with running_service(app.router.route["api"]):
            with _stdio(io.StringIO(), io.StringIO()):
                with self.assertRaises(SystemExit):
                    app.run()
        self.assertIn("returned 404", app.result.root.error)

    def test_requests_hit_the_service_that_is_already_running(self):
        hits = {"n": 0}
        service = Flask("lifetime")

        @service.get("/health")
        def health():
            hits["n"] += 1
            return {"n": hits["n"]}

        router = flatten(service, port=free_port())
        endpoint = router.route["health"]
        ctx = Context({}, options())
        with self.assertRaises(RuntimeError) as caught:
            invoke_endpoint(endpoint, ctx)
        self.assertIn("not running", str(caught.exception))

        with running_service(router):
            self.assertEqual(hits["n"], 0)
            again = asyncio.run(serve_service(router, Context({}, options())))
            self.assertEqual(again["status"], "running")
            first = invoke_endpoint(endpoint, ctx)
            second = invoke_endpoint(endpoint, ctx)
        self.assertEqual(first["body"], {"n": 1})
        self.assertEqual(second["body"], {"n": 2})
        self.assertEqual(hits["n"], 2)
        with self.assertRaises(RuntimeError) as caught:
            invoke_endpoint(endpoint, ctx)
        self.assertIn("not running", str(caught.exception))

    def test_another_process_reaches_the_same_service(self):
        port = free_port()
        with tempfile.TemporaryDirectory() as directory:
            app_path = Path(directory) / "app.py"
            pid_path = Path(directory) / "pids"
            app_path.write_text(textwrap.dedent(f'''
                import os
                from flask import Flask
                from pyouter.app import App

                service = Flask("svc")

                @service.get("/health")
                def health():
                    with open({str(pid_path)!r}, "a") as handle:
                        handle.write(str(os.getpid()) + "\\n")
                    return {{"ok": True}}

                app = App(config={{}})
                app.include(service, prefix="api", port={port})
                app.run()
            '''))
            env = os.environ.copy()
            src = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
            server = subprocess.Popen(
                [sys.executable, str(app_path), "api"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                address = ServiceAddress("127.0.0.1", port)
                for _ in range(100):
                    if listening(address):
                        break
                    if server.poll() is not None:
                        self.fail(server.stdout.read())
                    time.sleep(0.05)
                else:
                    self.fail("service process did not listen")

                def call(action):
                    return subprocess.run(
                        [sys.executable, str(app_path), action],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )

                first = call("api.health")
                second = call("api.health")
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertIn("/health -> 200", first.stdout)
                pids = [line for line in pid_path.read_text().splitlines() if line]
                self.assertEqual(pids, [str(server.pid), str(server.pid)])
                again = call("api")
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
                self.assertIn("already running", again.stdout)
                self.assertIsNone(server.poll())
            finally:
                if server.poll() is None:
                    os.kill(server.pid, signal.SIGINT)
                    server.wait(timeout=5)
                if server.stdout is not None:
                    server.stdout.close()
            for _ in range(50):
                if not listening(address):
                    break
                time.sleep(0.05)

            missed = subprocess.run(
                [sys.executable, str(app_path), "api.health"],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(missed.returncode, 1, missed.stdout + missed.stderr)
            self.assertIn("not running", missed.stdout + missed.stderr)

    def test_constructor_and_use_flatten(self):
        service = flask_service()
        router = Router(api=service, job=sync_action)
        self.assertEqual(node_kind(router.route["api"].route["health"]), "web")
        self.assertEqual(node_kind(router.route["job"]), "cli")

        app = App(config={})
        app.use(router=service)
        self.assertIn("health", app.router.route)

    def test_rejects_a_value_that_is_not_a_service(self):
        with self.assertRaises(TypeError):
            flatten(object())
        app = App(config={})
        with self.assertRaises(TypeError):
            app.include(sync_action)

    def test_sanitized_paths_that_collide_are_an_error(self):
        service = Flask("flatten-collision")

        @service.get("/a-b")
        def one():
            return "1"

        @service.get("/a_b")
        def two():
            return "2"

        with self.assertRaises(ValueError) as caught:
            flatten(service)
        self.assertIn("same pyouter node", str(caught.exception))

    def test_route_group_does_not_call_endpoints(self):
        seen = []
        service = Flask("flatten-group")

        @service.get("/users")
        def list_users():
            seen.append("users")
            return {}

        @service.get("/users/<int:user_id>")
        def one(user_id):
            seen.append(user_id)
            return {}

        router = flatten(service, port=free_port())
        self.assertTrue(router.serves)
        self.assertFalse(router.route["users"].serves)
        with _stdio(io.StringIO()):
            result = asyncio.run(router.route["users"].invoke("", Context({}, options())))
        self.assertTrue(result.ok)
        self.assertEqual(seen, [])

    def test_tree_describes_the_http_route(self):
        app = App(config={})
        app.include(flask_service(), prefix="api")
        tree = build_tree(app.router)
        health = find(tree, "api.health")
        self.assertEqual(health["kind"], "web")
        self.assertEqual(health["route_type"], "web")
        self.assertEqual(health["method"], "GET")
        self.assertEqual(health["rule"], "/health")
        self.assertEqual(health["target"], "GET /health")
        self.assertIn("service is up", health["doc"])
        api = find(tree, "api")
        self.assertEqual(api["kind"], "router")
        self.assertEqual(api["route_type"], "web")
        self.assertEqual(api["target"], "http://127.0.0.1:5000")

        stdout = io.StringIO()
        with _stdio(stdout):
            app.router.print_tree()
        self.assertIn("health (GET /health)", stdout.getvalue())

    def test_fastapi_and_starlette(self):
        api = FastAPI()
        group = APIRouter(prefix="/v1")
        nested = APIRouter()

        @group.get("/ping")
        def ping():
            """ping doc"""
            return {"pong": True}

        @nested.get("/x")
        def nested_x():
            return {"x": True}

        @api.get("/users/{user_id}")
        def read_user(user_id: int):
            return {"user_id": user_id}

        @api.post("/users")
        def create_user():
            return {"created": True}

        group.include_router(nested, prefix="/nest")
        api.include_router(group)
        mounted_app = FastAPI()

        @mounted_app.get("/health")
        def mounted_health():
            return {"ok": True}

        api.mount("/sub", mounted_app)
        app = App(config={})
        app.include(api, prefix="api", port=free_port())
        mounted = app.router.route["api"]
        self.assertEqual(mounted.framework, "fastapi")
        self.assertNotIn("docs", mounted.route)
        self.assertNotIn("redoc", mounted.route)
        self.assertNotIn("openapi_json", mounted.route)
        self.assertEqual(mounted.route["v1"].route["ping"].rule, "/v1/ping")
        self.assertEqual(mounted.route["v1"].route["ping"].doc, "ping doc")
        self.assertEqual(mounted.route["v1"].route["nest"].route["x"].rule, "/v1/nest/x")
        self.assertEqual(mounted.route["sub"].route["health"].rule, "/sub/health")
        self.assertEqual(list(mounted.route["users"].route), ["post", "user_id"])

        app.options = options(actions="api.users.user_id", user_id=4)
        with running_service(mounted):
            with _stdio(io.StringIO()):
                app.run()
        self.assertEqual(app.result.root.value["body"], {"user_id": 4})
        self.assertEqual(app.result.root.value["path"], "/users/4")

        async def homepage(request):
            return JSONResponse({"ok": True})

        starlette_app = Starlette(routes=[Route("/health", homepage)])
        starlette_router = flatten(starlette_app, port=free_port())
        self.assertEqual(starlette_router.framework, "starlette")
        self.assertEqual(starlette_router.route["health"].rule, "/health")
        app.use(router=starlette_router)
        app.options = options(actions="health")
        with running_service(starlette_router):
            with _stdio(io.StringIO()):
                app.run()
        self.assertEqual(app.result.root.value["body"], {"ok": True})


class WebFlattenTest(unittest.TestCase):
    def setUp(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        app = App(config={})
        app.include(flask_service(), prefix="api", port=free_port())
        app.options = options()
        self.app = app
        self.bridge = WebBridge(app, host="127.0.0.1", port=0, focus="api.health")

    def tearDown(self):
        self.bridge.close()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def test_bridge_runs_a_flattened_node(self):
        self.bridge.install_capture()
        with running_service(self.app.router.route["api"]):
            asyncio.run(self.bridge.execute_path("api.health"))
        node = self.bridge.store.nodes["api.health"]
        self.assertEqual(node.status, "success")
        messages = [line["message"] for line in node.logs]
        self.assertTrue(any("GET /health" in message for message in messages))
        self.assertTrue(any("/health -> 200" in message for message in messages))

    def test_service_stays_up_while_a_route_runs(self):
        self.bridge.install_capture()

        async def scenario():
            service = asyncio.create_task(self.bridge.execute_path("api"))
            api = self.app.router.route["api"]
            for _ in range(100):
                if listening(api.address) and self.bridge.store.nodes["api"].status == "running":
                    break
                await asyncio.sleep(0.05)
            else:
                self.fail("service node did not stay running")
            await self.bridge.execute_path("api.health")
            self.assertEqual(self.bridge.store.nodes["api"].status, "running")
            self.assertEqual(self.bridge.store.nodes["api.health"].status, "success")
            service.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await service
            self.assertEqual(self.bridge.store.nodes["api"].status, "cancelled")

        asyncio.run(scenario())

    def test_http_snapshot_and_run(self):
        self.bridge.start()
        service = running_service(self.app.router.route["api"])
        service.__enter__()
        try:
            with urllib.request.urlopen(self.bridge.url + "/", timeout=3) as response:
                html = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("接口", html)
            self.assertIn("服务", html)
            with urllib.request.urlopen(self.bridge.url + "/api/snapshot", timeout=3) as response:
                snap = json.loads(response.read().decode("utf-8"))
            health = find(snap["tree"], "api.health")
            self.assertEqual(health["kind"], "web")
            self.assertEqual(health["rule"], "/health")
            request = urllib.request.Request(
                self.bridge.url + "/api/run",
                data=json.dumps({"path": "api.health"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 202)
            self.assertTrue(body["ok"])
            deadline = time.time() + 5
            last = None
            while time.time() < deadline:
                with urllib.request.urlopen(self.bridge.url + "/api/snapshot", timeout=3) as response:
                    last = json.loads(response.read().decode("utf-8"))["nodes"]["api.health"]
                if last["status"] in {"success", "error"}:
                    break
                time.sleep(0.05)
            else:
                self.fail(f"api.health stuck at {None if last is None else last['status']}")
            self.assertEqual(last["status"], "success")
        finally:
            service.__exit__(None, None, None)
            self.bridge.close()


if __name__ == "__main__":
    unittest.main()
