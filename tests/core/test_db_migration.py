"""Tests for the Alembic-managed schema in `db.py`.

The database is built and migrated entirely by Alembic (greenfield — no
pre-Alembic databases to adopt).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from aim.core import db


def test_fresh_db_is_created_at_head(home: Path) -> None:
    db.reset_engine()
    db.get_engine()  # upgrade head runs the full revision chain, creating every table.
    with db.session() as s:
        live = inspect(s.connection())
        assert live.has_table("skillindex")
        assert live.has_table("registeredrepo")
        assert live.has_table("archetypeindex")
        assert live.has_table("alembic_version")


def test_migration_is_idempotent(home: Path) -> None:
    """Running get_engine repeatedly must not fail (upgrade head is idempotent)."""
    db.get_engine()
    db.reset_engine()
    db.get_engine()


def test_at_head_launch_skips_alembic_upgrade(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A launch against an already-at-head DB must not run the Alembic upgrade.

    The fresh build runs the real upgrade once; a subsequent engine build on the same
    (now at-head) database must short-circuit on the cheap revision check and never call
    `command.upgrade` again.
    """
    import alembic.command as alembic_command

    real_upgrade = alembic_command.upgrade
    calls: list[str] = []

    def spy(cfg: object, revision: str, *args: object, **kwargs: object) -> None:
        calls.append(revision)
        real_upgrade(cfg, revision, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(alembic_command, "upgrade", spy)

    db.reset_engine()
    db.get_engine()  # fresh DB -> full upgrade runs once
    assert calls == ["head"]

    db.reset_engine()
    db.get_engine()  # already at head -> must not upgrade again
    assert calls == ["head"]


def test_head_revision_matches_script_head(home: Path) -> None:
    """`db.HEAD_REVISION` must equal Alembic's script head, or the cheap check rots.

    This is the one place a test imports Alembic: it pins the constant the hot path
    relies on to the real head so adding a migration without bumping it fails loudly.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(db._MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_current_head() == db.HEAD_REVISION
