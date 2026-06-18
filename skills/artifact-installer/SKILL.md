---
name: artifact-installer
description: |
  Use whenever the user or another agent asks to install, add, update, remove,
  roll back, search for, or list skills, sub-agents, or rules managed by aim.
  Covers `aim skill`, `aim subagent`, and `aim rule` commands. This skill never
  registers source repositories — if a repo is missing, defer to the repo-add
  skill. Always prefer the `--compact` output format to keep context small.
---

# Artifact Installer

A skill for managing aim artifacts — skills, sub-agents, and rules — in a
project. It installs from **already-registered** source repositories by
qualified name (`<alias>/<name>`). It does **not** register repositories.

## When to use

Use this skill whenever the user (or another skill/agent) asks to:

- Add, update, remove, or roll back a skill, sub-agent, or rule
- Search for or list available skills, sub-agents, or rules

For *registering a source repository*, use the **repo-add** skill instead.

## Workflow

1. **Ensure `aim` is installed.** Before running any command, check whether `aim` is available:

   - Try `command -v aim` or `aim --version`.
   - If the command succeeds, continue.
   - If not found, tell the user: "`aim` is not installed. Install it with `uv tool install`? Defaults to the latest version; say a version number if you want a specific one."
   - If the user agrees, run:
     - Latest: `uv tool install git+https://github.com/JasperHG90/agent-integrations-manager.git`
     - Specific version: `uv tool install git+https://github.com/JasperHG90/agent-integrations-manager.git@<version>`
   - After installing, verify with `aim --version`.
   - If the user declines, stop and explain that this skill requires `aim`.

2. **Identify the artifact type** from the request:
   - Skills → `aim skill ...`
   - Sub-agents → `aim subagent ...`
   - Rules → `aim rule ...`

3. **Search the index first** (it only contains artifacts from *registered* repos). Prefer `--compact` NDJSON to keep token usage low:
   - `aim skill search <query> --compact`
   - `aim subagent search <query> --compact`
   - `aim rule search <query> --compact`

4. **If the search returns nothing, the source repo is not registered. Stop.**
   Do **not** run `aim repo add` and do **not** pass `--yes`. Tell the user the
   repo isn't registered and that they should register it with the **repo-add**
   skill first, then retry. Registering repositories is out of scope for this
   skill.

5. **Present matches with `AskUserQuestion`.** If the request is ambiguous or several artifacts match, render the top matches as a single-select `AskUserQuestion` (label = qualified name, description = short summary). If `AskUserQuestion` is unavailable, list the matches and ask the user to reply with the qualified name.

6. **Execute the command by qualified name** (`<alias>/<name>`). These operate on
   already-registered repos and fail cleanly if the repo is not registered —
   they never auto-register:
   - Add:      `aim skill add <alias>/<name>` · `aim subagent add <alias>/<name>` · `aim rule add <alias>/<name>`
   - Update:   `aim skill update <alias>/<name>` · `aim subagent update <alias>/<name>` · `aim rule update <alias>/<name>`
   - Remove:   `aim skill remove <alias>/<name>` · `aim subagent remove <alias>/<name>` · `aim rule remove <alias>/<name>`
   - Rollback: `aim skill rollback <alias>/<name>` · `aim subagent rollback <alias>/<name>` · `aim rule rollback <alias>/<name>`
   - List:     `aim skill list --compact` · `aim subagent list --compact` · `aim rule list --compact`

7. **If `add` reports that the repo is not registered,** treat it exactly like
   step 4: stop and defer to the repo-add skill. Never pass a git URL or `--yes`
   to work around it.

8. **Surface CLI warnings verbatim.** If `aim` prints warnings about missing prereqs, capability collisions, or local edits, relay them to the user without rewording.

## Compact output discipline

For every list or search command, append `--compact` so downstream agents get low-token, structured NDJSON they can parse reliably.
