"""Global list of project roots that `aim doctor` should audit.

Lives at `user_config_dir/roots.txt` — one absolute path per line, blank lines
and `#` comments ignored. Kept deliberately simple: not a schema, not JSON,
just a flat list a user can edit.
"""

from __future__ import annotations

from pathlib import Path

from aim.core import paths


def _roots_file() -> Path:
    """Return the path to the global `roots.txt` file."""
    return paths.user_config_dir() / "roots.txt"


def list_roots() -> list[Path]:
    """Read the roots file and return the configured project roots.

    Blank lines and `#` comments are skipped.

    Returns:
        The user-expanded root paths, or an empty list if the file is absent.
    """
    path = _roots_file()
    if not path.exists():
        return []
    out: list[Path] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(Path(stripped).expanduser())
    return out


def add_root(root: Path) -> None:
    """Add a project root to the roots file, skipping duplicates.

    Args:
        root: The project root to register; resolved before comparison.
    """
    paths.ensure_global_dirs()
    path = _roots_file()
    resolved = root.expanduser().resolve()
    existing = list_roots()
    if any(r.expanduser().resolve() == resolved for r in existing):
        return
    line = f"{resolved}\n"
    if path.exists():
        body = path.read_text()
        if not body.endswith("\n"):
            body += "\n"
        path.write_text(body + line)
    else:
        path.write_text(line)


def remove_root(root: Path) -> bool:
    """Remove a project root from the roots file, preserving comments.

    Args:
        root: The project root to remove; resolved before comparison.

    Returns:
        True if a matching root was found and removed, False otherwise.
    """
    path = _roots_file()
    if not path.exists():
        return False
    resolved = root.expanduser().resolve()
    out: list[str] = []
    removed = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        if Path(stripped).expanduser().resolve() == resolved:
            removed = True
            continue
        out.append(line)
    path.write_text("\n".join(out) + ("\n" if out else ""))
    return removed
