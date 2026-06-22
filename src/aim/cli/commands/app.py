"""`aim app`: manage the aim installation — project schema and the global cache."""

from __future__ import annotations

from pathlib import Path

import typer

from aim.cli._shared import _friendly, _here

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage the aim installation: project schema and the global cache database.",
)


@app.callback()
def app_group() -> None:
    """Keep `app` a command group: a single-command Typer would otherwise be collapsed
    into its lone command when materialized standalone by the lazy loader."""


@app.command("bump-manifest")
@_friendly
def bump_manifest(project: Path | None = typer.Argument(None, help="Project root.")) -> None:
    """Migrate `aim.toml` to the current schema version and rewrite it.

    Brings an older `manifest_version` up to date and materializes any newly-defaulted
    tables (such as the always-present `[archetype]` block). Re-running on an
    already-current file rewrites it idempotently.
    """
    from aim.core import declarations

    root = _here(project)
    from_version, to_version = declarations.bump(root)
    if from_version == to_version:
        typer.echo(f"aim.toml already at schema version {to_version}.")
    else:
        typer.echo(f"Bumped aim.toml schema version {from_version} -> {to_version}.")


@app.command("unlock-db")
@_friendly
def unlock_db() -> None:
    """Recover the global cache database after a "database is locked" failure.

    Checkpoints the write-ahead log to release WAL state. If another aim or TUI
    process is actively holding the database, this reports that instead — close that
    process and retry.
    """
    from aim.core import db as db_mod

    for action in db_mod.unlock():
        typer.echo(action)
