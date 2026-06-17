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
    """Pick a sensible dialect from a filename. Defaults to HTML."""
    lower = filename.lower()
    if lower.endswith((".md", ".html", ".htm")):
        return HTML_DIALECT
    if lower.endswith(
        (".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".gitignore", ".editorconfig")
    ):
        return HASH_DIALECT
    return HTML_DIALECT


class RegionError(ValueError):
    pass


@dataclass(frozen=True)
class Region:
    name: str
    body: str


def parse(text: str, dialect: Dialect = HTML_DIALECT) -> list[Region]:
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
    """Same semantics as agents_md.merge but parameterised by dialect."""
    parse(existing, dialect)
    handled: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
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
    parts: list[str] = []
    for name, body in regions:
        if not body.startswith("\n"):
            body = "\n" + body
        if not body.endswith("\n"):
            body = body + "\n"
        parts.append(f"{dialect.begin(name)}{body}{dialect.end(name)}")
    return "\n".join(parts) + "\n"
