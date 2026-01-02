# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.parallel — thread-pool parallel merge engine."""

from __future__ import annotations

import concurrent.futures
import threading
from typing import List

import pytest

from crdt_merge.parallel import (
    parallel_merge,
    parallel_merge_arrow,
    _compute_chunks,
    _SEQUENTIAL_THRESHOLD,
)
from crdt_merge.strategies import MergeSchema, LWW, MaxWins


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dataset(n: int, key: str = "id", prefix: str = "") -> List[dict]:
    """Generate a list of *n* dicts with sequential keys."""
    return [{key: i, "value": f"{prefix}{i}"} for i in range(n)]


# ===========================================================================
# 1–2. parallel_merge basic
# ===========================================================================

def test_parallel_merge_basic_small():
    """Small dataset → should fallback to sequential but still produce correct result."""
    left = [{"id": i, "v": f"a{i}"} for i in range(5)]
    right = [{"id": i, "v": f"b{i}"} for i in range(3, 8)]
    result = parallel_merge(left, right, key="id")
    assert len(result) == 8  # ids 0..7


def test_parallel_merge_basic_result_correctness():
    left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    right = [{"id": 2, "name": "Bobby"}, {"id": 3, "name": "Charlie"}]
    result = parallel_merge(left, right, key="id")
    ids = {r["id"] for r in result}
    assert ids == {1, 2, 3}
    # id=2 conflict → "Bobby" wins (b-wins default)
    row2 = [r for r in result if r["id"] == 2][0]
    assert row2["name"] == "Bobby"


# ===========================================================================
# 3. parallel_merge with schema
# ===========================================================================

def test_parallel_merge_with_schema():
    schema = MergeSchema(default=LWW(), score=MaxWins())
    left = [{"id": 1, "score": 100}]
    right = [{"id": 1, "score": 50}]
    result = parallel_merge(left, right, key="id", schema=schema)
    assert result[0]["score"] == 100


# ===========================================================================
# 4. parallel_merge multi-key
# ===========================================================================

def test_parallel_merge_multi_key():
    left = [{"a": 1, "b": "x", "v": "old"}]
    right = [{"a": 1, "b": "x", "v": "new"}]
    result = parallel_merge(left, right, key=["a", "b"])
    assert len(result) == 1
    assert result[0]["v"] == "new"


# ===========================================================================
# 5–6. chunk_size configuration
# ===========================================================================

def test_chunk_size_splits():
    """With tiny chunk_size, _compute_chunks should produce multiple chunks."""
    left = _make_dataset(20, prefix="L")
    right = _make_dataset(20, prefix="R")
    chunks = _compute_chunks(left, right, key="id", chunk_size=5)
    assert len(chunks) == 4  # 20 keys / 5 = 4 chunks


def test_chunk_size_large_single_chunk():
    """chunk_size larger than key count → single chunk."""
    left = _make_dataset(10, prefix="L")
    right = _make_dataset(10, prefix="R")
    chunks = _compute_chunks(left, right, key="id", chunk_size=100)
    assert len(chunks) == 1


# ===========================================================================
# 7. max_workers configuration
# ===========================================================================

def test_max_workers_accepted():
    """max_workers param is accepted without error."""
    left = [{"id": 1, "v": "a"}]
    right = [{"id": 2, "v": "b"}]
    result = parallel_merge(left, right, key="id", max_workers=2)
    assert len(result) == 2


# ===========================================================================
# 8–9. fallback to sequential for small datasets
# ===========================================================================

def test_fallback_small_dataset():
    """Datasets below threshold should still produce correct output."""
    n = _SEQUENTIAL_THRESHOLD // 3  # well below threshold
    left = _make_dataset(n, prefix="L")
    right = _make_dataset(n, prefix="R")
    result = parallel_merge(left, right, key="id")
    assert len(result) == n  # same keys, so same count


def test_fallback_no_key():
    """key=None always falls back to sequential (append + dedup)."""
    left = [{"v": 1}, {"v": 2}]
    right = [{"v": 2}, {"v": 3}]
    result = parallel_merge(left, right, key=None)
    assert len(result) == 3


# ===========================================================================
# 10–11. _compute_chunks correctness
# ===========================================================================

def test_compute_chunks_all_keys_covered():
    left = _make_dataset(15, prefix="L")
    right = _make_dataset(15, prefix="R")
    chunks = _compute_chunks(left, right, key="id", chunk_size=5)
    all_ids: set = set()
    for ca, cb in chunks:
        all_ids.update(r["id"] for r in ca)
        all_ids.update(r["id"] for r in cb)
    assert all_ids == set(range(15))


def test_compute_chunks_no_key():
    chunks = _compute_chunks([{"v": 1}], [{"v": 2}], key=None, chunk_size=10)
    assert len(chunks) == 1


# ===========================================================================
# 12. key-aligned chunking
# ===========================================================================

def test_key_aligned_chunking():
    """Records with the same key must end up in the same chunk."""
    left = [{"id": i, "side": "L"} for i in range(10)]
    right = [{"id": i, "side": "R"} for i in range(10)]
    chunks = _compute_chunks(left, right, key="id", chunk_size=3)
    for ca, cb in chunks:
        keys_a = {r["id"] for r in ca}
        keys_b = {r["id"] for r in cb}
        # Every key present on both sides should appear in both chunk halves
        assert keys_a == keys_b


# ===========================================================================
# 13–14. empty input
# ===========================================================================

def test_parallel_merge_empty_left():
    result = parallel_merge([], [{"id": 1, "v": "A"}], key="id")
    assert len(result) == 1


def test_parallel_merge_both_empty():
    result = parallel_merge([], [])
    assert result == []


# ===========================================================================
# 15. single-key dataset
# ===========================================================================

def test_single_key_dataset():
    left = [{"id": 1, "v": "old"}]
    right = [{"id": 1, "v": "new"}]
    result = parallel_merge(left, right, key="id")
    assert len(result) == 1
    assert result[0]["v"] == "new"


# ===========================================================================
# 16. error in worker propagated
# ===========================================================================

def test_worker_error_propagated():
    """Errors inside worker threads must surface to the caller."""
    left = [{"id": 1}]
    right = [{"id": 1}]
    with pytest.raises(KeyError):
        parallel_merge(left, right, key="nonexistent")


# ===========================================================================
# 17. thread safety
# ===========================================================================

def test_thread_safety():
    """Run parallel_merge from multiple threads concurrently."""
    left = _make_dataset(50, prefix="L")
    right = _make_dataset(50, prefix="R")
    results: list = [None] * 4
    errors: list = []

    def run(idx: int):
        try:
            results[idx] = parallel_merge(left, right, key="id")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    for r in results:
        assert r is not None
        assert len(r) == 50


# ===========================================================================
# 18. parallel_merge_arrow (may not have pyarrow)
# ===========================================================================

def test_parallel_merge_arrow_fallback():
    """Without pyarrow installed, parallel_merge_arrow falls back gracefully."""
    left = [{"id": 1, "v": "a"}]
    right = [{"id": 2, "v": "b"}]
    result = parallel_merge_arrow(left, right, key="id")
    assert len(result) == 2


# ===========================================================================
# 19. parallel_merge_arrow result correctness
# ===========================================================================

def test_parallel_merge_arrow_correctness():
    left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    right = [{"id": 2, "name": "Bobby"}, {"id": 3, "name": "Charlie"}]
    result = parallel_merge_arrow(left, right, key="id")
    # Result may be a pyarrow Table or list of dicts depending on pyarrow availability
    if isinstance(result, list):
        ids = {r["id"] for r in result}
    else:
        # pyarrow Table — convert to Python
        ids = set(result.column("id").to_pylist())
    assert ids == {1, 2, 3}


# ===========================================================================
# 20. large dataset (10K+ rows)
# ===========================================================================

def test_large_dataset():
    """Merge 6K + 6K rows — triggers parallel path (total > 10K)."""
    n = 6000
    left = [{"id": i, "v": f"L{i}"} for i in range(n)]
    right = [{"id": i, "v": f"R{i}"} for i in range(n // 2, n + n // 2)]
    result = parallel_merge(left, right, key="id", chunk_size=2000)
    expected_ids = set(range(n + n // 2))
    actual_ids = {r["id"] for r in result}
    assert actual_ids == expected_ids
