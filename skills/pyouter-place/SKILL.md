---
name: pyouter-place
description: >-
  Use when a pyouter route starts a Docker container, a Compose project, or
  an SSH host, or runs a command or HTTP check inside one. Covers Container,
  Command, Service, Compose, SSH, and Remote.
---

# Containers, Compose, and SSH

Open this only after `skills/pyouter-help/SKILL.md` says a command must run in a container, a Compose file, or an SSH host. A script that runs on this machine stays a leaf. Source: `src/pyouter/docker.py`, `src/pyouter/ssh.py`. Rules: `skills/pyouter/SKILL.md`.

The parent node owns the resource and stays up. A child runs only when its own path is routed, and only after the parent is up. Do not start Docker or SSH yourself with `subprocess` when one of these nodes can own it.

`workers` and `balancer` belong to the layer. See `skills/pyouter-layer/SKILL.md`. `runtime` belongs to deploy. See `skills/pyouter-network/SKILL.md`.

## Container

```python
from pyouter.docker import Command, Container, Service
from pyouter.router import Router

box = Container(
    "python:3.12-slim",
    name="tools",
    workers=2,
    ports=("8080:80",),
    routes=Router(
        c=Router(d=Command("echo", "deep")),
        api=Service("http://127.0.0.1:8080", health=("GET", "/health")),
    ),
)
app.include(Router(a=Router(b=box)))
```

`python app.py a.b` starts the container and waits. `a.b.c.d` runs `echo deep` inside it. `a.b.api.health` sends `GET /health` to the published address.

`Command` takes separate argument strings, not one shell line. `Command("echo", "deep")` is `echo` with argument `deep`. An empty argument raises `a container command needs at least one argument`.

`Service` takes `http://host:port` and routes shaped `("GET", "/health")` or `"GET /health"`. The path must start with `/`.

`ports` entries look like `"8080:80"`. The image needs Python. pyouter mounts its source and starts it. Do not write a Dockerfile. `command=("nginx", "-g", "daemon off;")` replaces that inner runtime when the image itself is the service.

A child before the container is up raises `container <name> is not running; start it by running the container node`. Starting it again while it is up leaves the container in place. Stopping the container command removes the container this process started.

## Compose

```python
from pyouter.docker import Command, Compose, Service
from pyouter.router import Router

stack = Compose(
    "compose.yaml",
    project="demo",
    routes=Router(
        web=Router(ping=Command("echo", "web")),
        api=Service("http://127.0.0.1:8080", health=("GET", "/health")),
    ),
)
app.include(stack, prefix="stack")
```

The file must exist when `Compose` is constructed. A `.yml` or `.yaml` file needs PyYAML. A `.json` file does not. `routes` keys are service names. An unknown name raises `compose file has no service '<name>'`.

Mount with a prefix. `include(stack)` or `use(stack)` raises `include a compose project with a prefix`.

`stack` runs `docker compose up -d` and waits. `stack.web` reports that service. It does not start the project and does not run `ping`. `stack.web.ping` is `docker compose exec` in the `web` service. If the project is down, the error says to start it by running the compose node. Stopping `stack` runs `docker compose down` for the stack this process started.

## SSH

```python
from pyouter.docker import Service
from pyouter.router import Router
from pyouter.ssh import Remote, SSH

edge = SSH(
    "10.0.0.8",
    user="deploy",
    forwards=("8080:127.0.0.1:80",),
    routes=Router(
        c=Router(d=Remote("echo", "deep")),
        api=Service("http://127.0.0.1:8080", health=("GET", "/health")),
    ),
)
app.include(edge, prefix="edge")
```

`host` is a hostname or an address. Pass `user` separately. `deploy@10.0.0.8` as the host raises `pass the user separately`. `Remote` takes argument strings, not a shell line. `forwards` look like `"8080:127.0.0.1:80"`.

The connection does not ask for a password. It uses the keys and agent already available to `ssh`. `identity` is a key file path.

`include` without a prefix raises `include an ssh host with a prefix`. `Router(b=edge)` gives it the name `b` instead.

`edge` opens one connection and waits. `edge.c.d` runs on that host. A child before the connection is up raises `ssh <dest> is not connected; start it by running the ssh node`. Stopping the ssh command closes the connection this process opened.

A nested `Router` under any of these nodes is only another path segment.
