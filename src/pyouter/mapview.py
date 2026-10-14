"""Fields the web map shows for a layer: address, peer, and reachability.

A layer row carries its kind, the runtime address or peer id, any IP that
address names, and whether that address answers. The page served by a node
runtime uses the same shape and marks the layer this process is.
"""

import json
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


_LAYERS = {"docker", "ssh", "cluster", "server"}
_CACHE = {}
_TTL = 3


def place_of(node):
    """Return the map fields stored on a route node."""
    from .layer import layer_kind
    from .peer import is_peer_id

    layer = layer_kind(node) or ""
    runtime = getattr(node, "runtime", None)
    runtime = runtime if isinstance(runtime, str) else ""
    peer_id = runtime if is_peer_id(runtime) else ""
    ip = ""
    host_port = None
    if _is_http(runtime):
        host, port = _split_http(runtime)
        if _is_ip(host):
            ip = host
        host_port = port
    elif not peer_id:
        host, port = _host_of(node)
        if _is_ip(host):
            ip = host
        host_port = port
    sn = _sn_list(getattr(node, "sn", None))
    return {
        "layer": layer,
        "runtime": runtime,
        "peer_id": peer_id,
        "ip": ip,
        "host_port": host_port,
        "sn": sn,
        "reach": "",
        "here": False,
    }


def with_reach(tree):
    """Return a copy of ``tree`` with ``reach`` filled in."""
    cloned = json.loads(json.dumps(tree))
    _fill(cloned)
    return cloned


def tree_from_runtime(specs, info):
    """Build the map for the runtime process described by ``info``.

    ``info`` has ``ip``, ``port``, ``peer_id``, and ``sn``. ``specs`` are
    the slices this process is serving. The outermost of those slices is
    the layer marked here. With no slice, the root itself is that mark.
    """
    paths = [item.get("path") or "" for item in specs if item.get("path")]
    here = _outermost(paths)
    root = _blank("(root)", "")
    if not paths:
        root["name"] = "这个节点"
        root["here"] = True
        root["reach"] = "up"
        root["ip"] = info.get("ip") or ""
        root["host_port"] = info.get("port")
        root["peer_id"] = info.get("peer_id") or ""
        root["sn"] = list(info.get("sn") or [])
        url = _self_url(info)
        if url:
            root["runtime"] = url
        return root, ""

    index = {"": root}
    for spec in specs:
        path = spec.get("path") or ""
        if not path:
            continue
        node = _ensure(index, path)
        kind = spec.get("kind") or ""
        node["layer"] = kind if kind in _LAYERS else ""
        node["route_type"] = kind or node["route_type"]
        node["kind"] = "router"
        node["type"] = "router"
        node["target"] = kind
        node["reach"] = "up"
        node["here"] = path == here
        if path == here:
            node["ip"] = info.get("ip") or ""
            node["host_port"] = info.get("port")
            node["peer_id"] = info.get("peer_id") or ""
            node["sn"] = list(info.get("sn") or [])
            url = _self_url(info)
            if url:
                node["runtime"] = url
    return root, here


def _fill(node):
    node["reach"] = _reach(node)
    for child in node.get("children") or []:
        _fill(child)


def _reach(node):
    runtime = node.get("runtime") or ""
    peer_id = node.get("peer_id") or ""
    if _is_http(runtime):
        return _cached(runtime, lambda: "up" if _http_ok(runtime) else "down")
    if peer_id:
        return _cached("peer:" + peer_id, lambda: "up" if _peer_ok(peer_id) else "down")
    ip = node.get("ip") or ""
    port = node.get("host_port")
    if ip and isinstance(port, int) and port > 0:
        return _cached(f"{ip}:{port}", lambda: "up" if _tcp_ok(ip, port) else "down")
    return ""


def _cached(key, probe):
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < _TTL:
        return hit[1]
    value = probe()
    _CACHE[key] = (now, value)
    return value


def _http_ok(url):
    target = url.rstrip("/") + "/health"
    request = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=0.4) as response:
            raw = response.read()
    except (OSError, urllib.error.URLError, TimeoutError):
        return False
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return bool(isinstance(body, dict) and body.get("ok"))


def _tcp_ok(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def _peer_ok(peer_id):
    from .peer import peer_reachable

    return peer_reachable(peer_id)


def _blank(name, path):
    return {
        "name": name,
        "path": path,
        "type": "router",
        "kind": "router",
        "route_type": "router",
        "method": "",
        "rule": "",
        "target": "",
        "signature": "",
        "doc": "",
        "children": [],
        "layer": "",
        "runtime": "",
        "peer_id": "",
        "ip": "",
        "host_port": None,
        "sn": [],
        "reach": "",
        "here": False,
    }


def _ensure(index, path):
    if path in index:
        return index[path]
    parent_path, _, name = path.rpartition(".")
    parent = index.get(parent_path)
    if parent is None:
        parent = _ensure(index, parent_path) if parent_path else index[""]
    node = _blank(name, path)
    parent["children"].append(node)
    index[path] = node
    return node


def _outermost(paths):
    if not paths:
        return ""
    return min(paths, key=lambda item: (item.count("."), len(item)))


def _self_url(info):
    ip = info.get("ip") or ""
    port = info.get("port")
    if not ip or not port:
        return ""
    host = f"[{ip}]" if ":" in ip and not ip.startswith("[") else ip
    return f"http://{host}:{int(port)}"


def _split_http(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host, parsed.port


def _host_of(node):
    origin = getattr(node, "origin", None)
    if origin == "ssh":
        host = getattr(node, "hostname", None) or ""
        port = getattr(node, "port", None)
        return host, 22 if port is None else int(port)
    address = getattr(node, "address", None)
    if address is not None and getattr(address, "host", None) and getattr(address, "port", None):
        host = address.host
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return host, int(address.port)
    return "", None


def _sn_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _is_http(value):
    return isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))


def _is_ip(host):
    if not isinstance(host, str) or host == "":
        return False
    if host in {"localhost"}:
        return False
    try:
        socket.inet_pton(socket.AF_INET, host)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, host)
        return True
    except OSError:
        return False


def display_ip(host):
    """An address a browser can open for this listen host."""
    if host in {"0.0.0.0", "::", "", None}:
        try:
            name = socket.gethostname()
            resolved = socket.gethostbyname(name)
        except OSError:
            resolved = ""
        if _is_ip(resolved) and not resolved.startswith("127."):
            return resolved
        return "127.0.0.1"
    if host == "localhost":
        return "127.0.0.1"
    return host
