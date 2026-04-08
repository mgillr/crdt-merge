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

"""Unified data + trust gossip engine (ref 1010-1020).

Wraps a base gossip pattern to include trust deltas alongside data
deltas in sync payloads.  On receive, routes data deltas to the data
pipeline and trust deltas to the trust pipeline; both pass through
adaptive verification before application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from crdt_merge.e4.adaptive_verification import (
        AdaptiveVerificationController,
        VerificationResult,
    )
    from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
    from crdt_merge.e4.projection_delta import ProjectionDelta


# -- Sync payload ----------------------------------------------------------

@dataclass
class TrustGossipPayload:
    # Resilience: optional convergence monitor (v0.9.5.1)
    _convergence_monitor = None

    @classmethod
    def enable_convergence_monitoring(cls, peer_count: int = 100, **kwargs):
        """Enable convergence time monitoring and alerting.

        Tracks actual convergence times against theoretical bounds and
        alerts if the system is converging slower than expected.

        See: resilience/convergence_monitor.py (addresses Vasquez §2, Wei §19)
        """
        from crdt_merge.e4.resilience.convergence_monitor import ConvergenceMonitor
        cls._convergence_monitor = ConvergenceMonitor(peer_count, **kwargs)

    @classmethod
    def disable_convergence_monitoring(cls):
        """Disable convergence monitoring."""
        cls._convergence_monitor = None

    """Wire payload that bundles data and trust deltas.

    Attributes
    ----------
    data_deltas  : Regular CRDT data deltas.
    trust_deltas : Trust evidence deltas (same wire format).
    peer_id      : The sending peer.
    """

    data_deltas: List[ProjectionDelta] = field(default_factory=list)
    trust_deltas: List[ProjectionDelta] = field(default_factory=list)
    peer_id: str = ""


# -- TrustGossipEngine -----------------------------------------------------

class TrustGossipEngine:
    """Gossip engine that propagates both data and trust deltas.

    Parameters
    ----------
    trust_lattice :
        Back-reference to the local DeltaTrustLattice.
    verifier :
        Adaptive verification controller for incoming deltas.
    state :
        Local application state (passed to verification routines).
    """

    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
    ) -> None:
        self._trust_lattice = trust_lattice
        self._verifier = verifier
        self._state = state
        self._outbound: List[TrustGossipPayload] = []

    # -- dependency injection ----------------------------------------------

    def bind_trust_lattice(self, lattice: DeltaTrustLattice) -> None:
        self._trust_lattice = lattice

    def bind_verifier(self, verifier: AdaptiveVerificationController) -> None:
        self._verifier = verifier

    def bind_state(self, state: object) -> None:
        self._state = state

    # -- prepare outbound payload ------------------------------------------

    def prepare_sync(
        self,
        data_deltas: Sequence[ProjectionDelta],
        *,
        include_trust: bool = True,
    ) -> TrustGossipPayload:
        """Build a sync payload from pending data deltas.

        When *include_trust* is True, the payload also contains any
        pending trust deltas from the lattice's async queue.
        """
        peer_id = ""
        if self._trust_lattice is not None:
            peer_id = self._trust_lattice.peer_id

        trust_deltas: List[ProjectionDelta] = []
        if include_trust and self._trust_lattice is not None:
            trust_deltas = self._trust_lattice.drain_async_queue()

        payload = TrustGossipPayload(
            data_deltas=list(data_deltas),
            trust_deltas=trust_deltas,
            peer_id=peer_id,
        )
        self._outbound.append(payload)
        return payload

    # -- receive and route -------------------------------------------------

    def receive_sync(
        self,
        payload: TrustGossipPayload,
    ) -> Tuple[List[ProjectionDelta], List[ProjectionDelta]]:
        """Process an incoming sync payload.

        Returns two lists: (accepted_data_deltas, accepted_trust_deltas).
        Both go through adaptive verification.  Rejected deltas are
        silently dropped (counter-evidence is recorded inside the
        verifier).
        """
        accepted_data: List[ProjectionDelta] = []
        accepted_trust: List[ProjectionDelta] = []

        # Route data deltas
        for delta in payload.data_deltas:
            if self._verify_delta(delta):
                accepted_data.append(delta)

        # Route trust deltas through the lattice receive path
        for delta in payload.trust_deltas:
            if self._receive_trust_delta(delta):
                accepted_trust.append(delta)

        return accepted_data, accepted_trust

    # -- introspection -----------------------------------------------------

    @property
    def pending_outbound(self) -> int:
        return len(self._outbound)

    def drain_outbound(self) -> List[TrustGossipPayload]:
        out = self._outbound
        self._outbound = []
        return out

    # -- internal ----------------------------------------------------------

    def _verify_delta(self, delta: ProjectionDelta) -> bool:
        if self._verifier is not None and self._trust_lattice is not None:
            result = self._verifier.verify(
                delta, self._state, self._trust_lattice,
            )
            return result.accepted
        # No verifier -- accept by default (pre-E4 compat)
        return True

    def _receive_trust_delta(self, delta: ProjectionDelta) -> bool:
        if self._trust_lattice is None:
            return False
        return self._trust_lattice.receive_trust_delta(delta, self._state)
