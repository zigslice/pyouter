"""Per-run context and the result of executing a route."""

import inspect
import sys


class Hooks:
    """Observers for one dispatch.

    ``before`` runs when a node is about to start. ``after`` runs when it
    finishes, including errors and cancellation. ``on_error`` runs only when
    the node itself fails. Listeners may be sync or async and receive one
    event dict.
    """

    def __init__(self):
        self.before = []
        self.after = []
        self.on_error = []

    async def emit(self, phase, event):
        for fn in list(getattr(self, phase)):
            result = fn(event)
            if inspect.isawaitable(result):
                await result


class Context:
    """One execution.

    A command-line run has one context for the process. The local web ui
    builds a new context for each click. ``config`` and ``options`` are the
    values shared with the application; hooks and the cancel flag belong to
    this run.
    """

    def __init__(self, config, options, executor=None, hooks=None):
        self.config = config
        self.options = options
        self.executor = executor
        self.hooks = hooks if hooks is not None else Hooks()
        self._cancelled = False

    def log(self, message, stream="stdout"):
        file = sys.stderr if stream == "stderr" else sys.stdout
        print(message, file=file)

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self):
        return self._cancelled


class NodeResult:
    """Outcome of one node, including the outcomes of its children."""

    def __init__(self, path, status, value=None, error=None, exc_type=None, children=None):
        self.path = path
        self.status = status
        self.value = value
        self.error = error
        self.exc_type = exc_type
        self.children = list(children) if children is not None else []

    @property
    def ok(self):
        return self.status == "success"

    def __repr__(self):
        return f"NodeResult(path={self.path!r}, status={self.status!r}, error={self.error!r})"


class RunResult:
    """Outcome of a top-level ``App.run`` or ``Router.dispatch``."""

    def __init__(self, root):
        self.root = root

    @property
    def ok(self):
        return self.root.ok

    @property
    def exit_code(self):
        return 0 if self.ok else 1

    def __repr__(self):
        return f"RunResult(ok={self.ok}, exit_code={self.exit_code})"
