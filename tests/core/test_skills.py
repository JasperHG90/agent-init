from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import repos, skills
from tests.fixtures import git_fixtures


def _build_repo_with(
    tmp_path: Path,
    files: dict[str, str],
) -> tuple[Path, Path]:
    working = git_fixtures.make_source_repo(tmp_path / "src", files=files)
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    return working, bare


def test_discover_finds_canonical_skill(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(
        tmp_path,
        {
            "skills/code-review/SKILL.md": "# Code Review\n\nReview a PR carefully.\n",
            "README.md": "x\n",
        },
    )
    repos.add("anth", f"file://{bare}")
    rows = skills.list_skills()
    assert len(rows) == 1
    assert rows[0].qualified_name == "anth/code-review"
    assert rows[0].source_path == "skills/code-review"
    assert rows[0].title == "Code Review"
    assert rows[0].description and "Review a PR" in rows[0].description


def test_discover_supports_claude_path(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(
        tmp_path,
        {
            ".claude/skills/foo/SKILL.md": "# Foo\n",
            "README.md": "x\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = skills.list_skills()
    assert [r.qualified_name for r in rows] == ["a/foo"]
    assert rows[0].source_path == ".claude/skills/foo"


def test_discover_supports_root_path(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(
        tmp_path,
        {
            "rootskill/SKILL.md": "# Root Skill\n",
            "README.md": "x\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = skills.list_skills()
    assert [r.qualified_name for r in rows] == ["a/rootskill"]
    assert rows[0].source_path == "rootskill"


def test_precedence_skills_dir_wins(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(
        tmp_path,
        {
            "skills/dup/SKILL.md": "# canonical\n",
            ".claude/skills/dup/SKILL.md": "# shadow\n",
        },
    )
    repos.add("a", f"file://{bare}")
    rows = skills.list_skills()
    assert [r.qualified_name for r in rows] == ["a/dup"]
    assert rows[0].source_path == "skills/dup"
    # Re-run discover directly to inspect shadowed list.
    d = skills.discover("a")
    assert any(s.source_path == ".claude/skills/dup" for s in d.shadowed)


def test_empty_repo_registration_fails_and_rolls_back(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(tmp_path, {"README.md": "no skills here\n"})
    with pytest.raises(repos.RepoHasNoSkillsError):
        repos.add("empty", f"file://{bare}")
    # Roll-back: nothing left in DB or on disk.
    with pytest.raises(repos.RepoNotFoundError):
        repos.get("empty")
    assert not repos.clone_dir("empty").exists()


def test_allow_empty_registers_anyway(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(tmp_path, {"README.md": "x\n"})
    repos.add("ok", f"file://{bare}", allow_empty=True)
    assert repos.get("ok").alias == "ok"
    assert skills.list_skills("ok") == []


def test_search_matches_qualified_name(home: Path, tmp_path: Path) -> None:
    _, bare = _build_repo_with(
        tmp_path,
        {
            "skills/review/SKILL.md": "# Review\n",
            "skills/format/SKILL.md": "# Format\n",
        },
    )
    repos.add("a", f"file://{bare}")
    hits = skills.search("review")
    assert [r.qualified_name for r in hits] == ["a/review"]


def test_refresh_reindexes_when_sha_changes(
    home: Path, bare_remote: tuple[Path, Path]
) -> None:
    working, bare = bare_remote
    repos.add("anth", f"file://{bare}")
    initial = [r.qualified_name for r in skills.list_skills()]
    assert initial == ["anth/foo"]

    git_fixtures.add_commit(
        working,
        {"skills/bar/SKILL.md": "# bar\n"},
        "add bar skill",
    )
    git_fixtures.push_to_bare(working, bare)
    repos.refresh("anth")
    after = sorted(r.qualified_name for r in skills.list_skills())
    assert after == ["anth/bar", "anth/foo"]


def test_remove_clears_skill_index(home: Path, bare_remote: tuple[Path, Path]) -> None:
    _, bare = bare_remote
    repos.add("anth", f"file://{bare}")
    assert skills.list_skills("anth")
    repos.remove("anth")
    assert skills.list_skills("anth") == []
