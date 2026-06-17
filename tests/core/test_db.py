from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from atm.core import db
from atm.core.models import RegisteredRepo


def test_engine_creates_tables(home: Path) -> None:
    engine = db.get_engine()
    assert engine is not None
    with db.session() as s:
        result = s.exec(select(RegisteredRepo)).all()
        assert result == []


def test_round_trip_registered_repo(home: Path) -> None:
    db.get_engine()
    with db.session() as s:
        s.add(RegisteredRepo(alias="anthropic", url="https://github.com/anthropics/skills"))
        s.commit()
    with db.session() as s:
        rows = s.exec(select(RegisteredRepo)).all()
        assert len(rows) == 1
        assert rows[0].alias == "anthropic"
