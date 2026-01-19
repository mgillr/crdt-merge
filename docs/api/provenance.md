# Provenance & Audit Trails

Per-field audit trail: which source won, which strategy, and why.

## Quick Example

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance
merged, log = merge_with_provenance(df_a, df_b, key="id")
json_str = export_provenance(log, format="json")
```

---

## API Reference

## `crdt_merge.provenance`

> Merge Provenance & Lineage — per-field audit trail for every merge decision.

**Module:** `crdt_merge.provenance`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeDecision(field: 'str', source: 'str', strategy: 'str', value: 'Any', alternative: 'Any' = None) -> None`

Record of how a single field was resolved during merge.

**Methods:**

- `to_dict(self) -> 'dict'` — 
- `was_conflict(self) -> 'bool'` — True if this field had a real conflict that needed resolution.

#### `MergeRecord(key: 'Any', origin: 'str', decisions: 'List[MergeDecision]' = <factory>) -> None`

Complete provenance for one merged row.

**Properties:**

- `conflict_count` — 
- `conflicts` — Return only decisions where a real conflict was resolved.
- `fields_from_a` — 
- `fields_from_b` — 

**Methods:**

- `to_dict(self) -> 'dict'` — 

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

#### `ProvenanceLog(records: 'List[MergeRecord]' = <factory>, total_rows: 'int' = 0, merged_rows: 'int' = 0, unique_a_rows: 'int' = 0, unique_b_rows: 'int' = 0, total_conflicts: 'int' = 0, duration_ms: 'float' = 0.0) -> None`

Complete provenance log for a merge operation.

**Methods:**

- `summary(self) -> 'str'` — 
- `to_dict(self) -> 'dict'` — 

### Functions

#### `asdict(obj, *, dict_factory=<class 'dict'>)`

Return the fields of a dataclass instance as a new dictionary mapping

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `export_provenance(log: 'ProvenanceLog', format: 'str' = 'json') -> 'str'`

Export provenance log to JSON or CSV string.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `merge_with_provenance(df_a, df_b, key: 'str' = 'id', schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None) -> 'Tuple'`

Merge two DataFrames/list-of-dicts and return full provenance audit trail.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
