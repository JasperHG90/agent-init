from __future__ import annotations

from pathlib import Path

import pytest

from aim.core import agent_files, content_guard, rules
from aim.core.models import Manifest


def test_add_writes_body_and_metadata(home: Path) -> None:
    r = rules.add("be-concise", "Be concise.", description="brevity", is_default=True)
    assert r.name == "be-concise"
    assert r.is_default is True
    assert rules.body_path("be-concise").read_text() == "Be concise."


def test_add_overwrites(home: Path) -> None:
    rules.add("r1", "first")
    rules.add("r1", "second", is_default=True)
    out = rules.get("r1")
    assert out.body == "second"
    assert out.is_default is True


def test_add_rejects_bad_name(home: Path) -> None:
    with pytest.raises(rules.RuleNameError):
        rules.add("Bad Name", "body")


def test_list_all_sorted(home: Path) -> None:
    rules.add("zeta", "z")
    rules.add("alpha", "a")
    rules.add("middle", "m")
    names = [r.name for r in rules.list_all()]
    assert names == ["alpha", "middle", "zeta"]


def test_list_defaults_filters(home: Path) -> None:
    rules.add("d1", "x", is_default=True)
    rules.add("d2", "y", is_default=False)
    names = [r.name for r in rules.list_defaults()]
    assert names == ["d1"]


def test_get_missing_raises(home: Path) -> None:
    with pytest.raises(rules.RuleNotFoundError):
        rules.get("ghost")


def test_set_default_toggles(home: Path) -> None:
    rules.add("toggleable", "body", is_default=False)
    rules.set_default("toggleable", is_default=True)
    assert rules.get("toggleable").is_default is True
    rules.set_default("toggleable", is_default=False)
    assert rules.get("toggleable").is_default is False


def test_delete_removes_both(home: Path) -> None:
    rules.add("deleteme", "body")
    rules.delete("deleteme")
    with pytest.raises(rules.RuleNotFoundError):
        rules.get("deleteme")
    assert not rules.body_path("deleteme").exists()


def test_apply_to_project_copies_body(home: Path, project_root: Path) -> None:
    rules.add("style", "Be terse.")
    rules.add("test", "Test first.")
    applied = rules.apply_to_project(project_root, ["style", "test"])
    assert [r.name for r in applied] == ["style", "test"]
    assert (project_root / ".claude" / "rules" / "style.md").read_text() == "Be terse."
    assert (project_root / ".claude" / "rules" / "test.md").read_text() == "Test first."


def test_apply_to_project_inline_skips_files(home: Path, project_root: Path) -> None:
    from aim.core import layout_profiles

    rules.add("style", "Be terse.")
    layout_profiles.save_project_profile(
        project_root,
        layout_profiles.LayoutProfile(
            name="inline",
            skills_dir=".claude/skills",
            rules_dir=".claude/rules",
            agents_dir=".claude/agents",
            agents_md="AGENTS.md",
            mcp_json=".mcp.json",
            rules_mode="inline",
        ),
    )
    applied = rules.apply_to_project(project_root, ["style"], rules_mode="inline")
    assert [r.name for r in applied] == ["style"]
    assert not (project_root / ".claude" / "rules" / "style.md").exists()


def test_add_rejects_hidden_unicode(home: Path) -> None:
    with pytest.raises(content_guard.HiddenUnicodeError):
        rules.add("bad", "behave​")
    assert not rules.body_path("bad").exists()


def test_apply_to_project_rejects_hidden_unicode(home: Path, project_root: Path) -> None:
    rules.add("clean", "safe body")
    rules.add("bad", "safe for now")
    # Bypass the library add() gate so we can test the project-write gate.
    rules.body_path("bad").write_text("bad​body")
    with pytest.raises(content_guard.HiddenUnicodeError):
        rules.apply_to_project(project_root, ["clean", "bad"])
    assert not (project_root / ".claude" / "rules" / "bad.md").exists()


def test_agents_md_renders_inline_rule_bodies(home: Path, project_root: Path) -> None:
    from aim.core import layout_profiles

    rules.add("style", "Be terse.")
    profile = layout_profiles.LayoutProfile(
        name="inline",
        skills_dir=".claude/skills",
        rules_dir=".claude/rules",
        agents_dir=".claude/agents",
        agents_md="AGENTS.md",
        mcp_json=".mcp.json",
        rules_mode="inline",
    )
    m = Manifest(rules=["style"])
    agent_files.write_agent_files(project_root, m, profile)
    text = (project_root / "AGENTS.md").read_text()
    assert "Be terse." in text
    assert not (project_root / ".claude" / "rules" / "style.md").exists()


def test_agents_md_renders_file_references(home: Path, project_root: Path) -> None:
    from aim.core import layout_profiles

    rules.add("style", "Be terse.")
    profile = layout_profiles.LayoutProfile(
        name="files",
        skills_dir=".claude/skills",
        rules_dir=".claude/rules",
        agents_dir=".claude/agents",
        agents_md="AGENTS.md",
        mcp_json=".mcp.json",
        rules_mode="files",
    )
    m = Manifest(rules=["style"])
    agent_files.write_agent_files(project_root, m, profile)
    text = (project_root / "AGENTS.md").read_text()
    assert ".claude/rules/style.md" in text
    assert "Be terse." not in text
