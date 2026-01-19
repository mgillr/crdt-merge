# Async Merge

Async/await wrappers for non-blocking merge operations.

## Quick Example

```python
from crdt_merge.async_merge import amerge, amerge_stream
result = await amerge(df_a, df_b, key="id")
```

---

## API Reference

## `crdt_merge.async_merge`

> Async wrappers for crdt-merge operations.

**Module:** `crdt_merge.async_merge`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `amerge(left: 'Any', right: 'Any', key: 'Optional[Union[str, List[str]]]' = None, timestamp_col: 'Optional[str]' = None, prefer: 'str' = 'latest', schema: 'Optional[Any]' = None, **kwargs: 'Any') -> 'Any'`

Async version of dataframe.merge(). Runs in thread pool.

#### `amerge_sorted_stream(source_a: 'Any', source_b: 'Any', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None) -> 'AsyncIterator[List[dict]]'`

Async sorted streaming merge. Sources **must** be pre-sorted by key.

#### `amerge_stream(source_a: 'Any', source_b: 'Any', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None) -> 'AsyncIterator[List[dict]]'`

Async streaming merge. Wraps :func:`streaming.merge_stream`.

#### `merge_sorted_stream(source_a: 'Iterable[dict]', source_b: 'Iterable[dict]', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None, stats: 'Optional[StreamStats]' = None) -> 'Generator[List[dict], None, None]'`

Merge two pre-sorted sources using merge-join. O(1) memory per row.

#### `merge_stream(source_a: 'Iterable[dict]', source_b: 'Iterable[dict]', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None, stats: 'Optional[StreamStats]' = None) -> 'Generator[List[dict], None, None]'`

Streaming merge of two row sources. Memory: O(batch_size + |source_b|).

#### `sync_merge(df_a: 'Any', df_b: 'Any', key: 'Optional[Union[str, List[str]]]' = None, timestamp_col: 'Optional[str]' = None, prefer: 'str' = 'latest', dedup: 'bool' = True, fuzzy_dedup: 'bool' = False, fuzzy_threshold: 'float' = 0.85, schema: 'Optional[Any]' = None) -> 'Any'`

Merge two DataFrames using CRDT semantics — conflict-free, deterministic, order-independent.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
