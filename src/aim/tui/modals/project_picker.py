"""Generic project-root picker modal — reused by skill install, rule install,
and anywhere else the TUI needs the user to pick a target project directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


@dataclass(frozen=True)
class ProjectPick:
    """Result of a project-root selection, holding the chosen directory."""

    project_root: Path


class ProjectPickerModal(ModalScreen[ProjectPick | None]):
    """Modal screen prompting the user to pick a target project directory."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def __init__(
        self,
        title: str,
        *,
        action_label: str = "Go",
        initial_project: Path | None = None,
        helper: str = "Project root (will be created if missing):",
    ) -> None:
        """Initialize the picker with display text and a starting directory.

        Args:
            title: Heading shown at the top of the modal.
            action_label: Label for the confirm button.
            initial_project: Pre-filled project root; defaults to the cwd.
            helper: Helper text shown above the input field.
        """
        super().__init__()
        self._title = title
        self._action_label = action_label
        self._initial_project = initial_project or Path.cwd()
        self._helper = helper

    def compose(self) -> ComposeResult:
        """Build the modal's title, helper, input, and action buttons."""
        yield Vertical(
            Static(self._title, classes="modal-title", markup=False),
            Static(self._helper, markup=False),
            Input(value=str(self._initial_project), id="project-root"),
            Horizontal(
                Button(self._action_label, id="go", variant="primary"),
                Button("Cancel", id="cancel"),
                classes="modal-buttons",
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Focus the project-root input when the modal is mounted."""
        self.query_one("#project-root", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with the chosen project on confirm, or None on cancel."""
        if event.button.id == "go":
            value = self.query_one("#project-root", Input).value.strip()
            if not value:
                return
            self.dismiss(ProjectPick(project_root=Path(value).expanduser()))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Dismiss the modal without making a selection."""
        self.dismiss(None)

    def on_key(self, event) -> None:
        """Cancel the modal when Escape is pressed, stopping propagation."""
        if event.key == "escape":
            event.stop()
            self.action_cancel()
