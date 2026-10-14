---
name: pyouter-route
description: >-
  Use when adding or changing a pyouter route: App, Router, include, use,
  a function or object leaf, app.option, policy, python app.py, --tasks, or
  --tree. Covers the one-argument context form, the (config, options) form,
  and how a command reaches the already running process.
---

# Routes

Read `skills/pyouter/SKILL.md` first. Source: `src/pyouter/app.py`, `src/pyouter/router.py`, `src/pyouter/executor.py`, `src/pyouter/runtime.py`.

## A leaf

One positional parameter receives a `Context`. Two positional parameters receive `(config, options)`.

```python
async def hello(ctx):
    ctx.log(ctx.config["name"])
    return ctx.options.debug

def hello_sync(config, options):
    print(options.debug)
```

`def hello(ctx, extra=None)` has two positional parameters, so pyouter calls it as `(config, options)`. Give a context action exactly one positional parameter.

An object is a leaf when it has `run`. The same count applies to `run(self, ctx)` or `run(self, config, options)`. Sync and async both work.

`ctx.log` writes stdout, or stderr when the stream is `"stderr"`. `ctx.cancel()` sets `ctx.cancelled`.

## The tree

```python
from pyouter.app import App
from pyouter.router import Router

app = App(config={"name": "pyouter"})  # or config="config.json"
app.option("-d", "--debug", dest="debug", action="store_true")
app.include(Router(hello=hello))
app.run()
```

`use(router)` replaces the tree. `include(router, prefix=None)` mounts. The first `include` sets the router. A later `include` merges. A name that is already present raises `route '<name>' already registered`.

`Router(..., policy="sequence")` runs children in order. The default `policy="parallel"` runs them together. Child failures are collected and the run exits 1. They do not cancel the other children.

`app.option` is `argparse.add_argument`. The dotted path is the optional positional `actions`.

A Compose project or an SSH host must be mounted with a prefix. `use` on either one raises `include a compose project with a prefix` or `include an ssh host with a prefix`. Nesting `Router(edge=host)` and including that router is the other way to give the host a name.

## Commands

```shell
python app.py
python app.py hello
python app.py --tasks
python app.py --tree
python app.py hello --tree
python app.py hello --view
python app.py --worker
```

`--tasks` lists every path. `--tree` prints the tree. A path limits `--tree` to that subtree. `--view` prints each hop while the node runs. Those three do not need a super node. `--worker` joins the pools of the process that is already running.

There is no `-i` or `--insepect` flag.

Routing to an ordinary router runs its children. Routing to a container, SSH host, Compose project, or web service starts that resource and waits. It does not also run the children. Route the child path separately.

## In-process

Set `options` before `run()`. Include every flag the leaf reads, plus the built-in flags.

```python
import argparse

app.options = argparse.Namespace(
    actions="hello",
    debug=False,
    view=False,
    tree=False,
    tasks=False,
    web=False,
    worker=False,
    host="127.0.0.1",
    port=8765,
    no_browser=True,
    script=None,
)
app.run()
value = app.result.root.value
```

A failed node raises `SystemExit`. `app.result.exit_code` is 1. The executed leaf's return value is `app.result.root.value`.

An object keeps its state across later commands because those commands stay on the worker that first ran it. Do not rebuild the object on each command to "reset" that. Construct it once, when the tree is built.
