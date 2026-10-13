"""Layers in a route tree.

A layer is a place that starts its own load balancer. Crossing into a
container, an SSH host, or a listening server enters a new layer. The
node that opens the layer stays on one worker of the parent layer. Work
under that node is balanced by the layer's own pool.

``cli > docker > ssh > docker > server`` is four crossings. Each crossing
has its own balancer and its own worker count. The call that lands on a
layer node is served outside it. A call that goes past the node is served
inside it.
"""


_KINDS = ("docker", "ssh", "server")


class Layer:
    """One crossing and the pool that belongs to it."""

    def __init__(self, path, kind, balancer, workers):
        self.path = path
        self.kind = kind
        self.balancer = balancer
        self.workers = workers

    def __eq__(self, other):
        return (
            isinstance(other, Layer)
            and self.path == other.path
            and self.kind == other.kind
            and self.balancer == other.balancer
            and self.workers == other.workers
        )

    def __repr__(self):
        return f"Layer({self.path!r}, {self.kind}, balancer={self.balancer!r}, workers={self.workers})"


class Plan:
    """How one path is balanced.

    ``crossings`` lists every layer from the outside in. ``serving`` is the
    pool that runs this path. It is ``None`` when the outermost cli pool
    runs it. ``boundary`` is true when the path is the layer node itself,
    so the parent pool runs it and that node stays on one worker.
    """

    def __init__(self, crossings, serving, boundary):
        self.crossings = list(crossings)
        self.serving = serving
        self.boundary = boundary

    def __repr__(self):
        return f"Plan(boundary={self.boundary}, serving={self.serving!r}, crossings={self.crossings!r})"


def layer_kind(node):
    """Return ``docker``, ``ssh``, ``server``, or ``None``."""
    kind = getattr(node, "layer", None)
    if kind in _KINDS:
        return kind
    origin = getattr(node, "origin", None)
    if origin == "docker":
        return "docker"
    if origin == "ssh":
        return "ssh"
    if getattr(node, "serves", False):
        return "server"
    return None


def balancer_name(node):
    name = getattr(node, "balancer", None)
    if name is None or name == "":
        return "uvicorn"
    return str(name)


def worker_count(node):
    value = getattr(node, "workers", None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return 1
    return value


def plan(router, path):
    """Return the layer plan for ``path``. Missing paths raise ``KeyError``."""
    text = "" if path is None else str(path)
    crossings = []
    node = router
    walked = ""
    parts = [] if text == "" else text.split(".")
    for part in parts:
        routes = getattr(node, "route", None)
        if not isinstance(routes, dict) or part not in routes:
            raise KeyError(text)
        node = routes[part]
        walked = f"{walked}.{part}" if walked else part
        kind = layer_kind(node)
        if kind is not None:
            crossings.append(Layer(walked, kind, balancer_name(node), worker_count(node)))
    if crossings and crossings[-1].path == text:
        parent = crossings[-2] if len(crossings) > 1 else None
        return Plan(crossings, parent, True)
    serving = crossings[-1] if crossings else None
    return Plan(crossings, serving, False)


def layers_of(router):
    """Return every layer in the tree, outer paths first."""
    found = []

    def visit(node, walked):
        kind = layer_kind(node)
        if kind is not None and walked:
            found.append(Layer(walked, kind, balancer_name(node), worker_count(node)))
        routes = getattr(node, "route", None)
        if not isinstance(routes, dict):
            return
        for key in sorted(routes):
            child = routes[key]
            child_path = f"{walked}.{key}" if walked else key
            visit(child, child_path)

    visit(router, "")
    return found
