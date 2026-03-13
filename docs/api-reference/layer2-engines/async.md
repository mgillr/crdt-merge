# crdt_merge.async_merge — Async Merge

**Module**: `crdt_merge/async_merge.py`
**Layer**: 2 — Merge Engines
**LOC**: 140 *(corrected 2026-03-31 — was 188 from inventory; AST-verified actual: 140)*
**Dependencies**: `crdt_merge.dataframe`, `asyncio`

---

## Functions

### amerge()
```python
async def amerge(
    df_a: DataFrame,
    df_b: DataFrame,
    key: str,
    schema: Optional[MergeSchema] = None
) -> DataFrame
```
Async wrapper around the synchronous `merge()`. Runs merge in executor.

### amerge_stream()
```python
async def amerge_stream(
    stream_a: AsyncIterable[dict],
    stream_b: AsyncIterable[dict],
    key: str,
    schema: Optional[MergeSchema] = None
) -> AsyncIterator[dict]
```
Async stream merge.

---

## Classes

### AsyncMerge
```python
class AsyncMerge:
    def __init__(self, schema: Optional[MergeSchema] = None, executor=None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `async merge(df_a, df_b, key) -> DataFrame` | Async merge |
| `merge_stream()` | `async merge_stream(stream_a, stream_b, key) -> AsyncIterator[dict]` | Async stream merge |
