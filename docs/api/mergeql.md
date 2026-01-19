# MergeQL — SQL Interface

SQL-like CRDT merge: MERGE t1, t2 ON id STRATEGY score='max'.

## Quick Example

```python
from crdt_merge.mergeql import MergeQL
ql = MergeQL()
ql.register("nyc", data_nyc)
result = ql.execute("MERGE nyc, london ON id STRATEGY salary='max'")
```

---

## API Reference

## `crdt_merge.mergeql`

> MergeQL — SQL-like interface for CRDT merge operations.

**Module:** `crdt_merge.mergeql`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Concat(separator: 'str' = ' | ', dedup: 'bool' = True)`

Concatenate both values with dedup. Sorted for commutativity.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Custom(fn: 'Callable')`

User-provided merge function.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LongestWins()`

Longer string wins. Equal length falls back to LWW.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MaxWins()`

Higher value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeAST(sources: 'List[str]', on_key: 'str', strategies: 'Dict[str, str]' = <factory>, where_clause: 'Optional[str]' = None, explain: 'bool' = False, schema_mapping: 'Optional[Dict[str, str]]' = None, limit: 'Optional[int]' = None) -> None`

Abstract syntax tree for a MergeQL statement.

**Methods:**


#### `MergePlan(sources: 'List[str]', source_sizes: 'Dict[str, int]', merge_key: 'str', strategies: 'Dict[str, str]', estimated_output_rows: 'int', schema_evolution_needed: 'bool', arrow_backend: 'bool', steps: 'List[str]') -> None`

Execution plan for a MergeQL query.

**Methods:**


#### `MergeQL(*, arrow_backend: 'bool' = False, provenance: 'bool' = True) -> 'None'`

SQL-like interface for CRDT merge operations.

**Methods:**

- `execute(self, query: 'str') -> 'MergeQLResult'` — Execute a MergeQL query.
- `explain(self, query: 'str') -> 'MergePlan'` — Show execution plan without running the merge.
- `list_sources(self) -> 'List[str]'` — List all registered source names.
- `register(self, name: 'str', data: 'Any') -> 'None'` — Register a data source for merge operations.
- `register_strategy(self, name: 'str', func: 'Callable') -> 'None'` — Register a custom merge strategy for use in STRATEGY clauses.
- `source_info(self, name: 'str') -> 'Dict[str, Any]'` — Get info about a registered source (row count, columns, etc).
- `unregister(self, name: 'str') -> 'None'` — Remove a registered data source.

#### `MergeQLError(...)`

Base exception for MergeQL errors.

#### `MergeQLParser()`

Parse MergeQL SQL-like syntax into AST nodes.

**Methods:**

- `parse(self, query: 'str') -> 'MergeAST'` — Parse a MergeQL query string into an AST.

#### `MergeQLResult(data: 'List[dict]', plan: 'MergePlan', conflicts: 'int', provenance: 'Optional[List[dict]]' = None, merge_time_ms: 'float' = 0.0, sources_merged: 'int' = 0) -> None`

Result of a MergeQL execution.

**Methods:**


#### `MergeQLSyntaxError(...)`

Raised when MergeQL query has syntax errors.

#### `MergeQLValidationError(...)`

Raised when MergeQL query references invalid sources or strategies.

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

#### `MinWins()`

Lower value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Priority(levels: 'List[str]')`

Ranked priority — higher index in the priority list wins.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `UnionSet(separator: 'str' = ',')`

Merge separated values as a set union. Sorted for determinism.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
