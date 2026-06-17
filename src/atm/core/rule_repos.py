"""Shared rule library overlay.

Register a git repo whose `rules/*.md` files are layered into the rule library
behind the local `user_config_dir/rules/`. Lookups resolve local-first so a
team-shared snippet can be overridden per machine.

Cache lives at `user_cache_dir/rule_repos/<alias>/` — a git --mirror clone.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select

from atm.core import db, git, paths
from atm.core.models import RegisteredRuleRepo

_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class RuleRepoAliasError(ValueError):
    pass


class RuleRepoExistsError(ValueError):
    pass


class RuleRepoNotFoundError(KeyError):
    pass


def _validate_alias(alias: str) -> None:
    if not _ALIAS_RE.fullmatch(alias):
        raise RuleRepoAliasError(
            f"rule-repo alias {alias!r} invalid: must be lowercase alphanumeric, _, or -"
        )


def clone_dir(alias: str) -> Path:
    return paths.rule_repos_cache_dir() / alias


def add(alias: str, url: str, *, default_ref: str = "HEAD") -> RegisteredRuleRepo:
    _validate_alias(alias)
    paths.ensure_global_dirs()
    with db.session() as session:
        if session.get(RegisteredRuleRepo, alias) is not None:
            raise RuleRepoExistsError(alias)
    dest = clone_dir(alias)
    git.get_backend().clone_bare(url, dest)
    try:
        sha = git.get_backend().resolve_ref(dest, default_ref)
    except git.GitError:
        sha = None
    entry = RegisteredRuleRepo(
        alias=alias,
        url=url,
        default_ref=default_ref,
        last_fetched_at=datetime.now(UTC),
        last_sha=sha,
    )
    # Worktree out the rules into a non-bare side dir so we can read .md files.
    _materialise_rules(alias, sha)
    with db.session() as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
    return entry


def _materialise_dir(alias: str) -> Path:
    return clone_dir(alias).parent / f"{alias}.work"


def _materialise_rules(alias: str, sha: str | None) -> None:
    """Extract the rules/ subtree at `sha` into a side worktree dir so we can
    read .md files. Uses `git archive` (no working tree on the bare cache)."""
    if sha is None:
        return
    dest = _materialise_dir(alias)
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        git.get_backend().archive(clone_dir(alias), sha, "rules", dest)
    except git.GitError:
        # No `rules/` dir at this sha — overlay is empty.
        pass


def list_repos() -> list[RegisteredRuleRepo]:
    with db.session() as session:
        rows = list(session.exec(select(RegisteredRuleRepo)).all())
    rows.sort(key=lambda r: r.alias)
    return rows


def remove(alias: str) -> None:
    with db.session() as session:
        row = session.get(RegisteredRuleRepo, alias)
        if row is None:
            raise RuleRepoNotFoundError(alias)
        session.delete(row)
        session.commit()
    git.remove_clone(clone_dir(alias))
    side = _materialise_dir(alias)
    if side.exists():
        import shutil

        shutil.rmtree(side)


def refresh(alias: str) -> RegisteredRuleRepo:
    with db.session() as session:
        row = session.get(RegisteredRuleRepo, alias)
    if row is None:
        raise RuleRepoNotFoundError(alias)
    repo_dir = clone_dir(alias)
    git.get_backend().fetch(repo_dir)
    try:
        new_sha = git.get_backend().resolve_ref(repo_dir, row.default_ref)
    except git.GitError:
        new_sha = row.last_sha
    _materialise_rules(alias, new_sha)
    with db.session() as session:
        fresh = session.get(RegisteredRuleRepo, alias)
        if fresh is None:  # pragma: no cover
            raise RuleRepoNotFoundError(alias)
        fresh.last_fetched_at = datetime.now(UTC)
        fresh.last_sha = new_sha
        session.add(fresh)
        session.commit()
        session.refresh(fresh)
    return fresh


def overlay_paths() -> list[tuple[str, Path]]:
    """Return [(alias, materialised_dir), ...] for each registered rule repo
    that successfully materialised. Used by `rules.list_all` to extend the
    local library."""
    out: list[tuple[str, Path]] = []
    for repo in list_repos():
        dir_ = _materialise_dir(repo.alias)
        if dir_.exists():
            out.append((repo.alias, dir_))
    return out
