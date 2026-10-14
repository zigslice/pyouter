---
name: pyouter-init
description: >-
  Use when creating the first pyouter app.py for a new project. Add one
  route and nothing else. An existing project of scripts, a CLI, a service,
  or containers is pyouter-refactor, not this skill.
---

# The first app

`skills/pyouter-help/SKILL.md` decides which project this is. An existing project is `skills/pyouter-refactor/SKILL.md`. Do not use this skill to mount one old script and stop. Read `skills/pyouter/SKILL.md` for the process rules. This skill only creates the first tree of a new project. It does not add a second command, a worker pool, or a deploy.

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

## After it runs

Hand back to `skills/pyouter-help/SKILL.md`. The next step is the person running `python app.py`, then the path, then `python app.py --tasks`. Do not add further commands in the same turn.
