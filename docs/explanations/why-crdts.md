# Why CRDTs for Merging?

The case for CRDT-based merging over traditional approaches, with concrete examples.

---

## The Problem

When two replicas of the same data diverge, you need to merge them. Traditional approaches all have fundamental problems:

| Approach | Problem | Example |
|---|---|---|
| Last-write-wins (global) | Data loss — the "newer" write may overwrite an important value | Alice updates email on mobile (ts=1001), Bob updates email on desktop (ts=1000). Mobile wins, but Bob's update was intentional. |
| Manual conflict resolution | Doesn't scale; requires human intervention | 1000 replicas, each with a different value for the same field |
| Operational transforms | Order-dependent; hard to implement correctly | Must buffer and re-order operations across all nodes |
| Consensus (Paxos/Raft) | Requires coordination; not available offline | Partition → no merges until quorum restored |
| Application-level merge | Reimplemented per-app; bugs in every implementation | Every team writes their own "latest wins" logic |

---

## The CRDT Solution

CRDTs provide **automatic, correct, coordination-free merging** via three mathematical properties:

1. **Commutative**: `merge(A, B) = merge(B, A)` — any message arrival order works
2. **Associative**: `merge(merge(A, B), C) = merge(A, merge(B, C))` — any grouping works
3. **Idempotent**: `merge(A, A) = A` — duplicate deliveries are harmless

These three properties together guarantee **strong eventual consistency**: any replicas that have seen all updates will be in the same state, regardless of what order they processed them.

```python
from crdt_merge.core import GCounter

# Three nodes, each increments independently and offline
node_a = GCounter(); node_a.increment("a", 5)
node_b = GCounter(); node_b.increment("b", 3)
node_c = GCounter(); node_c.increment("c", 2)

# Different merge orders all converge to the same value
path1 = node_a.merge(node_b).merge(node_c)
path2 = node_c.merge(node_a).merge(node_b)
path3 = node_b.merge(node_c).merge(node_a)

assert path1.value == path2.value == path3.value == 10   # ✅ Always 10
```

---

## Why Not Just "Latest Timestamp Wins"?

Simple LWW (Last-Writer-Wins with a global timestamp) is the obvious alternative. It fails in three important ways:

**Problem 1 — Data loss for non-scalar fields**

```python
# Two users update the same user's tags concurrently
user_a_tags = "python,ml"      # at t=1000
user_b_tags = "python,ai"      # at t=1001

# LWW: b wins, a's "ml" tag is silently lost
global_lww = user_b_tags      # "python,ai" — "ml" is gone

# CRDT UnionSet: preserves both
from crdt_merge.strategies import UnionSet
s = UnionSet(separator=",")
result = s.resolve(user_a_tags, user_b_tags)   # "ai,ml,python" — nothing lost
```

**Problem 2 — Wrong winner for domain-specific values**

```python
# Status field: "approved" should always beat "draft" regardless of timestamp
# Node A (old replica): status="approved", ts=1000
# Node B (new replica): status="draft",    ts=1001

# Global LWW: "draft" wins because it's newer — regression!
# CRDT Priority: "approved" wins regardless
from crdt_merge.strategies import Priority
s = Priority(["draft", "review", "approved", "published"])
print(s.resolve("approved", "draft", ts_a=1000, ts_b=1001))  # "approved" ✅
```

**Problem 3 — Numeric aggregates require both values**

```python
# vote counter: we want the sum, not the latest value
# Node A: 45 votes  Node B: 52 votes (concurrent, different voters)

# LWW: 52 votes (47 votes from Node A are lost)
# CRDT GCounter: 97 votes (correct total)
from crdt_merge.core import GCounter
a = GCounter(); a.increment("node_a", 45)
b = GCounter(); b.increment("node_b", 52)
print(a.merge(b).value)  # 97 ✅
```

---

## Per-Field Strategy Selection

crdt-merge's `MergeSchema` applies the mathematically correct strategy per field:

```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority, Concat

schema = MergeSchema(
    # LWW: name, email — most recent update is correct
    name=LWW(),
    email=LWW(),
    # MaxWins: version number, score — higher is correct
    version=MaxWins(),
    score=MaxWins(),
    # MinWins: price, expiry — lower/earliest is binding
    price=MinWins(),
    expires_at=MinWins(),
    # UnionSet: tags — merge both sets, no loss
    tags=UnionSet(separator=","),
    # Priority: status — follows workflow state machine
    status=Priority(["draft", "review", "approved", "published"]),
    # Concat: notes — preserve all updates
    notes=Concat(separator=" | "),
)

result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="updated_at")
```

---

## When CRDTs Are The Right Choice

- **Distributed databases with eventual consistency**: Multiple write regions
- **Offline-first applications**: Mobile apps that sync when connected
- **Multi-master replication**: Active-active database configurations
- **Edge computing and IoT**: Sensors that batch-sync periodically
- **ML model federation**: Combining models trained on private data across hospitals, devices
- **Multi-agent AI systems**: Multiple agents updating shared knowledge state
- **Collaborative tools**: Shared documents, spreadsheets, whiteboards

---

## When CRDTs Are Not Enough

CRDTs guarantee convergence but not correctness for all business rules:

- **Transactions across multiple keys**: CRDTs merge keys independently. If you need `balance = credit - debit` to remain consistent across a multi-key transaction, you need a transaction layer.
- **Unique constraint enforcement**: ORSet add-wins means concurrent adds of the same logical entity can both persist. Application code must handle deduplication after merge.
- **Ordered operations**: If operation B must always be applied after operation A on a given key, you need vector clocks or causal ordering on top of CRDTs.

For these cases, use crdt-merge's vector clocks alongside CRDT primitives:

```python
from crdt_merge.clocks import VectorClock

vc_a = VectorClock()
vc_b = VectorClock()

vc_a.increment("node_a")
vc_b.increment("node_b")

# Check causality
from crdt_merge.clocks import Ordering
order = vc_a.compare(vc_b)
print(order)   # Ordering.CONCURRENT — neither happened-before the other
```
