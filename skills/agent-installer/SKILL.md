---
name: agent-installer
description: |
  Use whenever the user or another agent asks to install, add, update, delete,
  search for, or list skills, sub-agents, or rules managed by aim.
  Covers `aim skill`, `aim agent`, and `aim rule` commands.
  Always prefer the `--compact` output format to keep context small.
---

# Agent Installer

A skill for installing and managing aim artifacts: skills, sub-agents, and rules.

## When to use

Use this skill whenever the user (or another skill/agent) asks to:

- Install, add, update, delete, or roll back a skill
- Install, add, update, delete, or roll back a sub-agent
- Install, add, update, delete, or roll back a rule
- Search for or list available skills, agents, or rules

## Workflow

1. **Ensure `aim` is installed.** Before running any command, check whether `aim` is available:

   - Try `command -v aim` or `aim --version`.
   - If the command succeeds, continue with the workflow.
   - If the command is not found, tell the user: "`aim` is not installed. Install it with `uv tool install`? Defaults to the latest version; say a version number if you want a specific one."
   - If the user agrees, run:
     - Latest: `uv tool install git+https://github.com/JasperHG90/agent-integrations-manager.git`
     - Specific version: `uv tool install git+https://github.com/JasperHG90/agent-integrations-manager.git@<version>`
   - After installing, verify with `aim --version` before continuing.
   - If the user declines, stop and explain that this skill requires `aim`.

2. **Identify the artifact type** from the request:
   - Skills: `aim skill ...`
   - Agents: `aim agent ...`
   - Rules: `aim rule ...`

3. **If the exact name is not known, search first.** Prefer `--compact` NDJSON output to keep token usage low:
   - Skills: `aim skill search <query> --compact`
   - Agents: `aim agent search <query> --compact`
   - Rules: `aim rule list --compact` and filter client-side by the query

4. **Present top matches with `AskUserQuestion`.** If the request is ambiguous or multiple artifacts match, render the top matches as a single-select `AskUserQuestion`. Use the compact NDJSON fields for labels (qualified name and short description). The tool requires `header`, `question`, `type`, and `options` fields; each option must be an object with `label`, `value`, and `description`. If `AskUserQuestion` is unavailable, list the matches in plain text and ask the user to reply with the qualified name.

   Example:
   ```json
   {
     "header": "Select a skill",
     "question": "Which skill do you want to install?",
     "type": "single_select",
     "options": [
       {"label": "repo-add", "value": "aim/repo-add", "description": "Register source repositories"},
       {"label": "agent-installer", "value": "aim/agent-installer", "description": "Install skills, agents, and rules"}
     ]
   }
   ```

5. **Execute the right command** for the artifact and action:
   - Install: `aim skill install <qualified>` / `aim agent install <qualified>` / `aim rule install <name>`
   - Update: `aim skill update <qualified>` / `aim agent update <qualified>` / `aim rule update <name>`
   - Delete: `aim skill delete <qualified>` / `aim agent delete <qualified>` / `aim rule delete <name>`
   - Rollback: `aim skill rollback <qualified>` / `aim agent rollback <qualified>` / `aim rule rollback <name>`
   - List: `aim skill list --compact` / `aim agent list --compact` / `aim rule list --compact`

6. **Surface CLI warnings verbatim.** If `aim` prints warnings about missing prereqs, capability collisions, or local edits, relay them to the user without rewording.

7. **If the artifact is not found,** suggest registering a source repo first using the `repo-add` skill.

## Compact output discipline

For every list or search command, append `--compact` so downstream agents get low-token, structured NDJSON they can parse reliably.
