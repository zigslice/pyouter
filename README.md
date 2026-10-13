# Pyouter

Pyouter is a tasks router by  hierarchy and layered tasks, which may come from command line or http restful api

Deepwki: https://deepwiki.com/fanfeilong/pyouter

![pyouter](pyouter.gif)

## INSTALL

install pyouter

```shell
pip install pyouter
```

* advanced: [install for shell completion support](./advanced.md)

## examples

* [src/tests/test.py](src/tests/test.py)
  * depends: [src/tests/config.json](src/tests/config.json)

minimal example code for pyouoter:

```python
from typing import Any
from pyouter.app import App
from pyouter.router import Router

import json
import asyncio
import time


async def hello(config, options):
    print("hello function")
    
def hello_sync(config, options):
    print("hello sync")

class Hello:
    def __init__(self, value) -> None:
        self.value = value
    
    # Router class SHOULD provider method: `run(self, config, options)`
    async def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        await self.inner()
    
    async def inner(self):
        print(f"run Hello, {self.value}")
        await asyncio.sleep(2)
        print(f"hello class object, self.options.debug:{self.options.debug}, sleep 2s")
        if self.options.debug:
            print(f'debug, {self.value}')
            
class Hello_Sync:
    def __init__(self, value) -> None:
        self.value = value
    
    # Router class SHOULD provider method: `run(self, config, options)`
    def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        self.inner()
    
    def inner(self):
        print(f"run Hello_Sync, {self.value}")
        time.sleep(self.value)
        print(f"hello class object, self.options.debug:{self.options.debug}, sleep {self.value}s")
        if self.options.debug:
            print(f'debug, {self.value}')

if __name__=="__main__":
    '''
    Usage:
        ## start pyouter, then route into that process:
        * python test.py
        * python test.py test.hello.func
        * python test.py test.hello.obj
        * python test.py test
        
        ## dump router path only:
        * python test.py test.hello -i
        * python test.py test.hello --insepect
        
        ## dump router path and execute:
        * python test.py test.hello -v
        * python test.py test.hello --view

        ## browse and run in a local web ui:
        * python test.py --web
        * python test.py test.hello --web --no-browser
    '''
    
    app = App(
        config='config.json',
    )
    
    app.option(
        '-d', '--debug',
        dest='debug',
        action="store_true",
        help='debug'
    )
    
    app.use(
        router=Router(
            test=Router(
                hello=Router(
                    func=hello,
                    obj=Hello("world"),
                    obj2=Hello_Sync(10)
                ),
                hello2=hello,
                hello3=Router(
                    func=hello_sync,
                    obj=Hello("world"),
                    obj2=Hello_Sync(20),
                )
            )
        )
    )
    
    app.run()
    
    
```

## framework

An application is a router tree plus one context per run. `use()` replaces the tree. `include()` mounts another tree, optionally under a prefix. A leaf is still a function or an object with `run`. A single parameter receives a `Context`; two parameters keep the `(config, options)` form. An object's `run` method follows the same rule.

```python
from pyouter.app import App
from pyouter.router import Router

async def hello(ctx):
    ctx.log(ctx.config["name"])
    return ctx.options.debug

app = App(config={"name": "pyouter"})
app.include(Router(hello=hello))
app.run()
```

```shell
python app.py
python app.py hello
```

`python app.py` starts one process and leaves it running. Every later command routes a node into that process, prints the result, and exits. A function, a router, a web service, and a web endpoint are the same kind of step: the process you started is what executes the node. The command delivers the path.

`python app.py hello` runs `hello` there. The object you mounted keeps its state across commands, because both commands are executed by the same process. A second `python app.py` prints `pyouter already running`. A command issued before that process exists fails and tells you to start it. `--tasks` and `--tree` only read the route tree, so they run in the command itself.

Calling `run()` after you have set `options` executes in the current process. Tests and embedded callers use that path.

After a run, `app.result.exit_code` is 1 when a node fails, and `run()` raises `SystemExit`. A context action's return value is `app.result.root.value` when that action is the node that was executed.

Router nodes run their children in parallel. `policy="sequence"` runs them in order. Child failures are collected into `app.result` and the process exits with code 1. `ctx.cancelled` is set when a local web run is stopped.

## local web

https://cursor.com/artifacts/v/art-1cdde7f3-5756-49a3-97ac-2d54dc193da9

Open the current router in a browser. The server binds to `127.0.0.1:8765` and uses only the Python standard library.

```shell
python test.py --web
python test.py --web --port 9000
python test.py test.hello --web --no-browser
```

`--web` starts the same pyouter process and opens the browser on it. A later `python test.py test.hello.func` routes into that process. The left column is the route tree. The right panel shows the selected node's status, a map of the nearby routes, and the logs captured from that node's standard output and standard error. Click a node to inspect it. Use ▶, double-click, or 执行 to run it. Running a router runs its children, same as the command line.

`app.web()` starts the same page from Python. `--host` defaults to localhost; binding another interface exposes task execution on that interface.

## web services

A route is a command (`cli`), a router (`router`), or a web endpoint (`web`). `node_kind` reports which. A Flask or FastAPI application used to sit in the tree as one opaque node, so the routes declared inside it were invisible. Mounting the application flattens each HTTP route into a pyouter node. The command line, `--tasks`, and the local web ui then see those routes.

Flask and FastAPI are not required to install pyouter. They are imported only by the application you mount.

```python
from flask import Flask
from pyouter.app import App

service = Flask(__name__)

@service.get("/health")
def health():
    """service is up"""
    return {"ok": True}

@service.get("/users/<int:user_id>")
def user(user_id):
    return {"user_id": user_id}

app = App(config={})
app.option("--user-id", dest="user_id")
app.include(service, prefix="api")
app.run()
```

```shell
python app.py
python app.py api
python app.py api.health
python app.py api.users.user_id --user-id 7
python app.py --tasks
```

`python app.py` is the process that stays up. `python app.py api` routes to the service node inside it and waits there while Flask listens on `127.0.0.1:5000`. `python app.py api.health` routes to that endpoint: one `GET /health` against the service already listening in the same process, then the command exits. `api.users.user_id` is `GET /users/<int:user_id>`, routed the same way. `python app.py hello`, for an ordinary function mounted beside the service, is also a route into this process.

A path parameter is taken from an option of the same name, from `options.params`, or from config. Several methods on one path become `get`, `post`, and the other method names. The request returns `status`, `body`, `method`, and `path`. A response of 400 or higher fails the node. If the service node is not running, the route fails and tells you to start it. Running the service node again, while it is already listening, reports that and leaves the service in place. Stopping the `api` command stops the service. The pyouter process keeps running.

`app.include(service, prefix="api", port=5000)` selects the address. `flatten(service, port=5000)` returns the same router when you want to mount it yourself. A FastAPI application listens on `127.0.0.1:8000` unless you pass a port, and starting it needs `uvicorn`. `GET /users/{user_id}` becomes `users.user_id`.

## containers

A container is a node too. Commands and HTTP services inside it are child nodes, so a path such as `a.b.c.d` reaches through the container `b` into `c` and then `d`. Docker is not required to install pyouter. The `docker` executable is used only when a container node runs.

```python
from pyouter.app import App
from pyouter.docker import Command, Container, Service
from pyouter.router import Router

box = Container(
    "alpine:3",
    name="tools",
    ports=("8080:80",),
    routes=Router(
        c=Router(
            d=Command("echo", "deep"),
        ),
        api=Service(
            "http://127.0.0.1:8080",
            health=("GET", "/health"),
        ),
    ),
)

app = App(config={})
app.include(Router(a=Router(b=box)))
app.run()
```

```shell
python app.py
python app.py a.b
python app.py a.b.c.d
python app.py a.b.api.health
```

`python app.py a.b` starts the container and waits. `a.b.c.d` is `docker exec tools echo deep` in that container, then the command exits. `a.b.api.health` sends `GET /health` to the published address. Both fail, and say to start the container, when `a.b` is not running. Running `a.b` again while it is running reports that and leaves the container in place. Stopping the `a.b` command removes the container it started. The pyouter process keeps running.

`command=("nginx", "-g", "daemon off;")` replaces the default `sleep infinity` when the image itself is the service. A nested router such as `c` is only another path segment.

## What's new

### 0.5.0

* a container is a node; commands and published HTTP routes under it are child nodes

### 0.4.0

* `python app.py` starts the process that executes every node
* a later command routes into that process, for a function, a router, or a web route

### 0.3.1

* a flattened web service stays listening; route nodes send requests to it

### 0.3.0

* a route is `cli`, `router`, or `web`
* Flask and FastAPI applications flatten into pyouter nodes

### 0.2.0

* one dispatcher shared by the command line and the local web ui
* `Context` and `RunResult` for each run; context actions take `ctx`
* `include()` mounts routers; `policy="sequence"` runs children in order
* a failed child sets exit code 1

### 0.1.2

* add a local web ui (`--web`) to browse, visualize, and run routers

### 0.1.0

* fix executor bug

### 0.0.9

* improve -v, --view, -i, --insepect option for path debug

### 0.0.8

* add app.option support
* improve App(config=), support config patth
* add aysnc support
* will execute all routers pallarent by using async ThreadPoolExecutor

### 0.0.7

* add pyouter self completion of bash and fish

### 0.0.6

* fixed bug in fish completion install

### 0.0.5

* pass config if need

### 0.04

* custom parser

### 0.0.3

* support pyouter completion
* pyouter as entry points of package

### 0.0.2

* rename plugin to pyouter

### 0.0.1

* project init
* add pypi settings
* add installer
