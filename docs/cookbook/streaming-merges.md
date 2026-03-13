# Streaming Merge Recipes

> **Important:** Both `merge_stream` and `merge_sorted_stream` yield **batches**
> (lists of dicts), not individual records. Always use a nested loop:
> `for batch in merge_stream(...): for record in batch: ...`

## Recipe 1: Basic Stream Merge

```python
from crdt_merge.streaming import merge_stream

stream_a = iter([{"id": 1, "val": "a"}, {"id": 2, "val": "b"}])
stream_b = iter([{"id": 1, "val": "c"}, {"id": 3, "val": "d"}])

# merge_stream yields batches (List[dict]), not individual records
for batch in merge_stream(stream_a, stream_b, key="id"):
    for record in batch:
        print(record)
```

## Recipe 2: Sorted Stream (Optimal)

```python
from crdt_merge.streaming import merge_sorted_stream

# Pre-sorted streams → O(1) memory per row, O(n+m) time
sorted_a = iter([{"id": 1, "val": "a"}, {"id": 3, "val": "c"}])
sorted_b = iter([{"id": 2, "val": "b"}, {"id": 4, "val": "d"}])

# merge_sorted_stream also yields batches, just like merge_stream
for batch in merge_sorted_stream(sorted_a, sorted_b, key="id"):
    for record in batch:
        print(record)
```

## Recipe 3: File-Based Streaming

```python
import json
from crdt_merge.streaming import merge_stream

def json_file_stream(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)

for batch in merge_stream(
    json_file_stream("data_a.jsonl"),
    json_file_stream("data_b.jsonl"),
    key="id"
):
    for record in batch:
        process(record)
```

## Recipe 4: Tracking Progress with StreamStats

```python
from crdt_merge.streaming import merge_stream
from crdt_merge import StreamStats

stats = StreamStats()

stream_a = iter([{"id": i, "val": f"a{i}"} for i in range(10)])
stream_b = iter([{"id": i, "val": f"b{i}"} for i in range(5, 15)])

for batch in merge_stream(stream_a, stream_b, key="id", stats=stats):
    print(f"Batch of {len(batch)} records")

print(f"\nFinal stats: {stats}")
print(f"  Rows processed: {stats.rows_processed}")
print(f"  Rows merged:    {stats.rows_merged}")
print(f"  Unique to A:    {stats.rows_unique_a}")
print(f"  Unique to B:    {stats.rows_unique_b}")
print(f"  Throughput:     {stats.rows_per_sec:.0f} rows/s")
```

## Recipe 5: Custom Batch Size and Per-Field Schema

```python
from crdt_merge.streaming import merge_stream
from crdt_merge import MergeSchema, LWW, MaxWins

# Per-field strategies: LWW for names, MaxWins for scores
schema = MergeSchema(default=LWW(), score=MaxWins())

stream_a = iter([
    {"id": 1, "name": "Alice", "score": 50},
    {"id": 2, "name": "Bob",   "score": 70},
])
stream_b = iter([
    {"id": 1, "name": "Alice B", "score": 80},
    {"id": 3, "name": "Carol",   "score": 90},
])

# batch_size controls how many rows per yielded batch (default: 5000)
for batch in merge_stream(
    stream_a, stream_b,
    key="id",
    batch_size=2,
    schema=schema,
):
    for record in batch:
        print(record)
```

## Recipe 6: Timestamp-Based Last-Write-Wins

```python
from crdt_merge.streaming import merge_stream

stream_a = iter([
    {"id": 1, "val": "old-a", "_ts": 1704067200},   # 2024-01-01
    {"id": 2, "val": "only-a", "_ts": 1717200000},   # 2024-06-01
])
stream_b = iter([
    {"id": 1, "val": "new-b", "_ts": 1717200000},    # 2024-06-01
    {"id": 3, "val": "only-b", "_ts": 1709251200},   # 2024-03-01
])

# timestamp_col tells the merger which field holds the numeric timestamp
# for LWW conflict resolution — the row with the higher timestamp wins
for batch in merge_stream(stream_a, stream_b, key="id", timestamp_col="_ts"):
    for record in batch:
        print(record)
```

## API Reference

### `merge_stream` / `merge_sorted_stream` Parameters

| Parameter       | Type                    | Default | Description                                                        |
|-----------------|-------------------------|---------|--------------------------------------------------------------------|
| `source_a`      | `Iterable[dict]`        | —       | First iterable of dicts (streamed, not fully loaded)               |
| `source_b`      | `Iterable[dict]`        | —       | Second iterable of dicts (loaded into memory for `merge_stream`)   |
| `key`           | `str`                   | `"id"`  | Primary key field name for matching rows                           |
| `batch_size`    | `int`                   | `5000`  | Maximum number of rows per yielded batch                           |
| `schema`        | `Optional[MergeSchema]` | `None`  | Per-field merge strategies (e.g., `LWW`, `MaxWins`, `UnionSet`)    |
| `timestamp_col` | `Optional[str]`         | `None`  | Column holding a numeric timestamp for LWW resolution              |
| `stats`         | `Optional[StreamStats]` | `None`  | Pass a `StreamStats()` instance to collect merge statistics        |

**Return type:** `Generator[List[dict], None, None]` — yields lists of merged dicts.

### `StreamStats` Fields

| Field              | Type    | Description                           |
|--------------------|---------|---------------------------------------|
| `rows_processed`   | `int`   | Total rows in all yielded batches     |
| `rows_merged`      | `int`   | Rows merged from both sources         |
| `rows_unique_a`    | `int`   | Rows only in source A                 |
| `rows_unique_b`    | `int`   | Rows only in source B                 |
| `batches_processed`| `int`   | Number of batches yielded             |
| `duration_ms`      | `float` | Total merge time in milliseconds      |
| `peak_batch_size`  | `int`   | Largest batch size seen               |
| `rows_per_sec`     | `float` | Computed throughput (property)        |
