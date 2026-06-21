"""`aim profile`: manage and apply reusable project templates (profiles)."""

from __future__ import annotations

from pathlib import Path

import typer

from aim.cli._shared import _friendly, _get_allow_insecure, _get_format, _here
from aim.core import format as format_mod
from aim.core import profiles as profiles_mod

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage and apply reusable project templates (profiles).",
)


@app.command("save")
@_friendly
def profile_save(
    name: str,
    project: Path | None = typer.Argument(None, help="Project to snapshot as a reusable template."),
) -> None:
    """Snapshot a project's declarations into a reusable named profile."""
    profile = profiles_mod.from_project(name, _here(project))
    path = profiles_mod.save(profile)
    typer.echo(f"saved project template {name} to {path}")


@app.command("list")
@_friendly
def profile_list(ctx: typer.Context) -> None:
    """List saved project profiles."""
    entries = profiles_mod.list_profiles()
    rows = [
        {
            "name": p.name,
            "instruction_template": p.instruction_template,
            "symlinks": ",".join(p.symlinks) or "-",
            "skills": len(p.skills),
            "subagents": len(p.agents),
            "mcp": len(p.mcp_servers),
            "rules": len(p.rules),
        }
        for p in entries
    ]
    format_mod.render(
        rows,
        _get_format(ctx),
        title="profiles saved",
        columns=["name", "instruction_template", "symlinks", "skills", "subagents", "mcp", "rules"],
        compact_columns=["name", "instruction_template", "skills", "subagents", "mcp", "rules"],
    )


@app.command("show")
@_friendly
def profile_show(name: str) -> None:
    """Print a saved profile as JSON."""
    p = profiles_mod.load(name)
    typer.echo(p.model_dump_json(indent=2))


@app.command("delete")
@_friendly
def profile_delete(name: str) -> None:
    """Delete a saved profile."""
    removed = profiles_mod.delete(name)
    typer.echo(f"deleted {name}" if removed else f"not found: {name}")


@app.command("apply")
@_friendly
def profile_apply(
    ctx: typer.Context,
    name: str,
    project: Path | None = typer.Argument(None, help="Project root."),
) -> None:
    """Apply a saved profile to a project: init, lock, install artifacts, sync."""
    result = profiles_mod.apply(name, _here(project), allow_insecure=_get_allow_insecure(ctx))
    typer.echo(f"applied project template {name} to {result.project_root}")
    for qn in result.installed_skills:
        typer.echo(f"  installed skill: {qn}")
    for qn in result.skipped_skills:
        typer.echo(f"  skipped skill (not indexed locally): {qn}", err=True)
    for qn in result.installed_agents:
        typer.echo(f"  installed agent: {qn}")
    for qn in result.skipped_agents:
        typer.echo(f"  skipped agent (not indexed locally): {qn}", err=True)
    for alias in result.installed_mcp:
        typer.echo(f"  installed MCP server: {alias}")
    for alias in result.skipped_mcp:
        typer.echo(f"  skipped MCP server (unavailable): {alias}", err=True)
