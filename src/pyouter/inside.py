"""A pyouter tree running inside a container.

Starting a container boots this runtime as the container's main process.
The ``routes`` written on that container are the tree it serves. The
processes named by ``workers`` are the pool inside the container: a call
that has crossed the container boundary is handed to this runtime, and the
runtime spreads that call across those processes.
"""

import socket
import subprocess
import sys
from pathlib import Path

from .router import Router


INSIDE_PORT = 7711


def install(app, path):
    """Replace ``app.router`` with the tree mounted inside the container at ``path``."""
    node = app.router
    text = "" if path is None else str(path)
    if text and text != ".":
        for part in text.split("."):
            routes = getattr(node, "route", None)
            if not isinstance(routes, dict) or part not in routes:
                return
            node = routes[part]
    inner = Router()
    routes = getattr(node, "route", None)
    if isinstance(routes, dict):
        for key, child in routes.items():
            inner.route[key] = child
    app.router = inner


def launch(node, route_path):
    """Return ``(docker_args, command)`` that boot the inner tree, or None.

    The image stays the one given to the container. pyouter mounts its own
    source and the application script, then starts ``python`` on that
    script. No Dockerfile is written.
    """
    if not getattr(node, "hosts_inside", False) or route_path is None:
        return None
    script = Path(sys.argv[0]).resolve()
    package_root = Path(__file__).resolve().parents[1]
    port = _free_port()
    node.inner_port = port
    node.inside_path = "" if route_path is None else str(route_path)
    workers = getattr(node, "workers", 2)
    try:
        workers = int(workers)
    except (TypeError, ValueError):
        workers = 2
    if workers < 1:
        workers = 1
    args = [
        "-v", f"{package_root}:/opt/pyouter:ro",
        "-v", f"{script.parent}:/opt/app:ro",
        "-w", "/opt/app",
        "-e", "PYTHONPATH=/opt/pyouter",
        "-e", f"PYOUTER_INSIDE={node.inside_path}",
        "-e", f"PYOUTER_INSIDE_WORKERS={workers}",
        "-e", f"PYOUTER_INSIDE_PORT={INSIDE_PORT}",
        "-p", f"127.0.0.1:{port}:{INSIDE_PORT}",
    ]
    return args, ["python", f"/opt/app/{script.name}"]


def enclosing_docker(router, path):
    """Return the container path that contains ``path``.

    The container node itself is not inside its own tree, so that path
    returns None.
    """
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
        if getattr(node, "origin", None) == "docker":
            found = walked
    if found is None or found == text:
        return None
    return found


def forward_plan(router, path):
    """Return ``(container_path, relative_path, port)`` when the inner runtime is up."""
    gate = enclosing_docker(router, path)
    if gate is None or not path.startswith(gate + "."):
        return None
    node = router
    for part in gate.split("."):
        node = node.route[part]
    port = getattr(node, "inner_port", None)
    if not port:
        return None
    return gate, path[len(gate) + 1:], int(port)


def local_command(node):
    """Run a command in this process. Used when this process is already inside the container."""
    completed = subprocess.run(list(node.argv), capture_output=True, text=True)
    out = completed.stdout or ""
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if completed.returncode != 0:
        detail = (completed.stderr or out).strip()
        message = f"command exited {completed.returncode}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)
    return {"container": "inside", "argv": list(node.argv), "output": out}


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
