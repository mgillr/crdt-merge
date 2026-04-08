> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# E4 Integration Bridges -- API Reference

Integration bridges wire the E4 subsystem into the broader crdt-merge
framework. For core E4 modules, see [e4.md](e4.md). For the resilience
subsystem, see [e4_resilience.md](e4_resilience.md).

---

## Quick Import

```python
from crdt_merge.e4.integration import (
    initialize_defaults,
    get_trust_lattice,
    get_circuit_breaker,
    get_verifier,
    get_gossip_engine,
    get_stream_merge,
    get_agent_state,
    get_compat_controller,
    is_initialized,
    reset,
)
from crdt_merge.e4.integration.config import E4Config, get_config, set_config
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk, ChunkResult
from crdt_merge.e4.integration.agent_bridge import TrustAgentState, TrustAnnotatedEntry
```

---

## 1. `crdt_merge.e4.integration`

System-wide bootstrap and component registry. The `initialize_defaults()` function
is the single entry point called by `crdt_merge/__init__.py` on import.

### `initialize_defaults(config=None)`

```python
def initialize_defaults(config: Optional[E4Config] = None) -> None
```

Bootstrap the E4 subsystem with default component instances. Idempotent --
repeated calls are no-ops unless `config` differs from the current active
configuration. Constructs and registers:

- `DeltaTrustLattice` (peer_id `"local"`)
- `TrustCircuitBreaker`
- `TrustHomeostasis` (if `config.homeostasis_enabled`)
- `AdaptiveVerificationController`
- `CompatibilityController`
- `TrustGossipEngine`
- `TrustStreamMerge`
- `TrustAgentState`

### Accessors

| Function | Returns | Description |
|----------|---------|-------------|
| `get_trust_lattice()` | `DeltaTrustLattice` | Default trust lattice instance |
| `get_circuit_breaker()` | `TrustCircuitBreaker` | Default circuit breaker |
| `get_verifier()` | `AdaptiveVerificationController` | Default verification controller |
| `get_gossip_engine()` | `TrustGossipEngine` | Default gossip engine |
| `get_stream_merge()` | `TrustStreamMerge` | Default stream merge |
| `get_agent_state()` | `TrustAgentState` | Default agent state bridge |
| `get_compat_controller()` | `CompatibilityController` | Default compatibility controller |
| `is_initialized()` | `bool` | Whether `initialize_defaults` has run |
| `reset()` | `None` | Tear down default instances (for tests) |

All accessors auto-call `initialize_defaults()` if not yet initialized.

---

## 2. `crdt_merge.e4.integration.config`

### `class E4Config`

```python
@dataclass
class E4Config:
    # Trust thresholds (ref 896-899)
    probation_trust: float = 0.5
    quarantine_threshold: float = 0.1
    low_trust_threshold: float = 0.4
    partial_trust_threshold: float = 0.8

    # Circuit breaker (ref 829)
    cb_window_size: int = 100
    cb_sigma_threshold: float = 2.0
    cb_cooldown_seconds: float = 30.0
    cb_min_samples: int = 10

    # Merkle tree (ref 850)
    merkle_branching_factor: int = 256

    # Compatibility (ref 855)
    compatibility_mode: str = "e4_only"

    # Adaptive verification (ref 895)
    verification_level_override: Optional[int] = None
    async_queue_limit: int = 1024

    # Homeostasis (ref 828)
    homeostasis_enabled: bool = True
    homeostasis_target_budget: Optional[float] = None

    # Delta management
    delta_max_history: int = 64

    # Gossip bridge
    gossip_include_trust_deltas: bool = True

    # Stream bridge
    stream_per_chunk_validation: bool = True
    stream_min_trust: float = 0.1

    # Agent bridge
    agent_trust_weight_context: bool = True
```

Unified runtime configuration for the E4 subsystem. Every field has a
sensible default matching the specification.

| Method | Returns | Description |
|--------|---------|-------------|
| `trust_thresholds()` | `dict` | `{"probation": ..., "quarantine": ..., "low": ..., "partial": ...}` |

### Module Functions

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_config()` | -- | `E4Config` | Current global config (creates default if needed) |
| `set_config(config)` | `config: E4Config` | `None` | Replace the global config |
| `reset_config()` | -- | `None` | Reset to factory defaults |

---

## 3. `crdt_merge.e4.integration.gossip_bridge`

Unified data + trust gossip engine (ref 1010-1020). Piggybacks trust
deltas alongside data deltas in sync payloads.

### `class TrustGossipPayload`

```python
@dataclass
class TrustGossipPayload:
    data_deltas: List[ProjectionDelta]
    trust_deltas: List[ProjectionDelta]
    peer_id: str = ""
```

Wire payload bundling data and trust deltas.

#### Class Methods

| Method | Parameters | Description |
|--------|-----------|-------------|
| `TrustGossipPayload.enable_convergence_monitoring(peer_count=100, **kwargs)` | `peer_count: int` | Enable convergence time monitoring via `resilience.convergence_monitor` |
| `TrustGossipPayload.disable_convergence_monitoring()` | -- | Disable convergence monitoring |

### `class TrustGossipEngine`

```python
class TrustGossipEngine:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
    ) -> None
```

Gossip engine that propagates both data and trust deltas.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `prepare_sync(data_deltas, *, include_trust=True)` | `data_deltas: Sequence[ProjectionDelta]` | `TrustGossipPayload` | Build a sync payload. When `include_trust=True`, drains pending trust deltas from the lattice. |
| `receive_sync(payload)` | `payload: TrustGossipPayload` | `Tuple[List[ProjectionDelta], List[ProjectionDelta]]` | Process incoming payload. Returns `(accepted_data, accepted_trust)`. |
| `drain_outbound()` | -- | `List[TrustGossipPayload]` | Drain prepared outbound payloads |
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Late-bind trust lattice |
| `bind_verifier(verifier)` | `verifier: AdaptiveVerificationController` | `None` | Late-bind verifier |
| `bind_state(state)` | `state: object` | `None` | Late-bind application state |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `pending_outbound` | `int` | Number of prepared but un-drained payloads |

---

## 4. `crdt_merge.e4.integration.stream_bridge`

Trust-validated streaming merge (ref 1155-1156). Per-chunk PCO validation
with trust-gated stream acceptance.

### `class StreamChunk`

```python
@dataclass
class StreamChunk:
    delta: ProjectionDelta
    sequence: int              # monotonic within stream
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
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
        *,
        min_trust: float = 0.1,
    ) -> None
```

Streaming merge with per-chunk trust validation. Streams from quarantined
peers (trust < `min_trust`) are rejected outright.

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `accept_stream(peer_id, stream_id, trust_lattice)` | `peer_id: str, stream_id: str, trust_lattice: object` | `bool` | Gate: accept or reject a stream based on peer trust |
| `validate_chunk(chunk, trust_lattice=None)` | `chunk: StreamChunk, trust_lattice: object` | `ChunkResult` | Validate a single chunk via adaptive verification |
| `validate_stream(chunks, trust_lattice=None)` | `chunks: Sequence[StreamChunk], trust_lattice: object` | `List[ChunkResult]` | Validate all chunks in order. Stops early on failure. |
| `stream_results(stream_id)` | `stream_id: str` | `List[ChunkResult]` | Validation history for a stream |
| `active_stream_ids()` | -- | `List[str]` | Currently tracked streams |
| `close_stream(stream_id)` | `stream_id: str` | `None` | Remove stream from tracking |
| `bind_verifier(verifier)` | `verifier: AdaptiveVerificationController` | `None` | Late-bind verifier |
| `bind_state(state)` | `state: object` | `None` | Late-bind application state |

---

## 5. `crdt_merge.e4.integration.agent_bridge`

Trust-aware agent state bridge (ref 1157). Agent memory entries are CRDTs
with trust annotations.

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

Single memory entry with trust provenance.

### `class TrustAgentState`

```python
class TrustAgentState:
    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        *,
        trust_weight_context: bool = True,
    ) -> None
```

Agent memory as a CRDT with trust provenance. When `trust_weight_context`
is enabled, conflicts resolve in favour of the higher-trust peer; on equal
trust, the later timestamp wins (LWW fallback).

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `get(key)` | `key: str` | `Optional[TrustAnnotatedEntry]` | Retrieve an entry |
| `put(key, value, peer_id, *, timestamp=0.0)` | `key: str, value: Any, peer_id: str` | `TrustAnnotatedEntry` | Write an entry. Trust is looked up from the lattice. Conflicts resolved automatically. |
| `delete(key)` | `key: str` | `Optional[TrustAnnotatedEntry]` | Remove an entry |
| `merge_context(other)` | `other: TrustAgentState` | `TrustAgentState` | CRDT merge of two agent states |
| `snapshot()` | -- | `Dict[str, TrustAnnotatedEntry]` | Export all entries |
| `load_snapshot(entries)` | `entries: Dict[str, TrustAnnotatedEntry]` | `None` | Restore from a snapshot |
| `ranked_entries()` | -- | `List[TrustAnnotatedEntry]` | Entries sorted by trust at write time (descending) |
| `peer_contributions()` | -- | `Dict[str, int]` | Count of entries per peer |
| `bind_trust_lattice(lattice)` | `lattice: DeltaTrustLattice` | `None` | Late-bind trust lattice |

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `size` | `int` | Number of entries |

---

*crdt-merge v0.9.5 -- April 2026*
