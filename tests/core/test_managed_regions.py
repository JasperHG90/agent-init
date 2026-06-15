"""Tests for the generalised managed-region engine.

HTML dialect parity is already exercised via `test_agents_md.py`; this file
focuses on the hash dialect and the auto-dispatch by filename.
"""

from __future__ import annotations

from agent_init.core import managed_regions as mr


def test_hash_dialect_round_trip() -> None:
    body = (
        "# pre-commit config\n\n"
        "# BEGIN agent-init: hooks\n"
        "repos:\n  - repo: ...\n"
        "# END agent-init: hooks\n\n"
        "# user-added section\n"
    )
    regions = mr.parse(body, mr.HASH_DIALECT)
    assert [r.name for r in regions] == ["hooks"]
    assert "repos:" in regions[0].body

    merged = mr.merge(body, {"hooks": "repos:\n  - repo: changed\n"}, mr.HASH_DIALECT)
    assert "repos:\n  - repo: changed" in merged
    assert "# user-added section" in merged  # preserved


def test_hash_dialect_unbalanced_raises() -> None:
    bad = "# BEGIN agent-init: x\nbody\n"
    import pytest

    with pytest.raises(mr.RegionError):
        mr.parse(bad, mr.HASH_DIALECT)


def test_for_filename_picks_html() -> None:
    assert mr.for_filename("AGENTS.md") is mr.HTML_DIALECT
    assert mr.for_filename("foo.html") is mr.HTML_DIALECT


def test_for_filename_picks_hash() -> None:
    assert mr.for_filename(".editorconfig") is mr.HASH_DIALECT
    assert mr.for_filename("pyproject.toml") is mr.HASH_DIALECT
    assert mr.for_filename(".gitignore") is mr.HASH_DIALECT


def test_build_from_scratch_hash() -> None:
    out = mr.build([("a", "x")], mr.HASH_DIALECT)
    assert "# BEGIN agent-init: a" in out
    assert "x" in out
    assert "# END agent-init: a" in out


def test_html_round_trip_via_module() -> None:
    """Sanity: the HTML dialect through this module matches agents_md."""
    text = "<!-- BEGIN agent-init: a -->\nfoo\n<!-- END agent-init: a -->\n"
    out = mr.merge(text, {"a": "bar"}, mr.HTML_DIALECT)
    assert "bar" in out
    assert "foo" not in out
