from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from aim.core import format as format_mod


class _PydanticRow(BaseModel):
    name: str
    count: int
    description: str | None = None


@dataclass
class _DataclassRow:
    name: str
    count: int


def test_render_compact_emits_ndjson(capsys: pytest.CaptureFixture[str]) -> None:
    format_mod.render_compact(
        [{"name": "a", "count": 1}, {"name": "b", "count": 2}],
        columns=["name", "count"],
    )
    out, _ = capsys.readouterr()
    lines = out.strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"name": "a", "count": 1}
    assert json.loads(lines[1]) == {"name": "b", "count": 2}


def test_render_compact_with_row_extractor(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [_PydanticRow(name="x", count=5, description="long")]
    format_mod.render_compact(
        rows,
        columns=["qualified", "title"],
        row_extractor={"qualified": "name", "title": "description"},
    )
    out, _ = capsys.readouterr()
    assert json.loads(out.strip()) == {"qualified": "x", "title": "long"}


def test_render_compact_compact_columns_omit_others(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = [{"name": "a", "count": 1, "extra": "drop me"}]
    format_mod.render_compact(
        rows,
        columns=["name", "count", "extra"],
        compact_columns=["name", "count"],
    )
    out, _ = capsys.readouterr()
    assert json.loads(out.strip()) == {"name": "a", "count": 1}


def test_render_compact_empty_rows_emits_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    format_mod.render_compact([], columns=["name"])
    out, _ = capsys.readouterr()
    assert out == ""


def test_render_dispatches_compact(capsys: pytest.CaptureFixture[str]) -> None:
    format_mod.render(
        [{"name": "a"}],
        format_mod.OutputFormat.COMPACT,
        columns=["name"],
    )
    out, _ = capsys.readouterr()
    assert json.loads(out.strip()) == {"name": "a"}


def test_serialize_flattens_common_types() -> None:
    assert format_mod._serialize(Path("/foo")) == "/foo"
    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert format_mod._serialize(dt) == "2024-01-02T03:04:05+00:00"
    assert format_mod._serialize(_PydanticRow(name="n", count=1)) == {
        "name": "n",
        "count": 1,
        "description": None,
    }
    assert format_mod._serialize(_DataclassRow(name="n", count=1)) == {
        "name": "n",
        "count": 1,
    }
