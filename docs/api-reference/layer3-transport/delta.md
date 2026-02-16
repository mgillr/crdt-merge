# delta

> Layer 3 — Sync & Transport
> Source: `crdt_merge/delta.py`  
> LOC: 269 (AST-verified)

## Overview
Delta-State Dataset Sync — O(delta) synchronization instead of O(n).

Instead of exchanging full datasets, compute and ship only what changed.
Deltas are composable: delta(1→2) ⊔ delta(2→3) == delta(1→3).

Inspired by Almeida et al. (2018) δ-CRDTs, extended for tabular datasets.

Usage:
    from crdt_merge.delta import DeltaStore, compute_delta, apply_delta, compose_deltas

    store = DeltaStore(key="id")
    store.ingest(initial_records)

    # Later, compute what changed
    delta = store.compute_delta(updated_records)

    # Ship delta to remote (much smaller than full state)
    remote_store.apply_delta(delta)

    # Compose multiple deltas
    combined = compose_deltas(delta_1, delta_2, delta_3)

## Classes

### `Delta`

Represents the minimal changeset between two dataset states.

Contains:
    added: Records that are new
    modified: Records that changed (with new values)
    removed: Keys that were deleted
    version: Monotonic version counter
    timestamp: When this delta was computed

#### Constructor
```python
__init__(self, added: Optional[List[dict]] = None, modified: Optional[List[dict]] = None, removed: Optional[List[str]] = None, version: int = 0, timestamp: Optional[float] = None, source_node: str = '')
```

Initialize a Delta with changeset components.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `added` | `Optional[List[dict]]` | `None` | Records that are new in this delta. Defaults to empty list. |
| `modified` | `Optional[List[dict]]` | `None` | Records that changed (with updated values). Defaults to empty list. |
| `removed` | `Optional[List[str]]` | `None` | Keys of records that were deleted. Defaults to empty list. |
| `version` | `int` | `0` | Monotonic version counter for ordering deltas. |
| `timestamp` | `Optional[float]` | `None` | Unix timestamp when this delta was computed. Defaults to current time. |
| `source_node` | `str` | `''` | Identifier of the node that produced this delta. |

#### Properties

##### `size: int`

Total number of changes in this delta. Returns the sum of added, modified, and removed record counts.

##### `is_empty: bool`

Whether this delta contains no changes. Returns `True` if the delta has zero added, modified, and removed records.

#### Methods

##### `to_dict(self) -> dict`

Serialize the delta to a plain dictionary. Returns a dictionary containing all delta fields (`added`, `modified`, `removed`, `version`, `timestamp`, `source_node`).

##### `@classmethod from_dict(cls, d: dict) -> Delta`
Decorators: `@classmethod`

Reconstruct a Delta from a dictionary.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `d` | `dict` | `—` | Dictionary with delta fields as produced by `to_dict()`. |

##### `__repr__(self) -> str`

Return a concise summary string showing change counts and version (e.g., `Delta(+3 ~1 -2, v5)`).

---

### `DeltaStore`

Stateful delta tracker — remembers the last known state and computes
deltas automatically on each ingest.

Usage:
    store = DeltaStore(key="id", node_id="node-1")
    store.ingest(initial_records)  # First ingest, no delta

    # Later...
    delta = store.ingest(updated_records)
    ship_to_remote(delta)  # Only send changes

#### Constructor
```python
__init__(self, key: str, node_id: str = 'default')
```

Initialize a DeltaStore.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | `str` | `—` | The field name used as the primary key for record identity. |
| `node_id` | `str` | `'default'` | Identifier of this node, embedded in produced deltas. |

#### Properties

##### `version: int`

Current version counter of the store. Monotonically increasing, incremented on each ingest that produces a delta.

##### `size: int`

Number of records currently held in the store's latest snapshot.

##### `records: List[dict]`

Current state as a list of records. Returns all records in the store's latest snapshot.

#### Methods

##### `ingest(self, records: List[dict]) -> Optional[Delta]`

Ingest new state and return the delta from previous state.
First call returns `None` (no previous state to diff against).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `records` | `List[dict]` | `—` | The complete set of current records. |

##### `__repr__(self) -> str`

Return a summary string with key field, record count, and version (e.g., `DeltaStore(key='id', records=5, v3)`).

---

## Functions

### `_record_hash(record: dict, key: str) -> str`

Hash a record's non-key content for change detection.

| Parameter | Type | Default |
|-----------|------|---------|
| `record` | `dict` | `—` |
| `key` | `str` | `—` |

### `compute_delta(old_records: List[dict], new_records: List[dict], key: str, version: int = 0, source_node: str = '') -> Delta`

Compute the minimal delta between old and new states.

Returns only what changed — added, modified, removed.

| Parameter | Type | Default |
|-----------|------|---------|
| `old_records` | `List[dict]` | `—` |
| `new_records` | `List[dict]` | `—` |
| `key` | `str` | `—` |
| `version` | `int` | `0` |
| `source_node` | `str` | `''` |

### `apply_delta(records: List[dict], delta: Delta, key: str, schema: Optional[MergeSchema] = None) -> List[dict]`

Apply a delta to a record set, producing the updated state.

Uses merge strategies for modified records if schema is provided.

| Parameter | Type | Default |
|-----------|------|---------|
| `records` | `List[dict]` | `—` |
| `delta` | `Delta` | `—` |
| `key` | `str` | `—` |
| `schema` | `Optional[MergeSchema]` | `None` |

### `compose_deltas(*deltas: Delta, key: Optional[str] = None) -> Delta`

Compose multiple deltas into one: delta(1→2) ⊔ delta(2→3) == delta(1→3).

This is the key composability property of δ-CRDTs.
The result contains the net effect of all deltas applied in order.

Args:
    *deltas: Delta objects to compose. Also accepts a single list/tuple of Deltas.
    key: Optional key field name for identity tracking. When provided,
         records are tracked by their key field value instead of content hash.
         This prevents duplicates when a record is added then modified.

| Parameter | Type | Default |
|-----------|------|---------|
| `deltas` | `Delta` | `—` |
| `key` | `Optional[str]` | `None` |

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 3
- Inherited methods: None
- No circular dependencies
- Regex-only symbol: `Delta._record_id` (found by regex but not AST — likely a dynamic attribute)

### RREA Findings
- Entropy profile: zero (first pass); heightened sensitivity found 3 genuine chokepoints
- `Delta`: combined H=0.3121, ping H=0.4317, 3 endpoints
- `Delta.size`: combined H=0.3121, ping H=0.4317, 3 endpoints
- `Delta.is_empty`: combined H=0.3121, ping H=0.4317, 3 endpoints
- Dead code: None
- Shadow dependencies: `added.append` (only endpoint: `crdt_merge.delta.compute_delta`)
- Chokepoint status: 3 genuine chokepoints — Delta class and its size/is_empty properties serve as convergence points

### Code Quality (Team 2)
- Docstring coverage: 100% — all public methods and properties documented with Google-style docstrings
- `__all__` defined: yes (`Delta`, `DeltaStore`, `compute_delta`, `apply_delta`, `compose_deltas`)
- All parameters, return types, and CRDT properties documented

---
Approved by: Auditor (Team 1), Cross-validated by Teams 2–4  
Last reviewed: 2026-03-31
