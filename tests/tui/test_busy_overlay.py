"""The install loading overlay (BusyModal) shown while a worker thread runs."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import LoadingIndicator, Static

from aim.core import install as install_mod
from aim.core import repos
from aim.tui.app import AimApp
from aim.tui.modals.busy import BusyModal
from aim.tui.modals.skill_install import SkillInstallConfig
from aim.tui.screens.skills_screen import SkillsScreen
from tests.fixtures import git_fixtures


@pytest.mark.asyncio
async def test_busy_modal_renders_message_and_spinner(home: Path) -> None:
    app = AimApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(BusyModal("Installing a/foo…"))
        await pilot.pause()
        assert isinstance(app.screen, BusyModal)
        assert str(app.screen.query_one(Static).render()) == "Installing a/foo…"
        # The spinner is what tells the user work is in flight.
        assert app.screen.query(LoadingIndicator)


@pytest.mark.asyncio
async def test_skill_install_shows_then_clears_overlay(
    home: Path, project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# foo\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("a", f"file://{bare}")

    # Hold the install inside the worker so the overlay is observable mid-flight,
    # instead of racing a fast local install that finishes within a pause.
    entered = threading.Event()
    release = threading.Event()
    real_install = install_mod.install

    def blocking_install(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        release.wait(5)
        return real_install(*args, **kwargs)

    monkeypatch.setattr("aim.core.install.install", blocking_install)

    app = AimApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SkillsScreen()
        app.push_screen(screen)
        await pilot.pause()
        screen._install("a/foo", SkillInstallConfig(project_root=project_root))
        # Wait until the worker thread is inside the (blocked) install.
        for _ in range(200):
            if entered.is_set():
                break
            await pilot.pause()
        assert isinstance(app.screen, BusyModal), "overlay should be up during install"
        # Release the install and let the worker finish; the overlay must clear.
        release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not isinstance(app.screen, BusyModal)
        assert screen._busy is None

    # The install actually happened: the skill was deployed to disk.
    assert (project_root / ".claude" / "skills" / "foo" / "SKILL.md").exists()
