---
name: pyouter-web
description: >-
  Use when mounting a Flask, FastAPI, or Starlette application on pyouter,
  calling an HTTP route node, or opening the local --web page or the node
  runtime map. Covers flatten, path parameters, and which page can run a node.
---

# Web services and pages

Open this only after `skills/pyouter-help/SKILL.md` says the person has an HTTP app or asked for `--web`. A first mount of an existing app is `skills/pyouter-init/SKILL.md`. Source: `src/pyouter/flatten.py`, `src/pyouter/web.py`, `src/pyouter/node.py`. Rules: `skills/pyouter/SKILL.md`.

Flask and FastAPI are not install dependencies of pyouter. They are imported only by the application you mount. Starting FastAPI needs `uvicorn`.

## Mount

```python
from flask import Flask
from pyouter.app import App

service = Flask(__name__)

@service.get("/health")
def health():
    return {"ok": True}

@service.get("/users/<int:user_id>")
def user(user_id):
    return {"user_id": user_id}

app = App(config={})
app.option("--user-id", dest="user_id")
app.include(service, prefix="api", port=5000)
```

`include` and `Router` flatten a Flask, FastAPI, or Starlette app. Do not wrap the app in your own object to list its routes.

`flatten(service, host="127.0.0.1", port=None, workers=1, balancer="uvicorn", runtime=None)` returns the same router when you want to set the layer yourself. The default port is 5000 for Flask and 8000 for FastAPI or Starlette.

A path prefix becomes a router. One method with no extra path segment becomes a leaf. Several methods on one path become children named `get`, `post`, and the other method names. The site root is the leaf `root`.

```shell
python app.py api
python app.py api.health
python app.py api.users.user_id --user-id 7
```

`api` starts Flask and waits on `127.0.0.1:5000`. If the root router itself serves, `python app.py` starts that service. `api.health` sends one HTTP request to the service that is already listening. It does not call the view function in-process. A path prefix such as `api.users` prints the address and does not call the endpoints under it.

A path parameter comes from an option of the same name, from `options.params`, or from config. A missing one raises `missing path parameter '<name>'`.

The leaf returns `status`, `body`, `method`, `path`, and `url`. A response of 400 or higher fails the node. If nothing is listening, the error is `web service is not running at <url>; start it by running the service node`. Running the service node again while it is listening reports `web service already running` and leaves it in place.

## Two pages

`--web` is the control process. It binds `127.0.0.1:8765` unless `--host` and `--port` say otherwise. `app.web()` starts the same page. This page can run a node. Binding a non-loopback host exposes task execution on that interface.

```shell
python app.py --web
python app.py --web --port 9000 --no-browser
```

`python -m pyouter.node` prints `web http://<ip>:<port>` and serves the map on that same port. No extra `--web` flag. That page only shows the runtime. Its run and stop calls answer 409. Run and stop stay on the control `--web` page.

On the runtime map, the outermost deployed layer is marked as where you are. With no slice deployed, the root is marked. Green means reachable. Red means unreachable. A container is blue, an SSH host is purple, a cluster is teal, and a web service is orange. The words on the page are Chinese.
