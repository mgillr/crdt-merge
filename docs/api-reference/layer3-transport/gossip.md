# gossip

> Layer 3 — Sync & Transport
> Source: `crdt_merge/gossip.py`  
> LOC: 394 (AST-verified)

## Overview
Gossip protocol state management for distributed CRDT synchronization.

This module provides the STATE MACHINE for gossip-based sync.
You provide the transport (HTTP, TCP, UDP, etc.).
crdt-merge provides the merge logic.

Key design: NO networking. NO scheduling. Pure state machine.

The GossipState class manages a key-value store where each entry is tracked
with a VectorClock for causal ordering. Anti-entropy methods enable efficient
synchronisation by comparing compact digests rather than full state.

All CRDT types implement:
  - merge()    — returns a NEW instance (never mutates)
  - to_dict()  — serialise to a plain dict
  - from_dict() — deserialise from a plain dict

CRDT convergence guarantees:
  - Commutative:  merge(A, B) == merge(B, A)
  - Associative:  merge(merge(A, B), C) == merge(A, merge(B, C))
  - Idempotent:   merge(A, A) == A

Usage:
    from crdt_merge.gossip import GossipState, GossipEntry, anti_entropy

    state = GossipState("node-1")
    state.update("user:42", {"name": "Alice"})
    state.update("user:43", {"name": "Bob"})

    # Anti-entropy: compare digests to find what needs syncing
    local_digest = state.digest()
    push_keys, pull_keys = state.anti_entropy_push_pull(remote_digest)

    # Apply remote entries received over the wire
    count = state.apply_entries(remote_entries)

    # Full merge of two complete states
    merged = state_a.merge(state_b)

## Classes

### `GossipEntry`
`@dataclass`  


A single entry in the gossip key-value store.

Each entry tracks:
  - key:       the unique identifier for this datum
  - value:     the application payload (any JSON-serialisable value)
  - clock:     a VectorClock recording the causal history of this entry
  - tombstone: whether the entry has been logically deleted

Tombstoned entries are retained so that deletes propagate through
the gossip protocol — they will eventually be reaped by compaction.

#### Methods

##### `to_dict(self) -> dict`

Serialize to a plain dict suitable for JSON encoding.

##### `@classmethod from_dict(cls, d: dict) -> GossipEntry`
Decorators: `@classmethod`

Deserialize from a plain dict.

Args:
    d: A dict previously produced by ``to_dict()``.

Returns:
    A new GossipEntry instance.

##### `__repr__(self) -> str`

---

### `GossipState`

Gossip protocol state machine for distributed CRDT synchronization.

Manages a replicated key-value store where every mutation is tracked
by a VectorClock. Provides anti-entropy methods to efficiently detect
and resolve differences between replicas.

Parameters:
    node_id: Unique identifier for this node in the cluster.
    fanout:  Number of peers to contact per gossip round (default 3).

Example::

    state = GossipState("node-1", fanout=2)
    state.update("sensor:temp", 22.5)
    digest = state.digest()

#### Constructor
```python
__init__(self, node_id: str, fanout: int = 3) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | `str` | `—` | — |
| `fanout` | `int` | `3` | — |

#### Properties

##### `node_id: str`
The unique identifier of this node.

##### `fanout: int`
The gossip fanout (number of peers per round).

##### `size: int`
Count of live (non-tombstoned) entries.

##### `clock: VectorClock`
The node-level vector clock reflecting all observed events.

#### Methods

##### `update(self, key: str, value: Any, clock: Optional[VectorClock] = None) -> VectorClock`

Insert or update a key-value pair.

Increments this node's logical clock.  If *clock* is provided
(e.g. when replaying a remote event), it is merged with the
current clock to preserve causality.

Args:
    key:   The key to upsert.
    value: The new value.
    clock: Optional external clock to merge in.

Returns:
    The updated node-level VectorClock.

##### `delete(self, key: str) -> VectorClock`

Logically delete a key by tombstoning it.

The entry is retained with ``tombstone=True`` so the deletion
propagates to other nodes during anti-entropy sync.

Args:
    key: The key to delete.

Returns:
    The updated node-level VectorClock.

##### `get(self, key: str) -> Optional[Any]`

Get the live value for *key*, or ``None`` if missing / tombstoned.

##### `get_entry(self, key: str) -> Optional[GossipEntry]`

Get the raw GossipEntry for *key*, including tombstones.

##### `get_entries(self, keys: Set[str]) -> List[GossipEntry]`

Get raw GossipEntry objects for a set of keys.

Keys not present in the store are silently skipped.

Args:
    keys: The set of keys to retrieve.

Returns:
    A list of GossipEntry objects (order not guaranteed).

##### `digest(self) -> Dict[str, str]`

Build a compact digest of the current state.

Returns a dict mapping each key to a short hex hash derived from
the entry's value, clock, and tombstone flag.  Two nodes with the
same digest for a key are in agreement; different hashes indicate
a difference that anti-entropy should resolve.

Returns:
    ``{key: hex_hash}`` for every entry (including tombstones).

##### `anti_entropy_push(self, remote_digest: Dict[str, str]) -> Set[str]`

Determine which keys this node should *push* to the remote.

A key should be pushed when the remote is either missing it entirely
or has a different hash (indicating a stale or divergent version).

Args:
    remote_digest: The remote node's digest.

Returns:
    Set of keys that need to be pushed to the remote.

##### `anti_entropy_pull(self, remote_digest: Dict[str, str]) -> Set[str]`

Determine which keys this node should *pull* from the remote.

A key should be pulled when we are missing it or our hash differs
from the remote's.

Args:
    remote_digest: The remote node's digest.

Returns:
    Set of keys to request from the remote.

##### `anti_entropy_push_pull(self, remote_digest: Dict[str, str]) -> Tuple[Set[str], Set[str]]`

Bidirectional anti-entropy: determine push and pull sets.

This is equivalent to calling ``anti_entropy_push`` and
``anti_entropy_pull`` but may be more convenient.

Args:
    remote_digest: The remote node's digest.

Returns:
    A tuple ``(keys_to_push, keys_to_pull)``.

##### `apply_entries(self, entries: List[GossipEntry]) -> int`

Apply a batch of entries received from a remote node.

Each entry is accepted only if its clock dominates or wins the
concurrent tiebreak against the locally held version.  The node
clock is advanced to incorporate the causal history of every
accepted entry.

Args:
    entries: Remote entries to apply.

Returns:
    Number of entries that caused a local update.

##### `_should_update(self, old_clock: VectorClock, new_clock: VectorClock) -> bool`

Determine whether *new_clock* should replace *old_clock*.

The new clock wins if it is strictly AFTER the old clock.
In the CONCURRENT case a deterministic tiebreak is applied so
all nodes converge to the same value regardless of message order.

The tiebreak compares the sorted string representation of the
clock dicts — this is arbitrary but deterministic.

Returns:
    ``True`` if the entry with *new_clock* should replace the one
    with *old_clock*.

##### `@staticmethod _deterministic_entry_key(entry: GossipEntry) -> tuple`
Decorators: `@staticmethod`

Build an order-independent comparison key for deterministic tiebreaks.

Used by ``merge()`` to guarantee commutativity and associativity
when vector clocks are concurrent or equal.  The key is a tuple
that can be compared with ``>=`` to pick a stable winner.

##### `merge(self, other: GossipState) -> GossipState`

Merge two GossipState instances. Returns a NEW instance.

The merged state contains the union of all keys.  Entry clocks
are always merged (element-wise max).  Value selection uses a
deterministic content-based comparison so that the result is
independent of argument order and grouping.

Satisfies: commutative, associative, idempotent.

Args:
    other: The other GossipState to merge with.

Returns:
    A new GossipState representing the merged state.

##### `to_dict(self) -> dict`

Serialize the full state to a plain dict.

##### `@classmethod from_dict(cls, d: dict) -> GossipState`
Decorators: `@classmethod`

Deserialize from a plain dict.

Args:
    d: A dict previously produced by ``to_dict()``.

Returns:
    A new GossipState instance.

##### `__eq__(self, other: object) -> bool`

##### `__repr__(self) -> str`

---

## Functions

### `anti_entropy(local_digest: Dict[str, str], remote_digest: Dict[str, str]) -> Dict[str, list]`

Compare two digests and classify keys by sync action needed.

This is a pure function operating on digest dicts — it does not need
access to any GossipState.  Useful when you want anti-entropy logic
in a stateless layer (e.g. a gateway or coordinator).

Args:
    local_digest:  ``{key: hash}`` from the local node.
    remote_digest: ``{key: hash}`` from the remote node.

Returns:
    A dict with three lists::

        {
            "missing_local":  [keys in remote but not local],
            "missing_remote": [keys in local but not remote],
            "different":      [keys in both with different hashes],
        }

| Parameter | Type | Default |
|-----------|------|---------|
| `local_digest` | `Dict[str, str]` | `—` |
| `remote_digest` | `Dict[str, str]` | `—` |

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: None
- No circular dependencies

### RREA Findings
- Entropy profile: zero (no symbols in reachability graph — gossip is a leaf module)
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: No chokepoints — pure state machine with no upstream dependents in the package graph

### Code Quality (Team 2)
- Docstring coverage: 85.7%
- `__all__` defined: no — **public API is ambiguous**
- Code smells: 1 assertion found (acceptable for invariant checking)
- Missing docstrings: `__repr__` (×2), `__init__`, `__eq__`

---
Approved by: Auditor (Team 1), Cross-validated by Teams 2–4  
Last reviewed: 2026-03-31
