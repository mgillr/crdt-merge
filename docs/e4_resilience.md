> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Resilience Subsystem -- API Reference

18 hardening modules addressing 49 concerns from two independent peer
review panels. Every module is additive and non-breaking -- existing APIs,
imports, and test suites remain unchanged.

For core E4 modules, see [e4.md](e4.md). For integration bridges, see
[e4_integration.md](e4_integration.md).

---

## Quick Import

```python
from crdt_merge.e4.resilience import (
    # Round 1 (original panel)
    DomainSeparatedHasher, HashDomain,
    KeyManager, KeyPair, PeerKeyRegistry, RevocationEntry,
    EpochManager, EpochState, EpochTransition,
    ConvergenceBound, ConvergenceMonitor,
    TrustPrivacyFilter, ByzantineThresholdAnalyzer,
    ColdStartBootstrap, ExtendedDimensionRegistry,
    SemanticValidator, MagnitudeValidator,
    StatisticalShiftDetector, ParameterRegionGuard,
    CompositeSemanticValidator,
    ReanchorPolicy, DeltaCompositionSpec,
    ParameterTypeEncoder, ParameterType, CommutativityAdapter,
    SketchConfig, FanoutOptimizer,
    ProductionDeratingSpec, HardwareRequirements,
    # Round 2 (alternate panel)
    E4FormalSpec, PropertyVerifier, SpecBounds, TemporalProperty,
    LongConDetector, LongConConfig, SybilAlert,
    HmacScheme, DilithiumLite, HybridScheme,
    register_scheme, get_scheme, available_schemes,
    TrustConvergenceAnalyser, HeterogeneityProfile, WarmupSchedule,
    TrustInheritanceManager, VouchRecord, DeviceCluster,
    HierarchicalAggregator, SparseTrustDelta,
    AdaptiveGossipRate, estimate_bandwidth,
    DeterministicMerge, deterministic_sum,
    StrategyDriftDiscriminator, DriftVerdict,
    PartitionReconciler,
    SchemaDescriptor, SchemaAligner,
    SchemaRegistry, ResultNormaliser,
)
```

---

## Overview

| # | Module | Panel | Concern | Key Classes |
|---|--------|-------|---------|-------------|
| 1 | `domain_hash` | Round 1 | Cross-component hash isolation | `DomainSeparatedHasher`, `HashDomain` |
| 2 | `key_manager` | Round 1 | Key lifecycle and rotation | `KeyManager`, `KeyPair`, `PeerKeyRegistry` |
| 3 | `epoch_protocol` | Round 1 | Epoch coordination and evidence GC | `EpochManager`, `EpochState`, `EpochTransition` |
| 4 | `convergence_monitor` | Round 1 | Convergence time monitoring | `ConvergenceMonitor`, `ConvergenceBound` |
| 5 | `trust_resilience` | Round 1 | Privacy, Byzantine analysis, cold start | `TrustPrivacyFilter`, `ByzantineThresholdAnalyzer`, `ColdStartBootstrap` |
| 6 | `semantic_validator` | Round 1 | Semantic validation of parameters | `SemanticValidator`, `MagnitudeValidator`, `CompositeSemanticValidator` |
| 7 | `delta_validation` | Round 1 | Delta composition and commutativity | `ReanchorPolicy`, `DeltaCompositionSpec`, `CommutativityAdapter` |
| 8 | `performance_spec` | Round 1 | Production performance specification | `SketchConfig`, `FanoutOptimizer`, `ProductionDeratingSpec` |
| 9 | `formal_spec` | Round 2 | Formal specification and verification | `E4FormalSpec`, `PropertyVerifier` |
| 10 | `longcon_sybil` | Round 2 | Long-con Sybil detection | `LongConDetector`, `LongConConfig`, `SybilAlert` |
| 11 | `pq_signatures` | Round 2 | Post-quantum signature abstraction | `HmacScheme`, `DilithiumLite`, `HybridScheme` |
| 12 | `noniid_convergence` | Round 2 | Non-IID convergence analysis | `TrustConvergenceAnalyser`, `HeterogeneityProfile` |
| 13 | `trust_inheritance` | Round 2 | Trust inheritance and vouching | `TrustInheritanceManager`, `VouchRecord`, `DeviceCluster` |
| 14 | `gossip_budget` | Round 2 | Hierarchical gossip aggregation | `HierarchicalAggregator`, `SparseTrustDelta`, `AdaptiveGossipRate` |
| 15 | `deterministic_merge` | Round 2 | Bit-exact deterministic merge | `DeterministicMerge`, `deterministic_sum` |
| 16 | `strategy_drift` | Round 2 | Strategy drift detection | `StrategyDriftDiscriminator`, `DriftVerdict` |
| 17 | `partition_reconciler` | Round 2 | Post-partition trust reconciliation | `PartitionReconciler` |
| 18 | `schema_adapter` | Round 2 | Schema alignment across versions | `SchemaDescriptor`, `SchemaAligner`, `SchemaRegistry` |

---

## 1. `crdt_merge.e4.resilience.longcon_sybil` -- Sybil Defence

Patient adversary resistance. Detects coordinated Sybil attacks that
individually stay below trust velocity thresholds by correlating statistical
patterns across the peer population.

### `class LongConConfig`

```python
@dataclass
class LongConConfig:
    correlation_window: int = 100
    correlation_threshold: float = 0.7
    timing_ks_threshold: float = 0.3
    density_ratio_threshold: float = 3.0
    min_evidence_count: int = 10
    signals_required: int = 2          # any 2 of 3 signals trigger alert
    quarantine_duration: float = 3600.0
```

### `class LongConDetector`

```python
class LongConDetector:
    def __init__(self, config: Optional[LongConConfig] = None) -> None
```

Three independent detection signals -- any two trigger an alert:

- **Signal A: Entropy clustering.** Pairwise Pearson correlation of trust growth vectors.
- **Signal B: Evidence timing correlation.** Kolmogorov-Smirnov test on inter-evidence arrival times.
- **Signal C: Graph density anomaly.** Local clustering coefficient vs global average.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `record_evidence(peer_id, timestamp, dimension, magnitude)` | `peer_id: str, ...` | `None` | Record an evidence observation |
| `detect()` | -- | `List[SybilAlert]` | Run detection and return alerts for suspected groups |
| `quarantined_peers()` | -- | `Set[str]` | Currently quarantined peer IDs |

### `class SybilAlert`

```python
@dataclass(frozen=True)
class SybilAlert:
    group: FrozenSet[str]          # suspected Sybil peer IDs
    signals: List[SybilSignal]     # which signals triggered
    confidence: float              # [0.0, 1.0]
    timestamp: float
```

---

## 2. `crdt_merge.e4.resilience.epoch_protocol` -- Epoch Rotation

Epoch coordination as a CRDT (max-register) with evidence garbage collection.

### `class EpochState`

```python
class EpochState:
    def __init__(
        self,
        *,
        initial_epoch: int = 0,
        retention_epochs: int = 3,
    ) -> None
```

Epoch number merged by taking the maximum -- convergence without coordination.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `current_epoch()` | -- | `int` | Current epoch number |
| `advance(trigger="interval")` | `trigger: str` | `EpochTransition` | Advance to next epoch, pruning old evidence |
| `merge(other)` | `other: EpochState` | `EpochState` | CRDT merge: higher epoch wins |

### `class EpochManager`

Manages epoch lifecycle including automatic advance triggers and evidence GC.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `tick()` | -- | `Optional[EpochTransition]` | Check if epoch should advance |
| `force_advance(trigger)` | `trigger: str` | `EpochTransition` | Force an epoch advance |

### `class EpochTransition`

```python
@dataclass(frozen=True)
class EpochTransition:
    from_epoch: int
    to_epoch: int
    timestamp: float
    trigger: str = "interval"
    evidence_pruned: int = 0
```

---

## 3. `crdt_merge.e4.resilience.partition_reconciler` -- Partition Reconciliation

Graduated trust reconciliation after network partition healing.

### `class PartitionReconciler`

```python
class PartitionReconciler:
    def __init__(
        self,
        *,
        grace_rounds: int = 5,
        evidence_multiplier: float = 2.0,
    ) -> None
```

Four-phase reconciliation: merge -> grace period -> evidence catch-up -> steady state.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `on_partition_heal(local_peers, remote_peers, pre_budget, post_budget)` | `...` | `PartitionEvent` | Register a partition heal event |
| `in_grace_period(peer_id)` | `peer_id: str` | `bool` | Whether a peer is in the grace period |
| `evidence_multiplier_for(peer_id)` | `peer_id: str` | `float` | Current evidence multiplier (1.0 when not in catch-up) |
| `tick()` | -- | `None` | Advance reconciliation state machine |

---

## 4. `crdt_merge.e4.resilience.pq_signatures` -- Post-Quantum Signatures

Scheme-agnostic signature interface with hybrid classical/PQ support.

### `class HmacScheme`

Current HMAC-SHA256 implementation. Drop-in compatible with existing `KeyManager`.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `generate_keypair(seed=None)` | `seed: Optional[bytes]` | `Tuple[bytes, bytes]` | `(private_key, public_key)` |
| `sign(private_key, message)` | `private_key: bytes, message: bytes` | `bytes` | HMAC-SHA256 signature |
| `verify(public_key, message, signature)` | `...` | `bool` | Verify signature |

### `class DilithiumLite`

Dilithium-inspired lattice-based scheme using SHAKE-256. Captures the
security model and API shape for migration readiness.

| Property | Value |
|----------|-------|
| `signature_size` | 2420 bytes |
| `public_key_size` | 1312 bytes |

### `class HybridScheme`

Runs classical + PQ in parallel. Both must verify for acceptance (belt-and-suspenders).

```python
class HybridScheme:
    def __init__(
        self,
        classical: SignatureScheme,
        post_quantum: SignatureScheme,
    ) -> None
```

### Module Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `register_scheme(name, scheme)` | `name: str, scheme: SignatureScheme` | `None` | Register a named scheme |
| `get_scheme(name)` | `name: str` | `SignatureScheme` | Retrieve a registered scheme |
| `available_schemes()` | -- | `List[str]` | List registered scheme names |

---

## 5. `crdt_merge.e4.resilience.domain_hash` -- Domain-Separated Hashing

Cross-component hash isolation. Hardens against collision attacks where
a valid hash in one domain is reused in another.

### `class DomainSeparatedHasher`

```python
class DomainSeparatedHasher:
    def __init__(self) -> None
```

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `hash(domain, data)` | `domain: HashDomain, data: bytes` | `str` | Domain-separated SHA-256 |

### `class HashDomain` (Enum)

| Value | Description |
|-------|-------------|
| `MERKLE` | Merkle tree node hashing |
| `TRUST` | Trust score serialization |
| `PCO` | Proof-carrying operation hashing |
| `DELTA` | Projection delta content hashing |
| `CLOCK` | Causal trust clock hashing |

---

## 6. `crdt_merge.e4.resilience.key_manager` -- Key Management

Key lifecycle, rotation, and peer key registry.

### `class KeyManager`

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `generate_key()` | -- | `KeyPair` | Generate a new signing keypair |
| `rotate(peer_id)` | `peer_id: str` | `KeyPair` | Rotate keys for a peer |
| `revoke(peer_id, reason)` | `peer_id: str, reason: str` | `RevocationEntry` | Revoke a peer's keys |

### `class PeerKeyRegistry`

Peer-scoped key storage with revocation tracking.

### `class KeyPair`

```python
@dataclass(frozen=True)
class KeyPair:
    private_key: bytes
    public_key: bytes
    created_at: float
```

---

## 7. `crdt_merge.e4.resilience.convergence_monitor` -- Convergence Monitoring

Tracks actual convergence times against theoretical bounds and alerts if
the system is converging slower than expected.

### `class ConvergenceMonitor`

```python
class ConvergenceMonitor:
    def __init__(self, peer_count: int = 100, **kwargs) -> None
```

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `record_convergence(duration)` | `duration: float` | `None` | Record an observed convergence time |
| `check_bounds()` | -- | `ConvergenceBound` | Compare observed vs theoretical bounds |
| `is_healthy()` | -- | `bool` | Whether convergence is within expected bounds |

---

## 8. `crdt_merge.e4.resilience.trust_resilience` -- Trust Extensions

### `class TrustPrivacyFilter`

Differential privacy for trust score queries. Adds calibrated noise to
prevent trust score inference attacks.

### `class ByzantineThresholdAnalyzer`

Computes the maximum tolerable fraction of Byzantine peers for a given
federation size and trust topology.

### `class ColdStartBootstrap`

Bootstrapping strategy for new peers joining a federation with no trust
history. Supports: vouch-based, challenge-response, and gradual ramp-up.

### `class ExtendedDimensionRegistry`

Register custom trust dimensions beyond the base six.

---

## 9. `crdt_merge.e4.resilience.semantic_validator` -- Semantic Validation

### `class SemanticValidator`

Abstract base for semantic validators.

### `class MagnitudeValidator`

Rejects parameter updates that exceed a magnitude threshold.

### `class StatisticalShiftDetector`

Detects distributional shift in parameter updates via two-sample testing.

### `class ParameterRegionGuard`

Enforces per-parameter region constraints (min, max, type).

### `class CompositeSemanticValidator`

Chains multiple validators. All must pass for acceptance.

---

## 10. `crdt_merge.e4.resilience.delta_validation` -- Delta Composition

### `class ReanchorPolicy`

Defines when deltas should be re-anchored to a fresh base state.

### `class DeltaCompositionSpec`

Formal specification of delta composition rules, including associativity
and commutativity constraints.

### `class ParameterTypeEncoder`

Type-aware encoding for heterogeneous parameter types.

### `class CommutativityAdapter`

Adapts non-commutative operations to commutative form via canonical ordering.

---

## 11. `crdt_merge.e4.resilience.performance_spec` -- Performance Specification

### `class SketchConfig`

Configuration for probabilistic sketches (HLL, CMS) used in trust aggregation.

### `class FanoutOptimizer`

Optimizes gossip fanout based on cluster size and network topology.

### `class ProductionDeratingSpec`

Maps benchmark results to production expectations with derating factors.

### `class HardwareRequirements`

Minimum hardware requirements for a given federation size and throughput target.

---

## Remaining Modules (Round 2)

### `formal_spec`

| Class | Description |
|-------|-------------|
| `E4FormalSpec` | Machine-checkable formal specification of E4 invariants |
| `PropertyVerifier` | Runtime verifier for formal properties |
| `SpecBounds` | Quantitative bounds from the formal spec |
| `TemporalProperty` | Temporal logic properties (liveness, safety) |

### `noniid_convergence`

| Class | Description |
|-------|-------------|
| `TrustConvergenceAnalyser` | Convergence analysis under non-IID data distributions |
| `HeterogeneityProfile` | Quantifies data heterogeneity across peers |
| `WarmupSchedule` | Warm-up schedule for trust in heterogeneous settings |

### `trust_inheritance`

| Class | Description |
|-------|-------------|
| `TrustInheritanceManager` | Manages trust inheritance from parent to child nodes |
| `VouchRecord` | Cryptographic vouch from an existing peer for a new peer |
| `DeviceCluster` | Groups devices under a single trust identity |

### `gossip_budget`

| Class / Function | Description |
|-----------------|-------------|
| `HierarchicalAggregator` | Multi-level gossip aggregation to reduce bandwidth |
| `SparseTrustDelta` | Sparse encoding of trust deltas for bandwidth efficiency |
| `AdaptiveGossipRate` | Adjusts gossip frequency based on trust change rate |
| `estimate_bandwidth(peers, dimensions)` | Estimate bandwidth requirements |

### `deterministic_merge`

| Class / Function | Description |
|-----------------|-------------|
| `DeterministicMerge` | Bit-exact merge via compensated summation |
| `deterministic_sum(values)` | Kahan-compensated summation for reproducible results |

### `strategy_drift`

| Class | Description |
|-------|-------------|
| `StrategyDriftDiscriminator` | Detects when merge strategy outcomes drift from expected distributions |
| `DriftVerdict` | Verdict with confidence and recommended action |

### `partition_reconciler`

See section 3 above.

### `schema_adapter`

| Class | Description |
|-------|-------------|
| `SchemaDescriptor` | Describes the schema of a parameter set |
| `SchemaAligner` | Aligns schemas across versions for compatible merge |
| `SchemaRegistry` | Tracks known schemas and their compatibility relationships |
| `ResultNormaliser` | Normalizes merge results to a target schema |

---

*crdt-merge v0.9.5 -- April 2026*
