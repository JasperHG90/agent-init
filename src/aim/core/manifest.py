"""Per-project manifest read/write. The manifest is the source of truth for
installed-skill state and history; the global DB is a cache only.

The committed manifest is a TOML lockfile named `aim.lock` at the project root.
Older `.atm/manifest.json` files are still readable as a one-time migration.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import tomli_w

from aim.core import paths
from aim.core.manifest_migrate import migrate
from aim.core.models import Manifest


class ManifestNotFoundError(FileNotFoundError):
    pass


def load(project_root: Path) -> Manifest:
    lock_path = paths.project_lock_path(project_root)
    if lock_path.exists():
        raw = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        migrated = migrate(raw)
        return Manifest.model_validate(migrated)

    legacy_path = paths.project_manifest_path(project_root)
    if legacy_path.exists():
        raw = json.loads(legacy_path.read_text())
        migrated = migrate(raw)
        manifest = Manifest.model_validate(migrated)
        # One-time migration: write the TOML lockfile and remove the stale JSON.
        save(project_root, manifest)
        legacy_path.unlink()
        return manifest

    raise ManifestNotFoundError(lock_path)


def load_or_default(project_root: Path) -> Manifest:
    try:
        return load(project_root)
    except ManifestNotFoundError:
        return Manifest()


def load_or_create(project_root: Path) -> Manifest:
    """Load the existing lockfile, or seed a new Manifest from aim.yml metadata.

    Used by install/update/delete paths so that the first artifact written to
    a project still produces a lockfile with template, mirrors, symlinks, rules,
    and layout profile copied from the user's declarations.
    """
    try:
        return load(project_root)
    except ManifestNotFoundError:
        from aim.core import declarations as declarations_mod

        decl = declarations_mod.load_or_default(project_root)
        m = Manifest(
            template=decl.template,
            layout_profile=decl.layout_profile,
            agent_dialect=decl.agent_dialect,
            rules=list(decl.rules),
            mirrors=list(decl.mirrors),
            symlinks=list(decl.symlinks),
        )
        return m


def save(project_root: Path, manifest: Manifest) -> None:
    path = paths.project_lock_path(project_root)
    data = manifest.model_dump(mode="json", exclude_none=True)
    text = tomli_w.dumps(data)
    path.write_text(text + "\n", encoding="utf-8")
