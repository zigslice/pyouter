"""Flatten a Flask or FastAPI application into pyouter nodes.

A web application mounted on a router used to be one opaque leaf, so the
routes inside it never appeared in the command line, the task list, or the
local web ui. ``flatten`` reads the application's URL map and turns each HTTP
route into a leaf.

Running the service node, inside the pyouter process, starts that
application and leaves it listening. Running a leaf sends one request to
the address that is already listening. It does not boot the application
again.
"""

import asyncio
import inspect
import json
import logging
import re
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

from .router import Router

_DEFAULT_PORT = {"flask": 5000, "fastapi": 8000, "starlette": 8000}


_DOC_ROUTES = {"openapi", "swagger_ui_html", "swagger_ui_redirect", "redoc_html"}
_METHOD_ORDER = ("GET", "POST", "PUT", "PATCH", "DELETE")
_MISSING = object()
_FLASK_PARAM = re.compile(r"^<([^>]+)>$")
_BRACE_PARAM = re.compile(r"^\{([^{}:]+)(?::[^{}]*)?\}$")


class ServiceAddress:
    """Host and port shared by a running service and the routes that call it."""

    def __init__(self, host, port):
        self.host = host
        self.port = int(port)

    @property
    def base_url(self):
        host = self.host
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.port}"


class WebEndpoint:
    """One HTTP route of a service that is already running."""

    kind = "web"

    def __init__(self, app, framework, method, rule, endpoint, params, doc, address):
        self.app = app
        self.framework = framework
        self.method = method
        self.rule = rule
        self.endpoint = endpoint
        self.params = tuple(params)
        self.doc = doc or ""
        self.address = address
        self.__name__ = getattr(endpoint, "__name__", method.lower())

    def run(self, ctx):
        return invoke_endpoint(self, ctx)

    def __repr__(self):
        return f"WebEndpoint({self.method} {self.rule})"


class _Record:
    def __init__(self, segments, method, rule, endpoint, params, doc):
        self.segments = tuple(segments)
        self.method = method
        self.rule = rule
        self.endpoint = endpoint
        self.params = tuple(params)
        self.doc = doc or ""


def flatten(service, host="127.0.0.1", port=None):
    """Return a router whose leaves are the HTTP routes of ``service``.

    ``service`` is a Flask application or a FastAPI (or Starlette)
    application. Running the returned router starts the service at
    ``host`` and ``port`` and keeps it listening. Running a leaf sends a
    request to that address. A path that is only a prefix becomes a router;
    a single method with no child path becomes a leaf named by that path.
    Several methods on one path become children named ``get``, ``post``, and
    so on. The site root is the leaf ``root``.
    """
    framework = detect_framework(service)
    if framework is None:
        raise TypeError(
            "flatten() expects a Flask or FastAPI application, "
            f"got {type(service).__name__}"
        )
    return _flatten(service, framework, host=host, port=port)


def adopt(value, host=None, port=None):
    """Flatten a web application. Anything else is returned unchanged."""
    if isinstance(value, Router) or getattr(value, "kind", None) == "web":
        if isinstance(value, Router) and (host is not None or port is not None):
            _apply_address(value, host, port)
        return value
    framework = detect_framework(value)
    if framework is None:
        return value
    return _flatten(value, framework, host=host or "127.0.0.1", port=port)


def detect_framework(obj):
    """Return ``flask``, ``fastapi``, ``starlette``, or ``None``."""
    if obj is None or isinstance(obj, (str, bytes, bytearray, Router)):
        return None
    if getattr(obj, "kind", None) == "web":
        return None
    if _looks_like_flask(obj):
        return "flask"
    return _looks_like_asgi(obj)


def invoke_endpoint(node, ctx):
    """Send one request to the running service.

    The application is not started here. Start it by running the service node.
    """
    values = _param_values(node, ctx)
    route_path = _fill(node.rule, values)
    url = node.address.base_url.rstrip("/") + route_path
    return _http_call(node, route_path, url)


def _apply_address(router, host, port):
    address = getattr(router, "address", None)
    if address is None:
        return
    if host is not None:
        address.host = host
    if port is not None:
        address.port = int(port)


def _flatten(service, framework, host, port):
    if port is None:
        port = _DEFAULT_PORT.get(framework, 8000)
    address = ServiceAddress(host, port)
    tree = {"children": {}, "endpoints": {}}
    for record in _collect(service, framework):
        _place(tree, record)
    router = _materialize(service, framework, tree, address, root=True)
    router.app = service
    return router


def _collect(service, framework):
    if framework == "flask":
        yield from _collect_flask(service)
        return
    yield from _collect_asgi(service)


def _collect_flask(app):
    for rule in app.url_map.iter_rules():
        endpoint_name = rule.endpoint
        if endpoint_name == "static" or str(endpoint_name).endswith(".static"):
            continue
        if getattr(rule, "websocket", False):
            continue
        endpoint = app.view_functions.get(endpoint_name)
        if endpoint is None:
            continue
        segments, params = _split_path(rule.rule)
        doc = inspect.getdoc(endpoint) or ""
        for method in _http_methods(rule.methods):
            yield _Record(segments, method, rule.rule, endpoint, params, doc)


def _collect_asgi(app, prefix=""):
    for route in _expand_included(app):
        yield from _collect_asgi_route(route, prefix)


def _expand_included(app):
    """Yield route objects, unfolding FastAPI included routers.

    Recent FastAPI keeps an included ``APIRouter`` as one ``_IncludedRouter``.
    Its own ``path`` is only the router prefix; ``effective_candidates()``
    carries the prefix from every surrounding ``include_router``.
    """
    routes = getattr(app, "routes", None) or []
    for route in routes:
        yield from _expand_route(route)


def _expand_route(route):
    expand = getattr(route, "effective_candidates", None)
    if expand is not None and getattr(route, "original_router", None) is not None:
        for candidate in expand():
            yield from _expand_route(candidate)
        return
    yield route


def _collect_asgi_route(route, prefix):
    name = getattr(route, "name", None)
    if name in _DOC_ROUTES:
        return
    mounted = getattr(route, "app", None)
    if mounted is not None and type(mounted).__name__ == "StaticFiles":
        return
    methods = getattr(route, "methods", None)
    endpoint = getattr(route, "endpoint", None)
    path = getattr(route, "path", None) or getattr(route, "path_format", None)
    if methods and path and endpoint is not None:
        full = _join(prefix, path)
        segments, params = _split_path(full)
        doc = inspect.getdoc(endpoint) or ""
        for method in _http_methods(methods):
            yield _Record(segments, method, full, endpoint, params, doc)
        return
    subroutes = getattr(route, "routes", None)
    nested = route
    if subroutes is None and mounted is not None:
        subroutes = getattr(mounted, "routes", None)
        nested = mounted
    if subroutes is not None and path:
        yield from _collect_asgi(nested, _join(prefix, path))


def _place(tree, record):
    node = tree
    for segment in record.segments:
        children = node["children"]
        if segment not in children:
            children[segment] = {"children": {}, "endpoints": {}}
        node = children[segment]
    current = node["endpoints"].get(record.method)
    if current is not None:
        raise ValueError(
            f"{current.method} {current.rule} and {record.method} {record.rule} "
            "flatten to the same pyouter node"
        )
    node["endpoints"][record.method] = record


def _materialize(service, framework, node, address, *, root=False):
    child_routes = {}
    for key in sorted(node["children"]):
        child_routes[key] = _materialize(service, framework, node["children"][key], address)
    endpoints = node["endpoints"]
    if not child_routes and len(endpoints) == 1 and not root:
        return _make_endpoint(service, framework, next(iter(endpoints.values())), address)
    for method, record in sorted(endpoints.items(), key=lambda item: _method_key(item[0])):
        preferred = "root" if not record.segments and len(endpoints) == 1 else method.lower()
        name = _free_key(preferred, child_routes)
        child_routes[name] = _make_endpoint(service, framework, record, address)
    ordered = {key: child_routes[key] for key in sorted(child_routes)}
    return _web_router(ordered, framework, address, serves=root)


def _web_router(routes, framework, address, serves):
    router = Router(**routes)
    router.origin = "web"
    router.framework = framework
    router.address = address
    router.serves = serves
    return router


def _make_endpoint(service, framework, record, address):
    return WebEndpoint(
        service,
        framework,
        record.method,
        record.rule,
        record.endpoint,
        record.params,
        record.doc,
        address,
    )


def _looks_like_flask(obj):
    url_map = getattr(obj, "url_map", None)
    if url_map is None or not hasattr(url_map, "iter_rules"):
        return False
    return hasattr(obj, "view_functions") and hasattr(obj, "test_client")


def _looks_like_asgi(obj):
    routes = getattr(obj, "routes", None)
    if not isinstance(routes, list) or not callable(obj):
        return None
    if hasattr(obj, "add_api_route") and hasattr(obj, "openapi"):
        return "fastapi"
    for cls in type(obj).mro():
        module = getattr(cls, "__module__", "") or ""
        if module.startswith("fastapi"):
            return "fastapi"
        if module.startswith("starlette."):
            return "starlette"
    if type(obj).__name__ == "Starlette" and hasattr(obj, "add_route") and hasattr(obj, "mount"):
        return "starlette"
    return None


def _split_path(rule):
    segments = []
    params = []
    for part in str(rule).split("/"):
        if part == "":
            continue
        flask_param = _FLASK_PARAM.match(part)
        brace_param = _BRACE_PARAM.match(part)
        if flask_param:
            body = flask_param.group(1)
            name = body.split(":", 1)[1] if ":" in body else body
            params.append(name)
            segments.append(_safe(name))
        elif brace_param:
            name = brace_param.group(1)
            params.append(name)
            segments.append(_safe(name))
        else:
            segments.append(_safe(part))
    return segments, params


def _safe(name):
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    if not cleaned:
        cleaned = "item"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _join(prefix, path):
    left = prefix or ""
    right = path or ""
    if not left:
        return right or "/"
    if not right or right == "/":
        return left
    return left.rstrip("/") + "/" + right.lstrip("/")


def _http_methods(methods):
    found = []
    for method in methods or []:
        name = str(method).upper()
        if name not in found:
            found.append(name)
    primary = [method for method in found if method not in {"HEAD", "OPTIONS"}]
    return sorted(primary or found, key=_method_key)


def _method_key(method):
    try:
        return (0, _METHOD_ORDER.index(method))
    except ValueError:
        return (1, method)


def _free_key(name, taken):
    if name not in taken:
        return name
    if f"_{name}" not in taken:
        return f"_{name}"
    index = 2
    while f"{name}_{index}" in taken:
        index += 1
    return f"{name}_{index}"


def _param_values(node, ctx):
    options = getattr(ctx, "options", None)
    config = getattr(ctx, "config", None)
    bag = getattr(options, "params", None) if options is not None else None
    option_data = getattr(options, "__dict__", None) if options is not None else None
    values = {}
    for name in node.params:
        value = _MISSING
        if isinstance(option_data, dict) and name in option_data:
            value = option_data[name]
        elif isinstance(bag, dict) and name in bag:
            value = bag[name]
        elif isinstance(config, dict) and name in config:
            value = config[name]
        if value is _MISSING or value is None:
            raise ValueError(f"missing path parameter '{name}' for {node.method} {node.rule}")
        values[name] = value
    return values


def _fill(rule, values):
    def replace_flask(match):
        body = match.group(1)
        name = body.split(":", 1)[1] if ":" in body else body
        return _quote_param(name, values, rule)

    def replace_brace(match):
        name = match.group(1).split(":", 1)[0]
        return _quote_param(name, values, rule)

    filled = re.sub(r"<([^>]+)>", replace_flask, rule)
    return re.sub(r"\{([^{}]+)\}", replace_brace, filled)


def _quote_param(name, values, rule):
    if name not in values:
        raise ValueError(f"missing path parameter '{name}' for {rule}")
    return quote(str(values[name]), safe="/")


def listening(address):
    """Return whether a TCP service is already accepting connections."""
    if not address or not address.port:
        return False
    host = address.host
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, int(address.port))) == 0


async def serve_service(node, ctx):
    """Start ``node`` and keep it listening until cancelled.

    A second call while that address is already open does not start another
    process. It reports that the service is already running and returns.
    """
    if listening(node.address):
        url = node.address.base_url
        print(f"web service already running at {url}")
        from .segment import host_is_ready
        host_is_ready()
        return {"status": "running", "url": url}

    handle = _ServerHandle(node)
    try:
        await asyncio.to_thread(handle.start)
        if handle.errors:
            if listening(node.address):
                url = node.address.base_url
                print(f"web service already running at {url}")
                return {"status": "running", "url": url}
            raise RuntimeError(f"cannot bind {node.address.base_url}: {handle.errors[0]}")
        print(f"web service {node.address.base_url}")
        from .segment import host_is_down, host_is_ready
        host_is_ready()
        try:
            while handle.thread is not None and handle.thread.is_alive():
                if ctx is not None and getattr(ctx, "cancelled", False):
                    break
                await asyncio.sleep(0.05)
        finally:
            host_is_down()
    finally:
        await asyncio.to_thread(handle.stop)
    if ctx is not None and getattr(ctx, "cancelled", False):
        raise asyncio.CancelledError()
    return {"status": "stopped", "url": node.address.base_url}


class _ServerHandle:
    def __init__(self, node):
        self.node = node
        self.thread = None
        self.httpd = None
        self.stop_event = threading.Event()
        self.started = threading.Event()
        self.errors = []

    def start(self):
        self.thread = threading.Thread(
            target=self._run,
            name="pyouter-web-service",
            daemon=True,
        )
        self.thread.start()
        self.started.wait(5)
        if not self.started.is_set() and not self.errors:
            self.errors.append(RuntimeError("web service did not start"))

    def stop(self):
        self.stop_event.set()
        httpd = self.httpd
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
        thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _run(self):
        try:
            if self.node.framework == "flask":
                self._run_flask()
            else:
                self._run_asgi()
        except BaseException as exc:
            # uvicorn calls sys.exit when a port is already taken. In this
            # thread that must not end the pyouter process.
            if isinstance(exc, Exception):
                self.errors.append(exc)
            else:
                self.errors.append(RuntimeError(str(exc) or exc.__class__.__name__))
            self.started.set()

    def _run_flask(self):
        from werkzeug.serving import make_server

        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        self.httpd = make_server(
            self.node.address.host,
            self.node.address.port,
            self.node.app,
            threaded=True,
        )
        self.node.address.port = self.httpd.server_port
        self.started.set()
        self.httpd.serve_forever()

    def _run_asgi(self):
        try:
            import uvicorn
        except ImportError as exc:
            raise RuntimeError("starting a FastAPI service needs uvicorn") from exc

        config = uvicorn.Config(
            self.node.app,
            host=self.node.address.host,
            port=self.node.address.port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = False
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._asgi_until_stopped(server))
        finally:
            loop.close()

    async def _asgi_until_stopped(self, server):
        task = asyncio.create_task(server.serve())
        startup_error = None
        try:
            while True:
                if _server_ready(server):
                    break
                if task.done() or self.stop_event.is_set():
                    break
                await asyncio.sleep(0.05)
            if task.done():
                startup_error = task.exception()
                return
            self.started.set()
            while not self.stop_event.is_set() and not task.done():
                await asyncio.sleep(0.05)
        finally:
            server.should_exit = True
            if not task.done():
                await task
        if startup_error is not None:
            raise startup_error


def _server_ready(server):
    started = getattr(server, "started", None)
    if isinstance(started, bool):
        return started
    is_set = getattr(started, "is_set", None)
    if callable(is_set):
        return bool(is_set())
    return False


def _http_call(node, route_path, url):
    data = b"" if node.method in {"POST", "PUT", "PATCH"} else None
    request = urllib.request.Request(url, data=data, method=node.method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("Content-Type", "")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        status = exc.code
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"web service is not running at {node.address.base_url}; "
            "start it by running the service node"
        ) from exc
    return _finish(node, route_path, url, status, body, content_type)


def _finish(node, route_path, url, status, body, content_type):
    payload = _interpret(body, content_type)
    print(f"{node.method} {url} -> {status}")
    if status >= 400:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        if len(text) > 500:
            text = text[:500] + "…"
        raise RuntimeError(f"{node.method} {url} returned {status}: {text}")
    return {
        "status": status,
        "body": payload,
        "method": node.method,
        "path": route_path,
        "url": url,
    }


def _interpret(body, content_type):
    if body and content_type and "json" in content_type.lower():
        try:
            return json.loads(body)
        except ValueError:
            return body
    return body
