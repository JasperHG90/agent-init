# Editor extensions — design notes

This file describes how a Zed / VS Code / JetBrains extension would talk to
`aim`. The extensions themselves are not built here (they live in
their own repos, in different languages). This is the contract.

## Status surface

A status-bar item showing project health: outdated skills, drifted regions,
missing prereqs.

```sh
aim doctor --json
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
| `aim init <project>`                 | Scaffold AGENTS.md + chosen mirrors             |
| `aim init <project> --diff`          | Preview what init would change (unified diff)   |
| `aim skill list --json`              | (not yet) List indexed skills as JSON           |
| `aim skill update <qn>`              | Update one skill                                |
| `aim skill update-many --all --outdated` | Bulk update                                 |
| `aim check`                          | Pre-commit-friendly drift check                 |
| `aim doctor`                         | Full audit across configured roots              |

## MCP integration

Editors that already host MCP clients (Claude Desktop, Cursor, Zed) can
register the local MCP server directly. Add to the editor's MCP config:

```json
{
  "mcpServers": {
    "aim": {
      "command": "aim",
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

- Add `--json` flag to `aim doctor`, `skill list`, `repo list`,
  `rule list`, `profile list`. Today they print human-readable lines —
  adding `--json` is a small change per command.
- Define a stable CLI version (`aim --version`) so extensions can
  gate on minimum supported versions.
- Publish a JSON Schema for `manifest.json` so extensions can validate
  before reading.

These are intentionally not built yet — they should be driven by the
first real extension's needs rather than speculative work.
