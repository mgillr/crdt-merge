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

"""Causal trust clock -- E2 entanglement (ref 860-863).

Vector clock where entries are (logical_time, trust_score) pairs.
Low-trust peers cannot causally dominate high-trust peers: even if a
low-trust peer has a higher logical time, the trust weight can override
the standard causal ordering.

Four comparison outcomes:
  before         -- strictly causally before (standard)
  after          -- strictly causally after (standard)
  concurrent     -- incomparable (standard)
  trust_override -- causally before but trust weight overrides

CRDT merge: element-wise max of logical time; on ties, take the higher
trust score.  This maintains the join-semilattice property required for
the product lattice convergence proof.
"""

from __future__ import annotations

import hashlib
import struct
from typing import TYPE_CHECKING, Dict, Optional, Set, Tuple

from .typed_trust import TypedTrustScore

if TYPE_CHECKING:
    from .delta_trust_lattice import DeltaTrustLattice


# -- CausalTrustClock (ref 860) --------------------------------------------

class CausalTrustClock:
    """Vector clock where entries carry trust scores.

    Parameters
    ----------
    peer_id :
        Identifier of the local peer that owns this clock.
    trust_lattice :
        Back-reference to the DeltaTrustLattice for trust lookups.
        Creates the E2 binding: causal ordering depends on trust, and
        trust changes are themselves causally ordered.
    """

    TRUST_OVERRIDE_FACTOR = 1.5

    def __init__(
        self,
        peer_id: str,
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> None:
        self._peer_id = peer_id
        self._entries: Dict[str, Tuple[int, float]] = {}
        self._trust_lattice = trust_lattice

    # -- dependency injection post-init ------------------------------------

    def bind_trust_lattice(self, lattice: DeltaTrustLattice) -> None:
        """Late-bind the trust lattice (resolves circular init order)."""
        self._trust_lattice = lattice

    # -- increment (ref 876-882) -------------------------------------------

    def increment(self) -> CausalTrustClock:
        """Increment local clock with current trust score.

        Returns a new clock instance (immutable-style API).
        """
        current_trust = 0.0
        if self._trust_lattice is not None:
            current_trust = (
                self._trust_lattice.get_trust(self._peer_id).overall_trust()
            )

        current_time = self._entries.get(self._peer_id, (0, 0.0))[0]
        result = CausalTrustClock(self._peer_id, self._trust_lattice)
        result._entries = dict(self._entries)
        result._entries[self._peer_id] = (current_time + 1, current_trust)
        return result

    # -- trust-weighted comparison (ref 884-894) ---------------------------

    def trust_weighted_compare(self, other: CausalTrustClock) -> str:
        """Compare with trust weighting.

        Returns one of:
          'before'         -- self is strictly causally before other
          'after'          -- self is strictly causally after other
          'concurrent'     -- incomparable under standard causality
          'trust_override' -- causally before, but local trust weight
                             exceeds remote by the override factor
        """
        standard = self._standard_compare(other)
        if standard == "before":
            self_weight = sum(t for _, t in self._entries.values())
            other_weight = sum(t for _, t in other._entries.values())
            if self_weight > other_weight * self.TRUST_OVERRIDE_FACTOR:
                return "trust_override"
        return standard

    # -- CRDT merge (ref 896-909) ------------------------------------------

    def merge(self, other: CausalTrustClock) -> CausalTrustClock:
        """CRDT merge: element-wise max of (time, trust) pairs.

        For each peer entry:
          - Higher logical time wins.
          - On equal logical time, higher trust wins.
        """
        result = CausalTrustClock(self._peer_id, self._trust_lattice)
        all_peers = set(self._entries) | set(other._entries)
        for peer in all_peers:
            s = self._entries.get(peer, (0, 0.0))
            o = other._entries.get(peer, (0, 0.0))
            if s[0] > o[0]:
                result._entries[peer] = s
            elif o[0] > s[0]:
                result._entries[peer] = o
            else:
                result._entries[peer] = (s[0], max(s[1], o[1]))
        return result

    # -- compact serialization for PCO embedding ---------------------------

    def serialize_compact(self) -> bytes:
        """Compact binary representation for aggregate PCO embedding.

        Format per entry: [peer_id_len: 2B][peer_id: varlen][time: 8B][trust: 8B]
        Entries sorted by peer_id for determinism.
        """
        parts: list[bytes] = []
        for pid in sorted(self._entries):
            t, trust = self._entries[pid]
            pid_bytes = pid.encode("utf-8")
            parts.append(struct.pack("!H", len(pid_bytes)))
            parts.append(pid_bytes)
            parts.append(struct.pack("!Qd", t, trust))
        return b"".join(parts)

    @classmethod
    def deserialize_compact(
        cls,
        data: bytes,
        peer_id: str,
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> CausalTrustClock:
        """Reconstruct a clock from compact bytes."""
        clock = cls(peer_id, trust_lattice)
        off = 0
        while off < len(data):
            if off + 2 > len(data):
                break
            pid_len = struct.unpack("!H", data[off : off + 2])[0]
            off += 2
            pid = data[off : off + pid_len].decode("utf-8")
            off += pid_len
            t, trust = struct.unpack("!Qd", data[off : off + 16])
            off += 16
            clock._entries[pid] = (t, trust)
        return clock

    # -- causality check for PCO verification ------------------------------

    def is_consistent_with(self, snapshot: bytes) -> bool:
        """Check if a serialized clock snapshot is causally consistent.

        Consistent means the snapshot is not strictly after our current
        state -- i.e. the snapshot doesn't claim to have seen events we
        haven't processed yet.
        """
        if not snapshot:
            return True
        remote = self.deserialize_compact(
            snapshot, self._peer_id, self._trust_lattice,
        )
        cmp = remote._standard_compare_against(self)
        return cmp != "after"

    # -- content hash (for Merkle binding) ---------------------------------

    def content_hash(self) -> str:
        """SHA-256 of the compact serialization."""
        return hashlib.sha256(self.serialize_compact()).hexdigest()

    # -- accessors ---------------------------------------------------------

    @property
    def peer_id(self) -> str:
        return self._peer_id

    @property
    def logical_time(self) -> int:
        """Local peer's logical time."""
        return self._entries.get(self._peer_id, (0, 0.0))[0]

    @property
    def entries(self) -> Dict[str, Tuple[int, float]]:
        return dict(self._entries)

    def known_peers(self) -> Set[str]:
        return set(self._entries)

    def get_entry(self, peer_id: str) -> Tuple[int, float]:
        return self._entries.get(peer_id, (0, 0.0))

    # -- internal comparison logic -----------------------------------------

    def _standard_compare(self, other: CausalTrustClock) -> str:
        """Standard vector clock comparison (no trust weighting)."""
        all_peers = set(self._entries) | set(other._entries)
        self_leq = True
        other_leq = True
        for p in all_peers:
            st = self._entries.get(p, (0, 0.0))[0]
            ot = other._entries.get(p, (0, 0.0))[0]
            if st > ot:
                other_leq = False
            if ot > st:
                self_leq = False

        if self_leq and other_leq:
            return "concurrent"  # identical
        if self_leq:
            return "before"
        if other_leq:
            return "after"
        return "concurrent"

    def _standard_compare_against(self, other: CausalTrustClock) -> str:
        """Compare self against other (used internally for consistency)."""
        return self._standard_compare(other)

    def __repr__(self) -> str:
        return (
            f"CausalTrustClock(peer={self._peer_id!r}, "
            f"time={self.logical_time}, "
            f"peers={len(self._entries)})"
        )
