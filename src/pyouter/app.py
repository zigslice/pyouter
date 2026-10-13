
from typing import Any
import asyncio
import sys

from pyouter.context import Context, Hooks, RunResult
from pyouter.default import create_parser
from pyouter.errors import NotInit
from pyouter.router import Router, _as_router

class App(object):
    def __init__(self, config=None, parser=None, executor=None):
        opt_parser = parser if parser is not None else create_parser("tasks router runner")
        
        self.opt_parser = opt_parser
        self.options = None
        self.executor = executor
        self.result = None
        
        if config is None:
            self.config = {}
        elif type(config)==type(''):
            import json
            with open(config,'r') as f:
                self.config = json.load(f)
        elif type(config)==type({}):
            self.config = config
        else:
            raise NotInit("config type unknonw")
            
        self.router: Router

    def _require_router(self):
        if not hasattr(self, "router") or self.router is None:
            raise NotInit("self.router in App")
    
    def use(self, router: Router, host=None, port=None):
        """Replace the application's router.

        A Flask or FastAPI application is flattened into routes first.
        ``host`` and ``port`` are where that service listens.
        """
        self.router = _as_router(router, host=host, port=port)
        return self

    def include(self, router: Router, prefix=None, host=None, port=None):
        """Mount ``router`` on the application router.

        The first call sets the router. Later calls merge routes. ``prefix``
        mounts them under that name. A Flask or FastAPI application is
        flattened into routes before it is mounted. ``host`` and ``port``
        are where that service listens.
        """
        router = _as_router(router, host=host, port=port)
        if not hasattr(self, "router") or self.router is None:
            if prefix:
                self.router = Router()
                self.router.include(router, prefix=prefix)
            else:
                self.router = router
            return self
        self.router.include(router, prefix=prefix)
        return self
    
    def option(self, *args: Any, **kwds: Any):
        self.opt_parser.add_argument(*args, **kwds)
        return self

    def _context(self):
        return Context(self.config, self.options, self.executor, self._hooks(self.options))

    def _hooks(self, options):
        hooks = Hooks()
        hooks.before.append(_view_hook(options))
        hooks.on_error.append(_cli_error_hook)
        return hooks

    async def execute_options(self, options):
        """Execute ``options.actions`` and return the process exit code."""
        ctx = Context(self.config, options, self.executor, self._hooks(options))
        node_result = await self.router.dispatch("", options.actions, 0, ctx)
        self.result = RunResult(node_result)
        return 0 if node_result.ok else 1

    async def serve_root(self):
        """Start the root when the whole application is a web service."""
        if not getattr(self.router, "serves", False):
            return 0
        ctx = Context(self.config, self.options, self.executor, self._hooks(self.options))
        node_result = await self.router.dispatch("", "", 0, ctx)
        self.result = RunResult(node_result)
        return 0 if node_result.ok else 1

    def web(self, host="127.0.0.1", port=8765, open_browser=True, focus=None):
        """Start the local web ui for this app's router."""
        self._require_router()

        if self.config is None:
            raise NotInit("self.config in App")

        if self.options is None:
            self.options = self.opt_parser.parse_args()

        self.router.context(self.config, self.options, self.executor)

        from pyouter.web import serve
        serve(
            self,
            host=host,
            port=port,
            open_browser=open_browser,
            focus="" if focus is None else focus,
        )
        return self

    def run(self):
        self._require_router()
        
        if self.config is None:
            raise NotInit("self.config in App")
        
        cli = self.options is None
        if cli:
            self.options = self.opt_parser.parse_args()
            
        self.router.context(self.config, self.options, self.executor)

        # A command typed at the shell routes into the process started by
        # ``python app.py``. A caller that already set ``options`` is inside
        # that process and executes here.
        if cli:
            from .runtime import route_cli
            if route_cli(self):
                return self

        if getattr(self.options, 'web', False):
            self.web(
                host=getattr(self.options, "host", "127.0.0.1"),
                port=getattr(self.options, "port", 8765),
                open_browser=not getattr(self.options, "no_browser", False),
                focus=self.options.actions,
            )
            return self

        if getattr(self.options, 'tree', False):
            if self.options.actions:
                # 如果有actions参数，显示路径追踪和子树
                self.router.print_tree(self.options.actions)
            else:
                # 如果没有actions参数，显示完整树
                self.router.print_tree()
            return self

        if self.options.tasks:
            for task in self.router.tasks():
                print(task)
        else:
            try:
                code = asyncio.run(self.execute_options(self.options))
            except KeyboardInterrupt:
                print("\n[pyouter] stopped")
                return self
            if code:
                raise SystemExit(code)

        return self


def _view_hook(options):
    def hook(event):
        if options is None:
            return
        show = getattr(options, "view", False) or getattr(options, "tree", False)
        if not show:
            return
        role = event.get("role")
        if role == "hop":
            label = "router"
        elif role == "fanout":
            label = "router2"
        elif role == "serve":
            label = "service"
        elif role == "container":
            label = "container"
        elif role == "group":
            label = "web"
        elif role == "action":
            label = "action"
        else:
            return
        prefix = "  " * event.get("depth", 0) if getattr(options, "tree", False) else ""
        print(f"[pyouter] {prefix}->{label}: {event['path']}")
    return hook


def _cli_error_hook(event):
    if event.get("role") not in ("action", "serve", "container"):
        return
    traceback_text = event.get("traceback")
    if traceback_text:
        print(traceback_text, file=sys.stderr)
        return
    result = event.get("result")
    if result is not None and result.error:
        print(f"[pyouter] {event['path']}: {result.error}", file=sys.stderr)
