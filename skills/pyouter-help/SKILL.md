---
name: pyouter-help
description: >-
  Use when a person wants to start using pyouter, bring existing Python
  scripts into pyouter, or asks how to use the pyouter skills. Two projects:
  a new project from nothing, and an existing project of scripts, a CLI,
  maybe a service, maybe containers. Walk one of those step by step and
  open the other skills only when this skill says to.
---

# How a person uses pyouter

You are walking a person through pyouter. Do the steps in order. Do not open a later skill until the step names it. Do not deploy, add a super node, or set `--net` in a first session.

The installed `pyouter` command only installs shell completion (`pyouter install.bash`). The person's entry is the `app.py` you create. They run `python app.py`.

## 1. Say which project this is

Say one sentence before you edit.

**New.** The directory has no commands they already run. They want to start from nothing.

**Existing.** There are already Python scripts, a CLI, modules that call each other ad hoc, maybe a Flask or FastAPI app, maybe a container or Compose file. They want one tree in front of what already runs.

A repo that already imports pyouter is not a new project. Continue from the step they have reached.

## 2. New project

1. Read `skills/pyouter-init/SKILL.md`, section "New project". Create that one file. One leaf. No service, container, SSH host, or cluster.
2. Stop and give them the commands. The first process stays running.

   ```shell
   python app.py
   python app.py hello
   python app.py --tasks
   ```

   `hello` in the second terminal must print. `--tasks` must list `hello`. Then they can look at the tree:

   ```shell
   python app.py --web
   ```

3. The next real command is another leaf. Read `skills/pyouter-route/SKILL.md`. Add one command they named. Do not add a batch of placeholders.
4. Go to "When the tree grows" only for something they asked for.

Done for this session when one path runs and `--tasks` lists it.

## 3. Existing project

1. Inventory before you edit. Show them this list, using their real files:

   ```text
   commands:
   - python scripts/ingest.py --date 2024-01-01  →  data.ingest
   services:
   - server.py Flask on 127.0.0.1:5000           →  api
   containers:
   - compose.yaml                                →  not in the first mount
   left where they are:
   - every other script
   ```

   Put in the first mount only the one command they run most. A service goes in only if they already start it. A container goes in only if they asked to run that stack from the tree. Everything else stays unmounted.

2. Read `skills/pyouter-init/SKILL.md`, section "Existing project". Add one `app.py`. Import their function or mount their app. Do not move, rename, or rewrite their modules.
3. Show the mapping `old command → dotted path`. Then the same run as a new project: start `python app.py`, route that path from another terminal, then `python app.py --tasks`. The old command and the new path must do the same thing.
4. The next group is another path, after this one works, and only if they want it. Read `skills/pyouter-route/SKILL.md`.
5. Go to "When the tree grows" only for something on the inventory that they asked to include.

Done for this session when that one old command runs through its dotted path.

## When the tree grows

Open a skill only when the row matches. Read `skills/pyouter/SKILL.md` for the rules that apply to every edit.

| They now need | Read |
| --- | --- |
| another function, object, or flag | `skills/pyouter-route/SKILL.md` |
| a Flask, FastAPI, or Starlette app they already have, or `--web` | `skills/pyouter-web/SKILL.md` |
| a command that must run in a container, a Compose file they already use, or an SSH host | `skills/pyouter-place/SKILL.md` |
| more than one worker on that container, host, or service | `skills/pyouter-layer/SKILL.md` |
| that layer on another machine, a peer id, or a cluster pod | `skills/pyouter-network/SKILL.md` |

A script that runs on this machine stays a leaf. Do not put it in a container to make the tree look complete. Do not add `runtime`, `workers`, or `--net` to reach a later skill.

## What you tell them

At each step, the next thing they type is one command. Say which process must already be running. Do not explain peers, the secret, or the cluster until the last row of the table is the thing they asked for.
