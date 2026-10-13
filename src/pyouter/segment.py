"""Flat segments of one route tree.

A Docker container, a Compose project, an SSH host, or a web service is a
boundary. The routers and commands written under it in Python are the next
segment. Starting the boundary opens that segment; stopping it closes the
segment. Workers joined to a segment can run its leaves. The boundary node
itself stays on the worker that claimed it.

A container's ``routes`` are started as another pyouter inside that
container. The pool inside the container is separate from the pool outside
it. A call that crosses the container is delivered to the inner pyouter,
which then chooses one of its own workers.
"""

import contextvars
import hashlib
import inspect
import json
import os
from contextlib import contextmanager
from pathlib import Path

from .router import Router


_board = contextvars.ContextVar("pyouter_segment_board", default=None)
_worker = contextvars.ContextVar("pyouter_segment_worker", default=None)
_path = contextvars.ContextVar("pyouter_segment_path", default=None)

_ROOT = ""
_INTERIOR = "."


class Placement:
    """Where one path sits relative to host boundaries.

    ``segment`` is the pool that may run this path. ``bound`` is true when
    the path is a boundary node, so only its owner may run it. ``boundary``
    is the host path that opened ``segment`` (``None`` on the outer pool).
    """

    def __init__(self, segment, bound, boundary):
        self.segment = segment
        self.bound = bound
        self.boundary = boundary

    def __eq__(self, other):
        return (
            isinstance(other, Placement)
            and self.segment == other.segment
            and self.bound == other.bound
            and self.boundary == other.boundary
        )

    def __repr__(self):
        return f"Placement({self.segment!r}, bound={self.bound}, boundary={self.boundary!r})"


def locate(router, path):
    """Return the segment placement of ``path``, or ``None`` when it is absent."""
    text = "" if path is None else str(path)
    if text == "":
        if _boundary(router):
            return Placement(_ROOT, True, _ROOT)
        return Placement(_ROOT, False, None)
    segment = _INTERIOR if _boundary(router) else _ROOT
    boundary = _ROOT if _boundary(router) else None
    node = router
    walked = ""
    parts = text.split(".")
    for index, part in enumerate(parts):
        routes = getattr(node, "route", None)
        if not isinstance(node, Router) or not isinstance(routes, dict) or part not in routes:
            return None
        node = routes[part]
        walked = f"{walked}.{part}" if walked else part
        if _boundary(node):
            if index == len(parts) - 1:
                return Placement(segment, True, walked)
            segment = walked
            boundary = walked
    return Placement(segment, False, boundary)


def activate(board, worker):
    """Use ``board`` for host lifetime on this thread. Return the reset tokens."""
    return _board.set(board), _worker.set(str(worker))


def bind_path(path):
    """Remember the route path while a boundary is starting."""
    return _path.set("" if path is None else str(path))


def reset_path(token):
    _path.reset(token)


def host_is_ready():
    """Open the interior segment of the boundary that just came up."""
    board = _board.get()
    path = _path.get()
    worker = _worker.get()
    if board is None or path is None or not worker:
        return
    board.ready(path, worker)


def host_is_down():
    """Close the interior segment when its owner stops the boundary."""
    board = _board.get()
    path = _path.get()
    worker = _worker.get()
    if board is None or path is None or not worker:
        return
    board.down(path, worker)


class SegmentBoard:
    """Workers, owners, and open segments for one application script.

    The outer pool is always open. A boundary's interior opens when that
    host is ready, and every live worker joins it. Leaves in an open
    segment are spread across those workers. A boundary node, and an object
    that keeps ``self``, stay on the worker that claimed them.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "board.json"
        self.lockfile = self.root / "board.lock"

    @classmethod
    def for_script(cls, script=None):
        return cls(Path.home() / ".pyouter" / "segments" / script_digest(script))

    def register(self, pid, port):
        """Add a live worker and join it to every segment that is already open."""
        wid = str(pid)
        with self._locked():
            data = self._load()
            segments = list(data["open"])
            data["workers"][wid] = {"pid": int(pid), "port": int(port), "segments": segments}
            self._save(data)
        return wid

    def unregister(self, pid):
        wid = str(pid)
        with self._locked():
            data = self._load()
            data["workers"].pop(wid, None)
            for key, owner in list(data["owners"].items()):
                if owner == wid:
                    data["owners"].pop(key, None)
            self._save(data)

    def ready(self, path, worker):
        """The boundary at ``path`` is up and owned by ``worker``."""
        interior = _interior(path)
        with self._locked():
            data = self._load()
            data["owners"][path] = str(worker)
            if interior not in data["open"]:
                data["open"].append(interior)
            for info in data["workers"].values():
                if interior not in info["segments"]:
                    info["segments"].append(interior)
            self._save(data)

    def down(self, path, worker):
        """Close ``path`` when ``worker`` is the owner that stopped it."""
        interior = _interior(path)
        with self._locked():
            data = self._load()
            if data["owners"].get(path) == str(worker):
                data["owners"].pop(path, None)
            if interior != _ROOT and interior in data["open"]:
                data["open"].remove(interior)
            for info in data["workers"].values():
                segments = info["segments"]
                if interior != _ROOT and interior in segments:
                    segments.remove(interior)
            self._save(data)

    def assign(self, router, path, worker):
        """Choose the worker that should run ``path``.

        Return ``None`` when ``path`` is not in the tree. A closed interior
        is delivered on the outer pool, so the leaf can report that the host
        is not running.
        """
        place = locate(router, path)
        if place is None:
            return None
        node = _node_at(router, path)
        me = str(worker)
        with self._locked():
            data = self._load()
            self._drop_dead(data)
            from .inside import enclosing_docker
            gate = enclosing_docker(router, path)
            if gate is not None:
                if gate in data["open"]:
                    owner = data["owners"].get(gate)
                    if owner and owner in data["workers"]:
                        self._save(data)
                        return owner
                chosen = self._pick(data, _ROOT) or me
                self._save(data)
                return chosen
            if place.bound or _sticky(node):
                key = place.boundary if place.bound else path
                owner = data["owners"].get(key)
                if owner and owner in data["workers"]:
                    self._save(data)
                    return owner
                chosen = self._pick(data, place.segment) or me
                data["owners"][key] = chosen
                self._save(data)
                return chosen
            if place.segment not in data["open"]:
                chosen = self._pick(data, _ROOT) or me
                self._save(data)
                return chosen
            chosen = self._pick(data, place.segment) or me
            self._save(data)
            return chosen

    def port(self, worker):
        with self._locked():
            data = self._load()
            info = data["workers"].get(str(worker))
            if not info or not _alive(info.get("pid")):
                return None
            return info.get("port")

    def owner(self, path):
        with self._locked():
            return self._load()["owners"].get(path)

    def is_open(self, path):
        interior = _interior(path) if path != _ROOT else _ROOT
        with self._locked():
            return interior in self._load()["open"]

    def members(self, segment):
        with self._locked():
            data = self._load()
            return [
                wid
                for wid, info in data["workers"].items()
                if segment in info["segments"] and _alive(info.get("pid"))
            ]

    @contextmanager
    def _locked(self):
        import fcntl

        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.lockfile, "a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _load(self):
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            data = {}
        workers = data.get("workers")
        owners = data.get("owners")
        opened = data.get("open")
        rr = data.get("rr")
        if not isinstance(workers, dict):
            workers = {}
        if not isinstance(owners, dict):
            owners = {}
        if not isinstance(opened, list):
            opened = [_ROOT]
        if _ROOT not in opened:
            opened.insert(0, _ROOT)
        if not isinstance(rr, dict):
            rr = {}
        return {"workers": workers, "owners": owners, "open": opened, "rr": rr}

    def _save(self, data):
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        temporary = self.file.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.file)

    def _drop_dead(self, data):
        dead = [wid for wid, info in data["workers"].items() if not _alive(info.get("pid"))]
        for wid in dead:
            data["workers"].pop(wid, None)
            for key, owner in list(data["owners"].items()):
                if owner == wid:
                    data["owners"].pop(key, None)

    def _pick(self, data, segment):
        members = [
            wid
            for wid, info in data["workers"].items()
            if segment in info.get("segments", []) and _alive(info.get("pid"))
        ]
        if not members:
            return None
        members.sort()
        cursor = int(data["rr"].get(segment, 0))
        chosen = members[cursor % len(members)]
        data["rr"][segment] = cursor + 1
        return chosen


def script_digest(script=None):
    raw = __import__("sys").argv[0] if script is None else script
    resolved = str(Path(raw).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:20]


def _boundary(node):
    if not isinstance(node, Router):
        return False
    if getattr(node, "origin", None) in {"docker", "compose", "ssh"}:
        return True
    return bool(getattr(node, "serves", False))


def _interior(path):
    if path == _ROOT:
        return _INTERIOR
    return path


def _node_at(router, path):
    text = "" if path is None else str(path)
    if text == "":
        return router
    node = router
    for part in text.split("."):
        routes = getattr(node, "route", None)
        if not isinstance(routes, dict) or part not in routes:
            return None
        node = routes[part]
    return node


def _sticky(node):
    """An object with ``run`` keeps its state on one worker."""
    if node is None or isinstance(node, Router):
        return False
    if inspect.isfunction(node) or inspect.ismethod(node):
        return False
    if getattr(node, "kind", None) in {"docker", "ssh", "web"}:
        return False
    return hasattr(node, "run")


def _alive(pid):
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
