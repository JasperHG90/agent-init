# Editor extensions — design notes

This file describes how a Zed / VS Code / JetBrains extension would talk to
`agent-init`. The extensions themselves are not built here (they live in
their own repos, in different languages). This is the contract.

## Status surface

A status-bar item showing project health: outdated skills, drifted regions,
missing prereqs.

```sh
agent-init doctor --json
```

(Not yet implemented — see "JSON output" below.) Returns:

```json
{
  "ok": false,
  "projects_audited": 1,
  "counts": {"error": 0, "warning": 2, "info": 1},
  "findings": [
    {"severity": "warning", "project": "/Users/me/proj",
     "message": "anth/code-review: target .claude/skills/code-review edited since install"},
    {"severity": "info", "project": null,
     "message": "repo anthropic: not refreshed in 41 days"}
  ]
}
```

## Command-palette actions

Extensions should shell out for these commands. Each is already exit-coded
sensibly (0 = success, 1 = drift / failure).

| Command                                     | What it does                                     |
| ------------------------------------------- | ------------------------------------------------ |
| `agent-init init <project>`                 | Scaffold AGENTS.md + chosen mirrors             |
| `agent-init init <project> --diff`          | Preview what init would change (unified diff)   |
| `agent-init skill list --json`              | (not yet) List indexed skills as JSON           |
| `agent-init skill update <qn>`              | Update one skill                                |
| `agent-init skill update-many --all --outdated` | Bulk update                                 |
| `agent-init check`                          | Pre-commit-friendly drift check                 |
| `agent-init doctor`                         | Full audit across configured roots              |

## MCP integration

Editors that already host MCP clients (Claude Desktop, Cursor, Zed) can
register the local MCP server directly. Add to the editor's MCP config:

```json
{
  "mcpServers": {
    "agent-init": {
      "command": "agent-init",
      "args": ["mcp", "serve"],
      "transport": "stdio"
    }
  }
}
```

The server exposes:
- `list_skills` — list skills installed in the active project (cwd)
- `get_skill` — return the SKILL.md body for a qualified_name

## Open work for these extensions

- Add `--json` flag to `agent-init doctor`, `skill list`, `repo list`,
  `rule list`, `profile list`. Today they print human-readable lines —
  adding `--json` is a small change per command.
- Define a stable CLI version (`agent-init --version`) so extensions can
  gate on minimum supported versions.
- Publish a JSON Schema for `manifest.json` so extensions can validate
  before reading.

These are intentionally not built yet — they should be driven by the
first real extension's needs rather than speculative work.
