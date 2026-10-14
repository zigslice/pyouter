---
name: pyouter-layer
description: >-
  Use when choosing balancer or workers for a pyouter container, SSH host,
  cluster, or web service, or when deciding which pool runs a path. Covers
  the four layer kinds and the difference between landing on a layer node
  and crossing it.
---

# Layers

Open this only after a container, SSH host, or web service from `skills/pyouter-help/SKILL.md` needs more than one worker. Do not set `workers` on the first leaf. Source: `src/pyouter/layer.py`, `src/pyouter/balance.py`. Rules: `skills/pyouter/SKILL.md`.

Four nodes start their own pool. Crossing one is a new layer.

| node | kind | parent pool | this pool |
| --- | --- | --- | --- |
| `Container` | `docker` | one worker owns the container | balances every call under it |
| `SSH` | `ssh` | one worker owns the connection | balances every call on that host |
| `Cluster` | `cluster` | one worker places the one pod | balances every call inside that pod |
| flattened web service | `server` | one worker owns the listener | balances every request |

The process started by `python app.py` is the outermost pool. It is not a layer.

`cli > docker > ssh > docker > server` is four layers. A call that lands on the layer node stays on one worker of the parent. A call that goes past that node is balanced inside the layer.

```python
from pyouter.layer import layers_of, plan

layers_of(app.router)          # outer path first
plan(app.router, "cli.box")    # boundary=True, parent pool runs it
plan(app.router, "cli.box.api.health")  # serving is the layer that contains it
```

A missing path raises `KeyError`.

## What to set

Set `balancer` and `workers` on the layer node: `Container`, `SSH`, `Cluster`, or `flatten(...)`. Do not set them on a plain `Router`, a `Command`, or a `Remote`.

`balancer` defaults to `"uvicorn"`. `workers` defaults to `1` and must be a positive integer. `workers` is a process count. On a cluster it is the pool inside the one pod, not a replica count.

```python
from pyouter.balance import register_provider

def start(workers, port):
    ...  # return a process whose /health answers on port
    return proc

register_provider("mine", start)
Container("python:3.12-slim", balancer="mine", workers=2, routes=routes)
```

`register_provider(name, start)` registers `start(workers, port) -> process`. An unknown name raises `unknown balancer '<name>'`.

`runtime` is not a pool setting. It is where `deploy_tree` installs that layer. See `skills/pyouter-network/SKILL.md`.
