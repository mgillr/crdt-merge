> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Trust Quickstart

Practical recipes covering the core E4 trust-delta API. Every snippet runs
against `crdt-merge>=0.9.5`.

---

## Prerequisites

```bash
pip install crdt-merge>=0.9.5
```

Verify the E4 subsystem is available:

```python
import crdt_merge.e4 as e4
print(e4.__name__)  # crdt_merge.e4
```

---

## 1. Basic Trust Scoring

A `TypedTrustScore` tracks negative evidence across six dimensions
(`integrity`, `causality`, `consistency`, `gossip`, `model`, `context`).
Trust for each dimension starts at `PROBATION_TRUST` (0.5) and decreases
monotonically as verified evidence accumulates.

```python
from crdt_merge.e4.typed_trust import (
    TypedTrustScore,
    TrustHomeostasis,
    TRUST_DIMENSIONS,
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
)

# New peers start at probation -- no evidence yet
score = TypedTrustScore.probationary()
print(score.overall_trust())       # 0.5
print(score.verification_level())  # 1  (signature + Merkle root)
print(TRUST_DIMENSIONS)
# frozenset({'integrity', 'causality', 'consistency', 'gossip', 'model', 'context'})
```

### Observing evidence

`record_evidence` returns a **new** `TypedTrustScore` (immutable API).
The `proof` object must expose a `verify()` method that returns `True`.

```python
from crdt_merge.e4.proof_evidence import TrustEvidence

# Build verifiable evidence of a Merkle hash violation
evidence = TrustEvidence.create(
    observer="node-a",
    target="node-b",
    evidence_type="invalid_delta",
    dimension="integrity",
    amount=0.3,
    proof=b"\x00" * 33,  # 32-byte expected hash + 1-byte delta stub
)

# Record it against the target's score
updated = score.record_evidence(
    observer="node-a",
    dimension="integrity",
    amount=0.3,
    proof=evidence,
)

print(updated.trust_for_dimension("integrity"))  # 0.2
print(updated.overall_trust())                   # ~0.45
print(updated.verification_level())              # 1
```

### Checking individual dimensions

```python
for dim in sorted(TRUST_DIMENSIONS):
    print(f"  {dim}: {updated.trust_for_dimension(dim):.2f}")
# causality:    0.50
# consistency:  0.50
# context:      0.50
# gossip:       0.50
# integrity:    0.20
# model:        0.50
```

### CRDT merge

Two replicas of the same peer's score merge via element-wise max per
dimension per observer (GCounter semantics).

```python
replica_a = TypedTrustScore.probationary()
replica_b = TypedTrustScore.probationary()

# Different observers record evidence on different replicas
replica_a = replica_a.record_evidence(
    observer="node-x", dimension="integrity", amount=0.1, proof=evidence,
)
replica_b = replica_b.record_evidence(
    observer="node-y", dimension="gossip", amount=0.2, proof=evidence,
)

merged = replica_a.merge(replica_b)
print(merged.trust_for_dimension("integrity"))  # 0.4  (node-x evidence)
print(merged.trust_for_dimension("gossip"))     # 0.3  (node-y evidence)
```

---

## 2. Trust-Weighted Merge

The `TrustWeightedStrategySelector` routes conflicts to the appropriate
resolver based on data type and trust topology. High-trust peers dominate;
low-trust peers are filtered.

```python
from crdt_merge.e4.trust_weighted_strategy import (
    TrustWeightedStrategySelector,
    TrustWeightedLWWResolver,
    TrustWeightedAveragingResolver,
    TrustGatedAcceptanceFilter,
    ConflictEntry,
    ConflictType,
)
from crdt_merge.e4.typed_trust import TypedTrustScore

# Two peers report different values for the same key
high_trust = TypedTrustScore.full_trust()
low_trust = TypedTrustScore.probationary()

entries = [
    ConflictEntry(
        peer_id="trusted-peer",
        value=42.0,
        timestamp=1000.0,
        trust=high_trust,
        dimension="model",
    ),
    ConflictEntry(
        peer_id="new-peer",
        value=999.0,
        timestamp=2000.0,
        trust=low_trust,
        dimension="model",
    ),
]

selector = TrustWeightedStrategySelector()
result = selector.resolve(entries, ConflictType.NUMERIC)

print(result.resolved_value)   # close to 42.0 -- trusted peer dominates
print(result.method)           # trust_weighted_averaging
print(result.contributors)     # ('trusted-peer', 'new-peer')
```

### LWW with trust weighting

```python
lww = TrustWeightedLWWResolver(trust_weight_factor=1.0)
result = lww.resolve(entries)

# effective_t = timestamp * (1 + trust_weight)
# trusted-peer: 1000 * (1 + 0.5) = 1500
# new-peer:     2000 * (1 + 0.5) = 3000
# new-peer wins on effective timestamp despite lower trust
print(result.resolved_value)  # 999.0
print(result.method)          # trust_weighted_lww
```

### Trust gate (pre-merge filter)

```python
gate = TrustGatedAcceptanceFilter(
    thresholds={"integrity": 0.6},
    global_threshold=0.4,
    strict_mode=True,
)

accepted, rejected = gate.filter_entries(entries)
print(len(accepted))   # 2  (both above global threshold)
print(rejected)        # []
```

---

## 3. Proof-Carrying Operations

Every CRDT operation carries a 128-byte aggregate PCO covering four
properties: integrity, causality, trust, and minimality.

```python
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    SubtreeRef,
)
from crdt_merge.e4.typed_trust import TypedTrustScore

# Define a changed subtree
subtree = SubtreeRef(
    path=(42,),
    depth=1,
    old_hash="aaa111",
    new_hash="bbb222",
)

# Build a PCO
trust_score = TypedTrustScore.probationary()
pco = AggregateProofCarryingOperation.build(
    originator_id="node-a",
    signing_fn=lambda h: b"\x00" * 64,  # stub signer for demo
    merkle_root="deadbeef",
    clock_snapshot=b"\x00" * 16,
    trust_vector_hash=trust_score.hash(),
    delta_bounds=[subtree],
    version=1,
    flags=0,
)

print(pco)
# AggregatePCO(originator='node-a', hash=..., bounds=1)

# Wire format: exactly 128 bytes
wire = pco.to_wire()
print(len(wire))  # 128

# Deserialize from wire
restored = AggregateProofCarryingOperation.from_wire(
    wire,
    originator_id="node-a",
    merkle_root="deadbeef",
    clock_snapshot=b"\x00" * 16,
    trust_vector_hash=trust_score.hash(),
    delta_bounds=(subtree,),
)
```

### Adaptive verification levels

```python
# Level 0: signature only            O(1)
# Level 1: signature + Merkle root   O(1)
# Level 2: full aggregate PCO        O(k)
# Level 3: reject unconditionally    O(1)

result_l0 = pco.verify(state=None, trust_lattice=None, verification_level=0)
print(result_l0)  # True (signature passes)

result_l3 = pco.verify(state=None, trust_lattice=None, verification_level=3)
print(result_l3)  # False (always rejected)
```

---

## 4. Projection Deltas

`ProjectionDelta` encodes sparse state changes identified via O(log_B n)
high-arity Merkle tree traversal.

```python
from crdt_merge.e4.projection_delta import (
    ProjectionDelta,
    ProjectionDeltaManager,
    FrozenDict,
)
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef

# Build a minimal delta
subtree = SubtreeRef(path=(10,), depth=1, old_hash="aaa", new_hash="bbb")
pco = AggregateProofCarryingOperation.build(
    originator_id="node-a",
    signing_fn=lambda h: b"\x00" * 64,
    merkle_root="",
    clock_snapshot=b"",
    trust_vector_hash="",
    delta_bounds=[subtree],
)

delta = ProjectionDelta(
    source_id="node-a",
    source_version=None,
    target_version=None,
    changed_subtrees=(subtree,),
    insertions=FrozenDict({"key1": b"value1"}),
    updates=FrozenDict(),
    deletions=frozenset(),
    pco=pco,
)

print(delta)
# ProjectionDelta(src='node-a', subtrees=1, changes=1, enc='raw')
print(delta.is_empty())       # False
print(delta.content_hash())   # deterministic SHA-256
```

### Associative composition

```python
# delta_ab . delta_bc = delta_ac
subtree_bc = SubtreeRef(path=(20,), depth=1, old_hash="bbb", new_hash="ccc")
pco_bc = AggregateProofCarryingOperation.build(
    originator_id="node-a",
    signing_fn=lambda h: b"\x00" * 64,
    merkle_root="",
    clock_snapshot=b"",
    trust_vector_hash="",
    delta_bounds=[subtree_bc],
)

delta_bc = ProjectionDelta(
    source_id="node-a",
    source_version=None,
    target_version=None,
    changed_subtrees=(subtree_bc,),
    insertions=FrozenDict({"key2": b"value2"}),
    updates=FrozenDict(),
    deletions=frozenset(),
    pco=pco_bc,
)

composed = delta.compose(delta_bc)
print(composed)
# ProjectionDelta(src='node-a', subtrees=2, changes=2, enc='raw')
```

### Compression

```python
compressed = delta.compress(encoding="sparse")
print(compressed.encoding)          # sparse
print(compressed.compression_ratio) # >= 1.0
```

### Delta manager

```python
mgr = ProjectionDeltaManager(max_history=64)
mgr.record(delta)
mgr.record(delta_bc)

composed = mgr.compose_range("node-a", start=0, end=2)
print(composed)

latest = mgr.latest("node-a")
print(latest.source_id)  # node-a
print(mgr.peers())       # ['node-a']
```

---

## 5. Adaptive Verification

The `AdaptiveVerificationController` routes incoming deltas through
trust-tiered verification levels. Higher trust peers get cheaper checks;
low trust peers get the full aggregate PCO verification.

```python
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationResult,
    VerificationOutcome,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice, TrustCircuitBreaker

# Set up lattice and verifier
lattice = DeltaTrustLattice("local-node")
breaker = TrustCircuitBreaker(
    window_size=100,
    sigma_threshold=2.0,
    cooldown_seconds=30.0,
)
verifier = AdaptiveVerificationController(
    trust_lattice=lattice,
    circuit_breaker=breaker,
    async_queue_limit=1024,
)

# Verify a delta -- level is chosen based on sender trust
result = verifier.verify(delta, state=None, trust_lattice=lattice)
print(result.accepted)       # True or False
print(result.level)          # 0, 1, 2, or 3
print(result.async_pending)  # True if full verify queued for later

# Run async followup -- re-verifies optimistic accepts at Level 2
followups = verifier.run_async_followup(state=None, batch_size=32)
for d, vr in followups:
    print(d.source_id, vr.accepted)
```

### Circuit breaker override

When the breaker trips (anomalous trust velocity), all verification is
forced to Level 2 regardless of sender trust.

```python
print(breaker.is_tripped())  # False
# After many rapid trust changes...
breaker.reset()  # manual reset
```

---

## 6. Disabling E4

Set the `CRDT_MERGE_E4` environment variable to `0` before importing:

```bash
CRDT_MERGE_E4=0 python my_script.py
```

Or disable programmatically:

```python
import os
os.environ["CRDT_MERGE_E4"] = "0"
```

When disabled, all trust operations become no-ops: merges run without
trust scoring, PCO verification, or adaptive gating. Existing data
pipelines continue unchanged.

---

## Quick Reference

| Component | Import | Purpose |
|-----------|--------|---------|
| `TypedTrustScore` | `crdt_merge.e4.typed_trust` | Multi-dimensional trust with GCounter evidence |
| `TrustEvidence` | `crdt_merge.e4.proof_evidence` | Cryptographic evidence of misbehaviour |
| `AggregateProofCarryingOperation` | `crdt_merge.e4.pco` | 128-byte aggregate proof per operation |
| `ProjectionDelta` | `crdt_merge.e4.projection_delta` | Sparse delta encoding via Merkle traversal |
| `ProjectionDeltaManager` | `crdt_merge.e4.projection_delta` | Delta lifecycle, composition, history |
| `AdaptiveVerificationController` | `crdt_merge.e4.adaptive_verification` | Trust-tiered verification routing |
| `DeltaTrustLattice` | `crdt_merge.e4.delta_trust_lattice` | Recursive trust propagation as deltas |
| `TrustCircuitBreaker` | `crdt_merge.e4.delta_trust_lattice` | Trust velocity anomaly detection |
| `TrustHomeostasis` | `crdt_merge.e4.typed_trust` | Conserved-budget trust normalization |

---

*crdt-merge v0.9.5 -- April 2026*
