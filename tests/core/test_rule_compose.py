"""Tests for rule front-matter parsing and transitive composition."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import init as init_mod
from agent_init.core import rule_compose, rules


def test_no_front_matter_is_default_order() -> None:
    meta = rule_compose.parse_front_matter("Just a body.\n")
    assert meta.extends == ()
    assert meta.order == rule_compose.DEFAULT_ORDER
    assert meta.body_without_frontmatter == "Just a body.\n"


def test_parses_extends_list_and_order() -> None:
    body = "---\nextends: [a, b, c]\norder: 5\n---\nbody\n"
    meta = rule_compose.parse_front_matter(body)
    assert meta.extends == ("a", "b", "c")
    assert meta.order == 5
    assert meta.body_without_frontmatter == "body\n"


def test_parses_quoted_names() -> None:
    body = "---\nextends: ['quoted-one', \"quoted-two\"]\n---\nbody\n"
    meta = rule_compose.parse_front_matter(body)
    assert meta.extends == ("quoted-one", "quoted-two")


def test_resolve_expands_transitively(home: Path) -> None:
    rules.add("a", "---\nextends: [b]\norder: 50\n---\nbody-a\n")
    rules.add("b", "---\nextends: [c]\norder: 30\n---\nbody-b\n")
    rules.add("c", "---\norder: 10\n---\nbody-c\n")

    resolved = rule_compose.resolve(["a"], lambda n: rules.get(n).body)
    # c before b before a (by order)
    assert resolved == ["c", "b", "a"]


def test_resolve_detects_cycle(home: Path) -> None:
    rules.add("x", "---\nextends: [y]\n---\nx\n")
    rules.add("y", "---\nextends: [x]\n---\ny\n")
    with pytest.raises(rule_compose.RuleCycleError):
        rule_compose.resolve(["x"], lambda n: rules.get(n).body)


def test_init_includes_transitively_extended_rules(
    home: Path, project_root: Path
) -> None:
    rules.add("parent", "---\norder: 10\n---\nParent body.\n", is_default=False)
    rules.add(
        "child",
        "---\nextends: [parent]\norder: 20\n---\nChild body.\n",
        is_default=True,
    )
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    text = (project_root / "AGENTS.md").read_text()
    assert "Parent body." in text
    assert "Child body." in text
    # parent should appear before child (lower order):
    assert text.index("Parent body.") < text.index("Child body.")
