# Convergence Guarantees

Mathematical proofs and practical verification of CRDT convergence properties.

---

## Strong Eventual Consistency (SEC)

crdt-merge provides **Strong Eventual Consistency** (Shapiro et al., 2011):

> If two replicas have received the same set of updates (in any order), they will be in the same state.

This is stronger than eventual consistency because it requires no additional conflict resolution — the CRDT merge function handles everything deterministically.

**Formal definition**: A data type `T` with merge function `⊔` satisfies SEC if and only if `⊔` forms a **join-semilattice**:
1. Commutative: `a ⊔ b = b ⊔ a`
2. Associative: `(a ⊔ b) ⊔ c = a ⊔ (b ⊔ c)`
3. Idempotent: `a ⊔ a = a`

---

## Convergence Theorem

**Theorem**: For any CRDT type `T` with merge function `⊔`, given any set of replicas R₁…Rₙ that have each received all updates U₁…Uₘ (in any order), all replicas converge to the same unique state S:

```
R₁.state ⊔ R₂.state ⊔ … ⊔ Rₙ.state = S   (unique, regardless of merge order)
```

**Proof**:
1. `⊔` is commutative → order of pairwise merges doesn't matter
2. `⊔` is associative → grouping of merges doesn't matter
3. `⊔` is idempotent → duplicate deliveries are harmless
4. Therefore, any sequence of merges incorporating all states reaches the same S ∎

**Code demonstration**:
```python
from crdt_merge.core import GCounter

# Three replicas with identical updates
r1 = GCounter(); r1.increment("a", 5)
r2 = GCounter(); r2.increment("b", 3)
r3 = GCounter(); r3.increment("c", 2)

# Six different merge orderings
paths = [
    r1.merge(r2).merge(r3),
    r1.merge(r3).merge(r2),
    r2.merge(r1).merge(r3),
    r2.merge(r3).merge(r1),
    r3.merge(r1).merge(r2),
    r3.merge(r2).merge(r1),
]

# All converge to 10
assert all(p.value == 10 for p in paths)   # 
```

---

## Per-Strategy Proofs

### GCounter

Merge = element-wise maximum per node slot.

```
merge({a:5, b:3}, {a:3, b:7}) = {a:max(5,3), b:max(3,7)} = {a:5, b:7}
```

- **Commutative**: `max(a, b) = max(b, a)` 
- **Associative**: `max(max(a, b), c) = max(a, max(b, c))` 
- **Idempotent**: `max(a, a) = a` 

```python
from crdt_merge.core import GCounter

a = GCounter(); a.increment("x", 5)
b = GCounter(); b.increment("x", 3); b.increment("y", 7)

assert a.merge(b).value == b.merge(a).value   # commutative 
assert a.merge(a).value == a.value             # idempotent 
```

### LWWRegister

Merge = take value with higher timestamp. Equal timestamps: lexicographic `node_id` comparison.

- **Commutative**: Timestamp comparison `ts_a > ts_b` is antisymmetric; lexicographic node_id is a total order, so `resolve(A, B) = resolve(B, A)` 
- **Associative**: Transitivity of total timestamp + node_id order 
- **Idempotent**: Merging register with itself returns same value (same timestamp, same node_id) 

```python
from crdt_merge.core import LWWRegister

r1 = LWWRegister(value="v1", timestamp=1000.0, node_id="node_a")
r2 = LWWRegister(value="v2", timestamp=1001.0, node_id="node_b")

assert r1.merge(r2).value == r2.merge(r1).value   # commutative 
assert r1.merge(r1).value == r1.value              # idempotent 
```

### ORSet

Merge = union of tag sets per element. An element is live if it has at least one tag.

- **Commutative**: Set union is commutative (`A ∪ B = B ∪ A`) 
- **Associative**: Set union is associative (`(A ∪ B) ∪ C = A ∪ (B ∪ C)`) 
- **Idempotent**: Set union is idempotent (`A ∪ A = A`) 

```python
from crdt_merge.core import ORSet

a = ORSet(); a.add("x"); a.add("y")
b = ORSet(); b.add("y"); b.add("z")

m1 = a.merge(b)
m2 = b.merge(a)
assert m1.value == m2.value   # commutative 

m3 = a.merge(a)
assert m3.value == a.value    # idempotent 
```

**Add-wins**: A concurrent add and remove resolve in favour of the add:
```python
a = ORSet(); tag = a.add("x")      # A adds with unique tag
b = ORSet(); b.add("x"); b.remove("x")  # B adds then removes

merged = a.merge(b)
assert "x" in merged.value   # A's tag survives — add-wins
```

### MergeSchema Strategies

All eight built-in strategies satisfy the semilattice properties:

| Strategy | Commutativity | Associativity | Idempotency | Proof |
|---|---|---|---|---|
| `LWW` | | | | Timestamp order is total; tie-break is symmetric |
| `MaxWins` | | | | `max(a,b)=max(b,a)`, max is associative, `max(a,a)=a` |
| `MinWins` | | | | Same as MaxWins with min |
| `UnionSet` | | | | Set union is a join-semilattice |
| `Concat` | | | | Sort + dedup makes order-independent |
| `Priority` | | | | Total order on priority list; lex tiebreak |
| `LongestWins` | | | | Length comparison total; LWW fallback |
| `Custom` | | | | User must verify — use `verify_crdt()` |

---

## Built-In Verification

crdt-merge provides `verify_crdt()` for property-based testing of any type:

```python
from crdt_merge.verify import verify_crdt
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet

for cls in [GCounter, PNCounter, LWWRegister, ORSet]:
    result = verify_crdt(cls, trials=100)
    print(f"{cls.__name__}:")
    print(f"  commutativity: {result.commutativity.passed} ({result.commutativity.trials} trials)")
    print(f"  associativity: {result.associativity.passed} ({result.associativity.trials} trials)")
    print(f"  idempotency:   {result.idempotency.passed}   ({result.idempotency.trials} trials)")
```

**Verify a custom strategy**:
```python
from crdt_merge.verify import verify_crdt
from crdt_merge.strategies import Custom
from crdt_merge.core import LWWRegister

# Your merge function must be commutative
def my_merge(a, b):
    return max(str(a), str(b))   # symmetric 

result = verify_crdt(LWWRegister, strategy=Custom(fn=my_merge))
assert result.commutativity.passed   # Will fail if fn(a,b) ≠ fn(b,a)
```

---

## Causality and Vector Clocks

CRDTs guarantee state convergence. For causal ordering of operations (happened-before relationships), use vector clocks:

```python
from crdt_merge.clocks import VectorClock, Ordering

vc_a = VectorClock()
vc_b = VectorClock()

vc_a.increment("node_a")   # node_a does something
vc_b.increment("node_b")   # node_b does something concurrently

order = vc_a.compare(vc_b)
print(order)   # Ordering.CONCURRENT — neither happened-before the other

# After node_a receives node_b's clock
vc_a.merge(vc_b)
vc_a.increment("node_a")   # node_a acts after seeing node_b

order2 = vc_b.compare(vc_a)
print(order2)  # Ordering.BEFORE — vc_b happened before vc_a's latest event
```

**Dotted Version Vectors** (more efficient for single-key causality):
```python
from crdt_merge.clocks import DottedVersionVector

dvv = DottedVersionVector(node_id="node_a")
dot = dvv.next_dot()   # (node_a, seq_number) — uniquely identifies this event
```

---

## Limitations

CRDTs guarantee convergence — they do NOT guarantee:

1. **Business logic correctness**: Two nodes can concurrently add the same user — ORSet add-wins means both persist. Application deduplication is needed.
2. **Cross-key transactions**: Each key is merged independently. Maintaining `total = a + b` across two keys is not CRDT-safe.
3. **Bounded divergence time**: SEC provides no time bound. Replicas can diverge for arbitrarily long — they'll converge when they eventually communicate.
4. **Idempotency of model merge strategies**: Most model merge strategies (SLERP, TIES, DARE) are NOT idempotent on tensors directly. `CRDTMergeState` provides the CRDT wrapper that makes them idempotent at the contribution-set level. See [Model CRDT Matrix](../guides/model-crdt-matrix.md).
