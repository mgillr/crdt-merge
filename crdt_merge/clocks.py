# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Vector clocks and causality detection for distributed CRDT systems.

Provides VectorClock and DottedVersionVector — pure CRDT types for tracking
causal ordering of events across distributed nodes. Used by gossip protocols
and available independently for any distributed system.

Both types satisfy the CRDT convergence theorem:
  - Commutative:  merge(A, B) == merge(B, A)
  - Associative:  merge(merge(A, B), C) == merge(A, merge(B, C))
  - Idempotent:   merge(A, A) == A

Usage:
    from crdt_merge.clocks import VectorClock, Ordering

    a = VectorClock({"node1": 3, "node2": 1})
    b = VectorClock({"node1": 2, "node2": 4})
    merged = a.merge(b)  # VectorClock({"node1": 3, "node2": 4})
    assert a.compare(b) == Ordering.CONCURRENT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


class Ordering(Enum):
    """Causal ordering between two vector clocks."""

    BEFORE = "before"        # a happened-before b
    AFTER = "after"          # b happened-before a
    CONCURRENT = "concurrent"  # neither happened-before the other
    EQUAL = "equal"          # identical clocks


@dataclass
class VectorClock:
    """Vector clock for tracking causal ordering in distributed systems.

    Each node maintains its own logical counter. The element-wise max merge
    guarantees convergence across any number of replicas in any order.

    Invariants:
      - All counters are non-negative integers
      - Zero counters are stripped (treated as absent)
      - merge() returns a NEW instance — never mutates self or other
    """

    _clocks: Dict[str, int] = field(default_factory=dict)

    def __init__(self, clocks: Optional[Dict[str, int]] = None) -> None:
        """Create a vector clock from an optional {node_id: counter} dict.

        Args:
            clocks: Initial counter values. None or empty → no events seen.

        Raises:
            ValueError: If any counter is negative.
            TypeError: If any counter is not an int.
        """
        if clocks is None:
            self._clocks: Dict[str, int] = {}
        else:
            for k, v in clocks.items():
                if not isinstance(v, int) or isinstance(v, bool):
                    raise TypeError(
                        f"Clock values must be int, got {type(v).__name__}"
                    )
                if v < 0:
                    raise ValueError(
                        f"Clock values must be non-negative, got {v}"
                    )
            # Normalize: strip zero counters so VectorClock({"a": 0}) == VectorClock({})
            self._clocks = {k: v for k, v in clocks.items() if v > 0}

    # ── Queries ──────────────────────────────────────────────────────────

    def get(self, node_id: str) -> int:
        """Get the counter for *node_id* (0 if the node has never been seen)."""
        return self._clocks.get(node_id, 0)

    @property
    def value(self) -> Dict[str, int]:
        """Return a **copy** of the internal clock dict."""
        return dict(self._clocks)

    # ── Mutations (always return NEW instances) ──────────────────────────

    def increment(self, node_id: str) -> VectorClock:
        """Return a NEW clock with *node_id*'s counter incremented by 1."""
        new_clocks = dict(self._clocks)
        new_clocks[node_id] = new_clocks.get(node_id, 0) + 1
        return VectorClock(new_clocks)

    # ── Causal comparison ────────────────────────────────────────────────

    def compare(self, other: VectorClock) -> Ordering:
        """Compare two vector clocks for causal ordering.

        Returns:
            BEFORE:     all self[n] <= other[n] with at least one strict <
            AFTER:      all self[n] >= other[n] with at least one strict >
            EQUAL:      all counters identical
            CONCURRENT: otherwise (incomparable)
        """
        all_nodes = set(self._clocks) | set(other._clocks)
        if not all_nodes:
            return Ordering.EQUAL

        has_less = False
        has_greater = False

        for node in all_nodes:
            s = self._clocks.get(node, 0)
            o = other._clocks.get(node, 0)
            if s < o:
                has_less = True
            elif s > o:
                has_greater = True
            if has_less and has_greater:
                return Ordering.CONCURRENT

        if has_less and not has_greater:
            return Ordering.BEFORE
        if has_greater and not has_less:
            return Ordering.AFTER
        return Ordering.EQUAL

    # ── CRDT merge ───────────────────────────────────────────────────────

    def merge(self, other: VectorClock) -> VectorClock:
        """Element-wise max of two vector clocks. Returns a NEW instance.

        Satisfies: commutative, associative, idempotent.
        """
        all_nodes = set(self._clocks) | set(other._clocks)
        merged = {
            node: max(self._clocks.get(node, 0), other._clocks.get(node, 0))
            for node in all_nodes
        }
        return VectorClock(merged)

    # ── Serialization (CRDT trinity) ─────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        return {"type": "vector_clock", "clocks": dict(self._clocks)}

    @classmethod
    def from_dict(cls, d: dict) -> VectorClock:
        """Deserialize from a plain dict."""
        return cls(d.get("clocks", {}))

    # ── Dunder methods ───────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VectorClock):
            return NotImplemented
        return self._clocks == other._clocks

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._clocks.items())))

    def __repr__(self) -> str:
        return f"VectorClock({self._clocks})"


# ═════════════════════════════════════════════════════════════════════════════
# DottedVersionVector — causal context with a single outstanding event (dot)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class DottedVersionVector:
    """Dotted Version Vector for precise causality tracking.

    Combines a *base* VectorClock (what the node has seen) with an optional
    *dot* — a single ``(node_id, counter)`` tuple representing the latest
    event that has not yet been folded into the base.

    Key semantics:
      - ``advance(node)`` creates a new dot (does NOT touch the base).
      - ``merge()`` folds both dots into the merged base; the result's dot is
        always ``None``.
      - ``descends(other)`` checks if self causally follows other.
    """

    _base: VectorClock = field(default_factory=VectorClock)
    _dot: Optional[Tuple[str, int]] = None

    def __init__(
        self,
        base: Optional[VectorClock] = None,
        dot: Optional[Tuple[str, int]] = None,
    ) -> None:
        self._base = base if base is not None else VectorClock()
        self._dot = dot

    # ── Queries ──────────────────────────────────────────────────────────

    @property
    def value(self) -> Dict[str, int]:
        """Effective state: base with dot merged in."""
        result = dict(self._base.value)
        if self._dot is not None:
            node_id, counter = self._dot
            result[node_id] = max(result.get(node_id, 0), counter)
        return {k: v for k, v in result.items() if v > 0}

    @property
    def base(self) -> VectorClock:
        """The base vector clock (read-only copy)."""
        return VectorClock(self._base.value)

    @property
    def dot(self) -> Optional[Tuple[str, int]]:
        """The outstanding dot, or None."""
        return self._dot

    # ── Mutations (always return NEW instances) ──────────────────────────

    def advance(self, node_id: str) -> DottedVersionVector:
        """Advance the dot for *node_id*. Returns a NEW instance.

        The dot becomes ``(node_id, base.get(node_id) + 1)``.
        The base stays unchanged (it is only updated on merge).
        """
        new_counter = self._base.get(node_id) + 1
        return DottedVersionVector(
            base=VectorClock(self._base.value),
            dot=(node_id, new_counter),
        )

    # ── CRDT merge ───────────────────────────────────────────────────────

    def merge(self, other: DottedVersionVector) -> DottedVersionVector:
        """Merge two DVVs: merge bases, fold both dots into the new base.

        Returns a NEW instance whose dot is always ``None``.
        Satisfies: commutative, associative, idempotent (by effective value).
        """
        # Start with element-wise max of both bases
        merged = self._base.merge(other._base)
        merged_clocks = merged.value

        # Fold self's dot into the merged base
        if self._dot is not None:
            n, c = self._dot
            merged_clocks[n] = max(merged_clocks.get(n, 0), c)

        # Fold other's dot into the merged base
        if other._dot is not None:
            n, c = other._dot
            merged_clocks[n] = max(merged_clocks.get(n, 0), c)

        return DottedVersionVector(
            base=VectorClock(merged_clocks),
            dot=None,
        )

    # ── Causality ────────────────────────────────────────────────────────

    def descends(self, other: DottedVersionVector) -> bool:
        """Return True if *self* causally descends from (or equals) *other*.

        Self descends from other iff self's effective clock dominates other's
        effective clock on every node.
        """
        self_eff = self.value
        other_eff = other.value
        for node, counter in other_eff.items():
            if self_eff.get(node, 0) < counter:
                return False
        return True

    # ── Serialization (CRDT trinity) ─────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        result: dict = {
            "type": "dotted_version_vector",
            "base": self._base.to_dict(),
        }
        if self._dot is not None:
            result["dot"] = list(self._dot)
        return result

    @classmethod
    def from_dict(cls, d: dict) -> DottedVersionVector:
        """Deserialize from a plain dict."""
        base_data = d.get("base", {})
        base = VectorClock.from_dict(base_data) if base_data else VectorClock()
        dot_data = d.get("dot")
        dot: Optional[Tuple[str, int]] = tuple(dot_data) if dot_data is not None else None  # type: ignore[arg-type]
        return cls(base=base, dot=dot)

    # ── Dunder methods ───────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DottedVersionVector):
            return NotImplemented
        return self.value == other.value

    def __repr__(self) -> str:
        if self._dot is not None:
            return f"DottedVersionVector(base={self._base}, dot={self._dot})"
        return f"DottedVersionVector(base={self._base})"
