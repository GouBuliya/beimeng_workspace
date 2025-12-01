"""Selection table queue utilities for continuous publish workflow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from loguru import logger

from .selection_table_reader import ProductSelectionRow, SelectionTableReader


class SelectionTableEmptyError(RuntimeError):
    """Raised when the selection table has no remaining rows."""


class SelectionTableFormatError(RuntimeError):
    """Raised when the selection table cannot be parsed due to format issues."""


@dataclass(slots=True)
class SelectionBatch:
    """Simple value object describing a popped batch."""

    rows: list[ProductSelectionRow]
    total_before_pop: int
    start_index: int = 1

    @property
    def size(self) -> int:
        return len(self.rows)

    def iter_with_position(
        self, page_size: int = 20
    ) -> Iterable[tuple[int, int, int, ProductSelectionRow]]:
        """Yield rows with absolute index, page index and index on page.

        Useful for UI脚本：序号>20 需翻页，点击位置可用 num % page_size 计算。
        """

        if page_size <= 0:
            raise ValueError("page_size must be positive")

        for offset, row in enumerate(self.rows):
            seq_num = self.start_index + offset
            page = (seq_num - 1) // page_size + 1
            index_on_page = seq_num % page_size or page_size
            yield seq_num, page, index_on_page, row


class SelectionTableQueue:
    """Implements a queue backed by the selection Excel file."""

    def __init__(
        self,
        selection_table_path: Path | str,
        *,
        archive_root: Path | str | None = None,
    ) -> None:
        self.selection_table_path = Path(selection_table_path).expanduser().resolve()
        self.reader = SelectionTableReader()
        self._processed_count = 0  # 用于计算序号和翻页位置
        self._cached_rows: list[ProductSelectionRow] | None = None  # 只在首次读取，后续复用

        if archive_root:
            self.archive_root = Path(archive_root).expanduser().resolve()
        else:
            self.archive_root = self._default_archive_dir()
        self.archive_root.mkdir(parents=True, exist_ok=True)
        logger.debug("SelectionTableQueue archive dir: {}", self.archive_root)

    def pop_next_batch(self, batch_size: int) -> SelectionBatch:
        """Pop the next batch of rows from the Excel file."""

        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        rows = self._load_rows()
        if not rows:
            raise SelectionTableEmptyError(f"选品表 {self.selection_table_path} 无数据，停止运行")

        batch_rows = rows[:batch_size]
        remaining_rows = rows[batch_size:]
        self._write_rows(remaining_rows)

        start_index = self._processed_count + 1
        self._processed_count += len(batch_rows)

        logger.info(
            "弹出 %s 条选品数据, 剩余 %s 条 (来源: %s, 序号起点=%s)",
            len(batch_rows),
            len(remaining_rows),
            self.selection_table_path,
            start_index,
        )

        return SelectionBatch(rows=batch_rows, total_before_pop=len(rows), start_index=start_index)

    def iter_batches(
        self, batch_size: int, *, wait_on_empty: bool = False, poll_interval: float = 3.0
    ) -> Iterable[SelectionBatch]:
        """Continuously yield batches until表空; 可选空表轮询."""

        if wait_on_empty and poll_interval <= 0:
            raise ValueError("poll_interval must be positive when wait_on_empty is True")

        while True:
            try:
                yield self.pop_next_batch(batch_size)
            except SelectionTableEmptyError:
                if not wait_on_empty:
                    break
                time.sleep(poll_interval)
                continue

    def return_batch(self, rows: Sequence[ProductSelectionRow]) -> None:
        """Push rows back to the head of the queue (e.g., when workflow failed)."""

        if not rows:
            return
        existing = self._load_rows()
        combined = list(rows) + existing
        self._write_rows(combined)
        self._processed_count = max(0, self._processed_count - len(rows))
        logger.info("已将 {} 条选品数据回滚到选品表", len(rows))

    def archive_batch(
        self,
        rows: Sequence[ProductSelectionRow],
        *,
        suffix: str | None = None,
    ) -> Path | None:
        """Persist a processed batch for auditing."""

        if not rows:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_part = f"_{suffix}" if suffix else ""
        target = self.archive_root / f"{timestamp}{suffix_part}.xlsx"

        df = self._rows_to_dataframe(rows)
        df.to_excel(target, index=False)
        logger.info("已归档 {} 条选品数据 -> {}", len(rows), target)
        return target

    def has_pending_rows(self) -> bool:
        """Quick check whether the selection table still contains rows."""

        try:
            # 只读检查，无需复制列表（性能优化）
            rows = self._load_rows(copy=False)
        except SelectionTableFormatError:
            return False
        return bool(rows)

    def _load_rows(self, *, copy: bool = True) -> list[ProductSelectionRow]:
        """加载选品行数据。

        Args:
            copy: 是否返回副本。默认 True 以防止外部修改缓存。
                  在只读场景（如 has_pending_rows）可设为 False 以提升性能。
        """
        if self._cached_rows is not None:
            # 性能优化：只读场景下避免不必要的列表复制
            return list(self._cached_rows) if copy else self._cached_rows

        try:
            rows = self.reader.read_excel(str(self.selection_table_path))
            self._cached_rows = list(rows)
            return list(rows) if copy else rows
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"选品表不存在: {self.selection_table_path}") from exc
        except Exception as exc:
            raise SelectionTableFormatError(f"选品表格式异常，无法解析: {exc}") from exc

    def _write_rows(self, rows: Sequence[ProductSelectionRow]) -> None:
        df = self._rows_to_dataframe(rows)
        # pandas 会在空 DataFrame 中保留列结构，方便继续填写
        df.to_excel(self.selection_table_path, index=False)
        self._cached_rows = list(rows)

    @staticmethod
    def _rows_to_dataframe(rows: Sequence[ProductSelectionRow]) -> pd.DataFrame:
        if not rows:
            columns = list(ProductSelectionRow.model_fields.keys())
            return pd.DataFrame(columns=columns)
        return pd.DataFrame([row.model_dump(mode="json") for row in rows])

    @staticmethod
    def _default_archive_dir() -> Path:
        app_root = Path(__file__).resolve().parents[3]
        return app_root / "data" / "output" / "processed"
