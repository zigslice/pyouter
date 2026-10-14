---
name: pyouter-network
description: >-
  Use when deploying a pyouter layer with deploy_tree, setting runtime to an
  http URL or a peer id, starting python -m pyouter.node, joining a super
  node, passing --net or PYOUTER_NET, or placing a cluster pod. Covers the
  shared secret, what it does not protect, and the one-pod cluster.
---

# Deploy, peers, and cluster

Read `skills/pyouter/SKILL.md` and `skills/pyouter-layer/SKILL.md` first. Source: `src/pyouter/node.py`, `src/pyouter/peer.py`, `src/pyouter/cluster.py`.

`deploy_tree(router, sn=None, net=None)` installs each layer, then pushes that layer's slice. It returns one record per layer, outer path first: `path`, `kind`, `balancer`, `workers`, `port`. `port` is the free port that layer's pool bound. It is not `--port` of `pyouter.node`.

A layer with no `runtime`, and not under a cluster that was just placed, raises `<path> has no runtime`. Routing to one cluster node publishes that pod only. It does not walk the other layers. Use `deploy_tree` to push all of them.

## An http runtime

```python
Container("python:3.12-slim", routes=routes, workers=2, runtime="http://127.0.0.1:7710")
SSH("10.0.0.9", routes=routes, workers=2, runtime="http://10.0.0.9:7710")
flatten(service, workers=4, runtime="http://10.0.0.9:7711")
```

`deploy_tree(app.router)` is enough. A direct `http://` URL does not use `sn` or `net`.

A listener that already answers `/health` stays. A later push replaces the pool. `127.0.0.1` is started here with `python -m pyouter.node`. An SSH host, or a layer reached through one, receives the package at `~/.pyouter/runtime` over that host's `ssh`. Any other remote URL that is down is refused: there is no path to copy the package there.

The node HTTP port is a separate door. `--net` does not guard `POST /deploy`. Leave `--host` at `127.0.0.1` unless that interface is meant to accept deploys.

## A peer id

A peer id is not a credential. Every process on the network, including super nodes and the control process, is started with the same secret.

```bash
python -m pyouter.node --port 7710 --identity ~/.pyouter/peer/sn \
  --sn-listen 127.0.0.1:4001 --net "$PYOUTER_NET"
```

```text
node 7710
web http://127.0.0.1:7710
peer 12D3KooW...
sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooW...
```

Copy the `peer` line into `runtime`. Copy the `sn` line into the other runtimes' `--sn` and into `deploy_tree(..., sn=[...])`.

```bash
python -m pyouter.node --port 7711 --identity ~/.pyouter/peer/api \
  --sn /ip4/127.0.0.1/tcp/4001/p2p/12D3KooW... \
  --net "$PYOUTER_NET"
```

`joined <id>` means the reservation landed. `joined none` means every `--sn` failed, or the secret did not match. A later deploy to that peer id does not deliver the slice.

```python
deploy_tree(app.router, sn=["/ip4/127.0.0.1/tcp/4001/p2p/12D3KooW..."], net=os.environ["PYOUTER_NET"])
```

Leave `sn` unset to read `PYOUTER_SN`, a comma-separated list. Leave `net` unset to read `PYOUTER_NET`. Do not store `sn` or `net` on the layer.

The same `--identity` file is the same peer id after a restart. The default file is `~/.pyouter/peer/identity`. `PYOUTER_PEER_IDENTITY` selects the control peer's file. Do not create a new key file on every deploy when the tree already names a peer id.

| missing piece | error |
| --- | --- |
| peer id and no super node | `needs a super node` |
| super node and no secret | `needs a network secret` |
| `--sn-listen` without `--net` | exit 1, `this network needs --net`, before it listens |
| peer printed `joined none`, or joined a different super node | `has not joined a super node` |

A peer without the secret is not given a relay slot, and a stream it opens is refused. A failed hole punch still leaves the slice on the relay stream.

`peer_reachable` only asks a control peer that is already running. Do not call it to boot one.

## Cluster

```python
from pyouter.cluster import Cluster

edge = Cluster(
    "registry.example.com/app:1.2",
    name="edge",
    routes=Router(api=flatten(service, workers=4)),
    workers=4,
)
app.include(Router(cli=Router(box=edge)))
deploy_tree(app.router, sn=[sn_multiaddr], net=os.environ["PYOUTER_NET"])
```

`image` must contain a registry slash, such as `registry.example.com/app:1.2`. A bare name raises `cluster image must be a registry name`. `name` is a DNS label of at most 53 characters. `workers` is the pool inside the pod. The Deployment replica count is 1. Do not set replicas. Do not write a Dockerfile.

`deploy_tree` builds the image from this tree, pushes it, and applies one Deployment. The pod's entrypoint is `python -m pyouter.node`. No super node in the call and no `PYOUTER_SN` raises `needs a super node` before `docker` runs. No secret raises `needs a network secret` the same way.

The pod mounts a Secret at `/var/pyouter/identity`. That file is reused from `~/.pyouter/cluster` on the control machine, so a restarted pod is the same peer id. The same Secret holds the network secret. The container reads it from `PYOUTER_NET` through `secretKeyRef`. Do not put the secret in the container args or the image. The args are `--sn` for each super node passed to this call.

A child layer under the cluster with no `runtime` is pushed to this same peer. A child that sets `runtime` to an `http://` URL or a peer id is installed there instead.

A second `deploy_tree` of the same tree does not build or roll. It pushes the slices again. Changing `workers` is that same push. Changing the tree, the image name, or the secret builds, pushes, and rolls. The pod template hash covers the tree and the secret.

A cluster with no super node is refused before an image is built.
