import asyncio

from .errors import NotFound
from .executor import LeafExecutor

class Router(object):
    def __init__(self, **args):
        self.route = {}
        for key in args:
            self.route[key] = args[key]

    def context(self, config, options, executor):
        self.config = config
        self.options = options
        self.executor = executor
        for key in self.route:
            router = self.route[key]
            if type(router) == type(self):
                router.context(config, options, executor)

    async def dispatch(self, pre:str|None, command: str, depth: int):
        show_path = self.options.view or getattr(self.options, 'tree', False)
        path_prefix = '  '*depth if getattr(self.options, 'tree', False) else ''
        run_action = not getattr(self.options, 'tree', False)
        
        def full_path(pre, command):
            if pre is not None and pre!='':
                return f'{pre}.{command}'
            else:
                return command
        
        if "." in command:
            crt, nxt = command.split('.', 1)
            if crt not in self.route:
                raise NotFound(self.route, crt)
            
            router_path = full_path(pre, crt)
            if show_path:
                print(f'[pyouter] {path_prefix}->router: {router_path}')
            
            return await self.route[crt].dispatch(router_path, nxt, depth+1)
        else:
            if command not in self.route.keys():
                raise NotFound(self.route, command)

            leaf = self.route[command]
            if isinstance(leaf, Router):
                # 只在第一次遇到Router时输出路径信息
                router_path = full_path(pre, command)
                if show_path:
                    print(f'[pyouter] {path_prefix}->router2: {router_path}')
                
                tasks = []
                for crt in leaf.route:
                    task = asyncio.create_task(leaf.dispatch(router_path, crt, depth+1))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                action_path = full_path(pre, command)
                if show_path:
                    print(f'[pyouter] {path_prefix}->action: {action_path}')
                
                if run_action:
                    executor = LeafExecutor(self.config, self.options, self.executor, leaf)
                    await executor.run()

    def tasks(self, base=None):

        for key in self.route:
            current = f"{base}.{key}" if base else key
            item = self.route[key]
            if type(item) is Router:
                for task in item.tasks(current):
                    yield task
            else:
                yield current

    def print_tree(self, path=None, prefix="", is_last=True):
        """
        打印树状结构，类似tree命令的输出格式
        path: 要追踪的路径，如 "a.b.c"
        prefix: 当前行的前缀（用于缩进）
        is_last: 是否是当前层级的最后一个节点
        """
        if path:
            # 解析路径，先追踪到目标节点
            parts = path.split('.')
            current_router = self
            current_path = ""
            
            # 追踪路径
            for i, part in enumerate(parts):
                if part not in current_router.route:
                    print(f"路径 '{path}' 不存在")
                    return
                
                current_path = f"{current_path}.{part}" if current_path else part
                current_router = current_router.route[part]
                
                # 如果不是Router，说明到达叶子节点
                if not isinstance(current_router, Router):
                    if i < len(parts) - 1:
                        print(f"路径 '{path}' 在 '{current_path}' 处终止（不是Router节点）")
                        return
                    break
            
            # 打印路径追踪
            print(f"路径追踪: {path}")
            print("└── " + path)
            
            # 打印目标节点下的完整树
            if isinstance(current_router, Router):
                print(f"\n{current_path} 下的完整树:")
                current_router._print_subtree("", True)
            else:
                print(f"叶子节点: {current_path}")
        else:
            # 打印完整树
            self._print_subtree("", True)
    
    def _print_subtree(self, prefix="", is_last=True):
        """
        打印子树结构
        """
        items = list(self.route.items())
        for i, (key, value) in enumerate(items):
            is_last_item = i == len(items) - 1
            connector = "└── " if is_last_item else "├── "
            
            if isinstance(value, Router):
                print(f"{prefix}{connector}{key}/")
                # 递归打印子树
                next_prefix = prefix + ("    " if is_last_item else "│   ")
                value._print_subtree(next_prefix, is_last_item)
            else:
                # 叶子节点
                func_name = value.__name__ if hasattr(value, '__name__') else type(value).__name__
                print(f"{prefix}{connector}{key} ({func_name})")
