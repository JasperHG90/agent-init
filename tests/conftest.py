"""Shared fixtures. The AGENT_INIT_HOME env var redirects all platformdirs
lookups to a tmp dir so tests never touch the real user data/cache/config dirs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from agent_init.core import db, paths


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolate all global agent-init state into tmp_path/home."""
    home_dir = tmp_path / "home"
    monkeypatch.setenv("AGENT_INIT_HOME", str(home_dir))
    paths.ensure_global_dirs()
    db.reset_engine()
    yield home_dir
    db.reset_engine()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


@pytest.fixture
def bare_remote(tmp_path: Path) -> tuple[Path, Path]:
    """Create a real local bare git remote with one commit and a `skills/foo/SKILL.md`.
    Returns (working_repo_path, bare_remote_path)."""
    from tests.fixtures import git_fixtures

    working = git_fixtures.make_source_repo(
        tmp_path / "src-repo",
        files={
            "README.md": "fixture\n",
            "skills/foo/SKILL.md": "# foo\n\nFoo skill.\n",
            "skills/foo/extra.md": "supporting content\n",
        },
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare-remote.git")
    return working, bare
