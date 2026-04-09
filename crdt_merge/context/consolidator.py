# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
ContextConsolidator — bundles thousands of small memories into indexed blocks.

Converts a flat list of memories into manageable consolidated blocks,
each with a sidecar index for O(1) filtering.

    50K memories → 50 indexed blocks of 1000 each

Each block has a merged sidecar index keyed by ``fact_id`` so that
queries can check metadata without scanning memory content.

New in v0.8.2.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .bloom import ContextBloom
from .sidecar import MemorySidecar


# ── Data structures ────────────────────────────────────────────────────────


@dataclass
class MemoryChunk:
    """A single memory entry with its sidecar.

    Attributes:
        fact: The textual content of the memory.
        sidecar: Pre-computed metadata sidecar for this memory.

    Examples:
        >>> mc = MemoryChunk(
        ...     fact="The sky is blue",
        ...     sidecar=MemorySidecar.from_fact("The sky is blue")
        ... )
        >>> mc.fact
        'The sky is blue'
    """

    fact: str
    sidecar: MemorySidecar

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {"fact": self.fact, "sidecar": self.sidecar.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> MemoryChunk:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            fact=d["fact"],
            sidecar=MemorySidecar.from_dict(d["sidecar"]),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MemoryChunk):
            return NotImplemented
        return self.fact == other.fact and self.sidecar == other.sidecar

    def __repr__(self) -> str:
        return f"MemoryChunk(fact={self.fact!r}, id={self.sidecar.fact_id!r})"


@dataclass
class ConsolidatedBlock:
    """A block of consolidated memories with a sidecar index.

    Attributes:
        block_id: Unique identifier for this block.
        memories: List of MemoryChunk instances in this block.
        sidecar_index: Mapping from ``fact_id`` to ``MemorySidecar`` for O(1) lookup.
        created_at: Unix timestamp when this block was created.

    Examples:
        >>> block = ConsolidatedBlock(
        ...     block_id="b1", memories=[], sidecar_index={}, created_at=1000.0
        ... )
        >>> block.size
        0
    """

    block_id: str
    memories: List[MemoryChunk]
    sidecar_index: Dict[str, MemorySidecar]
    created_at: float

    @property
    def size(self) -> int:
        """Number of memories in this block."""
        return len(self.memories)

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {
            "block_id": self.block_id,
            "memories": [m.to_dict() for m in self.memories],
            "sidecar_index": {k: v.to_dict() for k, v in self.sidecar_index.items()},
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConsolidatedBlock:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            block_id=d["block_id"],
            memories=[MemoryChunk.from_dict(m) for m in d.get("memories", [])],
            sidecar_index={
                k: MemorySidecar.from_dict(v)
                for k, v in d.get("sidecar_index", {}).items()
            },
            created_at=d.get("created_at", 0.0),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConsolidatedBlock):
            return NotImplemented
        return (
            self.block_id == other.block_id
            and self.memories == other.memories
            and self.sidecar_index == other.sidecar_index
        )

    def __repr__(self) -> str:
        return f"ConsolidatedBlock(id={self.block_id!r}, size={self.size})"


# ── Consolidator ───────────────────────────────────────────────────────────


class ContextConsolidator:
    """Bundles thousands of small memories into manageable indexed blocks.

    50K memories → 50 indexed blocks of 1000 each.
    Each block has a merged sidecar index for O(1) filtering.

    Args:
        block_size: Maximum number of memories per block.

    Examples:
        >>> consolidator = ContextConsolidator(block_size=100)
        >>> chunks = [
        ...     MemoryChunk("fact1", MemorySidecar.from_fact("fact1")),
        ...     MemoryChunk("fact2", MemorySidecar.from_fact("fact2")),
        ... ]
        >>> blocks = consolidator.consolidate(chunks)
        >>> len(blocks)
        1
    """

    def __init__(self, block_size: int = 1000) -> None:
        self.block_size = max(block_size, 1)

    def consolidate(self, memories: List[MemoryChunk]) -> List[ConsolidatedBlock]:
        """Bundle memories into blocks of ``block_size``.

        Args:
            memories: Flat list of MemoryChunk instances.

        Returns:
            List of ConsolidatedBlock instances.
        """
        if not memories:
            return []

        blocks: List[ConsolidatedBlock] = []
        now = time.time()

        for start in range(0, len(memories), self.block_size):
            chunk_slice = memories[start : start + self.block_size]
            # Build sidecar index for O(1) lookup
            index: Dict[str, MemorySidecar] = {}
            for mc in chunk_slice:
                fid = mc.sidecar.fact_id
                if fid in index:
                    # Merge sidecars for duplicate fact IDs within the block
                    index[fid] = index[fid].merge(mc.sidecar)
                else:
                    index[fid] = mc.sidecar

            # Block ID: hash of all fact IDs in sorted order for determinism
            sorted_ids = sorted(index.keys())
            block_id = hashlib.sha256(
                "|".join(sorted_ids).encode("utf-8")
            ).hexdigest()[:16]

            blocks.append(
                ConsolidatedBlock(
                    block_id=block_id,
                    memories=list(chunk_slice),
                    sidecar_index=index,
                    created_at=now,
                )
            )

        return blocks

    def query(
        self,
        blocks: List[ConsolidatedBlock],
        topic: Optional[str] = None,
        min_confidence: float = 0.0,
        source_agent: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[MemoryChunk]:
        """Query across blocks using the sidecar index — no full content scan needed.

        Uses sidecar metadata for O(1) per-memory filtering.

        Args:
            blocks: List of ConsolidatedBlock instances to search.
            topic: Filter by topic. None means no topic filter.
            min_confidence: Minimum confidence threshold.
            source_agent: Filter by source agent. None means no agent filter.
            tags: Filter by required tags. None means no tag filter.

        Returns:
            List of matching MemoryChunk instances.
        """
        results: List[MemoryChunk] = []
        for block in blocks:
            for mc in block.memories:
                if mc.sidecar.matches_filter(
                    topic=topic,
                    min_confidence=min_confidence,
                    source_agent=source_agent,
                    tags=tags,
                ):
                    results.append(mc)
        return results

    def merge_blocks(
        self,
        blocks_a: List[ConsolidatedBlock],
        blocks_b: List[ConsolidatedBlock],
        bloom: Optional[ContextBloom] = None,
    ) -> List[ConsolidatedBlock]:
        """Merge two sets of blocks with optional bloom dedup.

        Collects all memories from both block sets, deduplicates using
        the bloom filter (if provided) or by ``fact_id``, merges sidecars
        for duplicates, and re-consolidates into new blocks.

        Args:
            blocks_a: First set of blocks.
            blocks_b: Second set of blocks.
            bloom: Optional ContextBloom for probabilistic dedup.

        Returns:
            A new list of ConsolidatedBlock instances.
        """
        # Collect all memories, keyed by fact_id for dedup / sidecar merge
        seen: Dict[str, MemoryChunk] = {}

        for block in list(blocks_a) + list(blocks_b):
            for mc in block.memories:
                fid = mc.sidecar.fact_id

                # Bloom-based dedup check
                if bloom is not None:
                    if bloom.contains(mc.fact):
                        # Probable duplicate -- merge sidecar if we already have it
                        if fid in seen:
                            merged_sc = seen[fid].sidecar.merge(mc.sidecar)
                            seen[fid] = MemoryChunk(fact=mc.fact, sidecar=merged_sc)
                        continue
                    bloom.add(mc.fact)

                if fid in seen:
                    # Merge sidecars for exact duplicates
                    merged_sc = seen[fid].sidecar.merge(mc.sidecar)
                    seen[fid] = MemoryChunk(fact=mc.fact, sidecar=merged_sc)
                else:
                    seen[fid] = mc

        # Re-consolidate
        all_memories = list(seen.values())
        return self.consolidate(all_memories)

    def __repr__(self) -> str:
        return f"ContextConsolidator(block_size={self.block_size})"
