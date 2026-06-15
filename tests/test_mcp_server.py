"""Tests for the MCP server core handler.

We exercise `_handle` synchronously rather than driving stdio. That covers
the JSON-RPC dispatch and the tool implementations without needing a
subprocess.
"""

from __future__ import annotations

from pathlib import Path

from agent_init import mcp_server
from agent_init.core import init as init_mod
from agent_init.core import install, repos
from tests.fixtures import git_fixtures


def _bare(tmp_path: Path) -> Path:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# foo\n\nFoo skill body.\n"}
    )
    return git_fixtures.make_bare_remote(working, tmp_path / "bare.git")


def test_initialize(home: Path, project_root: Path) -> None:
    resp = mcp_server.handle_for_test(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        project_root,
    )
    assert resp is not None
    assert resp["result"]["serverInfo"]["name"] == "agent-init"


def test_tools_list(home: Path, project_root: Path) -> None:
    resp = mcp_server.handle_for_test(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        project_root,
    )
    assert resp is not None
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"list_skills", "get_skill"}


def test_list_skills_returns_installed(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    bare = _bare(tmp_path)
    repos.add("anth", f"file://{bare}")
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    install.install(project_root, "anth/foo")

    resp = mcp_server.handle_for_test(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "list_skills", "arguments": {}},
        },
        project_root,
    )
    assert resp is not None
    text = resp["result"]["content"][0]["text"]
    assert "anth/foo" in text


def test_get_skill_returns_body(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    bare = _bare(tmp_path)
    repos.add("anth", f"file://{bare}")
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    install.install(project_root, "anth/foo")
    resp = mcp_server.handle_for_test(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_skill",
                "arguments": {"qualified_name": "anth/foo"},
            },
        },
        project_root,
    )
    assert resp is not None
    text = resp["result"]["content"][0]["text"]
    assert "Foo skill body." in text


def test_get_skill_unknown_returns_error(
    home: Path, project_root: Path
) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    resp = mcp_server.handle_for_test(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_skill",
                "arguments": {"qualified_name": "ghost/x"},
            },
        },
        project_root,
    )
    assert resp is not None
    result = resp["result"]
    assert result["isError"] is True


def test_no_manifest_returns_error(
    home: Path, project_root: Path
) -> None:
    resp = mcp_server.handle_for_test(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "list_skills", "arguments": {}},
        },
        project_root,
    )
    assert resp is not None
    assert resp["result"]["isError"] is True


def test_unknown_method(home: Path, project_root: Path) -> None:
    resp = mcp_server.handle_for_test(
        {"jsonrpc": "2.0", "id": 7, "method": "nope"},
        project_root,
    )
    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_notifications_initialized_returns_none(
    home: Path, project_root: Path
) -> None:
    resp = mcp_server.handle_for_test(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        project_root,
    )
    assert resp is None
