---
name: pyouter
description: >-
  Use when an edit must follow pyouter's process model: a dotted route,
  python app.py, a leaf, a layer, deploy_tree, or python -m pyouter.node.
  For a new project or an existing pile of scripts, read pyouter-help first
  and create the tree with pyouter-init. This skill is the invariants.
---

# Pyouter

A command, an HTTP route, a container, an SSH host, and a cluster pod are nodes in one tree. A path is dotted: `a.b.c`. It is not a URL and not a shell command.

Human docs: `README.md` (English) and `README.zh-CN.md`. When a doc and the source disagree, follow the source under `src/pyouter/`.

## Which skill

A first session starts at `skills/pyouter-help/SKILL.md`. That skill says when to open the rest. `skills/pyouter-init/SKILL.md` creates the first `app.py` and then stops.

| You are about to | Read |
| --- | --- |
| decide how a person starts, or adopt scripts they already run | `skills/pyouter-help/SKILL.md` |
| create the first `app.py` | `skills/pyouter-init/SKILL.md` |
| add a function, object, `include`, `use`, or a CLI command | `skills/pyouter-route/SKILL.md` |
| mount Flask, FastAPI, or Starlette, or open a page | `skills/pyouter-web/SKILL.md` |
| add a container, Compose project, or SSH host | `skills/pyouter-place/SKILL.md` |
| set `balancer` or `workers`, or decide which pool runs a path | `skills/pyouter-layer/SKILL.md` |
| call `deploy_tree`, set `runtime`, start `pyouter.node`, join a super node, or place a pod | `skills/pyouter-network/SKILL.md` |

## Process model

`python app.py` starts the process that executes nodes and leaves it running. A later `python app.py a.b` only delivers the path into that process. It does not execute `a.b` in the new process.

If that process is not running, the command exits 1 and prints `pyouter is not running; start it with python app.py`. A second bare `python app.py` prints `pyouter already running`.

Tests and embedded callers set `app.options` before `app.run()`. That executes in the current process. Do not shell out to `python app.py <path>` from a unit test.

`App` needs a config (a dict or a JSON file path) and a router from `use()` or `include()` before `run()`.

## Do not

- Do not add `--net` to a local route, a Flask app, a container, an SSH host, or a `runtime` that is an `http://` URL. The secret is only for joining or serving a super node, and for `deploy_tree` to a peer id or a cluster.
- Do not invent a privileged control role. The control process is a peer. Membership is the shared secret.
- Do not write a Dockerfile for a `Container`. `deploy_tree` builds the cluster image itself.
- Do not treat a peer id as a credential. Anyone can generate one.
