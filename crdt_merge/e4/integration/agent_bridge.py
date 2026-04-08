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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

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
    """

    key: str
    value: Any
    peer_id: str
    trust_at_write: float
    timestamp: float = 0.0


# -- TrustAgentState -------------------------------------------------------

class TrustAgentState:
    """Agent memory as a CRDT with trust provenance.

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
        self._entries: Dict[str, TrustAnnotatedEntry] = {}

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
        )
        existing = self._entries.get(key)
        if existing is not None:
            entry = self._resolve_conflict(existing, entry)
        self._entries[key] = entry
        return entry

    def delete(self, key: str) -> Optional[TrustAnnotatedEntry]:
        return self._entries.pop(key, None)

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

        all_keys = set(self._entries) | set(other._entries)
        for key in all_keys:
            mine = self._entries.get(key)
            theirs = other._entries.get(key)
            if mine is None:
                result._entries[key] = theirs  # type: ignore[assignment]
            elif theirs is None:
                result._entries[key] = mine
            else:
                result._entries[key] = self._resolve_conflict(mine, theirs)

        return result

    # -- bulk export / import ----------------------------------------------

    def snapshot(self) -> Dict[str, TrustAnnotatedEntry]:
        return dict(self._entries)

    def load_snapshot(self, entries: Dict[str, TrustAnnotatedEntry]) -> None:
        self._entries = dict(entries)

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
            return a if a.timestamp >= b.timestamp else b

        a_trust = self._live_trust(a)
        b_trust = self._live_trust(b)

        if a_trust > b_trust:
            return a
        if b_trust > a_trust:
            return b
        # Equal trust -- LWW
        return a if a.timestamp >= b.timestamp else b

    def _live_trust(self, entry: TrustAnnotatedEntry) -> float:
        """Get live trust for an entry's peer, falling back to stored."""
        if self._trust_lattice is not None:
            return self._trust_lattice.get_trust(entry.peer_id).overall_trust()
        return entry.trust_at_write
