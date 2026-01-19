# Self-Merging Parquet

Parquet files with embedded CRDT metadata that self-merge.

## Quick Example

```python
from crdt_merge.parquet import SelfMergingParquet
smf = SelfMergingParquet("customers", key="id", schema=schema)
smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
```

---

## API Reference

## `crdt_merge.parquet`

> Self-Merging Parquet — Parquet files with embedded CRDT merge semantics.

**Module:** `crdt_merge.parquet`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `CompactResult(records_before: 'int' = 0, records_after: 'int' = 0, duplicates_removed: 'int' = 0, compact_time_ms: 'float' = 0.0) -> None`

Result of compacting a self-merging Parquet file.

**Methods:**


#### `IngestResult(records_ingested: 'int' = 0, conflicts_resolved: 'int' = 0, new_records: 'int' = 0, updated_records: 'int' = 0, merge_time_ms: 'float' = 0.0, provenance_entries: 'int' = 0) -> None`

Result of ingesting data into a self-merging Parquet file.

**Methods:**


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

#### `ParquetMergeMetadata(key_column: 'str', strategies: 'Dict[str, str]', provenance_enabled: 'bool' = True, schema_version: 'str' = '1.0', created_at: 'Optional[str]' = None, source_count: 'int' = 0, merge_count: 'int' = 0) -> None`

Merge schema stored in Parquet key-value metadata.

**Methods:**

- `from_dict(d: 'Dict[str, Any]') -> "'ParquetMergeMetadata'"` — Deserialize from plain dict.
- `from_parquet_metadata(meta: 'Dict[str, str]') -> "'ParquetMergeMetadata'"` — Deserialize from Parquet key-value metadata.
- `to_dict(self) -> 'Dict[str, Any]'` — Serialize to plain dict.
- `to_parquet_metadata(self) -> 'Dict[str, str]'` — Serialize to Parquet key-value metadata format.

#### `ProvenanceEntry(source: 'str', timestamp: 'float', records_ingested: 'int', conflicts_resolved: 'int', new_records: 'int', updated_records: 'int') -> None`

A single provenance log entry for an ingest operation.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

#### `SelfMergingParquet(name: 'str', key: 'str' = 'id', schema: 'Optional[MergeSchema]' = None, provenance: 'bool' = True) -> 'None'`

Parquet files with embedded CRDT merge semantics.

**Methods:**

- `compact(self) -> 'CompactResult'` — Compact the container, removing exact-duplicate rows and dead entries.
- `from_parquet(path: 'str') -> "'SelfMergingParquet'"` — Load from a Parquet file with embedded merge metadata.
- `get_provenance_log(self) -> 'List[Dict[str, Any]]'` — Return the provenance log as a list of dicts.
- `ingest(self, data: 'Any', source: 'Optional[str]' = None) -> 'IngestResult'` — Merge new data into the container.
- `merge_with(self, other: "'SelfMergingParquet'") -> 'IngestResult'` — Merge another SelfMergingParquet into this one.
- `metadata(self) -> 'ParquetMergeMetadata'` — Get the embedded merge metadata.
- `read(self) -> 'List[dict]'` — Read all merged records.
- `to_parquet(self, path: 'str') -> 'None'` — Export to actual Parquet file with embedded metadata.

### Functions

#### `asdict(obj, *, dict_factory=<class 'dict'>)`

Return the fields of a dataclass instance as a new dictionary mapping

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
