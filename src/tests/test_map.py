import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from pyouter.docker import Container
from pyouter.mapview import tree_from_runtime, with_reach
from pyouter.router import Router
from pyouter.ssh import SSH
from pyouter.web import build_tree


def _server(workers, runtime):
    node = Router(health=lambda ctx: None)
    node.serves = True
    node.layer = "server"
    node.balancer = "uvicorn"
    node.workers = workers
    node.runtime = runtime
    return node


class MapFieldTests(unittest.TestCase):
    def test_a_layer_carries_its_address_and_kind(self):
        api = _server(4, "http://127.0.0.1:7711")
        jump = SSH("10.0.0.9", routes=Router(api=api), port=2222)
        edge = Container(
            "python:3.12-slim",
            name="edge",
            routes=Router(host=jump),
            runtime="A" * 46,
        )
        tree = build_tree(Router(edge=edge))
        box = tree["children"][0]
        host = box["children"][0]
        server = host["children"][0]
        self.assertEqual(box["layer"], "docker")
        self.assertEqual(box["peer_id"], "A" * 46)
        self.assertEqual(host["layer"], "ssh")
        self.assertEqual(host["ip"], "10.0.0.9")
        self.assertEqual(host["host_port"], 2222)
        self.assertEqual(server["layer"], "server")
        self.assertEqual(server["ip"], "127.0.0.1")
        self.assertEqual(server["runtime"], "http://127.0.0.1:7711")

    def test_http_reach_is_green_or_red(self):
        with _Runtime() as url:
            live = with_reach(build_tree(Router(api=_server(1, url))))
            self.assertEqual(live["children"][0]["reach"], "up")
        dead = with_reach(build_tree(Router(api=_server(1, "http://127.0.0.1:1"))))
        self.assertEqual(dead["children"][0]["reach"], "down")
        self.assertEqual(dead["children"][0]["ip"], "127.0.0.1")

    def test_the_outer_slice_is_the_layer_you_are_on(self):
        tree, here = tree_from_runtime(
            [
                {"path": "cli.box", "kind": "cluster", "balancer": "uvicorn", "workers": 2, "port": 1},
                {"path": "cli.box.api", "kind": "server", "balancer": "uvicorn", "workers": 4, "port": 2},
            ],
            {"ip": "127.0.0.1", "port": 7710, "peer_id": "A" * 46, "sn": ["/ip4/127.0.0.1/tcp/4001/p2p/B"]},
        )
        self.assertEqual(here, "cli.box")
        box = tree["children"][0]["children"][0]
        api = box["children"][0]
        self.assertTrue(box["here"])
        self.assertEqual(box["layer"], "cluster")
        self.assertEqual(box["ip"], "127.0.0.1")
        self.assertEqual(box["peer_id"], "A" * 46)
        self.assertEqual(box["sn"], ["/ip4/127.0.0.1/tcp/4001/p2p/B"])
        self.assertEqual(box["reach"], "up")
        self.assertFalse(api["here"])
        self.assertEqual(api["layer"], "server")
        self.assertEqual(api["reach"], "up")


class RuntimePageTests(unittest.TestCase):
    def test_the_runtime_serves_the_page_on_its_own_port(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = _start_node(directory)
            try:
                port = _read_port(proc)
                page = _get(port, "/")
                self.assertEqual(page.status, 200)
                self.assertIn("目录", page.text)
                self.assertIn("你在这里", page.text)
                health = _get(port, "/health")
                self.assertEqual(health.status, 200)
                self.assertTrue(json.loads(health.text)["ok"])
                snap = json.loads(_get(port, "/api/snapshot").text)
                self.assertEqual(snap["mode"], "runtime")
                self.assertEqual(snap["here"], "")
                self.assertTrue(snap["tree"]["here"])
                self.assertEqual(snap["tree"]["reach"], "up")
                self.assertEqual(snap["self"]["ip"], "127.0.0.1")
                body = json.dumps(
                    {"path": "api", "kind": "server", "balancer": "uvicorn", "workers": 1}
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/deploy",
                    data=body,
                    headers={"content-type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    deployed = json.loads(response.read().decode("utf-8"))
                self.assertEqual(deployed["path"], "api")
                again = json.loads(_get(port, "/api/snapshot").text)
                self.assertEqual(again["here"], "api")
                self.assertTrue(again["tree"]["children"][0]["here"])
                self.assertEqual(again["tree"]["children"][0]["layer"], "server")
                self.assertEqual(again["tree"]["children"][0]["reach"], "up")
                self.assertEqual(again["tree"]["children"][0]["ip"], "127.0.0.1")
            finally:
                _stop(proc)


def _start_node(directory):
    env = os.environ.copy()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pyouter.node",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--identity",
            str(Path(directory) / "identity"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _read_port(proc):
    line = proc.stdout.readline()
    if not line.startswith("node "):
        raise RuntimeError(line or "node runtime did not start")
    return int(line.split()[1])


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
        return _Body(response.status, response.read().decode("utf-8"))


class _Body:
    def __init__(self, status, text):
        self.status = status
        self.text = text


def _stop(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except OSError:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    if proc.stdout is not None:
        proc.stdout.close()


class _Runtime:
    def __enter__(self):
        env = os.environ.copy()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "pyouter.node", "--host", "127.0.0.1", "--port", "0"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
        line = self.proc.stdout.readline()
        if not line.startswith("node "):
            raise RuntimeError(line or "node runtime did not start")
        self.url = f"http://127.0.0.1:{int(line.split()[1])}"
        return self.url

    def __exit__(self, exc_type, exc, tb):
        from pyouter.node import shutdown

        shutdown(self.url)
        _stop(self.proc)
        return False


if __name__ == "__main__":
    unittest.main()
