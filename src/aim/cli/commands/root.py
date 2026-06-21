"""`aim root`: manage the global list of project roots used by `doctor`."""

from __future__ import annotations

from pathlib import Path

import typer

from aim.cli._shared import _friendly, _get_format
from aim.core import format as format_mod
from aim.core import roots as roots_mod

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage the global list of project roots used by `doctor`.",
)


@app.command("add")
@_friendly
def root_add(path: Path = typer.Argument(..., help="Project root path.")) -> None:
    """Track a project root so `aim doctor` and global commands can find it."""
    roots_mod.add_root(path.expanduser())
    typer.echo(f"added root {path.expanduser().resolve()}")


@app.command("list")
@_friendly
def root_list(ctx: typer.Context) -> None:
    """List configured project roots."""
    entries = roots_mod.list_roots()
    rows = [{"path": str(r)} for r in entries]
    format_mod.render(
        rows,
        _get_format(ctx),
        title="roots configured",
        columns=["path"],
        compact_columns=["path"],
    )


@app.command("remove")
@_friendly
def root_remove(path: Path = typer.Argument(..., help="Project root path.")) -> None:
    """Stop tracking a project root."""
    removed = roots_mod.remove_root(path.expanduser())
    typer.echo(f"removed {path}" if removed else f"not in roots: {path}")
