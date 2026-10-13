"""Docker containers and Compose projects as pyouter nodes.

A container is one node. Commands and HTTP services declared under it are
child nodes, so ``a.b.c.d`` reaches a command or a service inside the
container named ``b``. A Compose file is a project node whose services are
children. Running the project starts the stack and waits. A command under
``web`` runs in that service; it does not start another stack.
"""

import asyncio
import hashlib
import json
import re
import subprocess
from pathlib import Path
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
        if not host_running(container):
            raise RuntimeError(host_down_message(container))
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
        _bind_host(self, self)
        return self


class ComposeService(Router):
    """One service from a Compose file.

    Running it reports the service. It does not start the project and it
    does not call the commands under it.
    """

    def __init__(self, project, name, image, ports):
        super().__init__()
        self.origin = "compose-service"
        self.project = project
        self.service_name = name
        self.image = image or ""
        self.ports = tuple(ports)
        self.docker = project.docker

    def include(self, router, prefix=None, host=None, port=None):
        super().include(router, prefix=prefix, host=host, port=port)
        _bind_host(self, self)
        return self


class Compose(Router):
    """A Compose project. Each service in the file is a child node.

    ``routes`` adds commands and HTTP routes onto those services, keyed by
    service name. ``web=Router(ping=Command("echo", "ok"))`` makes
    ``stack.web.ping`` run inside the ``web`` service. Mount the project
    with a prefix, because that prefix is the node that starts the stack.

    Reading a ``.yml`` or ``.yaml`` file needs PyYAML. A ``.json`` Compose
    file uses the standard library.
    """

    def __init__(self, file, routes=None, project=None, docker="docker"):
        super().__init__()
        path = Path(file)
        if not path.is_file():
            raise ValueError(f"compose file not found: {file}")
        data = _load_compose(path)
        services = data["services"]
        self.origin = "compose"
        self.file = str(path.resolve())
        self.project_name = _project_name(project, data, path)
        self.docker = docker
        self._owns = False
        user = _user_routes(routes, services)
        for name, spec in services.items():
            image, ports = _service_meta(spec)
            service = ComposeService(self, name, image, ports)
            extra = user.get(name)
            if extra is not None:
                service.include(extra)
            self.route[name] = service

    def _base(self):
        return ["compose", "-f", self.file, "-p", self.project_name]


def exec_command(node):
    """Run ``node`` inside its container or Compose service.

    The container or project is not started here.
    """
    host = getattr(node, "container", None)
    if host is None:
        raise RuntimeError("command is not inside a container")
    if not host_running(host):
        raise RuntimeError(host_down_message(host))
    if isinstance(host, ComposeService):
        project = host.project
        argv = [*project._base(), "exec", "-T", host.service_name, *node.argv]
        label = f"{project.project_name}/{host.service_name}"
        result = _docker(project, argv)
    else:
        label = host.container_name
        result = _docker(host, ["exec", host.container_name, *node.argv])
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
        "container": label,
        "argv": list(node.argv),
        "output": result.out,
    }


def host_running(node):
    """Return whether the container or Compose project for ``node`` is up."""
    if isinstance(node, ComposeService):
        return project_running(node.project)
    return container_running(node)


def host_down_message(node):
    if isinstance(node, ComposeService):
        return (
            f"compose project {node.project.project_name} is not running; "
            "start it by running the compose node"
        )
    return (
        f"container {node.container_name} is not running; "
        "start it by running the container node"
    )


def project_running(project):
    """Return whether any service in ``project`` is running."""
    result = _docker(
        project,
        [*project._base(), "ps", "--status", "running", "-q"],
        check=False,
    )
    return result.code == 0 and bool(result.out.strip())


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


async def start_compose(node, ctx):
    """Start ``node`` and keep the stack until cancelled.

    A second call while the project is already running does not start
    another stack. Stopping this call removes only a stack this call started.
    """
    if await asyncio.to_thread(project_running, node):
        print(f"compose project already running: {node.project_name}")
        return {"status": "running", "project": node.project_name}

    node._owns = True
    try:
        await asyncio.to_thread(_docker, node, [*node._base(), "up", "-d"])
        print(f"compose project {node.project_name}")
        while await asyncio.to_thread(project_running, node):
            if ctx is not None and getattr(ctx, "cancelled", False):
                break
            await asyncio.sleep(0.05)
    finally:
        if node._owns:
            await asyncio.to_thread(_docker, node, [*node._base(), "down"], False)
            node._owns = False
    if ctx is not None and getattr(ctx, "cancelled", False):
        raise asyncio.CancelledError()
    return {"status": "stopped", "project": node.project_name}


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


def _bind_host(host, node):
    origin = getattr(node, "origin", None)
    if (
        isinstance(node, Router)
        and node is not host
        and origin in {"docker", "compose", "compose-service"}
    ):
        return
    if isinstance(node, (Command, PublishedRoute)):
        node.container = host
        return
    if isinstance(node, Router):
        for child in node.route.values():
            _bind_host(host, child)


def _load_compose(path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"compose file is not valid JSON: {path}") from exc
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("reading a compose file needs PyYAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("compose file must be a mapping")
    services = data.get("services")
    if not isinstance(services, dict) or not services:
        raise ValueError("compose file has no services")
    for name, spec in services.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
            raise ValueError(
                f"compose service '{name}' cannot be a route segment; "
                "use letters, digits, '_' or '-'"
            )
        if not isinstance(spec, dict):
            raise ValueError(f"compose service '{name}' must be a mapping")
    return data


def _user_routes(routes, services):
    if routes is None:
        return {}
    if not isinstance(routes, Router):
        raise TypeError("compose routes must be a Router keyed by service name")
    unknown = [key for key in routes.route if key not in services]
    if unknown:
        raise ValueError(f"compose file has no service '{unknown[0]}'")
    for key, value in routes.route.items():
        if not isinstance(value, Router) or getattr(value, "origin", None) in {"docker", "compose"}:
            raise TypeError(f"routes for service '{key}' must be a router of commands or HTTP routes")
    return routes.route


def _project_name(project, data, path):
    if project is None:
        named = data.get("name")
        project = named if isinstance(named, str) and named else path.stem
    return _container_name(project, project)


def _service_meta(spec):
    image = spec.get("image") or ""
    if not isinstance(image, str):
        image = ""
    return image, _compose_ports(spec.get("ports"))


def _compose_ports(ports):
    if ports is None:
        return ()
    if isinstance(ports, (str, int, dict)):
        ports = [ports]
    found = []
    for item in ports:
        text = _port_text(item)
        if text:
            found.append(text)
    return tuple(found)


def _port_text(item):
    if isinstance(item, int):
        return str(item)
    if isinstance(item, str):
        text = item.strip()
        return text or None
    if isinstance(item, dict):
        published = item.get("published")
        target = item.get("target")
        if published is not None and target is not None:
            return f"{published}:{target}"
        if published is not None:
            return str(published)
        if target is not None:
            return str(target)
    return None


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
