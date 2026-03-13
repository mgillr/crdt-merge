# `crdt_merge/context/__init__.py`

> Context Memory System — CRDT-merged memory for AI agents.

This subpackage provides a complete system for merging, deduplicating,
and managing agent memories using CRDT semantics. Every merge operation
is commutative, associative, and idempotent — agents can merge in any
order and always converge to

**Source:** `crdt_merge/context/__init__.py` | **Lines:** 56

---

**Exports (`__all__`):** `['MemorySidecar', 'ContextManifest', 'ContextBloom', 'ContextConsolidator', 'ConsolidatedBlock', 'MemoryChunk', 'ContextMerge', 'MergeResult']`


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 5
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 100.0%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
