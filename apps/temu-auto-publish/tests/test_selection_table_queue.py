"""Tests for SelectionTableQueue."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data_processor.selection_table_queue import (
    SelectionTableEmptyError,
    SelectionTableFormatError,
    SelectionTableQueue,
)
from src.data_processor.selection_table_reader import SelectionTableReader


def _write_selection_file(target: Path, names: list[str]) -> None:
    df = pd.DataFrame(
        {
            "主品负责人": ["Alex"] * len(names),
            "产品名称": names,
            "标题后缀": [f"A{i:04d}" for i in range(1, len(names) + 1)],
            "采集数量": [5] * len(names),
        }
    )
    df.to_excel(target, index=False)


def _read_rows(path: Path) -> list:
    reader = SelectionTableReader()
    return reader.read_excel(str(path))


def test_pop_next_batch_updates_source(tmp_path):
    selection_file = tmp_path / "selection.xlsx"
    _write_selection_file(selection_file, ["商品1", "商品2", "商品3"])

    queue = SelectionTableQueue(selection_file, archive_root=tmp_path / "processed")

    batch = queue.pop_next_batch(batch_size=2)

    assert batch.size == 2
    assert len(_read_rows(selection_file)) == 1


def test_return_batch_restores_rows(tmp_path):
    selection_file = tmp_path / "selection.xlsx"
    _write_selection_file(selection_file, ["商品1", "商品2"])

    queue = SelectionTableQueue(selection_file, archive_root=tmp_path / "processed")
    batch = queue.pop_next_batch(batch_size=1)

    queue.return_batch(batch.rows)

    assert len(_read_rows(selection_file)) == 2


def test_archive_batch_creates_file(tmp_path):
    selection_file = tmp_path / "selection.xlsx"
    archive_dir = tmp_path / "processed"
    _write_selection_file(selection_file, ["商品1"])

    queue = SelectionTableQueue(selection_file, archive_root=archive_dir)
    batch = queue.pop_next_batch(batch_size=1)

    archived_file = queue.archive_batch(batch.rows, suffix="success")

    assert archived_file is not None
    assert archived_file.exists()
    assert archived_file.parent == archive_dir


def test_pop_empty_file_raises(tmp_path):
    selection_file = tmp_path / "empty.xlsx"
    pd.DataFrame(columns=["产品名称", "标题后缀"]).to_excel(selection_file, index=False)

    queue = SelectionTableQueue(selection_file)

    with pytest.raises(SelectionTableEmptyError):
        queue.pop_next_batch(batch_size=1)


def test_format_error_raises(tmp_path):
    selection_file = tmp_path / "broken.xlsx"
    selection_file.write_text("not an excel file", encoding="utf-8")

    queue = SelectionTableQueue(selection_file)

    with pytest.raises(SelectionTableFormatError):
        queue.pop_next_batch(batch_size=1)
