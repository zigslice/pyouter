import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from pyouter.node import deploy_tree
from pyouter.peer import close_control, peer_id_of
from pyouter.router import Router


def _closed(addr):
    head, _, tail = addr.partition("/tcp/")
    _port, _sep, rest = tail.partition("/")
    return f"{head}/tcp/1/{rest}"


_NET = "test-net"


def _server(workers):
    node = Router(health=lambda ctx: None)
    node.serves = True
    node.layer = "server"
    node.balancer = "uvicorn"
    node.workers = workers
    return node


class PeerIdentityTests(unittest.TestCase):
    def test_a_peer_id_stays_the_same_across_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identity"
            first = peer_id_of(path)
            second = peer_id_of(path)
            other = peer_id_of(Path(directory) / "other")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertGreater(len(first), 45)


class PeerDeployTests(unittest.TestCase):
    def test_a_peer_id_without_a_super_node_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            peer = peer_id_of(Path(directory) / "identity")
            api = _server(1)
            api.runtime = peer
            with self.assertRaises(RuntimeError) as caught:
                deploy_tree(Router(api=api))
        self.assertIn("super node", str(caught.exception))

    def test_a_slice_reaches_a_peer_that_joined_the_super_node(self):
        with tempfile.TemporaryDirectory() as directory:
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", _NET)
            try:
                sn_addr = sn.value("sn ")
                worker = _Node(
                    directory,
                    "worker",
                    "--sn",
                    sn_addr,
                    "--net",
                    _NET,
                )
                try:
                    self.assertEqual(worker.value("joined "), sn.peer_id)
                    self._deploy(directory, worker.peer_id, [sn_addr], workers=2)
                    self._deploy(directory, worker.peer_id, [sn_addr], workers=2)
                finally:
                    worker.stop()
            finally:
                sn.stop()
                close_control()

    def test_a_peer_that_has_not_joined_is_not_given_the_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", _NET)
            try:
                sn_addr = sn.value("sn ")
                closed = _closed(sn_addr)
                worker = _Node(directory, "worker", "--sn", closed, "--net", _NET)
                try:
                    self.assertEqual(worker.value("joined "), "none")
                    api = _server(1)
                    api.runtime = worker.peer_id
                    previous = os.environ.get("PYOUTER_PEER_IDENTITY")
                    os.environ["PYOUTER_PEER_IDENTITY"] = str(Path(directory) / "control")
                    try:
                        with self.assertRaises(RuntimeError) as caught:
                            deploy_tree(Router(api=api), sn=[sn_addr], net=_NET)
                    finally:
                        if previous is None:
                            os.environ.pop("PYOUTER_PEER_IDENTITY", None)
                        else:
                            os.environ["PYOUTER_PEER_IDENTITY"] = previous
                        close_control()
                    self.assertIn("has not joined", str(caught.exception))
                finally:
                    worker.stop()
            finally:
                sn.stop()

    def test_a_peer_joins_the_super_node_that_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            live = _Node(directory, "live", "--sn-listen", "127.0.0.1:0", "--net", _NET)
            try:
                live_addr = live.value("sn ")
                decoy = peer_id_of(Path(directory) / "decoy")
                closed = f"/ip4/127.0.0.1/tcp/1/p2p/{decoy}"
                worker = _Node(directory, "worker", "--sn", closed, "--sn", live_addr, "--net", _NET)
                try:
                    self.assertEqual(worker.value("joined "), live.peer_id)
                    self._deploy(directory, worker.peer_id, [closed, live_addr], workers=1)
                finally:
                    worker.stop()
            finally:
                live.stop()
                close_control()

    def test_a_peer_without_the_secret_is_not_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", _NET)
            try:
                sn_addr = sn.value("sn ")
                worker = _Node(directory, "worker", "--sn", sn_addr, "--net", "someone-else")
                try:
                    self.assertEqual(worker.value("joined "), "none")
                finally:
                    worker.stop()
            finally:
                sn.stop()

    def test_a_push_without_the_secret_does_not_land(self):
        with tempfile.TemporaryDirectory() as directory:
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", _NET)
            try:
                sn_addr = sn.value("sn ")
                worker = _Node(directory, "worker", "--sn", sn_addr, "--net", _NET)
                try:
                    self.assertEqual(worker.value("joined "), sn.peer_id)
                    api = _server(1)
                    api.runtime = worker.peer_id
                    previous = os.environ.get("PYOUTER_PEER_IDENTITY")
                    os.environ["PYOUTER_PEER_IDENTITY"] = str(Path(directory) / "control")
                    try:
                        with self.assertRaises(RuntimeError) as caught:
                            deploy_tree(Router(api=api), sn=[sn_addr])
                    finally:
                        if previous is None:
                            os.environ.pop("PYOUTER_PEER_IDENTITY", None)
                        else:
                            os.environ["PYOUTER_PEER_IDENTITY"] = previous
                        close_control()
                    self.assertIn("network secret", str(caught.exception))
                    port = int(worker.node_line.split()[1])
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    self.assertFalse(body["deployed"])
                finally:
                    worker.stop()
            finally:
                sn.stop()

    def test_joining_without_a_secret_is_refused(self):
        env = os.environ.copy()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        env.pop("PYOUTER_NET", None)
        proc = subprocess.Popen(
            [sys.executable, "-m", "pyouter.node", "--port", "0", "--sn-listen", "127.0.0.1:0"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("a super node without --net kept running")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("this network needs --net", stderr)
        self.assertNotIn("node ", stdout)

    def _deploy(self, directory, peer_id, sn, workers):
        api = _server(workers)
        api.runtime = peer_id
        previous = os.environ.get("PYOUTER_PEER_IDENTITY")
        os.environ["PYOUTER_PEER_IDENTITY"] = str(Path(directory) / "control")
        try:
            sent = deploy_tree(Router(api=api), sn=sn, net=_NET)
        finally:
            if previous is None:
                os.environ.pop("PYOUTER_PEER_IDENTITY", None)
            else:
                os.environ["PYOUTER_PEER_IDENTITY"] = previous
        self.assertEqual(sent[0]["path"], "api")
        self.assertEqual(sent[0]["workers"], workers)
        self.assertEqual(sent[0]["kind"], "server")


class _Node:
    def __init__(self, directory, name, *args):
        env = os.environ.copy()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        self.err = []
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pyouter.node",
                "--port",
                "0",
                "--identity",
                str(Path(directory) / name),
                *args,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        threading.Thread(target=self._drain, daemon=True).start()
        self.node_line = self._line("node ")
        self.peer_line = self._line("peer ")
        self.peer_id = self.peer_line.split(" ", 1)[1]

    def line(self, prefix):
        return self._line(prefix)

    def value(self, prefix):
        return self.line(prefix).split(" ", 1)[1]

    def stop(self):
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
        if self.proc.stderr is not None:
            self.proc.stderr.close()

    def _line(self, prefix):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            box = []

            def read(box=box):
                box.append(self.proc.stdout.readline())

            thread = threading.Thread(target=read, daemon=True)
            thread.start()
            thread.join(max(0.1, deadline - time.monotonic()))
            if not box:
                continue
            line = box[0]
            if line == "" and self.proc.poll() is not None:
                detail = "".join(self.err).strip()
                raise RuntimeError(detail or "runtime exited before it was ready")
            text = (line or "").strip()
            if text.startswith(prefix):
                return text
        detail = "".join(self.err).strip()
        raise RuntimeError(detail or f"timed out waiting for {prefix!r}")

    def _drain(self):
        if self.proc.stderr is None:
            return
        for line in self.proc.stderr:
            self.err.append(line)


if __name__ == "__main__":
    unittest.main()
