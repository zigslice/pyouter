---
name: pyouter-help
description: >-
  Use when a person wants to start using pyouter, or asks which skill to
  follow. Two projects: a new project from nothing uses pyouter-init, and
  an existing project of scripts, a CLI, maybe a service, maybe containers
  uses pyouter-refactor, which runs to the end and keeps current behavior.
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

Read `skills/pyouter-refactor/SKILL.md` and follow it until its contract is closed. Do not switch to `pyouter-init`. Do not stop after the first script, and do not wait to be asked for the next one.

The refactor keeps every current command, service, and container working, moves the work into modules that match the dotted paths, and leaves `app.py` as the wiring. Old entry points stay as shims. It does not add a peer network.

## When a new project grows

This table is only for a new project, after its first route runs. An existing project does not pause here. `pyouter-refactor` already opens the route, web, and place skills for each row of its contract.

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

On a new project, the next thing they type is one command. Say which process must already be running.

On an existing project, tell them the contract, then do the refactor. When it is closed, give them the table of old invocation, dotted path, and what you ran. Do not explain peers, the secret, or the cluster unless that project already deploys that way.
