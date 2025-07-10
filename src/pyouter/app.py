
from typing import Any
import asyncio

from pyouter.default import create_parser
from pyouter.errors import NotInit
from pyouter.router import Router

class App(object):
    def __init__(self, config=None, parser=None):
        opt_parser = parser if parser is not None else create_parser("tasks router runner")
        
        self.opt_parser = opt_parser
        self.options = None
        self.executor = None
        
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
    
    def use(self, router: Router):
        self.router = router
        return self
    
    def option(self, *args: Any, **kwds: Any):
        self.opt_parser.add_argument(*args, **kwds)
        return self

    def run(self):
        if self.router is None:
            raise NotInit("self.router in App")
        
        if self.config is None:
            raise NotInit("self.config in App")
        
        if self.options is None:
            self.options = self.opt_parser.parse_args()
            
        self.router.context(self.config, self.options, self.executor)

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
            asyncio.get_event_loop().run_until_complete(self.router.dispatch('', self.options.actions, 0))
        
        return self
