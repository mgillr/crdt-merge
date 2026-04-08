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

"""Dual-hash compatibility mode for E4 migration (ref 855, 945).

Manages the transition from pre-E4 peers (plain Merkle hashes) to the
E4 trust-bound hash scheme.  Three modes:

  E4_ONLY    -- only H(data || trust) hashes computed and exchanged
  DUAL_HASH  -- both H(data) and H(data || trust) maintained in parallel
  LEGACY_ONLY -- pre-E4 mode, only H(data)

Version detection via handshake: each peer announces its E4 capability
level.  The CompatibilityController picks the appropriate mode for each
peer pair and manages the migration lifecycle.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional, Set

if TYPE_CHECKING:
    from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle


# -- Compatibility modes ---------------------------------------------------

class CompatibilityMode(enum.Enum):
    E4_ONLY = "e4_only"
    DUAL_HASH = "dual_hash"
    LEGACY_ONLY = "legacy_only"


# -- Peer capability levels ------------------------------------------------

class PeerCapability(enum.Enum):
    PRE_E4 = 0
    E4_DUAL = 1
    E4_FULL = 2


# -- Handshake payload -----------------------------------------------------

@dataclass(frozen=True)
class CompatHandshake:
    """Exchanged during peer connection to negotiate hash mode.

    Attributes
    ----------
    peer_id    : Identifier of the announcing peer.
    capability : Self-reported E4 capability level.
    version    : Wire protocol version number.
    """

    peer_id: str
    capability: PeerCapability
    version: int = 1


# -- CompatibilityController -----------------------------------------------

class CompatibilityController:
    """Manages hash compatibility across mixed E4 / pre-E4 clusters.

    The controller tracks each peer's capability (learned through
    handshake) and determines the wire format to use for each peer
    pair.  It also drives the migration path:

        LEGACY_ONLY  ->  DUAL_HASH  ->  E4_ONLY

    Migration is per-peer: once BOTH sides support E4, the pair can
    graduate from DUAL_HASH to E4_ONLY.

    Parameters
    ----------
    default_mode :
        System-level default mode.  New peers without a handshake are
        assumed to use this mode.
    merkle :
        Optional reference to the trust-bound Merkle tree for toggling
        its compatibility flag.
    """

    def __init__(
        self,
        *,
        default_mode: CompatibilityMode = CompatibilityMode.E4_ONLY,
        merkle: Optional[TrustBoundMerkle] = None,
    ) -> None:
        self._default_mode = default_mode
        self._merkle = merkle
        self._peer_caps: Dict[str, PeerCapability] = {}
        self._negotiated: Dict[str, CompatibilityMode] = {}

    # -- dependency injection ----------------------------------------------

    def bind_merkle(self, merkle: TrustBoundMerkle) -> None:
        self._merkle = merkle

    # -- handshake ---------------------------------------------------------

    def process_handshake(self, hs: CompatHandshake) -> CompatibilityMode:
        """Record peer capability from a handshake and negotiate mode.

        Returns the mode that should be used for communication with
        *hs.peer_id*.
        """
        self._peer_caps[hs.peer_id] = hs.capability
        mode = self._negotiate(hs.capability)
        self._negotiated[hs.peer_id] = mode
        return mode

    def build_handshake(self, local_peer_id: str) -> CompatHandshake:
        """Build a handshake payload advertising local capability.

        Capability is inferred from the current default mode.
        """
        cap = _mode_to_capability(self._default_mode)
        return CompatHandshake(
            peer_id=local_peer_id,
            capability=cap,
        )

    # -- mode queries ------------------------------------------------------

    def mode_for_peer(self, peer_id: str) -> CompatibilityMode:
        """Effective mode for communicating with *peer_id*.

        Falls back to the system default if no handshake was received.
        """
        return self._negotiated.get(peer_id, self._default_mode)

    @property
    def default_mode(self) -> CompatibilityMode:
        return self._default_mode

    def set_default_mode(self, mode: CompatibilityMode) -> None:
        self._default_mode = mode

    # -- dual hash helpers -------------------------------------------------

    def compute_hashes(
        self,
        data: bytes,
        originator: str,
        peer_id: str,
    ) -> Dict[str, str]:
        """Compute the required hashes for *peer_id*.

        Returns a dict with keys ``"e4"`` and/or ``"legacy"`` depending
        on the negotiated mode.
        """
        mode = self.mode_for_peer(peer_id)
        result: Dict[str, str] = {}

        if self._merkle is not None:
            if mode in (CompatibilityMode.E4_ONLY, CompatibilityMode.DUAL_HASH):
                result["e4"] = self._merkle.compute_leaf_hash(data, originator)
            if mode in (CompatibilityMode.LEGACY_ONLY, CompatibilityMode.DUAL_HASH):
                result["legacy"] = self._merkle.compute_leaf_hash_compat(data)
        else:
            import hashlib
            if mode in (CompatibilityMode.E4_ONLY, CompatibilityMode.DUAL_HASH):
                result["e4"] = hashlib.sha256(data).hexdigest()
            if mode in (CompatibilityMode.LEGACY_ONLY, CompatibilityMode.DUAL_HASH):
                result["legacy"] = hashlib.sha256(data).hexdigest()

        return result

    # -- migration helpers -------------------------------------------------

    def peers_ready_for_e4_only(self) -> Set[str]:
        """Return peers that can be upgraded from DUAL_HASH to E4_ONLY."""
        ready: Set[str] = set()
        for pid, cap in self._peer_caps.items():
            if cap == PeerCapability.E4_FULL:
                if self._negotiated.get(pid) == CompatibilityMode.DUAL_HASH:
                    ready.add(pid)
        return ready

    def upgrade_peer(self, peer_id: str) -> CompatibilityMode:
        """Attempt to upgrade a peer to the next compatibility level.

        Returns the new mode after the upgrade attempt.
        """
        current = self._negotiated.get(peer_id, self._default_mode)
        cap = self._peer_caps.get(peer_id, PeerCapability.PRE_E4)

        if current == CompatibilityMode.LEGACY_ONLY and cap.value >= PeerCapability.E4_DUAL.value:
            self._negotiated[peer_id] = CompatibilityMode.DUAL_HASH
        elif current == CompatibilityMode.DUAL_HASH and cap == PeerCapability.E4_FULL:
            self._negotiated[peer_id] = CompatibilityMode.E4_ONLY
        return self._negotiated.get(peer_id, current)

    # -- introspection -----------------------------------------------------

    def known_peers(self) -> Dict[str, PeerCapability]:
        return dict(self._peer_caps)

    def peer_count_by_mode(self) -> Dict[CompatibilityMode, int]:
        counts: Dict[CompatibilityMode, int] = {m: 0 for m in CompatibilityMode}
        for mode in self._negotiated.values():
            counts[mode] += 1
        return counts

    # -- internal ----------------------------------------------------------

    def _negotiate(self, remote_cap: PeerCapability) -> CompatibilityMode:
        local_cap = _mode_to_capability(self._default_mode)

        if local_cap == PeerCapability.E4_FULL and remote_cap == PeerCapability.E4_FULL:
            return CompatibilityMode.E4_ONLY
        if local_cap == PeerCapability.PRE_E4 or remote_cap == PeerCapability.PRE_E4:
            # At least one side is pre-E4
            if local_cap == PeerCapability.PRE_E4 and remote_cap == PeerCapability.PRE_E4:
                return CompatibilityMode.LEGACY_ONLY
            return CompatibilityMode.DUAL_HASH
        # Both E4-aware but not both full
        return CompatibilityMode.DUAL_HASH


# -- helpers ---------------------------------------------------------------

def _mode_to_capability(mode: CompatibilityMode) -> PeerCapability:
    if mode == CompatibilityMode.E4_ONLY:
        return PeerCapability.E4_FULL
    if mode == CompatibilityMode.DUAL_HASH:
        return PeerCapability.E4_DUAL
    return PeerCapability.PRE_E4
