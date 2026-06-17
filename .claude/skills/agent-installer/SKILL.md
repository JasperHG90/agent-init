---
name: agent-installer
description: |
  Use whenever the user or another agent asks to install, add, update, delete,
  search for, or list skills, sub-agents, or rules managed by agent-init.
  Covers `agent-init skill`, `agent-init agent`, and `agent-init rule` commands.
  Always prefer the `--compact` output format to keep context small.
---

# Agent Installer

A skill for installing and managing agent-init artifacts: skills, sub-agents, and rules.

## When to use

Use this skill whenever the user (or another skill/agent) asks to:

- Install, add, update, delete, or roll back a skill
- Install, add, update, delete, or roll back a sub-agent
- Install, add, update, delete, or roll back a rule
- Search for or list available skills, agents, or rules

## Workflow

1. **Identify the artifact type** from the request:
   - Skills: `agent-init skill ...`
   - Agents: `agent-init agent ...`
   - Rules: `agent-init rule ...`

2. **If the exact name is not known, search first.** Prefer `--compact` NDJSON output to keep token usage low:
   - Skills: `agent-init skill search <query> --compact`
   - Agents: `agent-init agent search <query> --compact`
   - Rules: `agent-init rule list --compact` and filter client-side by the query

3. **Present top matches** using the compact NDJSON output. If the request is ambiguous, ask the user to pick one.

4. **Execute the right command** for the artifact and action:
   - Install: `agent-init skill install <qualified>` / `agent-init agent install <qualified>` / `agent-init rule install <name>`
   - Update: `agent-init skill update <qualified>` / `agent-init agent update <qualified>` / `agent-init rule update <name>`
   - Delete: `agent-init skill delete <qualified>` / `agent-init agent delete <qualified>` / `agent-init rule delete <name>`
   - Rollback: `agent-init skill rollback <qualified>` / `agent-init agent rollback <qualified>` / `agent-init rule rollback <name>`
   - List: `agent-init skill list --compact` / `agent-init agent list --compact` / `agent-init rule list --compact`

5. **Surface CLI warnings verbatim.** If `agent-init` prints warnings about missing prereqs, capability collisions, or local edits, relay them to the user without rewording.

6. **If the artifact is not found,** suggest registering a source repo first using the `repo-add` skill.

## Compact output discipline

For every list or search command, append `--compact` so downstream agents get low-token, structured NDJSON they can parse reliably.