# Context Memory System 🆕

CRDT-merged memory for AI agents — sidecars, manifests, bloom dedup, consolidation, quality-weighted merge. **New in v0.8.2.**

## Quick Example

```python
from crdt_merge.context import ContextMerge, ContextBloom, MemorySidecar
bloom = ContextBloom(expected_items=100_000)
merger = ContextMerge(bloom=bloom, strategy="lww")
result = merger.merge(agent_a_memories, agent_b_memories)
```

---

## API Reference

## `crdt_merge.context`

> Context Memory System — CRDT-merged memory for AI agents.

**Module:** `crdt_merge.context`

### Classes

#### `ConsolidatedBlock(block_id: 'str', memories: 'List[MemoryChunk]', sidecar_index: 'Dict[str, MemorySidecar]', created_at: 'float') -> None`

A block of consolidated memories with a sidecar index.

**Properties:**

- `size` — Number of memories in this block.

**Methods:**

- `from_dict(d: 'dict') -> 'ConsolidatedBlock'` — Deserialize from a dict produced by :meth:`to_dict`.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `ContextBloom(expected_items: 'int' = 100000, fp_rate: 'float' = 0.001, num_shards: 'int' = 64) -> 'None'`

64-shard bloom filter for memory dedup.

**Properties:**

- `estimated_items` — Estimated total number of items across all shards.
- `false_positive_rate` — Estimated current false-positive rate (average across shards).

**Methods:**

- `add(self, fact: 'str') -> 'bool'` — Add a fact to the bloom filter.
- `contains(self, fact: 'str') -> 'bool'` — Check if a fact was seen before.
- `from_dict(d: 'dict') -> 'ContextBloom'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextBloom') -> 'ContextBloom'` — Merge two ContextBlooms by merging each shard pair.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `ContextConsolidator(block_size: 'int' = 1000) -> 'None'`

Bundles thousands of small memories into manageable indexed blocks.

**Methods:**

- `consolidate(self, memories: 'List[MemoryChunk]') -> 'List[ConsolidatedBlock]'` — Bundle memories into blocks of ``block_size``.
- `merge_blocks(self, blocks_a: 'List[ConsolidatedBlock]', blocks_b: 'List[ConsolidatedBlock]', bloom: 'Optional[ContextBloom]' = None) -> 'List[ConsolidatedBlock]'` — Merge two sets of blocks with optional bloom dedup.
- `query(self, blocks: 'List[ConsolidatedBlock]', topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'List[MemoryChunk]'` — Query across blocks using the sidecar index — no full content scan needed.

#### `ContextManifest(manifest_id: 'str', created_at: 'float', source_agents: 'List[str]', total_memories: 'int', unique_memories: 'int', duplicates_removed: 'int', conflicts_resolved: 'int', strategy_used: 'str', quality_score: 'float', provenance_chain: 'List[dict]' = <factory>) -> None`

Self-describing merge attestation package.

**Methods:**

- `from_dict(d: 'dict') -> 'ContextManifest'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextManifest') -> 'ContextManifest'` — Merge two manifests.
- `summary(self) -> 'str'` — Human-readable one-line summary.
- `to_dict(self) -> 'dict'` — Full serialisation to a plain dict.

#### `ContextMerge(bloom: 'Optional[ContextBloom]' = None, strategy: 'str' = 'lww', budget: 'Optional[int]' = None, min_confidence: 'float' = 0.0, agent_priority: 'Optional[Dict[str, int]]' = None) -> 'None'`

Quality-weighted, budget-aware context merge.

**Methods:**

- `merge(self, memories_a: 'List[dict]', memories_b: 'List[dict]') -> 'MergeResult'` — Merge two sets of agent memories.
- `merge_multi(self, *memory_sets: 'List[dict]') -> 'MergeResult'` — Merge N sets of memories (from N agents).

#### `MemoryChunk(fact: 'str', sidecar: 'MemorySidecar') -> None`

A single memory entry with its sidecar.

**Methods:**

- `from_dict(d: 'dict') -> 'MemoryChunk'` — Deserialize from a dict produced by :meth:`to_dict`.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MemorySidecar(fact_id: 'str', content_hash: 'str', topic: 'str' = '', confidence: 'float' = 1.0, source_agent: 'str' = '', timestamp: 'float' = <factory>, access_count: 'int' = 0, ttl: 'Optional[float]' = None, tags: 'List[str]' = <factory>, metadata: 'Dict[str, Any]' = <factory>) -> None`

Pre-computed metadata sidecar for a memory chunk.

**Methods:**

- `from_dict(d: 'dict') -> 'MemorySidecar'` — Deserialize from a dict produced by :meth:`to_dict`.
- `from_fact(fact: 'str', source_agent: 'str' = '', topic: 'str' = '', confidence: 'float' = 1.0, **kwargs: 'Any') -> 'MemorySidecar'` — Create a sidecar from a fact string.
- `is_expired(self, now: 'Optional[float]' = None) -> 'bool'` — Check if this memory has expired based on its TTL.
- `matches_filter(self, topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'bool'` — O(1) filter check against sidecar metadata.
- `merge(self, other: 'MemorySidecar') -> 'MemorySidecar'` — Merge two sidecars for the same fact.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MergeResult(memories: 'List[MemoryChunk]', manifest: 'ContextManifest', bloom: 'ContextBloom', duplicates_found: 'int', conflicts_resolved: 'int') -> None`

Result of a context merge operation.

**Methods:**



## `crdt_merge.context.sidecar`

> MemorySidecar — pre-computed metadata sidecar for a memory chunk.

**Module:** `crdt_merge.context.sidecar`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `MemorySidecar(fact_id: 'str', content_hash: 'str', topic: 'str' = '', confidence: 'float' = 1.0, source_agent: 'str' = '', timestamp: 'float' = <factory>, access_count: 'int' = 0, ttl: 'Optional[float]' = None, tags: 'List[str]' = <factory>, metadata: 'Dict[str, Any]' = <factory>) -> None`

Pre-computed metadata sidecar for a memory chunk.

**Methods:**

- `from_dict(d: 'dict') -> 'MemorySidecar'` — Deserialize from a dict produced by :meth:`to_dict`.
- `from_fact(fact: 'str', source_agent: 'str' = '', topic: 'str' = '', confidence: 'float' = 1.0, **kwargs: 'Any') -> 'MemorySidecar'` — Create a sidecar from a fact string.
- `is_expired(self, now: 'Optional[float]' = None) -> 'bool'` — Check if this memory has expired based on its TTL.
- `matches_filter(self, topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'bool'` — O(1) filter check against sidecar metadata.
- `merge(self, other: 'MemorySidecar') -> 'MemorySidecar'` — Merge two sidecars for the same fact.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.context.manifest`

> ContextManifest — self-describing merge attestation package.

**Module:** `crdt_merge.context.manifest`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ContextManifest(manifest_id: 'str', created_at: 'float', source_agents: 'List[str]', total_memories: 'int', unique_memories: 'int', duplicates_removed: 'int', conflicts_resolved: 'int', strategy_used: 'str', quality_score: 'float', provenance_chain: 'List[dict]' = <factory>) -> None`

Self-describing merge attestation package.

**Methods:**

- `from_dict(d: 'dict') -> 'ContextManifest'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextManifest') -> 'ContextManifest'` — Merge two manifests.
- `summary(self) -> 'str'` — Human-readable one-line summary.
- `to_dict(self) -> 'dict'` — Full serialisation to a plain dict.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.context.bloom`

> ContextBloom — 64-shard bloom filter for O(1) memory dedup.

**Module:** `crdt_merge.context.bloom`

### Classes

#### `ContextBloom(expected_items: 'int' = 100000, fp_rate: 'float' = 0.001, num_shards: 'int' = 64) -> 'None'`

64-shard bloom filter for memory dedup.

**Properties:**

- `estimated_items` — Estimated total number of items across all shards.
- `false_positive_rate` — Estimated current false-positive rate (average across shards).

**Methods:**

- `add(self, fact: 'str') -> 'bool'` — Add a fact to the bloom filter.
- `contains(self, fact: 'str') -> 'bool'` — Check if a fact was seen before.
- `from_dict(d: 'dict') -> 'ContextBloom'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextBloom') -> 'ContextBloom'` — Merge two ContextBlooms by merging each shard pair.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MergeableBloom(capacity: int = 10000, fp_rate: float = 0.01, *, _size: Optional[int] = None, _num_hashes: Optional[int] = None)`

Bloom filter with CRDT merge semantics.

**Methods:**

- `add(self, item: Any) -> None` — Add an item to the filter.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items.
- `contains(self, item: Any) -> bool` — Check if an item might be in the set.
- `estimated_fp_rate(self) -> float` — Estimate current false positive rate based on fill ratio.
- `from_dict(d: dict) -> 'MergeableBloom'` — Deserialize from dict.
- `merge(self, other: 'MergeableBloom') -> 'MergeableBloom'` — Merge two Bloom filters via bitwise OR.
- `size_bytes(self) -> int` — Return memory usage in bytes.
- `to_dict(self) -> dict` — Serialize to dict for wire format.


## `crdt_merge.context.consolidator`

> ContextConsolidator — bundles thousands of small memories into indexed blocks.

**Module:** `crdt_merge.context.consolidator`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ConsolidatedBlock(block_id: 'str', memories: 'List[MemoryChunk]', sidecar_index: 'Dict[str, MemorySidecar]', created_at: 'float') -> None`

A block of consolidated memories with a sidecar index.

**Properties:**

- `size` — Number of memories in this block.

**Methods:**

- `from_dict(d: 'dict') -> 'ConsolidatedBlock'` — Deserialize from a dict produced by :meth:`to_dict`.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `ContextBloom(expected_items: 'int' = 100000, fp_rate: 'float' = 0.001, num_shards: 'int' = 64) -> 'None'`

64-shard bloom filter for memory dedup.

**Properties:**

- `estimated_items` — Estimated total number of items across all shards.
- `false_positive_rate` — Estimated current false-positive rate (average across shards).

**Methods:**

- `add(self, fact: 'str') -> 'bool'` — Add a fact to the bloom filter.
- `contains(self, fact: 'str') -> 'bool'` — Check if a fact was seen before.
- `from_dict(d: 'dict') -> 'ContextBloom'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextBloom') -> 'ContextBloom'` — Merge two ContextBlooms by merging each shard pair.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `ContextConsolidator(block_size: 'int' = 1000) -> 'None'`

Bundles thousands of small memories into manageable indexed blocks.

**Methods:**

- `consolidate(self, memories: 'List[MemoryChunk]') -> 'List[ConsolidatedBlock]'` — Bundle memories into blocks of ``block_size``.
- `merge_blocks(self, blocks_a: 'List[ConsolidatedBlock]', blocks_b: 'List[ConsolidatedBlock]', bloom: 'Optional[ContextBloom]' = None) -> 'List[ConsolidatedBlock]'` — Merge two sets of blocks with optional bloom dedup.
- `query(self, blocks: 'List[ConsolidatedBlock]', topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'List[MemoryChunk]'` — Query across blocks using the sidecar index — no full content scan needed.

#### `MemoryChunk(fact: 'str', sidecar: 'MemorySidecar') -> None`

A single memory entry with its sidecar.

**Methods:**

- `from_dict(d: 'dict') -> 'MemoryChunk'` — Deserialize from a dict produced by :meth:`to_dict`.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MemorySidecar(fact_id: 'str', content_hash: 'str', topic: 'str' = '', confidence: 'float' = 1.0, source_agent: 'str' = '', timestamp: 'float' = <factory>, access_count: 'int' = 0, ttl: 'Optional[float]' = None, tags: 'List[str]' = <factory>, metadata: 'Dict[str, Any]' = <factory>) -> None`

Pre-computed metadata sidecar for a memory chunk.

**Methods:**

- `from_dict(d: 'dict') -> 'MemorySidecar'` — Deserialize from a dict produced by :meth:`to_dict`.
- `from_fact(fact: 'str', source_agent: 'str' = '', topic: 'str' = '', confidence: 'float' = 1.0, **kwargs: 'Any') -> 'MemorySidecar'` — Create a sidecar from a fact string.
- `is_expired(self, now: 'Optional[float]' = None) -> 'bool'` — Check if this memory has expired based on its TTL.
- `matches_filter(self, topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'bool'` — O(1) filter check against sidecar metadata.
- `merge(self, other: 'MemorySidecar') -> 'MemorySidecar'` — Merge two sidecars for the same fact.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.context.merge`

> ContextMerge — quality-weighted, budget-aware context merge.

**Module:** `crdt_merge.context.merge`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ContextBloom(expected_items: 'int' = 100000, fp_rate: 'float' = 0.001, num_shards: 'int' = 64) -> 'None'`

64-shard bloom filter for memory dedup.

**Properties:**

- `estimated_items` — Estimated total number of items across all shards.
- `false_positive_rate` — Estimated current false-positive rate (average across shards).

**Methods:**

- `add(self, fact: 'str') -> 'bool'` — Add a fact to the bloom filter.
- `contains(self, fact: 'str') -> 'bool'` — Check if a fact was seen before.
- `from_dict(d: 'dict') -> 'ContextBloom'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextBloom') -> 'ContextBloom'` — Merge two ContextBlooms by merging each shard pair.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `ContextManifest(manifest_id: 'str', created_at: 'float', source_agents: 'List[str]', total_memories: 'int', unique_memories: 'int', duplicates_removed: 'int', conflicts_resolved: 'int', strategy_used: 'str', quality_score: 'float', provenance_chain: 'List[dict]' = <factory>) -> None`

Self-describing merge attestation package.

**Methods:**

- `from_dict(d: 'dict') -> 'ContextManifest'` — Deserialize from a dict produced by :meth:`to_dict`.
- `merge(self, other: 'ContextManifest') -> 'ContextManifest'` — Merge two manifests.
- `summary(self) -> 'str'` — Human-readable one-line summary.
- `to_dict(self) -> 'dict'` — Full serialisation to a plain dict.

#### `ContextMerge(bloom: 'Optional[ContextBloom]' = None, strategy: 'str' = 'lww', budget: 'Optional[int]' = None, min_confidence: 'float' = 0.0, agent_priority: 'Optional[Dict[str, int]]' = None) -> 'None'`

Quality-weighted, budget-aware context merge.

**Methods:**

- `merge(self, memories_a: 'List[dict]', memories_b: 'List[dict]') -> 'MergeResult'` — Merge two sets of agent memories.
- `merge_multi(self, *memory_sets: 'List[dict]') -> 'MergeResult'` — Merge N sets of memories (from N agents).

#### `MemoryChunk(fact: 'str', sidecar: 'MemorySidecar') -> None`

A single memory entry with its sidecar.

**Methods:**

- `from_dict(d: 'dict') -> 'MemoryChunk'` — Deserialize from a dict produced by :meth:`to_dict`.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MemorySidecar(fact_id: 'str', content_hash: 'str', topic: 'str' = '', confidence: 'float' = 1.0, source_agent: 'str' = '', timestamp: 'float' = <factory>, access_count: 'int' = 0, ttl: 'Optional[float]' = None, tags: 'List[str]' = <factory>, metadata: 'Dict[str, Any]' = <factory>) -> None`

Pre-computed metadata sidecar for a memory chunk.

**Methods:**

- `from_dict(d: 'dict') -> 'MemorySidecar'` — Deserialize from a dict produced by :meth:`to_dict`.
- `from_fact(fact: 'str', source_agent: 'str' = '', topic: 'str' = '', confidence: 'float' = 1.0, **kwargs: 'Any') -> 'MemorySidecar'` — Create a sidecar from a fact string.
- `is_expired(self, now: 'Optional[float]' = None) -> 'bool'` — Check if this memory has expired based on its TTL.
- `matches_filter(self, topic: 'Optional[str]' = None, min_confidence: 'float' = 0.0, source_agent: 'Optional[str]' = None, tags: 'Optional[List[str]]' = None) -> 'bool'` — O(1) filter check against sidecar metadata.
- `merge(self, other: 'MemorySidecar') -> 'MemorySidecar'` — Merge two sidecars for the same fact.
- `to_dict(self) -> 'dict'` — Serialize to a plain dict.

#### `MergeResult(memories: 'List[MemoryChunk]', manifest: 'ContextManifest', bloom: 'ContextBloom', duplicates_found: 'int', conflicts_resolved: 'int') -> None`

Result of a context merge operation.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
