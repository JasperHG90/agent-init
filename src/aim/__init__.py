"""Top-level package for the aim Typer CLI and Textual TUI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aim")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"
