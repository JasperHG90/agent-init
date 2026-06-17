"""TUI tests for the startup layout-profile picker."""

from __future__ import annotations

from pathlib import Path

import pytest

from aim.core import layout_profiles, manifest
from aim.tui.app import AimApp
from aim.tui.modals.layout_profile_picker_modal import (
    LayoutProfilePickerModal,
)
from aim.tui.screens.main_screen import MainScreen


@pytest.mark.asyncio
async def test_picker_opens_without_global_default(home: Path, project_root: Path) -> None:
    layout_profiles.set_global_default(None)
    app = AimApp(project_root=project_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LayoutProfilePickerModal)


@pytest.mark.asyncio
async def test_picker_selects_profile(home: Path, project_root: Path) -> None:
    layout_profiles.set_global_default(None)
    app = AimApp(project_root=project_root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LayoutProfilePickerModal)
        # Built-ins come first: claude then gemini.
        await pilot.press("down", "enter")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

    m = manifest.load(project_root)
    assert m.layout_profile == "gemini"
