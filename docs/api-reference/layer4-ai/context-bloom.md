# Bloom

> ContextBloom — 64-shard bloom filter for O(1) memory dedup.

**Source:** `crdt_merge/context/bloom.py`  
**Lines of Code:** 225

## Overview

Partitions the hash space into shards for parallel operation.
Each shard is an independent ``MergeableBloom`` from
:mod:`crdt_merge.probabilistic`.

Because each shard merges via bitwise OR, the composite merge is also
commutative, associative, and idempotent — a natural CRDT.

Expected performance: millions of checks/sec, sub-microsecond per check.

New in v0.8.2.

## Classes

### `ContextBloom`

64-shard bloom filter for memory dedup.

**Constructor:**

```python
ContextBloom(expected_items: int = 100000, fp_rate: float = 0.001, num_shards: int = 64) -> None
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `add(fact: str) -> bool` | Add a fact to the bloom filter. |
| `contains` | `contains(fact: str) -> bool` | Check if a fact was seen before. |
| `merge` | `merge(other: ContextBloom) -> ContextBloom` | Merge two ContextBlooms by merging each shard pair. |
| `to_dict` | `to_dict() -> dict` | Serialize to a plain dict. |
| `from_dict` | `from_dict(d: dict) -> ContextBloom` | Deserialize from a dict produced by :meth:`to_dict`. |
| `estimated_items` | `estimated_items() -> int` | Estimated total number of items across all shards. |
| `false_positive_rate` | `false_positive_rate() -> float` | Estimated current false-positive rate (average across shards). |

**Special Methods:**

- `__eq__(other: object) -> bool` — —
- `__repr__() -> str` — —

## Functions

### `_shard_index()`

```python
_shard_index(fact: str, num_shards: int) -> int
```

Deterministically map a fact to a shard index.


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
