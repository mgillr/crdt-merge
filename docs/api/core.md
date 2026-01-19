# Core CRDT Types

Fundamental CRDT data types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap.

## Quick Example

```python
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet
counter = GCounter("node_a")
counter.increment("node_a", 5)
```

---

## API Reference

## `crdt_merge.core`

> Core CRDT primitives — mathematically proven conflict-free replicated data types.

**Module:** `crdt_merge.core`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `GCounter(node_id: 'Optional[str]' = None, initial: 'int' = 0)`

Grow-only counter. Each node has its own slot; value = sum of all slots.

**Properties:**

- `value` — 

**Methods:**

- `from_dict(d: 'dict') -> 'GCounter'` — 
- `increment(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `merge(self, other: 'GCounter') -> 'GCounter'` — 
- `to_dict(self) -> 'dict'` — 

#### `LWWMap()`

Last-Writer-Wins Map — a dictionary where each key is an LWW Register.

**Properties:**

- `value` — 

**Methods:**

- `delete(self, key: 'str', timestamp: 'Optional[float]' = None) -> 'None'` — 
- `from_dict(d: 'dict') -> 'LWWMap'` — 
- `get(self, key: 'str', default: 'Any' = None) -> 'Any'` — 
- `merge(self, other: 'LWWMap') -> 'LWWMap'` — 
- `set(self, key: 'str', value: 'Any', timestamp: 'Optional[float]' = None, node_id: 'str' = '') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

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

#### `ORSet()`

Observed-Remove Set — add and remove elements without conflicts.

**Properties:**

- `value` — 

**Methods:**

- `add(self, element: 'Hashable') -> 'str'` — 
- `contains(self, element: 'Hashable') -> 'bool'` — 
- `from_dict(d: 'dict') -> 'ORSet'` — 
- `merge(self, other: 'ORSet') -> 'ORSet'` — 
- `remove(self, element: 'Hashable') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

#### `PNCounter()`

Positive-Negative counter — supports both increment and decrement.

**Properties:**

- `value` — 

**Methods:**

- `decrement(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `from_dict(d: 'dict') -> 'PNCounter'` — 
- `increment(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `merge(self, other: 'PNCounter') -> 'PNCounter'` — 
- `to_dict(self) -> 'dict'` — 



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
