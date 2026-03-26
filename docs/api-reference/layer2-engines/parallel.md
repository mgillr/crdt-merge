# crdt_merge.parallel — Parallel Merge

**Module**: `crdt_merge/parallel.py`
**Layer**: 2 — Merge Engines
**LOC**: 175 *(corrected 2026-03-31 — was 251 from inventory; AST-verified actual: 175)*
**Dependencies**: `crdt_merge.dataframe`, `multiprocessing`

> **Missing `__all__`**: This module does not define `__all__`, making its public API boundary ambiguous. See issue LAY2-004.

---

## Functions

### parallel_merge()
```python
def parallel_merge(
    df_a: DataFrame,
    df_b: DataFrame,
    key: str,
    schema: Optional[MergeSchema] = None,
    num_workers: int = 4
) -> DataFrame
```
Merge DataFrames in parallel by partitioning on key.

---

## Classes

### ParallelMerge
```python
class ParallelMerge:
    def __init__(self, num_workers: int = 4, chunk_size: int = 10000) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(df_a, df_b, key, schema) -> DataFrame` | Parallel merge |
| `merge_many()` | `merge_many(dataframes: List[DataFrame], key, schema) -> DataFrame` | Merge multiple DataFrames |
