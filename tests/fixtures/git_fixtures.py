"""Helpers for tests that need a real local git repo to clone from.

We use real `git` against a local file:// URL — fast and exercises the actual
shell-out code path. Tests run in tmp_path so nothing leaks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def make_source_repo(
    root: Path,
    files: dict[str, str] | None = None,
    initial_commit_message: str = "initial",
) -> Path:
    """Create a normal working repo at `root` with the given files committed."""
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)
    files = files or {"README.md": "fixture\n"}
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _run(["git", "add", "."], root)
    _run(["git", "commit", "-q", "-m", initial_commit_message], root)
    return root


def make_bare_remote(working_repo: Path, dest: Path) -> Path:
    """Bare-clone `working_repo` to `dest`. Return `dest`."""
    subprocess.run(
        ["git", "clone", "--bare", "--quiet", str(working_repo), str(dest)],
        check=True,
        capture_output=True,
    )
    return dest


def add_commit(working_repo: Path, files: dict[str, str], message: str) -> str:
    for rel, content in files.items():
        path = working_repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _run(["git", "add", "."], working_repo)
    _run(["git", "commit", "-q", "-m", message], working_repo)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=working_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def add_tag(working_repo: Path, tag: str) -> None:
    _run(["git", "tag", tag], working_repo)


def push_to_bare(working_repo: Path, bare_remote: Path) -> None:
    """Mirror updates from the working repo into the bare remote."""
    subprocess.run(
        ["git", "push", "--mirror", str(bare_remote)],
        cwd=working_repo,
        check=True,
        capture_output=True,
    )
