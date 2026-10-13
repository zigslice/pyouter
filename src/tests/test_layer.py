import concurrent.futures
import os
import signal
import subprocess
import sys
import time
import unittest

from pyouter.balance import boot_argv, register_provider, start_pool
from pyouter.docker import Container
from pyouter.layer import Layer, plan
from pyouter.node import call, deploy_tree, health, push, shutdown
from pyouter.router import Router
from pyouter.ssh import SSH


def _server(workers):
    node = Router(health=lambda ctx: None)
    node.serves = True
    node.layer = "server"
    node.balancer = "uvicorn"
    node.workers = workers
    return node


def _tree():
    api = _server(4)
    inner = Container(
        "python:3.12-slim",
        name="inner",
        routes=Router(api=api),
        balancer="uvicorn",
        workers=3,
    )
    jump = SSH(
        "10.0.0.9",
        routes=Router(box=inner),
        balancer="uvicorn",
        workers=2,
    )
    edge = Container(
        "python:3.12-slim",
        name="edge",
        routes=Router(host=jump),
        balancer="uvicorn",
        workers=2,
    )
    return Router(cli=Router(box=edge))


class LayerPlanTests(unittest.TestCase):
    def test_cli_docker_ssh_docker_server_is_four_layers(self):
        root = _tree()
        entered = plan(root, "cli.box.host.box.api.health")
        self.assertFalse(entered.boundary)
        self.assertEqual(
            [(item.kind, item.workers) for item in entered.crossings],
            [("docker", 2), ("ssh", 2), ("docker", 3), ("server", 4)],
        )
        self.assertEqual(entered.serving.kind, "server")
        self.assertEqual(entered.serving.workers, 4)
        self.assertEqual(entered.serving.balancer, "uvicorn")
        self.assertTrue(all(item.balancer == "uvicorn" for item in entered.crossings))

        boundary = plan(root, "cli.box")
        self.assertTrue(boundary.boundary)
        self.assertIsNone(boundary.serving)
        self.assertEqual(boundary.crossings[0].kind, "docker")

        inside_edge = plan(root, "cli.box.host")
        self.assertTrue(inside_edge.boundary)
        self.assertEqual(inside_edge.serving.kind, "docker")
        self.assertEqual(inside_edge.serving.path, "cli.box")

    def test_each_layer_can_name_its_balancer(self):
        api = _server(1)
        api.balancer = "remote"
        box = Container("python:3.12-slim", routes=Router(api=api), balancer="near", workers=2)
        chosen = plan(Router(box=box), "box.api.health")
        self.assertEqual(chosen.crossings[0].balancer, "near")
        self.assertEqual(chosen.serving.balancer, "remote")
        self.assertEqual(boot_argv(box)[4], "near")
        self.assertEqual(boot_argv(box)[6], "2")

    def test_a_layer_without_a_runtime_is_not_pushed(self):
        with self.assertRaises(ValueError) as caught:
            deploy_tree(_tree())
        self.assertIn("no runtime", str(caught.exception))

    def test_an_unknown_balancer_is_rejected_when_the_pool_starts(self):
        with self.assertRaises(ValueError):
            start_pool(provider="missing", workers=1)


class LoadBalanceTests(unittest.TestCase):
    def test_a_pushed_slice_serves_from_the_node_runtime(self):
        root = _tree()
        with _Runtime() as edge, _Runtime() as jump, _Runtime() as inner, _Runtime() as api:
            root.route["cli"].route["box"].runtime = edge
            root.route["cli"].route["box"].route["host"].runtime = jump
            root.route["cli"].route["box"].route["host"].route["box"].runtime = inner
            root.route["cli"].route["box"].route["host"].route["box"].route["api"].runtime = api
            sent = deploy_tree(root)
            self.assertEqual(
                [item["path"] for item in sent],
                ["cli.box", "cli.box.host", "cli.box.host.box", "cli.box.host.box.api"],
            )
            self.assertEqual([item["workers"] for item in sent], [2, 2, 3, 4])
            self.assertEqual(
                [health(url)["path"] for url in (edge, jump, inner, api)],
                ["cli.box", "cli.box.host", "cli.box.host.box", "cli.box.host.box.api"],
            )

    def test_more_workers_finish_concurrent_calls_sooner(self):
        with _Runtime() as url:
            single = _measure(url, workers=1, calls=4, hold=0.3)
            multi = _measure(url, workers=4, calls=4, hold=0.3)
        print(
            f"BENCH workers=1 elapsed={single['elapsed']:.3f} pids={single['pids']} "
            f"workers=4 elapsed={multi['elapsed']:.3f} pids={multi['pids']}"
        )
        self.assertEqual(len(single["pids"]), 1)
        self.assertGreaterEqual(len(multi["pids"]), 2)
        self.assertLess(multi["elapsed"] * 1.5, single["elapsed"])

    def test_a_registered_provider_can_replace_the_default(self):
        seen = {}

        def start(workers, port):
            seen["workers"] = workers
            seen["port"] = port
            from pyouter.balance import _start_uvicorn
            return _start_uvicorn(1, port)

        register_provider("probe", start)
        pool = start_pool(provider="probe", workers=3)
        try:
            self.assertEqual(seen["workers"], 3)
            body = pool.call({"path": "health", "hold": 0})
            self.assertEqual(body["path"], "health")
        finally:
            pool.close()


class _Runtime:
    """One physical-node runtime started the way a node would start it."""

    def __enter__(self):
        env = os.environ.copy()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "pyouter.node", "--port", "0"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        line = self.proc.stdout.readline()
        if not line.startswith("node "):
            raise RuntimeError(line or "node runtime did not start")
        self.url = f"http://127.0.0.1:{int(line.split()[1])}"
        return self.url

    def __exit__(self, exc_type, exc, tb):
        shutdown(self.url)
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGINT)
            except OSError:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)
        if self.proc.stdout is not None:
            self.proc.stdout.close()
        return False


def _measure(url, workers, calls, hold):
    push(url, Layer("bench", "server", "uvicorn", workers))
    call(url, {"path": "warm", "hold": 0})
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=calls) as pool_threads:
        bodies = list(pool_threads.map(
            lambda _index: call(url, {"path": "work", "hold": hold}),
            range(calls),
        ))
    elapsed = time.perf_counter() - started
    return {"elapsed": elapsed, "pids": sorted({item["pid"] for item in bodies})}


if __name__ == "__main__":
    unittest.main()
