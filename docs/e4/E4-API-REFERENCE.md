> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 API Reference

> **Version:** 0.9.5 &middot; **Module:** `crdt_merge.e4` &middot; **Author:** Ryan Gillespie / mgillr

Comprehensive reference for every public class, method, constant, and helper in the E4 recursive trust-delta architecture. Organized by source module.

**Related documents:** [Developer Guide](E4-DEVELOPER-GUIDE.md) · [Integration Guide](E4-INTEGRATION-GUIDE.md) · [Security Model](E4-SECURITY-MODEL.md) · [Changelog](E4-CHANGELOG.md)

---

## Table of Contents

1. [`crdt_merge.e4` — Package Init](#1-crdt_mergee4--package-init)
2. [`crdt_merge.e4.typed_trust` — Multi-Dimensional Trust Scores](#2-crdt_mergee4typed_trust--multi-dimensional-trust-scores)
3. [`crdt_merge.e4.proof_evidence` — Proof-Carrying Trust Evidence](#3-crdt_mergee4proof_evidence--proof-carrying-trust-evidence)
4. [`crdt_merge.e4.pco` — Aggregate Proof-Carrying Operations](#4-crdt_mergee4pco--aggregate-proof-carrying-operations)
5. [`crdt_merge.e4.projection_delta` — Sparse Delta Encoding](#5-crdt_mergee4projection_delta--sparse-delta-encoding)
6. [`crdt_merge.e4.delta_trust_lattice` — The Recursive Binding](#6-crdt_mergee4delta_trust_lattice--the-recursive-binding)
7. [`crdt_merge.e4.trust_bound_merkle` — Trust-Bound High-Arity Merkle Tree](#7-crdt_mergee4trust_bound_merkle--trust-bound-high-arity-merkle-tree)
8. [`crdt_merge.e4.causal_trust_clock` — Causal Trust Clock](#8-crdt_mergee4causal_trust_clock--causal-trust-clock)
9. [`crdt_merge.e4.adaptive_verification` — Adaptive Immune Verification](#9-crdt_mergee4adaptive_verification--adaptive-immune-verification)
10. [`crdt_merge.e4.compatibility` — Dual-Hash Compatibility Mode](#10-crdt_mergee4compatibility--dual-hash-compatibility-mode)
11. [`crdt_merge.e4.integration.config` — Runtime Configuration](#11-crdt_mergee4integrationconfig--runtime-configuration)
12. [`crdt_merge.e4.integration.gossip_bridge` — Trust-Enhanced Gossip](#12-crdt_mergee4integrationgossip_bridge--trust-enhanced-gossip)
13. [`crdt_merge.e4.integration.stream_bridge` — Trust-Validated Streaming](#13-crdt_mergee4integrationstream_bridge--trust-validated-streaming)
14. [`crdt_merge.e4.integration.agent_bridge` — Trust-Aware Agent State](#14-crdt_mergee4integrationagent_bridge--trust-aware-agent-state)

---

## 1. `crdt_merge.e4` — Package Init

The top-level `__init__.py` re-exports the core public API and defines `__all__`.

### Public Exports

```python
from crdt_merge.e4 import (
    # Trust
    TypedTrustScore,
    TrustHomeostasis,
    TRUST_DIMENSIONS,
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    # Evidence
    TrustEvidence,
    EVIDENCE_TYPES,
    pack_attestation_pair,
    pack_clock_pair,
    pack_delta_proof,
    pack_merkle_path,
    pack_state_pair,
    # PCO
    AggregateProofCarryingOperation,
    SubtreeRef,
    # Delta
    ProjectionDelta,
    ProjectionDeltaManager,
    FrozenDict,
)
```

---

## 2. `crdt_merge.e4.typed_trust` — Multi-Dimensional Trust Scores

Implements the typed trust lattice (ref 820) with GCounter-based evidence tracking and homeostatic normalization.

### Constants

| Constant | Type | Value | Description |
|----------|------|-------|-------------|
| `TRUST_DIMENSIONS` | `FrozenSet[str]` | `{"integrity", "causality", "consistency", "gossip", "model", "context"}` | Six trust dimensions |
| `PROBATION_TRUST` | `float` | `0.5` | Default trust for new/unknown peers |
| `QUARANTINE_THRESHOLD` | `float` | `0.1` | Below this → rejected (Level 3) |
| `LOW_TRUST_THRESHOLD` | `float` | `0.4` | Below this → full PCO verification (Level 2) |
| `PARTIAL_THRESHOLD` | `float` | `0.8` | Above this → signature only (Level 0) |

### `class TypedTrustScore`

```python
@dataclass
class TypedTrustScore:
    _evidence: Dict[str, Dict[str, float]]  # dimension → {observer → amount}
```

Multi-dimensional trust score backed by GCounter evidence per observer. This is a CRDT: merge is element-wise max per dimension per observer.

#### Class Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `TypedTrustScore.probationary()` | `TypedTrustScore` | Score at probation level (empty evidence) |
| `TypedTrustScore.full_trust()` | `TypedTrustScore` | Score with zero violations (empty evidence) |

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `trust_for_dimension(dimension)` | `dimension: str` | `float` | Trust in a specific dimension [0.0, 1.0]. Defaults to `PROBATION_TRUST` if no evidence. |
| `overall_trust()` | — | `float` | Weighted mean across all six dimensions |
| `verification_level()` | — | `int` | Adaptive immune level: 0 (>0.8), 1 (0.4–0.8), 2 (<0.4), 3 (<0.1) |
| `record_evidence(observer, dimension, amount, proof)` | `observer: str, dimension: str, amount: float, proof: object` | `TypedTrustScore` | Record verified negative evidence. Returns a **new** instance. Raises `ValueError` if `proof.verify()` fails. |
| `merge(other)` | `other: TypedTrustScore` | `TypedTrustScore` | CRDT merge — element-wise max per dimension per observer |
| `serialize()` | — | `bytes` | Compact deterministic serialization for Merkle binding |
| `hash()` | — | `str` | SHA-256 hex digest of serialized trust vector |

**Example:**

```python
from crdt_merge.e4 import TypedTrustScore, TRUST_DIMENSIONS

# New peer starts at probation
score = TypedTrustScore.probationary()
print(score.overall_trust())       # 0.5
print(score.verification_level())  # 1

# After recording evidence
new_score = score.record_evidence(
    observer="peer-alice",
    dimension="integrity",
    amount=0.3,
    proof=some_verified_evidence,
)
print(new_score.trust_for_dimension("integrity"))  # 0.2
```

---

### `class TrustHomeostasis`

Conserved-budget normalization across all peers. After every observation cycle, total trust per dimension is rescaled so `sum(trust_d) == peer_count`.

#### Static Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `normalize(scores, peer_count)` | `scores: Dict[str, TypedTrustScore], peer_count: int` | `Dict[str, TypedTrustScore]` | Return rescaled trust scores preserving rank order |

**Example:**

```python
from crdt_merge.e4 import TrustHomeostasis

normalized = TrustHomeostasis.normalize(trust_scores_dict, len(trust_scores_dict))
```

---

## 3. `crdt_merge.e4.proof_evidence` — Proof-Carrying Trust Evidence

Every piece of trust evidence carries a cryptographic proof verifiable by any honest node without trusting the observer.

### Constants

```python
EVIDENCE_TYPES = {
    "equivocation":       "attestation_pair",
    "merkle_divergence":  "merkle_path",
    "clock_regression":   "vector_clock_pair",
    "invalid_delta":      "delta_verification",
    "trust_manipulation": "trust_state_pair",
}
```

### `class TrustEvidence`

```python
@dataclass(frozen=True)
class TrustEvidence:
    observer: str           # Peer that observed misbehaviour
    target: str             # Peer accused of misbehaviour
    evidence_type: str      # One of five canonical types
    dimension: str          # Trust dimension affected
    amount: float           # Severity (positive, added to GCounter)
    proof: bytes            # Opaque cryptographic proof payload
    proof_type: str         # Expected proof format for this evidence type
    timestamp: float        # POSIX timestamp of observation
```

#### Class Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `TrustEvidence.create(observer, target, evidence_type, dimension, amount, proof, *, timestamp=None)` | See fields above | `TrustEvidence` | Build with validation. Raises `ValueError` for unknown evidence type. |

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `verify(merkle_root=None)` | `merkle_root: Optional[str]` | `bool` | Verify proof without trusting observer. Dispatches to type-specific verifier. |
| `to_bytes()` | — | `bytes` | Deterministic byte representation |
| `content_hash()` | — | `str` | SHA-256 hex digest of packed evidence |

### Proof Packing Helpers

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `pack_attestation_pair(op_a, op_b)` | `op_a: bytes, op_b: bytes` | `bytes` | Pack two attestation blobs for equivocation proof |
| `pack_clock_pair(before, after)` | `before: bytes, after: bytes` | `bytes` | Pack two serialized vector clocks for regression proof |
| `pack_delta_proof(expected_hash, delta_bytes)` | `expected_hash: bytes (32B), delta_bytes: bytes` | `bytes` | Pack hash + delta for invalid-delta evidence |
| `pack_state_pair(state_a, state_b)` | `state_a: bytes, state_b: bytes` | `bytes` | Pack two trust-state snapshots for manipulation evidence |
| `pack_merkle_path(path_segments)` | `path_segments: list[Tuple[list[str], int]]` | `bytes` | Pack a Merkle path (list of sibling_hashes, position tuples) |

**Example:**

```python
from crdt_merge.e4 import TrustEvidence, pack_attestation_pair

# Build equivocation proof
proof = pack_attestation_pair(op_a_bytes, op_b_bytes)

evidence = TrustEvidence.create(
    observer="peer-alice",
    target="peer-eve",
    evidence_type="equivocation",
    dimension="integrity",
    amount=0.1,
    proof=proof,
)

assert evidence.verify()  # True if proofs are valid
```

---

## 4. `crdt_merge.e4.pco` — Aggregate Proof-Carrying Operations

Each CRDT operation carries a 128-byte aggregate proof covering four independently derivable properties: integrity, causality, trust, and minimality.

### `class SubtreeRef`

```python
@dataclass(frozen=True)
class SubtreeRef:
    path: Tuple[int, ...]   # Index path from root (0..B-1 per level)
    depth: int              # Depth in tree (max ~4 for B=256, n=1B)
    old_hash: str           # Hash before change
    new_hash: str           # Hash after change
```

### `class AggregateProofCarryingOperation`

```python
@dataclass(frozen=True)
class AggregateProofCarryingOperation:
    aggregate_hash: bytes                     # 32 bytes
    signature: bytes                          # 64 bytes (Ed25519)
    originator_id: str
    metadata: bytes                           # 32 bytes (version + flags + timestamp + pad)
    merkle_root_at_creation: str
    clock_snapshot: bytes
    trust_vector_hash: str
    delta_bounds: Tuple[SubtreeRef, ...]
```

Wire format: 64B signature + 32B aggregate hash + 32B metadata = **128 bytes total**.

#### Class Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `build(originator_id, signing_fn, merkle_root, clock_snapshot, trust_vector_hash, delta_bounds, *, version=1, flags=0)` | See params | `AggregateProofCarryingOperation` | Compute aggregate hash, sign, return ready PCO |
| `from_wire(data, originator_id, merkle_root="", clock_snapshot=b"", trust_vector_hash="", delta_bounds=())` | See params | `AggregateProofCarryingOperation` | Deserialize from 128-byte wire format |

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `verify(state, trust_lattice, *, verification_level=2)` | `state: object, trust_lattice: object, verification_level: int` | `bool` | Verify at adaptive immune level (0–3) |
| `to_wire()` | — | `bytes` | Serialize to 128-byte wire format |

**Verification levels:**

| Level | Cost | Checks |
|-------|------|--------|
| 0 | O(1) | Signature only |
| 1 | O(1) | Signature + Merkle root consistency |
| 2 | O(k) | Full: signature + integrity + causality + trust + minimality |
| 3 | O(1) | Reject unconditionally |

**Example:**

```python
from crdt_merge.e4 import AggregateProofCarryingOperation, SubtreeRef

pco = AggregateProofCarryingOperation.build(
    originator_id="peer-alice",
    signing_fn=my_ed25519_sign,
    merkle_root=merkle.root_hash,
    clock_snapshot=clock.serialize_compact(),
    trust_vector_hash=trust_score.hash(),
    delta_bounds=[SubtreeRef(path=(0,), depth=1, old_hash="aaa", new_hash="bbb")],
)

wire = pco.to_wire()  # 128 bytes
assert pco.verify(state, trust_lattice, verification_level=2)
```

---

## 5. `crdt_merge.e4.projection_delta` — Sparse Delta Encoding

Changed elements are identified via O(log_B n) high-arity Merkle tree traversal, then encoded as sparse deltas.

### `class FrozenDict`

```python
class FrozenDict(Mapping):
    """Immutable dictionary for use in frozen dataclasses."""
```

Implements `__getitem__`, `__iter__`, `__len__`, `__hash__`, `__eq__`. Accepts `Mapping` or keyword arguments in constructor.

### `class ProjectionDelta`

```python
@dataclass(frozen=True)
class ProjectionDelta:
    source_id: str
    source_version: object                    # VectorClock
    target_version: object                    # VectorClock
    changed_subtrees: Tuple[SubtreeRef, ...]
    insertions: FrozenDict                    # key → new_value (bytes)
    updates: FrozenDict                       # key → (old_hash, new_value)
    deletions: FrozenSet[str]
    pco: AggregateProofCarryingOperation
    encoding: str = "raw"                     # "raw", "sparse", "quantized"
    compression_ratio: float = 1.0
```

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `is_empty()` | — | `bool` | True when delta carries no changes |
| `compose(other)` | `other: ProjectionDelta` | `ProjectionDelta` | Associative chaining: `delta(A→B) . delta(B→C) = delta(A→C)` |
| `compress(encoding="sparse", **kwargs)` | `encoding: str` | `ProjectionDelta` | Return compressed copy. Encodings: `raw`, `sparse`, `quantized` (with `bits=8` kwarg) |
| `with_pco(pco)` | `pco: AggregateProofCarryingOperation` | `ProjectionDelta` | Return copy with new PCO attached |
| `content_hash()` | — | `str` | Deterministic SHA-256 of delta content (excluding PCO) |

**Example:**

```python
from crdt_merge.e4 import ProjectionDelta, FrozenDict, SubtreeRef

delta = ProjectionDelta(
    source_id="peer-alice",
    source_version=None,
    target_version=None,
    changed_subtrees=(SubtreeRef(path=(0,), depth=1, old_hash="aaa", new_hash="bbb"),),
    insertions=FrozenDict({"key1": b"value1"}),
    updates=FrozenDict({"key2": ("old_hash_hex", b"new_value")}),
    deletions=frozenset(["key3"]),
    pco=my_pco,
)

# Compose deltas
combined = delta_ab.compose(delta_bc)  # delta(A→C)

# Compress for transmission
sparse = delta.compress("sparse")
print(sparse.compression_ratio)
```

---

### `class ProjectionDeltaManager`

Manages delta lifecycle: creation, composition, and history.

```python
class ProjectionDeltaManager:
    def __init__(self, *, max_history: int = 64): ...
```

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `record(delta)` | `delta: ProjectionDelta` | `None` | Append to per-peer history log |
| `compose_range(peer_id, start=0, end=None)` | `peer_id: str, start: int, end: Optional[int]` | `Optional[ProjectionDelta]` | Compose contiguous range of deltas for a peer |
| `latest(peer_id)` | `peer_id: str` | `Optional[ProjectionDelta]` | Most recent delta from peer, or None |
| `clear(peer_id=None)` | `peer_id: Optional[str]` | `None` | Clear history for specific peer or all peers |
| `peers()` | — | `list[str]` | Peer IDs with recorded deltas |

---

## 6. `crdt_merge.e4.delta_trust_lattice` — The Recursive Binding

**This is the E4 recursive binding.** Trust IS data — it flows through the same two-layer pipeline as data deltas. The trust system uses itself to propagate itself.

### Protocols

```python
@runtime_checkable
class MerkleProvider(Protocol):
    @property
    def root_hash(self) -> str: ...
    def update_trust_context(self, peer_id: str, trust: TypedTrustScore) -> None: ...

@runtime_checkable
class ClockProvider(Protocol):
    def serialize_compact(self) -> bytes: ...
    def increment(self) -> ClockProvider: ...

@runtime_checkable
class DeltaEncoderProvider(Protocol):
    def encode_trust_change(self, peer_id, old_trust, new_trust, evidence) -> ProjectionDelta: ...
    def decode_trust_evidence(self, delta: ProjectionDelta) -> TrustEvidence: ...
```

### Exceptions

```python
class CircuitBreakerTripped(RuntimeError):
    """Raised when trust velocity exceeds safe thresholds."""
```

### `class TrustCircuitBreaker`

Trust velocity monitor — halts delta application when anomalous. Biological analogy: immune system inflammatory response.

```python
class TrustCircuitBreaker:
    def __init__(
        self,
        *,
        window_size: int = 100,
        sigma_threshold: float = 2.0,
        cooldown_seconds: float = 30.0,
        min_samples: int = 10,
    ) -> None: ...
```

#### Instance Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `record_trust_change(peer_id, old, new)` | `peer_id: str, old: TypedTrustScore, new: TypedTrustScore` | `None` | Record change; trip if velocity > mean + σ×threshold |
| `is_tripped()` | — | `bool` | True when breaker is active (auto-resets after cooldown) |
| `reset()` | — | `None` | Manually reset the breaker |

### `class DeltaTrustLattice`

```python
class DeltaTrustLattice:
    def __init__(
        self,
        peer_id: str,
        *,
        merkle: Optional[MerkleProvider] = None,
        clock: Optional[ClockProvider] = None,
        delta_encoder: Optional[DeltaEncoderProvider] = None,
        homeostasis: Optional[TrustHomeostasis] = None,
        circuit_breaker: Optional[TrustCircuitBreaker] = None,
        signing_fn: Optional[Callable[[bytes], bytes]] = None,
        initial_peers: Optional[Set[str]] = None,
    ) -> None: ...
```

#### Dependency Injection Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_merkle(merkle)` | `merkle: MerkleProvider` | `None` | Late-bind Merkle tree |
| `bind_clock(clock)` | `clock: ClockProvider` | `None` | Late-bind causal clock |

#### Core Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `observe_and_propagate(evidence)` | `evidence: TrustEvidence` | `ProjectionDelta` | Observe misbehaviour, update trust, return delta for propagation. Raises `CircuitBreakerTripped`, `ValueError`. |
| `receive_trust_delta(delta, state=None)` | `delta: ProjectionDelta, state: Optional[object]` | `bool` | Receive trust delta from another peer with adaptive verification |
| `get_trust(peer_id)` | `peer_id: str` | `TypedTrustScore` | Current trust score for peer (defaults to probationary) |
| `compute_trust_root()` | — | `str` | Aggregate SHA-256 hash across all peer trust vectors |
| `merge(other)` | `other: DeltaTrustLattice` | `DeltaTrustLattice` | CRDT merge of two lattices with homeostasis |
| `drain_async_queue()` | — | `List[ProjectionDelta]` | Return and clear pending async verification items |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `peer_id` | `str` | Local peer identifier |
| `peer_count` | `int` | Number of tracked peers |
| `evidence_log` | `List[TrustEvidence]` | Copy of all recorded evidence |
| `pending_async_verifications` | `int` | Items in the async verification queue |

#### Instance Methods (introspection)

| Method | Returns | Description |
|--------|---------|-------------|
| `known_peers()` | `Set[str]` | Set of all tracked peer IDs |

**Example:**

```python
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice

lattice = DeltaTrustLattice("peer-alice", initial_peers={"peer-bob", "peer-carol"})

# Check trust
trust = lattice.get_trust("peer-bob")
print(trust.overall_trust())       # 0.5 (probationary)
print(trust.verification_level())  # 1

# Observe misbehaviour and propagate
delta = lattice.observe_and_propagate(evidence)
# delta is a ProjectionDelta that flows through the standard pipeline

# Receive trust delta from remote peer
accepted = lattice.receive_trust_delta(incoming_delta)
```

---

## 7. `crdt_merge.e4.trust_bound_merkle` — Trust-Bound High-Arity Merkle Tree

E1 entanglement: hashes incorporate trust context. `H(data ‖ trust_score ‖ originator)` instead of `H(data)`.

### `class MerkleNode`

```python
@dataclass
class MerkleNode:
    path: Tuple[int, ...]
    hash: str = ""
    compat_hash: str = ""
    is_leaf: bool = False
    children: List[Optional[MerkleNode]] = field(default_factory=list)
    data: Optional[bytes] = None
    originator: Optional[str] = None
```

| Method | Returns | Description |
|--------|---------|-------------|
| `child_hashes()` | `List[str]` | Hashes of all children |

### `class TrustBoundMerkle`

```python
class TrustBoundMerkle:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        *,
        branching_factor: int = 256,
        compatibility_mode: bool = False,
    ) -> None: ...
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `root_hash` | `str` | Current root hash (empty string if no tree) |
| `root_compat_hash` | `str` | Pre-E4 compatible root hash |
| `branching_factor` | `int` | Number of children per node |
| `compatibility_mode` | `bool` | Whether dual-hash mode is active |
| `leaf_count` | `int` | Number of leaves in the tree |

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Late-bind trust lattice |
| `compute_leaf_hash(data, originator)` | `data: bytes, originator: str` | `str` | Trust-bound leaf hash: `H(data ‖ trust ‖ originator)` |
| `compute_leaf_hash_compat(data)` | `data: bytes` | `str` | Standard `H(data)` for pre-E4 compat |
| `compute_intermediate_hash(child_hashes, trust_root)` | `child_hashes: Sequence[str], trust_root: str` | `str` | Trust-bound intermediate hash |
| `compute_intermediate_hash_compat(child_hashes)` | `child_hashes: Sequence[str]` | `str` | Standard intermediate hash |
| `find_changed_subtrees(local_node, remote_node, result, depth=0)` | See params | `None` | O(k × depth) changed subtree detection; appends `SubtreeRef`s to `result` |
| `verify_path(leaf_data, originator, path_steps, expected_root)` | See params | `bool` | Verify trust-bound Merkle path |
| `verify_path_compat(leaf_data, path_steps, expected_root)` | See params | `bool` | Verify standard Merkle path |
| `is_plausible_root(root)` | `root: str` | `bool` | Check if root is plausible given local state |
| `update_trust_context(peer_id, trust)` | `peer_id: str, trust: TypedTrustScore` | `None` | Invalidate cached trust after trust change |
| `insert_leaf(key, data, originator)` | `key: str, data: bytes, originator: str` | `str` | Insert leaf, return trust-bound hash |
| `recompute()` | — | `str` | Full O(n) rebuild; returns new root hash |

---

## 8. `crdt_merge.e4.causal_trust_clock` — Causal Trust Clock

E2 entanglement: vector clock entries carry trust scores. Low-trust peers cannot causally dominate high-trust peers.

```python
class CausalTrustClock:
    TRUST_OVERRIDE_FACTOR = 1.5

    def __init__(
        self,
        peer_id: str,
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> None: ...
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `peer_id` | `str` | Local peer identifier |
| `logical_time` | `int` | Local peer's logical time |
| `entries` | `Dict[str, Tuple[int, float]]` | Copy of all (time, trust) entries |

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Late-bind trust lattice |
| `increment()` | — | `CausalTrustClock` | Increment local clock with current trust (new instance) |
| `trust_weighted_compare(other)` | `other: CausalTrustClock` | `str` | Returns `"before"`, `"after"`, `"concurrent"`, or `"trust_override"` |
| `merge(other)` | `other: CausalTrustClock` | `CausalTrustClock` | CRDT merge: element-wise max of (time, trust) pairs |
| `serialize_compact()` | — | `bytes` | Compact binary for PCO embedding |
| `deserialize_compact(data, peer_id, trust_lattice=None)` | See params | `CausalTrustClock` | Class method: reconstruct from compact bytes |
| `is_consistent_with(snapshot)` | `snapshot: bytes` | `bool` | Check serialized clock is causally consistent |
| `content_hash()` | — | `str` | SHA-256 of compact serialization |
| `known_peers()` | — | `Set[str]` | Set of peers with clock entries |
| `get_entry(peer_id)` | `peer_id: str` | `Tuple[int, float]` | Get (time, trust) for peer |

**Comparison outcomes:**

| Outcome | Meaning |
|---------|---------|
| `"before"` | Strictly causally before (standard) |
| `"after"` | Strictly causally after (standard) |
| `"concurrent"` | Incomparable under standard causality |
| `"trust_override"` | Causally before, but local trust weight exceeds remote by override factor |

---

## 9. `crdt_merge.e4.adaptive_verification` — Adaptive Immune Verification

Four-tier gating: trusted peers get O(1) verification, untrusted peers get full O(k) PCO verification, quarantined peers are rejected outright.

### `class VerificationOutcome` (Enum)

| Value | Description |
|-------|-------------|
| `ACCEPT` | Delta accepted |
| `REJECT` | Delta rejected |

### `class VerificationResult`

```python
@dataclass
class VerificationResult:
    outcome: VerificationOutcome
    level: int
    reason: str = ""
    async_pending: bool = False
```

| Property | Type | Description |
|----------|------|-------------|
| `accepted` | `bool` | Computed: `outcome == ACCEPT` |
| `reason` | `str` | Rejection reason (if applicable) |
| `async_pending` | `bool` | True if full verification is deferred |

### `class AdaptiveVerificationController`

```python
class AdaptiveVerificationController:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        circuit_breaker: Optional[TrustCircuitBreaker] = None,
        async_queue_limit: int = 1024,
    ) -> None: ...
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `verify(delta, state, trust_lattice=None)` | `delta: ProjectionDelta, state: object, trust_lattice: Optional[DeltaTrustLattice]` | `VerificationResult` | Verify delta at trust-determined level |
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Inject trust lattice |
| `bind_circuit_breaker(cb)` | `cb: TrustCircuitBreaker` | `None` | Inject circuit breaker |
| `run_async_followup(state, trust_lattice=None)` | `state: object, trust_lattice: Optional[DeltaTrustLattice]` | `List[Tuple[ProjectionDelta, VerificationResult]]` | Re-verify pending items at Level 2 |
| `drain_async_queue()` | — | `List[ProjectionDelta]` | Return and clear pending async items |

| Property | Type | Description |
|----------|------|-------------|
| `pending_async_count` | `int` | Number of items in async queue |

---

## 10. `crdt_merge.e4.compatibility` — Dual-Hash Compatibility Mode

Zero-downtime migration between pre-E4 and E4 peers.

### `class CompatibilityMode` (Enum)

| Value | Description |
|-------|-------------|
| `E4_ONLY` (`"e4_only"`) | Trust-bound hashes only |
| `DUAL_HASH` (`"dual_hash"`) | Both trust-bound and legacy hashes |
| `LEGACY_ONLY` (`"legacy_only"`) | Standard hashes only (pre-E4) |

### `class PeerCapability` (Enum)

| Value | Int | Description |
|-------|-----|-------------|
| `PRE_E4` | 0 | Pre-E4 peer |
| `E4_DUAL` | 1 | E4 peer in dual-hash mode |
| `E4_FULL` | 2 | Full E4 peer |

### `class CompatHandshake`

```python
@dataclass(frozen=True)
class CompatHandshake:
    peer_id: str
    capability: PeerCapability
    version: int = 1
```

### `class CompatibilityController`

```python
class CompatibilityController:
    def __init__(
        self,
        default_mode: CompatibilityMode = CompatibilityMode.E4_ONLY,
        merkle: Optional[TrustBoundMerkle] = None,
    ) -> None: ...
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `process_handshake(hs)` | `hs: CompatHandshake` | `CompatibilityMode` | Negotiate mode with peer based on capabilities |
| `mode_for_peer(peer_id)` | `peer_id: str` | `CompatibilityMode` | Get negotiated mode (default for unknown peers) |
| `build_handshake(peer_id)` | `peer_id: str` | `CompatHandshake` | Build outgoing handshake with local capability |
| `compute_hashes(data, originator, peer_id)` | `data: bytes, originator: str, peer_id: str` | `Dict[str, str]` | Compute hashes per negotiated mode (`"e4"`, `"legacy"` keys) |
| `set_default_mode(mode)` | `mode: CompatibilityMode` | `None` | Change default mode |
| `peers_ready_for_e4_only()` | — | `List[str]` | Peers in DUAL_HASH with E4_FULL capability |
| `upgrade_peer(peer_id)` | `peer_id: str` | `CompatibilityMode` | Upgrade peer to next mode if capable |
| `known_peers()` | — | `Dict[str, PeerCapability]` | Map of peer → capability |
| `peer_count_by_mode()` | — | `Dict[CompatibilityMode, int]` | Counts per negotiated mode |
| `bind_merkle(merkle)` | `merkle: TrustBoundMerkle` | `None` | Inject Merkle tree for hash computation |

| Property | Type | Description |
|----------|------|-------------|
| `default_mode` | `CompatibilityMode` | Current system default mode |

### Helper Function

```python
def _mode_to_capability(mode: CompatibilityMode) -> PeerCapability
```

---

## 11. `crdt_merge.e4.integration.config` — Runtime Configuration

### `class E4Config`

```python
@dataclass
class E4Config:
    # Trust thresholds
    probation_trust: float = 0.5
    quarantine_threshold: float = 0.1
    low_trust_threshold: float = 0.4
    partial_trust_threshold: float = 0.8

    # Circuit breaker
    cb_window_size: int = 100
    cb_sigma_threshold: float = 2.0
    cb_cooldown_seconds: float = 30.0
    cb_min_samples: int = 10

    # Merkle tree
    merkle_branching_factor: int = 256

    # Compatibility
    compatibility_mode: str = "e4_only"

    # Verification
    verification_level_override: Optional[int] = None

    # Performance
    async_queue_limit: int = 1024

    # Features
    homeostasis_enabled: bool = True
    gossip_include_trust_deltas: bool = True
    stream_per_chunk_validation: bool = True

    # History
    delta_max_history: int = 64
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `trust_thresholds()` | `Dict[str, float]` | Dict with `"probation"`, `"quarantine"`, `"low"`, `"partial"` keys |

### Module-Level Config Management

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_config()` | — | `E4Config` | Get global config (creates default if not set) |
| `set_config(cfg)` | `cfg: E4Config` | `None` | Replace global config |
| `reset_config()` | — | `None` | Reset to factory defaults |

**Example:**

```python
from crdt_merge.e4.integration.config import E4Config, set_config, get_config

# Customize for production
set_config(E4Config(
    merkle_branching_factor=64,
    compatibility_mode="dual_hash",
    cb_cooldown_seconds=60.0,
))

cfg = get_config()
print(cfg.trust_thresholds())
# {'probation': 0.5, 'quarantine': 0.1, 'low': 0.4, 'partial': 0.8}
```

---

## 12. `crdt_merge.e4.integration.gossip_bridge` — Trust-Enhanced Gossip

Unified data + trust gossip over the existing gossip protocol.

### `class TrustGossipPayload`

```python
class TrustGossipPayload:
    data_deltas: List[ProjectionDelta] = []
    trust_deltas: List[ProjectionDelta] = []
    peer_id: str = ""
```

### `class TrustGossipEngine`

```python
class TrustGossipEngine:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
    ) -> None: ...
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Set lattice |
| `bind_verifier(verifier)` | `verifier: AdaptiveVerificationController` | `None` | Set verifier |
| `bind_state(state)` | `state: object` | `None` | Set application state |
| `prepare_sync(deltas, include_trust=True)` | `deltas: List[ProjectionDelta], include_trust: bool` | `TrustGossipPayload` | Build outbound gossip payload |
| `receive_sync(payload)` | `payload: TrustGossipPayload` | `Tuple[List[ProjectionDelta], List[ProjectionDelta]]` | Process inbound payload; returns `(accepted_data, accepted_trust)` |
| `drain_outbound()` | — | `List[TrustGossipPayload]` | Return and clear pending outbound payloads |

| Property | Type | Description |
|----------|------|-------------|
| `pending_outbound` | `int` | Number of pending outbound payloads |

---

## 13. `crdt_merge.e4.integration.stream_bridge` — Trust-Validated Streaming

Trust-validated streaming merge with per-chunk verification.

### `class StreamChunk`

```python
@dataclass
class StreamChunk:
    delta: ProjectionDelta
    sequence: int
    stream_id: str = ""
```

### `class ChunkResult`

```python
@dataclass(frozen=True)
class ChunkResult:
    accepted: bool
    sequence: int
    reason: str = ""
```

### `class TrustStreamMerge`

```python
class TrustStreamMerge:
    def __init__(
        self,
        min_trust: float = 0.1,
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
    ) -> None: ...
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_verifier(verifier)` | `verifier: AdaptiveVerificationController` | `None` | Set verifier |
| `bind_state(state)` | `state: object` | `None` | Set application state |
| `accept_stream(peer_id, stream_id, lattice)` | `peer_id: str, stream_id: str, lattice: object` | `bool` | Gate: accept/reject stream based on peer trust |
| `validate_chunk(chunk)` | `chunk: StreamChunk` | `ChunkResult` | Validate a single stream chunk |
| `validate_stream(chunks)` | `chunks: List[StreamChunk]` | `List[ChunkResult]` | Validate all chunks in a stream |
| `stream_results(stream_id)` | `stream_id: str` | `List[ChunkResult]` | Get results for a stream |
| `close_stream(stream_id)` | `stream_id: str` | `None` | Close and remove a stream |
| `active_stream_ids()` | — | `List[str]` | List all active stream IDs |

---

## 14. `crdt_merge.e4.integration.agent_bridge` — Trust-Aware Agent State

Trust-weighted agent state management with conflict resolution and snapshot support.

### `class TrustAnnotatedEntry`

```python
@dataclass
class TrustAnnotatedEntry:
    key: str
    value: Any
    peer_id: str
    trust_at_write: float
    timestamp: float = 0.0
```

### `class TrustAgentState`

```python
class TrustAgentState:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        trust_weight_context: bool = True,
    ) -> None: ...
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Set lattice post-init |
| `put(key, value, peer_id, timestamp=None)` | `key: str, value: Any, peer_id: str, timestamp: Optional[float]` | `TrustAnnotatedEntry` | Store entry with trust annotation |
| `get(key)` | `key: str` | `Optional[TrustAnnotatedEntry]` | Retrieve entry or None |
| `delete(key)` | `key: str` | `Optional[TrustAnnotatedEntry]` | Remove and return entry, or None |
| `merge_context(other)` | `other: TrustAgentState` | `TrustAgentState` | Merge two states; conflicts resolved by trust weight |
| `snapshot()` | — | `Dict[str, TrustAnnotatedEntry]` | Export all entries |
| `load_snapshot(snap)` | `snap: Dict[str, TrustAnnotatedEntry]` | `None` | Replace all entries |
| `ranked_entries()` | — | `List[TrustAnnotatedEntry]` | All entries sorted by trust descending |
| `peer_contributions()` | — | `Dict[str, int]` | Count of entries per peer |

| Property | Type | Description |
|----------|------|-------------|
| `size` | `int` | Number of entries |

**Example:**

```python
from crdt_merge.e4.integration.agent_bridge import TrustAgentState

state = TrustAgentState(trust_lattice=lattice)
state.put("model_weights", weights_bytes, "peer-alice")
state.put("config", config_data, "peer-bob")

# Merge with remote state — trust resolves conflicts
merged = state.merge_context(remote_state)

# Inspect contributions
print(merged.peer_contributions())  # {"peer-alice": 1, "peer-bob": 1}
```

---

*This document is auto-generated from the E4 source code on branch `feature/0.9.5-e4-recursive-entanglement`. For architectural context, see [E4-MASTER-ARCHITECTURE.md](../E4-MASTER-ARCHITECTURE.md).*


---

## Resilience API (v0.9.5.1)

### `crdt_merge.e4.resilience.domain_hash`

| Class | Method | Description |
|-------|--------|-------------|
| `DomainSeparatedHasher` | `domain_hash(domain, data)` | Hash with domain separator |
| | `aggregate_hash(merkle, clock, trust, bounds)` | Four-domain aggregate |
| | `verify_aggregate(expected, m, c, t, b)` | Constant-time verification |
| | `epoch_scoped_hash(epoch, data)` | Epoch-tagged hash |

### `crdt_merge.e4.resilience.key_manager`

| Class | Method | Description |
|-------|--------|-------------|
| `KeyPair` | `generate()` | Create fresh key pair |
| | `sign(message)` | HMAC-SHA256 signature |
| | `verify(message, signature)` | Verify signature |
| `KeyManager` | `rotate_key()` | Rotate with auto-revocation |
| | `emergency_revoke(reason)` | Immediate key invalidation |
| `PeerKeyRegistry` | `register(peer, key)` | Add peer key |
| | `revoke(entry)` | Revoke key (CRDT grow-set) |
| | `merge(other)` | CRDT merge registries |

### `crdt_merge.e4.resilience.epoch_protocol`

| Class | Method | Description |
|-------|--------|-------------|
| `EpochState` | `advance()` | Increment epoch |
| | `merge(other)` | CRDT merge (max wins) |
| | `prune()` | GC old evidence |
| `EpochManager` | `force_advance()` | Force epoch transition |
| | `gc_evidence()` | Garbage collect |
| | `partition_resolution_strategy(local, remote)` | Fast-forward or quarantine |

### `crdt_merge.e4.resilience.convergence_monitor`

| Class | Method | Description |
|-------|--------|-------------|
| `ConvergenceBound` | `compute(peers, ...)` | Theoretical bound |
| `ConvergenceMonitor` | `record_convergence(time)` | Track actual convergence |
| | `average_convergence_time` | Rolling average |
| | `p99_convergence_time` | 99th percentile |

### `crdt_merge.e4.resilience.trust_resilience`

| Class | Method | Description |
|-------|--------|-------------|
| `TrustPrivacyFilter` | `filter_trust_score(score)` | ε-DP noised score |
| | `filter_trust_vector(scores)` | Batch DP filtering |
| `ByzantineThresholdAnalyzer` | `analyze(honest, adversarial)` | Degradation analysis |
| | `sweep(total, steps)` | Full ratio sweep |
| | `critical_threshold(total)` | Find critical f/n ratio |
| `ColdStartBootstrap` | `introduce(trust, intro)` | Vouch-based introduction |
| | `decay_step()` | Decay temporary boosts |
| `ExtendedDimensionRegistry` | `register(name, weight)` | Add custom dimension |
| | `weighted_overall_trust(scores)` | Weighted aggregate |

### `crdt_merge.e4.resilience.semantic_validator`

| Class | Method | Description |
|-------|--------|-------------|
| `MagnitudeValidator` | `validate(data, peer, trust)` | Absolute bounds check |
| `StatisticalShiftDetector` | `validate(data, peer, trust)` | Distribution shift detection |
| `ParameterRegionGuard` | `validate(data, peer, trust)` | Region-specific bounds |
| `CompositeSemanticValidator` | `validate(data, peer, trust)` | Chain all validators |

### `crdt_merge.e4.resilience.delta_resilience`

| Class | Method | Description |
|-------|--------|-------------|
| `ReanchorPolicy` | `record_composition()` | Track chain + check limit |
| | `checkpoint(version, hash)` | Re-anchor full precision |
| `DeltaCompositionSpec` | `compose(ab_*, bc_*)` | Formal δ(A→B) ∘ δ(B→C) |
| `ParameterTypeEncoder` | `classify(key)` | Detect parameter type |
| | `recommend(key)` | Optimal encoding strategy |
| `CommutativityAdapter` | `commutative_merge(entries, fn)` | Wrap non-commutative ops |

### `crdt_merge.e4.resilience.performance_spec`

| Class | Method | Description |
|-------|--------|-------------|
| `SketchConfig` | `for_target(ε, δ)` | Optimal sketch params |
| | `for_scale(peers)` | Auto-configure for scale |
| `FanoutOptimizer` | `optimize(peers)` | Optimal gossip fan-out |
| | `scale_report()` | Multi-scale report |
| `ProductionDeratingSpec` | `derate(value, category)` | Benchmark → production |
| `HardwareRequirements` | `for_scale(peers)` | Minimum hardware |
| | `scale_matrix()` | Multi-scale requirements |

---

## Round 2 Resilience API (v0.9.5.2)

### `crdt_merge.e4.resilience.formal_spec`

TLA+ specification generator and bounded model checker for E4 convergence properties.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `SpecBounds` | `max_peers`, `max_ops`, `trust_dimensions`, `max_epochs`, `max_logical_time` | Configurable model checking bounds |
| | `state_space_estimate()` | Rough upper bound on reachable states |
| `TemporalProperty` | `name`, `kind`, `formula`, `description` | Named temporal logic property (`"safety"` or `"liveness"`) |
| `PropertyVerifier` | `verify(spec, bounds)` | Run bounded model check on a spec |
| | `verify_property(spec, prop, bounds)` | Check a single temporal property |
| `E4FormalSpec` | `generate(bounds)` | Generate TLA+ spec from E4 state |
| | `properties()` | List all temporal properties checked |
| | `check_all(bounds)` | Generate spec and verify all properties |

### `crdt_merge.e4.resilience.longcon_sybil`

Long-con (patient) Sybil detector using three independent statistical correlation signals.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `LongConConfig` | `correlation_window`, `correlation_threshold`, `timing_ks_threshold`, `density_threshold`, `min_signals` | Detection thresholds |
| `EvidenceRecord` | `peer_id`, `timestamp`, `dimension`, `amount` | Single evidence observation record |
| `SybilAlert` | `suspect_group`, `signals_triggered`, `confidence`, `timestamp` | Alert raised when ≥2 signals trigger |
| `LongConDetector` | `record_evidence(record)` | Feed evidence observation |
| | `check()` | Run all three signals, return alerts |
| | `trust_growth_correlation()` | Signal A: pairwise Pearson correlation |
| | `timing_correlation()` | Signal B: KS test on inter-arrival times |
| | `graph_density()` | Signal C: local clustering coefficient |

### `crdt_merge.e4.resilience.pq_signatures`

Post-quantum signature abstraction layer with hybrid classical/PQ support.

| Class / Function | Method / Field | Description |
|-----------------|---------------|-------------|
| `SignatureScheme` (ABC) | `name()`, `generate_keypair(seed)`, `sign(private_key, message)`, `verify(public_key, message, signature)`, `signature_size` | Abstract scheme interface |
| `HmacScheme` | Implements `SignatureScheme` | HMAC-SHA256 (backwards compatible) |
| `DilithiumLite` | Implements `SignatureScheme` | Lattice-based PQ scheme (SHAKE-256) |
| `HybridScheme` | Implements `SignatureScheme` | Classical + PQ in parallel; both must verify |
| `get_scheme(name)` | — | Registry lookup by scheme name |
| `register_scheme(scheme)` | — | Register custom scheme |
| `available_schemes()` | — | List registered scheme names |

### `crdt_merge.e4.resilience.noniid_convergence`

Non-IID convergence analysis for trust-model interaction.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `HeterogeneityProfile` | `peer_count`, `label_skew`, `volume_skew`, `feature_shift` | Characterise non-IID data distribution |
| | `regime()` | Classify as `"iid"`, `"mild"`, or `"severe"` |
| `ConvergenceBound` | `rounds_to_converge`, `trust_gap_at_round`, `model_gap_at_round`, `regime` | Formal bound on convergence rate |
| `WarmupSchedule` | `compute(profile, gossip_interval, learning_rate)` | Adaptive warmup for early rounds |
| | `evidence_threshold_at(round)` | Per-round evidence threshold |
| `TrustConvergenceAnalyser` | `analyse(profile)` | Full convergence analysis |
| | `bound(profile)` | Compute formal convergence bound |
| | `recommend_warmup(profile)` | Recommend warmup schedule |

### `crdt_merge.e4.resilience.trust_inheritance`

Three-tier trust inheritance manager for cold-start at institutional scale.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `VouchRecord` | `institution_id`, `device_ids`, `trust_ceiling`, `dimensions`, `timestamp` | Signed institutional vouch (frozen, CRDT-compatible) |
| `DeviceCluster` | `cluster_id`, `device_ids`, `network_characteristics` | Devices sharing network characteristics |
| | `median_trust(lattice)` | Compute median trust of active cluster members |
| `TrustInheritanceManager` | `register_institution(id, trust)` | Register institution with trust score |
| | `issue_vouch(institution_id, device_ids, ceiling)` | Issue vouch record |
| | `register_cluster(cluster)` | Register device cluster |
| | `effective_trust(device_id)` | Tier 1 + Tier 2 + Tier 3 combined trust |
| | `merge(other)` | CRDT merge of inheritance state |

### `crdt_merge.e4.resilience.gossip_budget`

Hierarchical gossip budget management for O(√N) trust gossip at scale.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `BandwidthEstimate` | `full_state_bytes`, `sparse_delta_bytes`, `regional_summary_bytes`, `recommended_strategy` | Bandwidth estimate per strategy |
| `SparseTrustDelta` | `changed_peers`, `bloom_filter` | Sparse delta tracked via bloom filter |
| | `encode()` | Encode sparse delta for transmission |
| `HierarchicalAggregator` | `add_region(region_id, peer_ids)` | Partition peers into trust regions |
| | `regional_summary(region_id)` | Min/max/median/count for a region |
| | `cross_region_payload()` | Summaries for all regions |
| | `estimate_bandwidth(peer_count)` | Bandwidth estimate at given scale |
| `AdaptiveGossipRate` | `current_interval()` | Current gossip interval |
| | `record_convergence(variance)` | Adjust rate based on trust variance |
| | `on_churn_event()` | Increase rate during churn |

### `crdt_merge.e4.resilience.deterministic_merge`

IEEE 754 deterministic merge arithmetic for reproducible trust-weighted averaging.

| Class / Function | Method / Field | Description |
|-----------------|---------------|-------------|
| `kahan_sum(values)` | — | Compensated summation: error O(ε) instead of O(n×ε) |
| `deterministic_sum(values)` | — | Sorted Kahan: canonical order + compensation |
| `DeterministicMerge` | `weighted_average(values, weights)` | Deterministic trust-weighted average |
| | `strategy` | Active strategy: `"sorted_kahan"`, `"integer"`, or `"kahan"` |
| | `set_strategy(name)` | Switch accumulation strategy |

### `crdt_merge.e4.resilience.strategy_drift`

Strategy drift discriminator for multi-agent RL environments.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `BehavioralFingerprint` | `magnitude_histogram`, `region_histogram`, `frequency`, `total_contributions` | Rolling characterisation of agent contributions |
| | `record(magnitude, region)` | Record a contribution |
| | `normalised_magnitude()` | Normalised magnitude distribution |
| `DriftVerdict` | `peer_id`, `is_legitimate`, `confidence`, `coherence_score`, `cohort_correlation` | Verdict on drift legitimacy |
| `StrategyDriftDiscriminator` | `record_contribution(peer_id, magnitude, region)` | Feed contribution data |
| | `evaluate(peer_id)` | Two-phase analysis → `DriftVerdict` |
| | `cohort_shift_detected()` | Check for correlated multi-agent shifts |

### `crdt_merge.e4.resilience.partition_reconciler`

Post-partition trust reconciliation with graduated normalisation transition.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `PartitionEvent` | `timestamp`, `local_peers`, `remote_peers`, `pre_merge_budget`, `post_merge_budget` | Record of detected partition heal |
| `ReconciliationState` | `phase`, `grace_rounds_remaining`, `evidence_multiplier` | Current reconciliation state |
| `PartitionReconciler` | `on_partition_heal(event)` | Initiate graduated reconciliation |
| | `current_budget()` | Effective homeostasis budget (grace-period-aware) |
| | `evidence_multiplier(peer_id)` | Catch-up multiplier for minority-partition nodes |
| | `advance_round()` | Advance reconciliation by one round |
| | `is_reconciling()` | True during grace period |

### `crdt_merge.e4.resilience.schema_adapter`

Schema heterogeneity adapter for cross-domain delta merging.

| Class | Method / Field | Description |
|-------|---------------|-------------|
| `FieldDescriptor` | `name`, `dtype`, `position`, `nullable`, `default` | Single field in a schema |
| | `compatible_with(other)` | Check type compatibility for merge |
| `SchemaDescriptor` | `version`, `fields`, `name` | Compact schema descriptor for deltas |
| | `field_names()` | List of logical field names |
| | `content_hash()` | Deterministic hash of schema |
| `SchemaAligner` | `align(schema_a, schema_b)` | Compute field-level alignment |
| | `unified_schema(schemas)` | Produce unified merge schema |
| `SchemaRegistry` | `register(schema)` | Register schema version (CRDT OR-Set) |
| | `lookup(version)` | Retrieve schema by version |
| | `merge(other)` | CRDT merge of registries |
| `ResultNormaliser` | `set_reference(config)` | Set reference hardware/dataset config |
| | `normalise(result, source_config)` | Normalise result to reference |
| | `merge(other)` | CRDT merge of normalisation factors |
