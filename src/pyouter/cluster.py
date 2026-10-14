"""A cluster layer is one pod and one peer.

The cloud's nodes stay with the vendor. ``deploy_tree`` builds an image
from this tree, pushes it to the registry named on the layer, and applies
one Deployment. The pod runs ``pyouter.node``, mounts a stable identity,
and joins the super nodes carried by that call. ``workers`` is the pool
inside the pod. The Deployment has one replica.

A later call with the same tree pushes the slice again and does not build.
Changing the tree or the image name builds and rolls the pod.
"""

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .balance import normalize_balancer, normalize_workers
from .router import Router


_DOCKERFILE = """\
FROM python:3.12-slim
RUN pip install --no-cache-dir "libp2p>=0.8.0" "uvicorn"
COPY pyouter /opt/pyouter/pyouter
COPY app /opt/app
ENV PYTHONPATH=/opt/pyouter
WORKDIR /opt/app
ENTRYPOINT ["python", "-m", "pyouter.node"]
"""
_DNS = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_IDENTITY_MOUNT = "/var/pyouter/identity"


class Cluster(Router):
    """One pod started from a registry image.

    ``image`` is the name ``deploy_tree`` builds and pushes, such as
    ``registry.example.com/app:1.2``. ``name`` is the Deployment name.
    ``workers`` is the pool inside the pod, not a replica count.
    ``docker`` and ``kubectl`` are the executables, so tests can
    substitute fakes. ``home`` is where this control process keeps the
    pod's identity. The default is ``~/.pyouter/cluster``.
    """

    def __init__(
        self,
        image,
        routes=None,
        name=None,
        workers=1,
        balancer="uvicorn",
        namespace="default",
        docker="docker",
        kubectl="kubectl",
        home=None,
    ):
        super().__init__()
        self.origin = "cluster"
        self.layer = "cluster"
        self.image = _image(image)
        self.cluster_name = _dns_name(name, self.image)
        self.namespace = _namespace(namespace)
        self.balancer = normalize_balancer(balancer)
        self.workers = normalize_workers(workers)
        self.docker = docker
        self.kubectl = kubectl
        self.home = home
        self.runtime = None
        if routes is not None:
            self.include(routes)


def publish(node, path, sn=None, net=None):
    """Start this layer's pod when it is down, then push its slice."""
    from .layer import Layer, balancer_name, worker_count
    from .peer import push_peer

    peer = place(node, sn, net)
    node.runtime = peer
    layer = Layer(path, "cluster", balancer_name(node), worker_count(node))
    return push_peer(peer, layer, sn, net)


def place(node, sn=None, net=None):
    """Build and apply this pod, then wait until its peer has joined.

    The same tree and a peer that is already up skips the build and the
    apply. A tree change builds the image again and rolls the Deployment.
    A peer that is down is applied again from the image already pushed.
    """
    from .peer import network_secret, peer_id_of, super_nodes

    addresses = super_nodes(sn)
    if not addresses:
        raise RuntimeError(f"cluster {node.cluster_name} needs a super node")
    secret_text = network_secret(net)
    if not secret_text:
        raise RuntimeError(f"cluster {node.cluster_name} needs a network secret")
    identity = _identity_file(node)
    peer_id = peer_id_of(identity)
    image_digest = tree_hash(node)
    stamp = image_digest + "." + hashlib.sha256(secret_text.encode("utf-8")).hexdigest()[:16]
    record = identity.parent / "tree"
    previous = record.read_text(encoding="utf-8") if record.is_file() else ""
    if previous == stamp and _reachable(peer_id, addresses, secret_text):
        return peer_id
    if not previous.startswith(image_digest):
        _build_and_push(node)
    secret, deployment = resources(node, addresses, identity.read_bytes(), stamp, secret_text)
    _apply(node, secret)
    _apply(node, deployment)
    _rollout(node)
    record.write_text(stamp, encoding="utf-8")
    _wait_until_joined(node, peer_id, addresses, secret_text)
    return peer_id


def resources(node, sn, identity, digest, net):
    """Return the Secret and the Deployment for this one pod."""
    secret_name = f"{node.cluster_name}-identity"
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": secret_name, "namespace": node.namespace},
        "type": "Opaque",
        "data": {
            "identity": base64.b64encode(identity).decode("ascii"),
            "net": base64.b64encode(str(net).encode("utf-8")).decode("ascii"),
        },
    }
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": node.cluster_name,
            "namespace": node.namespace,
            "labels": {"app": node.cluster_name},
            "annotations": {"pyouter.dev/tree": digest},
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": node.cluster_name}},
            "template": {
                "metadata": {
                    "labels": {"app": node.cluster_name},
                    "annotations": {"pyouter.dev/tree": digest},
                },
                "spec": {
                    "containers": [
                        {
                            "name": node.cluster_name,
                            "image": node.image,
                            "imagePullPolicy": "Always",
                            "args": _container_args(sn),
                            "env": [
                                {
                                    "name": "PYOUTER_NET",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": secret_name,
                                            "key": "net",
                                        }
                                    },
                                }
                            ],
                            "volumeMounts": [
                                {
                                    "name": "identity",
                                    "mountPath": _IDENTITY_MOUNT,
                                    "subPath": "identity",
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "identity",
                            "secret": {"secretName": secret_name},
                        }
                    ],
                },
            },
        },
    }
    return secret, deployment


def enclosing_cluster(router, path):
    """Return the cluster path that contains ``path``, or ``None``."""
    text = "" if path is None else str(path)
    if not text:
        return None
    node = router
    walked = ""
    found = None
    for part in text.split("."):
        routes = getattr(node, "route", None)
        if not isinstance(routes, dict) or part not in routes:
            return None
        node = routes[part]
        walked = f"{walked}.{part}" if walked else part
        if getattr(node, "origin", None) == "cluster" or getattr(node, "layer", None) == "cluster":
            found = walked
    if found is None or found == text:
        return None
    return found


def tree_hash(node):
    """Hash the image name and the files that go into it."""
    digest = hashlib.sha256()
    digest.update(node.image.encode("utf-8"))
    digest.update(b"\0")
    digest.update(_DOCKERFILE.encode("utf-8"))
    package = Path(__file__).resolve().parent
    for path in _package_files(package):
        digest.update(str(path.relative_to(package)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    app = _app_source()
    if app is not None:
        digest.update(app.name.encode("utf-8"))
        digest.update(app.read_bytes())
    return digest.hexdigest()


def _build_and_push(node):
    context = Path(tempfile.mkdtemp(prefix="pyouter-cluster-"))
    try:
        package = Path(__file__).resolve().parent
        destination = context / "pyouter"
        destination.mkdir()
        for path in _package_files(package):
            target = destination / path.relative_to(package)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        app_dir = context / "app"
        app_dir.mkdir()
        app = _app_source()
        if app is not None:
            shutil.copyfile(app, app_dir / app.name)
        else:
            (app_dir / ".keep").write_text("", encoding="utf-8")
        (context / "Dockerfile").write_text(_DOCKERFILE, encoding="utf-8")
        _run(node.docker, ["build", "-t", node.image, str(context)])
        _run(node.docker, ["push", node.image])
    finally:
        shutil.rmtree(context, ignore_errors=True)


def _apply(node, document):
    _run(node.kubectl, ["apply", "-f", "-"], input_text=json.dumps(document))


def _rollout(node):
    _run(
        node.kubectl,
        [
            "rollout",
            "status",
            f"deployment/{node.cluster_name}",
            "-n",
            node.namespace,
            "--timeout=60s",
        ],
    )


def _container_args(sn):
    args = ["--host", "0.0.0.0", "--port", "0", "--identity", _IDENTITY_MOUNT]
    for item in sn:
        args.extend(["--sn", item])
    return args


def _reachable(peer_id, sn, net):
    from .peer import peer_health

    try:
        body = peer_health(peer_id, sn, net)
    except (OSError, RuntimeError):
        return False
    return bool(isinstance(body, dict) and body.get("ok"))


def _wait_until_joined(node, peer_id, sn, net):
    from .peer import peer_health

    deadline = time.monotonic() + 45
    last = ""
    while time.monotonic() < deadline:
        try:
            body = peer_health(peer_id, sn, net)
        except Exception as exc:
            last = str(exc)
            time.sleep(0.2)
            continue
        if isinstance(body, dict) and body.get("ok"):
            return
        last = "peer has not joined a super node"
        time.sleep(0.2)
    raise RuntimeError(f"cluster {node.cluster_name} did not join a super node: {last}")


def _identity_file(node):
    if node.home:
        root = Path(node.home)
    else:
        root = Path.home() / ".pyouter" / "cluster"
    directory = root / node.namespace / node.cluster_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "identity"


def _package_files(package):
    found = []
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        found.append(path)
    return found


def _app_source():
    raw = sys.argv[0] if sys.argv else ""
    if not raw or raw == "-":
        return None
    path = Path(raw)
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > 2_000_000:
            return None
    except OSError:
        return None
    return path


def _run(binary, args, input_text=None):
    try:
        completed = subprocess.run(
            [binary, *args],
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run {binary}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        message = f"{Path(binary).name} {args[0]} failed"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    return completed.stdout


def _image(image):
    if not isinstance(image, str) or image == "" or image.startswith("-") or " " in image:
        raise ValueError("cluster image must be a registry name, such as registry.example.com/app:1.2")
    if "/" not in image:
        raise ValueError("cluster image must be a registry name, such as registry.example.com/app:1.2")
    return image


def _dns_name(name, image):
    if name is None or name == "":
        leaf = image.rsplit("/", 1)[-1]
        leaf = leaf.split("@", 1)[0].split(":", 1)[0]
        name = re.sub(r"[^a-z0-9-]+", "-", leaf.lower()).strip("-")[:53]
    else:
        name = str(name)
    if not _DNS.fullmatch(name) or len(name) > 53:
        raise ValueError("cluster name must be a DNS label of at most 53 characters")
    return name


def _namespace(namespace):
    if namespace is None or namespace == "":
        namespace = "default"
    namespace = str(namespace)
    if not _DNS.fullmatch(namespace) or len(namespace) > 63:
        raise ValueError("cluster namespace must be a DNS label")
    return namespace
