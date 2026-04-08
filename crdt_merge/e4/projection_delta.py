# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Projection delta encoding for efficient state synchronization.

Implements the projection delta encoder (ref 810-814) from the E4
architecture.  Changed elements are identified via O(log_B n) high-arity
Merkle tree traversal (B = branching factor, default 256), then encoded
as a sparse delta containing only modified elements.

ProjectionDelta is a frozen dataclass carrying:
  - changed subtree references (minimal set)
  - sparse element changes (insertions, updates, deletions)
  - an aggregate PCO for verification
  - compression metadata

Deltas support associative composition:
  delta(A->B) . delta(B->C) = delta(A->C)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef


# -- Frozen dict wrapper ------------------------------------------------

class FrozenDict(Mapping):
    """Immutable dictionary for use in frozen dataclasses."""

    __slots__ = ("_data", "_hash")

    def __init__(self, data: Optional[Mapping] = None, **kwargs):
        object.__setattr__(self, "_data", dict(data or {}, **kwargs))
        object.__setattr__(self, "_hash", None)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __hash__(self):
        h = object.__getattribute__(self, "_hash")
        if h is None:
            h = hash(tuple(sorted(self._data.items())))
            object.__setattr__(self, "_hash", h)
        return h

    def __eq__(self, other):
        if isinstance(other, FrozenDict):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __repr__(self):
        return f"FrozenDict({self._data!r})"


# -- Compression helpers -----------------------------------------------

VALID_ENCODINGS = ("raw", "sparse", "quantized")


def _compress_sparse(
    insertions: FrozenDict,
    updates: FrozenDict,
    deletions: FrozenSet[str],
) -> Tuple[FrozenDict, FrozenDict, FrozenSet[str], float]:
    """Strip zero-diff updates and compute compression ratio."""
    live_updates = {
        k: v for k, v in updates.items() if v[0] != hashlib.sha256(v[1]).hexdigest()
    }
    total_raw = len(insertions) + len(updates) + len(deletions)
    total_sparse = len(insertions) + len(live_updates) + len(deletions)
    ratio = total_raw / max(total_sparse, 1)
    return (
        insertions,
        FrozenDict(live_updates),
        deletions,
        ratio,
    )


def _compress_quantized(
    insertions: FrozenDict,
    updates: FrozenDict,
    deletions: FrozenSet[str],
    bits: int = 8,
) -> Tuple[FrozenDict, FrozenDict, FrozenSet[str], float]:
    """Quantize values to *bits* precision for bandwidth savings."""
    mask = (1 << bits) - 1

    def quantize(val: bytes) -> bytes:
        # truncate each byte to the top `bits` significant bits
        return bytes(b & mask for b in val)

    q_ins = FrozenDict({k: quantize(v) for k, v in insertions.items()})
    q_upd = FrozenDict({k: (v[0], quantize(v[1])) for k, v in updates.items()})

    raw_bytes = sum(len(v) for v in insertions.values())
    raw_bytes += sum(len(v[1]) for v in updates.values())
    quant_bytes = sum(len(v) for v in q_ins.values())
    quant_bytes += sum(len(v[1]) for v in q_upd.values())
    ratio = raw_bytes / max(quant_bytes, 1)
    return q_ins, q_upd, deletions, ratio


# -- ProjectionDelta (ref 810) -----------------------------------------

@dataclass(frozen=True)
class ProjectionDelta:
    # Resilience: optional semantic validator (v0.9.5.1)
    _semantic_validator = None

    @classmethod
    def enable_semantic_validation(cls, **kwargs):
        """Enable semantic validation for incoming deltas.

        Validates that delta payloads contain statistically reasonable
        parameter values, detecting poisoned or corrupted updates before
        they enter the CRDT merge pipeline.

        See: resilience/semantic_validator.py (addresses Okonkwo §7, Nair §13)
        """
        from crdt_merge.e4.resilience.semantic_validator import (
            CompositeSemanticValidator, MagnitudeValidator, StatisticalShiftDetector,
        )
        cls._semantic_validator = CompositeSemanticValidator([
            MagnitudeValidator(**{k: v for k, v in kwargs.items() if k in ('max_magnitude', 'critical_regions')}),
            StatisticalShiftDetector(**{k: v for k, v in kwargs.items() if k in ('warmup_samples', 'shift_threshold')}),
        ])

    @classmethod
    def disable_semantic_validation(cls):
        """Disable semantic validation."""
        cls._semantic_validator = None

    """Sparse delta encoding for efficient CRDT state synchronization.

    Identifies changed elements via O(log_B n) high-arity Merkle tree
    traversal (B default 256), then encodes only modified elements.
    Achieves O(k * depth) ~ O(k) for practical sizes.
    """

    source_id: str
    source_version: object      # VectorClock (typed loosely to avoid circular dep)
    target_version: object      # VectorClock

    changed_subtrees: Tuple[SubtreeRef, ...]

    insertions: FrozenDict      # key -> new_value (bytes)
    updates: FrozenDict         # key -> (old_hash, new_value)
    deletions: FrozenSet[str]

    pco: AggregateProofCarryingOperation

    encoding: str = "raw"
    compression_ratio: float = 1.0

    # -- emptiness ------------------------------------------------------

    def is_empty(self) -> bool:
        """True when the delta carries no changes."""
        return not self.insertions and not self.updates and not self.deletions

    # -- associative composition ----------------------------------------

    def compose(self, other: ProjectionDelta) -> ProjectionDelta:
        """Associative chaining: delta(A->B) . delta(B->C) = delta(A->C).

        Insertions, updates, and deletions are merged according to
        CRDT delta-state composition rules.
        """
        # Merge insertions: B's insertions override A's
        merged_ins = dict(self.insertions)
        # Keys inserted in A then updated in B become insertions with B's value
        for k, v in other.insertions.items():
            merged_ins[k] = v

        # Merge updates
        merged_upd = dict(self.updates)
        for k, (old_h, new_v) in other.updates.items():
            if k in merged_ins:
                # was an insertion in A->B, now updated in B->C -> still insertion
                merged_ins[k] = new_v
            elif k in merged_upd:
                # chain: keep A's old_hash, take C's new_value
                merged_upd[k] = (merged_upd[k][0], new_v)
            else:
                merged_upd[k] = (old_h, new_v)

        # Merge deletions
        merged_del = set(self.deletions)
        merged_del |= other.deletions
        # If a key was inserted in A->B and deleted in B->C, it cancels out
        for k in other.deletions:
            merged_ins.pop(k, None)
            merged_upd.pop(k, None)
        # If a key was deleted in A->B and inserted in B->C, the insertion wins
        for k in other.insertions:
            merged_del.discard(k)

        # Merge subtree refs (union, deduplicated by path)
        seen_paths: dict[Tuple[int, ...], SubtreeRef] = {}
        for s in self.changed_subtrees:
            seen_paths[s.path] = s
        for s in other.changed_subtrees:
            if s.path in seen_paths:
                # extend range: keep earliest old_hash, latest new_hash
                prev = seen_paths[s.path]
                seen_paths[s.path] = SubtreeRef(
                    path=s.path,
                    depth=max(prev.depth, s.depth),
                    old_hash=prev.old_hash,
                    new_hash=s.new_hash,
                )
            else:
                seen_paths[s.path] = s

        return ProjectionDelta(
            source_id=self.source_id,
            source_version=self.source_version,
            target_version=other.target_version,
            changed_subtrees=tuple(seen_paths.values()),
            insertions=FrozenDict(merged_ins),
            updates=FrozenDict(merged_upd),
            deletions=frozenset(merged_del),
            pco=other.pco,  # use the most recent PCO
            encoding=self.encoding,
            compression_ratio=self.compression_ratio,
        )

    # -- compression ----------------------------------------------------

    def compress(self, encoding: str = "sparse", **kwargs) -> ProjectionDelta:
        """Return a compressed copy of this delta.

        Supported encodings:
          raw       -- no compression (identity)
          sparse    -- strip zero-diff updates
          quantized -- reduce value precision
        """
        if encoding not in VALID_ENCODINGS:
            raise ValueError(f"unknown encoding: {encoding}")

        if encoding == "raw":
            return ProjectionDelta(
                source_id=self.source_id,
                source_version=self.source_version,
                target_version=self.target_version,
                changed_subtrees=self.changed_subtrees,
                insertions=self.insertions,
                updates=self.updates,
                deletions=self.deletions,
                pco=self.pco,
                encoding="raw",
                compression_ratio=1.0,
            )

        if encoding == "sparse":
            ins, upd, dels, ratio = _compress_sparse(
                self.insertions, self.updates, self.deletions,
            )
        else:
            ins, upd, dels, ratio = _compress_quantized(
                self.insertions, self.updates, self.deletions,
                bits=kwargs.get("bits", 8),
            )

        return ProjectionDelta(
            source_id=self.source_id,
            source_version=self.source_version,
            target_version=self.target_version,
            changed_subtrees=self.changed_subtrees,
            insertions=ins,
            updates=upd,
            deletions=dels,
            pco=self.pco,
            encoding=encoding,
            compression_ratio=ratio,
        )

    # -- PCO replacement ------------------------------------------------

    def with_pco(self, pco: AggregateProofCarryingOperation) -> ProjectionDelta:
        """Return a copy with a new aggregate PCO attached."""
        return ProjectionDelta(
            source_id=self.source_id,
            source_version=self.source_version,
            target_version=self.target_version,
            changed_subtrees=self.changed_subtrees,
            insertions=self.insertions,
            updates=self.updates,
            deletions=self.deletions,
            pco=pco,
            encoding=self.encoding,
            compression_ratio=self.compression_ratio,
        )

    # -- content hash ---------------------------------------------------

    def content_hash(self) -> str:
        """Deterministic hash of the delta content (excluding PCO)."""
        h = hashlib.sha256()
        h.update(self.source_id.encode("utf-8"))
        for s in self.changed_subtrees:
            h.update(f"{s.path}:{s.old_hash}:{s.new_hash}".encode("utf-8"))
        for k in sorted(self.insertions):
            h.update(k.encode("utf-8"))
            h.update(self.insertions[k])
        for k in sorted(self.updates):
            old_h, new_v = self.updates[k]
            h.update(k.encode("utf-8"))
            h.update(old_h.encode("utf-8") if isinstance(old_h, str) else old_h)
            h.update(new_v)
        for k in sorted(self.deletions):
            h.update(k.encode("utf-8"))
        return h.hexdigest()

    # -- repr -----------------------------------------------------------

    def __repr__(self) -> str:
        n_changes = len(self.insertions) + len(self.updates) + len(self.deletions)
        return (
            f"ProjectionDelta(src={self.source_id!r}, "
            f"subtrees={len(self.changed_subtrees)}, "
            f"changes={n_changes}, enc={self.encoding!r})"
        )


# -- ProjectionDeltaManager --------------------------------------------

class ProjectionDeltaManager:
    """Manages delta lifecycle: creation, composition, and compression.

    Maintains a log of recent deltas per peer for efficient composition
    when a recipient is multiple versions behind.
    """

    def __init__(self, *, max_history: int = 64):
        self._history: Dict[str, list[ProjectionDelta]] = {}
        self._max_history = max_history

    def record(self, delta: ProjectionDelta) -> None:
        """Append *delta* to the per-peer history log."""
        peer = delta.source_id
        log = self._history.setdefault(peer, [])
        log.append(delta)
        if len(log) > self._max_history:
            self._history[peer] = log[-self._max_history :]

    def compose_range(
        self,
        peer_id: str,
        start: int = 0,
        end: Optional[int] = None,
    ) -> Optional[ProjectionDelta]:
        """Compose a contiguous range of deltas for *peer_id*.

        Returns None if the peer has no recorded deltas or the range is
        empty.
        """
        log = self._history.get(peer_id, [])
        if not log:
            return None
        sliced = log[start:end]
        if not sliced:
            return None
        result = sliced[0]
        for d in sliced[1:]:
            result = result.compose(d)
        return result

    def latest(self, peer_id: str) -> Optional[ProjectionDelta]:
        """Return the most recent delta from *peer_id*, or None."""
        log = self._history.get(peer_id, [])
        return log[-1] if log else None

    def clear(self, peer_id: Optional[str] = None) -> None:
        """Clear history for a specific peer, or all peers."""
        if peer_id is not None:
            self._history.pop(peer_id, None)
        else:
            self._history.clear()

    def peers(self) -> list[str]:
        """Return peer IDs with recorded deltas."""
        return list(self._history)
