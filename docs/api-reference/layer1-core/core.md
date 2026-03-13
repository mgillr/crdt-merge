# crdt_merge.core — CRDT Primitives

**Module**: `crdt_merge/core.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 320
**Dependencies**: Python stdlib only (`copy`, `time`, `uuid`)

---

## Overview

Implements 5 mathematically proven Conflict-Free Replicated Data Types (CRDTs). Each type satisfies:
- **Commutative**: `merge(A, B) == merge(B, A)`
- **Associative**: `merge(merge(A, B), C) == merge(A, merge(B, C))`
- **Idempotent**: `merge(A, A) == A`

---

## Quick Start

```python
from crdt_merge.core import GCounter, LWWRegister, LWWMap, ORSet

# Grow-only counter — each node tracks its own count
a = GCounter("node1", 10)
b = GCounter("node2", 5)
merged = a.merge(b)
assert merged.value == 15  # sum across all nodes

# Last-Writer-Wins Register — latest timestamp wins
reg_a = LWWRegister("Alice", 1000.0, "node1")
reg_b = LWWRegister("Bob", 2000.0, "node2")
assert reg_a.merge(reg_b).value == "Bob"  # ts 2000 > 1000

# LWW Map — each key is an independent LWW register
m = LWWMap()
m.set("name", "Alice", timestamp=100.0)
m.set("email", "alice@example.com", timestamp=100.0)
assert m.get("name") == "Alice"

# OR-Set — add/remove with add-wins semantics
s = ORSet()
s.add("apple")
s.add("banana")
s.remove("banana")
assert s.value == {"apple"}
```

---

## Classes

### GCounter

Grow-only counter. Each node tracks its own count; total value is the sum across all nodes.

```python
class GCounter:
    def __init__(self, node_id: Optional[str] = None, initial: int = 0) -> None
```

**Parameters**:
- `node_id` (`str | None`): Node identifier. If `None`, creates empty counter.
- `initial` (`int`): Initial count for the node. Default: `0`. Only applied if `node_id` is provided and `initial > 0`.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `int` | Sum of all node counts. O(n) where n = number of nodes. |

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `increment()` | `increment(node_id: str, amount: int = 1) -> None` | Add `amount` to node's count. Raises `TypeError` if amount is bool, `ValueError` if amount < 0. |
| `merge()` | `merge(other: GCounter) -> GCounter` | Returns new GCounter with element-wise max of both counters. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize to `{"type": "g_counter", "counts": {...}}` |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> GCounter` | Deserialize from dict. |
| `__repr__()` | `__repr__() -> str` | Returns `"GCounter(value=N, nodes=M)"` |

**Example**:
```python
from crdt_merge.core import GCounter

a = GCounter("node1", 10)
b = GCounter("node2", 5)
c = a.merge(b)
assert c.value == 15

# Merge with older state — max wins
a2 = GCounter("node1", 8)
c2 = a.merge(a2)
assert c2.value == 10  # max(10, 8) = 10
```

---

### PNCounter

Positive-Negative counter supporting both increment and decrement. Internally uses two GCounters (`_pos` for increments, `_neg` for decrements).

```python
class PNCounter:
    def __init__(self) -> None
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `int` | `_pos.value - _neg.value` |

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `increment()` | `increment(node_id: str, amount: int = 1) -> None` | Delegates to `_pos.increment()` |
| `decrement()` | `decrement(node_id: str, amount: int = 1) -> None` | Delegates to `_neg.increment()` |
| `merge()` | `merge(other: PNCounter) -> PNCounter` | Merges both `_pos` and `_neg` GCounters independently. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> PNCounter` | Deserialize |

**Example**:
```python
from crdt_merge.core import PNCounter

c = PNCounter()
c.increment("node1", 10)  # value = 10
c.decrement("node1", 3)   # value = 7
assert c.value == 7
```

---

### LWWRegister

Last-Writer-Wins Register. Stores a single value; concurrent writes resolved by timestamp with deterministic tie-breaking on `node_id`.

```python
class LWWRegister:
    def __init__(self, value: Any = None, timestamp: Optional[float] = None, node_id: str = "") -> None
```

**Parameters**:
- `value` (`Any`): Stored value.
- `timestamp` (`float | None`): Write timestamp in seconds. `0.0` if `None`.
- `node_id` (`str`): Writing node identifier for tie-breaking.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `Any` | The stored value |
| `timestamp` | `float` | Write timestamp |

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `set()` | `set(value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None` | Update value. If `timestamp` is `None`, uses `time.time()`. |
| `merge()` | `merge(other: LWWRegister) -> LWWRegister` | Returns register with higher timestamp. **Tie-break**: lexicographic comparison of `node_id` (higher string wins). |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> LWWRegister` | Deserialize |

**Tie-Breaking**: When timestamps are equal, `node_id` strings are compared lexicographically. `"node_b" > "node_a"` → node_b's value wins.

> ⚠️ **Known Issue (LAY1-001)**: Lexicographic comparison means `"node9" > "node10"`. This can be unintuitive.

**Example**:
```python
from crdt_merge.core import LWWRegister

a = LWWRegister("Alice", 1000.0, "node1")
b = LWWRegister("Bob", 2000.0, "node2")
c = a.merge(b)
assert c.value == "Bob"  # timestamp 2000 > 1000

# Tie-break:
a = LWWRegister("x", 1000.0, "node_a")
b = LWWRegister("y", 1000.0, "node_b")
c = a.merge(b)
assert c.value == "y"  # "node_b" > "node_a"
```

---

### ORSet

Observed-Remove Set. Supports concurrent add/remove without conflicts. Each `add()` generates a unique tag; `remove()` clears all tags.

```python
class ORSet:
    def __init__(self) -> None
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `set` | Set of all elements with at least one tag |

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(element: Hashable) -> str` | Add element, returns unique 12-char hex tag. |
| `remove()` | `remove(element: Hashable) -> None` | Clears ALL tags for element. |
| `contains()` | `contains(element: Hashable) -> bool` | True if element has any tags. |
| `merge()` | `merge(other: ORSet) -> ORSet` | Union of tag sets per element. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize. Non-string keys stored in `element_types` map. |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> ORSet` | Deserialize |

> ⚠️ **Known Issue (LAY1-002)**: `remove()` clears ALL tags. No selective tag removal API.

**Concurrent Add/Remove — Add Wins**:
```python
from crdt_merge.core import ORSet

replica_a = ORSet()
replica_b = ORSet()

tag = replica_a.add("apple")  # Replica A adds
replica_b.remove("apple")     # Replica B removes (no-op, not in B)

merged = replica_a.merge(replica_b)
assert "apple" in merged.value  # ADD WINS
```

---

### LWWMap

Last-Writer-Wins Map. Each key backed by an LWWRegister. Supports deletion via tombstones.

```python
class LWWMap:
    def __init__(self) -> None
```

**Internal State**:
- `_registers`: `Dict[str, LWWRegister]`
- `_tombstones`: `Dict[str, float]` (deletion timestamps)

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `dict` | All non-tombstoned entries |

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `set()` | `set(key: str, value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None` | Set key. Removes tombstone if write is newer. |
| `get()` | `get(key: str, default: Any = None) -> Any` | Get value, or `default` if tombstoned/missing. |
| `delete()` | `delete(key: str, timestamp: Optional[float] = None) -> None` | Record tombstone. Does NOT remove from `_registers`. |
| `merge()` | `merge(other: LWWMap) -> LWWMap` | Merge registers via LWWRegister.merge(); tombstones via max timestamp. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> LWWMap` | Deserialize |

**Example**:
```python
from crdt_merge.core import LWWMap

m = LWWMap()
m.set("name", "Alice", timestamp=1000.0)
m.delete("name", timestamp=500.0)  # Older delete — ignored
assert m.get("name") == "Alice"    # Write at 1000 > delete at 500
```

---

## Known Issues

| ID | Issue | Impact |
|----|-------|--------|
| LAY1-001 | Lexicographic node_id tie-breaking | `"node9" > "node10"` is unintuitive |
| LAY1-002 | ORSet full-remove only | No selective tag removal |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class ModelMergeSchema`

Maps layer-name patterns to merge strategies.

    Pattern matching priority: **exact > glob > range > regex > default**.

    Parameters
    ----------
    strategies : dict[str, str | ModelMergeStrategy]
        Mapping from patterns to strategy names or instances.
        Use ``"default"`` key for the fallback strategy.
    



### `ModelMergeSchema.strategy_for(self, layer_name: str) → ModelMergeStrategy`

Return the strategy that applies to *layer_name*.

        Resolution order: exact match → glob → range → regex → default.

        Raises
        ------
        KeyError
            If no pattern matches and no default is set.
        

**Parameters:**
- `layer_name` (`str`)

**Returns:** `ModelMergeStrategy`

**Raises:** `KeyError(f"No strategy matches layer '{layer_name}' and no default set")`



### `class ModelMerge`

Main entry-point for schema-driven model merging.

    Applies per-layer merge strategies according to a
    :class:`ModelMergeSchema`. Includes runtime CRDT-law verification
    via :meth:`verify`.

    .. deprecated:: 0.8.1
       The former name ``ModelCRDT`` is retained as a backward-compatible
       alias but will be removed in v1.0.  Prefer ``ModelMerge``.

    Parameters
    ----------
    schema : ModelMergeSchema
        Defines which strategy applies to each layer.
    

