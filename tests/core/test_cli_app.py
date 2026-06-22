"""CLI coverage for `aim app` (bump-manifest, unlock-db)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aim import cli
from aim.core import declarations
from aim.core.models import CURRENT_DECLARATIONS_VERSION

_runner = CliRunner()


def test_bump_manifest_migrates_and_materializes_archetype(home: Path, project_root: Path) -> None:
    (project_root / "aim.toml").write_text("manifest_version = 7\n")

    res = _runner.invoke(cli.app, ["app", "bump-manifest", str(project_root)])

    assert res.exit_code == 0, res.output
    assert f"7 -> {CURRENT_DECLARATIONS_VERSION}" in res.output
    text = (project_root / "aim.toml").read_text()
    assert f"manifest_version = {CURRENT_DECLARATIONS_VERSION}" in text
    assert "[archetype]" in text
    assert declarations.load(project_root).archetype.is_builtin


def test_bump_manifest_is_idempotent(home: Path, project_root: Path) -> None:
    (project_root / "aim.toml").write_text("manifest_version = 7\n")
    _runner.invoke(cli.app, ["app", "bump-manifest", str(project_root)])

    res = _runner.invoke(cli.app, ["app", "bump-manifest", str(project_root)])

    assert res.exit_code == 0, res.output
    assert f"already at schema version {CURRENT_DECLARATIONS_VERSION}" in res.output


def test_unlock_db_runs(home: Path) -> None:
    res = _runner.invoke(cli.app, ["app", "unlock-db"])

    assert res.exit_code == 0, res.output
