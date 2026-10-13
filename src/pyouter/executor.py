import asyncio
import contextvars
import inspect

from functools import partial


def _positional(fn):
    signature = inspect.signature(fn)
    found = []
    for param in signature.parameters.values():
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            found.append(param)
    return found


def accepts_context(fn):
    """A context action takes one parameter. Legacy actions take config and options."""
    try:
        params = _positional(fn)
    except (TypeError, ValueError):
        return False
    return len(params) == 1


def _is_async(leaf):
    if inspect.isfunction(leaf) or inspect.ismethod(leaf):
        return inspect.iscoroutinefunction(leaf)
    return inspect.iscoroutinefunction(leaf.run)


class LeafExecutor:
    def __init__(self, config, options, executor, leaf):
        self.config = config
        self.options = options
        self.executor = executor
        self.leaf = leaf

    async def run(self, ctx=None):
        config = self.config if ctx is None else ctx.config
        options = self.options if ctx is None else ctx.options
        executor = self.executor if ctx is None else ctx.executor
        leaf = self.leaf

        target = leaf if inspect.isfunction(leaf) or inspect.ismethod(leaf) else leaf.run
        contextual = accepts_context(target)

        async def run_async():
            if contextual:
                return await target(ctx)
            return await target(config, options)

        def run_sync():
            if contextual:
                return target(ctx)
            return target(config, options)

        if _is_async(leaf):
            return await run_async()

        loop = asyncio.get_running_loop()
        # Keep the caller's contextvars in the worker thread so a web run
        # can attribute prints from synchronous actions to the right node.
        copied = contextvars.copy_context()
        return await loop.run_in_executor(executor, partial(copied.run, run_sync))
