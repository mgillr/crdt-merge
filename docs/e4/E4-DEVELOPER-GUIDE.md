> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Developer Guide

> **Version:** 0.9.5 &middot; **Module:** `crdt_merge.e4` &middot; **Author:** Ryan Gillespie / mgillr

A practical guide for developers working with the E4 recursive trust-delta architecture. Covers the core concepts, programming patterns, and debugging strategies you'll need to build with E4 effectively.

**Related documents:** [API Reference](E4-API-REFERENCE.md) · [Integration Guide](E4-INTEGRATION-GUIDE.md) · [Security Model](E4-SECURITY-MODEL.md) · [Changelog](E4-CHANGELOG.md)

---

## Table of Contents

1. [What Is E4?](#1-what-is-e4)
2. [Quick Start](#2-quick-start)
3. [Core Concepts](#3-core-concepts)
4. [Working with TypedTrustScores](#4-working-with-typedtrustscores)
5. [Proof-Carrying Evidence](#5-proof-carrying-evidence)
6. [ProjectionDeltas and the Delta Pipeline](#6-projectiondeltas-and-the-delta-pipeline)
7. [The Four Entanglement Points](#7-the-four-entanglement-points)
8. [Trust Propagation in Practice](#8-trust-propagation-in-practice)
9. [Common Patterns](#9-common-patterns)
10. [Anti-Patterns](#10-anti-patterns)
11. [Debugging and Observability](#11-debugging-and-observability)
12. [Testing Strategies](#12-testing-strategies)

---

## 1. What Is E4?

E4 is the fourth entanglement point in the crdt-merge trust architecture. The key insight: **trust IS data**. Trust changes propagate as ProjectionDeltas through the same two-layer pipeline as application data — Merkle layer (integrity) and CRDT layer (convergence).

This creates a recursive dependency: trust validates data integrity via Merkle proofs, and data integrity validates trust evidence via proof verification. The result is a system where you can't silently compromise trust without breaking Merkle consistency, and you can't forge Merkle proofs without having sufficient trust.

**What E4 gives you:**
- Multi-dimensional trust tracking across six dimensions
- Adaptive verification — expensive checks only for untrusted peers
- Sybil resistance via conserved trust budgets
- Proof-carrying evidence — any honest node can verify misbehaviour
- Zero-downtime migration from pre-E4 deployments

**What E4 does NOT do:**
- Replace application-level access control
- Protect against physical key compromise (post-compromise security)
- Guarantee real-time global consistency (it's still eventually consistent)

---

## 2. Quick Start

### Minimal Single-Node Setup

```python
from crdt_merge.e4.typed_trust import TypedTrustScore, TrustHomeostasis
from crdt_merge.e4.proof_evidence import TrustEvidence
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.causal_trust_clock import CausalTrustClock

# 1. Create the three core components
merkle = TrustBoundMerkle(branching_factor=256)
clock = CausalTrustClock("my-peer")
lattice = DeltaTrustLattice(
    "my-peer",
    initial_peers={"peer-alice", "peer-bob"},
)

# 2. Wire the recursive dependencies (late binding)
merkle.bind_trust_lattice(lattice)
clock.bind_trust_lattice(lattice)
lattice.bind_merkle(merkle)
lattice.bind_clock(clock)

# 3. Store data with trust context
leaf_hash = merkle.insert_leaf("key1", b"hello", "peer-alice")
merkle.recompute()

# 4. Check trust
trust = lattice.get_trust("peer-alice")
print(f"Trust: {trust.overall_trust()}")       # 0.5 (probationary)
print(f"Level: {trust.verification_level()}")  # 1
```

### Wiring Order

The three core components have circular dependencies. E4 resolves this with a **lazy init pattern**: create all three, then bind them:

```
TrustBoundMerkle  ←─── references ───→  DeltaTrustLattice
CausalTrustClock  ←─── references ───→  DeltaTrustLattice
```

1. Construct `TrustBoundMerkle` (no lattice yet)
2. Construct `CausalTrustClock` (no lattice yet)
3. Construct `DeltaTrustLattice` (stubs used internally)
4. Call `merkle.bind_trust_lattice(lattice)`
5. Call `clock.bind_trust_lattice(lattice)`
6. Call `lattice.bind_merkle(merkle)` and `lattice.bind_clock(clock)`

Stub implementations (`_StubMerkle`, `_StubClock`) ensure the lattice works even without bindings — useful for unit testing.

---

## 3. Core Concepts

### Trust is a CRDT

`TypedTrustScore` is a CRDT backed by GCounters. Evidence is recorded per-observer per-dimension, and merge takes the element-wise max. This means:

- **Trust only decreases** from its initial probation level as evidence accumulates
- **Merge is commutative, associative, and idempotent** — peer ordering doesn't matter
- **No coordination required** — eventual consistency is guaranteed

### Six Trust Dimensions

Trust is not a single number. E4 tracks six orthogonal dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| `integrity` | Merkle proof validity, hash consistency |
| `causality` | Vector clock correctness, no regressions |
| `consistency` | CRDT invariant preservation |
| `gossip` | Gossip protocol compliance |
| `model` | ML model weight validity |
| `context` | Context-appropriate behaviour |

Each dimension is independently measurable with its own evidence types.

### Adaptive Immune System (Four Verification Tiers)

The biological metaphor is intentional. Like an immune system, E4 spends more energy verifying unknown entities:

| Level | Trust Range | Verification | Cost | Analogy |
|-------|------------|-------------|------|---------|
| 0 | > 0.8 | Signature only | O(1) | Trusted self-cell |
| 1 | 0.4–0.8 | Signature + Merkle root | O(1) | Recognised antigen |
| 2 | 0.1–0.4 | Full PCO derivation | O(k) | Active immune response |
| 3 | < 0.1 | Reject unconditionally | O(1) | Quarantine |

This is where the recursive dependency is most visible: **trust determines how deeply we verify, and verification results update trust.**

### Aggregate Proof-Carrying Operations (PCO)

Every CRDT operation carries a 128-byte aggregate proof covering four properties:

1. **Integrity**: Merkle root matches local computation
2. **Causality**: Clock snapshot consistent with known state
3. **Trust**: Originator meets minimum trust threshold
4. **Minimality**: Delta bounds match claimed subtrees

One hash, one signature, four guarantees. The aggregate design means the per-operation overhead is constant (128 bytes) regardless of operation complexity.

---

## 4. Working with TypedTrustScores

### Creating and Inspecting

```python
from crdt_merge.e4.typed_trust import TypedTrustScore, TRUST_DIMENSIONS

# New peer — probationary
score = TypedTrustScore.probationary()
print(score.overall_trust())       # 0.5
print(score.verification_level())  # 1

# Check specific dimension
print(score.trust_for_dimension("integrity"))  # 0.5

# Full-trust peer
trusted = TypedTrustScore.full_trust()
print(trusted.overall_trust())       # 1.0
print(trusted.verification_level())  # 0
```

### Recording Evidence (Trust Decreases)

Trust decreases when evidence of misbehaviour is recorded. Evidence must be proof-carrying:

```python
# Create evidence (see section 5)
evidence = TrustEvidence.create(
    observer="peer-alice",
    target="peer-eve",
    evidence_type="equivocation",
    dimension="integrity",
    amount=0.1,  # severity
    proof=proof_bytes,
)

# Record it — returns a NEW TypedTrustScore (immutable)
new_score = score.record_evidence(
    observer="peer-alice",
    dimension="integrity",
    amount=0.1,
    proof=evidence,
)

print(new_score.trust_for_dimension("integrity"))  # < 0.5
```

### CRDT Merge

```python
# Alice and Bob independently observe misbehaviour
alice_view = score.record_evidence(observer="alice", dimension="integrity", amount=0.1, proof=ev_a)
bob_view = score.record_evidence(observer="bob", dimension="causality", amount=0.05, proof=ev_b)

# Merge: takes max evidence per observer per dimension
merged = alice_view.merge(bob_view)
# merged has BOTH alice's integrity observation and bob's causality observation
```

### Homeostasis (Budget Conservation)

```python
from crdt_merge.e4.typed_trust import TrustHomeostasis

# After any trust change cycle, normalize:
scores = {"peer-a": score_a, "peer-b": score_b, "peer-c": score_c}
normalized = TrustHomeostasis.normalize(scores, len(scores))
# Total trust per dimension is rescaled to sum == peer_count
# This prevents inflation/deflation attacks
```

### Serialization and Hashing

```python
# For Merkle binding
raw = score.serialize()       # deterministic bytes
h = score.hash()              # SHA-256 hex digest

# Scores with same evidence produce same hash
assert score1.hash() == score2.hash()  # if evidence identical
```

---

## 5. Proof-Carrying Evidence

Every piece of trust evidence must carry a cryptographic proof that **any honest node** can verify independently, without trusting the observer. This is what makes E4's trust system Byzantine-fault-tolerant.

### Five Evidence Types

| Type | Proof Format | What It Proves |
|------|-------------|---------------|
| `equivocation` | `attestation_pair` | Peer signed two conflicting operations |
| `merkle_divergence` | `merkle_path` | Peer's Merkle path doesn't match claimed root |
| `clock_regression` | `vector_clock_pair` | Peer's clock went backward |
| `invalid_delta` | `delta_verification` | Delta fails structural/integrity check |
| `trust_manipulation` | `trust_state_pair` | Peer sent inconsistent trust state |

### Creating Evidence

```python
from crdt_merge.e4.proof_evidence import (
    TrustEvidence,
    pack_attestation_pair,
    pack_merkle_path,
    pack_clock_pair,
    pack_delta_proof,
    pack_state_pair,
)

# Equivocation: peer signed two conflicting ops
proof = pack_attestation_pair(signed_op_a, signed_op_b)
evidence = TrustEvidence.create(
    observer="peer-alice",
    target="peer-eve",
    evidence_type="equivocation",
    dimension="integrity",
    amount=0.1,
    proof=proof,
)

# Verify proof (any node can do this)
assert evidence.verify()

# With Merkle binding
assert evidence.verify(merkle_root="abc123...")
```

### Proof Packing Rules

Each evidence type has a specific proof format:

```python
# Equivocation: two signed attestations
proof = pack_attestation_pair(op_bytes_a, op_bytes_b)

# Merkle divergence: Merkle path segments
proof = pack_merkle_path([(sibling_hashes, position), ...])

# Clock regression: before/after clock snapshots
proof = pack_clock_pair(clock_before_bytes, clock_after_bytes)

# Invalid delta: expected hash + delta bytes
proof = pack_delta_proof(expected_hash_32b, delta_bytes)

# Trust manipulation: two trust state snapshots
proof = pack_state_pair(state_a_bytes, state_b_bytes)
```

### Proof Verification Internals

Proofs have minimum size requirements (33 bytes for most types). The `verify()` method dispatches to type-specific verifiers that check:
1. Proof format is valid for the claimed evidence type
2. Proof content is internally consistent
3. Proof is bound to the current Merkle root (when provided)

---

## 6. ProjectionDeltas and the Delta Pipeline

### What Is a ProjectionDelta?

A ProjectionDelta is a sparse diff between two states, identified through O(log_B n) high-arity Merkle tree traversal. It carries:
- **Changed subtrees** — which parts of the Merkle tree differ
- **Insertions** — new key-value pairs
- **Updates** — changed values (with old hash for verification)
- **Deletions** — removed keys
- **PCO** — the 128-byte aggregate proof

### Creating Deltas

In normal operation, deltas are created by the system (e.g., by `DeltaTrustLattice.observe_and_propagate()`). For testing or custom workflows:

```python
from crdt_merge.e4.projection_delta import ProjectionDelta, FrozenDict
from crdt_merge.e4.pco import SubtreeRef

delta = ProjectionDelta(
    source_id="peer-alice",
    source_version=clock_before,
    target_version=clock_after,
    changed_subtrees=(
        SubtreeRef(path=(42,), depth=1, old_hash="aaa", new_hash="bbb"),
    ),
    insertions=FrozenDict({"new_key": b"new_value"}),
    updates=FrozenDict({"existing_key": ("old_hash", b"updated_value")}),
    deletions=frozenset(["removed_key"]),
    pco=aggregate_pco,
)
```

### Composing Deltas

Deltas are associative — they can be chained:

```python
# delta_ab: state A → state B
# delta_bc: state B → state C
delta_ac = delta_ab.compose(delta_bc)  # state A → state C directly
```

### Compression

```python
# Sparse encoding (removes zero entries)
sparse = delta.compress("sparse")
print(sparse.compression_ratio)  # e.g., 0.3

# Quantized encoding (lossy, for model weights)
quantized = delta.compress("quantized", bits=8)
```

### Managing Delta History

```python
from crdt_merge.e4.projection_delta import ProjectionDeltaManager

manager = ProjectionDeltaManager(max_history=64)
manager.record(delta_1)
manager.record(delta_2)

# Compose a range
combined = manager.compose_range("peer-alice", start=0, end=2)
latest = manager.latest("peer-alice")
```

---

## 7. The Four Entanglement Points

E4's security comes from four recursive dependencies that make isolated attacks impossible.

### E1: Merkle ↔ Trust

The Merkle tree incorporates trust context into hashes:

```
H(data ‖ trust_score ‖ originator)  instead of  H(data)
```

Consequence: changing trust invalidates Merkle hashes. Modifying the tree requires current trust context. This is implemented by `TrustBoundMerkle`.

```python
merkle = TrustBoundMerkle(trust_lattice=lattice, branching_factor=256)
leaf_hash = merkle.compute_leaf_hash(data, "peer-alice")
# This hash depends on peer-alice's current trust score
```

### E2: Clock ↔ Trust

Vector clock entries carry trust scores: `(logical_time, trust_score)` pairs. Low-trust peers cannot causally dominate high-trust peers:

```python
clock = CausalTrustClock("my-peer", trust_lattice=lattice)
clock = clock.increment()  # Embeds current trust score

result = clock.trust_weighted_compare(remote_clock)
# "trust_override" if we have higher trust despite lower time
```

### E3: Proofs ↔ Trust

Every trust evidence carries a cryptographic proof verifiable without trusting the observer. Proof verification itself requires the Merkle root (E1 binding), creating a loop:

```
trust evidence → needs Merkle proof → needs trust context → back to trust
```

### E4: Trust ↔ Delta Pipeline

Trust changes propagate as ProjectionDeltas through the same pipeline as data. This is the recursive closure:

```python
# Observe misbehaviour → create trust delta → send through pipeline
delta = lattice.observe_and_propagate(evidence)
# This delta flows through Merkle verification, CRDT merge, etc.
# — the same pipeline as data deltas
```

---

## 8. Trust Propagation in Practice

### The Full Lifecycle

1. **Observation**: Peer Alice detects misbehaviour by Peer Eve
2. **Evidence creation**: Alice builds proof-carrying evidence
3. **Local trust update**: Alice's `DeltaTrustLattice` updates Eve's trust locally
4. **Homeostasis**: Trust budget is rebalanced
5. **Delta creation**: Trust change encoded as a `ProjectionDelta` with PCO
6. **Propagation**: Delta sent to other peers via gossip/streaming
7. **Remote verification**: Other peers verify the PCO at adaptive depth
8. **Remote trust update**: If verified, remote peers update Eve's trust
9. **Merkle rehash**: Trust-bound Merkle trees are invalidated and recomputed

### observe_and_propagate() Walkthrough

```python
# Inside DeltaTrustLattice.observe_and_propagate():
def observe_and_propagate(self, evidence: TrustEvidence) -> ProjectionDelta:
    # 1. Circuit breaker check (prevent flooding)
    if self._circuit_breaker.is_tripped():
        raise CircuitBreakerTripped(...)

    # 2. Verify evidence proof (trust-independent)
    if not evidence.verify(self._merkle.root_hash):
        raise ValueError("evidence proof failed")

    # 3. Update local trust (GCounter increment)
    old_trust = self.get_trust(target)
    new_trust = old_trust.record_evidence(...)

    # 4. Homeostasis normalization
    self._trust_scores = self._homeostasis.normalize(...)

    # 5. Circuit breaker tracking
    self._circuit_breaker.record_trust_change(...)

    # 6. Encode as ProjectionDelta
    trust_delta = self._delta_encoder.encode_trust_change(...)

    # 7. Build and attach PCO
    pco = AggregateProofCarryingOperation.build(...)
    return trust_delta.with_pco(pco)
```

### receive_trust_delta() Walkthrough

```python
# Inside DeltaTrustLattice.receive_trust_delta():
def receive_trust_delta(self, delta, state=None) -> bool:
    # 1. Determine sender's verification level
    sender_trust = self.get_trust(delta.source_id)
    level = sender_trust.verification_level()

    # 2. Verify PCO at adaptive depth
    if not delta.pco.verify(state, self, verification_level=level):
        self._record_counter_evidence(delta.source_id, "invalid_delta")
        return False

    # 3. Queue async full verification for optimistic levels
    if level < 2:
        self._async_queue.append(delta)

    # 4. Decode and verify embedded evidence
    evidence = self._delta_encoder.decode_trust_evidence(delta)
    if not evidence.verify(self._merkle.root_hash):
        self._record_counter_evidence(delta.source_id, "trust_manipulation")
        return False

    # 5. Apply trust update via CRDT merge
    old_trust = self.get_trust(target)
    new_trust = old_trust.merge(updated)

    # 6. Homeostasis + circuit breaker
    # 7. Update Merkle tree (trust-bound hashes now stale)
    self._merkle.update_trust_context(target, new_trust)
    return True
```

---

## 9. Common Patterns

### Pattern: Wiring the E4 Stack

The most common pattern — creating a fully wired E4 stack:

```python
def create_e4_stack(peer_id, initial_peers=None):
    """Create a fully wired E4 stack."""
    merkle = TrustBoundMerkle(branching_factor=256)
    clock = CausalTrustClock(peer_id)
    lattice = DeltaTrustLattice(
        peer_id,
        initial_peers=initial_peers or set(),
    )

    # Wire dependencies
    merkle.bind_trust_lattice(lattice)
    clock.bind_trust_lattice(lattice)
    lattice.bind_merkle(merkle)
    lattice.bind_clock(clock)

    return merkle, clock, lattice
```

### Pattern: Trust-Gated Operations

Only allow operations from peers above a trust threshold:

```python
def accept_operation(lattice, peer_id, operation):
    trust = lattice.get_trust(peer_id)
    level = trust.verification_level()

    if level == 3:  # Quarantined
        return False, "peer quarantined"

    if level == 2:  # Low trust — full verification
        if not operation.pco.verify(state, lattice, verification_level=2):
            return False, "PCO verification failed"

    # Level 0–1: optimistic acceptance
    return True, "accepted"
```

### Pattern: Trust Recovery Monitoring

Watch for peers climbing out of low trust:

```python
def monitor_trust_recovery(lattice, peer_id):
    trust = lattice.get_trust(peer_id)
    level = trust.verification_level()

    if level == 2:
        print(f"⚠️  {peer_id} at low trust: {trust.overall_trust():.3f}")
    elif level == 3:
        print(f"🚫 {peer_id} quarantined: {trust.overall_trust():.3f}")
    else:
        print(f"✅ {peer_id} healthy: {trust.overall_trust():.3f}")

    return {
        "peer_id": peer_id,
        "overall": trust.overall_trust(),
        "level": level,
        "dimensions": {
            d: trust.trust_for_dimension(d)
            for d in TRUST_DIMENSIONS
        },
    }
```

### Pattern: Batch Delta Processing with History

```python
manager = ProjectionDeltaManager(max_history=64)

# Process a batch of incoming deltas
for delta in incoming_deltas:
    if lattice.receive_trust_delta(delta):
        manager.record(delta)

# Later: compose the full range for a peer
combined = manager.compose_range("peer-alice")
```

---

## 10. Anti-Patterns

### ❌ Bypassing Evidence Proofs

```python
# WRONG: fabricating evidence without proof
bad_evidence = TrustEvidence.create(
    observer="me", target="peer-eve",
    evidence_type="equivocation",
    dimension="integrity",
    amount=0.5,
    proof=b"\x00" * 33,  # Fake proof!
)
# This will fail verify() on all honest nodes
```

**Why:** The whole point of E4 is that trust evidence must be independently verifiable. Fake proofs get caught and generate counter-evidence against the fabricator.

### ❌ Forgetting to Recompute Merkle After Trust Changes

```python
# WRONG: trust changed but Merkle tree not recomputed
lattice.receive_trust_delta(delta)
# ... using merkle.root_hash here gives STALE hash
```

**Fix:** After trust changes propagated through `receive_trust_delta()`, the Merkle tree's trust context is updated automatically via `update_trust_context()`. However, if you need the new root hash, call `merkle.recompute()`:

```python
lattice.receive_trust_delta(delta)
merkle.recompute()  # Rebuild with updated trust context
print(merkle.root_hash)  # Now reflects new trust state
```

### ❌ Creating Multiple Lattices for Same Peer

```python
# WRONG: two lattice instances for same peer_id
lattice_a = DeltaTrustLattice("peer-alice")
lattice_b = DeltaTrustLattice("peer-alice")  # Different state!
```

**Fix:** One `DeltaTrustLattice` per peer identity. Share the instance across components.

### ❌ Ignoring the Circuit Breaker

```python
# WRONG: catching and suppressing CircuitBreakerTripped
try:
    delta = lattice.observe_and_propagate(evidence)
except CircuitBreakerTripped:
    pass  # Silently ignoring!
```

**Fix:** The circuit breaker is there for a reason — it detects anomalous trust velocity. Log it, alert, and back off:

```python
try:
    delta = lattice.observe_and_propagate(evidence)
except CircuitBreakerTripped:
    logger.warning("Circuit breaker active — trust velocity too high")
    # Queue the evidence for later processing
    deferred_queue.append(evidence)
```

### ❌ Hardcoding Verification Levels

```python
# WRONG: always using Level 0 (trusting everyone)
pco.verify(state, lattice, verification_level=0)
```

**Fix:** Let the adaptive immune system decide. Use `trust.verification_level()` or the `AdaptiveVerificationController`.

---

## 11. Debugging and Observability

### Inspecting Trust State

```python
# Current trust for all peers
for peer in lattice.known_peers():
    trust = lattice.get_trust(peer)
    print(f"{peer}: overall={trust.overall_trust():.3f} level={trust.verification_level()}")
    for dim in TRUST_DIMENSIONS:
        print(f"  {dim}: {trust.trust_for_dimension(dim):.3f}")
```

### Repr Strings

All core classes have informative `__repr__`:

```python
print(lattice)  # DeltaTrustLattice(peer='my-peer', peers=3, breaker=ok)
print(merkle)   # TrustBoundMerkle(B=256, leaves=42, compat=False)
print(clock)    # CausalTrustClock(peer='my-peer', time=7, peers=3)
```

### Evidence Log

```python
# Full evidence history
for ev in lattice.evidence_log:
    print(f"[{ev.timestamp}] {ev.observer} → {ev.target}: "
          f"{ev.evidence_type} ({ev.dimension}, {ev.amount})")
```

### Async Verification Queue

```python
# How many items pending full verification?
print(f"Pending async: {lattice.pending_async_verifications}")

# Drain and re-verify
for delta in lattice.drain_async_queue():
    result = delta.pco.verify(state, lattice, verification_level=2)
    if not result:
        logger.error(f"Async verification failed for {delta.source_id}")
```

### Circuit Breaker State

```python
# Check if breaker is active
if lattice._circuit_breaker.is_tripped():
    print("⚡ Circuit breaker is TRIPPED — defensive mode active")
    print("All incoming deltas get Level 2 verification")
```

### Merkle Tree Diagnostics

```python
print(f"Leaves: {merkle.leaf_count}")
print(f"Root hash: {merkle.root_hash}")
print(f"Compat mode: {merkle.compatibility_mode}")
print(f"Branching factor: {merkle.branching_factor}")

# After operations, check root hasn't diverged
assert merkle.is_plausible_root(expected_root)
```

### Clock Diagnostics

```python
print(f"Local time: {clock.logical_time}")
print(f"Known peers: {clock.known_peers()}")
for peer in clock.known_peers():
    time, trust = clock.get_entry(peer)
    print(f"  {peer}: time={time}, trust={trust:.3f}")
```

---

## 12. Testing Strategies

### Unit Testing with Stubs

The `DeltaTrustLattice` uses stubs when no Merkle/Clock is injected, making unit testing simple:

```python
def test_trust_observation():
    lattice = DeltaTrustLattice("test-peer", initial_peers={"target"})

    evidence = TrustEvidence.create(
        observer="test-peer",
        target="target",
        evidence_type="invalid_delta",
        dimension="integrity",
        amount=0.05,
        proof=pack_delta_proof(b"\x00" * 32, b"\x01" * 33),
    )

    delta = lattice.observe_and_propagate(evidence)
    assert not delta.is_empty()
    assert lattice.get_trust("target").overall_trust() < 0.5
```

### Integration Testing with Full Stack

```python
def test_full_e4_stack():
    merkle, clock, lattice = create_e4_stack(
        "test-peer",
        initial_peers={"peer-a", "peer-b"},
    )

    # Insert data
    merkle.insert_leaf("k1", b"v1", "peer-a")
    merkle.recompute()

    # Verify trust-bound hash depends on trust
    hash_before = merkle.root_hash

    # Record evidence → trust changes → hashes change
    evidence = TrustEvidence.create(...)
    lattice.observe_and_propagate(evidence)
    merkle.recompute()

    hash_after = merkle.root_hash
    assert hash_before != hash_after  # Trust change invalidated hashes
```

### Testing Convergence

```python
def test_lattice_merge_convergence():
    """Two lattices merge to same state regardless of order."""
    lattice_a = DeltaTrustLattice("peer-a", initial_peers={"target"})
    lattice_b = DeltaTrustLattice("peer-b", initial_peers={"target"})

    # Independent observations
    lattice_a.observe_and_propagate(evidence_a)
    lattice_b.observe_and_propagate(evidence_b)

    # Merge in both orders
    merged_ab = lattice_a.merge(lattice_b)
    merged_ba = lattice_b.merge(lattice_a)

    # Must converge
    assert (
        merged_ab.get_trust("target").overall_trust()
        == merged_ba.get_trust("target").overall_trust()
    )
```

---

*For full API signatures, see [E4-API-REFERENCE.md](E4-API-REFERENCE.md). For deployment and migration, see [E4-INTEGRATION-GUIDE.md](E4-INTEGRATION-GUIDE.md).*


---

## Resilience Subsystem

The resilience subsystem (v0.9.5.1) provides 9 optional security and
performance modules.  All are enabled via class-method hooks on
existing E4 classes.

### Quick Start

```python
from crdt_merge.e4.resilience import (
    DomainSeparatedHasher,
    KeyManager,
    EpochManager,
    ConvergenceMonitor,
    TrustPrivacyFilter,
    CompositeSemanticValidator,
    ReanchorPolicy,
    SketchConfig,
    FanoutOptimizer,
)

# Enable domain-separated hashing on Merkle operations
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
TrustBoundMerkle.enable_domain_hashing()

# Enable convergence monitoring
from crdt_merge.e4.integration.gossip_bridge import TrustGossipPayload
TrustGossipPayload.enable_convergence_monitoring(peer_count=10000)

# Enable semantic validation on incoming deltas
from crdt_merge.e4.projection_delta import ProjectionDelta
ProjectionDelta.enable_semantic_validation(max_magnitude=100.0)

# Enable differential privacy on trust queries
from crdt_merge.e4.typed_trust import TypedTrustScore
TypedTrustScore.enable_privacy_filtering(epsilon=1.0)
```

### Key Lifecycle

```python
km = KeyManager("my-peer-id")
signature = km.sign(b"message")

# Rotate keys (old key automatically revoked)
new_key, revocation = km.rotate_key()

# Emergency revocation
km.emergency_revoke("potential compromise")
```

### Epoch Management

```python
em = EpochManager("my-peer-id", max_evidence_per_epoch=1000)
em.record_evidence()

if em.should_advance():
    transition = em.force_advance()
    pruned = em.gc_evidence()
```

### Delta Composition

```python
from crdt_merge.e4.resilience.delta_resilience import (
    DeltaCompositionSpec, ReanchorPolicy, ParameterTypeEncoder,
)

# Formal delta composition
spec = DeltaCompositionSpec()
result = spec.compose(ab_ins, ab_upd, ab_del, bc_ins, bc_upd, bc_del)

# Re-anchoring after quantized compositions
policy = ReanchorPolicy(max_chain_length=50, max_error_bound=0.01)
if policy.record_composition():
    checkpoint = policy.checkpoint(version=42, state_hash="abc123")

# Type-aware encoding
encoder = ParameterTypeEncoder()
rec = encoder.recommend("model.layers.0.q_proj.weight")
# → EncodingRecommendation(encoding='sparse', threshold=1e-6)
```

### Performance Planning

```python
from crdt_merge.e4.resilience.performance_spec import (
    SketchConfig, FanoutOptimizer, HardwareRequirements,
)

# CountMinSketch sizing
sketch = SketchConfig.for_scale(100000)
# → width=544, depth=10, memory=21,760B

# Gossip fan-out
opt = FanoutOptimizer()
cfg = opt.optimize(10000)
# → fan_out=10, rounds_to_all=4

# Hardware requirements
hw = HardwareRequirements.for_scale(10000)
# → 2 cores, 2GB RAM, 10Mbps
```

---

## Round 2 Resilience Modules

Round 2 adds 10 additional resilience modules addressing threats and operational
requirements that emerged from adversarial analysis at scale. All are
non-breaking and composable with the existing pipeline.

### Post-Quantum Signatures

Drop-in replacement for HMAC-SHA256 with quantum-resistant alternatives:

```python
from crdt_merge.e4.resilience.pq_signatures import (
    HmacScheme, DilithiumLite, HybridScheme,
    get_scheme, register_scheme,
)

# Use hybrid mode during migration (both classical + PQ must verify)
hybrid = HybridScheme(HmacScheme(), DilithiumLite())
priv, pub = hybrid.generate_keypair()
sig = hybrid.sign(priv, b"message")
assert hybrid.verify(pub, b"message", sig)

# Register for epoch-scoped rotation
register_scheme(hybrid)
```

### Long-Con Sybil Detection

Detects patient adversaries that build trust slowly below the circuit breaker
threshold. Three independent statistical signals (any two trigger an alert):

```python
from crdt_merge.e4.resilience.longcon_sybil import (
    LongConDetector, LongConConfig, EvidenceRecord,
)

detector = LongConDetector(LongConConfig(
    correlation_threshold=0.7,
    timing_ks_threshold=0.3,
    density_threshold=2.0,
))

# Feed evidence observations over time
detector.record_evidence(EvidenceRecord(
    peer_id="peer-x", timestamp=now, dimension="integrity", amount=0.01,
))

# Periodically check for Sybil clusters
alerts = detector.check()
for alert in alerts:
    print(f"Sybil group: {alert.suspect_group}, confidence: {alert.confidence}")
```

### Formal Verification

Generate TLA+ specs and run bounded model checking on E4 convergence properties:

```python
from crdt_merge.e4.resilience.formal_spec import (
    E4FormalSpec, SpecBounds,
)

spec = E4FormalSpec()
bounds = SpecBounds(max_peers=3, max_ops=5, trust_dimensions=5)

# Check all four temporal properties
results = spec.check_all(bounds)
for prop, passed in results.items():
    print(f"{prop}: {'PASS' if passed else 'FAIL'}")
```

### Non-IID Convergence Analysis

Analyse trust-model convergence interaction under heterogeneous data:

```python
from crdt_merge.e4.resilience.noniid_convergence import (
    TrustConvergenceAnalyser, HeterogeneityProfile,
)

profile = HeterogeneityProfile(
    peer_count=100, label_skew=0.3, volume_skew=5.0, feature_shift=0.1,
)

analyser = TrustConvergenceAnalyser()
bound = analyser.bound(profile)
warmup = analyser.recommend_warmup(profile)
print(f"Rounds to converge: {bound.rounds_to_converge}")
print(f"Early-round evidence threshold: {warmup.evidence_threshold_at(0)}")
```

### Trust Inheritance

Reduce cold-start latency through institutional vouching:

```python
from crdt_merge.e4.resilience.trust_inheritance import (
    TrustInheritanceManager, VouchRecord,
)

mgr = TrustInheritanceManager()
mgr.register_institution("hospital-a", trust=0.85)
mgr.issue_vouch("hospital-a", device_ids={"device-1", "device-2"}, ceiling=0.7)

# device-1 starts at inherited trust instead of probation
effective = mgr.effective_trust("device-1")
```

### Gossip Budget Management

Control trust gossip bandwidth at large peer counts:

```python
from crdt_merge.e4.resilience.gossip_budget import (
    HierarchicalAggregator, AdaptiveGossipRate,
)

agg = HierarchicalAggregator()
agg.add_region("us-east", peer_ids={"p1", "p2", "p3"})
agg.add_region("eu-west", peer_ids={"p4", "p5"})

# Cross-region payload: summaries only, not individual scores
payload = agg.cross_region_payload()
estimate = agg.estimate_bandwidth(peer_count=10000)
print(f"Recommended: {estimate.recommended_strategy}")

# Adaptive rate: slow gossip when stable, fast during churn
rate = AdaptiveGossipRate()
rate.record_convergence(variance=0.001)  # stable → longer interval
```

### Deterministic Merge

Reproducible trust-weighted averaging regardless of accumulation order:

```python
from crdt_merge.e4.resilience.deterministic_merge import (
    DeterministicMerge, deterministic_sum,
)

# Sorted Kahan: bitwise-reproducible for any permutation
result = deterministic_sum([0.1, 0.2, 0.3, 1e-15, 0.4])

merger = DeterministicMerge()
avg = merger.weighted_average(
    values=[0.5, 0.8, 0.3],
    weights=[0.9, 0.7, 0.4],  # trust scores as weights
)
```

### Strategy Drift Discrimination

Prevent false trust demotion of agents undergoing legitimate strategy shifts:

```python
from crdt_merge.e4.resilience.strategy_drift import (
    StrategyDriftDiscriminator,
)

disc = StrategyDriftDiscriminator()

# Feed contribution history
for contrib in agent_contributions:
    disc.record_contribution(contrib.peer_id, contrib.magnitude, contrib.region)

# Evaluate whether a drift is legitimate or adversarial
verdict = disc.evaluate("agent-7")
if verdict.is_legitimate:
    # Suppress trust penalty for this agent
    pass
```

### Post-Partition Reconciliation

Graduated trust recovery after network partition healing:

```python
from crdt_merge.e4.resilience.partition_reconciler import (
    PartitionReconciler, PartitionEvent,
)

reconciler = PartitionReconciler()

# On partition heal detection
event = PartitionEvent(
    timestamp=time.time(),
    local_peers=frozenset({"p1", "p2"}),
    remote_peers=frozenset({"p3", "p4"}),
    pre_merge_budget=4.0,
    post_merge_budget=8.0,
)
reconciler.on_partition_heal(event)

# During grace period, use adjusted budget
while reconciler.is_reconciling():
    budget = reconciler.current_budget()
    reconciler.advance_round()
```

### Schema Heterogeneity

Merge deltas across different model architectures and data schemas:

```python
from crdt_merge.e4.resilience.schema_adapter import (
    SchemaDescriptor, SchemaAligner, SchemaRegistry,
)

registry = SchemaRegistry()
schema_a = SchemaDescriptor(version="v1", fields=[...], name="resnet50")
schema_b = SchemaDescriptor(version="v2", fields=[...], name="vit-base")

registry.register(schema_a)
registry.register(schema_b)

aligner = SchemaAligner()
unified = aligner.unified_schema([schema_a, schema_b])
```
