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
ContextManifest — self-describing merge attestation package.

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
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContextManifest:
    """Self-describing merge attestation package.

    Records what was merged, which strategies were used, timestamps,
    quality scores, and provenance chain.

    Attributes:
        manifest_id: Unique identifier for this manifest.
        created_at: Unix timestamp when the manifest was created.
        source_agents: Sorted list of contributing agent identifiers.
        total_memories: Total number of input memories before dedup.
        unique_memories: Number of memories after dedup.
        duplicates_removed: Number of duplicates caught.
        conflicts_resolved: Number of conflicts resolved via strategy.
        strategy_used: Name of the merge strategy applied.
        quality_score: Overall quality score in [0.0, 1.0].
        provenance_chain: Ordered list of merge operation records.

    Examples:
        >>> m = ContextManifest(
        ...     manifest_id="m1", created_at=1000.0,
        ...     source_agents=["agent-a"], total_memories=100,
        ...     unique_memories=80, duplicates_removed=20,
        ...     conflicts_resolved=5, strategy_used="lww",
        ...     quality_score=0.9, provenance_chain=[]
        ... )
        >>> m.summary()
        'Manifest m1: 100 memories → 80 unique (20 dups, 5 conflicts) via lww [quality=0.90]'
    """

    manifest_id: str
    created_at: float
    source_agents: List[str]
    total_memories: int
    unique_memories: int
    duplicates_removed: int
    conflicts_resolved: int
    strategy_used: str
    quality_score: float
    provenance_chain: List[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize fields at creation for CRDT idempotency.

        Ensures source_agents is sorted and provenance_chain is
        deterministically ordered so that merge(A, A) == A.
        """
        self.source_agents = sorted(self.source_agents)
        # Deduplicate and sort provenance chain deterministically
        seen: set = set()
        unique_prov: List[dict] = []
        for entry in self.provenance_chain:
            key = repr(sorted(entry.items()))
            if key not in seen:
                seen.add(key)
                unique_prov.append(dict(entry))
        unique_prov.sort(
            key=lambda e: (e.get("timestamp", 0.0), repr(sorted(e.items())))
        )
        self.provenance_chain = unique_prov

    # ── Display ────────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Human-readable one-line summary.

        Returns:
            Summary string with key metrics.
        """
        return (
            f"Manifest {self.manifest_id}: "
            f"{self.total_memories} memories → {self.unique_memories} unique "
            f"({self.duplicates_removed} dups, {self.conflicts_resolved} conflicts) "
            f"via {self.strategy_used} [quality={self.quality_score:.2f}]"
        )

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full serialisation to a plain dict.

        Returns:
            Dictionary representation suitable for JSON serialisation.
        """
        return {
            "manifest_id": self.manifest_id,
            "created_at": self.created_at,
            "source_agents": list(self.source_agents),
            "total_memories": self.total_memories,
            "unique_memories": self.unique_memories,
            "duplicates_removed": self.duplicates_removed,
            "conflicts_resolved": self.conflicts_resolved,
            "strategy_used": self.strategy_used,
            "quality_score": self.quality_score,
            "provenance_chain": [dict(p) for p in self.provenance_chain],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContextManifest:
        """Deserialize from a dict produced by :meth:`to_dict`.

        Args:
            d: Dictionary with manifest fields.

        Returns:
            A new ContextManifest instance.
        """
        return cls(
            manifest_id=d["manifest_id"],
            created_at=d["created_at"],
            source_agents=list(d.get("source_agents", [])),
            total_memories=d.get("total_memories", 0),
            unique_memories=d.get("unique_memories", 0),
            duplicates_removed=d.get("duplicates_removed", 0),
            conflicts_resolved=d.get("conflicts_resolved", 0),
            strategy_used=d.get("strategy_used", ""),
            quality_score=d.get("quality_score", 0.0),
            provenance_chain=[dict(p) for p in d.get("provenance_chain", [])],
        )

    # ── CRDT Merge ─────────────────────────────────────────────────────────

    def merge(self, other: ContextManifest) -> ContextManifest:
        """Merge two manifests.

        Merge semantics (all commutative, associative, idempotent):
          - ``manifest_id``: deterministic — derived from sorted union of IDs.
          - ``created_at``: max (LWW).
          - ``source_agents``: sorted set union.
          - ``total_memories``: max (grow-only).
          - ``unique_memories``: max (grow-only).
          - ``duplicates_removed``: max (grow-only).
          - ``conflicts_resolved``: max (grow-only).
          - ``strategy_used``: deterministic — max(str) for commutativity.
          - ``quality_score``: max (optimistic bound).
          - ``provenance_chain``: deduplicated union, sorted by timestamp then repr.

        Args:
            other: Another ContextManifest.

        Returns:
            A new merged ContextManifest.
        """
        # Source agents: sorted set union
        merged_agents = sorted(set(self.source_agents) | set(other.source_agents))

        # Strategy: deterministic tie-break
        if self.strategy_used and other.strategy_used:
            merged_strategy = max(self.strategy_used, other.strategy_used)
        else:
            merged_strategy = self.strategy_used or other.strategy_used

        # Provenance: deduplicated union sorted by (timestamp, repr) for determinism
        seen_reprs: set = set()
        merged_provenance: List[dict] = []
        for entry in self.provenance_chain + other.provenance_chain:
            entry_repr = repr(sorted(entry.items()))
            if entry_repr not in seen_reprs:
                seen_reprs.add(entry_repr)
                merged_provenance.append(dict(entry))
        # Sort by timestamp (if present) then by repr for full determinism
        merged_provenance.sort(
            key=lambda e: (e.get("timestamp", 0.0), repr(sorted(e.items())))
        )

        # Manifest ID: max of the two IDs — commutative, associative, idempotent
        merged_id = max(self.manifest_id, other.manifest_id)

        return ContextManifest(
            manifest_id=merged_id,
            created_at=max(self.created_at, other.created_at),
            source_agents=merged_agents,
            total_memories=max(self.total_memories, other.total_memories),
            unique_memories=max(self.unique_memories, other.unique_memories),
            duplicates_removed=max(self.duplicates_removed, other.duplicates_removed),
            conflicts_resolved=max(self.conflicts_resolved, other.conflicts_resolved),
            strategy_used=merged_strategy,
            quality_score=max(self.quality_score, other.quality_score),
            provenance_chain=merged_provenance,
        )

    # ── Dunder ─────────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContextManifest):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"ContextManifest(id={self.manifest_id!r}, agents={self.source_agents}, "
            f"unique={self.unique_memories}, quality={self.quality_score:.2f})"
        )
