"""Modal: save the current project as a reusable project template."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


@dataclass(frozen=True)
class TemplateSaveResult:
    """Result returned when the user confirms saving a template."""

    name: str


class TemplateSaveModal(ModalScreen[TemplateSaveResult | None]):
    """Modal prompting for a name to save the current project as a template."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Save", priority=True),
    ]

    def __init__(self, *, initial_name: str = "") -> None:
        """Initialize the modal with an optional pre-filled template name.

        Args:
            initial_name: Name to pre-populate the input field with.
        """
        super().__init__()
        self._initial_name = initial_name

    def compose(self) -> ComposeResult:
        """Build the modal's widget tree."""
        yield Vertical(
            Static("Save project as template", classes="modal-title", markup=False),
            Static("Template name:", markup=False),
            Input(value=self._initial_name, id="name"),
            Static("", id="error", markup=False, classes="modal-error"),
            Horizontal(
                Button("Save", id="go", variant="primary"),
                Button("Cancel", id="cancel"),
                classes="modal-buttons",
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Focus the name input when the modal is mounted."""
        self.query_one("#name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit on the Save button, otherwise dismiss without a result.

        Args:
            event: The button-pressed event identifying which button fired.
        """
        if event.button.id == "go":
            self._submit()
        else:
            self.dismiss(None)

    def action_submit(self) -> None:
        """Handle the submit binding by attempting to save."""
        self._submit()

    def _submit(self) -> None:
        """Validate the entered name and dismiss with the result.

        Shows an inline error and keeps the modal open when the name is empty.
        """
        name = self.query_one("#name", Input).value.strip()
        if not name:
            self._error("template name is required")
            return
        self.dismiss(TemplateSaveResult(name=name))

    def _error(self, msg: str) -> None:
        """Display an error message inline and as a notification.

        Args:
            msg: The error message to surface to the user.
        """
        self.query_one("#error", Static).update(msg)
        self.app.notify(msg, severity="error", title="Save template")

    def action_cancel(self) -> None:
        """Dismiss the modal without saving."""
        self.dismiss(None)
