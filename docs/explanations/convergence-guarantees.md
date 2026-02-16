# Convergence Guarantees

## Strong Eventual Consistency (SEC)

crdt-merge provides **Strong Eventual Consistency**:

> If two replicas have received the same set of updates (in any order), they will be in the same state.

This is stronger than eventual consistency because it doesn't require additional conflict resolution — the CRDT merge function handles everything.

## Proof Sketch

**Theorem**: For any CRDT type `T` with merge function `⊔`, given replicas R1...Rn that have each received all updates U1...Um:

```
R1.state ⊔ R2.state ⊔ ... ⊔ Rn.state = unique final state S
```

**Proof**:
1. Since `⊔` is commutative: order of pairwise merges doesn't matter
2. Since `⊔` is associative: grouping of merges doesn't matter
3. Since `⊔` is idempotent: duplicate merges are harmless
4. Therefore, any sequence of merges incorporating all states reaches the same S ∎

## Per-Strategy Proofs

### GCounter
- Merge = element-wise max
- `max(a, b) = max(b, a)` ✅ commutative
- `max(max(a, b), c) = max(a, max(b, c))` ✅ associative
- `max(a, a) = a` ✅ idempotent

### LWW
- Merge = take value with higher timestamp; deterministic tie-break
- Commutativity: tie-break function is symmetric ✅
- Associativity: transitivity of timestamp comparison ✅
- Idempotency: same timestamp → same value ✅

### ORSet
- Merge = union of tag sets per element
- Set union is commutative, associative, idempotent ✅
