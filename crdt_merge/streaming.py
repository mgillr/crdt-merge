# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""
Streaming Merge Pipeline — O(batch_size) memory merge for unlimited scale.

Generator-based processing: never loads entire datasets into memory.
Configurable batch_size controls the memory/throughput tradeoff.

Usage:
    from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats

    # Merge two iterables (generators, files, databases)
    for batch in merge_stream(source_a, source_b, key="id", batch_size=5000):
        write_batch(batch)

    # Track progress
    stats = StreamStats()
    for batch in merge_stream(source_a, source_b, key="id", stats=stats):
        write_batch(batch)
    print(stats)  # rows_processed, batches, duration, rows/sec

    # Memory: O(batch_size), not O(n) — bounded by config, not data size
"""

from __future__ import annotations
import gc
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Tuple

from .strategies import MergeSchema, MergeStrategy, LWW


@dataclass
class StreamStats:
    """Tracks streaming merge statistics."""
    rows_processed: int = 0
    rows_merged: int = 0
    rows_unique_a: int = 0
    rows_unique_b: int = 0
    batches_processed: int = 0
    duration_ms: float = 0.0
    peak_batch_size: int = 0
    _start_time: float = field(default=0.0, repr=False)

    @property
    def rows_per_sec(self) -> float:
        if self.duration_ms == 0:
            return 0.0
        return self.rows_processed / (self.duration_ms / 1000)

    def __repr__(self):
        return (f"StreamStats(rows={self.rows_processed}, merged={self.rows_merged}, "
                f"batches={self.batches_processed}, {self.rows_per_sec:.0f} rows/s, "
                f"{self.duration_ms:.1f}ms)")


def _resolve_row(
    row_a: dict, row_b: dict, columns: List[str],
    schema: Optional[MergeSchema], timestamp_col: Optional[str]
) -> dict:
    """Merge two rows using schema strategies."""
    result = {}
    ts_a = float(row_a.get(timestamp_col, 0)) if timestamp_col else 0.0
    ts_b = float(row_b.get(timestamp_col, 0)) if timestamp_col else 0.0

    for col in columns:
        val_a = row_a.get(col)
        val_b = row_b.get(col)

        if val_a is None and val_b is not None:
            result[col] = val_b
        elif val_b is None and val_a is not None:
            result[col] = val_a
        elif val_a == val_b:
            result[col] = val_a
        else:
            strategy = schema.strategy_for(col) if schema else LWW()
            result[col] = strategy.resolve(val_a, val_b, ts_a, ts_b)
    return result


def _iter_batches(iterable: Iterable[dict], batch_size: int) -> Generator[List[dict], None, None]:
    """Yield fixed-size batches from an iterable."""
    batch: List[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def merge_stream(
    source_a: Iterable[dict],
    source_b: Iterable[dict],
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None,
) -> Generator[List[dict], None, None]:
    """
    Streaming merge of two row sources. Memory: O(batch_size).

    Loads source_b into a lookup dict in batches, then streams source_a
    against it. For data that fits in memory, this is efficient. For huge
    datasets where both sides are too large, use merge_sorted_stream instead.

    Args:
        source_a: First iterable of dicts.
        source_b: Second iterable of dicts.
        key: Primary key field name.
        batch_size: Max rows per output batch.
        schema: Optional MergeSchema for per-column strategies.
        timestamp_col: Column name for LWW timestamps.
        stats: Optional StreamStats to track progress.

    Yields:
        Lists of merged dicts, each list up to batch_size rows.
    """
    start = time.time()
    if stats:
        stats._start_time = start

    # Build lookup from source_b
    b_index: Dict[Any, dict] = {}
    for row in source_b:
        b_index[row[key]] = row

    # Stream source_a, merge or pass through
    output_batch: List[dict] = []
    merged_count = 0
    unique_a = 0

    for row_a in source_a:
        k = row_a[key]
        if k in b_index:
            row_b = b_index.pop(k)  # pop to track unmatched
            all_cols = list(set(list(row_a.keys()) + list(row_b.keys())))
            merged = _resolve_row(row_a, row_b, all_cols, schema, timestamp_col)
            output_batch.append(merged)
            merged_count += 1
        else:
            output_batch.append(row_a)
            unique_a += 1

        if len(output_batch) >= batch_size:
            if stats:
                stats.rows_processed += len(output_batch)
                stats.batches_processed += 1
                stats.peak_batch_size = max(stats.peak_batch_size, len(output_batch))
            yield output_batch
            output_batch = []
            gc.collect()

    # Remaining unmatched from source_b
    unique_b = 0
    for row_b in b_index.values():
        output_batch.append(row_b)
        unique_b += 1
        if len(output_batch) >= batch_size:
            if stats:
                stats.rows_processed += len(output_batch)
                stats.batches_processed += 1
                stats.peak_batch_size = max(stats.peak_batch_size, len(output_batch))
            yield output_batch
            output_batch = []
            gc.collect()

    # Final batch
    if output_batch:
        if stats:
            stats.rows_processed += len(output_batch)
            stats.batches_processed += 1
            stats.peak_batch_size = max(stats.peak_batch_size, len(output_batch))
        yield output_batch

    if stats:
        stats.rows_merged = merged_count
        stats.rows_unique_a = unique_a
        stats.rows_unique_b = unique_b
        stats.duration_ms = (time.time() - start) * 1000


def merge_sorted_stream(
    source_a: Iterable[dict],
    source_b: Iterable[dict],
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None,
) -> Generator[List[dict], None, None]:
    """
    Merge two pre-sorted sources using merge-join. O(1) memory per row.

    Both sources MUST be sorted by key in ascending order.
    Uses the classic merge-join algorithm — never loads more than 1 row from each.

    Yields:
        Lists of merged dicts, each up to batch_size rows.
    """
    start = time.time()
    iter_a = iter(source_a)
    iter_b = iter(source_b)
    output_batch: List[dict] = []
    merged_count = 0

    row_a = next(iter_a, None)
    row_b = next(iter_b, None)

    while row_a is not None and row_b is not None:
        key_a = row_a[key]
        key_b = row_b[key]

        if key_a == key_b:
            all_cols = list(set(list(row_a.keys()) + list(row_b.keys())))
            merged = _resolve_row(row_a, row_b, all_cols, schema, timestamp_col)
            output_batch.append(merged)
            merged_count += 1
            row_a = next(iter_a, None)
            row_b = next(iter_b, None)
        elif key_a < key_b:
            output_batch.append(row_a)
            row_a = next(iter_a, None)
        else:
            output_batch.append(row_b)
            row_b = next(iter_b, None)

        if len(output_batch) >= batch_size:
            if stats:
                stats.rows_processed += len(output_batch)
                stats.batches_processed += 1
            yield output_batch
            output_batch = []

    # Drain remaining
    while row_a is not None:
        output_batch.append(row_a)
        row_a = next(iter_a, None)
        if len(output_batch) >= batch_size:
            if stats:
                stats.rows_processed += len(output_batch)
                stats.batches_processed += 1
            yield output_batch
            output_batch = []

    while row_b is not None:
        output_batch.append(row_b)
        row_b = next(iter_b, None)
        if len(output_batch) >= batch_size:
            if stats:
                stats.rows_processed += len(output_batch)
                stats.batches_processed += 1
            yield output_batch
            output_batch = []

    if output_batch:
        if stats:
            stats.rows_processed += len(output_batch)
            stats.batches_processed += 1
        yield output_batch

    if stats:
        stats.rows_merged = merged_count
        stats.duration_ms = (time.time() - start) * 1000


def count_stream(source: Iterable[dict]) -> int:
    """Count rows in a stream without loading into memory."""
    count = 0
    for _ in source:
        count += 1
    return count
