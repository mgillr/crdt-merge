# Parallel Merge

Parallel merge execution across multiple CPU cores.

## Quick Example

```python
from crdt_merge.parallel import parallel_merge
result = parallel_merge(df_a, df_b, key="id", n_workers=4)
```

---

## API Reference

## `crdt_merge.parallel`

> Thread-pool parallel merge for large datasets.

**Module:** `crdt_merge.parallel`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `parallel_merge(left: 'Any', right: 'Any', key: 'Optional[Union[str, List[str]]]' = None, schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None, chunk_size: 'int' = 50000, max_workers: 'Optional[int]' = None, prefer: 'str' = 'latest') -> 'Any'`

Parallel merge using a thread pool.

#### `parallel_merge_arrow(left: 'Any', right: 'Any', key: 'Optional[Union[str, List[str]]]' = None, schema: 'Optional[Any]' = None, chunk_size: 'int' = 100000, max_workers: 'Optional[int]' = None) -> 'Any'`

Parallel merge using the Arrow backend.

#### `sync_merge(df_a: 'Any', df_b: 'Any', key: 'Optional[Union[str, List[str]]]' = None, timestamp_col: 'Optional[str]' = None, prefer: 'str' = 'latest', dedup: 'bool' = True, fuzzy_dedup: 'bool' = False, fuzzy_threshold: 'float' = 0.85, schema: 'Optional[Any]' = None) -> 'Any'`

Merge two DataFrames using CRDT semantics — conflict-free, deterministic, order-independent.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
