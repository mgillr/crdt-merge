# Binary Wire Protocol

Compact binary serialization for all CRDT types.

## Quick Example

```python
from crdt_merge.wire import serialize, deserialize, peek_type
data = serialize(counter, compress=True)
restored = deserialize(data)
```

---

## API Reference

## `crdt_merge.wire`

> Cross-Language Wire Format for crdt-merge.

**Module:** `crdt_merge.wire`

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

#### `MergeableBloom(capacity: int = 10000, fp_rate: float = 0.01, *, _size: Optional[int] = None, _num_hashes: Optional[int] = None)`

Bloom filter with CRDT merge semantics.

**Methods:**

- `add(self, item: Any) -> None` — Add an item to the filter.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items.
- `contains(self, item: Any) -> bool` — Check if an item might be in the set.
- `estimated_fp_rate(self) -> float` — Estimate current false positive rate based on fill ratio.
- `from_dict(d: dict) -> 'MergeableBloom'` — Deserialize from dict.
- `merge(self, other: 'MergeableBloom') -> 'MergeableBloom'` — Merge two Bloom filters via bitwise OR.
- `size_bytes(self) -> int` — Return memory usage in bytes.
- `to_dict(self) -> dict` — Serialize to dict for wire format.

#### `MergeableCMS(width: int = 2000, depth: int = 7)`

Count-Min Sketch with CRDT merge semantics.

**Properties:**

- `total` — Total count of all items added.

**Methods:**

- `add(self, item: Any, count: int = 1) -> None` — Add an item with the given count.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items (count 1 each).
- `estimate(self, item: Any) -> int` — Estimate the count of an item.
- `from_dict(d: dict) -> 'MergeableCMS'` — Deserialize from dict.
- `merge(self, other: 'MergeableCMS') -> 'MergeableCMS'` — Merge two Count-Min Sketches via per-cell max.
- `size_bytes(self) -> int` — Approximate memory usage in bytes.
- `to_dict(self) -> dict` — Serialize to dict for wire format.

#### `MergeableHLL(precision: int = 14)`

HyperLogLog cardinality estimator with CRDT merge semantics.

**Methods:**

- `add(self, item: Any) -> None` — Add an item to the HLL.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items.
- `cardinality(self) -> float` — Estimate the number of distinct elements.
- `from_dict(d: dict) -> 'MergeableHLL'` — Deserialize from dict.
- `merge(self, other: 'MergeableHLL') -> 'MergeableHLL'` — Merge two HLLs by taking register-max.
- `size_bytes(self) -> int` — Return the memory usage in bytes.
- `standard_error(self) -> float` — Return the standard error rate for this precision.
- `to_dict(self) -> dict` — Serialize to dict for wire format.

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

#### `WireError(...)`

Raised on serialization/deserialization errors.

### Functions

#### `deserialize(data: bytes) -> Any`

Deserialize a CRDT object from wire format bytes.

#### `deserialize_batch(data: bytes) -> list`

Deserialize multiple CRDT objects from a batch byte stream.

#### `peek_type(data: bytes) -> str`

Read the type tag from wire format bytes without deserializing.

#### `serialize(obj: Any, *, compress: bool = False) -> bytes`

Serialize a CRDT object to the wire format.

#### `serialize_batch(objects: list, *, compress: bool = False) -> bytes`

Serialize multiple CRDT objects into a single byte stream.

#### `wire_size(data: bytes) -> dict`

Get size information about wire-format data without deserializing.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
