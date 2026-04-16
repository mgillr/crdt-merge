> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Integration Guide

> **Version:** 0.9.6 &middot; **Module:** `crdt_merge.e4` &middot; **Author:** Ryan Gillespie / mgillr

How to integrate E4 into existing crdt-merge deployments. Covers zero-downtime migration, configuration, bridge setup, single-node and multi-peer operation, and performance tuning.

**v0.9.6 adds real cryptographic primitives (Ed25519, ML-DSA-65) as opt-in upgrades.** See the [Enabling Real Cryptography](#enabling-real-cryptography) section.

**Related documents:** [API Reference](E4-API-REFERENCE.md) · [Developer Guide](E4-DEVELOPER-GUIDE.md) · [Security Model](E4-SECURITY-MODEL.md) · [Changelog](E4-CHANGELOG.md)

---

## Table of Contents

1. [Integration Overview](#1-integration-overview)
2. [Prerequisites](#2-prerequisites)
3. [Zero-Downtime Migration](#3-zero-downtime-migration)
4. [Configuration](#4-configuration)
5. [Bridge Setup](#5-bridge-setup)
6. [Single-Node Operation](#6-single-node-operation)
7. [Multi-Peer Deployment](#7-multi-peer-deployment)
8. [Performance Tuning](#8-performance-tuning)
9. [Monitoring in Production](#9-monitoring-in-production)
10. [Rollback Procedure](#10-rollback-procedure)

---

## 1. Integration Overview

E4 is designed to activate as a drop-in upgrade to the existing crdt-merge system. The key principle: **zero breaking changes**. Pre-E4 peers continue to operate normally alongside E4 peers via the dual-hash compatibility layer.

### What Changes

| Component | Pre-E4 | E4 |
|-----------|--------|-----|
| Merkle hash | `H(data)` | `H(data ‖ trust ‖ originator)` |
| Vector clock | `(logical_time)` | `(logical_time, trust_score)` |
| CRDT operations | Raw delta | Delta + 128B PCO |
| Trust propagation | Out-of-band | In-band (same delta pipeline) |
| Verification | Uniform | Adaptive (4 tiers) |

### What Doesn't Change

- CRDT merge semantics (still eventually consistent)
- Gossip protocol wire format (trust payload is additive)
- Streaming protocol framing (trust validation is middleware)
- Application-level API (data access unchanged)

---

## 2. Prerequisites

### Minimum Version

- `crdt-merge` ≥ 0.9.4 (the last pre-E4 release)
- Python ≥ 3.10
- hashlib with SHA-256 support (standard library)

### Dependencies

E4 adds **no new external dependencies**. All cryptographic operations use the Python standard library:
- `hashlib` for SHA-256
- `struct` for binary packing
- `dataclasses` for type-safe structures

Ed25519 signing is injected as a callback (`signing_fn`), so you bring your own crypto library (e.g., `cryptography`, `pynacl`, or `ed25519`).

---

## 3. Zero-Downtime Migration

E4 supports a phased migration using the `CompatibilityController`:

### Phase 1: Enable Dual-Hash Mode

Start E4 peers in dual-hash mode. They compute **both** trust-bound and legacy hashes, so pre-E4 peers can verify using the standard hash.

```python
from crdt_merge.e4.integration.config import E4Config, set_config
from crdt_merge.e4.compatibility import (
    CompatibilityController,
    CompatibilityMode,
    CompatHandshake,
    PeerCapability,
)

# Configure dual-hash mode globally
set_config(E4Config(compatibility_mode="dual_hash"))

# Create compatibility controller
compat = CompatibilityController(
    default_mode=CompatibilityMode.DUAL_HASH,
    merkle=merkle,
)
```

In this mode, the `TrustBoundMerkle` tree maintains two hash chains:
- `root_hash` — trust-bound E4 hash
- `root_compat_hash` — standard pre-E4 hash

Pre-E4 peers use `root_compat_hash` and never see the trust-bound hash.

### Phase 2: Handshake and Negotiate

When peers connect, they exchange capability handshakes:

```python
# Outbound: tell the remote peer what we support
outgoing = compat.build_handshake("my-peer")
# CompatHandshake(peer_id="my-peer", capability=PeerCapability.E4_DUAL, version=1)

# Inbound: process remote peer's handshake
incoming = CompatHandshake(
    peer_id="remote-peer",
    capability=PeerCapability.PRE_E4,
)
mode = compat.process_handshake(incoming)
# Returns CompatibilityMode.DUAL_HASH (both sides can verify)
```

The negotiation logic:
- **Pre-E4 ↔ Pre-E4**: LEGACY_ONLY
- **Pre-E4 ↔ E4_DUAL**: DUAL_HASH
- **E4_DUAL ↔ E4_DUAL**: DUAL_HASH
- **E4_DUAL ↔ E4_FULL**: DUAL_HASH
- **E4_FULL ↔ E4_FULL**: E4_ONLY

### Phase 3: Monitor Readiness

```python
# Check which peers are ready for E4-only
ready = compat.peers_ready_for_e4_only()
print(f"Ready for E4-only: {ready}")

# Check mode distribution
distribution = compat.peer_count_by_mode()
print(distribution)
# {CompatibilityMode.E4_ONLY: 5, CompatibilityMode.DUAL_HASH: 3, CompatibilityMode.LEGACY_ONLY: 1}
```

### Phase 4: Upgrade to E4-Only

Once all peers support E4:

```python
# Upgrade individual peers
compat.upgrade_peer("peer-alice")

# Or switch the default
compat.set_default_mode(CompatibilityMode.E4_ONLY)

# Update global config
set_config(E4Config(compatibility_mode="e4_only"))
```

### Hash Computation Per Mode

```python
# Compute hashes respecting the negotiated mode
hashes = compat.compute_hashes(data=b"payload", originator="peer-alice", peer_id="remote-peer")
# Returns dict with "e4" and/or "legacy" keys depending on mode
```

---

## 4. Configuration

### E4Config Reference

All E4 behaviour is configured through a single `E4Config` dataclass:

```python
from crdt_merge.e4.integration.config import E4Config, set_config, get_config, reset_config

cfg = E4Config(
    # Trust thresholds
    probation_trust=0.5,          # Initial trust for new peers
    quarantine_threshold=0.1,     # Below this → rejected (Level 3)
    low_trust_threshold=0.4,      # Below this → full PCO verification
    partial_trust_threshold=0.8,  # Above this → signature only

    # Circuit breaker
    cb_window_size=100,           # Rolling window for velocity
    cb_sigma_threshold=2.0,       # Standard deviations before trip
    cb_cooldown_seconds=30.0,     # Seconds before breaker auto-resets
    cb_min_samples=10,            # Minimum observations before tripping

    # Merkle tree
    merkle_branching_factor=256,  # Children per node (256 → depth 4 for 1B)

    # Compatibility
    compatibility_mode="e4_only", # "e4_only", "dual_hash", "legacy_only"

    # Verification
    verification_level_override=None,  # None = adaptive, 0–3 = forced

    # Performance
    async_queue_limit=1024,       # Max pending async verifications

    # Features
    homeostasis_enabled=True,         # Budget conservation normalization
    gossip_include_trust_deltas=True, # Include trust deltas in gossip
    stream_per_chunk_validation=True, # Validate every stream chunk

    # History
    delta_max_history=64,         # Max deltas per peer in history
)

set_config(cfg)
```

### Global Config Functions

| Function | Description |
|----------|-------------|
| `get_config()` | Get current global config (creates default if not set) |
| `set_config(cfg)` | Replace global config |
| `reset_config()` | Reset to factory defaults |

### Runtime Threshold Inspection

```python
cfg = get_config()
thresholds = cfg.trust_thresholds()
# {'probation': 0.5, 'quarantine': 0.1, 'low': 0.4, 'partial': 0.8}
```

---

## 5. Bridge Setup

E4 integrates with crdt-merge's three communication patterns: gossip, streaming, and agent state.

### 5.1 Gossip Bridge

The `TrustGossipEngine` wraps the existing gossip protocol with trust-enhanced payloads:

```python
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.adaptive_verification import AdaptiveVerificationController

# Create verification controller
verifier = AdaptiveVerificationController(
    trust_lattice=lattice,
    circuit_breaker=lattice._circuit_breaker,
)

# Create gossip engine
gossip = TrustGossipEngine(
    trust_lattice=lattice,
    verifier=verifier,
    state=app_state,
)

# Outbound: prepare sync payload
payload = gossip.prepare_sync(
    deltas=[data_delta_1, data_delta_2],
    include_trust=True,  # Include trust deltas from lattice
)
# payload.data_deltas + payload.trust_deltas sent together

# Inbound: process received payload
accepted_data, accepted_trust = gossip.receive_sync(incoming_payload)
print(f"Accepted {len(accepted_data)} data, {len(accepted_trust)} trust deltas")
```

**Key detail:** Trust deltas ride alongside data deltas in the same gossip round. This is the E4 principle: trust IS data.

### 5.2 Streaming Bridge

The `TrustStreamMerge` adds per-chunk trust validation to streaming connections:

```python
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk

stream_merge = TrustStreamMerge(
    min_trust=0.1,      # Minimum trust to accept a stream
    verifier=verifier,
    state=app_state,
)

# Gate: accept or reject the stream based on peer trust
if stream_merge.accept_stream("peer-alice", "stream-001", lattice):
    # Process chunks
    for chunk in incoming_chunks:
        result = stream_merge.validate_chunk(chunk)
        if result.accepted:
            apply_chunk(chunk)
        else:
            print(f"Rejected chunk {result.sequence}: {result.reason}")

    # Or validate all at once
    results = stream_merge.validate_stream(all_chunks)

# Cleanup
stream_merge.close_stream("stream-001")
```

**Per-chunk validation** (controlled by `E4Config.stream_per_chunk_validation`) verifies each chunk's PCO at the adaptive level determined by the sender's trust. This catches mid-stream trust degradation.

### 5.3 Agent Bridge

The `TrustAgentState` adds trust-weighted conflict resolution to agent state:

```python
from crdt_merge.e4.integration.agent_bridge import TrustAgentState

agent_state = TrustAgentState(
    trust_lattice=lattice,
    trust_weight_context=True,  # Enable trust-weighted conflict resolution
)

# Store data with trust annotation
entry = agent_state.put("model_weights", weights_data, "peer-alice")
print(f"Trust at write: {entry.trust_at_write}")

# Merge with remote state — conflicts resolved by trust weight
merged = agent_state.merge_context(remote_agent_state)

# Inspect
snapshot = merged.snapshot()
ranked = merged.ranked_entries()  # Sorted by trust descending
contributions = merged.peer_contributions()  # {"peer-alice": 3, "peer-bob": 2}
```

**Trust-weighted conflict resolution:** When two peers write to the same key, the entry from the higher-trust peer wins. This prevents low-trust (potentially compromised) peers from overwriting trusted data.

---

## 6. Single-Node Operation

E4 works on a single node for testing, development, or as a local trust oracle:

```python
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.causal_trust_clock import CausalTrustClock

# Minimal setup — stubs used for unbound components
lattice = DeltaTrustLattice("local", initial_peers={"peer-a", "peer-b"})

# Single-node Merkle (no compatibility needed)
merkle = TrustBoundMerkle(branching_factor=256)
clock = CausalTrustClock("local")

# Wire
merkle.bind_trust_lattice(lattice)
clock.bind_trust_lattice(lattice)
lattice.bind_merkle(merkle)
lattice.bind_clock(clock)

# Use normally
merkle.insert_leaf("key1", b"data", "peer-a")
merkle.recompute()
```

In single-node mode:
- All trust starts at probationary (0.5)
- Circuit breaker still functions (monitors local observation rate)
- Homeostasis normalizes across local peer set
- No gossip/streaming bridges needed

---

## 7. Multi-Peer Deployment

### Architecture

Each peer runs the full E4 stack:

```
┌──────────────────────────────────────┐
│              Peer Instance           │
│                                      │
│  TrustBoundMerkle ◄──┐              │
│  CausalTrustClock ◄──┼─ recursive   │
│  DeltaTrustLattice ──►┘  binding    │
│                                      │
│  ┌─────────────────┐                │
│  │ Gossip Bridge   │─── gossip ──►  │
│  │ Stream Bridge   │─── stream ──►  │
│  │ Agent Bridge    │─── state ───►  │
│  └─────────────────┘                │
│                                      │
│  AdaptiveVerificationController      │
│  CompatibilityController             │
│  E4Config                            │
└──────────────────────────────────────┘
```

### Bootstrap Procedure

1. **Configure**: Set `E4Config` with deployment-specific tuning
2. **Create stack**: Instantiate Merkle, Clock, Lattice per peer
3. **Wire dependencies**: Bind all three components
4. **Create bridges**: Gossip, Stream, Agent as needed
5. **Handshake**: Exchange `CompatHandshake` with known peers
6. **Start**: Begin normal operation

```python
def bootstrap_e4_peer(peer_id, known_peers, config=None):
    """Full bootstrap for a multi-peer E4 node."""
    if config:
        set_config(config)

    # Core stack
    merkle = TrustBoundMerkle(
        branching_factor=get_config().merkle_branching_factor,
        compatibility_mode=(get_config().compatibility_mode == "dual_hash"),
    )
    clock = CausalTrustClock(peer_id)
    lattice = DeltaTrustLattice(
        peer_id,
        initial_peers=set(known_peers),
        circuit_breaker=TrustCircuitBreaker(
            window_size=get_config().cb_window_size,
            sigma_threshold=get_config().cb_sigma_threshold,
            cooldown_seconds=get_config().cb_cooldown_seconds,
            min_samples=get_config().cb_min_samples,
        ),
    )

    # Wire
    merkle.bind_trust_lattice(lattice)
    clock.bind_trust_lattice(lattice)
    lattice.bind_merkle(merkle)
    lattice.bind_clock(clock)

    # Verification
    verifier = AdaptiveVerificationController(
        trust_lattice=lattice,
        circuit_breaker=lattice._circuit_breaker,
        async_queue_limit=get_config().async_queue_limit,
    )

    # Compatibility
    compat = CompatibilityController(
        default_mode=CompatibilityMode(get_config().compatibility_mode),
        merkle=merkle,
    )

    # Bridges
    gossip = TrustGossipEngine(trust_lattice=lattice, verifier=verifier)
    stream = TrustStreamMerge(
        min_trust=get_config().quarantine_threshold,
        verifier=verifier,
    )
    agent = TrustAgentState(trust_lattice=lattice)

    return {
        "merkle": merkle,
        "clock": clock,
        "lattice": lattice,
        "verifier": verifier,
        "compat": compat,
        "gossip": gossip,
        "stream": stream,
        "agent": agent,
    }
```

### Peer Discovery

New peers are automatically tracked at probationary trust:

```python
# When a new peer is discovered
trust = lattice.get_trust("new-peer")
# Returns TypedTrustScore.probationary() (0.5 overall, Level 1)
# No explicit registration needed — the lattice creates entries on demand
```

### Trust Convergence

After sufficient evidence exchange, all honest peers converge to the same trust state (CRDT guarantee). The convergence rate depends on:
- Gossip frequency (more rounds → faster convergence)
- Evidence quality (higher-severity evidence converges faster)
- Network connectivity (partitions delay convergence)

---

## 8. Performance Tuning

### Merkle Branching Factor

The branching factor `B` controls tree depth:

| B | Depth for 1M | Depth for 1B | Depth for 1T |
|---|--------------|--------------|--------------|
| 16 | 5 | 7 | 9 |
| 64 | 4 | 5 | 7 |
| 256 (default) | 3 | 4 | 5 |
| 1024 | 2 | 3 | 4 |

Higher B = shallower tree = fewer comparisons in `find_changed_subtrees()`, but wider nodes = more child hash checks per level. The default (256) is optimal for most deployments.

```python
# For very large state spaces (>1T params)
set_config(E4Config(merkle_branching_factor=1024))

# For small deployments (reduce memory)
set_config(E4Config(merkle_branching_factor=64))
```

### Adaptive Verification Cost

| Level | Per-Operation Cost | When Used |
|-------|-------------------|-----------|
| 0 | ~O(1) — 1 signature check | Trusted peers (>0.8 trust) |
| 1 | ~O(1) — signature + 1 hash | Known peers (0.4–0.8) |
| 2 | ~O(k) — full derivation | Low-trust peers (<0.4) |
| 3 | ~O(1) — immediate reject | Quarantined peers (<0.1) |

**In practice**, most operations after initial bootstrap are Level 0–1 (constant cost). Level 2 verification is rare and targeted.

### Async Verification Queue

Level 0–1 verification is optimistic. Full verification happens asynchronously:

```python
# Tune the queue size
set_config(E4Config(async_queue_limit=2048))

# In a background task, drain and verify
verifier = AdaptiveVerificationController(...)
results = verifier.run_async_followup(state, trust_lattice=lattice)
for delta, result in results:
    if not result.accepted:
        logger.error(f"Async verification failed: {delta.source_id}")
```

### Circuit Breaker Tuning

```python
# Stricter: trip faster, cool down slower
set_config(E4Config(
    cb_sigma_threshold=1.5,     # Trip at 1.5σ (default: 2.0)
    cb_cooldown_seconds=60.0,   # Wait 60s before reset (default: 30s)
    cb_min_samples=5,           # Trip with fewer samples (default: 10)
))

# Looser: for high-churn environments
set_config(E4Config(
    cb_sigma_threshold=3.0,
    cb_cooldown_seconds=10.0,
    cb_min_samples=20,
))
```

### Delta History

```python
# Reduce memory for peers with many connections
set_config(E4Config(delta_max_history=32))

# Increase for debugging/auditing
set_config(E4Config(delta_max_history=128))
```

### Disabling Optional Features

```python
# Disable homeostasis (not recommended for production)
set_config(E4Config(homeostasis_enabled=False))

# Disable trust in gossip (reduces gossip payload size)
set_config(E4Config(gossip_include_trust_deltas=False))

# Disable per-chunk stream validation (better throughput)
set_config(E4Config(stream_per_chunk_validation=False))
```

---

## 9. Monitoring in Production

### Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Trust velocity | `TrustCircuitBreaker._velocity` | > 2σ from mean |
| Circuit breaker trips | `circuit_breaker.is_tripped()` | Any trip |
| Quarantined peers | Peers with `verification_level() == 3` | > 10% of peers |
| Async queue depth | `verifier.pending_async_count` | > 80% of `async_queue_limit` |
| Evidence rate | `len(lattice.evidence_log)` over time | Sudden spikes |
| Compatibility mode distribution | `compat.peer_count_by_mode()` | Unexpected LEGACY_ONLY |

### Dashboard Snippet

```python
def e4_health_check(lattice, verifier, compat):
    peers = lattice.known_peers()
    quarantined = sum(
        1 for p in peers
        if lattice.get_trust(p).verification_level() == 3
    )
    low_trust = sum(
        1 for p in peers
        if lattice.get_trust(p).verification_level() == 2
    )

    return {
        "peer_count": len(peers),
        "quarantined": quarantined,
        "low_trust": low_trust,
        "circuit_breaker": "TRIPPED" if lattice._circuit_breaker.is_tripped() else "ok",
        "async_pending": verifier.pending_async_count,
        "evidence_total": len(lattice.evidence_log),
        "mode_distribution": compat.peer_count_by_mode(),
    }
```

---

## 10. Rollback Procedure

If you need to revert E4:

### Step 1: Switch to Legacy Mode

```python
set_config(E4Config(compatibility_mode="legacy_only"))
compat.set_default_mode(CompatibilityMode.LEGACY_ONLY)
```

### Step 2: Stop Trust Propagation

```python
set_config(E4Config(gossip_include_trust_deltas=False))
```

### Step 3: Remove E4 Components

The CRDT layer continues to work without E4. Operations use standard hashes, standard vector clocks, and no PCO verification.

### Step 4: Return to Pre-E4

Since E4 introduces **no breaking changes** (see [Changelog](E4-CHANGELOG.md)), the rollback path is simply disabling the E4 features. Pre-E4 peers never knew about E4 in the first place.

---

## Enabling Real Cryptography

New in v0.9.6. Real Ed25519 signatures and NIST ML-DSA-65 post-quantum signatures are available as opt-in upgrades over the v0.9.5 stub verification.

### Three Verification Tiers

| Tier | When active | Signature backend | Security |
|---|---|---|---|
| Tier 0 | No registry configured (default) | Stub (64-byte length check) | Legacy backward compat |
| Tier 1 | Registry configured, cryptography not installed | HMAC-SHA256 | Symmetric, real integrity |
| Tier 2 | Registry configured + `[crypto]` installed | Ed25519 (real) | Asymmetric, production |
| Tier 3 | Registry + `[security]` installed | Ed25519 + ML-DSA-65 | Post-quantum ready |

### Installation

```bash
pip install crdt-merge[crypto]    # real Ed25519
pip install crdt-merge[security]  # Ed25519 + NIST ML-DSA-65 post-quantum
```

### Minimum Configuration

```python
from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification

class PeerRegistry:
    def __init__(self):
        self._keys = {}

    def register(self, peer_id: str, public_key: bytes):
        self._keys[peer_id] = public_key

    def get_public_key(self, peer_id: str):
        return self._keys.get(peer_id)

registry = PeerRegistry()
# Register peer public keys (Ed25519 raw 32-byte format)
registry.register("alice", alice_public_key_bytes)
registry.register("bob", bob_public_key_bytes)

configure_ed25519_verification(registry)     # enforce PCO signatures
configure_evidence_verification(registry)    # enforce evidence observer auth
```

### Signing Evidence as an Observer

```python
from crdt_merge.e4.proof_evidence import TrustEvidence
from cryptography.hazmat.primitives.asymmetric import ed25519

observer_key = ed25519.Ed25519PrivateKey.generate()

evidence = TrustEvidence.create(
    observer="alice",
    target="eve",
    evidence_type="invalid_delta",
    dimension="integrity",
    amount=0.1,
    proof=proof_bytes,
    observer_signing_fn=lambda payload: observer_key.sign(payload),
)

# Verify with timestamp binding (replay protection)
assert evidence.verify(max_age_seconds=3600, require_observer_auth=True)
```

### Using Real ML-DSA-65 (Post-Quantum)

```python
from crdt_merge.e4.resilience.pq_signatures import Dilithium3Scheme, has_real_pq

if has_real_pq():
    scheme = Dilithium3Scheme()
    private_key, public_key = scheme.generate_keypair()
    signature = scheme.sign(private_key, b"message")
    assert scheme.verify(public_key, b"message", signature)
```

Requires `pip install crdt-merge[security]` and a working liboqs install.

### Migration Path from v0.9.5

1. **Phase 0**: Current v0.9.5 users run without any changes -- v0.9.6 is a drop-in replacement with identical default behavior.
2. **Phase 1**: Install `[crypto]` extra alongside existing code. No configuration change yet. Verify tests still pass.
3. **Phase 2**: Generate Ed25519 keys for each peer. Distribute public keys via existing out-of-band channels.
4. **Phase 3**: Configure the peer registry. Real signature verification activates for all NEW operations.
5. **Phase 4**: Re-sign any long-lived evidence or deltas that must survive the transition. Old stub signatures are automatically rejected once the registry is live.

### Rollback

Call `configure_ed25519_verification(None)` and `configure_evidence_verification(None)`. All verification reverts to v0.9.5 stub behavior immediately. No data migration needed.

---

*For the full API, see [E4-API-REFERENCE.md](E4-API-REFERENCE.md). For security analysis, see [E4-SECURITY-MODEL.md](E4-SECURITY-MODEL.md).*
