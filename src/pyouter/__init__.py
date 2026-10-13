from .router import Router, node_kind
from .flatten import WebEndpoint, flatten
from .docker import Command, Compose, Container, Service
from .context import Context, Hooks, NodeResult, RunResult
from .oh_my_zsh.install import install as omz
from .fish.install import install as fish
from .bash.install import install as bash
from .app import App


def runner():
    app = App()
    app.use(
        router=Router(
            install=Router(
                ohmyzsh=omz,
                fish=fish,
                bash=bash)))
    app.run()
