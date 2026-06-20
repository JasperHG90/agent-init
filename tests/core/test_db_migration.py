"""Tests for the Alembic-managed schema in `db.py`.

The database is built and migrated entirely by Alembic (greenfield — no
pre-Alembic databases to adopt).
"""

from __future__ import annotations

from pathlib import Path

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
