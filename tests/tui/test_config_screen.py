"""Tests for the GLOBAL/PROJECT tabbed Config screen."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import init as init_mod
from agent_init.core import manifest, roots
from agent_init.tui.app import AgentInitApp
from agent_init.tui.screens.config_screen import ConfigScreen


@pytest.mark.asyncio
async def test_global_tab_shows_roots(home: Path, tmp_path: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    roots.add_root(proj)
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfigScreen())
        await pilot.pause()
        from textual.widgets import DataTable

        rt = app.screen.query_one("#roots-table", DataTable)
        assert rt.row_count == 1


@pytest.mark.asyncio
async def test_project_tab_shows_current_manifest(
    home: Path, project_root: Path
) -> None:
    init_mod.run(
        init_mod.InitOptions(
            project_root=project_root,
            mirrors=("CLAUDE.md",),
            agent_dialect="claude",
        )
    )
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfigScreen(project_root))
        await pilot.pause()
        from textual.widgets import Checkbox, Input

        assert app.screen.query_one("#proj-root", Input).value == str(project_root.resolve())
        assert app.screen.query_one("#proj-template", Input).value == "default"
        assert app.screen.query_one("#proj-mirror-CLAUDE-md", Checkbox).value is True
        assert app.screen.query_one("#proj-mirror-GEMINI-md", Checkbox).value is False
        assert app.screen.query_one("#proj-dialect", Input).value == "claude"


@pytest.mark.asyncio
async def test_project_save_writes_manifest(
    home: Path, project_root: Path
) -> None:
    app = AgentInitApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfigScreen(project_root))
        await pilot.pause()
        from textual.widgets import Button, Checkbox

        app.screen.query_one("#proj-mirror-GEMINI-md", Checkbox).value = True
        await pilot.pause()
        for btn in app.screen.query(Button):
            if btn.id == "proj-save":
                btn.press()
                break
        await pilot.pause()
        await pilot.pause()

    m = manifest.load(project_root)
    assert "GEMINI.md" in m.managed_files
    assert (project_root / "GEMINI.md").exists()
