# Gossip Protocol

Anti-entropy gossip state tracking for CRDT convergence.

## Quick Example

```python
from crdt_merge.gossip import GossipState, anti_entropy
state = GossipState(node_id="node-1")
state.update("key", value, clock)
```

---

## API Reference

## `crdt_merge.gossip`

> Gossip protocol state management for distributed CRDT synchronization.

**Module:** `crdt_merge.gossip`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `GossipEntry(key: 'str', value: 'Any', clock: 'VectorClock', tombstone: 'bool' = False) -> None`

A single entry in the gossip key-value store.

**Methods:**

- `from_dict(d: 'dict') -> 'GossipEntry'` — Deserialize from a plain dict.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict suitable for JSON encoding.

#### `GossipState(node_id: 'str', fanout: 'int' = 3) -> 'None'`

Gossip protocol state machine for distributed CRDT synchronization.

**Properties:**

- `clock` — The node-level vector clock reflecting all observed events.
- `fanout` — The gossip fanout (number of peers per round).
- `node_id` — The unique identifier of this node.
- `size` — Count of live (non-tombstoned) entries.

**Methods:**

- `anti_entropy_pull(self, remote_digest: 'Dict[str, str]') -> 'Set[str]'` — Determine which keys this node should *pull* from the remote.
- `anti_entropy_push(self, remote_digest: 'Dict[str, str]') -> 'Set[str]'` — Determine which keys this node should *push* to the remote.
- `anti_entropy_push_pull(self, remote_digest: 'Dict[str, str]') -> 'Tuple[Set[str], Set[str]]'` — Bidirectional anti-entropy: determine push and pull sets.
- `apply_entries(self, entries: 'List[GossipEntry]') -> 'int'` — Apply a batch of entries received from a remote node.
- `delete(self, key: 'str') -> 'VectorClock'` — Logically delete a key by tombstoning it.
- `digest(self) -> 'Dict[str, str]'` — Build a compact digest of the current state.
- `from_dict(d: 'dict') -> 'GossipState'` — Deserialize from a plain dict.
- `get(self, key: 'str') -> 'Optional[Any]'` — Get the live value for *key*, or ``None`` if missing / tombstoned.
- `get_entries(self, keys: 'Set[str]') -> 'List[GossipEntry]'` — Get raw GossipEntry objects for a set of keys.
- `get_entry(self, key: 'str') -> 'Optional[GossipEntry]'` — Get the raw GossipEntry for *key*, including tombstones.
- `merge(self, other: 'GossipState') -> 'GossipState'` — Merge two GossipState instances. Returns a NEW instance.
- `to_dict(self) -> 'dict'` — Serialize the full state to a plain dict.
- `update(self, key: 'str', value: 'Any', clock: 'Optional[VectorClock]' = None) -> 'VectorClock'` — Insert or update a key-value pair.

#### `Ordering(*values)`

Causal ordering between two vector clocks.

#### `VectorClock(clocks: 'Optional[Dict[str, int]]' = None) -> 'None'`

Vector clock for tracking causal ordering in distributed systems.

**Properties:**

- `value` — Return a **copy** of the internal clock dict.

**Methods:**

- `compare(self, other: 'VectorClock') -> 'Ordering'` — Compare two vector clocks for causal ordering.
- `from_dict(d: 'dict') -> 'VectorClock'` — Deserialize from a plain dict.
- `get(self, node_id: 'str') -> 'int'` — Get the counter for *node_id* (0 if the node has never been seen).
- `increment(self, node_id: 'str') -> 'VectorClock'` — Return a NEW clock with *node_id*'s counter incremented by 1.
- `merge(self, other: 'VectorClock') -> 'VectorClock'` — Element-wise max of two vector clocks. Returns a NEW instance.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

### Functions

#### `anti_entropy(local_digest: 'Dict[str, str]', remote_digest: 'Dict[str, str]') -> 'Dict[str, list]'`

Compare two digests and classify keys by sync action needed.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
