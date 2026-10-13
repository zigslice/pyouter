import asyncio
import io
import json
import sys
import time
import unittest
import urllib.request
from types import SimpleNamespace

from flask import Blueprint, Flask, abort
from fastapi import APIRouter, FastAPI
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from pyouter.app import App
from pyouter.flatten import WebEndpoint, flatten
from pyouter.router import Router, node_kind
from pyouter.web import WebBridge, build_tree


def sync_action(config, options):
    return "sync"


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
        self.assertEqual(api.policy, "sequence")
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
        app.include(service, prefix="api")
        app.options = options(actions="api.health")
        stdout = io.StringIO()
        with _stdio(stdout):
            app.run()
        self.assertEqual(app.result.root.value["status"], 200)
        self.assertEqual(app.result.root.value["body"], {"ok": True})
        self.assertIn("GET /health -> 200", stdout.getvalue())

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
        app.include(service, prefix="api")
        app.options = options(actions="api.users.user_id")
        with _stdio(io.StringIO(), io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                app.run()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("user_id", app.result.root.error)

        app.options = options(actions="api.missing")
        with _stdio(io.StringIO(), io.StringIO()):
            with self.assertRaises(SystemExit):
                app.run()
        self.assertIn("returned 404", app.result.root.error)

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

    def test_root_and_sequence(self):
        seen = []
        service = Flask("flatten-root")

        @service.get("/")
        def index():
            seen.append("root")
            return {"root": True}

        @service.get("/a")
        def first():
            seen.append("a")
            return "a"

        @service.get("/b")
        def second():
            seen.append("b")
            return "b"

        router = flatten(service)
        self.assertEqual(router.route["root"].rule, "/")
        from pyouter.context import Context

        with _stdio(io.StringIO()):
            result = asyncio.run(router.invoke("", Context({}, options())))
        self.assertTrue(result.ok)
        self.assertEqual(seen, ["a", "b", "root"])

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
        self.assertEqual(api["target"], "flask")

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
        app.include(api, prefix="api")
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
        with _stdio(io.StringIO()):
            app.run()
        self.assertEqual(app.result.root.value["body"], {"user_id": 4})
        self.assertEqual(app.result.root.value["path"], "/users/4")

        async def homepage(request):
            return JSONResponse({"ok": True})

        starlette_app = Starlette(routes=[Route("/health", homepage)])
        starlette_router = flatten(starlette_app)
        self.assertEqual(starlette_router.framework, "starlette")
        self.assertEqual(starlette_router.route["health"].rule, "/health")
        app.use(router=starlette_router)
        app.options = options(actions="health")
        with _stdio(io.StringIO()):
            app.run()
        self.assertEqual(app.result.root.value["body"], {"ok": True})


class WebFlattenTest(unittest.TestCase):
    def setUp(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        app = App(config={})
        app.include(flask_service(), prefix="api")
        app.options = options()
        self.bridge = WebBridge(app, host="127.0.0.1", port=0, focus="api.health")

    def tearDown(self):
        self.bridge.close()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def test_bridge_runs_a_flattened_node(self):
        self.bridge.install_capture()
        asyncio.run(self.bridge.execute_path("api.health"))
        node = self.bridge.store.nodes["api.health"]
        self.assertEqual(node.status, "success")
        messages = [line["message"] for line in node.logs]
        self.assertTrue(any("GET /health" in message for message in messages))
        self.assertTrue(any("GET /health -> 200" in message for message in messages))

    def test_http_snapshot_and_run(self):
        self.bridge.start()
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
            self.bridge.close()


if __name__ == "__main__":
    unittest.main()
