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

"""Tests for crdt_merge.async_merge — async wrappers around the merge engine."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List

import pytest
import pytest_asyncio  # noqa: F401  — ensures plugin is loaded

from crdt_merge.async_merge import amerge, amerge_stream, amerge_sorted_stream, _collect
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_iter(items):
    """Turn a plain list into an async iterator (yields one item at a time)."""
    for item in items:
        yield item

async def _async_batch_iter(items, batch_size=2):
    """Yield items in list-batches via an async iterator."""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

async def _collect_async_gen(agen) -> List:
    """Consume an async generator into a list."""
    result = []
    async for batch in agen:
        if isinstance(batch, list):
            result.extend(batch)
        else:
            result.append(batch)
    return result

# ===========================================================================
# 1–2. amerge basic merge
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_basic():
    left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    right = [{"id": 2, "name": "Bobby"}, {"id": 3, "name": "Charlie"}]
    result = await amerge(left, right, key="id")
    assert len(result) == 3
    ids = {r["id"] for r in result}
    assert ids == {1, 2, 3}

@pytest.mark.asyncio
async def test_amerge_basic_prefer_a():
    left = [{"id": 1, "v": "A"}]
    right = [{"id": 1, "v": "B"}]
    result = await amerge(left, right, key="id", prefer="a")
    assert result[0]["v"] == "A"

# ===========================================================================
# 3–4. amerge with schema
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_with_schema_lww():
    schema = MergeSchema(default=LWW())
    left = [{"id": 1, "v": 10, "_ts": 1}]
    right = [{"id": 1, "v": 20, "_ts": 2}]
    result = await amerge(left, right, key="id", schema=schema, timestamp_col="_ts")
    assert result[0]["v"] == 20

@pytest.mark.asyncio
async def test_amerge_with_schema_max():
    schema = MergeSchema(default=LWW(), score=MaxWins())
    left = [{"id": 1, "score": 100}]
    right = [{"id": 1, "score": 50}]
    result = await amerge(left, right, key="id", schema=schema)
    assert result[0]["score"] == 100

# ===========================================================================
# 5. amerge with multi-key
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_multi_key():
    left = [{"a": 1, "b": "x", "v": "old"}]
    right = [{"a": 1, "b": "x", "v": "new"}]
    result = await amerge(left, right, key=["a", "b"])
    assert len(result) == 1
    assert result[0]["v"] == "old"  # deterministic tie-breaking (lexicographic)

# ===========================================================================
# 6. amerge key=None (append + dedup)
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_no_key():
    left = [{"v": 1}, {"v": 2}]
    right = [{"v": 2}, {"v": 3}]
    result = await amerge(left, right)
    assert len(result) == 3  # deduped

# ===========================================================================
# 7–8. amerge empty input
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_empty_left():
    result = await amerge([], [{"id": 1, "v": "A"}], key="id")
    assert len(result) == 1

@pytest.mark.asyncio
async def test_amerge_both_empty():
    result = await amerge([], [])
    assert result == []

# ===========================================================================
# 9–10. amerge_stream basic
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_stream_basic():
    a = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
    b = [{"id": 2, "v": "B"}, {"id": 3, "v": "c"}]
    rows = await _collect_async_gen(amerge_stream(a, b, key="id"))
    assert len(rows) == 3

@pytest.mark.asyncio
async def test_amerge_stream_yields_lists():
    a = [{"id": i, "v": i} for i in range(10)]
    b = [{"id": i, "v": i * 10} for i in range(5, 15)]
    batches = []
    async for batch in amerge_stream(a, b, key="id", batch_size=5):
        assert isinstance(batch, list)
        batches.append(batch)
    total = sum(len(b) for b in batches)
    assert total == 15  # ids 0..14

# ===========================================================================
# 11. amerge_stream batch size
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_stream_batch_size():
    a = [{"id": i, "v": "a"} for i in range(20)]
    b = []
    batches = []
    async for batch in amerge_stream(a, b, key="id", batch_size=7):
        batches.append(batch)
    # Every batch except possibly the last should be <= 7
    for batch in batches[:-1]:
        assert len(batch) <= 7

# ===========================================================================
# 12. amerge_sorted_stream basic
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_sorted_stream_basic():
    a = [{"id": 1, "v": "a"}, {"id": 3, "v": "c"}]
    b = [{"id": 2, "v": "b"}, {"id": 3, "v": "C"}]
    rows = await _collect_async_gen(amerge_sorted_stream(a, b, key="id"))
    assert len(rows) == 3

# ===========================================================================
# 13. amerge_sorted_stream with schema
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_sorted_stream_with_schema():
    schema = MergeSchema(default=LWW())
    a = [{"id": 1, "v": 10, "_ts": 1}]
    b = [{"id": 1, "v": 20, "_ts": 2}]
    rows = await _collect_async_gen(
        amerge_sorted_stream(a, b, key="id", schema=schema, timestamp_col="_ts")
    )
    assert rows[0]["v"] == 20

# ===========================================================================
# 14–15. async iterator input
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_stream_async_iter_input():
    a_items = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
    b_items = [{"id": 2, "v": "B"}, {"id": 3, "v": "c"}]
    rows = await _collect_async_gen(
        amerge_stream(_async_iter(a_items), _async_iter(b_items), key="id")
    )
    assert len(rows) == 3

@pytest.mark.asyncio
async def test_collect_async_batch_iter():
    items = [{"id": i} for i in range(5)]
    collected = await _collect(_async_batch_iter(items, batch_size=2))
    assert len(collected) == 5

# ===========================================================================
# 16. concurrent amerge calls
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_amerge():
    left = [{"id": i, "v": i} for i in range(50)]
    right = [{"id": i, "v": i * 10} for i in range(25, 75)]

    results = await asyncio.gather(
        amerge(left, right, key="id"),
        amerge(left, right, key="id"),
        amerge(left, right, key="id"),
    )
    for r in results:
        assert len(r) == 75

# ===========================================================================
# 17–18. error propagation
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_bad_key_propagates():
    left = [{"id": 1}]
    right = [{"id": 1}]
    with pytest.raises(KeyError):
        await amerge(left, right, key="nonexistent")

@pytest.mark.asyncio
async def test_amerge_bad_type_propagates():
    with pytest.raises(TypeError):
        await amerge("not a df", "also bad", key="id")

# ===========================================================================
# 19. cancellation handling
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_cancellation():
    """Verify a cancelled amerge task does not hang."""
    left = [{"id": i, "v": i} for i in range(100)]
    right = [{"id": i, "v": i * 2} for i in range(100)]
    task = asyncio.create_task(amerge(left, right, key="id"))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

# ===========================================================================
# 20. empty stream
# ===========================================================================

@pytest.mark.asyncio
async def test_amerge_stream_empty():
    rows = await _collect_async_gen(amerge_stream([], [], key="id"))
    assert rows == []
