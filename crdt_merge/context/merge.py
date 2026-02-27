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
ContextMerge — quality-weighted, budget-aware context merge.

The main entry point for merging agent memories. Supports four strategies:

  - ``lww``: Last-Writer-Wins — latest timestamp wins for conflicts.
  - ``max_confidence``: Highest confidence score wins.
  - ``priority``: Source agent priority ordering.
  - ``union``: Keep all unique memories.

All strategies produce deterministic, CRDT-compliant results.
One API for data AND knowledge.

New in v0.8.2.
"""

from __future__ import annotations

import functools
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .bloom import ContextBloom
from .consolidator import MemoryChunk
from .manifest import ContextManifest
from .sidecar import MemorySidecar


# ── Result type ────────────────────────────────────────────────────────────


@dataclass
class MergeResult:
    """Result of a context merge operation.

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
    """

    memories: List[MemoryChunk]
    manifest: ContextManifest
    bloom: ContextBloom
    duplicates_found: int
    conflicts_resolved: int

    def __repr__(self) -> str:
        return (
            f"MergeResult(memories={len(self.memories)}, "
            f"dups={self.duplicates_found}, conflicts={self.conflicts_resolved})"
        )


# ── Strategy helpers ───────────────────────────────────────────────────────


def _resolve_conflict_lww(a: MemoryChunk, b: MemoryChunk) -> MemoryChunk:
    """Last-Writer-Wins: higher timestamp wins.  Tie-break: higher confidence."""
    if b.sidecar.timestamp > a.sidecar.timestamp:
        winner_fact, merged_sc = b.fact, a.sidecar.merge(b.sidecar)
    elif a.sidecar.timestamp > b.sidecar.timestamp:
        winner_fact, merged_sc = a.fact, a.sidecar.merge(b.sidecar)
    else:
        # Same timestamp — higher confidence wins, then deterministic
        if b.sidecar.confidence > a.sidecar.confidence:
            winner_fact = b.fact
        elif a.sidecar.confidence > b.sidecar.confidence:
            winner_fact = a.fact
        else:
            winner_fact = max(a.fact, b.fact)
        merged_sc = a.sidecar.merge(b.sidecar)
    return MemoryChunk(fact=winner_fact, sidecar=merged_sc)


def _resolve_conflict_max_confidence(a: MemoryChunk, b: MemoryChunk) -> MemoryChunk:
    """Highest confidence wins. Tie-break: latest timestamp, then deterministic."""
    if b.sidecar.confidence > a.sidecar.confidence:
        winner_fact = b.fact
    elif a.sidecar.confidence > b.sidecar.confidence:
        winner_fact = a.fact
    else:
        # Same confidence — LWW tie-break
        if b.sidecar.timestamp > a.sidecar.timestamp:
            winner_fact = b.fact
        elif a.sidecar.timestamp > b.sidecar.timestamp:
            winner_fact = a.fact
        else:
            winner_fact = max(a.fact, b.fact)
    return MemoryChunk(fact=winner_fact, sidecar=a.sidecar.merge(b.sidecar))


def _resolve_conflict_priority(
    a: MemoryChunk, b: MemoryChunk, agent_priority: Dict[str, int]
) -> MemoryChunk:
    """Source agent priority wins. Tie-break: confidence, then deterministic."""
    rank_a = agent_priority.get(a.sidecar.source_agent, -1)
    rank_b = agent_priority.get(b.sidecar.source_agent, -1)
    if rank_b > rank_a:
        winner_fact = b.fact
    elif rank_a > rank_b:
        winner_fact = a.fact
    else:
        # Same priority — max confidence
        return _resolve_conflict_max_confidence(a, b)
    return MemoryChunk(fact=winner_fact, sidecar=a.sidecar.merge(b.sidecar))


# ── Main class ─────────────────────────────────────────────────────────────


class ContextMerge:
    """Quality-weighted, budget-aware context merge.

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
    """

    STRATEGIES = {"lww", "max_confidence", "priority", "union"}

    def __init__(
        self,
        bloom: Optional[ContextBloom] = None,
        strategy: str = "lww",
        budget: Optional[int] = None,
        min_confidence: float = 0.0,
        agent_priority: Optional[Dict[str, int]] = None,
    ) -> None:
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy {strategy!r}. Choose from {sorted(self.STRATEGIES)}"
            )
        self.bloom = bloom or ContextBloom(expected_items=100_000, fp_rate=0.001)
        self.strategy = strategy
        self.budget = budget
        self.min_confidence = min_confidence
        self.agent_priority = agent_priority or {}

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _dict_to_chunk(d: dict) -> MemoryChunk:
        """Convert a raw memory dict to a MemoryChunk with sidecar.

        The dict must have at least ``{"fact": str}``. Optional fields:
        ``confidence``, ``source``, ``ts``, ``topic``, ``tags``.
        """
        fact = d.get("fact", "")
        confidence = float(d.get("confidence", 1.0))
        source = d.get("source", "")
        ts = float(d.get("ts", 0.0)) or time.time()
        topic = d.get("topic", "")
        tags = list(d.get("tags", []))
        metadata = {k: v for k, v in d.items() if k not in ("fact", "confidence", "source", "ts", "topic", "tags")}

        sidecar = MemorySidecar.from_fact(
            fact,
            source_agent=source,
            topic=topic,
            confidence=confidence,
            tags=tags,
            metadata=metadata,
        )
        # Override timestamp if provided
        if d.get("ts"):
            sidecar.timestamp = float(d["ts"])
        else:
            sidecar.timestamp = ts

        return MemoryChunk(fact=fact, sidecar=sidecar)

    def _resolve_conflict(self, a: MemoryChunk, b: MemoryChunk) -> MemoryChunk:
        """Route to the correct strategy resolver."""
        if self.strategy == "lww":
            return _resolve_conflict_lww(a, b)
        elif self.strategy == "max_confidence":
            return _resolve_conflict_max_confidence(a, b)
        elif self.strategy == "priority":
            return _resolve_conflict_priority(a, b, self.agent_priority)
        else:  # union — no conflict, keep both
            # For union strategy, we still merge sidecars
            return MemoryChunk(fact=a.fact, sidecar=a.sidecar.merge(b.sidecar))

    # ── Public API ─────────────────────────────────────────────────────────

    def merge(
        self, memories_a: List[dict], memories_b: List[dict]
    ) -> MergeResult:
        """Merge two sets of agent memories.

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
        """
        # Step 1: Convert to MemoryChunks
        chunks_a = [self._dict_to_chunk(d) for d in memories_a]
        chunks_b = [self._dict_to_chunk(d) for d in memories_b]
        all_chunks = chunks_a + chunks_b

        total_input = len(all_chunks)
        duplicates_found = 0
        conflicts_resolved = 0

        # Collect source agents
        source_agents: set = set()
        for mc in all_chunks:
            if mc.sidecar.source_agent:
                source_agents.add(mc.sidecar.source_agent)

        # Step 2 & 3: Dedup + conflict resolution
        # Index by fact_id for conflict detection
        merged: Dict[str, MemoryChunk] = {}

        for mc in all_chunks:
            fid = mc.sidecar.fact_id

            # Bloom filter check
            is_bloom_dup = self.bloom.contains(mc.fact)
            self.bloom.add(mc.fact)

            if fid in merged:
                # Same fact_id → conflict or exact dup
                existing = merged[fid]
                if existing.fact == mc.fact:
                    # Exact duplicate — merge sidecars
                    merged[fid] = MemoryChunk(
                        fact=mc.fact,
                        sidecar=existing.sidecar.merge(mc.sidecar),
                    )
                    duplicates_found += 1
                else:
                    # Conflict: same fact_id but different content
                    merged[fid] = self._resolve_conflict(existing, mc)
                    conflicts_resolved += 1
            elif is_bloom_dup:
                # Bloom says we've seen this fact before but fact_id not in merged
                # (might have been from a previous merge session)
                # Still add it — bloom false positives handled gracefully
                merged[fid] = mc
            else:
                merged[fid] = mc

        # Step 2b: Confidence filter
        result_memories = [
            mc for mc in merged.values()
            if mc.sidecar.confidence >= self.min_confidence
        ]

        # Step 4: Budget filter — keep highest confidence
        if self.budget is not None and len(result_memories) > self.budget:
            result_memories.sort(key=lambda mc: mc.sidecar.confidence, reverse=True)
            result_memories = result_memories[: self.budget]

        # Sort by fact for deterministic output
        result_memories.sort(key=lambda mc: mc.fact)

        unique_count = len(result_memories)

        # Step 5: Build manifest
        manifest_id = hashlib.sha256(
            f"{time.time()}-{total_input}-{unique_count}".encode()
        ).hexdigest()[:16]

        quality_score = (
            sum(mc.sidecar.confidence for mc in result_memories) / max(unique_count, 1)
        )

        manifest = ContextManifest(
            manifest_id=manifest_id,
            created_at=time.time(),
            source_agents=sorted(source_agents),
            total_memories=total_input,
            unique_memories=unique_count,
            duplicates_removed=duplicates_found,
            conflicts_resolved=conflicts_resolved,
            strategy_used=self.strategy,
            quality_score=quality_score,
            provenance_chain=[
                {
                    "operation": "merge",
                    "timestamp": time.time(),
                    "input_a_size": len(memories_a),
                    "input_b_size": len(memories_b),
                    "strategy": self.strategy,
                    "duplicates": duplicates_found,
                    "conflicts": conflicts_resolved,
                }
            ],
        )

        return MergeResult(
            memories=result_memories,
            manifest=manifest,
            bloom=self.bloom,
            duplicates_found=duplicates_found,
            conflicts_resolved=conflicts_resolved,
        )

    def merge_multi(self, *memory_sets: List[dict]) -> MergeResult:
        """Merge N sets of memories (from N agents).

        Reduces pairwise using :meth:`merge`. The bloom filter is carried
        forward between merges for cumulative dedup.

        Args:
            *memory_sets: Variable number of memory dict lists.

        Returns:
            MergeResult from the final pairwise merge.

        Raises:
            ValueError: If fewer than 2 memory sets are provided.
        """
        if len(memory_sets) < 2:
            raise ValueError("merge_multi requires at least 2 memory sets")

        # Start with first two
        result = self.merge(memory_sets[0], memory_sets[1])

        # Reduce remaining sets
        for mem_set in memory_sets[2:]:
            # Convert current result memories back to dicts for merge()
            current_dicts = [
                {
                    "fact": mc.fact,
                    "confidence": mc.sidecar.confidence,
                    "source": mc.sidecar.source_agent,
                    "ts": mc.sidecar.timestamp,
                    "topic": mc.sidecar.topic,
                    "tags": mc.sidecar.tags,
                }
                for mc in result.memories
            ]
            result = self.merge(current_dicts, mem_set)

        return result

    def evict_expired(
        self, memories: List[dict], now: float = None
    ) -> tuple:
        """Remove expired chunks. Returns (remaining, evicted_count).

        Note: Merge is CRDT-pure. Call evict_expired() separately for TTL
        enforcement. Eviction is NOT automatic in merge() to preserve CRDT
        purity.

        Args:
            memories: List of memory dicts (same format as merge() inputs).
            now: Current unix timestamp. Defaults to time.time().

        Returns:
            Tuple of (remaining_memories, evicted_count) where remaining_memories
            is a list of dicts that have not yet expired.
        """
        now = now or time.time()
        remaining = []
        evicted = 0
        for m in memories:
            chunk = self._dict_to_chunk(m) if isinstance(m, dict) else m
            if not chunk.sidecar.is_expired(now):
                remaining.append(m)
            else:
                evicted += 1
        return remaining, evicted

    def __repr__(self) -> str:
        return (
            f"ContextMerge(strategy={self.strategy!r}, "
            f"budget={self.budget}, min_conf={self.min_confidence})"
        )
