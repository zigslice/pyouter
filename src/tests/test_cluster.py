import base64
import json
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

from pyouter.cluster import Cluster, resources
from pyouter.layer import plan
from pyouter.node import deploy_tree, health, shutdown
from pyouter.peer import close_control
from pyouter.router import Router
from pyouter.segment import locate


def _server(workers):
    node = Router(health=lambda ctx: None)
    node.serves = True
    node.layer = "server"
    node.balancer = "uvicorn"
    node.workers = workers
    return node


class ClusterShapeTests(unittest.TestCase):
    def test_a_cluster_image_must_name_a_registry(self):
        with self.assertRaises(ValueError):
            Cluster("python:3.12-slim")

    def test_a_cluster_without_a_super_node_is_refused(self):
        edge = Cluster(
            "registry.example.com/app:1.2",
            name="edge",
            docker="missing-docker",
            kubectl="missing-kubectl",
        )
        with self.assertRaises(RuntimeError) as caught:
            deploy_tree(Router(edge=edge), sn=[])
        self.assertIn("super node", str(caught.exception))

    def test_a_cluster_manifest_is_one_pod(self):
        node = Cluster("registry.example.com/app:1.2", name="edge", workers=4)
        secret, deployment = resources(
            node,
            ["/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSn"],
            b"key",
            "abc",
            "s3cret",
        )
        self.assertEqual(deployment["spec"]["replicas"], 1)
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], "registry.example.com/app:1.2")
        self.assertEqual(container["imagePullPolicy"], "Always")
        self.assertEqual(container["volumeMounts"][0]["mountPath"], "/var/pyouter/identity")
        self.assertEqual(container["args"].count("--sn"), 1)
        self.assertIn("/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSn", container["args"])
        self.assertNotIn("s3cret", json.dumps(container["args"]))
        self.assertEqual(container["env"][0]["name"], "PYOUTER_NET")
        self.assertEqual(container["env"][0]["valueFrom"]["secretKeyRef"]["key"], "net")
        self.assertEqual(secret["data"]["identity"], base64.b64encode(b"key").decode("ascii"))
        self.assertEqual(secret["data"]["net"], base64.b64encode(b"s3cret").decode("ascii"))
        self.assertEqual(deployment["metadata"]["annotations"]["pyouter.dev/tree"], "abc")
        self.assertNotIn('"replicas": 4', json.dumps(deployment))

    def test_a_cluster_is_a_layer_and_a_host_boundary(self):
        api = _server(2)
        edge = Cluster(
            "registry.example.com/app:1.2",
            name="edge",
            routes=Router(api=api),
            workers=4,
        )
        root = Router(cli=Router(box=edge))
        chosen = plan(root, "cli.box.api.health")
        self.assertEqual(
            [(item.kind, item.workers) for item in chosen.crossings],
            [("cluster", 4), ("server", 2)],
        )
        self.assertEqual(chosen.serving.kind, "server")
        self.assertTrue(locate(root, "cli.box").bound)
        self.assertEqual(locate(root, "cli.box.api").segment, "cli.box")


class ClusterDeployTests(unittest.TestCase):
    def test_a_cluster_layer_is_one_pod_and_one_peer(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = _write_docker(directory)
            kubectl = _write_kubectl(directory)
            home = Path(directory) / "home"
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", "test-net")
            previous = os.environ.get("PYOUTER_PEER_IDENTITY")
            os.environ["PYOUTER_PEER_IDENTITY"] = str(Path(directory) / "control")
            try:
                sn_addr = sn.value("sn ")
                api = _server(2)
                edge = Cluster(
                    "registry.example.com/app:1.2",
                    name="edge",
                    routes=Router(api=api),
                    workers=4,
                    docker=str(docker),
                    kubectl=str(kubectl),
                    home=str(home),
                )
                root = Router(edge=edge)
                sent = deploy_tree(root, sn=[sn_addr], net="test-net")
                self.assertEqual([item["path"] for item in sent], ["edge", "edge.api"])
                self.assertEqual(sent[0]["kind"], "cluster")
                self.assertEqual(sent[0]["workers"], 4)
                self.assertEqual(sent[1]["kind"], "server")
                self.assertEqual(sent[1]["workers"], 2)
                self.assertEqual(_docker_count(directory, "build"), 1)
                self.assertEqual(_docker_count(directory, "push"), 1)
                deployment = _last(directory, "Deployment")
                self.assertEqual(deployment["spec"]["replicas"], 1)
                self.assertEqual(
                    deployment["spec"]["template"]["spec"]["containers"][0]["image"],
                    "registry.example.com/app:1.2",
                )
                again = deploy_tree(root, sn=[sn_addr], net="test-net")
                self.assertEqual(again[0]["workers"], 4)
                self.assertEqual(_docker_count(directory, "build"), 1)
                edge.workers = 3
                changed = deploy_tree(root, sn=[sn_addr], net="test-net")
                self.assertEqual(changed[0]["workers"], 3)
                self.assertEqual(changed[1]["workers"], 2)
                self.assertEqual(_docker_count(directory, "build"), 1)
                edge.image = "registry.example.com/app:1.3"
                rolled = deploy_tree(root, sn=[sn_addr], net="test-net")
                self.assertEqual(rolled[0]["workers"], 3)
                self.assertEqual(_docker_count(directory, "build"), 2)
                self.assertEqual(
                    _last(directory, "Deployment")["spec"]["template"]["spec"]["containers"][0]["image"],
                    "registry.example.com/app:1.3",
                )
            finally:
                _stop_pod(directory)
                sn.stop()
                close_control()
                if previous is None:
                    os.environ.pop("PYOUTER_PEER_IDENTITY", None)
                else:
                    os.environ["PYOUTER_PEER_IDENTITY"] = previous

    def test_a_layer_with_its_own_runtime_is_not_sent_to_the_pod(self):
        with tempfile.TemporaryDirectory() as directory:
            docker = _write_docker(directory)
            kubectl = _write_kubectl(directory)
            home = Path(directory) / "home"
            sn = _Node(directory, "sn", "--sn-listen", "127.0.0.1:0", "--net", "test-net")
            previous = os.environ.get("PYOUTER_PEER_IDENTITY")
            os.environ["PYOUTER_PEER_IDENTITY"] = str(Path(directory) / "control")
            try:
                sn_addr = sn.value("sn ")
                with _Runtime() as url:
                    api = _server(2)
                    api.runtime = url
                    edge = Cluster(
                        "registry.example.com/app:1.2",
                        name="edge",
                        routes=Router(api=api),
                        workers=1,
                        docker=str(docker),
                        kubectl=str(kubectl),
                        home=str(home),
                    )
                    sent = deploy_tree(Router(edge=edge), sn=[sn_addr], net="test-net")
                    self.assertEqual(sent[0]["kind"], "cluster")
                    self.assertEqual(sent[0]["path"], "edge")
                    self.assertEqual(health(url)["path"], "edge.api")
                    self.assertEqual(health(url)["kind"], "server")
                    self.assertEqual(health(url)["workers"], 2)
            finally:
                _stop_pod(directory)
                sn.stop()
                close_control()
                if previous is None:
                    os.environ.pop("PYOUTER_PEER_IDENTITY", None)
                else:
                    os.environ["PYOUTER_PEER_IDENTITY"] = previous


def _write_docker(directory):
    state = Path(directory) / "docker.json"
    script = Path(directory) / "docker"
    script.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            f"""
            import json
            import os
            import sys

            path = {str(state)!r}
            argv = sys.argv[1:]
            if not argv or argv[0] not in {{"build", "push"}}:
                sys.stderr.write("unexpected docker\\n")
                sys.exit(2)
            data = {{}}
            if os.path.exists(path):
                with open(path) as handle:
                    data = json.load(handle)
            data.setdefault(argv[0], []).append(argv)
            with open(path, "w") as handle:
                json.dump(data, handle)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_kubectl(directory):
    state = Path(directory) / "kubectl.json"
    identity = Path(directory) / "pod-identity"
    log = Path(directory) / "pod.log"
    script = Path(directory) / "kubectl"
    script.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            f"""
            import base64
            import json
            import os
            import signal
            import subprocess
            import sys
            import time

            state_path = {str(state)!r}
            identity_path = {str(identity)!r}
            net_path = {str(Path(directory) / "pod-net")!r}
            log_path = {str(log)!r}
            argv = sys.argv[1:]

            def load():
                if not os.path.exists(state_path):
                    return {{}}
                with open(state_path) as handle:
                    return json.load(handle)

            def save(data):
                with open(state_path, "w") as handle:
                    json.dump(data, handle)

            if argv[:2] == ["rollout", "status"]:
                sys.exit(0)
            if argv[:3] != ["apply", "-f", "-"]:
                sys.stderr.write("unexpected kubectl\\n")
                sys.exit(2)
            document = json.load(sys.stdin)
            data = load()
            data.setdefault("applied", []).append(document)
            kind = document.get("kind")
            if kind == "Secret":
                raw = base64.b64decode(document["data"]["identity"])
                with open(identity_path, "wb") as handle:
                    handle.write(raw)
                net = base64.b64decode(document["data"]["net"]).decode("utf-8")
                with open(net_path, "w") as handle:
                    handle.write(net)
            if kind == "Deployment":
                pid = data.get("pid")
                if pid:
                    try:
                        os.killpg(int(pid), signal.SIGINT)
                    except OSError:
                        pass
                    deadline = time.time() + 5
                    while time.time() < deadline:
                        try:
                            os.kill(int(pid), 0)
                        except OSError:
                            break
                        time.sleep(0.05)
                    else:
                        try:
                            os.killpg(int(pid), signal.SIGKILL)
                        except OSError:
                            pass
                container = document["spec"]["template"]["spec"]["containers"][0]
                args = list(container["args"])
                slot = args.index("--identity")
                args[slot + 1] = identity_path
                log = open(log_path, "ab")
                env = os.environ.copy()
                if os.path.exists(net_path):
                    env["PYOUTER_NET"] = open(net_path).read()
                proc = subprocess.Popen(
                    [sys.executable, "-m", "pyouter.node", *args],
                    env=env,
                    stdout=log,
                    stderr=log,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
                log.close()
                data["pid"] = proc.pid
            save(data)
            sys.stdout.write("applied\\n")
            """
        ).lstrip(),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _docker_count(directory, key):
    path = Path(directory) / "docker.json"
    if not path.is_file():
        return 0
    return len(json.loads(path.read_text(encoding="utf-8")).get(key, []))


def _last(directory, kind):
    applied = json.loads((Path(directory) / "kubectl.json").read_text(encoding="utf-8"))["applied"]
    found = [item for item in applied if item.get("kind") == kind]
    return found[-1]


def _stop_pod(directory):
    path = Path(directory) / "kubectl.json"
    if not path.is_file():
        return
    pid = json.loads(path.read_text(encoding="utf-8")).get("pid")
    if not pid:
        return
    try:
        os.killpg(int(pid), signal.SIGINT)
    except OSError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(int(pid), 0)
        except OSError:
            return
        time.sleep(0.05)
    try:
        os.killpg(int(pid), signal.SIGKILL)
    except OSError:
        pass


class _Runtime:
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

    def value(self, prefix):
        return self._line(prefix).split(" ", 1)[1]

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
