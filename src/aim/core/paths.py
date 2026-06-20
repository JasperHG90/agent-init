"""Platform-aware paths for aim's global state and per-project state.

Global state lives under platformdirs; per-project state lives under .aim/
inside the project root.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "aim"

_PROJECT_DIR_ENV = "AIM_HOME"


def _dirs() -> PlatformDirs:
    """Build the platformdirs resolver for aim's standard locations."""
    return PlatformDirs(appname=APP_NAME, appauthor=False, ensure_exists=False)


def user_data_dir() -> Path:
    """Return the global data directory, honoring the AIM_HOME override."""
    override = os.environ.get(_PROJECT_DIR_ENV)
    if override:
        return Path(override) / "data"
    return Path(_dirs().user_data_dir)


def user_cache_dir() -> Path:
    """Return the global cache directory, honoring the AIM_HOME override."""
    override = os.environ.get(_PROJECT_DIR_ENV)
    if override:
        return Path(override) / "cache"
    return Path(_dirs().user_cache_dir)


def user_config_dir() -> Path:
    """Return the global config directory, honoring the AIM_HOME override."""
    override = os.environ.get(_PROJECT_DIR_ENV)
    if override:
        return Path(override) / "config"
    return Path(_dirs().user_config_dir)


def db_path() -> Path:
    """Return the path to aim's global SQLite database."""
    return user_data_dir() / "aim.sqlite"


def repos_cache_dir() -> Path:
    """Return the cache directory holding cloned repositories."""
    return user_cache_dir() / "repos"


def snapshots_cache_dir() -> Path:
    """Return the cache directory holding repository snapshots."""
    return user_cache_dir() / "snapshots"


def templates_library_dir() -> Path:
    """Return the config directory holding the global templates library."""
    return user_config_dir() / "templates"


def project_aim_dir(project_root: Path) -> Path:
    """Return the per-project .aim state directory.

    Args:
        project_root: Root directory of the project.
    """
    return project_root / ".aim"


def project_declarations_path(project_root: Path) -> Path:
    """Return the path to the project's aim.toml declarations file.

    Args:
        project_root: Root directory of the project.
    """
    return project_root / "aim.toml"


def project_lock_path(project_root: Path) -> Path:
    """Return the path to the project's aim.lock.toml lockfile.

    Args:
        project_root: Root directory of the project.
    """
    return project_root / "aim.lock.toml"


def project_manifest_path(project_root: Path) -> Path:
    """Return the legacy JSON manifest path, kept only for migration fallback.

    Args:
        project_root: Root directory of the project.
    """
    return project_root / ".atm" / "manifest.json"


def project_rules_dir(project_root: Path) -> Path:
    """Return the per-project directory holding rule definitions.

    Args:
        project_root: Root directory of the project.
    """
    return project_aim_dir(project_root) / "rules"


def project_layout_profiles_dir(project_root: Path) -> Path:
    """Return the per-project directory holding layout profiles.

    Args:
        project_root: Root directory of the project.
    """
    return project_aim_dir(project_root) / "layout-profiles"


def safe_project_path(project_root: Path, rel: str, *extra: str) -> Path | None:
    """Resolve a relative project path and ensure it stays inside the project.

    Args:
        project_root: Root directory the resolved path must stay within.
        rel: Relative path to resolve against the project root.
        *extra: Additional path segments appended after rel.

    Returns:
        The resolved absolute path, or None if it escapes the project root or
        resolution fails. The project root itself is considered out of bounds so
        that empty or ``..``-only relative paths are rejected.
    """
    try:
        base = project_root.resolve()
        target = (base / rel / "/".join(extra)).resolve()
        if target != base and target.is_relative_to(base):
            return target
    except (ValueError, OSError):
        pass
    return None


def ensure_global_dirs() -> None:
    """Create all global data, cache, and config directories if missing."""
    for path in (
        user_data_dir(),
        user_cache_dir(),
        user_config_dir(),
        repos_cache_dir(),
        snapshots_cache_dir(),
        templates_library_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)
