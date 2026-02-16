# crdt_merge.streaming — Stream Merge Engine

**Module**: `crdt_merge/streaming.py`
**Layer**: 2 — Merge Engines
**LOC**: 288 *(corrected 2026-03-31 — was 362 from inventory; AST-verified actual: 288)*
**Dependencies**: `crdt_merge.strategies`

---

## Overview

Generator-based streaming merge engine for processing arbitrarily large datasets with bounded memory. Instead of loading entire DataFrames into memory, `merge_stream` and `merge_sorted_stream` consume row iterables (generators, file readers, database cursors) and yield merged results in configurable batches.

Key characteristics:
- **Memory**: O(batch_size) for sorted streams, O(batch_size + |source_b|) for unsorted
- **Throughput**: ~400K rows/s stable (v0.4.0 optimizations)
- **Output**: Batched — yields `List[dict]` chunks for backpressure-friendly pipelines

---

## Quick Start

```python
from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats

# Two record sources (could be generators, DB cursors, file readers, etc.)
source_a = [
    {"id": 1, "name": "Alice", "score": 80},
    {"id": 2, "name": "Charlie", "score": 70},
]
source_b = [
    {"id": 1, "name": "Bob", "score": 90},
    {"id": 3, "name": "Diana", "score": 85},
]

# Merge with progress tracking
stats = StreamStats()
for batch in merge_stream(source_a, source_b, key="id", stats=stats):
    for row in batch:
        print(row)
# {"id": 1, "name": "Bob", "score": 90}  — conflict resolved (LWW default)
# {"id": 2, "name": "Charlie", "score": 70}  — only in A
# {"id": 3, "name": "Diana", "score": 85}  — only in B
print(stats)  # StreamStats(rows=3, merged=1, batches=1, ...)

# For pre-sorted data, use merge_sorted_stream for O(1) memory per row
sorted_a = [{"id": 1, "val": "a"}, {"id": 3, "val": "c"}]
sorted_b = [{"id": 2, "val": "b"}, {"id": 3, "val": "d"}]
for batch in merge_sorted_stream(sorted_a, sorted_b, key="id"):
    print(batch)
```

---

## Functions

### merge_stream()
```python
def merge_stream(
    source_a: Iterable[dict],
    source_b: Iterable[dict],
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None,
) -> Generator[List[dict], None, None]
```
Streaming merge of two row sources with bounded memory. Loads `source_b` into a lookup dict, then streams `source_a` against it. Output is yielded in batches of up to `batch_size` rows.

**Parameters**:
- `source_a` (`Iterable[dict]`): First iterable of dicts (streamed, not fully loaded).
- `source_b` (`Iterable[dict]`): Second iterable of dicts (loaded into memory for lookup).
- `key` (`str`): Primary key field name. Default: `"id"`.
- `batch_size` (`int`): Max rows per output batch. Default: `5000`.
- `schema` (`MergeSchema | None`): Optional per-column merge strategies. Default: all LWW.
- `timestamp_col` (`str | None`): Column name for LWW timestamps.
- `stats` (`StreamStats | None`): Optional stats tracker to monitor progress.

**Yields**: `List[dict]` — batches of merged rows, each up to `batch_size` rows.

**Memory**: O(batch_size + |source_b|). `source_b` is fully indexed; `source_a` is streamed.

### merge_sorted_stream()
```python
def merge_sorted_stream(
    source_a: Iterable[dict],
    source_b: Iterable[dict],
    key: str = "id",
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None,
) -> Generator[List[dict], None, None]
```
Optimized merge for pre-sorted streams using the classic merge-join algorithm. Both sources **must** be sorted by `key` in ascending order. O(1) memory per row, O(n+m) time.

**Parameters**:
- `source_a` (`Iterable[dict]`): First pre-sorted iterable of dicts.
- `source_b` (`Iterable[dict]`): Second pre-sorted iterable of dicts.
- `key` (`str`): Primary key field name. Default: `"id"`.
- `batch_size` (`int`): Max rows per output batch. Default: `5000`.
- `schema` (`MergeSchema | None`): Optional per-column merge strategies.
- `timestamp_col` (`str | None`): Column name for LWW timestamps.
- `stats` (`StreamStats | None`): Optional stats tracker.

**Yields**: `List[dict]` — batches of merged rows.

**Raises**: `ValueError` if either source is not sorted by `key`.

---

## Classes

### StreamStats
```python
@dataclass
class StreamStats:
    rows_processed: int = 0
    rows_merged: int = 0
    rows_unique_a: int = 0
    rows_unique_b: int = 0
    batches_processed: int = 0
    duration_ms: float = 0.0
    peak_batch_size: int = 0
```
Dataclass that tracks streaming merge statistics. Pass an instance to `merge_stream()` or `merge_sorted_stream()` via the `stats` parameter to collect metrics during the merge.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `rows_per_sec` | `float` | Computed throughput: `rows_processed / (duration_ms / 1000)`. Returns `0.0` if `duration_ms` is zero. |

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `rows_processed` | `int` | Total rows emitted (merged + unique from both sides). |
| `rows_merged` | `int` | Rows that matched on key and were CRDT-merged. |
| `rows_unique_a` | `int` | Rows only in source A (passed through as-is). |
| `rows_unique_b` | `int` | Rows only in source B (appended after A is drained). |
| `batches_processed` | `int` | Number of output batches yielded. |
| `duration_ms` | `float` | Total wall-clock time in milliseconds. |
| `peak_batch_size` | `int` | Largest batch size yielded. |

**Example**:
```python
from crdt_merge.streaming import merge_stream, StreamStats

stats = StreamStats()
for batch in merge_stream(source_a, source_b, key="id", stats=stats):
    process(batch)
print(f"Processed {stats.rows_processed} rows in {stats.duration_ms:.0f}ms")
print(f"Throughput: {stats.rows_per_sec:.0f} rows/sec")
```

---

### count_stream()
```python
def count_stream(source: Iterable[dict]) -> int
```
Count rows in a stream without loading into memory. Fully consumes the iterable.

**Parameters:**
- `source` (`Iterable[dict]`): Any iterable of dict records.

**Returns:** `int` — the total number of rows in the stream.

