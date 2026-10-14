---
name: pyouter-refactor
description: >-
  Use when an existing Python project should become a pyouter tree:
  scattered scripts, a CLI, unclear modules, maybe a service, maybe
  containers. Drive the refactor to the end. Keep every current command,
  HTTP route, and container working, and leave a modular package whose
  paths match the tree.
---

# Refactor an existing project

`skills/pyouter-help/SKILL.md` sends an existing project here. This is the whole job, not a sample mount. Do not stop after the first script. Do not ask whether to continue. Ask only when a run would destroy data, needs a secret you do not have, or two public names would collide.

New projects do not use this skill. They use `skills/pyouter-init/SKILL.md`.

Rules: `skills/pyouter/SKILL.md`. Leaves and flags: `skills/pyouter-route/SKILL.md`. An HTTP app already in the tree: `skills/pyouter-web/SKILL.md`. A container, Compose file, or SSH host already in the tree: `skills/pyouter-place/SKILL.md`.

The installed `pyouter` command is shell completion. The project entry you add is `python app.py`.

## What done means

Every command, service, and container they can already run is still runnable. Each one also has a dotted path. The work lives in modules, grouped the way the path reads. `app.py` only wires the tree. `python app.py --tasks` lists every path. You have run the check for each row.

Do not add a peer, a super node, `--net`, `deploy_tree`, or a cluster. Do not put a local script into a container. Do not change a flag, an HTTP path, a port, a response body, or an exit code to make the tree tidier.

## 1. Lock the contract

Read the project before editing. Write this list in the conversation, from their real files:

```text
commands:
- python scripts/ingest.py --date 2024-01-01  →  data.ingest
services:
- python server.py  (Flask 127.0.0.1:5000, GET /health)  →  api
containers:
- docker compose -f compose.yaml up  →  stack
unchanged entry points:
- python scripts/ingest.py
- python server.py
```

A row is anything a person can already run: `python file.py`, `python -m package`, a Flask or FastAPI process, `docker`, `docker compose`, `ssh`. Flags, defaults, ports, and HTTP methods belong on the row. Names on the right are theirs: the script name, the module name, the service name. Do not invent a new vocabulary.

If the repo has tests, those tests are part of the contract. If a command is safe to run, record the stdout and exit code you just saw. Skip a command that deletes data, spends money, or needs a credential.

Show the list once, then start. Do not wait for approval.

## 2. Lay the modules out like the tree

One package, named from the repo or the package they already have. Do not create a second framework beside their code.

```text
app.py
pkg/
  data/ingest.py     # the work, no argparse
  api/app.py         # the Flask or FastAPI object they already had
  ops/report.py
```

The path `data.ingest` is `pkg/data/ingest.py`. A group of commands is a package. A command is a function. A service is the application object, included with a prefix, not a handwritten list of routes. A Compose file stays that file. A `Container` or `SSH` node exists only for an image or host they already run.

`app.py` imports those functions and mounts them. The function bodies do not move into `app.py`.

A local script stays a leaf under its group. It does not become a `Container`. `workers` stays at the default unless they already start more than one process. Open `skills/pyouter-layer/SKILL.md` only to keep that existing pool. Do not open `skills/pyouter-network/SKILL.md`.

## 3. Move one group, prove it, then the next

Take the contract from top to bottom. Finish the check before the next group.

**Command.** Put the body in a function with one positional parameter (`ctx`) or two (`config`, `options`). Keep the logic. argparse does not stay inside that function.

The old file becomes a shim that parses the same flags and calls that function, so `python scripts/ingest.py --date ...` still works:

```python
from pkg.data.ingest import run

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    options = parser.parse_args()
    run({}, options)

if __name__ == "__main__":
    main()
```

Mount the same function on the tree. Repeat the flags with `app.option`. The leaf does not read `sys.argv`.

```python
from pyouter.app import App
from pyouter.router import Router
from pkg.data.ingest import run as ingest_run

def ingest(ctx):
    return ingest_run(ctx.config, ctx.options)

app = App(config={})
app.option("--date", dest="date", required=True)
app.include(Router(data=Router(ingest=ingest)))
app.run()
```

Config they already load stays the config `App` receives. Do not add keys.

Check, then continue:

- Run the old command the same way as before, when it is safe.
- Route `data.ingest` with the same flag values. In a test, set `app.options` and call `app.run()`. From a shell, start `python app.py`, then run the path in a second terminal.
- Exit code and stdout match. Their test suite, if this group has tests, passes.

A leaf that shells out to the old script is not the end state. Import the function.

**Service.** Move nothing about the routes. Export the application object they already wrote. `app.include(service, prefix="api")`. Follow `skills/pyouter-web/SKILL.md`. The old `python server.py` still constructs that same object and starts it. `python app.py api` is the pyouter way to start it. `python app.py api.health` sends one request and must match a request to the old server. Do not copy handlers into pyouter leaves.

**Container, Compose, or SSH.** Mount only a stack or host the contract lists. Follow `skills/pyouter-place/SKILL.md`. Do not write a Dockerfile. Do not turn a Dockerfile they never asked to run into a `Container`. The node runs the same image, file, or host as before. If docker or ssh cannot run here, say so, and still check that the node is built from that file or host rather than from a new one.

If a check fails, fix that group before touching the next file.

## 4. Close the contract

When every row has a module and a path:

- `python app.py --tasks` prints each path.
- Each old entry point still runs, through its shim or its original server command.
- Each safe new path was run and matched.
- The project's tests passed, if it has tests.

Report one table: old invocation, dotted path, what you ran. Name any row you could not run and why. Do not delete a shim to make the tree look pure. A cron job or a doc that calls `python scripts/ingest.py` must keep working.
