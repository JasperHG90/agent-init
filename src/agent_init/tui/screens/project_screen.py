"""Project view: installed skills, drift detection, update/rollback/delete."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Static

from agent_init.core import git, hashing, install, manifest, paths
from agent_init.tui.modals.confirm import ConfirmModal


class ProjectScreen(Screen[None]):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("b", "app.pop_screen", "Back"),
        ("u", "update_current", "Update"),
        ("r", "rollback_current", "Rollback"),
        ("x", "delete_current", "Delete"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, project_root: Path | None = None) -> None:
        super().__init__()
        self._project_root = project_root or Path.cwd()
        self.last_status: str = ""
        self._has_manifest: bool = False

    def compose(self) -> ComposeResult:
        manifest_path = paths.project_manifest_path(self._project_root)
        yield Static(
            f"Project: {self._project_root}    ·    manifest: {manifest_path}",
            id="title",
            markup=False,
        )
        yield DataTable(id="project-table", cursor_type="row")
        yield Static("", id="status", markup=False)
        yield Static(
            "[u] Update  [r] Rollback  [x] Delete  [b] Back  [q] Quit",
            id="hint",
            markup=False,
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("skill", "version", "target", "drift")
        self._populate()
        table.focus()

    def on_screen_resume(self) -> None:
        self._populate()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        try:
            m = manifest.load(self._project_root)
            self._has_manifest = True
        except manifest.ManifestNotFoundError:
            self._has_manifest = False
            self._status("no .agent-init/manifest.json — run init from the main menu")
            return
        dialect = f" · agent: {m.agent_dialect}" if m.agent_dialect else ""
        if not m.skills:
            self._status(f"no skills installed in this project{dialect}")
            return
        for s in m.skills:
            target = self._project_root / s.target_dir
            if s.content_hash is None:
                drift = "(no hash)"
            elif not target.exists():
                drift = "missing"
            else:
                current = hashing.hash_tree(target)
                drift = "clean" if current == s.content_hash else "edited"
            table.add_row(
                s.qualified_name,
                s.current.identifier(),
                s.target_dir,
                drift,
                key=s.qualified_name,
            )
        self._status(f"{len(m.skills)} installed skill(s){dialect}")

    def _selected(self) -> str | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key and row_key.value is not None else None

    def _guard(self) -> str | None:
        """Return the selected qualified_name, or None after notifying about
        WHY there is nothing actionable (no manifest / no skills / no row)."""
        if not self._has_manifest:
            self.app.notify(
                "no manifest in this project — run init first", severity="warning"
            )
            return None
        qn = self._selected()
        if qn is None:
            if self.query_one(DataTable).row_count == 0:
                self.app.notify(
                    "no skills installed yet", severity="warning"
                )
            else:
                self._status("no row selected")
            return None
        return qn

    def action_update_current(self) -> None:
        qn = self._guard()
        if qn is None:
            return
        try:
            result = install.update(self._project_root, qn)
        except install.LocalEditsError as exc:
            def _on_confirm(yes: bool | None) -> None:
                if yes is not True:
                    return
                try:
                    install.update(self._project_root, qn, force=True)
                except (
                    install.SkillNotInstalledError,
                    install.SkillSourcePathChangedError,
                    install.SkillNotIndexedError,
                    git.GitError,
                ) as inner_exc:
                    self.app.notify(f"update failed: {inner_exc}", severity="error")
                    return
                self.app.notify(f"updated {qn} (forced)")
                self._populate()

            self.app.push_screen(
                ConfirmModal(
                    f"{exc}\n\nOverwrite local edits?", confirm_label="Force update"
                ),
                _on_confirm,
            )
            return
        except (
            install.SkillNotInstalledError,
            install.SkillSourcePathChangedError,
            install.SkillNotIndexedError,
            git.GitError,
        ) as exc:
            self.app.notify(f"update failed: {exc}", severity="error")
            return
        self.app.notify(f"updated {qn} -> {result.current.identifier()}")
        self._populate()

    def action_rollback_current(self) -> None:
        qn = self._guard()
        if qn is None:
            return
        try:
            result = install.rollback(self._project_root, qn)
        except install.NoHistoryToRollbackError:
            self.app.notify("no previous version to roll back to", severity="warning")
            return
        except (install.RollbackUnavailableError, git.GitError) as exc:
            self.app.notify(f"rollback failed: {exc}", severity="error")
            return
        self.app.notify(f"rolled back {qn} -> {result.current.identifier()}")
        self._populate()

    def action_delete_current(self) -> None:
        qn = self._guard()
        if qn is None:
            return

        def _on_confirm(yes: bool | None) -> None:
            if yes is not True:
                return
            try:
                install.delete(self._project_root, qn)
            except install.SkillNotInstalledError as exc:
                self.app.notify(f"delete failed: {exc}", severity="error")
                return
            self.app.notify(f"deleted {qn}")
            self._populate()

        self.app.push_screen(
            ConfirmModal(f"Delete installed skill {qn!r}?"), _on_confirm
        )

    def _status(self, msg: str) -> None:
        self.last_status = msg
        self.query_one("#status", Static).update(msg)
