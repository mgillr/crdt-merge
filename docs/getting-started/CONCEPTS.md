# Core Concepts

The mental model you need to use crdt-merge effectively.

---

## What is a CRDT?

A **Conflict-Free Replicated Data Type** (CRDT) is a data structure that can be replicated across multiple nodes and merged without coordination, always converging to the same state.

### Three Mathematical Guarantees

```python
from crdt_merge.core import GCounter

a = GCounter(); a.increment("node_a", 5)
b = GCounter(); b.increment("node_b", 3)

# 1. Commutative: merge(A, B) == merge(B, A)
assert a.merge(b).value == b.merge(a).value   # ✅ order doesn't matter

# 2. Associative: merge(merge(A, B), C) == merge(A, merge(B, C))
c = GCounter(); c.increment("node_c", 2)
assert a.merge(b).merge(c).value == a.merge(b.merge(c)).value  # ✅ grouping OK

# 3. Idempotent: merge(A, A) == A
assert a.merge(a).value == a.value   # ✅ duplicate messages harmless
```

**Why this matters**: In distributed systems, you can't guarantee message delivery order, or that messages aren't delivered twice. CRDTs make all three irrelevant.

---

## CRDT Primitives

Five core types, each designed for a specific pattern:

### GCounter — Grow-Only Counter

```python
from crdt_merge.core import GCounter

views = GCounter()
views.increment("server_1", 1_000_000)  # Server 1 counted 1M views
views.increment("server_2", 500_000)    # Server 2 counted 500K views

print(views.value)   # 1,500,000 (correct total)

# Merge any two replicas
replica_a = GCounter(); replica_a.increment("eu", 200)
replica_b = GCounter(); replica_b.increment("us", 150)
merged = replica_a.merge(replica_b)
print(merged.value)   # 350
```

**Use for**: Page views, download counts, event counters, any monotonically increasing quantity.

### PNCounter — Bidirectional Counter

```python
from crdt_merge.core import PNCounter

stock = PNCounter()
stock.increment("warehouse_a", 100)   # 100 units added
stock.decrement("warehouse_b", 30)    # 30 units sold
print(stock.value)   # 70
```

**Use for**: Inventory levels, like/dislike counts, balance tracking.

### LWWRegister — Latest-Wins Single Value

```python
from crdt_merge.core import LWWRegister

reg_a = LWWRegister(value="alice@old.com", timestamp=1000.0, node_id="node_a")
reg_b = LWWRegister(value="alice@new.com", timestamp=1001.0, node_id="node_b")

merged = reg_a.merge(reg_b)
print(merged.value)   # "alice@new.com" — higher timestamp wins
```

**Use for**: Single scalar fields (name, email, status), any field where "most recent" is correct.

### ORSet — Add-Wins Set

```python
from crdt_merge.core import ORSet

# Add-wins: concurrent add + remove resolves to "add"
replica_a = ORSet(); replica_a.add("feature_x")  # A enables feature
replica_b = ORSet(); replica_b.add("feature_x"); replica_b.remove("feature_x")  # B disables

merged = replica_a.merge(replica_b)
print(merged.value)   # {"feature_x"} — A's add wins ✅
```

**Use for**: Permission sets, feature flags, tag lists, membership lists.

### LWWMap — Distributed Key-Value Store

```python
from crdt_merge.core import LWWMap
import time

now = time.time()
map_a = LWWMap(node_id="node_a")
map_b = LWWMap(node_id="node_b")

map_a.set("name", "Alice", timestamp=now)
map_b.set("email", "alice@corp.com", timestamp=now + 1)

merged = map_a.merge(map_b)
print(merged.get("name"))    # "Alice"
print(merged.get("email"))   # "alice@corp.com"
print(merged.keys())         # {"name", "email"}
```

**Use for**: Configuration stores, user profile records, feature flag maps.

---

## Merge Strategies

Strategies define how to resolve conflicts for individual **DataFrame fields**. Each satisfies the three CRDT properties.

```python
from crdt_merge.strategies import (
    LWW, MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins, Custom
)
```

| Strategy | Constructor | Rule | Best for |
|---|---|---|---|
| `LWW` | `LWW()` | Higher timestamp wins | Any scalar — most recent is correct |
| `MaxWins` | `MaxWins()` | Higher value always wins | Score, version, count |
| `MinWins` | `MinWins()` | Lower value always wins | Price, expiry, latency SLA |
| `UnionSet` | `UnionSet(separator=",")` | Set union of delimited values | Tag lists, permission sets |
| `Concat` | `Concat(separator=" \| ")` | Append both values (sorted, deduped) | Notes, audit history |
| `Priority` | `Priority(["a", "b", "c"])` | Higher index in list wins | Workflow states |
| `LongestWins` | `LongestWins()` | Longer string wins (LWW fallback) | Descriptions, bios |
| `Custom` | `Custom(fn=my_fn)` | Your function `(a, b) → result` | Anything else |

```python
# Strategy examples
from crdt_merge.strategies import LWW, MaxWins, Priority, UnionSet

print(LWW().resolve("old", "new", ts_a=1000, ts_b=1001))   # "new"
print(MaxWins().resolve(80, 95))                             # 95
print(MinWins().resolve(10.0, 8.5))                         # 8.5
print(UnionSet(",").resolve("python,ml", "python,ai"))      # "ai,ml,python"
print(Priority(["draft","review","published"]).resolve("draft", "published"))  # "published"
```

---

## MergeSchema — Per-Field Strategy Map

`MergeSchema` applies different strategies to different columns in the same row:

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority, Concat

schema = MergeSchema(
    default=LWW(),                                         # fallback for any unlisted field
    name=LWW(),                                            # most recent name
    score=MaxWins(),                                       # highest score wins
    price=MinWins(),                                       # lowest price is binding
    tags=UnionSet(separator=","),                          # union all tags
    notes=Concat(separator=" | "),                         # keep all notes
    status=Priority(["draft", "review", "approved", "published"]),
)

# Use in DataFrame merge
from crdt_merge import merge
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="updated_at")

# Use row-by-row
row_a = {"name": "Alice", "score": 80, "tags": "ml,python", "status": "review", "updated_at": 1000}
row_b = {"name": "Alice", "score": 95, "tags": "ai,python", "status": "approved", "updated_at": 999}
merged = schema.resolve_row(row_a, row_b, timestamp_col="updated_at")
print(merged["score"])    # 95 — MaxWins (ignores timestamp)
print(merged["tags"])     # "ai,ml,python" — UnionSet
print(merged["status"])   # "approved" — Priority (ignores timestamp)
```

---

## Key Column

The `key` parameter is how rows are matched across the two DataFrames:

```python
# Single key
result = merge(df_a, df_b, key="id", schema=schema)

# Composite key
result = merge(df_a, df_b, key=["org_id", "user_id"], schema=schema)
```

- Rows with the same key → resolved using MergeSchema
- Rows only in df_a → included as-is
- Rows only in df_b → included as-is

---

## Timestamp Column

Used by `LWW` strategy to determine which value is "more recent":

```python
# Unix timestamp (int or float)
result = merge(df_a, df_b, key="id", timestamp_col="updated_at")

# ISO-8601 string — also supported
# df["updated_at"] = "2024-01-15T10:30:00"

# Without timestamp_col: LWW falls back to lexicographic value comparison
result = merge(df_a, df_b, key="id")
```

**Important**: `MaxWins`, `MinWins`, `Priority`, and `UnionSet` **ignore timestamps** — they always pick based on value semantics.

---

## The Two-Layer Model Merge Architecture

For ML model merging, `CRDTMergeState` provides CRDT guarantees on top of any strategy:

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# Layer 1 (CRDT): OR-Set of contributions — commutative, associative, idempotent
state_a = CRDTMergeState("weight_average")
state_a.add_contribution(model_a, model_id="hospital_a")

state_b = CRDTMergeState("weight_average")
state_b.add_contribution(model_b, model_id="hospital_b")

# Merge is set union — always commutative
merged = state_a.merge(state_b)
print(merged.state_hash)   # SHA-256 Merkle root

# Layer 2 (Strategy): applied at resolve() time — not per-pair
weights = merged.resolve()   # weight_average applied to all contributions at once
```

The key insight: strategies are **not** applied pairwise during merge. They're applied once, to all contributions, during `resolve()`. This is what makes all 26 strategies CRDT-safe.

---

## What To Read Next

| Topic | Guide |
|---|---|
| Deep-dive on CRDT math | [CRDT Fundamentals](../guides/crdt-fundamentals.md) |
| Working code for every primitive | [CRDT Primitives Reference](../guides/crdt-primitives-reference.md) |
| Every strategy explained | [Merge Strategies](../guides/merge-strategies.md) |
| When to use CRDTs vs alternatives | [Why CRDTs?](../explanations/why-crdts.md) |
| Convergence theorem and proofs | [Convergence Guarantees](../explanations/convergence-guarantees.md) |
| 6-layer architecture | [Architecture Layers](../explanations/architecture-layers.md) |
