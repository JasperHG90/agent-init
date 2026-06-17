"""Tests for the additive schema migrator in `db.py`.

Repros the user-hit crash: an existing SQLite DB created before the
`prereqs`/`provides` columns were added must still work after upgrade.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlmodel import select

from aim.core import db
from aim.core.models import SkillIndex


def test_missing_column_is_added(home: Path) -> None:
    # Pre-create the SQLite file with a legacy schema (no prereqs/provides).
    db_path = home / "data" / "aim.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_conn = sqlite3.connect(db_path)
    legacy_conn.execute(
        """
        CREATE TABLE skillindex (
            qualified_name VARCHAR PRIMARY KEY,
            repo_alias VARCHAR,
            skill_name VARCHAR,
            source_path VARCHAR,
            title VARCHAR,
            description VARCHAR,
            indexed_at_sha VARCHAR
        )
        """
    )
    legacy_conn.execute(
        "INSERT INTO skillindex (qualified_name, repo_alias, skill_name, source_path, indexed_at_sha) "
        "VALUES ('legacy/foo', 'legacy', 'foo', 'skills/foo', 'abc123')"
    )
    legacy_conn.commit()
    legacy_conn.close()

    db.reset_engine()
    db.get_engine()  # triggers create_all + _migrate_schema

    with db.session() as s:
        rows = list(s.exec(select(SkillIndex)).all())
    assert len(rows) == 1
    row = rows[0]
    assert row.qualified_name == "legacy/foo"
    # New columns now exist with their defaults.
    assert row.prereqs == ""
    assert row.provides == ""


def test_migration_is_idempotent(home: Path) -> None:
    """Running get_engine twice doesn't fail (ALTER TABLE ADD COLUMN errors
    on a second run if not skipped)."""
    db.get_engine()
    db.reset_engine()
    db.get_engine()
