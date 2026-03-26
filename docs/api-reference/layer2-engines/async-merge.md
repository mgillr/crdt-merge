# `crdt_merge/async_merge.py`

> Async wrappers for crdt-merge operations.

Enables non-blocking merge in async applications.
Uses asyncio.to_thread for CPU-bound merge operations.

Usage:
    from crdt_merge.async_merge import amerge, amerge_stream, amerge_sorted_stream

    # Async merge (runs sync merge in thread pool)
    resul

**Source:** `crdt_merge/async_merge.py` | **Lines:** 140 *(corrected 2026-03-31 — was 188; AST-verified actual: 140)*

> **Missing `__all__`**: This module does not define `__all__`, making its public API boundary ambiguous. See issue LAY2-004.

---

## Functions

### `async amerge(left: Any, right: Any, key: Optional[Union[str, List[str]]] = None, timestamp_col: Optional[str] = None, prefer: str = 'latest', schema: Optional[Any] = None, **kwargs: Any) → Any`

Async version of dataframe.merge(). Runs in thread pool.

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

### `async amerge_stream(source_a: Any, source_b: Any, key: str = 'id', batch_size: int = 5000, schema: Optional[Any] = None, timestamp_col: Optional[str] = None) → AsyncIterator[List[dict]]`

Async streaming merge. Wraps :func:`streaming.merge_stream`.

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

### `async amerge_sorted_stream(source_a: Any, source_b: Any, key: str = 'id', batch_size: int = 5000, schema: Optional[Any] = None, timestamp_col: Optional[str] = None) → AsyncIterator[List[dict]]`

Async sorted streaming merge. Sources **must** be pre-sorted by key.

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

### `async _collect(source: Any) → Any`

Collect from an async iterator if needed; pass through sync iterables.

    If *source* implements ``__aiter__``, it is consumed into a flat list.
    Items that are themselves lists (batched async sources) are flattened.
    Sync iterables (list, generator, etc.) are returned unchanged.

