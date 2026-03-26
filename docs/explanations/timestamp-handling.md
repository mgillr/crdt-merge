# Timestamp Handling

## How Timestamps Are Parsed

The `_safe_parse_ts()` function handles diverse timestamp formats:

| Input Type | Example | Result |
|------------|---------|--------|
| `int` | `1000` | `1000.0` |
| `float` | `1000.5` | `1000.5` |
| Numeric string | `"1000"` | `1000.0` |
| ISO-8601 | `"2024-01-15T10:30:00Z"` | epoch float |
| Object with `.timestamp()` | `datetime.now()` | epoch float |
| Invalid | `"not a date"` | `0.0` |

## Silent Fallback

Invalid timestamps silently become `0.0`. This means they will lose to any valid timestamp in LWW resolution.

**Recommendation**: Validate timestamps before merging. The library does not raise on invalid timestamps.

---

## Hybrid Logical Clocks (HLC)

The `crdt_merge.clocks` module provides `VectorClock` and `DottedVersionVector` for tracking causal ordering in distributed systems.

### VectorClock

A `VectorClock` maintains per-node counters. It supports:

- **Increment**: advance a node's counter by 1
- **Merge**: element-wise max of all counters (commutative, associative, idempotent)
- **Causal comparison**: determine if one event happened-before another, or if events are concurrent

```python
from crdt_merge.clocks import VectorClock, Ordering

# Node 1 has seen 3 events, node 2 has seen 1 event
clock_a = VectorClock({"node1": 3, "node2": 1})

# Node 2 has seen 2 events from node1, 4 events from node2
clock_b = VectorClock({"node1": 2, "node2": 4})

# These clocks are CONCURRENT — neither happened-before the other
print(clock_a.compare(clock_b))  # Ordering.CONCURRENT

# Merge: element-wise max
merged = clock_a.merge(clock_b)
print(merged.value)  # {"node1": 3, "node2": 4}
```

### DottedVersionVector

A `DottedVersionVector` extends `VectorClock` with a "dot" — a single outstanding event that has not yet been folded into the base clock. This enables precise per-event causality tracking:

```python
from crdt_merge.clocks import DottedVersionVector, VectorClock

# Node A advances its clock
dvv_a = DottedVersionVector(base=VectorClock({"node_a": 2}))
dvv_a = dvv_a.advance("node_a")  # dot = ("node_a", 3)

# Node B advances its clock
dvv_b = DottedVersionVector(base=VectorClock({"node_b": 1}))
dvv_b = dvv_b.advance("node_b")  # dot = ("node_b", 2)

# Merge: folds both dots into the merged base
merged = dvv_a.merge(dvv_b)
print(merged.value)  # {"node_a": 3, "node_b": 2}
print(merged.dot)    # None — dots are folded on merge
```

### Zero-Counter Normalization

`VectorClock` automatically strips zero-valued counters during construction. This ensures canonical representation:

```python
from crdt_merge.clocks import VectorClock

# These are equivalent — zero counters are stripped
vc1 = VectorClock({"a": 0})
vc2 = VectorClock({})
print(vc1 == vc2)  # True
```

---

## Tie-Breaking Behavior

When two values have **identical timestamps**, `crdt_merge` needs a deterministic rule to choose a winner. Different CRDT types use different tie-breaking strategies:

### LWWRegister: Lexicographic node_id Comparison

The `LWWRegister.merge()` implementation uses the `node_id` field as a deterministic tiebreaker:

```python
# From crdt_merge/core.py — LWWRegister.merge():
if other._timestamp > self._timestamp:
    return LWWRegister(other._value, other._timestamp, other._node_id)
elif other._timestamp == self._timestamp:
    # Tie-break: higher node_id wins (lexicographic comparison)
    if other._node_id > self._node_id:
        return LWWRegister(other._value, other._timestamp, other._node_id)
return LWWRegister(self._value, self._timestamp, self._node_id)
```

**Rule:** When `ts_a == ts_b`, the node with the **lexicographically greater** `node_id` wins.

### Why Lexicographic Comparison?

The tie-breaking rule must satisfy three properties to preserve CRDT convergence:

1. **Deterministic** — given the same two inputs, always produce the same output
2. **Commutative** — `tiebreak(A, B) == tiebreak(B, A)` (same winner regardless of argument order)
3. **No coordination** — the rule must work independently on every replica without communication

Lexicographic string comparison (`>` in Python) satisfies all three:

- It is a **total order** over all strings — every pair of distinct strings has a defined winner
- It is **position-independent** — `max("node_a", "node_b")` returns the same result regardless of which argument is first
- It requires **no shared state** — each replica can independently apply `>` on `node_id` strings

### Example: Tie-Breaking in Action

```python
from crdt_merge.core import LWWRegister

# Two nodes write at the exact same time
reg_west = LWWRegister("west_value", timestamp=1719500000.0, node_id="us-west-2")
reg_east = LWWRegister("east_value", timestamp=1719500000.0, node_id="us-east-1")

# "us-west-2" > "us-east-1" lexicographically → us-west-2 wins
merged = reg_west.merge(reg_east)
print(merged.value)  # "west_value"

# Same result in reverse order (commutativity)
merged_rev = reg_east.merge(reg_west)
print(merged_rev.value)  # "west_value"
```

### LWW Strategy: Value-Based Tie-Breaking

The `LWW` merge strategy (used in `MergeSchema`) uses a different tie-breaking approach — it compares `str(value)` representations instead of `node_id`:

```python
# From crdt_merge/strategies.py — LWW.resolve():
if ts_b > ts_a:
    return val_b
elif ts_a > ts_b:
    return val_a
# Timestamps equal: tie-break via str() comparison
str_a, str_b = str(val_a), str(val_b)
if str_a != str_b:
    return val_a if str_a >= str_b else val_b
return val_a
```

This ensures `resolve(A, B) == resolve(B, A)` without needing node identity information.

### Lexicographic Ordering Gotcha

Lexicographic ordering does **not** match numeric ordering:

| Comparison | Lexicographic Result | Numeric Result |
|------------|---------------------|----------------|
| `"node9" > "node10"` | `True` | `False` |
| `"node2" > "node11"` | `True` | `False` |
| `"abc" > "abd"` | `False` | N/A |

**Recommendation:** Use zero-padded identifiers (`node01`, `node02`, …, `node10`) or UUIDs to ensure lexicographic order aligns with logical expectations.

### Tie-Breaking Summary

| CRDT Type / Strategy | Tie-Break Mechanism | Winner |
|----------------------|---------------------|--------|
| `LWWRegister` | `node_id` lexicographic comparison | Higher `node_id` |
| `LWW` strategy | `str(value)` lexicographic comparison | Higher string value |
| `LWWMap` | Delegates to `LWWRegister.merge()` per key | Higher `node_id` |
| `GCounter` | N/A — per-slot `max()`, no ties | Both values preserved |
| `ORSet` | N/A — tag set union, no ties | Both additions preserved |
| `VectorClock` | N/A — per-node `max()`, no ties | Both counters preserved |

See also: [Conflict Resolution](conflict-resolution.md) for runnable examples of each scenario.
