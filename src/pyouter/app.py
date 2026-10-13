
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
        hooks = Hooks()
        hooks.before.append(_view_hook(self.options))
        hooks.on_error.append(_cli_error_hook)
        return Context(self.config, self.options, self.executor, hooks)

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
        
        if self.options is None:
            self.options = self.opt_parser.parse_args()
            
        self.router.context(self.config, self.options, self.executor)

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
                node_result = asyncio.run(
                    self.router.dispatch("", self.options.actions, 0, self._context())
                )
            except KeyboardInterrupt:
                print("\n[pyouter] stopped")
                return self
            self.result = RunResult(node_result)
            if not node_result.ok:
                raise SystemExit(self.result.exit_code)
        
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
    if event.get("role") not in ("action", "serve"):
        return
    traceback_text = event.get("traceback")
    if traceback_text:
        print(traceback_text, file=sys.stderr)
        return
    result = event.get("result")
    if result is not None and result.error:
        print(f"[pyouter] {event['path']}: {result.error}", file=sys.stderr)
