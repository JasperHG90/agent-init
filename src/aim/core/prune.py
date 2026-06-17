"""`aim prune` — remove artifacts on disk that are no longer in `aim.lock.toml`.

Scans the active layout profile's skills, agents, and rules directories,
plus `.mcp.json` managed aliases, and removes anything not listed in the
lockfile. Only acts inside the project root for safety.

Local-only artifacts can be protected by creating `.aimignore` in the project
root with glob patterns (one per line), e.g.:

    .claude/skills/local/*
    .claude/agents/local_*.md
    .claude/rules/local_*.md

Blank lines and `#` comments are ignored. Patterns match the same path format
used by `aim.lock.toml` (relative POSIX paths from the project root).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from aim.core import layout_profiles, manifest, mcp_registry


class PruneError(RuntimeError):
    pass


@dataclass
class PruneOptions:
    project_root: Path
    dry_run: bool = False
    layout_profile: str | None = None
    excludes: list[str] = field(default_factory=list)


@dataclass
class PruneItem:
    kind: str
    path: str
    action: str  # "removed" | "would-remove" | "skipped" | "skipped-unsafe"


@dataclass
class PruneResult:
    removed: list[PruneItem] = field(default_factory=list)
    kept: list[PruneItem] = field(default_factory=list)


def _safe_rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _ensure_inside(root: Path, path: Path) -> bool:
    """Return True only if `path` resolves to a location under `root`."""
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except (OSError, ValueError):
        return False
    return resolved == root_resolved or resolved.is_relative_to(root_resolved)


def _load_aimignore(project_root: Path) -> list[str]:
    """Read .aimignore if it exists, returning non-comment, non-empty patterns."""
    ignore_path = project_root / ".aimignore"
    if not ignore_path.is_file():
        return []
    patterns: list[str] = []
    for line in ignore_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_excluded(rel: str, patterns: list[str]) -> bool:
    """Match a project-relative POSIX path against glob patterns.

    Supports direct globs (`.claude/agents/local_*.md`) and directory
    patterns (`.claude/skills/local/`, `.claude/skills/local`, or
    `.claude/skills/local/*`). Directory patterns protect the directory
    itself and anything inside it.
    """
    rel_dir = rel + "/"
    for raw in patterns:
        # Direct glob match against the exact relative path.
        if fnmatch.fnmatch(rel, raw.rstrip("/")):
            return True

        prefix = raw.rstrip("/")
        if prefix.endswith("/*"):
            # `.claude/skills/local/*` also protects the `local` directory.
            if rel_dir.startswith(prefix[:-1]):
                return True
        elif not prefix.endswith("*"):
            # Bare directory or trailing-slash pattern.
            if rel_dir.startswith(prefix + "/"):
                return True

    return False


def _run(options: PruneOptions) -> PruneResult:
    project_root = options.project_root.resolve()
    try:
        m = manifest.load(project_root)
    except manifest.ManifestNotFoundError as exc:
        raise PruneError(f"no aim.lock.toml in {project_root}; run `aim init` first") from exc

    active_name = options.layout_profile or m.layout_profile
    if active_name:
        try:
            profile = layout_profiles.get_profile(project_root, active_name)
        except layout_profiles.LayoutProfileNotFoundError:
            profile = layout_profiles.BUILTIN_CLAUDE
    else:
        profile = layout_profiles.BUILTIN_CLAUDE

    result = PruneResult()
    exclude_patterns = _load_aimignore(project_root) + list(options.excludes)

    def _maybe_remove(entry: Path, rel: str, kind: str, *, locked: bool) -> None:
        if locked:
            result.kept.append(PruneItem(kind, rel, "kept"))
            return
        if _is_excluded(rel, exclude_patterns):
            result.kept.append(PruneItem(kind, rel, "skipped"))
            return
        _remove(project_root, entry, rel, kind, result, options.dry_run)

    # Managed sets from the lock.
    locked_skill_dirs = {s.target_dir for s in m.skills}
    locked_agent_paths = {a.target_path for a in m.agents}
    locked_rule_names = set(m.rules)
    locked_mcp_aliases = {mc.alias for mc in m.mcp_servers}

    # Skills directory.
    skills_dir = project_root / profile.skills_dir
    if skills_dir.exists() and skills_dir.is_dir():
        for entry in skills_dir.iterdir():
            rel = _safe_rel(project_root, entry)
            if not entry.is_dir():
                continue
            _maybe_remove(entry, rel, "skill", locked=rel in locked_skill_dirs)

    # Agents directory.
    agents_dir = project_root / profile.agents_dir
    if agents_dir.exists() and agents_dir.is_dir():
        for entry in agents_dir.iterdir():
            rel = _safe_rel(project_root, entry)
            if not entry.is_file():
                continue
            _maybe_remove(entry, rel, "agent", locked=rel in locked_agent_paths)

    # Rules directory.
    rules_dir = project_root / profile.rules_dir
    if rules_dir.exists() and rules_dir.is_dir():
        for entry in rules_dir.iterdir():
            rel = _safe_rel(project_root, entry)
            if not entry.is_file() or entry.suffix != ".md":
                continue
            name = entry.stem
            _maybe_remove(entry, rel, "rule", locked=name in locked_rule_names)

    # MCP servers in .mcp.json.
    mcp_path = project_root / profile.mcp_json
    if mcp_path.exists():
        try:
            data = mcp_registry.read_mcp_json(project_root)
        except Exception as exc:
            raise PruneError(f"failed to read {profile.mcp_json}: {exc}") from exc
        servers = data.get("mcpServers", {})
        if isinstance(servers, dict):
            to_remove: list[str] = []
            for alias in list(servers.keys()):
                if alias in locked_mcp_aliases:
                    result.kept.append(PruneItem("mcp", alias, "kept"))
                    continue
                if _is_excluded(alias, exclude_patterns):
                    result.kept.append(PruneItem("mcp", alias, "skipped"))
                    continue
                to_remove.append(alias)
            if to_remove:
                if options.dry_run:
                    for alias in to_remove:
                        result.removed.append(PruneItem("mcp", alias, "would-remove"))
                else:
                    for alias in to_remove:
                        del servers[alias]
                    try:
                        mcp_registry.write_mcp_json(project_root, data)
                    except Exception as exc:
                        raise PruneError(f"failed to write {profile.mcp_json}: {exc}") from exc
                    for alias in to_remove:
                        result.removed.append(PruneItem("mcp", alias, "removed"))

    return result


def _remove(
    root: Path,
    path: Path,
    rel: str,
    kind: str,
    result: PruneResult,
    dry_run: bool,
) -> None:
    if not _ensure_inside(root, path):
        result.removed.append(PruneItem(kind, rel, "skipped-unsafe"))
        return
    if dry_run:
        result.removed.append(PruneItem(kind, rel, "would-remove"))
        return
    try:
        if path.is_dir():
            import shutil

            shutil.rmtree(path)
        elif path.is_file() or path.is_symlink():
            path.unlink()
        result.removed.append(PruneItem(kind, rel, "removed"))
    except Exception as exc:
        result.removed.append(PruneItem(kind, rel, f"error: {exc}"))


def run(options: PruneOptions) -> PruneResult:
    return _run(options)
