import asyncio
import io
import json
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pyouter.app import App
from pyouter.default import create_parser
from pyouter.router import Router
from pyouter.web import WebBridge


async def hello_action(config, options):
    print("async-hello")


def sync_action(config, options):
    print("sync-ok")
    print("debug-on" if getattr(options, "debug", False) else "debug-off")
    print(config["marker"])


def err_action(config, options):
    print("err-line", file=sys.stderr)


async def ok_action(config, options):
    print("from-ok")


async def slow_action(config, options):
    print("slow-start")
    await asyncio.sleep(30)


class Boom:
    """box doc"""

    def run(self, config, options):
        print("before-boom")
        raise RuntimeError("boom")


def make_app():
    app = App(config={"marker": "cfg"})
    app.use(
        router=Router(
            job=Router(
                hello=hello_action,
                sync=sync_action,
                err=err_action,
                boom=Boom(),
                slow=slow_action,
            ),
            group=Router(
                ok=ok_action,
                bad=Boom(),
            ),
            plain=sync_action,
        )
    )
    app.options = SimpleNamespace(
        debug=True,
        view=False,
        tree=False,
        tasks=False,
        actions=None,
        web=False,
    )
    app.router.context(app.config, app.options, app.executor)
    return app


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.bridge = WebBridge(make_app())
        self.bridge.install_capture()

    def tearDown(self):
        self.bridge.restore_capture()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def test_tree_describes_routers_and_actions(self):
        tree = self.bridge.tree
        self.assertEqual(tree["name"], "(root)")
        self.assertEqual(tree["path"], "")
        self.assertEqual(tree["type"], "router")
        job = next(child for child in tree["children"] if child["name"] == "job")
        sync = next(child for child in job["children"] if child["name"] == "sync")
        self.assertEqual(sync["path"], "job.sync")
        self.assertEqual(sync["kind"], "function")
        self.assertEqual(sync["target"], "sync_action")
        boom = next(child for child in job["children"] if child["name"] == "boom")
        self.assertEqual(boom["kind"], "object")
        self.assertEqual(boom["target"], "Boom")
        self.assertIn("box doc", boom["doc"])
        self.assertIn("", self.bridge.store.nodes)

    def test_sync_print_stays_on_that_node(self):
        sink = io.StringIO()
        self.bridge.restore_capture()
        sys.stdout = sink
        self.bridge.install_capture()
        asyncio.run(self.bridge.execute_path("job.sync"))
        self.assertNotIn("sync-ok", sink.getvalue())
        node = self.bridge.store.nodes["job.sync"]
        messages = [line["message"] for line in node.logs]
        self.assertEqual(node.status, "success")
        self.assertIn("sync-ok", messages)
        self.assertIn("debug-on", messages)
        self.assertIn("cfg", messages)
        self.assertNotIn("sync-ok", [line["message"] for line in self.bridge.store.nodes["job"].logs])

    def test_async_and_stderr_logs(self):
        asyncio.run(self.bridge.execute_path("job.hello"))
        asyncio.run(self.bridge.execute_path("job.err"))
        hello_logs = self.bridge.store.nodes["job.hello"].logs
        err_logs = self.bridge.store.nodes["job.err"].logs
        self.assertTrue(any(line["message"] == "async-hello" and line["stream"] == "stdout" for line in hello_logs))
        self.assertTrue(any(line["message"] == "err-line" and line["stream"] == "stderr" for line in err_logs))

    def test_router_keeps_child_status_and_logs(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(self.bridge.execute_path("group"))
        nodes = self.bridge.store.nodes
        self.assertEqual(nodes["group.ok"].status, "success")
        self.assertEqual(nodes["group.bad"].status, "error")
        self.assertEqual(nodes["group"].status, "error")
        self.assertIn("boom", nodes["group.bad"].error)
        ok_messages = [line["message"] for line in nodes["group.ok"].logs]
        parent_messages = [line["message"] for line in nodes["group"].logs]
        self.assertIn("from-ok", ok_messages)
        self.assertNotIn("from-ok", parent_messages)
        self.assertTrue(any("before-boom" in line["message"] for line in nodes["group.bad"].logs))
        self.assertTrue(any("RuntimeError: boom" in line["message"] for line in nodes["group"].logs))

    def test_missing_path_and_overlap(self):
        with self.assertRaises(Exception):
            asyncio.run(self.bridge.execute_path("missing.thing"))
        self.assertTrue(self.bridge.store.reserve("job", ["job", "job.slow"]))
        self.assertFalse(self.bridge.store.reserve("job.slow", ["job.slow"]))
        self.assertTrue(self.bridge.store.reserve("plain", ["plain"]))

    def test_cancel_running_node(self):
        async def scenario():
            self.bridge.loop = asyncio.get_running_loop()
            task = asyncio.create_task(self.bridge.execute_path("job.slow"))
            for _ in range(100):
                if self.bridge.store.nodes["job.slow"].status == "running":
                    break
                await asyncio.sleep(0.01)
            else:
                self.fail("slow node did not start")
            status, payload = self.bridge.request_stop("job.slow")
            self.assertEqual(status, 202)
            self.assertTrue(payload["ok"])
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(self.bridge.store.nodes["job.slow"].status, "cancelled")

        asyncio.run(scenario())


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.bridge = WebBridge(make_app(), host="127.0.0.1", port=0, focus="job.sync")
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def _get(self, path):
        with urllib.request.urlopen(self.bridge.url + path, timeout=3) as response:
            return response.status, response.read()

    def _post(self, path, payload):
        request = urllib.request.Request(
            self.bridge.url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _wait(self, path, expected, timeout=3):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            status, raw = self._get("/api/snapshot")
            self.assertEqual(status, 200)
            last = json.loads(raw.decode("utf-8"))["nodes"][path]
            if last["status"] in expected:
                return last
            time.sleep(0.05)
        self.fail(f"{path} stuck at {None if last is None else last['status']}")

    def test_page_and_snapshot(self):
        status, body = self._get("/")
        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("目录", html)
        self.assertIn("日志", html)
        self.assertIn("路由图", html)
        self.assertIn('"focus": "job.sync"', html)
        status, raw = self._get("/api/snapshot")
        snap = json.loads(raw.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(snap["focus"], "job.sync")
        self.assertIn("job.sync", snap["nodes"])
        status, raw = self._get("/api/events?since=0")
        events = json.loads(raw.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("seq", events)
        self.assertFalse(events["gap"])

    def test_run_sync_from_http(self):
        status, body = self._post("/api/run", {"path": "job.sync"})
        self.assertEqual(status, 202)
        self.assertTrue(body["ok"])
        node = self._wait("job.sync", {"success", "error"})
        self.assertEqual(node["status"], "success")
        self.assertIn("sync-ok", [line["message"] for line in node["logs"]])

    def test_missing_and_overlap(self):
        status, body = self._post("/api/run", {"path": "no.such"})
        self.assertEqual(status, 404)
        self.assertFalse(body["ok"])
        status, body = self._post("/api/run", {"path": "job.slow"})
        self.assertEqual(status, 202)
        self._wait("job.slow", {"running", "pending"})
        status, body = self._post("/api/run", {"path": "job"})
        self.assertEqual(status, 409)
        self.assertIn("正在执行", body["error"])
        status, body = self._post("/api/stop", {"path": "job.slow"})
        self.assertEqual(status, 202)
        node = self._wait("job.slow", {"cancelled", "success", "error"})
        self.assertEqual(node["status"], "cancelled")

    def test_invalid_json(self):
        request = urllib.request.Request(
            self.bridge.url + "/api/run",
            data=b"{",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 400)


class CliTest(unittest.TestCase):
    def test_parser_accepts_web_flags(self):
        parser = create_parser("demo")
        opts = parser.parse_args(["job.sync", "--web", "--port", "9001", "--no-browser", "--host", "127.0.0.1"])
        self.assertTrue(opts.web)
        self.assertEqual(opts.port, 9001)
        self.assertEqual(opts.host, "127.0.0.1")
        self.assertEqual(opts.actions, "job.sync")
        self.assertTrue(opts.no_browser)

    def test_run_dispatches_web(self):
        app = make_app()
        app.options = SimpleNamespace(
            web=True,
            host="127.0.0.1",
            port=9,
            no_browser=True,
            actions="job.sync",
            tree=False,
            tasks=False,
            view=False,
        )
        with mock.patch("pyouter.web.serve") as serve:
            returned = app.run()
        self.assertIs(returned, app)
        serve.assert_called_once()
        self.assertEqual(serve.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(serve.call_args.kwargs["port"], 9)
        self.assertFalse(serve.call_args.kwargs["open_browser"])
        self.assertEqual(serve.call_args.kwargs["focus"], "job.sync")

    def test_module_help_lists_web(self):
        src = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "pyouter", "--help"],
            cwd=src,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--web", proc.stdout)
        self.assertIn("--no-browser", proc.stdout)


if __name__ == "__main__":
    unittest.main()
