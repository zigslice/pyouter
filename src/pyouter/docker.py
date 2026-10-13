"""A Docker container as a pyouter node, with the routes inside it.

The container is one node. Commands and HTTP services declared under it are
child nodes, so ``a.b.c.d`` reaches a command or a service inside the
container named ``b``. Running the container node starts it and waits.
Running a child uses that container; it does not start another one.
"""

import asyncio
import hashlib
import re
import subprocess
from urllib.parse import urlparse

from .flatten import ServiceAddress, invoke_endpoint
from .router import Router


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PORT = re.compile(r"^\d+:\d+(?:/[a-zA-Z]+)?$")


class Command:
    """One command executed inside a container with ``docker exec``."""

    kind = "docker"

    def __init__(self, *argv):
        if not argv or any(not isinstance(item, str) or item == "" for item in argv):
            raise ValueError("a container command needs at least one argument")
        self.argv = tuple(argv)
        self.container = None
        self.__name__ = argv[0]

    def run(self, ctx):
        return exec_command(self)

    def __repr__(self):
        return f"Command({' '.join(self.argv)})"


class PublishedRoute:
    """One HTTP request to a port published by a container."""

    kind = "web"

    def __init__(self, method, rule, address):
        self.method = method.upper()
        self.rule = rule
        self.address = address
        self.params = tuple(_param_names(rule))
        self.endpoint = None
        self.doc = ""
        self.container = None
        self.__name__ = self.method.lower()

    def run(self, ctx):
        container = self.container
        if container is None:
            raise RuntimeError("route is not inside a container")
        if not container_running(container):
            raise RuntimeError(
                f"container {container.container_name} is not running; "
                "start it by running the container node"
            )
        return invoke_endpoint(self, ctx)

    def __repr__(self):
        return f"PublishedRoute({self.method} {self.rule})"


class Service(Router):
    """HTTP routes of a process that listens inside a container.

    ``base_url`` is the address on the host, such as ``http://127.0.0.1:8080``.
    Each route is ``name=(method, path)``. Running this node reports the
    address. Running a child sends one request once the container is up.
    """

    def __init__(self, base_url, **routes):
        super().__init__()
        self.origin = "web"
        self.framework = "docker"
        self.address = _address(base_url)
        self.container = None
        for key, spec in routes.items():
            method, rule = _route_spec(spec)
            self.route[key] = PublishedRoute(method, rule, self.address)


class Container(Router):
    """A container whose commands and services are child routes.

    ``routes`` is an ordinary router. A :class:`Command` runs inside the
    container. A :class:`Service` calls a port the container publishes.
    Nested routers add path segments, so ``b.c.d`` is node ``d`` under
    group ``c`` inside container ``b``.

    ``command`` is the process ``docker run`` starts. It defaults to
    ``sleep infinity`` so later commands can exec into a live container.
    ``ports`` are ``docker run -p`` values, such as ``"8080:80"``.
    ``docker`` is the docker executable, so tests can substitute a fake.
    """

    def __init__(self, image, routes=None, name=None, command=None, ports=None, docker="docker"):
        super().__init__()
        if not isinstance(image, str) or image == "" or image.startswith("-"):
            raise ValueError("container image must be a non-empty name")
        self.origin = "docker"
        self.image = image
        self.container_name = _container_name(name, image)
        self.command = _command(command)
        self.ports = _ports(ports)
        self.docker = docker
        self._owns = False
        if routes is not None:
            self.include(routes)

    def include(self, router, prefix=None, host=None, port=None):
        super().include(router, prefix=prefix, host=host, port=port)
        _bind(self, self)
        return self


def exec_command(node):
    """Run ``node`` inside its container. The container is not started here."""
    container = getattr(node, "container", None)
    if container is None:
        raise RuntimeError("command is not inside a container")
    if not container_running(container):
        raise RuntimeError(
            f"container {container.container_name} is not running; "
            "start it by running the container node"
        )
    result = _docker(
        container,
        ["exec", container.container_name, *node.argv],
    )
    if result.out:
        print(result.out, end="" if result.out.endswith("\n") else "\n")
    if result.code != 0:
        detail = (result.err or result.out).strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        message = f"docker exec exited {result.code}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    return {
        "container": container.container_name,
        "argv": list(node.argv),
        "output": result.out,
    }


def container_running(node):
    """Return whether ``node``'s container is running."""
    result = _docker(
        node,
        ["inspect", "-f", "{{.State.Running}}", node.container_name],
        check=False,
    )
    return result.code == 0 and result.out.strip() == "true"


async def start_container(node, ctx):
    """Start ``node`` and keep it until cancelled.

    A second call while that container is already running does not start
    another one. It reports that and returns. Stopping this call removes
    only a container this call started.
    """
    if await asyncio.to_thread(container_running, node):
        print(f"container already running: {node.container_name}")
        return {"status": "running", "container": node.container_name}

    if await asyncio.to_thread(_container_exists, node):
        await asyncio.to_thread(_docker, node, ["rm", "-f", node.container_name])

    argv = ["run", "--name", node.container_name, "-d"]
    for published in node.ports:
        argv.extend(["-p", published])
    argv.append(node.image)
    argv.extend(node.command)
    node._owns = True
    try:
        await asyncio.to_thread(_docker, node, argv)
        print(f"container {node.container_name}")
        while await asyncio.to_thread(container_running, node):
            if ctx is not None and getattr(ctx, "cancelled", False):
                break
            await asyncio.sleep(0.05)
    finally:
        if node._owns:
            await asyncio.to_thread(
                _docker, node, ["rm", "-f", node.container_name], False
            )
            node._owns = False
    if ctx is not None and getattr(ctx, "cancelled", False):
        raise asyncio.CancelledError()
    return {"status": "stopped", "container": node.container_name}


class _Result:
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err


def _docker(node, args, check=True):
    argv = [node.docker, *args]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run {node.docker}") from exc
    result = _Result(completed.returncode, completed.stdout or "", completed.stderr or "")
    if check and result.code != 0:
        detail = (result.err or result.out).strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        message = "docker " + " ".join(args[:1])
        if detail:
            message = f"{message} failed: {detail}"
        else:
            message = f"{message} failed with exit {result.code}"
        raise RuntimeError(message)
    return result


def _container_exists(node):
    result = _docker(
        node,
        ["inspect", "-f", "{{.State.Running}}", node.container_name],
        check=False,
    )
    return result.code == 0


def _bind(container, node):
    if isinstance(node, Router) and getattr(node, "origin", None) == "docker" and node is not container:
        return
    if isinstance(node, (Command, PublishedRoute)):
        node.container = container
        return
    if isinstance(node, Router):
        node.container = container
        for child in node.route.values():
            _bind(container, child)


def _container_name(name, image):
    if name is None:
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", image).strip("-")[:32] or "image"
        digest = hashlib.sha256(image.encode("utf-8")).hexdigest()[:8]
        name = f"pyouter-{slug}-{digest}"
    if not isinstance(name, str) or not _NAME.match(name):
        raise ValueError(
            "container name must start with a letter or digit and use only "
            "letters, digits, '.', '_' or '-'"
        )
    return name


def _command(command):
    if command is None:
        return ("sleep", "infinity")
    if isinstance(command, str) or not command:
        raise ValueError("container command must be a sequence of arguments")
    argv = tuple(command)
    if any(not isinstance(item, str) or item == "" for item in argv):
        raise ValueError("container command arguments must be non-empty strings")
    return argv


def _ports(ports):
    if ports is None:
        return ()
    published = tuple(ports)
    for item in published:
        if not isinstance(item, str) or not _PORT.match(item):
            raise ValueError(f"port must look like 8080:80, got {item!r}")
    return published


def _address(base_url):
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or not parsed.hostname or parsed.port is None:
        raise ValueError(
            "service address needs http host and port, for example http://127.0.0.1:8080"
        )
    return ServiceAddress(parsed.hostname, parsed.port)


def _route_spec(spec):
    if isinstance(spec, str):
        method, _, rule = spec.partition(" ")
        spec = (method, rule)
    if (
        not isinstance(spec, tuple)
        or len(spec) != 2
        or not isinstance(spec[0], str)
        or not isinstance(spec[1], str)
    ):
        raise ValueError("a service route is (method, path), for example ('GET', '/health')")
    method, rule = spec[0].upper(), spec[1]
    if method == "" or not rule.startswith("/"):
        raise ValueError("a service route needs a method and a path that starts with /")
    return method, rule


def _param_names(rule):
    names = []
    for part in rule.split("/"):
        if len(part) >= 2 and part[0] == "{" and part[-1] == "}":
            names.append(part[1:-1].split(":", 1)[0])
        elif len(part) >= 2 and part[0] == "<" and part[-1] == ">":
            body = part[1:-1]
            names.append(body.split(":", 1)[-1])
    return names
