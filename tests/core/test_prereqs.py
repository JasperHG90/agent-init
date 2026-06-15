"""Tests for skill prereqs + capability tags."""

from __future__ import annotations

from pathlib import Path

from agent_init.core import install, repos
from tests.fixtures import git_fixtures


def test_prereqs_warning_when_missing(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src",
        files={
            "skills/review/SKILL.md": (
                "---\nprereqs: [anth/format]\n---\n# review\n"
            ),
            "skills/format/SKILL.md": "# format\n",
        },
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("anth", f"file://{bare}")
    install.install(project_root, "anth/review")
    warnings = install.take_install_warnings()
    assert any("missing prereqs" in w and "anth/format" in w for w in warnings)


def test_prereqs_no_warning_when_present(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src",
        files={
            "skills/review/SKILL.md": (
                "---\nprereqs: [anth/format]\n---\n# review\n"
            ),
            "skills/format/SKILL.md": "# format\n",
        },
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("anth", f"file://{bare}")
    install.install(project_root, "anth/format")
    install.take_install_warnings()  # drain
    install.install(project_root, "anth/review")
    warnings = install.take_install_warnings()
    assert not any("missing prereqs" in w for w in warnings)


def test_capability_collision(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src",
        files={
            "skills/a/SKILL.md": "---\nprovides: [code-review]\n---\n# a\n",
            "skills/b/SKILL.md": "---\nprovides: [code-review]\n---\n# b\n",
        },
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("anth", f"file://{bare}")
    install.install(project_root, "anth/a")
    install.take_install_warnings()  # drain
    install.install(project_root, "anth/b")
    warnings = install.take_install_warnings()
    assert any("capability collision" in w and "code-review" in w for w in warnings)
