"""Tests for the user-requested round of changes:

1. Mirror union on re-init (existing mirrors don't silently disappear).
2. `rules.install_to_project` adds rule to manifest + re-renders AGENTS.md.
3. Per-project `agent_dialect` round-trips through the manifest.
4. `re.fullmatch` rejects trailing-newline names (adversarial finding #15).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atm.core import init as init_mod
from atm.core import manifest, repos, rules

# ---------- 1. Mirror union ----------


def test_re_init_preserves_existing_mirrors_when_none_specified(
    home: Path, project_root: Path
) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=("CLAUDE.md",)))
    assert (project_root / "CLAUDE.md").exists()

    # Re-init with no mirror flag — CLAUDE.md must still be there afterwards.
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    assert (project_root / "CLAUDE.md").exists()
    m = manifest.load(project_root)
    assert "CLAUDE.md" in m.managed_files


def test_re_init_unions_new_with_existing(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=("CLAUDE.md",)))
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=("GEMINI.md",)))
    m = manifest.load(project_root)
    assert "CLAUDE.md" in m.managed_files
    assert "GEMINI.md" in m.managed_files


def test_re_init_clear_mirrors_wipes(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=("CLAUDE.md",)))
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=(), clear_mirrors=True))
    m = manifest.load(project_root)
    assert m.managed_files == ["AGENTS.md"]


# ---------- 2. Rule install flow ----------


def test_rule_install_adds_to_manifest_and_renders(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    rules.add("be-concise", "Be concise.")

    rules.install_to_project(project_root, "be-concise")
    m = manifest.load(project_root)
    assert "be-concise" in m.rules
    agents_md = (project_root / "AGENTS.md").read_text()
    assert "Be concise." in agents_md


def test_rule_install_preserves_mirrors(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, mirrors=("CLAUDE.md",)))
    rules.add("focus", "Focus.")
    rules.install_to_project(project_root, "focus")

    assert (project_root / "CLAUDE.md").exists()
    assert "Focus." in (project_root / "CLAUDE.md").read_text()


def test_rule_install_unknown_errors(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    with pytest.raises(rules.RuleNotFoundError):
        rules.install_to_project(project_root, "ghost")


# ---------- 3. Agent dialect ----------


def test_agent_dialect_stored_in_manifest(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, agent_dialect="claude"))
    m = manifest.load(project_root)
    assert m.agent_dialect == "claude"


def test_agent_dialect_preserved_on_reinit_when_none_passed(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root, agent_dialect="claude"))
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    m = manifest.load(project_root)
    assert m.agent_dialect == "claude"


# ---------- 4. fullmatch trailing-newline ----------


def test_rule_name_rejects_trailing_newline(home: Path) -> None:
    with pytest.raises(rules.RuleNameError):
        rules.add("ok\n", "body")


def test_repo_alias_rejects_trailing_newline(home: Path, tmp_path: Path) -> None:
    from tests.fixtures import git_fixtures

    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# foo\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    with pytest.raises(repos.RepoAliasError):
        repos.add("anth\n", f"file://{bare}")
