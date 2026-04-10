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
