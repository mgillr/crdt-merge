# Manifest

> ContextManifest — self-describing merge attestation package.

**Source:** `crdt_merge/context/manifest.py`  
**Lines of Code:** 242

## Overview

Records what was merged, which strategies were used, timestamps,
quality scores, and provenance chain. Designed for EU AI Act Article 13
traceability: every merge is auditable.

The merge operation is a CRDT merge:
  - Source agents are unioned (set union).
  - Counts are max'd (grow-only counter semantics).
  - Quality score is max'd.
  - Provenance chains are unioned and sorted by timestamp for determinism.
  - Manifest ID is deterministically derived.

All three CRDT laws hold:
  - Commutative:  A.merge(B) == B.merge(A)
  - Associative:  A.merge(B).merge(C) == A.merge(B.merge(C))
  - Idempotent:   A.merge(A) == A

New in v0.8.2.

## Classes

### `ContextManifest`

Self-describing merge attestation package.

**Class Attributes:**

- `manifest_id` — `str`
- `created_at` — `float`
- `source_agents` — `List[str]`
- `total_memories` — `int`
- `unique_memories` — `int`
- `duplicates_removed` — `int`
- `conflicts_resolved` — `int`
- `strategy_used` — `str`
- `quality_score` — `float`
- `provenance_chain` — `List[dict] = field(default_factory=list)`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `summary` | `summary() -> str` | Human-readable one-line summary. |
| `to_dict` | `to_dict() -> dict` | Full serialisation to a plain dict. |
| `from_dict` | `from_dict(d: dict) -> ContextManifest` | Deserialize from a dict produced by :meth:`to_dict`. |
| `merge` | `merge(other: ContextManifest) -> ContextManifest` | Merge two manifests. |

**Special Methods:**

- `__post_init__() -> None` — Normalize fields at creation for CRDT idempotency.
- `__eq__(other: object) -> bool` — —
- `__repr__() -> str` — —


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 1
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 75.0%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
