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
MemorySidecar — pre-computed metadata sidecar for a memory chunk.

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
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemorySidecar:
    """Pre-computed metadata sidecar for a memory chunk.

    Enables O(1) filtering without reading memory content.
    Every memory chunk gets a sidecar at creation time.

    Attributes:
        fact_id: Unique identifier derived from content hash (first 16 hex chars).
        content_hash: Full SHA-256 hex digest of the fact content.
        topic: Topic category for this memory (e.g., "weather", "user_prefs").
        confidence: Confidence score in [0.0, 1.0].
        source_agent: Identifier of the agent that produced this memory.
        timestamp: Unix timestamp when the sidecar was created.
        access_count: Number of times this memory has been accessed.
        ttl: Time-to-live in seconds. None means no expiry.
        tags: List of string tags for categorisation.
        metadata: Arbitrary key-value metadata dict.

    Examples:
        >>> sc = MemorySidecar.from_fact("The sky is blue", source_agent="agent-1", topic="science")
        >>> sc.matches_filter(topic="science")
        True
        >>> sc.is_expired()
        False
    """

    fact_id: str
    content_hash: str
    topic: str = ""
    confidence: float = 1.0
    source_agent: str = ""
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory ────────────────────────────────────────────────────────────

    @classmethod
    def from_fact(
        cls,
        fact: str,
        source_agent: str = "",
        topic: str = "",
        confidence: float = 1.0,
        **kwargs: Any,
    ) -> MemorySidecar:
        """Create a sidecar from a fact string.

        Args:
            fact: The fact content string.
            source_agent: Which agent produced this fact.
            topic: Topic category.
            confidence: Confidence score in [0.0, 1.0].
            **kwargs: Additional keyword arguments forwarded to the constructor
                (e.g., ``ttl``, ``tags``, ``metadata``).

        Returns:
            A new MemorySidecar instance.
        """
        content_hash = hashlib.sha256(fact.encode("utf-8")).hexdigest()
        fact_id = content_hash[:16]
        # Ensure tags are sorted at creation time for CRDT idempotency
        if "tags" in kwargs:
            kwargs["tags"] = sorted(kwargs["tags"])
        return cls(
            fact_id=fact_id,
            content_hash=content_hash,
            source_agent=source_agent,
            topic=topic,
            confidence=confidence,
            **kwargs,
        )

    # ── Queries ────────────────────────────────────────────────────────────

    def is_expired(self, now: Optional[float] = None) -> bool:
        """Check if this memory has expired based on its TTL.

        Args:
            now: Current unix timestamp. Defaults to ``time.time()``.

        Returns:
            True if the memory is past its TTL, False otherwise.
            Memories with ``ttl=None`` never expire.
        """
        if self.ttl is None:
            return False
        now = now if now is not None else time.time()
        return (now - self.timestamp) > self.ttl

    def matches_filter(
        self,
        topic: Optional[str] = None,
        min_confidence: float = 0.0,
        source_agent: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """O(1) filter check against sidecar metadata.

        All supplied criteria must match (AND semantics).
        Omitted criteria (None / 0.0) are ignored.

        Args:
            topic: Required topic. None means any topic matches.
            min_confidence: Minimum confidence threshold.
            source_agent: Required source agent. None means any agent matches.
            tags: Required tags (all must be present). None means no tag filter.

        Returns:
            True if this sidecar passes all filter criteria.
        """
        if topic is not None and self.topic != topic:
            return False
        if self.confidence < min_confidence:
            return False
        if source_agent is not None and self.source_agent != source_agent:
            return False
        if tags is not None and not set(tags).issubset(set(self.tags)):
            return False
        return True

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dict.

        Returns:
            Dictionary representation suitable for JSON serialisation.
        """
        return {
            "fact_id": self.fact_id,
            "content_hash": self.content_hash,
            "topic": self.topic,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "ttl": self.ttl,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemorySidecar:
        """Deserialize from a dict produced by :meth:`to_dict`.

        Args:
            d: Dictionary with sidecar fields.

        Returns:
            A new MemorySidecar instance.
        """
        return cls(
            fact_id=d["fact_id"],
            content_hash=d["content_hash"],
            topic=d.get("topic", ""),
            confidence=d.get("confidence", 1.0),
            source_agent=d.get("source_agent", ""),
            timestamp=d.get("timestamp", 0.0),
            access_count=d.get("access_count", 0),
            ttl=d.get("ttl"),
            tags=sorted(d.get("tags", [])),
            metadata=dict(d.get("metadata", {})),
        )

    # ── CRDT Merge ─────────────────────────────────────────────────────────

    def merge(self, other: MemorySidecar) -> MemorySidecar:
        """Merge two sidecars for the same fact.

        Merge semantics (all are commutative, associative, idempotent):
          - ``fact_id``, ``content_hash``: must match (same fact).
          - ``topic``: deterministic tie-break via max(str) for commutativity.
          - ``confidence``: max wins (grow-only).
          - ``source_agent``: deterministic tie-break via max(str).
          - ``timestamp``: max wins (LWW).
          - ``access_count``: max wins (grow-only counter).
          - ``ttl``: max wins (longer TTL is more permissive); None beats any value.
          - ``tags``: set union, sorted for determinism.
          - ``metadata``: key-level merge — for each key, max(str(value)) wins.

        Args:
            other: Another MemorySidecar (ideally for the same fact).

        Returns:
            A new merged MemorySidecar instance.
        """
        # Determine merged topic: pick the lexicographically larger non-empty
        # topic, or whichever is non-empty. This is commutative and idempotent.
        if self.topic and other.topic:
            merged_topic = max(self.topic, other.topic)
        else:
            merged_topic = self.topic or other.topic

        # Determine merged source_agent similarly
        if self.source_agent and other.source_agent:
            merged_source = max(self.source_agent, other.source_agent)
        else:
            merged_source = self.source_agent or other.source_agent

        # TTL: None means "never expires" -- it dominates any finite TTL.
        # Among two finite TTLs, max wins (more permissive).
        if self.ttl is None or other.ttl is None:
            merged_ttl: Optional[float] = None
        else:
            merged_ttl = max(self.ttl, other.ttl)

        # Tags: set union, sorted for determinism
        merged_tags = sorted(set(self.tags) | set(other.tags))

        # Metadata: per-key merge via deterministic max(str(value))
        all_meta_keys = set(self.metadata.keys()) | set(other.metadata.keys())
        merged_metadata: Dict[str, Any] = {}
        for k in all_meta_keys:
            v_a = self.metadata.get(k)
            v_b = other.metadata.get(k)
            if v_a is None:
                merged_metadata[k] = v_b
            elif v_b is None:
                merged_metadata[k] = v_a
            else:
                # Deterministic tie-break: max by string repr
                merged_metadata[k] = v_a if str(v_a) >= str(v_b) else v_b

        # Use fact_id/content_hash from whichever has the longer content_hash
        # (they should be identical for same-fact merges; this handles edge cases)
        merged_fact_id = max(self.fact_id, other.fact_id)
        merged_content_hash = max(self.content_hash, other.content_hash)

        return MemorySidecar(
            fact_id=merged_fact_id,
            content_hash=merged_content_hash,
            topic=merged_topic,
            confidence=max(self.confidence, other.confidence),
            source_agent=merged_source,
            timestamp=max(self.timestamp, other.timestamp),
            access_count=max(self.access_count, other.access_count),
            ttl=merged_ttl,
            tags=merged_tags,
            metadata=merged_metadata,
        )

    # ── Dunder ─────────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MemorySidecar):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"MemorySidecar(fact_id={self.fact_id!r}, topic={self.topic!r}, "
            f"confidence={self.confidence}, source={self.source_agent!r})"
        )
