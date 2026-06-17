from __future__ import annotations

from pathlib import Path

import pytest

from agent_init.core import git
from tests.fixtures import git_fixtures


@pytest.fixture
def backend() -> git.RealGitBackend:
    return git.RealGitBackend()


def test_clone_bare_treats_dash_url_as_url_not_option(
    backend: git.RealGitBackend, tmp_path: Path
) -> None:
    # With the `--` separator, a URL starting with `-` is parsed as a URL.
    # Git will fail because it is not a valid repository, but it will not try
    # to interpret it as a command-line option.
    with pytest.raises(git.GitError):
        backend.clone_bare("-invalid.git", tmp_path / "dest")


def test_resolve_ref_rejects_dash_prefix(
    backend: git.RealGitBackend, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", {"README.md": "x\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    backend.clone_bare(f"file://{bare}", tmp_path / "clone")
    with pytest.raises(git.GitError, match="ref must not start with '-'"):
        backend.resolve_ref(tmp_path / "clone", "--evil")


def test_resolve_ref_accepts_normal_ref(
    backend: git.RealGitBackend, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", {"README.md": "x\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    backend.clone_bare(f"file://{bare}", tmp_path / "clone")
    sha = backend.resolve_ref(tmp_path / "clone", "HEAD")
    assert len(sha) == 40
