> Copyright 2026 Ryan Gillespie / Optitransfer. All rights reserved.
> Licensed under the Business Source License 1.1 (BSL-1.1).
> Patent: UK Application No. 2607132.4, GB2608127.3

# Trust-Weighted Agent Memory Synchronisation

Recipes for using the agent bridge and stream bridge to synchronise agent
memory with trust provenance across distributed agents.

---

## Prerequisites

```bash
pip install crdt-merge>=0.9.5
```

---

## 1. Agent Bridge Setup

The `TrustAgentState` wraps agent memory as a CRDT with trust annotations.
Each entry tracks which peer contributed it and at what trust level,
enabling trust-weighted conflict resolution when memories diverge.

```python
from crdt_merge.e4.integration.agent_bridge import (
    TrustAgentState,
    TrustAnnotatedEntry,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice, TrustCircuitBreaker

# Bootstrap the trust lattice
breaker = TrustCircuitBreaker(window_size=100, sigma_threshold=2.0)
lattice = DeltaTrustLattice("agent-0", circuit_breaker=breaker)

# Create agent state bound to the lattice
state = TrustAgentState(
    trust_lattice=lattice,
    trust_weight_context=True,  # enable trust-weighted conflict resolution
)

print(state.size)  # 0
```

---

## 2. Storing and Merging Agent Memories

### Writing entries

Every `put` records the peer's current trust alongside the value.

```python
# Agent-0 stores a memory
entry = state.put(
    key="user_preference",
    value={"theme": "dark", "lang": "en"},
    peer_id="agent-0",
    timestamp=1000.0,
)

print(entry.key)             # user_preference
print(entry.trust_at_write)  # 0.5 (probation -- new peer)
print(entry.peer_id)         # agent-0

# Retrieve it
retrieved = state.get("user_preference")
print(retrieved.value)       # {'theme': 'dark', 'lang': 'en'}
```

### Bulk population

```python
memories = {
    "session_context": {"tokens": 1024, "model": "gpt-4"},
    "tool_results": {"search": "ok", "calc": "ok"},
    "user_feedback": {"rating": 4, "comment": "good"},
}

for key, value in memories.items():
    state.put(key=key, value=value, peer_id="agent-0", timestamp=1001.0)

print(state.size)  # 4
```

---

## 3. Trust-Weighted Conflict Resolution

When two agent states contain conflicting values for the same key, the
entry from the higher-trust peer wins. On equal trust, the later
timestamp wins (LWW fallback).

```python
# Simulate a second agent with different memories
lattice_b = DeltaTrustLattice("agent-1", circuit_breaker=breaker)
state_b = TrustAgentState(
    trust_lattice=lattice_b,
    trust_weight_context=True,
)

state_b.put(
    key="user_preference",
    value={"theme": "light", "lang": "de"},
    peer_id="agent-1",
    timestamp=2000.0,
)

state_b.put(
    key="tool_results",
    value={"search": "failed", "calc": "ok"},
    peer_id="agent-1",
    timestamp=999.0,  # earlier than agent-0
)

# Merge: trust-weighted conflict resolution
merged = state.merge_context(state_b)

# user_preference: both at probation trust (0.5), agent-1 timestamp is later
pref = merged.get("user_preference")
print(pref.value)     # {'theme': 'light', 'lang': 'de'}
print(pref.peer_id)   # agent-1

# tool_results: both at probation trust (0.5), agent-0 timestamp is later
tools = merged.get("tool_results")
print(tools.value)    # {'search': 'ok', 'calc': 'ok'}
print(tools.peer_id)  # agent-0

# session_context: only in agent-0, no conflict
ctx = merged.get("session_context")
print(ctx.peer_id)    # agent-0

print(merged.size)    # 4 (union of all keys)
```

### Ranked entries

Entries sorted by trust at write time, descending -- useful for building
prioritised context windows.

```python
for entry in merged.ranked_entries():
    print(f"  {entry.key}: trust={entry.trust_at_write:.2f} peer={entry.peer_id}")
```

### Peer contribution summary

```python
contribs = merged.peer_contributions()
print(contribs)  # {'agent-0': 3, 'agent-1': 1}
```

---

## 4. Multi-Agent Convergence

With three or more agents, pairwise merge is associative and commutative
(CRDT semantics). The order of merge operations does not affect the final
converged state.

```python
lattice_c = DeltaTrustLattice("agent-2", circuit_breaker=breaker)
state_c = TrustAgentState(trust_lattice=lattice_c, trust_weight_context=True)

state_c.put(key="new_finding", value="important", peer_id="agent-2", timestamp=3000.0)
state_c.put(key="user_preference", value={"theme": "auto"}, peer_id="agent-2", timestamp=3000.0)

# Merge order 1: (a merge b) merge c
m1 = state.merge_context(state_b).merge_context(state_c)

# Merge order 2: a merge (b merge c)
m2 = state.merge_context(state_b.merge_context(state_c))

# Both converge to the same state
assert m1.size == m2.size
for key in ["user_preference", "session_context", "tool_results", "user_feedback", "new_finding"]:
    e1 = m1.get(key)
    e2 = m2.get(key)
    if e1 and e2:
        assert e1.peer_id == e2.peer_id, f"divergence on {key}"

print(f"converged: {m1.size} entries")  # 5
```

### Snapshots

Export and restore agent state for persistence or transport.

```python
snapshot = merged.snapshot()
print(len(snapshot))  # 4

# Restore on another agent
restored = TrustAgentState(trust_lattice=lattice, trust_weight_context=True)
restored.load_snapshot(snapshot)
print(restored.size)  # 4
```

---

## 5. Stream Bridge: Per-Chunk Validation

For streaming scenarios (model weight synchronisation, large context
transfers), the `TrustStreamMerge` validates each chunk independently.
Streams from quarantined peers are rejected outright.

```python
from crdt_merge.e4.integration.stream_bridge import (
    TrustStreamMerge,
    StreamChunk,
    ChunkResult,
)
from crdt_merge.e4.adaptive_verification import AdaptiveVerificationController
from crdt_merge.e4.projection_delta import ProjectionDelta, FrozenDict
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef

verifier = AdaptiveVerificationController(
    trust_lattice=lattice,
    circuit_breaker=breaker,
)

stream = TrustStreamMerge(
    verifier=verifier,
    min_trust=0.1,
)

# Gate: accept or reject the stream before processing chunks
accepted = stream.accept_stream(
    peer_id="agent-1",
    stream_id="sync-001",
    trust_lattice=lattice,
)
print(accepted)  # True (agent-1 trust > 0.1)
```

### Processing chunks

```python
# Build sample chunks
chunks = []
for i in range(3):
    st = SubtreeRef(path=(i,), depth=1, old_hash=f"h{i}", new_hash=f"h{i+1}")
    pco = AggregateProofCarryingOperation.build(
        originator_id="agent-1",
        signing_fn=lambda h: b"\x00" * 64,
        merkle_root="",
        clock_snapshot=b"",
        trust_vector_hash="",
        delta_bounds=[st],
    )
    delta = ProjectionDelta(
        source_id="agent-1",
        source_version=None,
        target_version=None,
        changed_subtrees=(st,),
        insertions=FrozenDict({f"chunk_{i}": f"data_{i}".encode()}),
        updates=FrozenDict(),
        deletions=frozenset(),
        pco=pco,
    )
    chunks.append(StreamChunk(delta=delta, sequence=i, stream_id="sync-001"))

# Validate entire stream (stops early on failure)
results = stream.validate_stream(chunks, trust_lattice=lattice)
for r in results:
    print(f"  seq={r.sequence} accepted={r.accepted} reason={r.reason!r}")

# Inspect stream history
history = stream.stream_results("sync-001")
print(f"total chunks processed: {len(history)}")

# Cleanup
stream.close_stream("sync-001")
print(stream.active_stream_ids())  # []
```

---

## Quick Reference

| Component | Module | Purpose |
|-----------|--------|---------|
| `TrustAgentState` | `integration.agent_bridge` | Agent memory as a CRDT with trust provenance |
| `TrustAnnotatedEntry` | `integration.agent_bridge` | Single memory entry with trust metadata |
| `TrustStreamMerge` | `integration.stream_bridge` | Per-chunk trust validation for streams |
| `StreamChunk` | `integration.stream_bridge` | Wrapper around a delta in a stream |
| `ChunkResult` | `integration.stream_bridge` | Validation outcome for a single chunk |

---

*crdt-merge v0.9.5 -- April 2026*
