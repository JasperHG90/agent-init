"""`aim db`: maintain the global cache database."""

from __future__ import annotations

import typer

from aim.cli._shared import _friendly
from aim.core import db as db_mod

app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Maintain the global cache database."
)


@app.callback()
def db_group() -> None:
    """Keep `db` a command group: a single-command Typer would otherwise be collapsed
    into its lone command when materialized standalone by the lazy loader."""


@app.command("unlock")
@_friendly
def db_unlock() -> None:
    """Recover the global cache database after a "database is locked" failure.

    Checkpoints the write-ahead log to release WAL state. If another aim or TUI
    process is actively holding the database, this reports that instead — close that
    process and retry.
    """
    for action in db_mod.unlock():
        typer.echo(action)
