from __future__ import annotations

from pathlib import Path

import pytest

from aim.core import rules


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
