from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import init as init_mod
from agent_init.core import install, profiles, repos, rules
from tests.fixtures import git_fixtures


def test_save_and_load_round_trip(home: Path) -> None:
    p = profiles.Profile(name="x", template="default", mirrors=["CLAUDE.md"], rules=["a"])
    profiles.save(p)
    loaded = profiles.load("x")
    assert loaded == p


def test_invalid_name_rejected(home: Path) -> None:
    with pytest.raises(profiles.ProfileNameError):
        profiles.save(profiles.Profile(name="Bad Name"))


def test_load_missing(home: Path) -> None:
    with pytest.raises(profiles.ProfileNotFoundError):
        profiles.load("ghost")


def test_from_project_snapshots(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# foo\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("anth", f"file://{bare}")
    rules.add("be-concise", "Be concise.", is_default=True)
    init_mod.run(
        init_mod.InitOptions(
            project_root=project_root,
            mirrors=("CLAUDE.md",),
            agent_dialect="claude",
        )
    )
    install.install(project_root, "anth/foo")

    snap = profiles.from_project("python-tui", project_root)
    assert snap.name == "python-tui"
    assert "CLAUDE.md" in snap.mirrors
    assert "be-concise" in snap.rules
    assert snap.agent_dialect == "claude"
    assert [s.qualified_name for s in snap.skills] == ["anth/foo"]


def test_apply_reproduces_state(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    # Build a source project, snapshot it, apply to a new project.
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# foo\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("anth", f"file://{bare}")
    rules.add("be-concise", "Be concise.", is_default=True)
    init_mod.run(
        init_mod.InitOptions(
            project_root=project_root, mirrors=("CLAUDE.md",)
        )
    )
    install.install(project_root, "anth/foo")

    profiles.save(profiles.from_project("source", project_root))

    target = tmp_path / "target"
    profiles.apply("source", target)
    target_target = target / ".claude" / "skills" / "foo"
    assert (target_target / "SKILL.md").exists()
    assert (target / "CLAUDE.md").exists()
    from agent_init.core import manifest

    m = manifest.load(target)
    assert "be-concise" in m.rules


def test_list_and_delete(home: Path) -> None:
    profiles.save(profiles.Profile(name="a"))
    profiles.save(profiles.Profile(name="b"))
    names = [p.name for p in profiles.list_profiles()]
    assert names == ["a", "b"]
    assert profiles.delete("a") is True
    assert profiles.delete("a") is False
    assert [p.name for p in profiles.list_profiles()] == ["b"]
