"""Tests for the generalised managed-region engine.

HTML dialect parity is already exercised via `test_agents_md.py`; this file
focuses on the hash dialect and the auto-dispatch by filename.
"""

from __future__ import annotations

from aim.core import managed_regions as mr


def test_hash_dialect_round_trip() -> None:
    body = (
        "# pre-commit config\n\n"
        "# BEGIN aim: hooks\n"
        "repos:\n  - repo: ...\n"
        "# END aim: hooks\n\n"
        "# user-added section\n"
    )
    regions = mr.parse(body, mr.HASH_DIALECT)
    assert [r.name for r in regions] == ["hooks"]
    assert "repos:" in regions[0].body

    merged = mr.merge(body, {"hooks": "repos:\n  - repo: changed\n"}, mr.HASH_DIALECT)
    assert "repos:\n  - repo: changed" in merged
    assert "# user-added section" in merged  # preserved


def test_hash_dialect_unbalanced_raises() -> None:
    bad = "# BEGIN aim: x\nbody\n"
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
    assert "# BEGIN aim: a" in out
    assert "x" in out
    assert "# END aim: a" in out


def test_html_round_trip_via_module() -> None:
    """Sanity: the HTML dialect through this module matches agents_md."""
    text = "<!-- BEGIN aim: a -->\nfoo\n<!-- END aim: a -->\n"
    out = mr.merge(text, {"a": "bar"}, mr.HTML_DIALECT)
    assert "bar" in out
    assert "foo" not in out
