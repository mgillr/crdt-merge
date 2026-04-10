# `crdt_merge/context/merge.py`

> ContextMerge — quality-weighted, budget-aware context merge.

The main entry point for merging agent memories. Supports four strategies:

  - ``lww``: Last-Writer-Wins — latest timestamp wins for conflicts.
  - ``max_confidence``: Highest confidence score wins.
  - ``priority``: Source agent priorit

**Source:** `crdt_merge/context/merge.py` | **Lines:** 402

---

## Classes

### `class MergeResult`

Result of a context merge operation.

    Attributes:
        memories: Final list of merged MemoryChunk instances.
        manifest: ContextManifest attesting to the merge.
        bloom: ContextBloom used for dedup (can be re-used for future merges).
        duplicates_found: Number of duplicates eliminated.
        conflicts_resolved: Number of conflicts resolved by the strategy.

    Examples:
        >>> mr = MergeResult(
        ...     memories=[], manifest=None, bloom=None,
        ...     duplicates_found=0, conflicts_resolved=0
        ... )

- `memories`: `List[MemoryChunk]`
- `manifest`: `ContextManifest`
- `bloom`: `ContextBloom`
- `duplicates_found`: `int`
- `conflicts_resolved`: `int`

**Methods:**

#### `MergeResult.__repr__(self) → str`

*No docstring*


### `class ContextMerge`

Quality-weighted, budget-aware context merge.

    Uses the same strategy pattern as tabular merge.
    One API for data AND knowledge.

    Args:
        bloom: Pre-existing bloom filter for dedup continuity.
            If ``None``, a fresh one is created.
        strategy: Conflict resolution strategy. One of:
            ``"lww"`` (latest wins), ``"max_confidence"`` (highest conf wins),
            ``"priority"`` (source agent ordering), ``"union"`` (keep all unique).
        budget: Maximum number of memories to keep. ``None`` = unlimited.
        min_confidence: Filter out memories below this threshold.
        agent_priority: Dict mapping agent name → priority int (used with
            ``"priority"`` strategy). Higher value = higher priority.

    Examples:
        >>> cm = ContextMerge(strategy="lww")
        >>> result = cm.merge(
        ...     [{"fact": "sky is blue"}],
        ...     [{"fact": "sky is blue", "confidence": 0.9}]
        ... )
        >>> len(result.memories)
        1


**Methods:**

#### `ContextMerge.__init__(self, bloom: Optional[ContextBloom] = None, strategy: str = 'lww', budget: Optional[int] = None, min_confidence: float = 0.0, agent_priority: Optional[Dict[str, int]] = None) → None`

*No docstring*

#### `ContextMerge._dict_to_chunk(d: dict) → MemoryChunk`

Convert a raw memory dict to a MemoryChunk with sidecar.

        The dict must have at least ``{"fact": str}``. Optional fields:
        ``confidence``, ``source``, ``ts``, ``topic``, ``tags``.

#### `ContextMerge._resolve_conflict(self, a: MemoryChunk, b: MemoryChunk) → MemoryChunk`

Route to the correct strategy resolver.

#### `ContextMerge.merge(self, memories_a: List[dict], memories_b: List[dict]) → MergeResult`

Merge two sets of agent memories.

        Steps:
          1. Create sidecars for all memories.
          2. Bloom dedup (catches ~60-80% duplicates).
          3. Apply strategy for conflicts (same fact_id, different metadata).
          4. Budget filter if budget is set (keep highest confidence).
          5. Build manifest.
          6. Return MergeResult.

        Args:
            memories_a: First list of memory dicts (``{"fact": str, ...}``).
            memories_b: Second list of memory dicts.

        Returns:
            MergeResult with merged memories, manifest, and bloom.

#### `ContextMerge.merge_multi(self, *memory_sets: List[dict]) → MergeResult`

Merge N sets of memories (from N agents).

        Reduces pairwise using :meth:`merge`. The bloom filter is carried
        forward between merges for cumulative dedup.

        Args:
            *memory_sets: Variable number of memory dict lists.

        Returns:
            MergeResult from the final pairwise merge.

        Raises:
            ValueError: If fewer than 2 memory sets are provided.

#### `ContextMerge.__repr__(self) → str`

*No docstring*


## Functions

### `_resolve_conflict_lww(a: MemoryChunk, b: MemoryChunk) → MemoryChunk`

Last-Writer-Wins: higher timestamp wins.  Tie-break: higher confidence.

### `_resolve_conflict_max_confidence(a: MemoryChunk, b: MemoryChunk) → MemoryChunk`

Highest confidence wins. Tie-break: latest timestamp, then deterministic.

### `_resolve_conflict_priority(a: MemoryChunk, b: MemoryChunk, agent_priority: Dict[str, int]) → MemoryChunk`

Source agent priority wins. Tie-break: confidence, then deterministic.


## Analysis Notes
