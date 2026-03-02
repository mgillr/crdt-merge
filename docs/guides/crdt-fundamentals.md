# CRDT Fundamentals — Deep Dive

Mathematical foundations plus working code for every primitive. All examples run against the live library.

---

## Mathematical Foundation

A CRDT is a data type equipped with a merge function that forms a **join-semilattice**:

1. **Commutative**: `merge(A, B) = merge(B, A)` — order of replicas doesn't matter
2. **Associative**: `merge(merge(A, B), C) = merge(A, merge(B, C))` — grouping doesn't matter
3. **Idempotent**: `merge(A, A) = A` — merging the same state twice is harmless

These three properties together guarantee **strong eventual consistency**: any set of replicas that have observed all updates will converge to identical state, regardless of message delivery order or network partitions.

---

## State-Based CRDTs (CvRDTs)

crdt-merge implements **state-based CRDTs** (convergent replicated data types):

- Each replica stores full local state
- On sync, replicas exchange full state objects
- The merge function computes the join (least upper bound) of two states

The alternative (op-based / CmRDT) transmits individual operations. State-based CRDTs are simpler to reason about and handle dropped messages naturally.

---

## GCounter — Grow-Only Counter

Each node gets its own slot. The global value is the sum; merge takes per-node max.

```python
from crdt_merge.core import GCounter

# Two replicas start independently
node_a = GCounter()
node_b = GCounter()

node_a.increment("node_a", 5)   # A counts 5 events
node_b.increment("node_b", 3)   # B counts 3 events — offline, no sync yet

# A also increments again
node_a.increment("node_a", 2)   # A total: 7

# Sync: merge takes element-wise max
merged = node_a.merge(node_b)
print(merged.value)              # 10 (7 + 3)

# Idempotent: merging same state twice gives same result
merged2 = merged.merge(node_a)
assert merged2.value == merged.value   # ✅

# Commutative: order doesn't matter
m1 = node_a.merge(node_b)
m2 = node_b.merge(node_a)
assert m1.value == m2.value            # ✅
```

**Why `max` works**: Each node only increments its own slot, so the true count for that node is monotonically increasing. `max` correctly identifies the most recent known count.

**Serialization**:
```python
# Round-trip through dict
d = merged.to_dict()
restored = GCounter.from_dict(d)
assert restored.value == merged.value

# Wire format (binary, cross-language compatible)
from crdt_merge.wire import serialize, deserialize
data = serialize(merged)
restored = deserialize(data)
assert restored.value == merged.value
```

---

## PNCounter — Increment and Decrement

Two GCounters internally: one for increments (`P`), one for decrements (`N`). Net value = P - N.

```python
from crdt_merge.core import PNCounter

inventory_a = PNCounter()
inventory_b = PNCounter()

# A adds 10 items to stock
inventory_a.increment("warehouse_a", 10)

# B sells 3 items concurrently
inventory_b.decrement("warehouse_b", 3)

# Sync
merged = inventory_a.merge(inventory_b)
print(merged.value)   # 7 (10 - 3)

# Another sale on B while offline
inventory_b.decrement("warehouse_b", 2)
merged2 = merged.merge(inventory_b)
print(merged2.value)  # 5 (10 - 5)
```

**Why `P` and `N` stay separate**: If you stored net value per-node, you couldn't distinguish `+5` from `+7, -2`. Keeping separate counters preserves the full history of increments and decrements, enabling correct merge via element-wise max on each.

---

## LWWRegister — Last-Writer-Wins Single Value

Stores one value. Higher timestamp wins. Tie-break: lexicographic node ID comparison.

```python
from crdt_merge.core import LWWRegister
import time

# Two nodes update the same field concurrently
reg_a = LWWRegister(value="Alice", timestamp=1000.0, node_id="node_a")
reg_b = LWWRegister(value="Alicia", timestamp=1001.0, node_id="node_b")

merged = reg_a.merge(reg_b)
print(merged.value)      # "Alicia" — higher timestamp wins

# Exact same timestamp — node_id tie-break (lexicographic)
reg_c = LWWRegister(value="v1", timestamp=1000.0, node_id="node_a")
reg_d = LWWRegister(value="v2", timestamp=1000.0, node_id="node_b")

merged_cd = reg_c.merge(reg_d)
print(merged_cd.value)   # "v2" — "node_b" > "node_a" lexicographically

# Commutativity check
assert reg_a.merge(reg_b).value == reg_b.merge(reg_a).value   # ✅
```

**Tie-breaking gotcha**: `"node9" > "node10"` because `"9" > "1"` lexicographically. Use zero-padded IDs: `"node09"`, `"node10"`.

**Reading with timestamp**:
```python
reg = LWWRegister(value="hello", timestamp=time.time(), node_id="node1")
print(reg.value)       # "hello"
print(reg.timestamp)   # Unix timestamp float
```

---

## ORSet — Observed-Remove Set

Each `add()` generates a unique tag. `remove()` clears all current tags. Concurrent `add + remove` resolves in favour of `add` (add-wins semantics).

```python
from crdt_merge.core import ORSet

replica_a = ORSet()
replica_b = ORSet()

# A adds element "x"
tag = replica_a.add("x")
print(tag)              # e.g., "a3f8c2d1e9b0"  (12-char hex)
print(replica_a.value)  # {"x"}

# B concurrently removes "x" — but B hasn't seen A's add yet
replica_b.add("x")     # B must add before removing
replica_b.remove("x")
print(replica_b.value)  # set() — removed from B's perspective

# Merge — A's unique tag survives B's remove
merged = replica_a.merge(replica_b)
print(merged.value)     # {"x"}  — A's add-tag was not known to B when B removed
```

**Why add-wins**: Each add generates a UUID tag. Remove clears only the tags the node has observed. B's remove clears B's own tag — it cannot clear A's tag because B never observed A's add. After merge, A's tag is present → element is alive.

**Membership check**:
```python
s = ORSet()
s.add("alpha")
s.add("beta")
s.remove("alpha")

print("alpha" in s.value)  # False
print("beta" in s.value)   # True
print(s.value)             # {"beta"}
```

**Elements method**:
```python
s = ORSet()
s.add("x")
s.add("y")
# Use .value property (set of live elements)
for elem in s.value:
    print(elem)
```

---

## LWWMap — Distributed Key-Value Store

A map where each key is an independent LWWRegister. Keys can be added and updated independently across replicas.

```python
from crdt_merge.core import LWWMap
import time

map_a = LWWMap(node_id="node_a")
map_b = LWWMap(node_id="node_b")

now = time.time()

map_a.set("name", "Alice", timestamp=now)
map_a.set("email", "alice@example.com", timestamp=now)

map_b.set("email", "alice@corp.com", timestamp=now + 5)  # Later update
map_b.set("role", "admin", timestamp=now + 1)

merged = map_a.merge(map_b)
print(merged.get("name"))    # "Alice"        — only A has this key
print(merged.get("email"))   # "alice@corp.com" — B's higher-ts value wins
print(merged.get("role"))    # "admin"         — only B has this key

# All keys visible after merge
print(merged.keys())         # {"name", "email", "role"}
```

---

## Convergence Theorem — Illustrated

```python
from crdt_merge.core import GCounter

# Three replicas, each receives updates in different order
r1 = GCounter(); r1.increment("a", 1); r1.increment("b", 2)
r2 = GCounter(); r2.increment("b", 2); r2.increment("c", 3)
r3 = GCounter(); r3.increment("a", 1); r3.increment("c", 3)

# Different merge orders
path1 = r1.merge(r2).merge(r3)
path2 = r3.merge(r1).merge(r2)
path3 = r2.merge(r3).merge(r1)

assert path1.value == path2.value == path3.value   # ✅ Always converge
print(path1.value)  # 6 (1 + 2 + 3)
```

**Proof sketch**: The merge operation (`max` per slot) is commutative, associative, and idempotent. The final state is the element-wise maximum across all inputs — a unique value independent of processing order.

---

## Formal Verification

crdt-merge includes built-in property-based testing to verify CRDT properties:

```python
from crdt_merge.verify import verify_crdt
from crdt_merge.core import GCounter, LWWRegister, ORSet

# Verify all three CRDT properties with 100 random test cases each
for cls in [GCounter, LWWRegister, ORSet]:
    result = verify_crdt(cls)
    print(f"{cls.__name__}: commutativity={result.commutativity.passed}, "
          f"associativity={result.associativity.passed}, "
          f"idempotency={result.idempotency.passed}")
```

See [CRDT Verification Toolkit](crdt-verification-toolkit.md) for custom strategy verification and property-based testing patterns.

---

## Choosing the Right Primitive

| Use case | Primitive | Why |
|---|---|---|
| Page view counter | `GCounter` | Monotonically increasing |
| Inventory level | `PNCounter` | Bidirectional |
| User profile field | `LWWRegister` | Single latest value |
| Tag set, membership | `ORSet` | Add-wins concurrent updates |
| Key-value record | `LWWMap` | Per-field LWW |
| DataFrame column | `MergeSchema` + strategy | Per-field strategies |

For DataFrame merging with configurable per-column strategies, see [Merge Strategies](merge-strategies.md).

For working examples of every primitive, see [CRDT Primitives Reference](crdt-primitives-reference.md).
