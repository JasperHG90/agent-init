"""Stable content hashing for directory trees and text bodies.

Used by:
- `install` to detect hand-edited files in a deployed skill dir.
- `agents_md` / `init` to detect hand-edited managed regions before rewrite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_text(body: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string.

    Args:
        body: Text to hash.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def hash_tree(root: Path) -> str:
    """Stable hash of a directory's file contents and names.

    Files are sorted by relative POSIX path for determinism. Directory entries
    themselves don't contribute (only files do). Empty trees hash to a known
    value.
    """
    if not root.exists():
        return hash_text("")
    h = hashlib.sha256()
    files = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in files:
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()
