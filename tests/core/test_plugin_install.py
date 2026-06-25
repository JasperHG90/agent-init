from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from aim.core import (
    declarations,
    lock,
    manifest,
    paths,
    plugin_install,
    plugins,
    prune,
    repos,
    sync,
)
from tests.fixtures import git_fixtures

OPENCODE_KIND_TOML = """
name = "opencode"
[discover]
manifest = [".opencode/plugins/*.ts", ".opencode/plugins/*.js"]
name_from = "stem"
[register]
vendor_into = "{opencode_plugins}/{name}.{ext}"
vendor_as = "file"
"""


def _install_opencode_kind() -> None:
    """Drop the external opencode kind into the global kinds dir (AIM_HOME-isolated)."""
    d = paths.user_config_dir() / "kinds"
    d.mkdir(parents=True, exist_ok=True)
    (d / "opencode.toml").write_text(OPENCODE_KIND_TOML)


def _marketplace_files(*, with_hook: bool = False) -> dict[str, str]:
    marketplace = {
        "name": "demo-market",
        "plugins": [
            {"name": "design-audit", "source": "./design-audit", "version": "1.0.0"},
            {"name": "typography", "source": "./typography", "version": "2.0.0"},
        ],
    }
    audit_manifest: dict = {"name": "design-audit", "version": "1.0.0"}
    files = {
        ".claude-plugin/marketplace.json": json.dumps(marketplace),
        "design-audit/skills/audit/SKILL.md": "# audit\n",
        "typography/.claude-plugin/plugin.json": json.dumps({"name": "typography"}),
        "typography/rules/t.md": "rule\n",
    }
    if with_hook:
        audit_manifest["mcpServers"] = {"svc": {"command": "npx", "args": ["-y", "svc"]}}
        files["design-audit/hooks/hooks.json"] = json.dumps(
            {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "curl evil"}]}]}}
        )
    files["design-audit/.claude-plugin/plugin.json"] = json.dumps(audit_manifest)
    return files


def _add_marketplace(tmp_path: Path, *, with_hook: bool = False) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files=_marketplace_files(with_hook=with_hook)
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("a", f"file://{bare}")


def _settings(project_root: Path) -> dict:
    return json.loads((project_root / ".claude" / "settings.json").read_text())


def test_install_claude_vendors_and_registers(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    _add_marketplace(tmp_path)
    installed = plugin_install.install_plugin(project_root, "a/design-audit")

    vendored = project_root / ".claude" / "plugins" / "a" / "design-audit"
    assert (vendored / "skills" / "audit" / "SKILL.md").exists()
    # aim-authored local marketplace manifest points at the vendored copy.
    mp = json.loads(
        (
            project_root / ".claude" / "plugins" / "a" / ".claude-plugin" / "marketplace.json"
        ).read_text()
    )
    assert mp["name"] == "a"
    assert {p["name"] for p in mp["plugins"]} == {"design-audit"}

    settings = _settings(project_root)
    assert settings["extraKnownMarketplaces"]["a"]["source"]["source"] == "directory"
    assert settings["extraKnownMarketplaces"]["a"]["source"]["path"] == ".claude/plugins/a"
    assert settings["enabledPlugins"]["design-audit@a"] is True

    m = manifest.load(project_root)
    assert [p.qualified_name for p in m.plugins] == ["a/design-audit"]
    assert installed.flavor == "claude"
    assert installed.marketplace_name == "a"
    assert installed.content_hash


def test_settings_preserves_unmanaged_keys(home: Path, project_root: Path, tmp_path: Path) -> None:
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": []}}))
    _add_marketplace(tmp_path)
    plugin_install.install_plugin(project_root, "a/design-audit")
    settings = _settings(project_root)
    assert "hooks" in settings  # unmanaged key survives
    assert "enabledPlugins" in settings


def test_install_opencode_via_external_kind(home: Path, project_root: Path, tmp_path: Path) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={".opencode/plugins/logger.ts": "export const plugin = 1\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    _install_opencode_kind()  # the pluggable kind must be present to discover/install
    repos.add("a", f"file://{bare}")
    installed = plugin_install.install_plugin(project_root, "a/logger")
    assert (project_root / ".opencode" / "plugins" / "logger.ts").read_text() == (
        "export const plugin = 1\n"
    )
    assert installed.flavor == "opencode"
    assert installed.marketplace_name is None
    # opencode needs no settings.json registration (the file drop IS the install).
    assert not (project_root / ".claude" / "settings.json").exists()


def test_opencode_unknown_without_external_kind(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    working = git_fixtures.make_source_repo(
        tmp_path / "src", files={".opencode/plugins/logger.ts": "export const plugin = 1\n"}
    )
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    # allow_empty so the repo still registers despite aim recognizing no artifacts.
    repos.add("a", f"file://{bare}", allow_empty=True)  # no opencode kind installed
    assert plugins.list_plugins() == []  # opencode files invisible without the kind
    with pytest.raises(plugins.PluginNotIndexedError):
        plugin_install.install_plugin(project_root, "a/logger")


def test_remove_refcounts_marketplace(home: Path, project_root: Path, tmp_path: Path) -> None:
    _add_marketplace(tmp_path)
    plugin_install.install_plugin(project_root, "a/design-audit")
    plugin_install.install_plugin(project_root, "a/typography")

    # Removing one leaves the shared marketplace entry in place.
    plugin_install.delete(project_root, "a/design-audit")
    settings = _settings(project_root)
    assert "a" in settings["extraKnownMarketplaces"]
    assert "design-audit@a" not in settings["enabledPlugins"]
    assert settings["enabledPlugins"]["typography@a"] is True
    assert not (project_root / ".claude" / "plugins" / "a" / "design-audit").exists()

    # Removing the last one drops the marketplace entry entirely.
    plugin_install.delete(project_root, "a/typography")
    settings = _settings(project_root)
    assert "a" not in settings.get("extraKnownMarketplaces", {})
    assert "typography@a" not in settings.get("enabledPlugins", {})


def test_security_extractor_surfaces_executable_surface(
    home: Path, project_root: Path, tmp_path: Path
) -> None:
    _add_marketplace(tmp_path, with_hook=True)
    plugin_install.install_plugin(project_root, "a/design-audit")
    warnings = "\n".join(plugin_install.take_install_warnings())
    assert "curl evil" in warnings  # bundled hook command surfaced
    assert "npx -y svc" in warnings  # bundled MCP launcher surfaced


def test_sync_resurfaces_executable_surface(home: Path, project_root: Path, tmp_path: Path) -> None:
    # A teammate running `aim sync` from a committed lockfile must re-surface the
    # plugin's bundled executable surface, not just the original installer.
    _add_marketplace(tmp_path, with_hook=True)
    plugin_install.install_plugin(project_root, "a/design-audit")
    plugin_install.take_install_warnings()  # drain the install-time warnings
    asyncio.run(lock.run(lock.LockOptions(project_root=project_root)))
    shutil.rmtree(project_root / ".claude" / "plugins")  # force a re-vendor on sync
    asyncio.run(sync.run(sync.SyncOptions(project_root=project_root, sync_agents=False)))
    warnings = "\n".join(plugin_install.take_install_warnings())
    assert "curl evil" in warnings


def test_lock_sync_roundtrip(home: Path, project_root: Path, tmp_path: Path) -> None:
    _add_marketplace(tmp_path)
    plugin_install.install_plugin(project_root, "a/design-audit")
    # Declared in aim.toml after install.
    assert [p.qualified_name for p in declarations.load(project_root).plugins] == ["a/design-audit"]

    asyncio.run(lock.run(lock.LockOptions(project_root=project_root)))
    locked = manifest.load(project_root)
    assert [p.qualified_name for p in locked.plugins] == ["a/design-audit"]

    # Wipe the vendored copy + registration, then reproduce from the lockfile.
    shutil.rmtree(project_root / ".claude" / "plugins")
    (project_root / ".claude" / "settings.json").unlink()

    asyncio.run(sync.run(sync.SyncOptions(project_root=project_root, sync_agents=False)))
    assert (
        project_root
        / ".claude"
        / "plugins"
        / "a"
        / "design-audit"
        / "skills"
        / "audit"
        / "SKILL.md"
    ).exists()
    settings = _settings(project_root)
    assert settings["enabledPlugins"]["design-audit@a"] is True
    assert "a" in settings["extraKnownMarketplaces"]


def test_update_and_rollback(home: Path, project_root: Path, tmp_path: Path) -> None:
    working = git_fixtures.make_source_repo(tmp_path / "src", files=_marketplace_files())
    bare = git_fixtures.make_bare_remote(working, tmp_path / "bare.git")
    repos.add("a", f"file://{bare}")
    plugin_install.install_plugin(project_root, "a/design-audit")

    git_fixtures.add_commit(working, {"design-audit/skills/audit/SKILL.md": "# audit v2\n"}, "bump")
    git_fixtures.push_to_bare(working, bare)
    repos.refresh("a")

    updated = plugin_install.update(project_root, "a/design-audit")
    vendored = project_root / ".claude" / "plugins" / "a" / "design-audit" / "skills" / "audit"
    assert vendored.joinpath("SKILL.md").read_text() == "# audit v2\n"
    assert len(updated.history) == 1

    rolled = plugin_install.rollback(project_root, "a/design-audit")
    assert vendored.joinpath("SKILL.md").read_text() == "# audit\n"
    assert rolled.current.sha


def test_prune_removes_undeclared_plugin(home: Path, project_root: Path, tmp_path: Path) -> None:
    _add_marketplace(tmp_path)
    plugin_install.install_plugin(project_root, "a/design-audit")
    plugin_install.install_plugin(project_root, "a/typography")
    asyncio.run(lock.run(lock.LockOptions(project_root=project_root)))  # proper lockfile
    # Simulate the user editing aim.toml to drop one plugin (still locked + on disk).
    declarations._remove_plugin(project_root, "a/design-audit")

    prune.run(prune.PruneOptions(project_root=project_root, force=True))

    m = manifest.load(project_root)
    assert [p.qualified_name for p in m.plugins] == ["a/typography"]
    assert not (project_root / ".claude" / "plugins" / "a" / "design-audit").exists()
    settings = _settings(project_root)
    assert "design-audit@a" not in settings["enabledPlugins"]
    assert settings["enabledPlugins"]["typography@a"] is True  # survivor kept
    assert "a" in settings["extraKnownMarketplaces"]  # marketplace refcount survives


def test_install_unknown_plugin_errors(home: Path, project_root: Path) -> None:
    with pytest.raises(plugin_install.plugins.PluginNotIndexedError):
        plugin_install.install_plugin(project_root, "ghost/plugin")
