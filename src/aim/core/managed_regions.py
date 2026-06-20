"""Generalised managed-region engine for files of any comment dialect.

`agents_md.py` is the HTML-comment specialisation. This module supports the
HTML dialect plus a hash-comment dialect for YAML / TOML / shell / .pre-commit
snippets, so companion-file templates can manage regions inside those too.

Add a new dialect by registering it in `DIALECTS`. Each dialect has:
- `begin_template(name) -> str` — the marker that opens a region
- `end_template(name) -> str`   — the marker that closes it
- `region_re` — compiled regex that matches an entire region pair
- `marker_pair_re` — compiled regex used for unbalanced-marker detection
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from re import Pattern


@dataclass(frozen=True)
class Dialect:
    """Describe how a comment dialect opens, closes, and matches a region."""

    name: str
    begin: Callable[[str], str]
    end: Callable[[str], str]
    region_re: Pattern[str]
    end_re: Pattern[str]


HTML_DIALECT = Dialect(
    name="html",
    begin=lambda n: f"<!-- BEGIN aim: {n} -->",
    end=lambda n: f"<!-- END aim: {n} -->",
    region_re=re.compile(
        r"<!-- BEGIN aim: (?P<name>[a-z0-9_-]+) -->"
        r"(?P<body>.*?)"
        r"<!-- END aim: (?P=name) -->",
        re.DOTALL,
    ),
    end_re=re.compile(r"<!-- END aim: ([a-z0-9_-]+) -->"),
)


HASH_DIALECT = Dialect(
    name="hash",
    begin=lambda n: f"# BEGIN aim: {n}",
    end=lambda n: f"# END aim: {n}",
    region_re=re.compile(
        r"# BEGIN aim: (?P<name>[a-z0-9_-]+)\n"
        r"(?P<body>.*?)"
        r"# END aim: (?P=name)",
        re.DOTALL,
    ),
    end_re=re.compile(r"# END aim: ([a-z0-9_-]+)"),
)


DIALECTS: dict[str, Dialect] = {
    "html": HTML_DIALECT,
    "hash": HASH_DIALECT,
}


def for_filename(filename: str) -> Dialect:
    """Pick a sensible dialect from a filename, defaulting to HTML.

    Args:
        filename: Name of the file whose comment dialect should be inferred.

    Returns:
        The HASH dialect for YAML/TOML/shell-style files, otherwise HTML.
    """
    lower = filename.lower()
    if lower.endswith((".md", ".html", ".htm")):
        return HTML_DIALECT
    if lower.endswith(
        (".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".gitignore", ".editorconfig")
    ):
        return HASH_DIALECT
    return HTML_DIALECT


class RegionError(ValueError):
    """Raise when aim markers in a file are malformed or unbalanced."""


@dataclass(frozen=True)
class Region:
    """Hold a single managed region's name and body text."""

    name: str
    body: str


def parse(text: str, dialect: Dialect = HTML_DIALECT) -> list[Region]:
    """Extract all managed regions from text, validating marker balance.

    Args:
        text: Source content to scan for aim-managed regions.
        dialect: Comment dialect whose markers delimit the regions.

    Returns:
        Every region found, in document order.

    Raises:
        RegionError: If begin and end markers do not balance.
    """
    regions = [
        Region(name=m.group("name"), body=m.group("body")) for m in dialect.region_re.finditer(text)
    ]
    begins_re = re.compile(dialect.begin("([a-z0-9_-]+)"))
    begins = begins_re.findall(text)
    ends = dialect.end_re.findall(text)
    if sorted(begins) != sorted(ends):
        raise RegionError(
            f"unbalanced aim markers ({dialect.name}): begins={sorted(begins)} ends={sorted(ends)}"
        )
    return regions


def merge(
    existing: str,
    new_regions: dict[str, str],
    dialect: Dialect = HTML_DIALECT,
) -> str:
    """Replace or append managed regions in existing text.

    Mirrors the semantics of ``agents_md.merge`` but is parameterised by
    dialect. Regions whose names appear in ``new_regions`` are rewritten in
    place; any remaining new regions are appended to the end.

    Args:
        existing: Current file content to merge into.
        new_regions: Mapping of region name to replacement body.
        dialect: Comment dialect whose markers delimit the regions.

    Returns:
        The merged content with all new regions present.
    """
    parse(existing, dialect)
    handled: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        """Rewrite one matched region's body if a replacement is supplied."""
        name = match.group("name")
        if name not in new_regions:
            return match.group(0)
        handled.add(name)
        body = new_regions[name]
        if not body.startswith("\n"):
            body = "\n" + body
        if not body.endswith("\n"):
            body = body + "\n"
        return f"{dialect.begin(name)}{body}{dialect.end(name)}"

    out = dialect.region_re.sub(_replace, existing)

    missing = [(n, b) for n, b in new_regions.items() if n not in handled]
    if missing:
        parts: list[str] = []
        if out and not out.endswith("\n"):
            parts.append("\n")
        for name, body in missing:
            if not body.startswith("\n"):
                body = "\n" + body
            if not body.endswith("\n"):
                body = body + "\n"
            parts.append(f"\n{dialect.begin(name)}{body}{dialect.end(name)}\n")
        out = out + "".join(parts)
    return out


def build(regions: Iterable[tuple[str, str]], dialect: Dialect = HTML_DIALECT) -> str:
    """Render a fresh file body from name/body region pairs.

    Args:
        regions: Iterable of ``(name, body)`` pairs to emit as regions.
        dialect: Comment dialect whose markers delimit the regions.

    Returns:
        The concatenated regions as a single trailing-newline string.
    """
    parts: list[str] = []
    for name, body in regions:
        if not body.startswith("\n"):
            body = "\n" + body
        if not body.endswith("\n"):
            body = body + "\n"
        parts.append(f"{dialect.begin(name)}{body}{dialect.end(name)}")
    return "\n".join(parts) + "\n"
