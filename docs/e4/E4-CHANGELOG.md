> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Changelog

> **Module:** `crdt_merge.e4` &middot; **Author:** Ryan Gillespie / mgillr

**Related documents:** [API Reference](E4-API-REFERENCE.md) · [Developer Guide](E4-DEVELOPER-GUIDE.md) · [Integration Guide](E4-INTEGRATION-GUIDE.md) · [Security Model](E4-SECURITY-MODEL.md)

---

## [0.9.5.2] — Round 2 Resilience

### Added
- **10 new resilience modules** addressing Round 2 expert review findings
- `resilience/formal_spec.py` — TLA+ specification generator and bounded model checker for convergence properties
- `resilience/longcon_sybil.py` — Long-con (patient) Sybil detection via three statistical correlation signals
- `resilience/pq_signatures.py` — Post-quantum signature abstraction layer with HMAC, Dilithium-lite, and hybrid schemes
- `resilience/noniid_convergence.py` — Non-IID convergence analysis with adaptive trust warm-up scheduling
- `resilience/trust_inheritance.py` — Three-tier trust inheritance: institutional vouching, device clusters, individual evidence
- `resilience/gossip_budget.py` — Hierarchical gossip budget management for O(√N) trust gossip at scale
- `resilience/deterministic_merge.py` — IEEE 754 deterministic merge arithmetic (sorted Kahan summation)
- `resilience/strategy_drift.py` — Strategy drift discriminator for multi-agent RL environments
- `resilience/partition_reconciler.py` — Post-partition trust reconciliation with graduated normalisation
- `resilience/schema_adapter.py` — Schema heterogeneity adapter for cross-domain delta merging
- 3 new resilience subsystems: post-quantum signature agility, long-con Sybil detection, formal TLA+ verification
- Updated architecture documentation with Round 2 Resilience Subsystem addendum
- Updated API reference, developer guide, and security model documentation

### Changed
- Total resilience module count: 9 → 19

### Fixed
- None — all additions are non-breaking

---

## [0.9.5.1] — Peer Review Resilience

### Added
- **9 resilience modules** (2,959 lines) addressing all 24 peer review concerns
- `resilience/domain_hash.py` — Domain-separated hashing, cross-component isolation
- `resilience/key_manager.py` — Key lifecycle: rotation, revocation, CRDT-mergeable registry
- `resilience/epoch_protocol.py` — Epoch coordination, evidence GC, partition recovery
- `resilience/convergence_monitor.py` — Real-time convergence monitoring with alerting
- `resilience/trust_resilience.py` — Differential privacy, cold-start bootstrap, extensible dimensions
- `resilience/semantic_validator.py` — Magnitude/shift/region validation for delta payloads
- `resilience/delta_resilience.py` — Re-anchoring, formal composition spec, type-aware encoding, commutativity adapter
- `resilience/performance_spec.py` — Sketch config, fan-out optimization, production derating, hardware requirements
- **124 new tests** across 8 test files (all passing)
- Non-breaking hooks wired into 4 existing modules (enable_*/disable_* class methods)
- Updated security model documentation with full resilience details
- Added 3 new resilience subsystems (domain-separated hashing, epoch GC, semantic validation)
- New architecture diagram (Figure 10): Resilience subsystem architecture

### Changed
- Total test count: 1,441 → 1,565 (including resilience)
- HMAC signing in KeyManager uses public key consistently (portable verification)

### Fixed
- None — all additions are non-breaking


## Version 0.9.5 — E4 Recursive Trust-Delta Architecture

**Release date:** April 2026
**Branch:** `feature/0.9.5-e4-recursive-entanglement`
**Tag:** `v0.9.5-e4`

### Breaking Changes

**NONE.**

E4 is a fully additive upgrade. All existing crdt-merge 0.9.4 code, protocols, and deployments continue to work without modification. The dual-hash compatibility layer ensures zero-downtime migration. See [Integration Guide §3](E4-INTEGRATION-GUIDE.md#3-zero-downtime-migration).

---

### 🆕 New Modules (15 total)

#### Core Trust and Evidence (4 modules)

| Module | Description | Ref |
|--------|-------------|-----|
| `crdt_merge.e4.typed_trust` | Multi-dimensional trust scores with GCounter evidence per observer. Six dimensions: integrity, causality, consistency, gossip, model, context. Includes `TypedTrustScore`, `TrustHomeostasis`, and all trust constants. | §820 |
| `crdt_merge.e4.proof_evidence` | Proof-carrying trust evidence. Five evidence types with cryptographic proofs: equivocation, merkle_divergence, clock_regression, invalid_delta, trust_manipulation. Includes `TrustEvidence` and proof packing helpers. | §830 |
| `crdt_merge.e4.pco` | Aggregate proof-carrying operations. 128-byte wire format covering integrity, causality, trust, and minimality in a single hash + signature. Includes `AggregateProofCarryingOperation` and `SubtreeRef`. | §880–886 |
| `crdt_merge.e4.projection_delta` | Sparse projection delta encoding with O(log_B n) changed-subtree identification. Includes `ProjectionDelta`, `ProjectionDeltaManager`, and `FrozenDict`. | §810–815 |

#### Recursive Binding (3 modules)

| Module | Description | Ref |
|--------|-------------|-----|
| `crdt_merge.e4.delta_trust_lattice` | The E4 recursive binding. Trust IS data — changes propagate as deltas through the same pipeline. Includes `DeltaTrustLattice`, `TrustCircuitBreaker`, `CircuitBreakerTripped`, and protocol interfaces. | §840–843 |
| `crdt_merge.e4.trust_bound_merkle` | Trust-bound high-arity Merkle tree (E1 entanglement). Hashes incorporate trust context. Branching factor B=256 gives depth 4 for 1B parameters. Includes `TrustBoundMerkle` and `MerkleNode`. | §850–855 |
| `crdt_merge.e4.causal_trust_clock` | Causal trust clock (E2 entanglement). Vector clock with (time, trust) pairs. Trust-weighted comparison prevents low-trust causal domination. Includes `CausalTrustClock`. | §860–863 |

#### Verification and Compatibility (2 modules)

| Module | Description | Ref |
|--------|-------------|-----|
| `crdt_merge.e4.adaptive_verification` | Four-tier adaptive immune verification. Trusted peers get O(1) checks, untrusted peers get O(k) full verification. Includes `AdaptiveVerificationController`, `VerificationResult`, `VerificationOutcome`. | §895 |
| `crdt_merge.e4.compatibility` | Dual-hash compatibility mode for zero-downtime migration. Pre-E4 peers continue using standard hashes alongside E4 peers. Includes `CompatibilityController`, `CompatibilityMode`, `PeerCapability`, `CompatHandshake`. | §855 |

#### Integration (4 modules)

| Module | Description |
|--------|-------------|
| `crdt_merge.e4.integration.config` | Runtime configuration via `E4Config` dataclass. Trust thresholds, circuit breaker tuning, Merkle settings, feature flags. Module-level `get_config()` / `set_config()` / `reset_config()`. |
| `crdt_merge.e4.integration.gossip_bridge` | Trust-enhanced gossip protocol. Unified data + trust delta gossip with adaptive verification. Includes `TrustGossipEngine` and `TrustGossipPayload`. |
| `crdt_merge.e4.integration.stream_bridge` | Trust-validated streaming merge with per-chunk verification. Stream gating by peer trust. Includes `TrustStreamMerge`, `StreamChunk`, `ChunkResult`. |
| `crdt_merge.e4.integration.agent_bridge` | Trust-weighted agent state management. Conflict resolution by trust weight. Includes `TrustAgentState` and `TrustAnnotatedEntry`. |

#### Package (2 files)

| File | Description |
|------|-------------|
| `crdt_merge.e4.__init__` | Package init with `__all__` re-exporting core public API |
| `crdt_merge.e4.integration.__init__` | Integration sub-package init |

---

### New Capabilities

#### Recursive Trust-Delta Architecture
- Trust changes propagate as `ProjectionDelta`s through the same two-layer pipeline as application data
- Four entanglement points (E1–E4) create recursive dependencies between trust, integrity, causality, and verification
- Self-healing: misbehaviour generates evidence → trust decreases → verification increases → further misbehaviour caught faster

#### Multi-Dimensional Trust
- Six trust dimensions: integrity, causality, consistency, gossip, model, context
- GCounter-based evidence tracking per observer per dimension
- Trust is a CRDT: commutative, associative, idempotent merge

#### Proof-Carrying Evidence
- Five evidence types with cryptographic proofs
- Any honest node can verify evidence independently (Byzantine-fault-tolerant)
- Proof helpers: `pack_attestation_pair`, `pack_merkle_path`, `pack_clock_pair`, `pack_delta_proof`, `pack_state_pair`

#### Aggregate PCO (128-byte proofs)
- Single proof covers integrity, causality, trust, and minimality
- Constant overhead per operation (128 bytes) regardless of complexity
- Four verification levels with adaptive cost

#### Trust-Bound Merkle Tree
- High-arity design: B=256 branching factor, depth 4 for 1B parameters
- Trust-dependent hashes at leaf and intermediate levels
- Dual-hash mode for backward compatibility

#### Causal Trust Clock
- Vector clock entries carry (time, trust) pairs
- Trust-weighted comparison: `trust_override` outcome
- CRDT merge: element-wise max preserving join-semilattice

#### Adaptive Immune Verification
- Four-tier gating: O(1) for trusted, O(k) for untrusted, reject for quarantined
- Async verification queue for optimistic acceptance
- Self-adjusting: trust changes drive verification level changes

#### Circuit Breaker
- Trust velocity monitoring with configurable σ threshold
- Auto-reset after cooldown period
- Protects against coordinated swarm attacks

#### Homeostatic Budget Conservation
- Total trust per dimension conserved: `sum(trust_d) == peer_count`
- Prevents trust inflation/deflation attacks
- Preserves rank ordering (relative trust unchanged)

#### Zero-Downtime Migration
- `CompatibilityController` negotiates per-peer modes
- `CompatHandshake` protocol for capability exchange
- Three modes: E4_ONLY, DUAL_HASH, LEGACY_ONLY
- Full rollback support without data loss

---

### Migration Notes from 0.9.4

#### Recommended Migration Path

1. **Upgrade to 0.9.5** — no code changes required
2. **Enable E4 in dual-hash mode** — `E4Config(compatibility_mode="dual_hash")`
3. **Monitor** — check `compat.peer_count_by_mode()` and trust health
4. **Upgrade all peers** — ensure all peers support E4
5. **Switch to E4-only** — `E4Config(compatibility_mode="e4_only")`

#### Configuration Defaults

All defaults are production-safe:
- Probation trust: 0.5
- Circuit breaker: 2σ threshold, 30s cooldown
- Merkle branching factor: 256
- Homeostasis: enabled
- Compatibility: e4_only (set to "dual_hash" during migration)

#### Import Changes

E4 is a new subpackage — no existing imports change:

```python
# Existing imports unchanged
from crdt_merge import ...  # still works

# New E4 imports (additive)
from crdt_merge.e4 import TypedTrustScore, TrustEvidence, ProjectionDelta
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.integration.config import E4Config, set_config
```

---

### New Dependencies

**NONE.**

E4 uses only the Python standard library:
- `hashlib` (SHA-256)
- `struct` (binary packing)
- `dataclasses`
- `collections` (deque)
- `typing`
- `time` (monotonic clock)

Ed25519 signing is injected as a callback — bring your own crypto library.

---

### Test Coverage

- 8 test modules covering all 15 E4 modules
- Integration tests for full E4 stack wiring
- Compatibility tests for all three modes
- Convergence tests for CRDT merge properties
- Circuit breaker trip/reset tests
- Evidence verification tests for all five types
- Gossip, streaming, and agent bridge tests

---

### Documentation

Five new documentation files (this release):

| Document | Description |
|----------|-------------|
| [E4-API-REFERENCE.md](E4-API-REFERENCE.md) | Comprehensive reference for every public class, method, and constant |
| [E4-DEVELOPER-GUIDE.md](E4-DEVELOPER-GUIDE.md) | Getting started, core concepts, patterns, anti-patterns, debugging |
| [E4-INTEGRATION-GUIDE.md](E4-INTEGRATION-GUIDE.md) | Zero-downtime migration, configuration, bridge setup, performance |
| [E4-SECURITY-MODEL.md](E4-SECURITY-MODEL.md) | Threat model, entanglement analysis, Sybil resistance, proofs |
| [E4-CHANGELOG.md](E4-CHANGELOG.md) | This file |

Master architecture document: [E4-MASTER-ARCHITECTURE.md](../E4-MASTER-ARCHITECTURE.md)

---

### Future Work (Post-0.9.5)

- Key rotation protocol (new identity not required)
- Differential privacy for trust observations
- GPU-accelerated Merkle tree operations
- Formal TLA+ specification of convergence
- Trust recovery protocol (controlled trust increase)
- Hierarchical trust delegation

---

*For the full API, see [E4-API-REFERENCE.md](E4-API-REFERENCE.md). For deployment instructions, see [E4-INTEGRATION-GUIDE.md](E4-INTEGRATION-GUIDE.md).*
