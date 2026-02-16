# Core Concepts

## What is a CRDT?

A **Conflict-Free Replicated Data Type** (CRDT) is a data structure that can be replicated across multiple nodes and merged without coordination, always converging to the same state.

### Three Guarantees
1. **Commutative**: `merge(A, B) == merge(B, A)` — order doesn't matter
2. **Associative**: `merge(merge(A, B), C) == merge(A, merge(B, C))` — grouping doesn't matter
3. **Idempotent**: `merge(A, A) == A` — merging with yourself is a no-op

### Why This Matters
In distributed systems, you can't guarantee the order in which updates arrive. CRDTs ensure that no matter what order merges happen, you always get the same result.

## CRDT Primitives

| Type | Use Case | Resolution |
|------|----------|------------|
| **GCounter** | Page views, downloads | Grow-only; per-node max |
| **PNCounter** | Likes/dislikes, inventory | Two GCounters (pos - neg) |
| **LWWRegister** | Single values (name, email) | Latest timestamp wins |
| **ORSet** | Set membership (tags, roles) | Add wins over remove |
| **LWWMap** | Key-value stores | Per-key LWW semantics |

> For complete working examples of each primitive, see [CRDT Primitives Reference](../guides/crdt-primitives-reference.md).

## Merge Strategies

Strategies define how to resolve conflicts for individual fields:

| Strategy | Rule | Example |
|----------|------|---------|
| **LWW** | Latest timestamp wins | name: "Alice" (t=1) vs "Bob" (t=2) → "Bob" |
| **MaxWins** | Higher value wins | score: 80 vs 90 → 90 |
| **MinWins** | Lower value wins | price: $10 vs $15 → $10 |
| **UnionSet** | Union of values | tags: "a,b" + "b,c" → "a,b,c" |
| **Priority** | Ranked list wins | status: "draft" vs "published" → "published" |
| **Concat** | Concatenate (optionally dedup) | notes: "x" + "y" → "x | y" |
| **LongestWins** | Longer string wins | bio: "short" vs "detailed bio" → "detailed bio" |
| **Custom** | Your function | Any custom logic |

## MergeSchema

A MergeSchema maps field names to strategies:

```python
schema = MergeSchema(
    default=LWW(),                                    # Fallback
    name=LWW(),                                       # Names: latest wins
    score=MaxWins(),                                   # Scores: highest wins
    tags=UnionSet(),                                   # Tags: union
    status=Priority(["draft", "review", "published"]), # Status: escalate
)
```

## Architecture Layers

crdt-merge is organized into 6 layers:

1. **Core** — CRDT primitives and strategies (no dependencies)
2. **Engines** — Apply CRDTs to DataFrames, Arrow, Parquet, streams
3. **Transport** — Wire protocol, gossip, Merkle sync, delta compression
4. **AI/Model** — ML model merging, agentic state, MergeQL
5. **Enterprise** — Audit, encryption, RBAC, observability
6. **Compliance** — GDPR, HIPAA, SOX, EU AI Act auditing
