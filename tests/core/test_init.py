from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import init as init_mod
from agent_init.core import manifest, rules


def test_first_init_creates_agents_md_and_manifest(home: Path, project_root: Path) -> None:
    rules.add("focus", "Focus on simplicity.", is_default=True)
    result = init_mod.run(init_mod.InitOptions(project_root=project_root))
    assert result.re_init is False
    assert result.agents_md_path.exists()
    contents = result.agents_md_path.read_text()
    assert "Focus on simplicity." in contents
    assert "BEGIN agent-init: header" in contents
    assert "BEGIN agent-init: rules" in contents
    m = manifest.load(project_root)
    assert m.rules == ["focus"]
    assert "AGENTS.md" in m.managed_files


def test_first_init_no_mirrors_by_default(home: Path, project_root: Path) -> None:
    """Default is opt-in: no CLAUDE.md / GEMINI.md unless requested."""
    result = init_mod.run(init_mod.InitOptions(project_root=project_root))
    assert result.mirror_paths == []
    assert not (project_root / "CLAUDE.md").exists()
    assert not (project_root / "GEMINI.md").exists()


def test_first_init_writes_only_selected_mirrors(home: Path, project_root: Path) -> None:
    result = init_mod.run(
        init_mod.InitOptions(project_root=project_root, mirrors=("CLAUDE.md",))
    )
    mirror_names = {p.name for p in result.mirror_paths}
    assert mirror_names == {"CLAUDE.md"}
    assert not (project_root / "GEMINI.md").exists()
    agents_text = result.agents_md_path.read_text()
    assert (project_root / "CLAUDE.md").read_text() == agents_text


def test_re_init_preserves_user_content_outside_regions(home: Path, project_root: Path) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    agents_path = project_root / "AGENTS.md"
    text = agents_path.read_text() + "\n## Hand-added section\n\nUser content.\n"
    agents_path.write_text(text)

    rules.add("new-rule", "Be exact.", is_default=True)
    init_mod.run(init_mod.InitOptions(project_root=project_root))

    updated = agents_path.read_text()
    assert "## Hand-added section" in updated
    assert "User content." in updated
    assert "Be exact." in updated


def test_re_init_updates_managed_region(home: Path, project_root: Path) -> None:
    rules.add("first", "First rule.", is_default=True)
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    assert "First rule." in (project_root / "AGENTS.md").read_text()

    rules.add("second", "Second rule.", is_default=True)
    init_mod.run(init_mod.InitOptions(project_root=project_root))
    text = (project_root / "AGENTS.md").read_text()
    assert "First rule." in text
    assert "Second rule." in text


def test_init_with_no_mirror(home: Path, project_root: Path) -> None:
    result = init_mod.run(
        init_mod.InitOptions(project_root=project_root, mirrors=tuple())
    )
    assert result.mirror_paths == []
    assert not (project_root / "CLAUDE.md").exists()


def test_init_with_no_default_rules(home: Path, project_root: Path) -> None:
    rules.add("would-be-default", "body", is_default=True)
    result = init_mod.run(
        init_mod.InitOptions(project_root=project_root, seed_default_rules=False)
    )
    assert result.applied_rules == []
    m = manifest.load(project_root)
    assert m.rules == []


def test_init_seeds_rule_from_file(home: Path, project_root: Path) -> None:
    rule_file = home / "my-rule.md"
    rule_file.write_text("# My rule\n\nAlways add tests.\n")
    result = init_mod.run(
        init_mod.InitOptions(
            project_root=project_root,
            extra_rule_files={"my-rule": rule_file},
        )
    )
    assert "my-rule" in result.applied_rules
    assert "Always add tests." in result.agents_md_path.read_text()
    # Rule is stored in the global library so re-init works without --rule-file.
    m = manifest.load(project_root)
    assert "my-rule" in m.rules
    assert rules.get("my-rule").body == "# My rule\n\nAlways add tests.\n"


def test_init_rejects_invalid_rule_file_name(home: Path, project_root: Path) -> None:
    rule_file = home / "bad rule.md"
    rule_file.write_text("# Bad\n")
    with pytest.raises(rules.RuleNameError):
        init_mod.run(
            init_mod.InitOptions(
                project_root=project_root,
                extra_rule_files={"bad rule": rule_file},
            )
        )


