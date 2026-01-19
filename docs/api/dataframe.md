# DataFrame Merge

Dataset merge with key matching, conflict resolution, and schema support.

## Quick Example

```python
from crdt_merge import merge, diff
result = merge(df_a, df_b, key="id")
changes = diff(df_a, df_b, key="id")
```

---

## API Reference

## `crdt_merge.dataframe`

> CRDT-powered DataFrame merge — conflict-free merge of any two DataFrames.

**Module:** `crdt_merge.dataframe`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LWWRegister(value: 'Any' = None, timestamp: 'Optional[float]' = None, node_id: 'str' = '')`

Last-Writer-Wins Register — stores a single value, latest timestamp wins.

**Properties:**

- `timestamp` — 
- `value` — 

**Methods:**

- `from_dict(d: 'dict') -> 'LWWRegister'` — 
- `merge(self, other: 'LWWRegister') -> 'LWWRegister'` — 
- `set(self, value: 'Any', timestamp: 'Optional[float]' = None, node_id: 'str' = '') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

### Functions

#### `diff(df_a: 'Any', df_b: 'Any', key: 'Union[str, List[str]]') -> 'Dict[str, Any]'`

Show what changed between two DataFrames.

#### `merge(df_a: 'Any', df_b: 'Any', key: 'Optional[Union[str, List[str]]]' = None, timestamp_col: 'Optional[str]' = None, prefer: 'str' = 'latest', dedup: 'bool' = True, fuzzy_dedup: 'bool' = False, fuzzy_threshold: 'float' = 0.85, schema: 'Optional[Any]' = None) -> 'Any'`

Merge two DataFrames using CRDT semantics — conflict-free, deterministic, order-independent.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
