"""Flatten a Flask or FastAPI application into pyouter nodes.

A web application mounted on a router used to be one opaque leaf, so the
routes inside it never appeared in the command line, the task list, or the
local web ui. ``flatten`` reads the application's URL map and turns each HTTP
route into a leaf. Path parameters are read from options, ``options.params``,
or config when that leaf runs.
"""

import inspect
import json
import re
from urllib.parse import quote

from .router import Router


_DOC_ROUTES = {"openapi", "swagger_ui_html", "swagger_ui_redirect", "redoc_html"}
_METHOD_ORDER = ("GET", "POST", "PUT", "PATCH", "DELETE")
_MISSING = object()
_FLASK_PARAM = re.compile(r"^<([^>]+)>$")
_BRACE_PARAM = re.compile(r"^\{([^{}:]+)(?::[^{}]*)?\}$")


class WebEndpoint:
    """One HTTP route exposed as a pyouter leaf."""

    kind = "web"

    def __init__(self, app, framework, method, rule, endpoint, params, doc):
        self.app = app
        self.framework = framework
        self.method = method
        self.rule = rule
        self.endpoint = endpoint
        self.params = tuple(params)
        self.doc = doc or ""
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


def flatten(service):
    """Return a router whose leaves are the HTTP routes of ``service``.

    ``service`` is a Flask application or a FastAPI (or Starlette)
    application. The flattened router runs its endpoints one at a time.
    A path that is only a prefix becomes a router; a single method with no
    child path becomes a leaf named by that path. Several methods on one
    path become children named ``get``, ``post``, and so on. The site root
    is the leaf ``root``.
    """
    framework = detect_framework(service)
    if framework is None:
        raise TypeError(
            "flatten() expects a Flask or FastAPI application, "
            f"got {type(service).__name__}"
        )
    return _flatten(service, framework)


def adopt(value):
    """Flatten a web application. Anything else is returned unchanged."""
    if isinstance(value, Router) or getattr(value, "kind", None) == "web":
        return value
    framework = detect_framework(value)
    if framework is None:
        return value
    return _flatten(value, framework)


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
    """Call one flattened route and return ``status``, ``body``, ``method``, and ``path``."""
    values = _param_values(node, ctx)
    url = _fill(node.rule, values)
    if node.framework == "flask":
        return _invoke_flask(node, url)
    return _invoke_asgi(node, url)


def _flatten(service, framework):
    tree = {"children": {}, "endpoints": {}}
    for record in _collect(service, framework):
        _place(tree, record)
    return _materialize(service, framework, tree, root=True)


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


def _materialize(service, framework, node, *, root=False):
    child_routes = {}
    for key in sorted(node["children"]):
        child_routes[key] = _materialize(service, framework, node["children"][key])
    endpoints = node["endpoints"]
    if not child_routes and len(endpoints) == 1 and not root:
        return _make_endpoint(service, framework, next(iter(endpoints.values())))
    for method, record in sorted(endpoints.items(), key=lambda item: _method_key(item[0])):
        preferred = "root" if not record.segments and len(endpoints) == 1 else method.lower()
        name = _free_key(preferred, child_routes)
        child_routes[name] = _make_endpoint(service, framework, record)
    ordered = {key: child_routes[key] for key in sorted(child_routes)}
    return _web_router(ordered, framework)


def _web_router(routes, framework):
    router = Router(**routes)
    router.policy = "sequence"
    router.origin = "web"
    router.framework = framework
    return router


def _make_endpoint(service, framework, record):
    return WebEndpoint(
        service,
        framework,
        record.method,
        record.rule,
        record.endpoint,
        record.params,
        record.doc,
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


def _invoke_flask(node, url):
    client = node.app.test_client()
    response = client.open(url, method=node.method, follow_redirects=False)
    content_type = response.content_type or ""
    body = response.get_data(as_text=True)
    return _finish(node, url, response.status_code, body, content_type)


def _invoke_asgi(node, url):
    try:
        import warnings

        from starlette.exceptions import StarletteDeprecationWarning

        # Starlette still imports httpx when httpx2 is absent, and warns on
        # that import. Pyouter works with either client.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", StarletteDeprecationWarning)
            from starlette.testclient import TestClient
    except ImportError as exc:
        raise RuntimeError("calling a FastAPI route needs starlette's TestClient") from exc
    with TestClient(node.app, raise_server_exceptions=False) as client:
        response = client.request(node.method, url)
    content_type = response.headers.get("content-type", "")
    return _finish(node, url, response.status_code, response.text, content_type)


def _finish(node, url, status, body, content_type):
    payload = _interpret(body, content_type)
    print(f"{node.method} {url} -> {status}")
    if status >= 400:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        if len(text) > 500:
            text = text[:500] + "…"
        raise RuntimeError(f"{node.method} {url} returned {status}: {text}")
    return {"status": status, "body": payload, "method": node.method, "path": url}


def _interpret(body, content_type):
    if body and content_type and "json" in content_type.lower():
        try:
            return json.loads(body)
        except ValueError:
            return body
    return body
