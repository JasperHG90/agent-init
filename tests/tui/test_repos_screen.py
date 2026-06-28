"""Repos screen: reindex action re-runs discovery for the selected repo."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import DataTable

from aim.core import db, repo_rules, repos
from aim.tui.app import AimApp
from aim.tui.screens.repos_screen import ReposScreen
from tests.fixtures import git_fixtures


@pytest.mark.asyncio
async def test_repos_screen_reindex_restores_index(home: Path, tmp_path: Path) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"rules/a.md": "a\n", "README.md": "x\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("r", f"file://{bare}")
    # Drop the index without moving the SHA, so only a forced reindex restores it.
    with db.session() as session:
        session.exec(repos._delete_rule_index("r"))
        session.commit()
    assert repo_rules.list_rules("r") == []

    app = AimApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ReposScreen()
        app.push_screen(screen)
        await pilot.pause()
        screen.action_reindex_current()
        await app.workers.wait_for_complete()
        await pilot.pause()
        # The repopulated table reflects the rediscovered rule artifact.
        table = screen.query_one(DataTable)
        assert "rules" in table.get_row_at(0)[4]

    assert {row.rule_name for row in repo_rules.list_rules("r")} == {"a"}
