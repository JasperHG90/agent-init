from __future__ import annotations

from pathlib import Path

import pytest

from aim.core import agents, repos
from tests.fixtures import git_fixtures


def _build_repo_with(tmp_path: Path, files: dict[str, str]) -> Path:
    working = git_fixtures.make_source_repo(tmp_path / "src", files=files)
    return git_fixtures.make_bare_remote(working, tmp_path / "bare.git")


def test_discover_finds_canonical_agent(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {
            "agents/review/AGENT.md": "---\nname: Review\ndescription: Review a PR\ntools: [git, github]\nmodel: claude-sonnet-4-6\n---\n# Review\n",
            "README.md": "x\n",
        },
    )
    repos.add("anth", f"file://{bare}")
    rows = agents.list_agents()
    assert len(rows) == 1
    assert rows[0].qualified_name == "anth/review"
    assert rows[0].title == "Review"
    assert "Review a PR" in (rows[0].description or "")
    assert rows[0].tools == "git,github"
    assert rows[0].model == "claude-sonnet-4-6"


def test_discover_supports_claude_path(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {
            ".claude/agents/foo/AGENT.md": "---\nname: Foo\n---\n# Foo\n",
            "README.md": "x\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = agents.list_agents()
    assert [r.qualified_name for r in rows] == ["a/foo"]
    assert rows[0].source_path == ".claude/agents/foo"


def test_discover_supports_nested_agents_dir(home: Path, tmp_path: Path) -> None:
    """Agents may be grouped under sub-categories: agents/<category>/<name>/AGENT.md."""
    bare = _build_repo_with(
        tmp_path,
        {
            "agents/review/code/AGENT.md": "---\nname: code-review\n---\n# CR\n",
            "agents/data/scout.md": "---\nname: scout\n---\n# scout\n",
            "README.md": "x\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = agents.list_agents()
    names = {r.qualified_name for r in rows}
    assert names == {"a/code", "a/scout"}
    paths = {r.qualified_name: r.source_path for r in rows}
    assert paths["a/code"] == "agents/review/code"
    assert paths["a/scout"] == "agents/data/scout.md"


def test_discover_supports_plugin_agents_dir(home: Path, tmp_path: Path) -> None:
    """Repos like wshobson/agents group agents under plugins/<cat>/agents/<name>."""
    bare = _build_repo_with(
        tmp_path,
        {
            "plugins/business-analytics/agents/python-pro/AGENT.md": (
                "---\nname: Python Pro\ndescription: Advanced Python agent.\n---\n# Python Pro\n"
            ),
            "plugins/business-analytics/agents/scout.md": "---\nname: Scout\n---\n# Scout\n",
            "README.md": "x\n",
        },
    )
    repos.add("wshobson", f"file://{bare}")
    rows = agents.list_agents()
    names = {r.qualified_name for r in rows}
    assert names == {"wshobson/python-pro", "wshobson/scout"}
    paths = {r.qualified_name: r.source_path for r in rows}
    assert paths["wshobson/python-pro"] == "plugins/business-analytics/agents/python-pro"
    assert paths["wshobson/scout"] == "plugins/business-analytics/agents/scout.md"


def test_precedence_agents_dir_wins(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {
            "agents/dup/AGENT.md": "---\nname: canonical\n---\n# canonical\n",
            ".claude/agents/dup/AGENT.md": "---\nname: shadow\n---\n# shadow\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = agents.list_agents()
    assert [r.qualified_name for r in rows] == ["a/dup"]
    assert rows[0].source_path == "agents/dup"


def test_precedence_canonical_wins_over_plugin_agent(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {
            "agents/dup/AGENT.md": "---\nname: canonical\n---\n# canonical\n",
            "plugins/cat/agents/dup/AGENT.md": "---\nname: plugin shadow\n---\n# plugin shadow\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = agents.list_agents()
    assert [r.qualified_name for r in rows] == ["a/dup"]
    assert rows[0].source_path == "agents/dup"
    d = agents.discover("a")
    assert any(s.source_path == "plugins/cat/agents/dup" for s in d.shadowed)


def test_empty_repo_registration_allows_agent_only(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(tmp_path, {"agents/x/AGENT.md": "# X\n", "README.md": "x\n"})
    repos.add("agent-only", f"file://{bare}")
    assert [r.qualified_name for r in agents.list_agents()] == ["agent-only/x"]


def test_search_matches_qualified_name(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {
            "agents/review/AGENT.md": "# Review\n",
            "agents/format/AGENT.md": "# Format\n",
        },
    )
    repos.add("a", f"file://{bare}")
    assert [r.qualified_name for r in agents.search("format")] == ["a/format"]


def test_read_agent_content(home: Path, tmp_path: Path) -> None:
    bare = _build_repo_with(
        tmp_path,
        {"agents/b/AGENT.md": "---\nname: B\n---\n# B body\n"},
    )
    repos.add("a", f"file://{bare}")
    content = agents.read_agent_content("a/b")
    assert "# B body" in content


def test_read_agent_content_missing_raises(home: Path) -> None:
    with pytest.raises(agents.AgentNotIndexedError):
        agents.read_agent_content("a/missing")
