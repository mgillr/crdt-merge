# Arrow Merge Engine

Apache Arrow-native merge path with zero-copy operations.

## Quick Example

```python
from crdt_merge.arrow import ArrowMerge
merger = ArrowMerge(schema=my_schema, engine="auto")
result = merger.merge(left_table, right_table, key="id")
```

---

## API Reference

## `crdt_merge.arrow`

> Apache Arrow-native merge engine for high-performance CRDT merges.

**Module:** `crdt_merge.arrow`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ArrowMerge(schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None, engine: 'str' = 'auto') -> 'None'`

Arrow-native CRDT merge engine.

**Properties:**

- `schema` — Return the configured MergeSchema (may be None).
- `timestamp_col` — Return the configured timestamp column name.

**Methods:**

- `merge(self, left: 'Any', right: 'Any', key: 'Optional[str]' = None) -> 'Any'` — Merge two Arrow tables using CRDT strategies.
- `merge_batches(self, batches: 'Iterator[Any]', key: 'Optional[str]' = None, batch_size: 'int' = 10000) -> 'Generator[Any, None, None]'` — Streaming merge for Arrow IPC record batches.
- `merge_ipc(self, left_path: 'str', right_path: 'str', output_path: 'str', key: 'Optional[str]' = None) -> 'Dict[str, Any]'` — Merge two Arrow IPC files and write the result.
- `merge_memory_mapped(self, left_path: 'str', right_path: 'str', key: 'Optional[str]' = None) -> 'Any'` — Merge two Arrow IPC files using memory-mapped I/O.

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

#### `SchemaPolicy(*values)`

Policy for resolving schema drift between two schemas.

### Functions

#### `arrow_merge(left: 'Any', right: 'Any', key: 'Optional[str]' = None, schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None, engine: 'str' = 'auto') -> 'Any'`

One-shot CRDT merge. Falls back to pure-Python if PyArrow is unavailable.

#### `arrow_merge_tables(tables: 'Sequence[Any]', key: 'Optional[str]' = None, schema: 'Optional[Any]' = None, timestamp_col: 'Optional[str]' = None) -> 'Any'`

Merge a sequence of Arrow tables pairwise.

#### `arrow_schema_info(table: 'Any') -> 'Dict[str, str]'`

Return a dict mapping column names to Arrow type strings.

#### `benchmark_arrow_merge(num_rows: 'int' = 10000, num_cols: 'int' = 10, key: 'str' = 'id', overlap: 'float' = 0.5) -> 'Dict[str, Any]'`

Generate synthetic data and benchmark Arrow merge vs dict merge.

#### `compare_arrow_schemas(left: 'Any', right: 'Any') -> 'Dict[str, Any]'`

Compare two Arrow tables' schemas and return a diff.

#### `evolve_schema(old: 'Dict[str, str]', new: 'Dict[str, str]', policy: 'SchemaPolicy' = <SchemaPolicy.UNION: 'union'>, defaults: 'Optional[Dict[str, Any]]' = None, allow_type_narrowing: 'bool' = False) -> 'SchemaEvolutionResult'`

Detect and resolve schema drift between *old* and *new*.

#### `polars_merge_arrow(left: "'pa.Table'", right: "'pa.Table'", key: 'str', schema: 'Any', timestamp_col: 'Optional[str]' = None) -> "Tuple['pa.Table', int]"`

Merge two Arrow tables using the Polars engine.

#### `read_ipc(path: 'str') -> 'Any'`

Read an Arrow IPC file and return a ``pa.Table``.

#### `table_to_batches(table: 'Any', batch_size: 'int' = 10000) -> 'List[Any]'`

Split a ``pa.Table`` into a list of ``pa.RecordBatch`` objects.

#### `write_ipc(table: 'Any', path: 'str') -> 'str'`

Write a ``pa.Table`` to an Arrow IPC file.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
