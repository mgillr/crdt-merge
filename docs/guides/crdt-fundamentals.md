# CRDT Fundamentals — Deep Dive

## Mathematical Foundation

A CRDT is a data type equipped with a merge function that forms a **join-semilattice**:

1. **Commutative**: `a ⊔ b = b ⊔ a`
2. **Associative**: `(a ⊔ b) ⊔ c = a ⊔ (b ⊔ c)`
3. **Idempotent**: `a ⊔ a = a`

Where `⊔` is the merge (join/least-upper-bound) operation.

## State-Based CRDTs (CvRDTs)

crdt-merge implements **state-based CRDTs** (convergent replicated data types):
- Each replica maintains full state
- States are transmitted and merged
- Merge function computes join of two states

### GCounter: The Simplest CRDT

Each node maintains its own counter. Merge takes per-node maximum.

```
Node A: {"a": 5, "b": 3}
Node B: {"a": 3, "b": 7}
Merge:  {"a": 5, "b": 7}  ← element-wise max
```

**Why this works**: `max` is commutative, associative, and idempotent. ✅

### PNCounter: Increment AND Decrement

Uses two GCounters: one for increments (`P`), one for decrements (`N`).

```
Value = P.value - N.value
Merge: P_merged = P_a.merge(P_b), N_merged = N_a.merge(N_b)
```

### LWWRegister: Timestamp-Based Resolution

Stores value with timestamp. Higher timestamp wins.

**Tie-breaking is critical**: Without deterministic tie-breaking, commutativity breaks. crdt-merge uses lexicographic `node_id` comparison.

### ORSet: Add-Wins Semantics

Each add generates a unique tag. Remove clears all tags.

**Key insight**: If node A adds element X (generating tag T1) and node B concurrently removes X (clearing its known tags), after merge node A's tag T1 is preserved. **Add wins over concurrent remove.**

## Convergence Theorem

Given any set of replicas R1, R2, ..., Rn with initial state S, and any sequence of local updates and merges, all replicas that have observed all updates will converge to the same state, regardless of the order of merges.

**Proof sketch**: Since merge is commutative, associative, and idempotent, the order of application doesn't matter. The final state is the join of all individual states, which is unique.
