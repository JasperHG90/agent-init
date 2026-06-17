"""Tests for the shared rule-repo overlay."""

from __future__ import annotations

from pathlib import Path

import pytest

from aim.core import rule_repos, rules
from tests.fixtures import git_fixtures


def _bare_rule_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    working = git_fixtures.make_source_repo(tmp_path / "src", files=files)
    return git_fixtures.make_bare_remote(working, tmp_path / "bare.git")


def test_add_lists_and_makes_rules_visible(home: Path, tmp_path: Path) -> None:
    bare = _bare_rule_repo(
        tmp_path,
        {
            "rules/team-style.md": "Team style guide.\n",
            "rules/be-direct.md": "Be direct.\n",
            "README.md": "hi\n",
        },
    )
    rule_repos.add("team", f"file://{bare}")
    listed = [r.alias for r in rule_repos.list_repos()]
    assert listed == ["team"]

    all_rules = rules.list_all()
    names = [r.name for r in all_rules]
    assert "team-style" in names
    assert "be-direct" in names
    overlay = next(r for r in all_rules if r.name == "team-style")
    assert overlay.source == "team"


def test_local_rule_shadows_overlay(home: Path, tmp_path: Path) -> None:
    bare = _bare_rule_repo(
        tmp_path,
        {"rules/be-concise.md": "Be concise. (overlay version)\n"},
    )
    rule_repos.add("team", f"file://{bare}")
    rules.add("be-concise", "Be concise. (local version)")
    resolved = rules.get("be-concise")
    assert resolved.source == "local"
    assert "local version" in resolved.body


def test_refresh_picks_up_new_overlay_rules(home: Path, tmp_path: Path) -> None:
    bare = _bare_rule_repo(tmp_path, {"rules/a.md": "a\n"})
    rule_repos.add("team", f"file://{bare}")
    assert {r.name for r in rules.list_all() if r.source == "team"} == {"a"}

    working = tmp_path / "src"
    git_fixtures.add_commit(working, {"rules/b.md": "b\n"}, "add b")
    git_fixtures.push_to_bare(working, bare)
    rule_repos.refresh("team")
    names = {r.name for r in rules.list_all() if r.source == "team"}
    assert names == {"a", "b"}


def test_remove_drops_overlay(home: Path, tmp_path: Path) -> None:
    bare = _bare_rule_repo(tmp_path, {"rules/a.md": "a\n"})
    rule_repos.add("team", f"file://{bare}")
    rule_repos.remove("team")
    assert rule_repos.list_repos() == []
    names = [r.name for r in rules.list_all()]
    assert "a" not in names


def test_remove_unknown_errors(home: Path) -> None:
    with pytest.raises(rule_repos.RuleRepoNotFoundError):
        rule_repos.remove("ghost")
