"""Read/merge/write Claude Code's project ``.claude/settings.json`` for plugins.

aim manages exactly two keys — ``extraKnownMarketplaces`` and
``enabledPlugins`` — and preserves every other key (e.g. ``hooks``). It registers
a **local-directory marketplace** pointing at aim's vendored copy, so Claude
loads the pinned bytes without fetching upstream.

Modeled on the preserve-unmanaged-keys discipline of the ``.mcp.json`` writer
(``mcp_registry``), but it spans two maps plus a side ``marketplace.json``, so it
is not a verbatim copy. Keys are written without reordering the user's existing
content (``settings.json`` is hand-edited far more than ``.mcp.json``).
"""

from __future__ import annotations

import json
from pathlib import Path

from aim.core import content_guard
from aim.core.layout_profiles import LayoutProfile


class SettingsJsonError(ValueError):
    """Raised when ``.claude/settings.json`` is present but not a JSON object."""


def settings_path(project_root: Path, profile: LayoutProfile) -> Path:
    """Return the project's ``.claude/settings.json`` path for this profile."""
    return project_root / profile.claude_settings


def read_settings(project_root: Path, profile: LayoutProfile) -> dict:
    """Read settings.json, returning an empty dict when absent or empty.

    Raises:
        SettingsJsonError: The file exists but is invalid JSON or not an object.
    """
    path = settings_path(project_root, profile)
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SettingsJsonError(f"invalid {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsJsonError(f"{path} must contain a JSON object")
    return data


def write_settings(project_root: Path, profile: LayoutProfile, data: dict) -> Path:
    """Write settings.json with stable 2-space indentation, preserving key order."""
    path = settings_path(project_root, profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def register(
    project_root: Path,
    profile: LayoutProfile,
    *,
    marketplace_name: str,
    marketplace_path: str,
    plugin_names: list[str],
) -> Path:
    """Register a local-directory marketplace and enable the given plugins.

    Sets ``extraKnownMarketplaces[marketplace_name]`` to a directory source at
    ``marketplace_path`` (repo-root-relative) and flips
    ``enabledPlugins["<plugin>@<marketplace_name>"]`` true for each plugin. Other
    keys are preserved. The composed enablement keys, marketplace name, and path
    are scanned for hidden Unicode (they derive from untrusted repo content).
    """
    content_guard.assert_no_hidden_unicode(marketplace_name, source="marketplace name")
    content_guard.assert_no_hidden_unicode(marketplace_path, source="marketplace path")
    data = read_settings(project_root, profile)

    mkts = data.setdefault("extraKnownMarketplaces", {})
    if not isinstance(mkts, dict):
        raise SettingsJsonError("extraKnownMarketplaces must be a JSON object")
    mkts[marketplace_name] = {"source": {"source": "directory", "path": marketplace_path}}

    enabled = data.setdefault("enabledPlugins", {})
    if not isinstance(enabled, dict):
        raise SettingsJsonError("enabledPlugins must be a JSON object")
    for name in plugin_names:
        key = f"{name}@{marketplace_name}"
        content_guard.assert_no_hidden_unicode(key, source="enabledPlugins key")
        enabled[key] = True

    return write_settings(project_root, profile, data)


def unregister(
    project_root: Path,
    profile: LayoutProfile,
    *,
    marketplace_name: str,
    plugin_name: str,
) -> Path:
    """Disable a plugin and drop its marketplace entry once nothing references it.

    Removes ``enabledPlugins["<plugin>@<marketplace>"]``; if no remaining
    ``enabledPlugins`` key references ``@<marketplace>``, the
    ``extraKnownMarketplaces`` entry is removed too (refcount).
    """
    data = read_settings(project_root, profile)
    enabled = data.get("enabledPlugins")
    if isinstance(enabled, dict):
        enabled.pop(f"{plugin_name}@{marketplace_name}", None)
        suffix = f"@{marketplace_name}"
        still_used = any(isinstance(k, str) and k.endswith(suffix) for k in enabled)
        if not still_used:
            mkts = data.get("extraKnownMarketplaces")
            if isinstance(mkts, dict):
                mkts.pop(marketplace_name, None)
    return write_settings(project_root, profile, data)
