# Sidecar

> MemorySidecar — pre-computed metadata sidecar for a memory chunk.

**Source:** `crdt_merge/context/sidecar.py`  
**Lines of Code:** 305

## Overview

Like a nutrition label for memories: you don't need to open the memory
to know what's inside. Enables O(1) filtering, expiry checking, and
metadata-based routing without reading memory content.

The merge operation is a CRDT merge:
  - Higher confidence wins for scalar value fields
  - Tags are unioned (set union is a CRDT)
  - Access counts are max'd (grow-only counter semantics)
  - Latest timestamp wins (LWW register semantics)

All three CRDT laws hold:
  - Commutative:  A.merge(B) == B.merge(A)
  - Associative:  A.merge(B).merge(C) == A.merge(B.merge(C))
  - Idempotent:   A.merge(A) == A

New in v0.8.2.

## Classes

### `MemorySidecar`

Pre-computed metadata sidecar for a memory chunk.

**Class Attributes:**

- `fact_id` — `str`
- `content_hash` — `str`
- `topic` — `str = ''`
- `confidence` — `float = 1.0`
- `source_agent` — `str = ''`
- `timestamp` — `float = field(default_factory=time.time)`
- `access_count` — `int = 0`
- `ttl` — `Optional[float] = None`
- `tags` — `List[str] = field(default_factory=list)`
- `metadata` — `Dict[str, Any] = field(default_factory=dict)`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_fact` | `from_fact(fact: str, source_agent: str = '', topic: str = '', confidence: float = 1.0, **kwargs: Any) -> MemorySidecar` | Create a sidecar from a fact string. |
| `is_expired` | `is_expired(now: Optional[float] = None) -> bool` | Check if this memory has expired based on its TTL. |
| `matches_filter` | `matches_filter(topic: Optional[str] = None, min_confidence: float = 0.0, source_agent: Optional[str] = None, tags: Optional[List[str]] = None) -> bool` | O(1) filter check against sidecar metadata. |
| `to_dict` | `to_dict() -> dict` | Serialize to a plain dict. |
| `from_dict` | `from_dict(d: dict) -> MemorySidecar` | Deserialize from a dict produced by :meth:`to_dict`. |
| `merge` | `merge(other: MemorySidecar) -> MemorySidecar` | Merge two sidecars for the same fact. |

**Special Methods:**

- `__eq__(other: object) -> bool` — —
- `__repr__() -> str` — —


## Analysis Notes
