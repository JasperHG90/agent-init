"""Per-project manifest read/write. The manifest is the source of truth for
installed-skill state and history; the global DB is a cache only.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_init.core import paths
from agent_init.core.manifest_migrate import migrate
from agent_init.core.models import Manifest


class ManifestNotFoundError(FileNotFoundError):
    pass


def load(project_root: Path) -> Manifest:
    path = paths.project_manifest_path(project_root)
    if not path.exists():
        raise ManifestNotFoundError(path)
    raw = json.loads(path.read_text())
    migrated = migrate(raw)
    return Manifest.model_validate(migrated)


def load_or_default(project_root: Path) -> Manifest:
    try:
        return load(project_root)
    except ManifestNotFoundError:
        return Manifest()


def save(project_root: Path, manifest: Manifest) -> None:
    path = paths.project_manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = manifest.model_dump_json(indent=2, exclude_none=False)
    path.write_text(text + "\n")
