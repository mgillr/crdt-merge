# How Conflicts Are Resolved

## What Is a Conflict?

A conflict occurs when two replicas have different values for the same field of the same record.

## Resolution Process

1. **Row Matching**: Records are matched by key column (e.g., `id`)
2. **Per-Field Resolution**: Each conflicting field is resolved independently using its assigned strategy
3. **Strategy Application**: The strategy's `resolve()` method determines the winning value

```
Row in df_a: {"id": 1, "name": "Alice", "score": 80}
Row in df_b: {"id": 1, "name": "Bob",   "score": 90}

Schema: name=LWW(timestamp), score=MaxWins()

Result:    {"id": 1, "name": "Bob",   "score": 90}
                     ↑ LWW chose Bob    ↑ MaxWins chose 90
```

## Edge Cases

### Both Values Are None
Most strategies return `None`. This is still CRDT-compliant.

### Only One Value Exists
If a field exists in only one replica, that value is used (no conflict).

### Values Are Equal
The value is used as-is. This is the idempotent case — `merge(a, a) = a`.

### Timestamp Ties
When timestamps are equal (LWW strategy), the tie-break uses lexicographic string comparison. This ensures determinism but can be unintuitive.

---

## Conflict Resolution Examples

The following examples demonstrate how `crdt_merge` resolves common concurrent-update scenarios using its built-in CRDT primitives. All imports come from `crdt_merge.core`.

### 1. Concurrent LWWMap Writes — Same Key, Different Values

When two nodes write to the same key concurrently, the **latest timestamp wins**. If timestamps are equal, lexicographic `node_id` comparison breaks the tie.

```python
from crdt_merge.core import LWWMap

# Node A writes "status" = "active" at timestamp 1000.0
node_a = LWWMap()
node_a.set("status", "active", timestamp=1000.0, node_id="node_a")

# Node B writes "status" = "inactive" at timestamp 1001.0 (later)
node_b = LWWMap()
node_b.set("status", "inactive", timestamp=1001.0, node_id="node_b")

# Merge: Node B's write wins because its timestamp is higher
merged = node_a.merge(node_b)
print(merged.get("status"))  # "inactive"

# Verify commutativity: merge order doesn't matter
merged_reverse = node_b.merge(node_a)
print(merged_reverse.get("status"))  # "inactive"
```

When both nodes also write to *different* keys concurrently, both values are preserved:

```python
from crdt_merge.core import LWWMap

node_a = LWWMap()
node_a.set("color", "red", timestamp=1000.0, node_id="node_a")

node_b = LWWMap()
node_b.set("size", "large", timestamp=1000.0, node_id="node_b")

merged = node_a.merge(node_b)
print(merged.value)  # {"color": "red", "size": "large"}
```

### 2. ORSet: Concurrent Add and Remove — Add-Wins Semantics

An `ORSet` (Observed-Remove Set) uses unique tags per addition. When one node adds an element while another concurrently removes it (without seeing the add), the **add wins** — this is the "add-wins" semantic that defines ORSet behavior.

```python
from crdt_merge.core import ORSet

# Node A adds "apple"
node_a = ORSet()
node_a.add("apple")

# Node B independently adds "banana" and removes "apple"
# Node B hasn't seen node A's add, so "apple" is not in its set — remove is a no-op
node_b = ORSet()
node_b.add("banana")
# node_b.remove("apple")  ← no-op since "apple" was never added locally

# Merge: both elements survive
merged = node_a.merge(node_b)
print(merged.value)  # {"apple", "banana"}
```

Now consider the case where both nodes share initial state and then diverge:

```python
from crdt_merge.core import ORSet

# Shared initial state: both nodes start with "apple"
shared = ORSet()
tag = shared.add("apple")

# Fork into two replicas (simulate by creating independent sets with same tags)
import copy

# Node A: adds "cherry" (has "apple" + "cherry")
node_a = ORSet()
node_a._elements = copy.deepcopy(shared._elements)
node_a.add("cherry")

# Node B: removes "apple" (clears all tags for "apple")
node_b = ORSet()
node_b._elements = copy.deepcopy(shared._elements)
node_b.remove("apple")

# Merge: node B's remove clears the original tag, but if node A had re-added "apple"
# with a NEW tag, that new tag would survive. Here, node A didn't re-add, so:
merged = node_a.merge(node_b)
# "apple" still has tags from node_a (the original tag survives because
# merge = tag union; node_b's empty set ∪ node_a's tag set = node_a's tags)
print("apple" in merged.value)  # True — tag union preserves node_a's tags
print("cherry" in merged.value)  # True
```

**Key insight:** ORSet merge is a *tag-level set union*. An element is live if it has ≥ 1 tag after union. `remove()` clears tags locally, but tags from other replicas survive the merge.

### 3. LWWRegister Tie-Breaking — Lexicographic node_id Comparison

When two `LWWRegister` values have **identical timestamps**, the `node_id` with the greater lexicographic value wins. This is deterministic, commutative, and requires no coordination.

```python
from crdt_merge.core import LWWRegister

# Both nodes write at exactly the same timestamp
reg_a = LWWRegister("value_from_A", timestamp=1000.0, node_id="node_a")
reg_b = LWWRegister("value_from_B", timestamp=1000.0, node_id="node_b")

# "node_b" > "node_a" lexicographically → node B wins
merged = reg_a.merge(reg_b)
print(merged.value)  # "value_from_B"

# Commutativity holds
merged_reverse = reg_b.merge(reg_a)
print(merged_reverse.value)  # "value_from_B"
```

**Gotcha — lexicographic ordering is NOT numeric ordering:**

```python
from crdt_merge.core import LWWRegister

reg_9  = LWWRegister("nine",  timestamp=500.0, node_id="node9")
reg_10 = LWWRegister("ten",   timestamp=500.0, node_id="node10")

# "node9" > "node10" lexicographically (because "9" > "1" in char comparison)
merged = reg_9.merge(reg_10)
print(merged.value)  # "nine" — node9 wins!
```

**Recommendation:** Use zero-padded node identifiers (`node01`, `node02`, …, `node10`) or UUIDs to avoid surprises.

### 4. GCounter Concurrent Increments — Per-Node Slot Max Merge

A `GCounter` maintains independent slots for each node. Merge takes the **max of each slot**, ensuring concurrent increments from different nodes are both captured.

```python
from crdt_merge.core import GCounter

# Node A increments 3 times
node_a = GCounter()
node_a.increment("node_a", 3)
node_a.increment("node_b", 0)  # hasn't seen node_b's updates

# Node B increments 5 times
node_b = GCounter()
node_b.increment("node_b", 5)
node_b.increment("node_a", 0)  # hasn't seen node_a's updates

# Merge: max of each slot → {node_a: 3, node_b: 5} → total = 8
merged = node_a.merge(node_b)
print(merged.value)  # 8

# If both nodes have partial knowledge of each other:
partial_a = GCounter()
partial_a.increment("node_a", 3)
partial_a.increment("node_b", 2)  # saw node_b at count=2

partial_b = GCounter()
partial_b.increment("node_b", 5)  # node_b continued to count=5
partial_b.increment("node_a", 1)  # saw node_a at count=1

merged = partial_a.merge(partial_b)
# max(3, 1) for node_a = 3; max(2, 5) for node_b = 5 → total = 8
print(merged.value)  # 8
```

**Key property:** GCounter merge is a *join* in the lattice — the result is always ≥ both inputs. No increments are ever lost.

---

## Timestamp Tie-Breaking

When two values have the same timestamp, `crdt_merge` uses a **deterministic tie-breaking rule** that requires no coordination between nodes:

| CRDT Type | Tie-Breaking Rule | Implementation |
|-----------|-------------------|----------------|
| `LWWRegister` | Lexicographic `node_id` comparison — higher wins | `if other._node_id > self._node_id: return other` |
| `LWW` strategy | Lexicographic `str(value)` comparison — higher wins | `if str_a >= str_b: return val_a` |
| `GCounter` | N/A — merge takes max per slot, no ties possible | `max(self.get(k, 0), other.get(k, 0))` |
| `ORSet` | N/A — merge is tag union, no ties possible | `tags_a \| tags_b` |

For detailed information on timestamp handling, see [Timestamp Handling](timestamp-handling.md).
