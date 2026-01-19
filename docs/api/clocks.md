# Clocks — HLC & Vector Clocks

Hybrid Logical Clocks and Vector Clocks for distributed ordering.

## Quick Example

```python
from crdt_merge.clocks import VectorClock, Ordering
vc = VectorClock({"a": 3, "b": 1})
print(vc.compare(other_vc))  # Ordering.CONCURRENT
```

---

## API Reference

## `crdt_merge.clocks`

> Vector clocks and causality detection for distributed CRDT systems.

**Module:** `crdt_merge.clocks`

### Classes

#### `DottedVersionVector(base: 'Optional[VectorClock]' = None, dot: 'Optional[Tuple[str, int]]' = None) -> 'None'`

Dotted Version Vector for precise causality tracking.

**Properties:**

- `base` — The base vector clock (read-only copy).
- `dot` — The outstanding dot, or None.
- `value` — Effective state: base with dot merged in.

**Methods:**

- `advance(self, node_id: 'str') -> 'DottedVersionVector'` — Advance the dot for *node_id*. Returns a NEW instance.
- `descends(self, other: 'DottedVersionVector') -> 'bool'` — Return True if *self* causally descends from (or equals) *other*.
- `from_dict(d: 'dict') -> 'DottedVersionVector'` — Deserialize from a plain dict.
- `merge(self, other: 'DottedVersionVector') -> 'DottedVersionVector'` — Merge two DVVs: merge bases, fold both dots into the new base.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `Enum(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)`

Create a collection of name/value pairs.

#### `Ordering(*values)`

Causal ordering between two vector clocks.

#### `VectorClock(clocks: 'Optional[Dict[str, int]]' = None) -> 'None'`

Vector clock for tracking causal ordering in distributed systems.

**Properties:**

- `value` — Return a **copy** of the internal clock dict.

**Methods:**

- `compare(self, other: 'VectorClock') -> 'Ordering'` — Compare two vector clocks for causal ordering.
- `from_dict(d: 'dict') -> 'VectorClock'` — Deserialize from a plain dict.
- `get(self, node_id: 'str') -> 'int'` — Get the counter for *node_id* (0 if the node has never been seen).
- `increment(self, node_id: 'str') -> 'VectorClock'` — Return a NEW clock with *node_id*'s counter incremented by 1.
- `merge(self, other: 'VectorClock') -> 'VectorClock'` — Element-wise max of two vector clocks. Returns a NEW instance.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
