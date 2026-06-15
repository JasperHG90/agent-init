"""Smoke tests that actually OPEN every modal from every screen.

Without these the original suite missed a `BadIdentifier: 'mirror-CLAUDE.md'` —
filenames contain dots and Textual ids can't. Each test here drives the key
that pops a modal and asserts the modal's class is on top of the screen stack.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import repos, rules
from agent_init.tui.app import AgentInitApp
from agent_init.tui.modals.confirm import ConfirmModal
from agent_init.tui.modals.init_modal import InitModal
from agent_init.tui.modals.repo_add import RepoAddModal
from agent_init.tui.modals.rule_add import RuleAddModal
from agent_init.tui.modals.skill_install import SkillInstallModal
from tests.fixtures import git_fixtures


def _bare_with_skills(tmp_path: Path) -> Path:
    working = git_fixtures.make_source_repo(
        tmp_path / "src",
        files={
            "skills/foo/SKILL.md": "# foo\n",
            "skills/bar/SKILL.md": "# bar\n",
        },
    )
    return git_fixtures.make_bare_remote(working, tmp_path / "bare.git")


@pytest.mark.asyncio
async def test_main_screen_opens_init_modal(home: Path) -> None:
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, InitModal)


@pytest.mark.asyncio
async def test_repos_screen_opens_add_modal(home: Path) -> None:
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, RepoAddModal)


@pytest.mark.asyncio
async def test_repos_screen_remove_opens_confirm(home: Path, tmp_path: Path) -> None:
    bare = _bare_with_skills(tmp_path)
    repos.add("anth", f"file://{bare}")
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_rules_screen_opens_add_modal(home: Path) -> None:
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, RuleAddModal)


@pytest.mark.asyncio
async def test_rules_screen_edit_opens_modal(home: Path) -> None:
    rules.add("existing", "body", is_default=True)
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, RuleAddModal)


@pytest.mark.asyncio
async def test_rules_screen_delete_opens_confirm(home: Path) -> None:
    rules.add("doomed", "body")
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_skills_screen_install_opens_modal(home: Path, tmp_path: Path) -> None:
    bare = _bare_with_skills(tmp_path)
    repos.add("anth", f"file://{bare}")
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, SkillInstallModal)


@pytest.mark.asyncio
async def test_init_modal_submits_with_selected_mirrors(
    home: Path, project_root: Path
) -> None:
    """End-to-end: open init modal, tick a mirror checkbox, submit, verify file."""
    rules.add("focus", "Focus.", is_default=True)
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, InitModal)

        from textual.widgets import Checkbox, Input

        modal.query_one("#project-root", Input).value = str(project_root)
        modal.query_one(f"#{InitModal._mirror_id('CLAUDE.md')}", Checkbox).value = True
        await pilot.pause()
        # Click the Initialize button.
        from textual.widgets import Button

        for btn in modal.query(Button):
            if btn.id == "go":
                btn.press()
                break
        await pilot.pause()
        await pilot.pause()

    assert (project_root / "AGENTS.md").exists()
    assert (project_root / "CLAUDE.md").exists()
    assert not (project_root / "GEMINI.md").exists()


@pytest.mark.asyncio
async def test_repo_add_modal_creates_repo(
    home: Path, tmp_path: Path
) -> None:
    bare = _bare_with_skills(tmp_path)
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, RepoAddModal)
        from textual.widgets import Button, Input

        modal.query_one("#alias", Input).value = "demo"
        modal.query_one("#url", Input).value = f"file://{bare}"
        await pilot.pause()
        for btn in modal.query(Button):
            if btn.id == "add":
                btn.press()
                break
        await pilot.pause()

    assert repos.get("demo").alias == "demo"


@pytest.mark.asyncio
async def test_rule_add_modal_creates_rule(home: Path) -> None:
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, RuleAddModal)
        from textual.widgets import Button, Checkbox, Input, TextArea

        modal.query_one("#name", Input).value = "from-tui"
        modal.query_one("#body", TextArea).text = "Body from the TUI."
        modal.query_one("#default", Checkbox).value = True
        await pilot.pause()
        for btn in modal.query(Button):
            if btn.id == "save":
                btn.press()
                break
        await pilot.pause()

    saved = rules.get("from-tui")
    assert saved.body == "Body from the TUI."
    assert saved.is_default is True
