import concurrent.futures
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from pyouter.balance import boot_argv, register_provider, start_pool
from pyouter.docker import Container
from pyouter.layer import Layer, plan
from pyouter.node import _install_plan, _place_ssh, call, deploy_tree, health, push, shutdown
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

    def test_install_picks_local_ssh_or_refuses(self):
        root = _tree()
        edge = root.route["cli"].route["box"]
        jump = edge.route["host"]
        inner = jump.route["box"]
        api = inner.route["api"]
        edge.runtime = "http://192.0.2.10:7710"
        jump.runtime = "http://10.0.0.9:7710"
        inner.runtime = "http://10.0.0.9:7711"
        api.runtime = "http://127.0.0.1:7712"
        self.assertEqual(_install_plan(edge, root, "cli.box")[0], "unreachable")
        self.assertEqual(_install_plan(jump, root, "cli.box.host")[0], "ssh")
        self.assertEqual(_install_plan(inner, root, "cli.box.host.box")[0], "ssh")
        self.assertEqual(_install_plan(api, root, "cli.box.host.box.api")[0], "local")

    def test_a_remote_layer_without_ssh_is_not_installed(self):
        root = Router(box=Container("python:3.12-slim", runtime="http://192.0.2.10:7710"))
        with self.assertRaises(RuntimeError) as caught:
            deploy_tree(root)
        self.assertIn("no ssh host", str(caught.exception))

    def test_an_unknown_balancer_is_rejected_when_the_pool_starts(self):
        with self.assertRaises(ValueError):
            start_pool(provider="missing", workers=1)


class InstallTests(unittest.TestCase):
    def test_deploy_starts_a_local_runtime_and_a_second_push_reuses_it(self):
        port = _free_port()
        api = _server(1)
        api.runtime = f"http://127.0.0.1:{port}"
        root = Router(api=api)
        try:
            sent = deploy_tree(root)
            self.assertEqual(sent[0]["path"], "api")
            self.assertEqual(sent[0]["workers"], 1)
            self.assertTrue(health(api.runtime)["deployed"])
            pid = api._runtime_proc.pid
            again = deploy_tree(root)
            self.assertEqual(again[0]["workers"], 1)
            self.assertEqual(api._runtime_proc.pid, pid)
            self.assertIsNone(api._runtime_proc.poll())
        finally:
            _stop_local(api)

    def test_ssh_install_copies_the_package_and_starts_the_listener(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = _write_install_ssh(directory)
            port = _free_port()
            host = SSH("10.0.0.9", ssh=str(binary), runtime=f"http://127.0.0.1:{port}")
            try:
                placed = _place_ssh(host, host.runtime, port)
                self.assertEqual(placed["status"], "installed")
                package = Path(directory) / "home" / ".pyouter" / "runtime" / "pyouter" / "node.py"
                self.assertTrue(package.is_file())
                self.assertIn("def serve", package.read_text())
                pid = int((Path(directory) / "home" / ".pyouter" / "runtime" / "node.pid").read_text())
                self.assertTrue(health(host.runtime)["ok"])
                self.assertFalse(health(host.runtime)["deployed"])
                again = _place_ssh(host, host.runtime, port)
                self.assertEqual(again["status"], "installed")
                self.assertEqual(
                    int((Path(directory) / "home" / ".pyouter" / "runtime" / "node.pid").read_text()),
                    pid,
                )
            finally:
                shutdown(host.runtime)
                pid_path = Path(directory) / "home" / ".pyouter" / "runtime" / "node.pid"
                if pid_path.is_file():
                    _kill_pid(int(pid_path.read_text()))


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


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _stop_local(node):
    url = getattr(node, "runtime", None)
    if isinstance(url, str) and url:
        shutdown(url)
    proc = getattr(node, "_runtime_proc", None)
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except OSError:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)


def _kill_pid(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def _write_install_ssh(directory):
    script = Path(directory) / "ssh"
    home = Path(directory) / "home"
    home.mkdir()
    script.write_text(textwrap.dedent(f'''
        #!/usr/bin/env python3
        import os
        import sys

        argv = sys.argv[1:]
        valued = {{"-S", "-O", "-p", "-i", "-L", "-o"}}
        positionals = []
        index = 0
        while index < len(argv):
            item = argv[index]
            if item in valued and index + 1 < len(argv):
                index += 2
                continue
            if item.startswith("-"):
                index += 1
                continue
            positionals.append(item)
            index += 1
        if len(positionals) < 2:
            sys.stderr.write("no command\\n")
            sys.exit(2)
        os.environ["HOME"] = {str(home)!r}
        os.execvp(positionals[1], positionals[1:])
    ''').lstrip())
    script.chmod(0o755)
    return script


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
