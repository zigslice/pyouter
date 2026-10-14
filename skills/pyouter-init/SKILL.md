---
name: pyouter-init
description: >-
  Use when creating the first pyouter app.py. For a new project, add one
  route and nothing else. For an existing project, mount the one command,
  service, or container that already runs, without rewriting it. Follow
  pyouter-help to decide which project this is.
---

# The first app

`skills/pyouter-help/SKILL.md` decides which section this is. Read `skills/pyouter/SKILL.md` for the process rules. This skill only creates the first tree. It does not add a second command, a worker pool, or a deploy.

The file is `app.py` in the directory they run from. Config is a dict inline, or a `config.json` next to `app.py` when they already have settings. `App(config="config.json")` opens that path from the current directory.

Do not edit `pyouter:runner` in this package. That command is shell completion.

## New project

One leaf that proves the process starts and a path routes into it.

```python
from pyouter.app import App
from pyouter.router import Router

def hello(ctx):
    ctx.log(ctx.config["name"])

app = App(config={"name": "pyouter"})
app.include(Router(hello=hello))
app.run()
```

Replace `hello` with the first command they named, still one leaf. Flags they named go on `app.option` before `include`. The leaf reads them from `ctx.options`. One positional parameter is the context. See `skills/pyouter-route/SKILL.md` when that leaf is no longer this small.

Do not add Flask, Docker, SSH, `workers`, `runtime`, or `--net`.

## Existing project

Their files stay. `app.py` only points at them. Mount the one row from the inventory in `pyouter-help`, not the whole list.

### A script or a function

Import the function their script already calls. Do not paste its body into `app.py`.

```python
from pyouter.app import App
from pyouter.router import Router
from scripts.ingest import run as ingest_run

def ingest(ctx):
    return ingest_run(ctx.config, ctx.options)

app = App(config={})
app.option("--date", dest="date", required=True)
app.include(Router(data=Router(ingest=ingest)))
app.run()
```

The dotted path is their words: `data.ingest` for `scripts/ingest.py`. Repeat the flags they already type. `app.option` is argparse. Do not leave their script parsing `sys.argv` a second time inside the leaf.

If the only callable is `main()` and it reads argv, do not rewrite that file in this step. The leaf runs the script once, with the same arguments:

```python
import subprocess
import sys

def ingest(ctx):
    completed = subprocess.run(
        [sys.executable, "scripts/ingest.py", "--date", ctx.options.date],
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"scripts/ingest.py exited {completed.returncode}")
```

Say which of the two you used. Prefer the import when a function can take `(config, options)` or no argv.

Group further scripts later, under names they already use. Do not invent a new package layout.

### A service they already start

Mount the application object. Do not copy its routes.

```python
from pyouter.app import App
from server import app as service

app = App(config={})
app.include(service, prefix="api")
app.run()
```

Then follow `skills/pyouter-web/SKILL.md`. `python app.py api` is what used to start the server. A route under it sends one request. It does not call the view in-process.

### A container or Compose file they already run

Only when they asked for that stack in the first mount. A Compose file is `Compose("compose.yaml", ...)` included with a prefix. An image they already run can be a `Container` with `command=` set to that image's process. Do not write a Dockerfile, and do not turn a loose Dockerfile into a `Container` unless they asked to run that image. Follow `skills/pyouter-place/SKILL.md`.

A script that runs on this machine is not a container.

## After it runs

Hand back to `skills/pyouter-help/SKILL.md`. The next step is the person running `python app.py`, then the path, then `python app.py --tasks`. Do not add the rest of the inventory in the same turn.
