# Pyouter

[English](./README.md) · 中文

Pyouter 是一个按层次组织任务的路由器。一条命令、一个 HTTP 路由、一个容器、一台 SSH 主机、一个集群 Pod，都是同一棵树上的节点。一条路径沿着这棵树走下去。容器、SSH 主机、集群和 Web 服务各自启动自己的工作进程池，跨过其中一个，就是新的一层。

![pyouter](pyouter.gif)

节点 runtime 启动后会打印 `web http://<ip>:<port>`。用浏览器打开这个地址，就是上面这张地图。容器是蓝色，SSH 主机是紫色，集群是青色，Web 服务是橙色。部署在这个 runtime 上的最外层会标着「你在这里」。还没有部署时，这个标记在根节点上。绿色是可达，红色是不可达。

下面这些例子都在本机运行。它们不加入超级节点，也不需要 `--net`。共享密钥只在两种情况下使用：进程要加入超级节点，或者 `deploy_tree` 要把某一层发到一个 peer id。

## 安装

```shell
pip install pyouter
```

Shell 补全见 [advanced.md](./advanced.md)。

## 一条路由

叶子是一个函数。只有一个参数时，收到的是上下文。`include()` 挂上这棵树。

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

`python app.py` 启动一个进程并让它一直运行。`python app.py hello` 把 `hello` 路由进这个进程，打印结果，然后退出。

## 最初的例子

[src/tests/test.py](src/tests/test.py) 仍然可以运行，配置文件是 [src/tests/config.json](src/tests/config.json)。函数也可以接收 `(config, options)`，而不只是一个上下文。对象只要有 `run`，就可以作为叶子。这个脚本不使用 peer 网络。

```python
from typing import Any
from pyouter.app import App
from pyouter.router import Router

import asyncio
import time


async def hello(config, options):
    print("hello function")

def hello_sync(config, options):
    print("hello sync")

class Hello:
    def __init__(self, value) -> None:
        self.value = value

    async def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        await self.inner()

    async def inner(self):
        print(f"run Hello, {self.value}")
        await asyncio.sleep(2)
        print(f"hello class object, self.options.debug:{self.options.debug}, sleep 2s")
        if self.options.debug:
            print(f"debug, {self.value}")

class Hello_Sync:
    def __init__(self, value) -> None:
        self.value = value

    def run(self, config, options) -> Any:
        self.config = config
        self.options = options
        self.inner()

    def inner(self):
        print(f"run Hello_Sync, {self.value}")
        time.sleep(self.value)
        print(f"hello class object, self.options.debug:{self.options.debug}, sleep {self.value}s")
        if self.options.debug:
            print(f"debug, {self.value}")

if __name__ == "__main__":
    app = App(config="config.json")
    app.option("-d", "--debug", dest="debug", action="store_true", help="debug")
    app.use(router=Router(
        test=Router(
            hello=Router(
                func=hello,
                obj=Hello("world"),
                obj2=Hello_Sync(10),
            ),
            hello2=hello,
            hello3=Router(
                func=hello_sync,
                obj=Hello("world"),
                obj2=Hello_Sync(20),
            ),
        )
    ))
    app.run()
```

```shell
python test.py
python test.py test.hello.func
python test.py test.hello.obj --debug
python test.py --tasks
python test.py --tree
python test.py test.hello --tree
python test.py test.hello.func --view
```

`--tasks` 列出全部路径。`--tree` 打印这棵树，带上路径时只打印那一棵子树。`--view` 在节点执行时打印经过的每一跳。这三项只读取或追踪路由树，不需要超级节点。

## 一条命令如何执行

一个应用是一棵路由树，再加上每次运行的一个上下文。`use()` 替换整棵树。`include()` 挂上另一棵树，可以带前缀。叶子是函数，或者带 `run` 的对象。一个参数时收到 `Context`。两个参数时仍是 `(config, options)`。对象的 `run` 遵循同一条规则。

`python app.py` 启动的那个进程负责执行每一个节点。之后的命令只是把路径送进这个进程。函数、路由器、Web 服务、Web 端点，都是同一种步骤。对象的状态会跨命令保留，因为这些命令留在第一次执行它的那个工作进程上。再执行一次 `python app.py` 会打印 `pyouter already running`。`python app.py --worker` 作为另一个进程加入进程池。第一个进程还不存在时就发命令，会失败，并告诉你先启动它。`--tasks` 和 `--tree` 只读取路由树，所以它们就在这条命令自己的进程里运行。

先设置好 `options` 再调用 `run()`，会在当前进程里执行。测试和嵌入的调用方走这条路径。

一次运行结束后，节点失败时 `app.result.exit_code` 为 1，并且 `run()` 抛出 `SystemExit`。当上下文动作就是被执行的那个节点时，它的返回值在 `app.result.root.value`。

路由器节点并行运行子节点。`policy="sequence"` 则按顺序运行。子节点的失败收集进 `app.result`，进程以退出码 1 结束。本地网页上的一次运行被停止时，会设置 `ctx.cancelled`。

## 本地网页

在浏览器里打开当前的路由器。服务绑定 `127.0.0.1:8765`，只用 Python 标准库。

```shell
python test.py --web
python test.py --web --port 9000
python test.py test.hello --web --no-browser
```

`--web` 启动同一个 pyouter 进程，并在它上面打开浏览器。之后的 `python test.py test.hello.func` 会路由进这个进程。左栏是路由树。右栏是选中节点的状态、附近路由的地图，以及从这个节点的标准输出和标准错误捕获的日志。单击节点查看。用播放按钮，或双击节点，来执行它。页面上的按钮写着「执行」。执行一个路由器会执行它的子节点，和命令行一样。

`app.web()` 从 Python 里启动同一张页面。`--host` 默认是本机。绑到其他网卡上，就会在那个网卡上暴露任务执行。

节点 runtime 在自己的端口上提供的页面，就是文首那张地图。那一页只展示这个 runtime。执行和停止留在这个 `--web` 页面上。

## Web 服务

一条路由是命令（`cli`）、路由器（`router`）或 Web 端点（`web`）。`node_kind` 报告是哪一种。以前，一个 Flask 或 FastAPI 应用在树里只是一个不透明的节点，里面声明的路由看不见。挂上这个应用后，每条 HTTP 路由都会展平为一个 pyouter 节点。命令行、`--tasks` 和本地网页就能看到这些路由。

安装 pyouter 不需要 Flask 和 FastAPI。只有你挂上的那个应用才会导入它们。

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

`python app.py` 是一直运行的那个进程。`python app.py api` 路由到里面的服务节点，并停在那里，此时 Flask 监听 `127.0.0.1:5000`。`python app.py api.health` 路由到那个端点：向已经在同一进程里监听的服务发一次 `GET /health`，然后这条命令退出。`api.users.user_id` 是 `GET /users/<int:user_id>`，路由方式相同。旁边再挂一个普通函数时，`python app.py hello` 同样是路由进这个进程。

路径参数取自同名选项、`options.params` 或配置。同一路径上的多个方法会变成 `get`、`post` 以及其他方法名。请求返回 `status`、`body`、`method` 和 `path`。400 及以上的响应让这个节点失败。服务节点没在运行时，路由会失败，并告诉你先启动它。服务已经在监听时再运行服务节点，会报告这一点并保持服务不动。停止 `api` 这条命令会停掉服务。pyouter 进程继续运行。

`app.include(service, prefix="api", port=5000)` 选择地址。想自己挂载时，`flatten(service, port=5000)` 返回同一个路由器。FastAPI 应用默认监听 `127.0.0.1:8000`，除非传入端口，并且启动它需要 `uvicorn`。`GET /users/{user_id}` 变成 `users.user_id`。

## 容器

容器也是一个节点。里面的命令和 HTTP 服务是子节点，所以 `a.b.c.d` 这样的路径会穿过容器 `b`，进入 `c`，再到 `d`。安装 pyouter 不需要 Docker。只有容器节点运行时才会用到 `docker` 可执行文件。

```python
from pyouter.app import App
from pyouter.docker import Command, Container, Service
from pyouter.router import Router

box = Container(
    "python:3.12-slim",
    name="tools",
    workers=2,
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

`python app.py a.b` 启动容器并等待。容器的主进程是另一个 pyouter，提供你传入的 `routes`。`workers=2` 在容器里启动这么多个 pyouter 进程。`a.b.c.d` 交给里面的 pyouter，由其中一个进程运行 `echo deep`。`a.b.api.health` 向发布出来的地址发送 `GET /health`。`a.b` 没在运行时，这两条都会失败，并提示先启动容器。容器已在运行时再运行 `a.b`，会报告这一点并保持容器不动。停止 `a.b` 这条命令会删掉它启动的容器。外面的 pyouter 进程继续运行。

镜像里需要有 Python。pyouter 挂载自己的源码和应用脚本再启动它们。你不用写 Dockerfile。`command=("nginx", "-g", "daemon off;")` 在镜像本身就是服务时，替换里面的 runtime。像 `c` 这样的嵌套路由器只是路径上的又一段。

## Compose

Compose 文件是同一种节点，再高一层。文件里的每个服务是一个子节点。命令和 HTTP 路由按服务名加到服务上。用前缀挂上这个项目。这个前缀就是启动整套服务的路径。`.yml` 文件需要 PyYAML。`.json` 的 Compose 文件不需要。

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

```shell
python app.py stack
python app.py stack.web
python app.py stack.web.ping
python app.py stack.api.health
```

`python app.py stack` 运行 `docker compose up -d` 并等待。`stack.web` 是文件里的 `web` 服务。`stack.web.ping` 是在那个服务里执行 `docker compose exec`。`stack.api.health` 向发布出来的地址发一次请求。停止 `stack` 这条命令，会对它启动的这套服务运行 `docker compose down`。

## SSH

SSH 主机也是一个节点。那台主机上的命令是子节点，所以 `a.b.c.d` 会在名为 `b` 的主机上运行。只有主机节点运行时才会用到 `ssh` 程序。连接不询问密码，使用 `ssh` 已经能用的密钥和 agent。

```python
from pyouter.app import App
from pyouter.docker import Service
from pyouter.router import Router
from pyouter.ssh import Remote, SSH

edge = SSH(
    "10.0.0.8",
    user="deploy",
    forwards=("8080:127.0.0.1:80",),
    routes=Router(
        c=Router(d=Remote("echo", "deep")),
        api=Service(
            "http://127.0.0.1:8080",
            health=("GET", "/health"),
        ),
    ),
)

app = App(config={})
app.include(Router(a=Router(b=edge)))
app.run()
```

```shell
python app.py
python app.py a.b
python app.py a.b.c.d
python app.py a.b.api.health
```

`python app.py a.b` 打开一条连接并等待。`a.b.c.d` 在 `deploy@10.0.0.8` 上运行 `echo deep`。`a.b.api.health` 通过本地转发发送 `GET /health`。`a.b` 还没连上时，这两条都会失败，并提示先启动 ssh 节点。已经连上时再运行 `a.b`，会报告这一点并保持连接不动。停止 `a.b` 这条命令会关闭它打开的连接。pyouter 进程继续运行。

用前缀挂上这台主机，或者像上面的 `b` 那样把它放在一个名字下面。`forwards` 就是 `ssh -L` 的值。

## 层

路由树可以嵌套上面这些节点。其中四个会启动新的负载均衡，跨过一个就是新的一层：

| 节点 | 层 | 父进程池做什么 | 这一层的进程池做什么 |
| --- | --- | --- | --- |
| 容器 | docker | 一个工作进程启动并持有这个容器 | 均衡容器下面的每一次调用 |
| SSH 主机 | ssh | 一个工作进程打开并持有这条连接 | 均衡这台主机上的每一次调用 |
| 集群 | cluster | 一个工作进程让集群运行这一个 Pod | 均衡这个 Pod 里面的每一次调用 |
| Web 服务 | server | 一个工作进程启动并持有监听器 | 均衡这个服务处理的每一个请求 |

正在监听的服务是一层。它有自己的工作进程池。你启动的 cli 进程是最外层的进程池，它本身不是一次跨越。

`cli > docker > ssh > docker > server` 是四层。落在层节点上的调用留在父池的一个工作进程上。越过那个节点的调用，在这一层内部均衡。

```python
from pyouter.docker import Container
from pyouter.flatten import flatten
from pyouter.ssh import SSH
from pyouter.router import Router

api = flatten(service, workers=4)
inner = Container("python:3.12-slim", name="inner", routes=Router(api=api), workers=3)
jump = SSH("10.0.0.9", routes=Router(box=inner), workers=2)
edge = Container("python:3.12-slim", name="edge", routes=Router(host=jump), workers=2)
app.include(Router(cli=Router(box=edge)))
```

`cli.box` 是外层容器节点，由 cli 进程池持有。`cli.box.host.box.api.health` 在服务里面，所以由这个服务的 4 个工作进程均衡这次调用。沿途的每一层都已经把调用交给了下一层的进程池。

| 位置 | 参数 | 默认 | 作用 |
| --- | --- | --- | --- |
| 容器、SSH 主机、集群、Web 服务 | `balancer` | `uvicorn` | 哪一个提供者启动这一层的进程池 |
| 容器、SSH 主机、集群、Web 服务 | `workers` | `1` | 这个进程池启动多少个进程。在集群上，这是那一个 Pod 里面的进程池 |
| 容器、SSH 主机、Web 服务 | `runtime` |  | 直接拨号用 `http://host:port`，或者一个 peer id，经控制进程的超级节点到达 |

提供者是进程池的内部细节。你设置 `balancer` 和 `workers`。要换提供者，用 `register_provider(name, start)`，再把那个名字作为 `balancer` 传入。

## 部署

runtime 就是 pyouter 这个包。`deploy_tree` 把这个包装到 `runtime` 指定的机器上，然后推送这一层。已经能应答 `/health` 的监听器会留在原地。之后的推送会替换进程池。

| 这一层跑在哪里 | 包如何到达那里 |
| --- | --- |
| `runtime` 在本机（`127.0.0.1`） | `deploy_tree` 在这里启动 `python -m pyouter.node` |
| 一台 SSH 主机，或经过一台 SSH 主机到达的层 | 第一次联系时，经那台主机的 `ssh` 把包复制到 `~/.pyouter/runtime` 并启动监听器 |
| 从本机启动的容器 | 启动容器时挂载这个包。不写 Dockerfile |
| 集群层 | `deploy_tree` 用这棵树构建镜像，推送它，并应用一个 Deployment |

```python
edge = Container("python:3.12-slim", routes=..., workers=2, runtime="http://127.0.0.1:7710")
jump = SSH("10.0.0.9", routes=..., workers=2, runtime="http://10.0.0.9:7710")
api = flatten(service, workers=4, runtime="http://10.0.0.9:7711")
```

`deploy_tree(app.router)` 是控制调用。没有 `runtime` 的层不会部署。一个远程地址既不是 SSH 主机、也不是经过 SSH 主机到达的，会被拒绝：没有路径把包复制过去。直接的 `http://` runtime 不使用 `--net`。

runtime 也是一个 peer。下一节是这个网络。

| | pyouter | Kubernetes |
| --- | --- | --- |
| 放置的是什么 | 树的一层 | 一个 Pod |
| 谁选择机器 | 写在这一层上的 `runtime` | 调度器 |
| 机器上已经有什么 | 一条到达它的路：这个进程，或 `ssh` | 一个持续调和 Pod 规格的 kubelet |
| 谁启动工作 | 装好的 runtime 启动这一层的进程池 | kubelet 按镜像启动容器 |
| 第二次推送做什么 | 替换提供这一段的进程池 | 向新的规格调和 |

一次实测：一段已经推到节点 runtime 上。四次并发调用各自占用一个进程 0.3 秒：

| workers | 调用 | 占用 | 耗时 | 用到的进程 | 加速 |
| --- | --- | --- | --- | --- | --- |
| 1 | 4 | 0.3s | 1.205s | 1 | 1 |
| 4 | 4 | 0.3s | 0.305s | 4 | 3.95 |

四个进程完成同样的并发工作，大约是四分之一的时间。一个进程则把这些调用一个接一个地跑。测试要求更大的进程池至少快 1.5 倍。

## 对等节点

一个 runtime 就是一个 peer。先启动超级节点，再用这个超级节点的 multiaddr 启动每一层的 runtime，把打印出来的 peer id 抄进 `runtime`，然后调用 `deploy_tree`。层本身不保存超级节点。控制进程带着这份名单。

控制进程也是一个 peer。peer id 不是凭证：谁都可以生成一个。这个网络上的每一个进程，包括超级节点，都用同一个 `--net` 密钥启动。没有这个密钥的进程得不到中继位置，它打开的流也会被拒绝。`deploy_tree` 用 `net` 接收这个密钥，或者读取 `PYOUTER_NET`。

`runtime="http://127.0.0.1:7711"` 仍然直接拨这个 URL，不使用这份名单，也不使用密钥。

### 启动

在其他 peer 能够到达的那台机器上启动超级节点。`--identity` 是密钥文件。同一个文件在重启之后仍是同一个 peer id。默认文件是 `~/.pyouter/peer/identity`。

```bash
python -m pyouter.node --port 7710 --identity ~/.pyouter/peer/sn --sn-listen 127.0.0.1:4001 --net "$PYOUTER_NET"
```

```text
node 7710
web http://127.0.0.1:7710
peer 12D3KooWSnA...
sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA...
```

`node` 是直接 `runtime` 使用的 HTTP 端口。`web` 是这个 runtime 的地图。当这个进程应该接收这一段时，`peer` 就是抄进层里的 id。`sn` 是其他每个 runtime 传给 `--sn` 的 multiaddr。

在浏览器里打开 `web`。面板上的标签会显示层、runtime、peer id、超级节点，以及节点有 IP 时的 IP。可达性标签同时出现在树的那一行和面板上。

启动某一层的 runtime，并让它指向那个 multiaddr：

```bash
python -m pyouter.node --port 7711 --identity ~/.pyouter/peer/api \
  --sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA... \
  --net "$PYOUTER_NET"
```

```text
node 7711
web http://127.0.0.1:7711
peer 12D3KooWApi...
joined 12D3KooWSnA...
```

`joined` 是这个 runtime 在上面预留了位置的超级节点。`joined none` 表示每一个 `--sn` 都失败了。之后向这个 peer id 部署，不会把这一段送过去。

第二个超级节点是另一个进程。runtime 会连接每一个有应答的地址：

```bash
python -m pyouter.node --port 7720 --identity ~/.pyouter/peer/sn-b --sn-listen 127.0.0.1:4002 \
  --sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA... \
  --net "$PYOUTER_NET"
```

```text
node 7720
web http://127.0.0.1:7720
peer 12D3KooWSnB...
sn /ip4/127.0.0.1/tcp/4002/p2p/12D3KooWSnB...
joined 12D3KooWSnA...
```

第二个超级节点拿到第一个超级节点的 multiaddr，所以两者互相看得见。它们不选举领导者，也不保存这棵树。然后一个工作节点会同时拿到两者：

```bash
python -m pyouter.node --port 7711 --identity ~/.pyouter/peer/api \
  --sn /ip4/127.0.0.1/tcp/1/p2p/12D3KooWClosed... \
  --sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA... \
  --net "$PYOUTER_NET"
```

关闭的地址失败。活着的那个有应答。runtime 打印 `joined 12D3KooWSnA...`，不为关闭的地址打印一行。

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `--port` | `7710` | 直接 `runtime` URL 的 HTTP 端口。`0` 选择一个空闲端口 |
| `--host` | `127.0.0.1` | HTTP 绑定地址 |
| `--identity` | `~/.pyouter/peer/identity` | 这个 peer id 的密钥文件 |
| `--sn-listen` |  | `host:port`，让这个进程成为超级节点 |
| `--sn` |  | 一个超级节点的 multiaddr。每一个都重复一次这个参数 |
| `--net` | `PYOUTER_NET` | 共享密钥。加入或提供超级节点时必须有 |

### 路由树

四层、四个 runtime、两个超级节点。每个 runtime 已经启动，并且至少为一个超级节点打印了 `joined`。把每一行 `peer` 抄进 `runtime`。下面的 id 代替那些行。`sn` 是这些 runtime 加入的那一对 multiaddr。它是 `deploy_tree` 的参数，不是层上的字段。

```python
import os

from flask import Flask

from pyouter.app import App
from pyouter.docker import Container
from pyouter.flatten import flatten
from pyouter.node import deploy_tree
from pyouter.router import Router
from pyouter.ssh import SSH

service = Flask("api")


@service.get("/health")
def health():
    return {"ok": True}


api = flatten(service, workers=4, runtime="12D3KooWApi...")
inner = Container(
    "python:3.12-slim",
    name="inner",
    routes=Router(api=api),
    workers=3,
    runtime="12D3KooWInner...",
)
jump = SSH("10.0.0.9", routes=Router(box=inner), workers=2, runtime="12D3KooWJump...")
edge = Container(
    "python:3.12-slim",
    name="edge",
    routes=Router(host=jump),
    workers=2,
    runtime="12D3KooWEdge...",
)

app = App(config={})
app.include(Router(cli=Router(box=edge)))
sent = deploy_tree(
    app.router,
    sn=[
        "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA...",
        "/ip4/127.0.0.1/tcp/4002/p2p/12D3KooWSnB...",
    ],
    net=os.environ["PYOUTER_NET"],
)
```

`sent` 是每一层一条记录，外层路径在前。工作进程数是写在那一层上的数量。`port` 是那一层的进程池在它的 peer 上绑定的空闲端口。它不是 `pyouter.node` 的 `--port`，四个进程池也不共用一个端口。下面的数字是这条记录的形状。真正部署时，填上进程池实际绑定的空闲端口：

```python
[
    {"path": "cli.box", "kind": "docker", "balancer": "uvicorn", "workers": 2, "port": 52431},
    {"path": "cli.box.host", "kind": "ssh", "balancer": "uvicorn", "workers": 2, "port": 53102},
    {"path": "cli.box.host.box", "kind": "docker", "balancer": "uvicorn", "workers": 3, "port": 54880},
    {"path": "cli.box.host.box.api", "kind": "server", "balancer": "uvicorn", "workers": 4, "port": 55114},
]
```

用同一份名单再调用一次 `deploy_tree`，会在同一个 peer 上替换进程池。新记录带上替换后的进程池绑定的端口。

不传 `sn` 时，控制进程读取 `PYOUTER_SN`，一份用逗号分隔的、同样的 multiaddr 名单。不传 `net` 时，它读取 `PYOUTER_NET`。`PYOUTER_PEER_IDENTITY` 是控制 peer 的密钥文件。未设置时，这个文件是 `~/.pyouter/peer/identity`。有超级节点但没有密钥的 peer id，会在发送这一段之前被拒绝。

超级节点已经向 peer 打开流之后，才会做打洞。打洞失败时，这一段仍然留在那条流上。

调用里没有超级节点、也没有 `PYOUTER_SN` 的 peer id，会在发送这一段之前被拒绝。打印了 `joined none` 的 peer，或者加入了别的超级节点的 peer，会在控制进程试图到达它时被拒绝。错误会说这个 peer 没有加入超级节点。

### 检查

测试是 `src/tests/test_peer.py`。它启动真正的 `python -m pyouter.node` 进程，读取它们打印的行，并调用 `deploy_tree`。

```shell
PYTHONPATH=src python3 -m unittest src.tests.test_peer -v
```

| 测试 | 它做什么 |
| --- | --- |
| `test_a_peer_id_stays_the_same_across_reads` | 同一个身份文件读两次得到同一个 id；另一个文件得到另一个 id |
| `test_a_peer_id_without_a_super_node_is_refused` | 带 peer id、不带 `sn` 的 `deploy_tree` 在发送这一段之前抛出 |
| `test_a_slice_reaches_a_peer_that_joined_the_super_node` | 打印了 `joined` 的工作节点收到这一段，第二次推送仍送到同一个 peer |
| `test_a_peer_that_has_not_joined_is_not_given_the_slice` | `--sn` 指向一个关闭的端口时打印 `joined none`；部署抛出 `has not joined` |
| `test_a_peer_joins_the_super_node_that_answers` | 一个关闭的 multiaddr 和一个活着的超级节点；工作节点加入活着的那个并收到这一段 |
| `test_a_peer_without_the_secret_is_not_admitted` | 用另一个 `--net` 启动的工作节点打印 `joined none` |
| `test_a_push_without_the_secret_does_not_land` | 不带密钥的 `deploy_tree` 会抛出，工作节点上的这一段保持未部署 |
| `test_joining_without_a_secret_is_refused` | 没有 `--net` 的 `--sn-listen` 在开始监听之前退出 |

这些测试里的一段是一个服务层：

```python
import os

from pyouter.node import deploy_tree
from pyouter.router import Router

def health(ctx):
    return None

api = Router(health=health)
api.serves = True
api.layer = "server"
api.balancer = "uvicorn"
api.workers = 2
api.runtime = worker_peer_id  # the "peer " line of the runtime that printed "joined"

sent = deploy_tree(Router(api=api), sn=[sn_multiaddr], net=os.environ["PYOUTER_NET"])
# sent[0]["path"] == "api"
# sent[0]["kind"] == "server"
# sent[0]["workers"] == 2
# sent[0]["port"] is the free port that peer's pool bound
```

`worker_peer_id` 和 `sn_multiaddr` 来自[启动](#启动)里的两个进程。`sn_multiaddr` 是 `sn` 那一行。`worker_peer_id` 是为那个超级节点打印了 `joined` 的 runtime 的 `peer` 那一行。同样的调用、`workers=2`，再来一次，返回的记录具有相同的路径、种类和工作进程数。

## 集群

云账号不会把 Kubernetes 节点交给你。你推送一个镜像。集群启动容器。那个容器是一个 Pod，这个 Pod 是一个 peer。`workers` 是 Pod 里面的进程池。Deployment 的副本数是 1。

```python
import os

from flask import Flask

from pyouter.app import App
from pyouter.cluster import Cluster
from pyouter.flatten import flatten
from pyouter.node import deploy_tree
from pyouter.router import Router

service = Flask("api")


@service.get("/health")
def health():
    return {"ok": True}


api = flatten(service, workers=4)
edge = Cluster(
    "registry.example.com/app:1.2",
    name="edge",
    routes=Router(api=api),
    workers=4,
)

app = App(config={})
app.include(Router(cli=Router(box=edge)))
sent = deploy_tree(
    app.router,
    sn=["/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWSnA..."],
    net=os.environ["PYOUTER_NET"],
)
```

`registry.example.com/app:1.2` 是要构建并推送的名字。pyouter 用这棵树写出镜像：pyouter 包、应用，以及入口 `python -m pyouter.node`。不用手写 Dockerfile。

Pod 把一个 Secret 挂在 `/var/pyouter/identity`。这个文件在控制机器的 `~/.pyouter/cluster` 下创建并重复使用，所以 Pod 重启后仍是同一个 peer id。同一个 Secret 里放着网络密钥，容器从 `PYOUTER_NET` 读取它。容器参数是这次 `deploy_tree` 调用传入的每一个超级节点的 `--sn`。层本身不保存这份名单。`imagePullPolicy` 是 `Always`。Pod 模板带有这棵树和网络密钥的哈希，所以新镜像或新密钥会滚出新的 Pod。

`sent` 是每一层一条记录，外层路径在前。集群记录和它里面的服务都从这同一个 peer 返回。`port` 是那一层的进程池在 Pod 里绑定的空闲端口：

```python
[
    {"path": "cli.box", "kind": "cluster", "balancer": "uvicorn", "workers": 4, "port": 52431},
    {"path": "cli.box.api", "kind": "server", "balancer": "uvicorn", "workers": 4, "port": 53102},
]
```

写在集群下面、又没有 `runtime` 的层，会推到这同一个 peer。把 `runtime` 设成 `http://` URL 或 peer id 的层，会装到那个 runtime 上，不会送到这个 Pod。

用同一棵树再调用一次 `deploy_tree`，不会构建，也不会滚动。它再次推送这些段，peer 替换每一层的进程池。改 `workers` 也是同一次推送：镜像保持不变。改了树，或者改了镜像名，才会构建、推送并滚动 Deployment。新 Pod 加入之后，这些段再推给它。

调用里没有超级节点、也没有 `PYOUTER_SN` 的集群层，会在构建镜像之前被拒绝。错误会说集群需要一个超级节点。

```shell
PYTHONPATH=src python3 -m unittest src.tests.test_cluster -v
```

| 测试 | 它做什么 |
| --- | --- |
| `test_a_cluster_image_must_name_a_registry` | 没有仓库名的镜像名会被拒绝 |
| `test_a_cluster_without_a_super_node_is_refused` | 没有 `sn` 的 `deploy_tree` 在 `docker` 运行之前抛出 |
| `test_a_cluster_manifest_is_one_pod` | Deployment 有一个副本、身份挂载和 `--sn`；网络密钥在 Secret 里，不在参数里 |
| `test_a_cluster_layer_is_one_pod_and_one_peer` | 这一段到达已加入的 peer；第二次推送和 `workers` 的改动跳过构建；新的镜像名会再次构建 |
| `test_a_layer_with_its_own_runtime_is_not_sent_to_the_pod` | 写了 `runtime` 的子节点被推到那里，Pod 收到的是集群这一段 |

## 更新

### 0.12.0

* 超级节点网络需要共享的 `--net` 密钥；没有它的 peer 不会被中继，它的流也会被拒绝
* `deploy_tree(..., net=)` 带上这个密钥，集群 Pod 从 `PYOUTER_NET` 读取它

### 0.11.0

* 集群层是一个 Pod、一个 peer；`workers` 是这个 Pod 里面的进程池
* `deploy_tree` 用这棵树构建镜像，推送它，并应用一个 Deployment
* Pod 加入这次调用传入的超级节点；同一棵树的第二次推送不会再次构建

### 0.10.0

* runtime 是一个 peer；`runtime` 可以是 peer id，也可以是 `http://host:port`
* `--sn-listen` 让这个 runtime 成为超级节点，`--sn` 加入名单里每一个能够到达的超级节点
* `deploy_tree` 经控制进程的超级节点，把 peer id 的那一层送出去

### 0.9.0

* 节点 runtime 留在一台物理节点上，接收推给它的层
* `deploy_tree` 在第一次联系时安装 runtime，然后启动这一层的进程池
* 回环 runtime 在这里启动；SSH 主机经 `ssh` 接收这个包

### 0.8.0

* 容器、SSH 主机和 Web 服务是层，各自有自己的 `balancer` 和 `workers`
* 默认的均衡器把并发工作分到这一层的进程上

### 0.7.0

* SSH 主机是一个节点；它下面的命令和转发的 HTTP 路由是子节点

### 0.6.0

* Compose 文件展平为一个项目节点，以及每个服务一个节点

### 0.5.0

* 容器是一个节点；它下面的命令和发布出来的 HTTP 路由是子节点

### 0.4.0

* `python app.py` 启动执行每一个节点的进程
* 之后的命令路由进这个进程，不论是函数、路由器还是 Web 路由

### 0.3.1

* 展平后的 Web 服务保持监听；路由节点向它发送请求

### 0.3.0

* 一条路由是 `cli`、`router` 或 `web`
* Flask 和 FastAPI 应用展平为 pyouter 节点

### 0.2.0

* 命令行和本地网页共用一个分发器
* 每次运行有 `Context` 和 `RunResult`；上下文动作接收 `ctx`
* `include()` 挂上路由器；`policy="sequence"` 按顺序运行子节点
* 失败的子节点把退出码设为 1

### 0.1.2

* 增加本地网页（`--web`），用来浏览、查看和运行路由器

### 0.1.0

* 修复执行器的缺陷

### 0.0.9

* 改进 -v、--view、-i、--insepect，用于路径调试

### 0.0.8

* 增加 app.option
* 改进 App(config=)，支持配置文件路径
* 增加异步
* 用异步线程池并行执行路由器

### 0.0.7

* 增加 pyouter 自己的 bash 和 fish 补全

### 0.0.6

* 修复 fish 补全安装中的缺陷

### 0.0.5

* 需要时传入配置

### 0.04

* 自定义解析器

### 0.0.3

* 支持 pyouter 补全
* pyouter 作为包的入口

### 0.0.2

* 把插件改名为 pyouter

### 0.0.1

* 项目初始化
* 增加 pypi 设置
* 增加安装器
