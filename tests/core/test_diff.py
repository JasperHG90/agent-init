"""Tests for `--diff` / `dry_run` on init and skill update."""

from __future__ import annotations

from pathlib import Path

from agent_init.core import init as init_mod
from agent_init.core import install, manifest, repos
from tests.fixtures import git_fixtures


def test_init_dry_run_does_not_write(home: Path, project_root: Path) -> None:
    result = init_mod.run(init_mod.InitOptions(project_root=project_root, dry_run=True))
    assert result.dry_run is True
    assert result.pending_changes  # at least AGENTS.md
    assert not (project_root / "AGENTS.md").exists()
    # No manifest either.
    import pytest

    with pytest.raises(manifest.ManifestNotFoundError):
        manifest.load(project_root)


def test_init_dry_run_reflects_mirror_addition(
    home: Path, project_root: Path
) -> None:
    init_mod.run(init_mod.InitOptions(project_root=project_root))  # commit baseline
    result = init_mod.run(
        init_mod.InitOptions(
            project_root=project_root,
            mirrors=("CLAUDE.md",),
            dry_run=True,
        )
    )
    paths = {str(c.path) for c in result.pending_changes}
    assert any("CLAUDE.md" in p for p in paths)
    assert not (project_root / "CLAUDE.md").exists()


def test_skill_update_dry_run(home: Path, project_root: Path, tmp_path: Path) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={"skills/foo/SKILL.md": "# v1\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("a", f"file://{bare}")
    install.install(project_root, "a/foo")
    v1_sha = manifest.load(project_root).skills[0].current.sha

    # No upstream change yet — should be no-op.
    preview = install.update(project_root, "a/foo", dry_run=True)
    assert isinstance(preview, install.UpdatePreview)
    assert preview.will_change is False
    assert preview.current_sha == v1_sha

    # Push a change.
    git_fixtures.add_commit(working, {"skills/foo/SKILL.md": "# v2\n"}, "v2")
    git_fixtures.push_to_bare(working, bare)
    repos.refresh("a")

    preview = install.update(project_root, "a/foo", dry_run=True)
    assert isinstance(preview, install.UpdatePreview)
    assert preview.will_change is True
    assert preview.proposed_sha != v1_sha

    # Dry-run did NOT apply — manifest still shows v1.
    assert manifest.load(project_root).skills[0].current.sha == v1_sha
