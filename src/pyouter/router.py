import asyncio
import traceback

from .context import Context, NodeResult
from .errors import NotFound
from .executor import LeafExecutor


_POLICIES = ("parallel", "sequence")


def walk(node, path=""):
    """Yield ``(path, node)`` for a router and every node under it."""
    yield path, node
    if not isinstance(node, Router):
        return
    for key, child in node.route.items():
        child_path = f"{path}.{key}" if path else key
        yield from walk(child, child_path)


def error_text(result):
    if result.exc_type:
        return f"{result.exc_type}: {result.error}"
    return result.error or "error"


def summarize_errors(children):
    failed = [child for child in children if child.status == "error"]
    parts = [error_text(child) for child in failed[:6]]
    extra = len(failed) - len(parts)
    if extra > 0:
        parts.append(f"另外 {extra} 个错误")
    return "；".join(parts)


def _qualify(pre, path):
    if pre:
        return f"{pre}.{path}" if path else pre
    return path


class Router(object):
    def __init__(self, **routes):
        policy = "parallel"
        chosen = routes.get("policy")
        if isinstance(chosen, str):
            policy = routes.pop("policy")
            if policy not in _POLICIES:
                raise ValueError(f"policy must be one of {', '.join(_POLICIES)}")
        self.policy = policy
        self.kind = "router"
        self.origin = "cli"
        self.framework = None
        self.serves = False
        self.address = None
        self.app = None
        self.route = {}
        for key, value in routes.items():
            self.route[key] = _adopt(value)

    def include(self, router, prefix=None, host=None, port=None):
        """Mount another router's routes on this one.

        Without ``prefix``, the child routes are copied onto this router and a
        name that is already present is an error. The included router's own
        policy is not copied. With ``prefix``, that router is placed at the
        name; if the name is already a router, the routes are merged into it.
        A Flask or FastAPI application is flattened into routes first.
        ``host`` and ``port`` are the address of that service.
        """
        router = _as_router(router, host=host, port=port)
        if getattr(router, "origin", None) == "compose" and not prefix:
            raise ValueError("include a compose project with a prefix")
        if getattr(router, "origin", None) == "ssh" and not prefix:
            raise ValueError("include an ssh host with a prefix")
        if getattr(router, "serves", False) and not prefix:
            if self.route:
                raise ValueError("include a web service with a prefix")
            self.route = dict(router.route)
            self.serves = True
            self.origin = "web"
            self.framework = router.framework
            self.address = router.address
            self.app = router.app
            return self
        if prefix:
            current = self.route.get(prefix)
            if current is None:
                self.route[prefix] = router
            elif isinstance(current, Router):
                current.include(router)
            else:
                raise ValueError(f"route '{prefix}' is not a router")
            return self
        for key, value in router.route.items():
            if key in self.route:
                raise ValueError(f"route '{key}' already registered")
            self.route[key] = value
        return self

    def context(self, config, options, executor):
        self.config = config
        self.options = options
        self.executor = executor
        for router in self.route.values():
            if isinstance(router, Router):
                router.context(config, options, executor)

    def resolve(self, command):
        """Return ``(node, path, hops)`` for a dotted command.

        ``hops`` lists the routers traversed before the final node, as
        ``(path, depth, node)`` relative to this router.
        """
        if command is None:
            command = ""
        if command == "":
            raise NotFound(self.route, "")

        node = self
        path = ""
        hops = []
        parts = command.split(".")
        for index, part in enumerate(parts):
            route = node.route if isinstance(node, Router) else {}
            if part == "" or not isinstance(node, Router) or part not in route:
                raise NotFound(route, part if part else command)
            path = f"{path}.{part}" if path else part
            node = route[part]
            if index < len(parts) - 1:
                if not isinstance(node, Router):
                    raise NotFound({}, parts[index + 1])
                hops.append((path, index, node))
        return node, path, hops

    async def invoke(self, path, ctx):
        """Execute this router as the node at ``path``."""
        return await execute(self, path, 0, ctx)

    async def dispatch(self, pre, command, depth=0, ctx=None):
        if ctx is None:
            options = getattr(self, "options", None)
            config = getattr(self, "config", None)
            executor = getattr(self, "executor", None)
            ctx = Context(config, options, executor)

        if (command is None or command == "") and getattr(self, "serves", False):
            from .segment import bind_path, reset_path
            token = bind_path(_qualify(pre, ""))
            try:
                return await execute(self, _qualify(pre, ""), depth, ctx)
            finally:
                reset_path(token)

        node, rel, hops = self.resolve(command)
        from .segment import bind_path, reset_path
        path_token = bind_path(_qualify(pre, rel))
        try:
            return await self._dispatch_resolved(pre, node, rel, hops, depth, ctx)
        finally:
            reset_path(path_token)

    async def _dispatch_resolved(self, pre, node, rel, hops, depth, ctx):
        for hop_path, hop_depth, hop_node in hops:
            await ctx.hooks.emit("before", {
                "path": _qualify(pre, hop_path),
                "node": hop_node,
                "role": "hop",
                "depth": depth + hop_depth,
                "result": None,
                "traceback": None,
            })
        return await execute(node, _qualify(pre, rel), depth + len(hops), ctx)

    def tasks(self, base=None):
        root = base or ""
        for path, node in walk(self, root):
            if isinstance(node, Router):
                continue
            yield path

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
            elif getattr(value, "kind", None) == "web":
                print(f"{prefix}{connector}{key} ({value.method} {value.rule})")
            elif getattr(value, "kind", None) in {"docker", "ssh"}:
                print(f"{prefix}{connector}{key} ({' '.join(value.argv)})")
            else:
                # 叶子节点
                func_name = value.__name__ if hasattr(value, '__name__') else type(value).__name__
                print(f"{prefix}{connector}{key} ({func_name})")


def node_kind(node):
    """Classify a route node.

    ``cli`` is a command function or an object with ``run``. ``router`` is a
    router written in Python.     ``web`` is a Flask or FastAPI endpoint, or a
    router produced by flattening one of those applications.     ``docker`` is a
    container, a Compose service, or a command that runs inside one.
    ``compose`` is a Compose project. ``ssh`` is an SSH host or a command
    that runs on one. ``cluster`` is one pod started from a registry image.
    """
    if isinstance(node, Router):
        if getattr(node, "origin", None) == "compose":
            return "compose"
        if getattr(node, "origin", None) == "compose-service":
            return "docker"
        if getattr(node, "origin", None) == "docker":
            return "docker"
        if getattr(node, "origin", None) == "ssh":
            return "ssh"
        if getattr(node, "origin", None) == "cluster":
            return "cluster"
        if getattr(node, "origin", None) == "web":
            return "web"
        return "router"
    if getattr(node, "kind", None) == "web":
        return "web"
    if getattr(node, "kind", None) == "docker":
        return "docker"
    if getattr(node, "kind", None) == "ssh":
        return "ssh"
    return "cli"


def _adopt(value, host=None, port=None):
    from .flatten import adopt
    return adopt(value, host=host, port=port)


def _as_router(value, host=None, port=None):
    if isinstance(value, Router):
        if host is not None or port is not None:
            _adopt(value, host=host, port=port)
        return value
    adopted = _adopt(value, host=host, port=port)
    if isinstance(adopted, Router):
        return adopted
    raise TypeError(
        "expected a Router or a Flask/FastAPI application, "
        f"got {type(value).__name__}"
    )


def _should_run(ctx):
    options = ctx.options
    if options is None:
        return True
    return not getattr(options, "tree", False)


async def execute(node, path, depth, ctx):
    """Run ``node`` at ``path`` and return a ``NodeResult``.

    Router children run together unless that router's policy is ``sequence``.
    Child failures are recorded and do not stop the remaining children.
    A web service node starts the server and leaves it listening. A route
    group inside that service does not call its endpoints.     A container node
    starts that container and leaves it running. A Compose project starts
    the stack and leaves it running. An SSH host opens its connection and
    leaves it up. Cancellation still stops the node and is re-raised.
    """
    if isinstance(node, Router):
        if getattr(node, "origin", None) == "compose":
            return await _execute_compose(node, path, depth, ctx)
        if getattr(node, "origin", None) == "compose-service":
            return await _execute_compose_service(node, path, depth, ctx)
        if getattr(node, "origin", None) == "docker":
            return await _execute_container(node, path, depth, ctx)
        if getattr(node, "origin", None) == "ssh":
            return await _execute_ssh(node, path, depth, ctx)
        if getattr(node, "origin", None) == "cluster":
            return await _execute_cluster(node, path, depth, ctx)
        if getattr(node, "serves", False):
            return await _execute_service(node, path, depth, ctx)
        if getattr(node, "origin", None) == "web":
            return await _execute_web_group(node, path, depth, ctx)
        return await _execute_router(node, path, depth, ctx)
    return await _execute_leaf(node, path, depth, ctx)


async def _execute_service(node, path, depth, ctx):
    from .flatten import serve_service

    event = _event(node, path, depth, "serve")
    await ctx.hooks.emit("before", event)
    try:
        from .segment import bind_path, reset_path
        token = bind_path(path)
        try:
            value = await serve_service(node, ctx)
        finally:
            reset_path(token)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_container(node, path, depth, ctx):
    from .docker import start_container

    event = _event(node, path, depth, "container")
    await ctx.hooks.emit("before", event)
    try:
        from .segment import bind_path, reset_path
        token = bind_path(path)
        try:
            value = await start_container(node, ctx)
        finally:
            reset_path(token)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_cluster(node, path, depth, ctx):
    from .cluster import publish

    event = _event(node, path, depth, "cluster")
    await ctx.hooks.emit("before", event)
    try:
        value = await asyncio.to_thread(publish, node, path, None)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_ssh(node, path, depth, ctx):
    from .ssh import start_ssh

    event = _event(node, path, depth, "ssh")
    await ctx.hooks.emit("before", event)
    try:
        from .segment import bind_path, reset_path
        token = bind_path(path)
        try:
            value = await start_ssh(node, ctx)
        finally:
            reset_path(token)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_compose(node, path, depth, ctx):
    from .docker import start_compose

    event = _event(node, path, depth, "compose")
    await ctx.hooks.emit("before", event)
    try:
        from .segment import bind_path, reset_path
        token = bind_path(path)
        try:
            value = await start_compose(node, ctx)
        finally:
            reset_path(token)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_compose_service(node, path, depth, ctx):
    """One service in a Compose project. Running it does not call its commands."""
    from .docker import project_running

    event = _event(node, path, depth, "service")
    await ctx.hooks.emit("before", event)
    try:
        if not await asyncio.to_thread(project_running, node.project):
            raise RuntimeError(
                f"compose project {node.project.project_name} is not running; "
                "start it by running the compose node"
            )
        ports = " ".join(node.ports)
        text = f"compose service {node.service_name}"
        if ports:
            text = f"{text} {ports}"
        print(text)
        value = {"service": node.service_name, "ports": list(node.ports), "image": node.image}
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result
    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_web_group(node, path, depth, ctx):
    """A path prefix of a web service. Running it does not call the endpoints."""
    event = _event(node, path, depth, "group")
    await ctx.hooks.emit("before", event)
    url = node.address.base_url if getattr(node, "address", None) else ""
    print(f"web routes at {url}")
    result = NodeResult(path, "success", value={"url": url})
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_router(node, path, depth, ctx):
    event = _event(node, path, depth, "fanout")
    await ctx.hooks.emit("before", event)
    tasks = []
    try:
        children = await _execute_children(node, path, depth, ctx, tasks)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled", children=[])
        await ctx.hooks.emit("after", event)
        raise

    failed = [child for child in children if child.status == "error"]
    if failed:
        result = NodeResult(path, "error", error=summarize_errors(children), children=children)
        event["result"] = result
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result

    result = NodeResult(path, "success", children=children)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _execute_children(node, path, depth, ctx, tasks):
    items = list(node.route.items())
    child_depth = depth + 1

    async def one(key, child):
        child_path = f"{path}.{key}" if path else key
        return await execute(child, child_path, child_depth, ctx)

    if node.policy == "sequence":
        children = []
        for key, child in items:
            children.append(await one(key, child))
        return children

    tasks.extend(asyncio.create_task(one(key, child)) for key, child in items)
    try:
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        await _cancel_tasks(tasks)
        raise

    children = []
    for (key, _child), item in zip(items, gathered):
        child_path = f"{path}.{key}" if path else key
        if isinstance(item, NodeResult):
            children.append(item)
            continue
        if isinstance(item, asyncio.CancelledError):
            await _cancel_tasks(tasks)
            raise item
        if isinstance(item, BaseException):
            children.append(NodeResult(
                child_path,
                "error",
                error=str(item),
                exc_type=type(item).__name__,
            ))
            continue
        children.append(NodeResult(child_path, "success", value=item))
    return children


async def _execute_leaf(node, path, depth, ctx):
    event = _event(node, path, depth, "action")
    await ctx.hooks.emit("before", event)
    if not _should_run(ctx):
        result = NodeResult(path, "success")
        event["result"] = result
        await ctx.hooks.emit("after", event)
        return result

    config = getattr(ctx, "config", None)
    options = getattr(ctx, "options", None)
    executor = getattr(ctx, "executor", None)
    try:
        value = await LeafExecutor(config, options, executor, node).run(ctx)
    except asyncio.CancelledError:
        event["result"] = NodeResult(path, "cancelled")
        await ctx.hooks.emit("after", event)
        raise
    except Exception as exc:
        result = NodeResult(path, "error", error=str(exc), exc_type=type(exc).__name__)
        event["result"] = result
        event["traceback"] = traceback.format_exc().rstrip()
        await ctx.hooks.emit("on_error", event)
        await ctx.hooks.emit("after", event)
        return result

    result = NodeResult(path, "success", value=value)
    event["result"] = result
    await ctx.hooks.emit("after", event)
    return result


async def _cancel_tasks(tasks):
    pending = [task for task in tasks if not task.done()]
    for task in pending:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _event(node, path, depth, role):
    return {
        "path": path,
        "node": node,
        "role": role,
        "depth": depth,
        "result": None,
        "traceback": None,
    }
