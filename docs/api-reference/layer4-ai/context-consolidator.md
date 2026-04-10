# Consolidator

> ContextConsolidator — bundles thousands of small memories into indexed blocks.

**Source:** `crdt_merge/context/consolidator.py`  
**Lines of Code:** 305

## Overview

Converts a flat list of memories into manageable consolidated blocks,
each with a sidecar index for O(1) filtering.

    50K memories → 50 indexed blocks of 1000 each

Each block has a merged sidecar index keyed by ``fact_id`` so that
queries can check metadata without scanning memory content.

New in v0.8.2.

## Classes

### `MemoryChunk`

A single memory entry with its sidecar.

**Class Attributes:**

- `fact` — `str`
- `sidecar` — `MemorySidecar`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_dict` | `to_dict() -> dict` | Serialize to a plain dict. |
| `from_dict` | `from_dict(d: dict) -> MemoryChunk` | Deserialize from a dict produced by :meth:`to_dict`. |

**Special Methods:**

- `__eq__(other: object) -> bool` — —
- `__repr__() -> str` — —

### `ConsolidatedBlock`

A block of consolidated memories with a sidecar index.

**Class Attributes:**

- `block_id` — `str`
- `memories` — `List[MemoryChunk]`
- `sidecar_index` — `Dict[str, MemorySidecar]`
- `created_at` — `float`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `size` | `size() -> int` | Number of memories in this block. |
| `to_dict` | `to_dict() -> dict` | Serialize to a plain dict. |
| `from_dict` | `from_dict(d: dict) -> ConsolidatedBlock` | Deserialize from a dict produced by :meth:`to_dict`. |

**Special Methods:**

- `__eq__(other: object) -> bool` — —
- `__repr__() -> str` — —

### `ContextConsolidator`

Bundles thousands of small memories into manageable indexed blocks.

**Constructor:**

```python
ContextConsolidator(block_size: int = 1000) -> None
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `consolidate` | `consolidate(memories: List[MemoryChunk]) -> List[ConsolidatedBlock]` | Bundle memories into blocks of ``block_size``. |
| `query` | `query(blocks: List[ConsolidatedBlock], topic: Optional[str] = None, min_confidence: float = 0.0, source_agent: Optional[str] = None, tags: Optional[List[str]] = None) -> List[MemoryChunk]` | Query across blocks using the sidecar index — no full content scan needed. |
| `merge_blocks` | `merge_blocks(blocks_a: List[ConsolidatedBlock], blocks_b: List[ConsolidatedBlock], bloom: Optional[ContextBloom] = None) -> List[ConsolidatedBlock]` | Merge two sets of blocks with optional bloom dedup. |

**Special Methods:**

- `__repr__() -> str` — —


## Analysis Notes
