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
        ## execute:
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
app.run()  # python app.py hello
```

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

The left column is the route tree. The right panel shows the selected node's status, a map of the nearby routes, and the logs captured from that node's standard output and standard error. Click a node to inspect it. Use ▶, double-click, or 执行 to run it. Running a router runs its children, same as the command line.

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
python app.py api
python app.py api.health
python app.py api.users.user_id --user-id 7
python app.py --tasks
```

`python app.py api` starts the Flask application and leaves it listening on `127.0.0.1:5000`. That process stays up. A later `python app.py api.health` does not start the application again. It sends `GET /health` to the service that is already listening, then exits. The same is true for `api.users.user_id`, which is `GET /users/<int:user_id>`.

A path parameter is taken from an option of the same name, from `options.params`, or from config. Several methods on one path become `get`, `post`, and the other method names. The request returns `status`, `body`, `method`, and `path`. A response of 400 or higher fails the node. If nothing is listening, the route fails and tells you to start the service node. Running the service node again, while it is already listening, reports that and leaves the existing process alone.

`app.include(service, prefix="api", port=5000)` selects the address. `flatten(service, port=5000)` returns the same router when you want to mount it yourself. A FastAPI application listens on `127.0.0.1:8000` unless you pass a port, and starting it needs `uvicorn`. `GET /users/{user_id}` becomes `users.user_id`.

## What's new

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
