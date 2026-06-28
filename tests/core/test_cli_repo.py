"""CLI coverage for `aim repo reindex`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aim import cli
from aim.core import db, repo_rules, repos
from tests.fixtures import git_fixtures

_runner = CliRunner()


def _register_rule_repo(tmp_path: Path) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"rules/a.md": "a\n", "README.md": "x\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("r", f"file://{bare}")


def test_repo_reindex_restores_stale_index(home: Path, tmp_path: Path) -> None:
    _register_rule_repo(tmp_path)
    # Drop the index without moving the SHA, then reindex via the CLI.
    with db.session() as session:
        session.exec(repos._delete_rule_index("r"))
        session.commit()
    assert repo_rules.list_rules("r") == []

    res = _runner.invoke(cli.app, ["repo", "reindex", "r"])

    assert res.exit_code == 0, res.output
    assert "reindexed r" in res.output
    assert {row.rule_name for row in repo_rules.list_rules("r")} == {"a"}


def test_repo_reindex_unknown_alias_errors(home: Path) -> None:
    res = _runner.invoke(cli.app, ["repo", "reindex", "nope"])

    assert res.exit_code != 0
