from __future__ import annotations

from aim.tui.modals.repo_add import sanitize_repo_alias
from aim.tui.modals.rule_add import sanitize_rule_name


def test_rule_name_lowercases_and_replaces_spaces() -> None:
    assert sanitize_rule_name("Be Concise") == "be-concise"


def test_rule_name_strips_symbols() -> None:
    assert sanitize_rule_name("Test First!!!") == "test-first"


def test_rule_name_strips_leading_separators() -> None:
    assert sanitize_rule_name("__my rule") == "my-rule"


def test_rule_name_strips_trailing_separators() -> None:
    assert sanitize_rule_name("name---") == "name"


def test_rule_name_collapses_runs() -> None:
    assert sanitize_rule_name("a   b   c") == "a-b-c"


def test_rule_name_empty_input() -> None:
    assert sanitize_rule_name("   !!!   ") == ""


def test_rule_name_preserves_existing_lowercase() -> None:
    assert sanitize_rule_name("already-fine") == "already-fine"


def test_rule_name_unicode_collapses() -> None:
    assert sanitize_rule_name("Café Rules") == "caf-rules"


def test_repo_alias_same_rules() -> None:
    assert sanitize_repo_alias("Anthropic Skills") == "anthropic-skills"
    assert sanitize_repo_alias("My/Org-Repo") == "my-org-repo"
    assert sanitize_repo_alias("--leading") == "leading"
