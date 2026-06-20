"""Startup modal: pick a layout profile when none is active.

Returns `(profile_name, remember_as_global_default)` or `None` if cancelled.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from aim.core import layout_profiles
from aim.tui.widgets import ToggleRow


class LayoutProfilePickerModal(ModalScreen[tuple[str, bool] | None]):
    """Modal that lets the user pick a layout profile at startup.

    Dismisses with ``(profile_name, remember_as_global_default)`` on
    confirm, or ``None`` if cancelled.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
    ]

    def __init__(self, project_root: Path) -> None:
        """Initialize the picker for the given project root.

        Args:
            project_root: Root directory whose available layout profiles are listed.
        """
        super().__init__()
        self._project_root = project_root
        self._profiles: list[layout_profiles.LayoutProfile] = []
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        """Build the modal layout."""
        yield Vertical(
            Static(
                "Choose a layout profile",
                classes="modal-title",
                markup=False,
            ),
            Static(
                "This determines where aim installs skills, rules, and symlinks.",
                markup=False,
            ),
            DataTable(id="profiles-table", cursor_type="row"),
            ToggleRow("Remember as global default", id="remember"),
            Static("", id="error", markup=False, classes="modal-error"),
            Horizontal(
                Button("Select", id="select", variant="primary"),
                Button("Cancel", id="cancel"),
                classes="modal-buttons",
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Set up the profiles table and populate it on mount."""
        table = self.query_one("#profiles-table", DataTable)
        table.add_columns("name", "scope", "skills", "rules", "subagents", "symlinks")
        self._populate()
        table.focus()

    def on_data_table_row_selected(self) -> None:
        """Confirm the selection when a table row is activated."""
        self._confirm()

    def on_data_table_cursor_moved(self, event) -> None:  # type: ignore[no-untyped-def]
        """Track the profile name under the cursor as the cursor moves.

        Args:
            event: Cursor-moved event carrying the target coordinate.
        """
        table = self.query_one("#profiles-table", DataTable)
        row_key, _ = table.coordinate_to_cell_key(event.coordinate)
        self._selected_name = str(row_key.value) if row_key and row_key.value is not None else None

    def _populate(self) -> None:
        """Load available profiles and render them as table rows."""
        table = self.query_one("#profiles-table", DataTable)
        table.clear()
        self._profiles = layout_profiles.list_profiles(self._project_root)
        for p in self._profiles:
            scope_label = _scope_label(p)
            table.add_row(
                p.display_name or p.name,
                scope_label,
                p.skills_dir,
                p.rules_dir,
                p.agents_md,
                ",".join(p.symlinks) if p.symlinks else "-",
                key=p.name,
            )
        if self._profiles:
            self._selected_name = self._profiles[0].name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Confirm on Select, otherwise dismiss the modal.

        Args:
            event: Button-pressed event identifying which button was clicked.
        """
        if event.button.id == "select":
            self._confirm()
        else:
            self.dismiss(None)

    def action_confirm(self) -> None:
        """Confirm the current selection."""
        self._confirm()

    def action_cancel(self) -> None:
        """Dismiss the modal without a selection."""
        self.dismiss(None)

    def _confirm(self) -> None:
        """Validate the selection and dismiss with the chosen profile.

        Shows an inline error and returns early when no profile is available
        or none is selected.
        """
        table = self.query_one("#profiles-table", DataTable)
        if table.row_count == 0:
            self.query_one("#error", Static).update("no profiles available")
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        name = str(row_key.value) if row_key and row_key.value is not None else None
        if name is None:
            self.query_one("#error", Static).update("select a profile first")
            return
        remember = self.query_one("#remember", ToggleRow).value
        self.dismiss((name, remember))


def _scope_label(profile: layout_profiles.LayoutProfile) -> str:
    """Return a human-readable scope label for a layout profile.

    Args:
        profile: Profile whose scope should be labelled.

    Returns:
        ``"built-in"`` for the bundled Claude/Gemini profiles, otherwise the
        profile's scope value.
    """
    if profile.name in (layout_profiles.BUILTIN_CLAUDE.name, layout_profiles.BUILTIN_GEMINI.name):
        return "built-in"
    return profile.scope.value
