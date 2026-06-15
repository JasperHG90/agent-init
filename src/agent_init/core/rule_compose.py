"""Rule composition: parse `extends:` / `order:` front-matter, resolve
transitively with cycle detection.

Front-matter format (optional, must be at start of body):

    ---
    extends: [be-concise, no-emojis]
    order: 10
    ---
    The actual rule body lives here.

Both keys are optional. `order` defaults to 100; lower numbers render first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_LIST_RE = re.compile(r"^\[(.*)\]$")

DEFAULT_ORDER = 100


@dataclass(frozen=True)
class RuleMeta:
    extends: tuple[str, ...]
    order: int
    body_without_frontmatter: str


class RuleCycleError(RuntimeError):
    """Cycle detected in rule extends graph."""


def parse_front_matter(body: str) -> RuleMeta:
    match = _FRONT_MATTER_RE.match(body)
    if match is None:
        return RuleMeta(extends=(), order=DEFAULT_ORDER, body_without_frontmatter=body)
    block = match.group(1)
    extends: tuple[str, ...] = ()
    order = DEFAULT_ORDER
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "extends":
            list_match = _LIST_RE.match(value)
            if list_match:
                inner = list_match.group(1)
                extends = tuple(
                    p.strip().strip("'\"")
                    for p in inner.split(",")
                    if p.strip()
                )
            elif value:
                extends = (value.strip("'\""),)
        elif key == "order":
            try:
                order = int(value)
            except ValueError:
                order = DEFAULT_ORDER
    rest = body[match.end():]
    return RuleMeta(extends=extends, order=order, body_without_frontmatter=rest)


def resolve(names, lookup) -> list[str]:  # type: ignore[no-untyped-def]
    """Resolve a list of seed rule names to the transitively expanded set,
    sorted by (order asc, insertion order). `lookup(name)` returns the rule body.

    Raises RuleCycleError on cycle.
    """
    result_order: list[str] = []
    seen: set[str] = set()
    in_progress: set[str] = set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in seen:
            return
        if name in in_progress:
            cycle = " -> ".join((*path, name))
            raise RuleCycleError(f"rule cycle detected: {cycle}")
        in_progress.add(name)
        body = lookup(name)
        meta = parse_front_matter(body)
        for parent in meta.extends:
            visit(parent, (*path, name))
        in_progress.discard(name)
        seen.add(name)
        result_order.append(name)

    for name in names:
        visit(name, ())

    # Stable-sort by order, breaking ties by post-traversal index.
    indexed = list(enumerate(result_order))
    indexed.sort(
        key=lambda pair: (parse_front_matter(lookup(pair[1])).order, pair[0])
    )
    return [name for _, name in indexed]
