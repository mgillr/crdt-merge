# CRDT Primitives Reference

Complete working examples for all CRDT primitive types.

## GCounter (Grow-Only Counter)

```python
from crdt_merge import GCounter

# Create counters (node_id is optional but recommended)
c1 = GCounter(node_id="server_west")
c2 = GCounter(node_id="server_east")

# increment(node_id, amount) — node_id is REQUIRED
c1.increment("server_west", 5)
c2.increment("server_east", 3)

# Merge: per-node maximum, then sum
merged = c1.merge(c2)
print(merged.value)  # 8 (5 + 3)
```

## PNCounter (Positive-Negative Counter)

```python
from crdt_merge import PNCounter

p1 = PNCounter()
p2 = PNCounter()

# increment(node_id, amount) and decrement(node_id, amount)
p1.increment("node_a", 10)
p2.decrement("node_b", 3)

merged = p1.merge(p2)
print(merged.value)  # 7 (10 - 3)
```

## LWWRegister (Last-Writer-Wins Register)

```python
from crdt_merge import LWWRegister

r1 = LWWRegister(value="old_value", timestamp=1.0)
r2 = LWWRegister(value="new_value", timestamp=2.0)

merged = r1.merge(r2)
print(merged.value)  # "new_value" (higher timestamp wins)
```

## ORSet (Observed-Remove Set)

```python
from crdt_merge import ORSet

s1 = ORSet()
s2 = ORSet()

s1.add("x")
s1.add("y")
s2.add("y")
s2.add("z")

merged = s1.merge(s2)
print(merged.value)  # {'x', 'y', 'z'}

# Check membership
print(merged.contains("x"))  # True
```

## LWWMap (Last-Writer-Wins Map)

```python
from crdt_merge import LWWMap

m1 = LWWMap()
m2 = LWWMap()

m1.set("key1", "val_a", timestamp=1.0)
m2.set("key1", "val_b", timestamp=2.0)
m2.set("key2", "val_c", timestamp=1.0)

merged = m1.merge(m2)
print(merged.get("key1"))  # "val_b" (higher timestamp)
print(merged.get("key2"))  # "val_c"
```

## VectorClock

> **Note**: VectorClock is **immutable**. `increment()` returns a NEW clock.

```python
from crdt_merge import VectorClock, Ordering

vc1 = VectorClock()
vc1 = vc1.increment("node_a")  # Returns new clock!
vc1 = vc1.increment("node_a")  # node_a counter is now 2

vc2 = VectorClock()
vc2 = vc2.increment("node_b")

merged = vc1.merge(vc2)
# After merge, merged contains both nodes' counts

# Compare causality
ordering = vc1.compare(vc2)
print(ordering)  # Ordering.CONCURRENT (independent events)
```

## Probabilistic Structures

### MergeableHLL (HyperLogLog)

```python
from crdt_merge import MergeableHLL

h1 = MergeableHLL()
h2 = MergeableHLL()

for i in range(100):
    h1.add(f"item_{i}")
for i in range(50, 150):
    h2.add(f"item_{i}")

merged = h1.merge(h2)
print(merged.cardinality())  # ~150 (approximate count of unique items)
```

### MergeableBloom (Bloom Filter)

```python
from crdt_merge import MergeableBloom

# Use fp_rate (not error_rate)
b1 = MergeableBloom(capacity=1000, fp_rate=0.01)
b2 = MergeableBloom(capacity=1000, fp_rate=0.01)

b1.add("hello")
b2.add("world")

merged = b1.merge(b2)
print(merged.contains("hello"))  # True (use .contains(), not 'in')
print(merged.contains("world"))  # True
```

### MergeableCMS (Count-Min Sketch)

```python
from crdt_merge import MergeableCMS

c1 = MergeableCMS()
c2 = MergeableCMS()

c1.add("apple", 5)
c2.add("apple", 3)

merged = c1.merge(c2)
print(merged.estimate("apple"))  # ≥ 5 (use .estimate(), not .count())
```

## Deduplication

```python
from crdt_merge import dedup, dedup_records

# dedup() works on strings, returns (unique_items, removed_indices)
unique, removed = dedup(["alice", "bob", "alice", "carol"])
print(unique)    # ["alice", "bob", "carol"]
print(removed)   # [2]

# dedup_records() works on list-of-dicts
records = [
    {"id": 1, "name": "Alice"},
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
]
unique_records, num_removed = dedup_records(records, columns=["id"])
print(len(unique_records))  # 2
print(num_removed)          # 1
```

## Verification

```python
from crdt_merge.verify import verify_crdt
from crdt_merge import GCounter
import random

# verify_crdt takes callable factories, not instances
def make_gcounter():
    c = GCounter()
    for _ in range(random.randint(1, 5)):
        c.increment(f"node_{random.randint(0,3)}", random.randint(1, 10))
    return c

result = verify_crdt(
    merge_fn=lambda a, b: a.merge(b),
    gen_fn=make_gcounter,
    trials=100,
)
print(result)  # CRDTVerification with commutative, associative, idempotent checks
```
