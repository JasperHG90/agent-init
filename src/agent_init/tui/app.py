"""Textual app shell. The TUI is a thin layer over `core/`; everything here
should route through the core API so CLI and TUI stay in sync.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from agent_init.tui.modals.palette import (
    PaletteEntry,
    PaletteModal,
    build_entries,
)
from agent_init.tui.screens.main_screen import MainScreen


class AgentInitApp(App[None]):
    """Top-level Textual app."""

    TITLE = "agent-init"
    SUB_TITLE = "scaffold and manage agent-engineering projects"
    CSS_PATH = "app.tcss"

    # NOTE: action name is `open_palette` (not `command_palette`) to avoid
    # collision with Textual's built-in app command palette.
    BINDINGS = [
        ("q", "quit", "Quit"),
        Binding("ctrl+p", "open_palette", "Palette", priority=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())

    def action_open_palette(self) -> None:
        entries = build_entries(self)
        self.push_screen(PaletteModal(entries), self._on_palette)

    def _on_palette(self, entry: PaletteEntry | None) -> None:
        if entry is None:
            return
        entry.handler()


def run() -> None:
    AgentInitApp().run()
