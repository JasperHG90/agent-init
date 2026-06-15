"""Minimal MCP (Model Context Protocol) server over stdio.

Exposes a project's installed skills to live agents (Claude Desktop, Cursor,
etc.) without pre-stuffing every skill body into the prompt.

Why hand-rolled instead of `pip install mcp`? Keeps deps small. We only need
three methods: `initialize`, `tools/list`, `tools/call`. Everything else
returns a method-not-found error and clients are tolerant of that.

Read-only by design: only `list_skills` and `get_skill` are exposed. If you
want to write through MCP, add it explicitly (this is a deliberate scope cap).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_init.core import manifest

SERVER_NAME = "agent-init"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _make_response(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _make_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "list_skills",
            "description": "List the skills installed in the active agent-init project.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "get_skill",
            "description": "Return the SKILL.md body of an installed skill, by qualified_name.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "qualified_name": {
                        "type": "string",
                        "description": "<repo_alias>/<skill_name> matching one returned by list_skills.",
                    }
                },
                "required": ["qualified_name"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(name: str, args: dict[str, Any], project_root: Path) -> dict[str, Any]:
    try:
        m = manifest.load(project_root)
    except manifest.ManifestNotFoundError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No .agent-init/manifest.json at {project_root}. Run `agent-init init` first.",
                }
            ],
            "isError": True,
        }

    if name == "list_skills":
        lines = [
            f"{s.qualified_name}  ({s.current.identifier()})  -> {s.target_dir}"
            for s in m.skills
        ]
        body = "\n".join(lines) if lines else "(no skills installed)"
        return {"content": [{"type": "text", "text": body}]}

    if name == "get_skill":
        qn = args.get("qualified_name", "")
        match = next((s for s in m.skills if s.qualified_name == qn), None)
        if match is None:
            return {
                "content": [{"type": "text", "text": f"Skill not installed: {qn}"}],
                "isError": True,
            }
        target = project_root / match.target_dir / "SKILL.md"
        if not target.exists():
            return {
                "content": [{"type": "text", "text": f"SKILL.md missing at {target}"}],
                "isError": True,
            }
        return {"content": [{"type": "text", "text": target.read_text()}]}

    return {
        "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
        "isError": True,
    }


def _handle(req: dict[str, Any], project_root: Path) -> dict[str, Any] | None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return _make_response(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {}},
            },
        )
    if method == "notifications/initialized":
        return None  # notification — no response
    if method == "tools/list":
        return _make_response(req_id, {"tools": _tools()})
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}
        return _make_response(req_id, _call_tool(name, args, project_root))
    return _make_error(req_id, -32601, f"method not found: {method}")


def serve(project_root: Path | None = None) -> None:
    """Run the stdio server loop until EOF."""
    root = (project_root or Path.cwd()).expanduser().resolve()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(
                json.dumps(_make_error(None, -32700, "parse error")) + "\n"
            )
            sys.stdout.flush()
            continue
        response = _handle(req, root)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


# Test-only helper: run one request synchronously without touching stdio.
def handle_for_test(req: dict[str, Any], project_root: Path) -> dict[str, Any] | None:
    return _handle(req, project_root)
