import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from pyouter.context import Context
from pyouter.docker import Command, Compose, Container
from pyouter.router import Router, execute
from pyouter.runtime import live_record
from pyouter.segment import Placement, SegmentBoard, activate, locate, script_digest
from pyouter.ssh import Remote, SSH


def options(**extra):
    values = dict(debug=False, view=False, tree=False, tasks=False, actions=None, web=False)
    values.update(extra)
    return SimpleNamespace(**values)


def write_fake_docker(directory):
    state = Path(directory) / "state.json"
    script = Path(directory) / "docker"
    body = textwrap.dedent(f"""
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
        if argv[:1] == ["inspect"]:
            info = load().get(argv[-1])
            if not info:
                sys.stderr.write("no such container\\n")
                sys.exit(1)
            sys.stdout.write("true\\n" if info.get("running") else "false\\n")
            sys.exit(0)
        if argv[:1] == ["rm"]:
            data = load()
            data.pop(argv[-1], None)
            save(data)
            sys.exit(0)
        if argv[:1] == ["run"]:
            name = argv[argv.index("--name") + 1]
            data = load()
            data[name] = {{"running": True}}
            save(data)
            sys.stdout.write(name + "\\n")
            sys.exit(0)
        sys.exit(2)
    """).lstrip("\n")
    script.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    script.chmod(0o755)
    return script


class SegmentTests(unittest.TestCase):
    def tree(self):
        edge = SSH(
            "10.0.0.8",
            user="deploy",
            routes=Router(e=Remote("echo", "in")),
        )
        box = Container(
            "alpine",
            name="box",
            routes=Router(
                c=Router(d=Command("echo", "deep")),
                edge=edge,
            ),
        )
        api = Router(health=lambda ctx: None)
        api.serves = True
        api.origin = "web"
        return Router(a=Router(b=box, ping=lambda ctx: None), api=api)

    def test_locate_splits_the_tree_at_each_host(self):
        root = self.tree()
        self.assertEqual(locate(root, "a"), Placement("", False, None))
        self.assertEqual(locate(root, "a.ping"), Placement("", False, None))
        self.assertEqual(locate(root, "a.b"), Placement("", True, "a.b"))
        self.assertEqual(locate(root, "a.b.c"), Placement("a.b", False, "a.b"))
        self.assertEqual(locate(root, "a.b.c.d"), Placement("a.b", False, "a.b"))
        self.assertEqual(locate(root, "a.b.edge"), Placement("a.b", True, "a.b.edge"))
        self.assertEqual(locate(root, "a.b.edge.e"), Placement("a.b.edge", False, "a.b.edge"))
        self.assertEqual(locate(root, "api"), Placement("", True, "api"))
        self.assertEqual(locate(root, "api.health"), Placement("api", False, "api"))
        self.assertIsNone(locate(root, "missing"))

    def test_compose_project_is_a_boundary_and_a_service_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "stack.yaml"
            spec.write_text("services:\n  web:\n    image: nginx\n", encoding="utf-8")
            root = Router(stack=Compose(spec))
        self.assertEqual(locate(root, "stack"), Placement("", True, "stack"))
        self.assertEqual(locate(root, "stack.web"), Placement("stack", False, "stack"))

    def test_assignment_follows_the_open_segment(self):
        root = self.tree()
        with tempfile.TemporaryDirectory() as directory:
            board = SegmentBoard(directory)
            first = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            second = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                board.register(first.pid, 1)
                board.register(second.pid, 2)
                outer = {board.assign(root, "a.ping", first.pid) for _ in range(6)}
                self.assertEqual(outer, {str(first.pid), str(second.pid)})

                owner = board.assign(root, "a.b", first.pid)
                self.assertEqual(board.assign(root, "a.b", second.pid), owner)
                closed = {board.assign(root, "a.b.c.d", first.pid) for _ in range(6)}
                self.assertEqual(closed, {str(first.pid), str(second.pid)})

                board.ready("a.b", owner)
                self.assertTrue(board.is_open("a.b"))
                self.assertEqual(set(board.members("a.b")), {str(first.pid), str(second.pid)})
                inner = {board.assign(root, "a.b.c.d", first.pid) for _ in range(6)}
                self.assertEqual(inner, {str(first.pid), str(second.pid)})
                self.assertEqual(board.assign(root, "a.b", first.pid), owner)

                nested = board.assign(root, "a.b.edge", first.pid)
                self.assertEqual(board.assign(root, "a.b.edge", second.pid), nested)
                board.ready("a.b.edge", nested)
                deep = {board.assign(root, "a.b.edge.e", first.pid) for _ in range(6)}
                self.assertEqual(deep, {str(first.pid), str(second.pid)})

                board.down("a.b", owner)
                self.assertFalse(board.is_open("a.b"))
                self.assertIsNone(board.owner("a.b"))
            finally:
                first.kill()
                second.kill()
                first.wait(timeout=5)
                second.wait(timeout=5)

    def test_starting_a_container_opens_its_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = write_fake_docker(directory)
            board = SegmentBoard(Path(directory) / "board")
            activate(board, os.getpid())
            board.register(os.getpid(), 9)
            box = Container("alpine", name="box", docker=str(docker), routes=Router(d=Command("echo", "ok")))
            ctx = Context({}, options())

            async def main():
                task = asyncio.create_task(execute(box, "box", 0, ctx))
                for _ in range(50):
                    if board.is_open("box"):
                        break
                    await asyncio.sleep(0.05)
                else:
                    self.fail("segment did not open")
                self.assertEqual(board.owner("box"), str(os.getpid()))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

            asyncio.run(main())
            self.assertFalse(board.is_open("box"))
            self.assertIsNone(board.owner("box"))


class WorkerPoolTests(unittest.TestCase):
    def test_workers_share_functions_and_pin_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            app_path = Path(directory) / "app.py"
            app_path.write_text(textwrap.dedent("""
                import os
                from pyouter.app import App
                from pyouter.router import Router

                class Box:
                    def __init__(self):
                        self.n = 0

                    def run(self, ctx):
                        self.n += 1
                        print(f"obj={os.getpid()} n={self.n}")

                def ping(ctx):
                    print(f"fn={os.getpid()}")

                app = App(config={})
                app.include(Router(ping=ping, box=Box()))
                app.run()
            """), encoding="utf-8")
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = directory
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")

            def call(action):
                return subprocess.run(
                    [sys.executable, str(app_path), action],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

            runtime = subprocess.Popen(
                [sys.executable, str(app_path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            worker = None
            runtime_log = []
            worker_log = []

            def drain(proc, sink):
                for line in proc.stdout:
                    sink.append(line)

            threading.Thread(target=drain, args=(runtime, runtime_log), daemon=True).start()
            board = SegmentBoard(Path(directory) / ".pyouter" / "segments" / script_digest(str(app_path)))
            try:
                for _ in range(100):
                    if live_record(app_path) is not None:
                        break
                    if runtime.poll() is not None:
                        self.fail("".join(runtime_log) or "runtime exited")
                    time.sleep(0.05)
                else:
                    self.fail("runtime did not start: " + "".join(runtime_log))

                worker = subprocess.Popen(
                    [sys.executable, str(app_path), "--worker"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                threading.Thread(target=drain, args=(worker, worker_log), daemon=True).start()
                for _ in range(100):
                    if str(worker.pid) in board.members(""):
                        break
                    if worker.poll() is not None:
                        self.fail("".join(worker_log) or "worker exited")
                    time.sleep(0.05)
                else:
                    self.fail("worker did not join: " + "".join(worker_log))

                pids = set()
                for _ in range(8):
                    result = call("ping")
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    pids.update(line.split("=", 1)[1].strip() for line in result.stdout.splitlines() if line.startswith("fn="))
                self.assertEqual(pids, {str(runtime.pid), str(worker.pid)})

                obj_pids = []
                counts = []
                for _ in range(3):
                    result = call("box")
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    line = next(item for item in result.stdout.splitlines() if item.startswith("obj="))
                    obj_pids.append(line.split()[0].split("=", 1)[1])
                    counts.append(line.split("n=", 1)[1])
                self.assertEqual(len(set(obj_pids)), 1)
                self.assertEqual(counts, ["1", "2", "3"])

                again = subprocess.run(
                    [sys.executable, str(app_path)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
                self.assertIn("already running", again.stdout)
                self.assertIsNone(runtime.poll())
                self.assertIsNone(worker.poll())
            finally:
                if worker is not None and worker.poll() is None:
                    os.kill(worker.pid, signal.SIGINT)
                    worker.wait(timeout=5)
                if runtime.poll() is None:
                    os.kill(runtime.pid, signal.SIGINT)
                    runtime.wait(timeout=5)
                if worker is not None and worker.stdout is not None:
                    worker.stdout.close()
                if runtime.stdout is not None:
                    runtime.stdout.close()
                if previous_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = previous_home
