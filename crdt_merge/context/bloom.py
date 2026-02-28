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
ContextBloom — 64-shard bloom filter for O(1) memory dedup.

Partitions the hash space into shards for parallel operation.
Each shard is an independent ``MergeableBloom`` from
:mod:`crdt_merge.probabilistic`.

Because each shard merges via bitwise OR, the composite merge is also
commutative, associative, and idempotent — a natural CRDT.

Expected performance: millions of checks/sec, sub-microsecond per check.

New in v0.8.2.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from crdt_merge.probabilistic import MergeableBloom


def _shard_index(fact: str, num_shards: int) -> int:
    """Deterministically map a fact to a shard index.

    Uses the first 8 bytes of the SHA-256 digest to get a uniform
    distribution across shards.
    """
    h = hashlib.sha256(fact.encode("utf-8")).digest()
    # Interpret first 8 bytes as big-endian unsigned int
    val = int.from_bytes(h[:8], "big")
    return val % num_shards


class ContextBloom:
    """64-shard bloom filter for memory dedup.

    Partitions the hash space into ``num_shards`` shards. Each shard is
    an independent :class:`MergeableBloom`. Facts are routed to exactly
    one shard based on a deterministic hash.

    Merge is per-shard ``MergeableBloom.merge`` (bitwise OR) — the whole
    structure is a CRDT.

    Args:
        expected_items: Expected total number of items across all shards.
        fp_rate: Target false-positive rate per shard.
        num_shards: Number of bloom-filter shards (default 64).

    Examples:
        >>> cb = ContextBloom(expected_items=10000, fp_rate=0.001)
        >>> was_dup = cb.add("the sky is blue")
        >>> cb.contains("the sky is blue")
        True
        >>> cb.contains("the sky is green")
        False
    """

    def __init__(
        self,
        expected_items: int = 100_000,
        fp_rate: float = 0.001,
        num_shards: int = 64,
    ) -> None:
        self.expected_items = expected_items
        self.fp_rate = fp_rate
        self.num_shards = num_shards
        # Distribute expected items evenly across shards
        per_shard = max(expected_items // num_shards, 16)
        self._shards: List[MergeableBloom] = [
            MergeableBloom(capacity=per_shard, fp_rate=fp_rate)
            for _ in range(num_shards)
        ]

    # ── Core API ───────────────────────────────────────────────────────────

    def add(self, fact: str) -> bool:
        """Add a fact to the bloom filter.

        Args:
            fact: The fact string to add.

        Returns:
            True if the fact was *probably* already present (duplicate),
            False if definitely new.
        """
        idx = _shard_index(fact, self.num_shards)
        shard = self._shards[idx]
        was_present = shard.contains(fact)
        shard.add(fact)
        return was_present

    def contains(self, fact: str) -> bool:
        """Check if a fact was seen before.

        Args:
            fact: The fact string to test.

        Returns:
            True if probably present, False if definitely absent.
        """
        idx = _shard_index(fact, self.num_shards)
        return self._shards[idx].contains(fact)

    # ── CRDT Merge ─────────────────────────────────────────────────────────

    def merge(self, other: ContextBloom) -> ContextBloom:
        """Merge two ContextBlooms by merging each shard pair.

        CRDT merge — commutative, associative, idempotent because each
        shard merge (bitwise OR) satisfies all three laws.

        Args:
            other: Another ContextBloom with the same configuration.

        Returns:
            A new merged ContextBloom.

        Raises:
            ValueError: If shard count or shard parameters differ.
        """
        if self.num_shards != other.num_shards:
            raise ValueError(
                f"Cannot merge ContextBlooms with different shard counts: "
                f"{self.num_shards} vs {other.num_shards}"
            )
        result = ContextBloom(
            expected_items=max(self.expected_items, other.expected_items),
            fp_rate=self.fp_rate,
            num_shards=self.num_shards,
        )
        # Replace the default shards with merged ones
        result._shards = [
            a.merge(b) for a, b in zip(self._shards, other._shards)
        ]
        return result

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dict.

        Returns:
            Dictionary suitable for JSON serialisation.
        """
        return {
            "type": "context_bloom",
            "expected_items": self.expected_items,
            "fp_rate": self.fp_rate,
            "num_shards": self.num_shards,
            "shards": [s.to_dict() for s in self._shards],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContextBloom:
        """Deserialize from a dict produced by :meth:`to_dict`.

        Args:
            d: Dictionary with bloom filter fields.

        Returns:
            A new ContextBloom instance.
        """
        obj = cls.__new__(cls)
        obj.expected_items = d["expected_items"]
        obj.fp_rate = d["fp_rate"]
        obj.num_shards = d["num_shards"]
        obj._shards = [MergeableBloom.from_dict(s) for s in d["shards"]]
        return obj

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def estimated_items(self) -> int:
        """Estimated total number of items across all shards.

        Returns:
            Sum of per-shard item count estimates.
        """
        return sum(s._count for s in self._shards)

    @property
    def false_positive_rate(self) -> float:
        """Estimated current false-positive rate (average across shards).

        Returns:
            Average estimated false-positive rate.
        """
        rates = [s.estimated_fp_rate() for s in self._shards]
        return sum(rates) / max(len(rates), 1)

    def estimated_fp_rate(self) -> float:
        """Alias for :attr:`false_positive_rate` — estimated false-positive rate."""
        return self.false_positive_rate

    # ── Dunder ─────────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ContextBloom):
            return NotImplemented
        if self.num_shards != other.num_shards:
            return False
        return all(a == b for a, b in zip(self._shards, other._shards))

    def __repr__(self) -> str:
        return (
            f"ContextBloom(shards={self.num_shards}, "
            f"est_items={self.estimated_items}, fp_rate={self.fp_rate})"
        )
