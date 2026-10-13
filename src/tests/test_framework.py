import asyncio
import io
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from pyouter.app import App
from pyouter.context import Context
from pyouter.router import Router


def legacy(config, options):
    print(config["marker"])
    print("debug-on" if options.debug else "debug-off")
    return "legacy"


async def contextual(ctx):
    ctx.log(ctx.config["marker"])
    return ctx.options.debug


def ok_leaf(config, options):
    print("ok-leaf")
    return "ok"


def boom(config, options):
    raise RuntimeError("boom")


class SubRouter(Router):
    pass


def options(**extra):
    values = dict(
        debug=True,
        view=False,
        tree=False,
        tasks=False,
        actions=None,
        web=False,
    )
    values.update(extra)
    return SimpleNamespace(**values)


class Box:
    async def run(self, ctx):
        return ctx.config["marker"]


class KernelTest(unittest.TestCase):
    def test_context_action_records_return_value(self):
        app = App(config={"marker": "cfg"})
        app.include(Router(hello=contextual, old=legacy))
        app.options = options(actions="hello")
        stdout = io.StringIO()
        with _stdio(stdout):
            returned = app.run()
        self.assertIs(returned, app)
        self.assertTrue(app.result.ok)
        self.assertEqual(app.result.exit_code, 0)
        self.assertTrue(app.result.root.value)
        self.assertIn("cfg", stdout.getvalue())

    def test_object_run_can_take_context(self):
        app = App(config={"marker": "cfg"})
        app.include(Router(box=Box()))
        app.options = options(actions="box")
        with _stdio(io.StringIO()):
            app.run()
        self.assertEqual(app.result.root.value, "cfg")

    def test_legacy_action_still_receives_config_and_options(self):
        app = App(config={"marker": "cfg"})
        app.use(router=Router(old=legacy))
        app.options = options(actions="old")
        stdout = io.StringIO()
        with _stdio(stdout):
            app.run()
        self.assertEqual(app.result.root.value, "legacy")
        self.assertIn("debug-on", stdout.getvalue())

    def test_child_failure_sets_exit_code(self):
        app = App(config={})
        app.use(router=Router(group=Router(ok=ok_leaf, bad=boom)))
        app.options = options(actions="group")
        stderr = io.StringIO()
        with _stdio(io.StringIO(), stderr):
            with self.assertRaises(SystemExit) as caught:
                app.run()
        self.assertEqual(caught.exception.code, 1)
        self.assertFalse(app.result.ok)
        self.assertIn("RuntimeError: boom", stderr.getvalue())
        bad = next(child for child in app.result.root.children if child.path == "group.bad")
        self.assertEqual(bad.status, "error")
        ok = next(child for child in app.result.root.children if child.path == "group.ok")
        self.assertEqual(ok.status, "success")

    def test_view_traces_routers_and_actions(self):
        app = App(config={"marker": "cfg"})
        app.use(router=Router(job=Router(sync=legacy)))
        app.options = options(actions="job.sync", view=True)
        stdout = io.StringIO()
        with _stdio(stdout):
            app.run()
        text = stdout.getvalue()
        self.assertIn("[pyouter] ->router: job", text)
        self.assertIn("[pyouter] ->action: job.sync", text)

    def test_sequence_waits_for_the_previous_child(self):
        order = []

        def first(config, options):
            time.sleep(0.05)
            order.append("first")

        def second(config, options):
            order.append("second")

        router = Router(policy="sequence", first=first, second=second)
        ctx = Context({}, options())
        result = asyncio.run(router.invoke("", ctx))
        self.assertTrue(result.ok)
        self.assertEqual(order, ["first", "second"])

    def test_include_merges_and_rejects_duplicates(self):
        app = App(config={})
        app.include(Router(a=legacy))
        app.include(Router(b=contextual), prefix="tools")
        self.assertIn("a", app.router.route)
        self.assertIsInstance(app.router.route["tools"], Router)
        self.assertIn("b", app.router.route["tools"].route)
        with self.assertRaises(ValueError):
            app.include(Router(a=legacy))

    def test_use_replaces_the_router(self):
        app = App(config={})
        app.use(router=Router(a=legacy))
        app.use(router=Router(b=legacy))
        self.assertNotIn("a", app.router.route)
        self.assertIn("b", app.router.route)

    def test_subclass_receives_context_and_stays_a_router(self):
        box = SubRouter(leaf=legacy)
        parent = Router(box=box)
        parent.context({"marker": "m"}, options(), None)
        self.assertEqual(box.config["marker"], "m")
        self.assertEqual(list(parent.tasks()), ["box.leaf"])

    def test_policy_string_is_not_a_route_name(self):
        router = Router(policy="sequence", leaf=legacy)
        self.assertEqual(router.policy, "sequence")
        self.assertNotIn("policy", router.route)

        def policy(config, options):
            return "route"

        named = Router(policy=policy)
        self.assertIs(named.route["policy"], policy)
        self.assertEqual(named.policy, "parallel")
        with self.assertRaises(ValueError):
            Router(policy="sideways")

    def test_executor_is_used_for_sync_actions(self):
        calls = []

        class Recording(ThreadPoolExecutor):
            def submit(self, fn, *args, **kwargs):
                calls.append(fn)
                return super().submit(fn, *args, **kwargs)

        pool = Recording(max_workers=1)
        try:
            app = App(config={"marker": "cfg"}, executor=pool)
            app.use(router=Router(old=legacy))
            app.options = options(actions="old")
            with _stdio(io.StringIO()):
                app.run()
        finally:
            pool.shutdown(wait=True)
        self.assertTrue(calls)

    def test_cancel_flag(self):
        ctx = Context({}, options())
        self.assertFalse(ctx.cancelled)
        ctx.cancel()
        self.assertTrue(ctx.cancelled)


class _stdio:
    def __init__(self, stdout, stderr=None):
        self.stdout = stdout
        self.stderr = stderr

    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self.stdout
        if self.stderr is not None:
            sys.stderr = self.stderr
        return self

    def __exit__(self, exc_type, exc, tb):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        return False


if __name__ == "__main__":
    unittest.main()
