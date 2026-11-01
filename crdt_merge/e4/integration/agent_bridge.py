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

"""Trust-aware agent state bridge (ref 1157).

Wraps agent state management to incorporate trust provenance into
context merges.  Agent memory entries are treated as CRDTs with trust
annotations: each entry tracks which peer contributed it and at what
trust level.

Trust-weighted context merge ensures that context from high-trust
peers dominates when entries conflict, while low-trust context is
retained but de-prioritised.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
    from crdt_merge.e4.typed_trust import TypedTrustScore


# -- Trust-annotated memory entry ------------------------------------------

@dataclass
class TrustAnnotatedEntry:
    """Single memory entry with trust provenance.

    Attributes
    ----------
    key         : Entry key in the agent state.
    value       : The payload.
    peer_id     : Peer that contributed this entry.
    trust_at_write : Overall trust of the peer at write time.
    timestamp   : Logical or wall-clock timestamp.
    tag         : Globally unique identifier of the write that created this
                  entry (assigned by :meth:`TrustAgentState.put`).  Deletes
                  tombstone tags, never keys, so they replicate causally.
                  Entries built without a tag get a deterministic legacy tag
                  derived from their content.
    """

    key: str
    value: Any
    peer_id: str
    trust_at_write: float
    timestamp: float = 0.0
    tag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "peer_id": self.peer_id,
            "trust_at_write": self.trust_at_write,
            "timestamp": self.timestamp,
            "tag": _tag_of(self),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrustAnnotatedEntry":
        return cls(
            key=d["key"],
            value=d["value"],
            peer_id=d["peer_id"],
            trust_at_write=d["trust_at_write"],
            timestamp=d.get("timestamp", 0.0),
            tag=d.get("tag", ""),
        )


def _tag_of(entry: TrustAnnotatedEntry) -> str:
    """Tag of *entry*; deterministic and content-derived for untagged entries."""
    if entry.tag:
        return entry.tag
    raw = f"{entry.key}\x1f{entry.peer_id}\x1f{entry.timestamp!r}\x1f{entry.value!r}"
    return "legacy:" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


# -- TrustAgentState -------------------------------------------------------

class TrustAgentState:
    """Agent memory as a CRDT with trust provenance.

    Every :meth:`put` is a uniquely tagged write.  :meth:`delete` is an
    observed-remove: it tombstones the tags this replica has seen for the
    key, so the delete replicates through :meth:`merge_context`, a stale
    replica cannot resurrect the key, and a concurrent put (a tag the
    deleter never observed) survives.  A new put by the same peer
    supersedes (tombstones) that peer's previous write for the key.
    Tombstones are kept for the lifetime of the state (no garbage
    collection) and travel with :meth:`to_dict`.

    Parameters
    ----------
    trust_lattice :
        Back-reference to the local DeltaTrustLattice for live trust
        lookups.
    trust_weight_context :
        When True, context merges are weighted by trust scores.
    """

    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        *,
        trust_weight_context: bool = True,
    ) -> None:
        self._trust_lattice = trust_lattice
        self._trust_weight_context = trust_weight_context
        # Visible (winning) live entry per key.
        self._entries: Dict[str, TrustAnnotatedEntry] = {}
        # Live concurrent writes that lost conflict resolution, per key.
        # Kept so that deleting the winner on another replica cannot hide
        # (or resurrect) them differently depending on merge order.
        self._shadow: Dict[str, Dict[str, TrustAnnotatedEntry]] = {}
        # Tags observed and removed.
        self._tombstones: Set[str] = set()

    # -- dependency injection ----------------------------------------------

    def bind_trust_lattice(self, lattice: DeltaTrustLattice) -> None:
        self._trust_lattice = lattice

    # -- read / write ------------------------------------------------------

    def get(self, key: str) -> Optional[TrustAnnotatedEntry]:
        return self._entries.get(key)

    def put(
        self,
        key: str,
        value: Any,
        peer_id: str,
        *,
        timestamp: float = 0.0,
    ) -> TrustAnnotatedEntry:
        """Write an entry with trust annotation.

        The peer's current trust is looked up from the lattice.
        """
        trust = self._resolve_trust(peer_id)
        entry = TrustAnnotatedEntry(
            key=key,
            value=value,
            peer_id=peer_id,
            trust_at_write=trust,
            timestamp=timestamp,
            tag=uuid.uuid4().hex,
        )
        versions = self._versions(key)
        # A peer's new write supersedes that peer's earlier writes (observed).
        for tag, old in list(versions.items()):
            if old.peer_id == peer_id:
                self._tombstones.add(tag)
                del versions[tag]
        versions[_tag_of(entry)] = entry
        self._install(key, versions)
        return self._entries[key]

    def delete(self, key: str) -> Optional[TrustAnnotatedEntry]:
        """Delete *key* with an observed-remove tombstone.

        Returns the entry that was visible, or ``None`` if there was none.
        The tombstones replicate on :meth:`merge_context`.
        """
        removed = self._entries.get(key)
        for tag in self._versions(key):
            self._tombstones.add(tag)
        self._entries.pop(key, None)
        self._shadow.pop(key, None)
        return removed

    # -- context merge (trust-weighted) ------------------------------------

    def merge_context(
        self,
        other: TrustAgentState,
    ) -> TrustAgentState:
        """Merge two agent states using trust-weighted conflict resolution.

        For each conflicting key the entry from the higher-trust peer
        wins.  When trust is equal, the later timestamp wins (LWW).
        """
        result = TrustAgentState(
            self._trust_lattice,
            trust_weight_context=self._trust_weight_context,
        )
        result._tombstones = self._tombstones | other._tombstones

        all_keys = set(self._entries) | set(other._entries) \
            | set(self._shadow) | set(other._shadow)
        for key in all_keys:
            versions = {
                tag: e
                for tag, e in {**other._versions(key), **self._versions(key)}.items()
                if tag not in result._tombstones
            }
            result._install(key, versions)

        return result

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise live writes and tombstones (values must be serialisable)."""
        keys = set(self._entries) | set(self._shadow)
        return {
            "type": "trust_agent_state",
            "version": 1,
            "trust_weight_context": self._trust_weight_context,
            "entries": {
                key: [e.to_dict() for _, e in sorted(self._versions(key).items())]
                for key in sorted(keys)
            },
            "tombstones": sorted(self._tombstones),
        }

    @classmethod
    def from_dict(
        cls,
        d: Dict[str, Any],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> "TrustAgentState":
        state = cls(
            trust_lattice,
            trust_weight_context=d.get("trust_weight_context", True),
        )
        state._tombstones = set(d.get("tombstones", ()))
        for key, items in d.get("entries", {}).items():
            versions = {}
            for item in items:
                e = TrustAnnotatedEntry.from_dict(item)
                if _tag_of(e) not in state._tombstones:
                    versions[_tag_of(e)] = e
            state._install(key, versions)
        return state

    # -- bulk export / import ----------------------------------------------

    def snapshot(self) -> Dict[str, TrustAnnotatedEntry]:
        return dict(self._entries)

    def load_snapshot(self, entries: Dict[str, TrustAnnotatedEntry]) -> None:
        """Replace the visible entries (local restore; tombstones are kept)."""
        self._entries = dict(entries)
        self._shadow = {}

    # -- trust-weighted ranking --------------------------------------------

    def ranked_entries(self) -> List[TrustAnnotatedEntry]:
        """Return entries sorted by trust at write time, descending."""
        return sorted(
            self._entries.values(),
            key=lambda e: e.trust_at_write,
            reverse=True,
        )

    # -- introspection -----------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._entries)

    def peer_contributions(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._entries.values():
            counts[entry.peer_id] = counts.get(entry.peer_id, 0) + 1
        return counts

    # -- internal ----------------------------------------------------------

    def _versions(self, key: str) -> Dict[str, TrustAnnotatedEntry]:
        """All live tagged writes for *key* (winner plus shadowed)."""
        versions = dict(self._shadow.get(key, {}))
        winner = self._entries.get(key)
        if winner is not None:
            versions[_tag_of(winner)] = winner
        return versions

    def _install(self, key: str, versions: Dict[str, TrustAnnotatedEntry]) -> None:
        """Set the live writes for *key* and recompute the visible winner."""
        if not versions:
            self._entries.pop(key, None)
            self._shadow.pop(key, None)
            return
        winner = None
        for entry in versions.values():
            winner = entry if winner is None else self._resolve_conflict(winner, entry)
        self._entries[key] = winner  # type: ignore[assignment]
        shadow = {t: e for t, e in versions.items() if e is not winner}
        if shadow:
            self._shadow[key] = shadow
        else:
            self._shadow.pop(key, None)

    def _resolve_trust(self, peer_id: str) -> float:
        if self._trust_lattice is not None:
            return self._trust_lattice.get_trust(peer_id).overall_trust()
        return 0.5  # Probation default

    def _resolve_conflict(
        self,
        a: TrustAnnotatedEntry,
        b: TrustAnnotatedEntry,
    ) -> TrustAnnotatedEntry:
        """Pick the winning entry in a conflict.

        When trust weighting is enabled, higher trust wins.
        On equal trust, later timestamp wins (LWW fallback).
        """
        if not self._trust_weight_context:
            return self._lww(a, b)

        a_trust = self._live_trust(a)
        b_trust = self._live_trust(b)

        if a_trust > b_trust:
            return a
        if b_trust > a_trust:
            return b
        # Equal trust -- LWW
        return self._lww(a, b)

    @staticmethod
    def _lww(a: TrustAnnotatedEntry, b: TrustAnnotatedEntry) -> TrustAnnotatedEntry:
        """Later timestamp wins; exact ties break on (peer_id, tag) so the
        outcome does not depend on argument order (commutative merge)."""
        if a.timestamp != b.timestamp:
            return a if a.timestamp > b.timestamp else b
        ka, kb = (a.peer_id, _tag_of(a)), (b.peer_id, _tag_of(b))
        if ka == kb:
            return a
        return a if ka > kb else b

    def _live_trust(self, entry: TrustAnnotatedEntry) -> float:
        """Get live trust for an entry's peer, falling back to stored."""
        if self._trust_lattice is not None:
            return self._trust_lattice.get_trust(entry.peer_id).overall_trust()
        return entry.trust_at_write
