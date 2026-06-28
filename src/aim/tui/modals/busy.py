"""Modal: a transient loading overlay shown while a background worker runs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import LoadingIndicator, Static


class BusyModal(ModalScreen[None]):
    """A non-interactive spinner overlay shown while a threaded task runs.

    It mirrors the CLI's transient scan spinner: install/scan work runs on a
    worker thread, and this overlay tells the user the action is in flight until
    the worker dismisses it. It intentionally has no key bindings, so it can only
    be dismissed programmatically when the work finishes.
    """

    def __init__(self, message: str) -> None:
        """Initialize the overlay with the message to display above the spinner.

        Args:
            message: A short description of the in-flight action, e.g.
                "Installing anth/code-review…".
        """
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Build the centered spinner overlay."""
        yield Vertical(
            Static(self._message, classes="modal-title", markup=False),
            LoadingIndicator(),
            classes="busy-modal",
        )
