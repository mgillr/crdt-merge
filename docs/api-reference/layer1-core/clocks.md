# crdt_merge.clocks — Vector Clocks & Causality

**Module**: `crdt_merge/clocks.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 324
**Dependencies**: Python stdlib only

---

## Overview

Provides VectorClock and DottedVersionVector for tracking causal ordering in distributed systems.

---

## Enums

### Ordering
```python
class Ordering(Enum):
    BEFORE = "before"        # A happened-before B
    AFTER = "after"          # B happened-before A
    CONCURRENT = "concurrent" # Neither happened-before the other
    EQUAL = "equal"          # Identical clocks
```

---

## Classes

### VectorClock

Track causal ordering across distributed nodes. Each node has a logical counter.

```python
class VectorClock:
    def __init__(self, clocks: Optional[Dict[str, int]] = None) -> None
```

**Parameters**:
- `clocks` (`Dict[str, int] | None`): Node → counter mapping. Counters must be non-negative ints.

**Validation**: Negative or non-int values raise `TypeError`/`ValueError`. Zero counters are stripped.

> **Known Issue (LAY1-004)**: `VectorClock({"a": 0}) == VectorClock({})` — zero-stripping is implicit.

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get()` | `get(node_id: str) -> int` | Counter for node, or 0 |
| `increment()` | `increment(node_id: str) -> None` | Increment counter by 1 |
| `merge()` | `merge(other: VectorClock) -> VectorClock` | Element-wise max. CRDT compliant. |
| `compare()` | `compare(other: VectorClock) -> Ordering` | Causal relationship |
| `happens_before()` | `happens_before(other: VectorClock) -> bool` | `compare() == BEFORE` |
| `concurrent_with()` | `concurrent_with(other: VectorClock) -> bool` | `compare() == CONCURRENT` |
| `to_dict()` | `to_dict() -> dict` | `{"node1": 1, "node2": 2}` |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> VectorClock` | Deserialize |

**compare() Logic**:
1. All counters equal → `EQUAL`
2. All self ≤ other, at least one < → `BEFORE`
3. All other ≤ self, at least one < → `AFTER`
4. Otherwise → `CONCURRENT`

**Example**:
```python
from crdt_merge.clocks import VectorClock, Ordering

a = VectorClock({"node1": 1, "node2": 0})
b = VectorClock({"node1": 1, "node2": 1})
assert a.compare(b) == Ordering.BEFORE

c = VectorClock({"node1": 1, "node2": 0})
d = VectorClock({"node1": 0, "node2": 1})
assert c.compare(d) == Ordering.CONCURRENT
```

---

### DottedVersionVector

Variant of VectorClock with additional "dot" metadata for fine-grained per-event causality tracking.

```python
class DottedVersionVector:
    def __init__(self, clocks: Optional[Dict[str, int]] = None,
                 dots: Optional[Dict[str, Set[int]]] = None) -> None
```

**Parameters**:
- `clocks`: Base vector clock (contiguous counters)
- `dots`: Per-node set of non-contiguous event IDs

#### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(other: DottedVersionVector) -> DottedVersionVector` | Merge clocks (max) and dots (union) |
| `add_dot()` | `add_dot(node_id: str, counter: int) -> None` | Add a specific event dot |
| `contains()` | `contains(node_id: str, counter: int) -> bool` | Check if event is observed |
| `compact()` | `compact() -> None` | Compress contiguous dots into base clock |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> DottedVersionVector` | Deserialize |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `DottedVersionVector.advance(self, node_id: str) → DottedVersionVector`

Advance the dot for *node_id*. Returns a NEW instance.

        The dot becomes ``(node_id, base.get(node_id) + 1)``.
        The base stays unchanged (it is only updated on merge).
        

**Parameters:**
- `node_id` (`str`)

**Returns:** `DottedVersionVector`



### `DottedVersionVector.descends(self, other: DottedVersionVector) → bool`

Return True if *self* causally descends from (or equals) *other*.

        Self descends from other iff self's effective clock dominates other's
        effective clock on every node.
        

**Parameters:**
- `other` (`DottedVersionVector`)

**Returns:** `bool`



---

## automatic Methods (Missing from initial docs)

*Discovered during Team 4 RREA re-analysis.*

### `VectorClock.__eq__(self, other: object) -> bool`

Equality comparison. Two VectorClocks are equal if all counters match (after zero-stripping).

### `VectorClock.__hash__(self) -> int`

Hash based on frozen counter state. Allows VectorClock to be used in sets and as dict keys.

### `VectorClock.__repr__(self) -> str`

Returns string representation, e.g., `"VectorClock({'node1': 3, 'node2': 1})"`.

### `DottedVersionVector.__eq__(self, other: object) -> bool`

Equality comparison. Two DVVs are equal if both base clocks and dot sets match.

### `DottedVersionVector.__repr__(self) -> str`

Returns string representation showing base clocks and active dots.

---

## RREA Priority Analysis

| Symbol | Classification | Entropy | Reachability Score |
|--------|---------------|---------|-------------------|
| `Ordering` | SPECIALIZED | — | Enum for causal comparison |
| `VectorClock` | SPECIALIZED | — | Core causality type |
| `VectorClock.get` | DEAD (static) | 0.2714 | 4.7 — likely dynamic dispatch FP |
| `VectorClock.increment` | DEAD (static) | — | Called via `obj.increment()` |
| `VectorClock.compare` | DEAD (static) | — | Called via `obj.compare()` |
| `DottedVersionVector` | SPECIALIZED | — | Advanced causality type |
| `DottedVersionVector.advance` | DEAD (static) | — | Called via `obj.advance()` |
| `DottedVersionVector.descends` | DEAD (static) | — | Called via `obj.descends()` |

> **Note:** All DEAD classifications are likely false positives — these are instance methods called via dynamic dispatch which static AST analysis cannot trace.
