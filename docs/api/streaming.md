# Streaming Merge

O(batch_size) and O(1) memory streaming merge pipelines.

## Quick Example

```python
from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats
for batch in merge_sorted_stream(src_a, src_b, key="id"):
    process(batch)
```

---

## API Reference

## `crdt_merge.streaming`

> Streaming Merge Pipeline — O(batch_size) memory merge for unlimited scale.

**Module:** `crdt_merge.streaming`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `StreamStats(rows_processed: 'int' = 0, rows_merged: 'int' = 0, rows_unique_a: 'int' = 0, rows_unique_b: 'int' = 0, batches_processed: 'int' = 0, duration_ms: 'float' = 0.0, peak_batch_size: 'int' = 0, _start_time: 'float' = 0.0) -> None`

Tracks streaming merge statistics.

**Properties:**

- `rows_per_sec` — 

**Methods:**


### Functions

#### `count_stream(source: 'Iterable[dict]') -> 'int'`

Count rows in a stream without loading into memory.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `merge_sorted_stream(source_a: 'Iterable[dict]', source_b: 'Iterable[dict]', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None, stats: 'Optional[StreamStats]' = None) -> 'Generator[List[dict], None, None]'`

Merge two pre-sorted sources using merge-join. O(1) memory per row.

#### `merge_stream(source_a: 'Iterable[dict]', source_b: 'Iterable[dict]', key: 'str' = 'id', batch_size: 'int' = 5000, schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None, stats: 'Optional[StreamStats]' = None) -> 'Generator[List[dict], None, None]'`

Streaming merge of two row sources. Memory: O(batch_size + |source_b|).



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
