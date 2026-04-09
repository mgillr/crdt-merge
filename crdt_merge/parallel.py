# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Thread-pool parallel merge for large datasets.

Splits datasets into chunks by key range, merges each chunk in parallel
using a :class:`concurrent.futures.ThreadPoolExecutor`, then combines the
results.  Automatic fallback to sequential merge for small datasets
(< 10 000 rows total) or when no key is specified.

Usage:
    from crdt_merge.parallel import parallel_merge, parallel_merge_arrow

    # Parallel merge (auto-chunked)
    merged = parallel_merge(left, right, key="id", chunk_size=50000)

    # Arrow-backed (falls back if pyarrow unavailable)
    merged = parallel_merge_arrow(left, right, key="id")
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple, Union

from crdt_merge.dataframe import merge as sync_merge, _to_records, _from_records

__all__ = [
    "parallel_merge",
    "parallel_merge_arrow",
]

# ---------------------------------------------------------------------------
# Threshold below which parallelism adds more overhead than benefit.
# ---------------------------------------------------------------------------
_SEQUENTIAL_THRESHOLD = 10_000

def parallel_merge(
    left: Any,
    right: Any,
    key: Optional[Union[str, List[str]]] = None,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
    chunk_size: int = 50_000,
    max_workers: Optional[int] = None,
    prefer: str = "latest",
) -> Any:
    """Parallel merge using a thread pool.

    Falls back to the sequential :func:`crdt_merge.dataframe.merge` when the
    total number of rows is below *_SEQUENTIAL_THRESHOLD* or when *key* is
    ``None``.

    Records are split into chunks so that **all rows sharing a given key end
    up in the same chunk** (key-aligned chunking).  Each chunk pair is merged
    independently; results are then concatenated.

    Args:
        left: First dataset (pandas/polars DataFrame or list of dicts).
        right: Second dataset.
        key: Column(s) to match rows on.
        schema: Optional MergeSchema for per-column strategies.
        timestamp_col: Column for LWW timestamps.
        chunk_size: Approximate number of *unique keys* per chunk.
        max_workers: Max threads (``None`` → executor default).
        prefer: Conflict resolution preference.

    Returns:
        Merged dataset in the same type as *left*.
    """
    records_a, cols_a, lib_a = _to_records(left)
    records_b, cols_b, lib_b = _to_records(right)

    total = len(records_a) + len(records_b)

    # Fallback for small datasets or no key
    if total < _SEQUENTIAL_THRESHOLD or key is None:
        return sync_merge(
            left, right, key=key, schema=schema,
            timestamp_col=timestamp_col, prefer=prefer,
        )

    # Compute key-aligned chunks
    chunks = _compute_chunks(records_a, records_b, key, chunk_size)

    if len(chunks) <= 1:
        return sync_merge(
            left, right, key=key, schema=schema,
            timestamp_col=timestamp_col, prefer=prefer,
        )

    # Parallel merge each chunk pair
    merged_records: List[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for chunk_a, chunk_b in chunks:
            futures.append(
                executor.submit(
                    sync_merge,
                    chunk_a,
                    chunk_b,
                    key=key,
                    schema=schema,
                    timestamp_col=timestamp_col,
                    prefer=prefer,
                )
            )
        errors = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if isinstance(result, list):
                    merged_records.extend(result)
                else:
                    # DataFrame result -- convert to records
                    recs, _, _ = _to_records(result)
                    merged_records.extend(recs)
            except Exception as e:
                errors.append(e)
        if errors:
            raise RuntimeError(f"parallel_merge: {len(errors)} worker(s) failed: {errors}")

    all_columns = list(dict.fromkeys(cols_a + [c for c in cols_b if c not in cols_a]))
    return _from_records(merged_records, all_columns, lib_a)

def parallel_merge_arrow(
    left: Any,
    right: Any,
    key: Optional[Union[str, List[str]]] = None,
    schema: Optional[Any] = None,
    chunk_size: int = 100_000,
    max_workers: Optional[int] = None,
) -> Any:
    """Parallel merge using the Arrow backend.

    Falls back to :func:`parallel_merge` when PyArrow is not installed.

    Args:
        left: First dataset.
        right: Second dataset.
        key: Column(s) to match rows on.
        schema: Optional MergeSchema.
        chunk_size: Approximate keys per chunk.
        max_workers: Max threads.

    Returns:
        Merged dataset.
    """
    # Handle empty PyArrow tables gracefully
    try:
        import pyarrow as _pa
        if isinstance(left, _pa.Table) and isinstance(right, _pa.Table):
            if left.num_rows == 0 and right.num_rows == 0:
                return _pa.table({})
            if left.num_columns == 0 and right.num_columns == 0:
                return _pa.table({})
            if left.num_rows == 0:
                return right
            if right.num_rows == 0:
                return left
    except ImportError:
        pass

    try:
        from crdt_merge.arrow import ArrowMerge  # type: ignore[import-untyped]  # lazy import avoids circular dep; module lacks py.typed

        engine = ArrowMerge(schema=schema)
        return engine.merge(left, right, key=key)
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: convert PyArrow tables to list of dicts for parallel_merge
    try:
        import pyarrow as _pa
        if isinstance(left, _pa.Table):
            left = left.to_pylist()
        if isinstance(right, _pa.Table):
            right = right.to_pylist()
    except ImportError:
        pass

    return parallel_merge(
        left, right, key=key, schema=schema,
        chunk_size=chunk_size, max_workers=max_workers,
    )

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_chunks(
    left: List[dict],
    right: List[dict],
    key: Optional[Union[str, List[str]]],
    chunk_size: int,
) -> List[Tuple[List[dict], List[dict]]]:
    """Split records into key-aligned chunk pairs.

    **Key-aligned** means every record that shares a given key value lands in
    the same chunk.  This guarantees correctness without a final re-merge step.

    Args:
        left: Records from the left dataset.
        right: Records from the right dataset.
        key: Key column(s).
        chunk_size: Number of unique key values per chunk.

    Returns:
        List of ``(chunk_a, chunk_b)`` tuples.
    """
    if key is None:
        return [(left, right)]

    # Normalise key
    key_cols: List[str] = [key] if isinstance(key, str) else list(key)

    def _get_key(record: dict) -> Any:
        if len(key_cols) == 1:
            return record.get(key_cols[0])
        return tuple(record.get(k) for k in key_cols)

    # Gather all unique keys and sort for deterministic chunking
    all_keys = sorted(
        set(_get_key(r) for r in left) | set(_get_key(r) for r in right),
        key=lambda x: str(x),
    )

    if not all_keys:
        return [(left, right)]

    # Partition keys into chunk-sized groups
    key_chunks: List[set] = []
    for i in range(0, len(all_keys), chunk_size):
        key_chunks.append(set(all_keys[i:i + chunk_size]))

    # Assign records to the correct chunk
    chunks: List[Tuple[List[dict], List[dict]]] = []
    for key_set in key_chunks:
        chunk_a = [r for r in left if _get_key(r) in key_set]
        chunk_b = [r for r in right if _get_key(r) in key_set]
        if chunk_a or chunk_b:
            chunks.append((chunk_a, chunk_b))

    return chunks
