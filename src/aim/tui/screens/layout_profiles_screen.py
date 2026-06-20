"""Layout profiles screen — list, add, edit, delete, and activate profiles."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Static

from aim.core import layout_profiles, manifest
from aim.tui.modals.confirm import ConfirmModal
from aim.tui.modals.layout_profile_modal import (
    LayoutProfileModal,
    LayoutProfileResult,
)


class LayoutProfilesScreen(Screen[None]):
    """Screen to list, add, edit, delete, and activate layout profiles."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("b", "app.pop_screen", "Back"),
        ("a", "add_profile", "Add"),
        ("e", "edit_profile", "Edit"),
        ("x", "delete_profile", "Delete"),
        ("s", "set_active", "Set active"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the screen, resolving the project root.

        Args:
            project_root: Project directory; defaults to the current working directory.
        """
        super().__init__()
        self._project_root = (project_root or Path.cwd()).resolve()

    def compose(self) -> ComposeResult:
        """Build the screen's widget tree."""
        yield Static("Profiles", id="title", markup=False)
        yield Static(
            "project = repo-only · global = DB cache + read-only repo copy",
            id="scope-help",
            markup=False,
        )
        yield DataTable(id="profiles-table", cursor_type="row")
        yield Static("", id="status", markup=False)
        yield Static(
            "[a] Add  [e] Edit  [x] Delete  [s] Set active  [b] Back  [q] Quit",
            id="hint",
            markup=False,
        )

    def on_mount(self) -> None:
        """Set up the table columns and populate rows on first display."""
        table = self.query_one("#profiles-table", DataTable)
        table.add_columns(
            "active", "name", "scope", "skills_dir", "rules_dir", "subagents_md", "symlinks"
        )
        self._refresh()
        table.focus()

    def on_screen_resume(self) -> None:
        """Refresh the profile list when the screen regains focus."""
        self._refresh()

    def _active_name(self) -> str | None:
        """Return the active profile name from the manifest, or None if unset.

        Returns:
            The active layout profile name, or None when no manifest exists.
        """
        try:
            m = manifest.load(self._project_root)
            return m.layout_profile
        except manifest.ManifestNotFoundError:
            return None

    def _selected_name(self) -> str | None:
        """Return the name of the profile under the cursor, or None if empty.

        Returns:
            The selected profile name, or None when the table has no rows.
        """
        table = self.query_one("#profiles-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key and row_key.value is not None else None

    def _refresh(self) -> None:
        """Sync profiles and repopulate the table, preserving the selection."""
        report = layout_profiles.sync_profiles(self._project_root)
        for warning in report.warnings:
            self.app.notify(warning, severity="warning")

        active = self._active_name()
        profiles = layout_profiles.list_profiles(self._project_root)
        table = self.query_one("#profiles-table", DataTable)
        selected = self._selected_name()
        table.clear()
        for p in profiles:
            is_active = ">" if p.name == active else ""
            scope = _scope_label(p)
            table.add_row(
                is_active,
                p.display_name or p.name,
                scope,
                p.skills_dir,
                p.rules_dir,
                p.agents_md,
                ",".join(p.symlinks) if p.symlinks else "-",
                key=p.name,
            )
        if selected is not None:
            try:
                table.move_cursor(row=table.get_row_index(selected), animate=False)
            except Exception:
                pass
        self._status(f"{len(profiles)} profile(s)")

    def action_add_profile(self) -> None:
        """Open the modal to create a new layout profile."""
        self.app.push_screen(
            LayoutProfileModal(self._project_root),
            self._on_save,
        )

    def action_edit_profile(self) -> None:
        """Open the modal to edit the selected layout profile."""
        name = self._selected_name()
        if name is None:
            self._status("select a profile to edit")
            return
        try:
            profile = layout_profiles.get_profile(self._project_root, name)
        except layout_profiles.LayoutProfileNotFoundError:
            self._status(f"profile {name!r} not found")
            return
        self.app.push_screen(
            LayoutProfileModal(self._project_root, profile=profile),
            self._on_save,
        )

    def _on_save(self, result: LayoutProfileResult | None) -> None:
        """Persist a saved profile and refresh the table.

        Args:
            result: Outcome from the profile modal, or None when cancelled.
        """
        if result is None:
            return
        try:
            if result.profile.scope == layout_profiles.LayoutProfileScope.GLOBAL:
                layout_profiles.save_global_profile(self._project_root, result.profile)
            else:
                layout_profiles.save_project_profile(self._project_root, result.profile)
        except Exception as exc:
            self.app.notify(f"save failed: {exc}", severity="error")
            return
        # Rename: remove the old profile if the name changed.
        if result.original_name is not None and result.original_name != result.profile.name:
            layout_profiles.delete_global_profile(self._project_root, result.original_name)
        self.app.notify(f"saved profile {result.profile.name}")
        self._refresh()

    def action_delete_profile(self) -> None:
        """Confirm and delete the selected profile, refusing built-ins."""
        name = self._selected_name()
        if name is None:
            self._status("select a profile to delete")
            return
        if name in (
            layout_profiles.BUILTIN_CLAUDE.name,
            layout_profiles.BUILTIN_GEMINI.name,
        ):
            self.app.notify("built-in profiles cannot be deleted", severity="error")
            return

        def _on_confirm(yes: bool | None) -> None:
            """Delete the profile if confirmed, clearing it from the manifest.

            Args:
                yes: Confirmation result; deletes only when True.
            """
            if yes is not True:
                return
            deleted = layout_profiles.delete_global_profile(self._project_root, name)
            if not deleted:
                self.app.notify(f"profile {name!r} not found", severity="error")
                return
            # If this was the active project profile, clear it from the manifest.
            try:
                m = manifest.load(self._project_root)
            except manifest.ManifestNotFoundError:
                m = None
            if m is not None and m.layout_profile == name:
                m.layout_profile = None
                manifest.save(self._project_root, m)
            self.app.notify(f"deleted profile {name!r}")
            self._refresh()

        self.app.push_screen(ConfirmModal(f"Delete layout profile {name!r}?"), _on_confirm)

    def action_set_active(self) -> None:
        """Activate the selected profile and refresh the table."""
        name = self._selected_name()
        if name is None:
            self._status("select a profile to activate")
            return
        try:
            layout_profiles.set_active(self._project_root, name)
        except Exception as exc:
            self.app.notify(f"activation failed: {exc}", severity="error")
            return
        self.app.notify(f"active layout profile: {name}")
        self._refresh()

    def _status(self, msg: str) -> None:
        """Update the status line with the given message."""
        self.query_one("#status", Static).update(msg)


def _scope_label(profile: layout_profiles.LayoutProfile) -> str:
    """Return the display label for a profile's scope.

    Args:
        profile: The layout profile to label.

    Returns:
        "built-in" for built-in profiles, otherwise the scope value.
    """
    if profile.name in (layout_profiles.BUILTIN_CLAUDE.name, layout_profiles.BUILTIN_GEMINI.name):
        return "built-in"
    return profile.scope.value
