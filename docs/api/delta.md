# Delta Engine

Delta-state CRDT sync — compute, apply, and compose deltas.

## Quick Example

```python
from crdt_merge.delta import compute_delta, apply_delta, DeltaStore
delta = compute_delta(old, new, key="id")
updated = apply_delta(remote, delta, key="id")
```

---

## API Reference

## `crdt_merge.delta`

> Delta-State Dataset Sync — O(delta) synchronization instead of O(n).

**Module:** `crdt_merge.delta`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Delta(added: 'Optional[List[dict]]' = None, modified: 'Optional[List[dict]]' = None, removed: 'Optional[List[str]]' = None, version: 'int' = 0, timestamp: 'Optional[float]' = None, source_node: 'str' = '')`

Represents the minimal changeset between two dataset states.

**Properties:**

- `is_empty` — 
- `size` — 

**Methods:**

- `from_dict(d: 'dict') -> 'Delta'` — 
- `to_dict(self) -> 'dict'` — 

#### `DeltaStore(key: 'str', node_id: 'str' = 'default')`

Stateful delta tracker — remembers the last known state and computes

**Properties:**

- `records` — 
- `size` — 
- `version` — 

**Methods:**

- `ingest(self, records: 'List[dict]') -> 'Optional[Delta]'` — Ingest new state and return the delta from previous state.

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

### Functions

#### `apply_delta(records: 'List[dict]', delta: 'Delta', key: 'str', schema: 'Optional[MergeSchema]' = None) -> 'List[dict]'`

Apply a delta to a record set, producing the updated state.

#### `compose_deltas(*deltas: 'Delta', key: 'Optional[str]' = None) -> 'Delta'`

Compose multiple deltas into one: delta(1→2) ⊔ delta(2→3) == delta(1→3).

#### `compute_delta(old_records: 'List[dict]', new_records: 'List[dict]', key: 'str', version: 'int' = 0, source_node: 'str' = '') -> 'Delta'`

Compute the minimal delta between old and new states.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
