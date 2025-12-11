# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""Async wrappers for crdt-merge operations.

Enables non-blocking merge in async applications.
Uses asyncio.to_thread for CPU-bound merge operations.

Usage:
    from crdt_merge.async_merge import amerge, amerge_stream, amerge_sorted_stream

    # Async merge (runs sync merge in thread pool)
    result = await amerge(left, right, key="id")

    # Async streaming merge
    async for batch in amerge_stream(source_a, source_b, key="id"):
        process(batch)

    # Async sorted streaming merge
    async for batch in amerge_sorted_stream(sorted_a, sorted_b, key="id"):
        process(batch)
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from crdt_merge.dataframe import merge as sync_merge
from crdt_merge.streaming import merge_stream, merge_sorted_stream


async def amerge(
    left: Any,
    right: Any,
    key: Optional[Union[str, List[str]]] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = "latest",
    schema: Optional[Any] = None,
    **kwargs: Any,
) -> Any:
    """Async version of dataframe.merge(). Runs in thread pool.

    All arguments are forwarded to :func:`crdt_merge.dataframe.merge`.
    The synchronous merge is executed in the default asyncio thread-pool
    executor so the event loop remains free.

    Args:
        left: First DataFrame (pandas, polars, or list of dicts).
        right: Second DataFrame.
        key: Column(s) to match rows on.
        timestamp_col: Column with timestamps for LWW resolution.
        prefer: Conflict resolution preference ('latest', 'a', or 'b').
        schema: Optional MergeSchema for per-column strategies.
        **kwargs: Additional keyword arguments forwarded to sync merge.

    Returns:
        Merged result in the same type as *left*.
    """
    return await asyncio.to_thread(
        sync_merge,
        left,
        right,
        key=key,
        timestamp_col=timestamp_col,
        prefer=prefer,
        schema=schema,
        **kwargs,
    )


async def amerge_stream(
    source_a: Any,
    source_b: Any,
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
) -> AsyncIterator[List[dict]]:
    """Async streaming merge. Wraps :func:`streaming.merge_stream`.

    Accepts both sync iterables and async iterators as sources.
    The sync merge_stream is run in a thread; batches are yielded
    asynchronously.

    Args:
        source_a: First source (sync iterable or async iterator of dicts).
        source_b: Second source.
        key: Primary key field name.
        batch_size: Max rows per output batch.
        schema: Optional MergeSchema for per-column strategies.
        timestamp_col: Column for LWW timestamps.

    Yields:
        Lists of merged dicts, each up to *batch_size* rows.
    """
    records_a = await _collect(source_a)
    records_b = await _collect(source_b)

    def _run_stream() -> List[List[dict]]:
        return list(
            merge_stream(
                records_a,
                records_b,
                key=key,
                batch_size=batch_size,
                schema=schema,
                timestamp_col=timestamp_col,
            )
        )

    batches: List[List[dict]] = await asyncio.to_thread(_run_stream)
    for batch in batches:
        yield batch


async def amerge_sorted_stream(
    source_a: Any,
    source_b: Any,
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
) -> AsyncIterator[List[dict]]:
    """Async sorted streaming merge. Sources **must** be pre-sorted by key.

    Wraps :func:`streaming.merge_sorted_stream` in a thread and yields
    batches asynchronously.

    Args:
        source_a: First pre-sorted source.
        source_b: Second pre-sorted source.
        key: Sort/merge key field name.
        batch_size: Max rows per output batch.
        schema: Optional MergeSchema.
        timestamp_col: Column for LWW timestamps.

    Yields:
        Lists of merged dicts, each up to *batch_size* rows.
    """
    records_a = await _collect(source_a)
    records_b = await _collect(source_b)

    def _run_sorted() -> List[List[dict]]:
        return list(
            merge_sorted_stream(
                records_a,
                records_b,
                key=key,
                batch_size=batch_size,
                schema=schema,
                timestamp_col=timestamp_col,
            )
        )

    batches: List[List[dict]] = await asyncio.to_thread(_run_sorted)
    for batch in batches:
        yield batch


async def _collect(source: Any) -> Any:
    """Collect from an async iterator if needed; pass through sync iterables.

    If *source* implements ``__aiter__``, it is consumed into a flat list.
    Items that are themselves lists (batched async sources) are flattened.
    Sync iterables (list, generator, etc.) are returned unchanged.
    """
    if hasattr(source, "__aiter__"):
        result: List[Any] = []
        async for item in source:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result
    return source
