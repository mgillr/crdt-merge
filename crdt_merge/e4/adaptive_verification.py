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

"""Adaptive immune verification controller (ref 895, 1200-1280).

Routes incoming deltas through trust-tiered verification levels.  Higher
trust peers get cheaper verification; low trust peers get the full
aggregate PCO check.  Async followup queues ensure that optimistic
accepts at Level 0/1 are eventually fully verified.

Levels:
  0 -- trust > 0.8  : signature only              O(1)
  1 -- trust 0.4-0.8: signature + Merkle root      O(1)
  2 -- trust < 0.4  : full aggregate PCO            O(k)
  3 -- trust < 0.1  : reject unconditionally        O(1)

When the circuit breaker is tripped, ALL verifications are forced to
Level 2 regardless of sender trust (ref 1280).
"""

from __future__ import annotations

import enum
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Deque, List, Optional, Tuple

if TYPE_CHECKING:
    from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice, TrustCircuitBreaker
    from crdt_merge.e4.pco import AggregateProofCarryingOperation
    from crdt_merge.e4.projection_delta import ProjectionDelta
    from crdt_merge.e4.typed_trust import TypedTrustScore


# -- Verification outcome --------------------------------------------------

class VerificationOutcome(enum.Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True)
class VerificationResult:
    """Result from adaptive verification.

    Attributes
    ----------
    outcome     : ACCEPT or REJECT.
    level       : The verification level that was applied (0-3).
    async_pending : True when full verification is queued for later.
    reason      : Short explanation when rejected.
    """

    outcome: VerificationOutcome
    level: int
    async_pending: bool = False
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.outcome is VerificationOutcome.ACCEPT


# -- AdaptiveVerificationController ----------------------------------------

class AdaptiveVerificationController:
    """Trust-tiered verification for incoming projection deltas (ref 895).

    Parameters
    ----------
    trust_lattice :
        Used to look up sender trust and record counter-evidence.
    circuit_breaker :
        When tripped, forces all deltas to Level 2 verification.
    async_queue_limit :
        Maximum pending async verification items before back-pressure.
    """

    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        circuit_breaker: Optional[TrustCircuitBreaker] = None,
        *,
        async_queue_limit: int = 1024,
    ) -> None:
        self._trust_lattice = trust_lattice
        self._circuit_breaker = circuit_breaker
        self._async_queue: Deque[Tuple[ProjectionDelta, int]] = deque(
            maxlen=async_queue_limit,
        )

    # -- dependency injection post-init ------------------------------------

    def bind_trust_lattice(self, lattice: DeltaTrustLattice) -> None:
        self._trust_lattice = lattice

    def bind_circuit_breaker(self, breaker: TrustCircuitBreaker) -> None:
        self._circuit_breaker = breaker

    # -- main entry point --------------------------------------------------

    def verify(
        self,
        delta: ProjectionDelta,
        state: object,
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> VerificationResult:
        """Adaptively verify *delta* based on sender trust.

        Algorithm from spec section 5.2 (AdaptiveVerify).  The
        *trust_lattice* argument overrides the instance-level lattice
        when provided (useful for one-off calls).
        """
        lattice = trust_lattice or self._trust_lattice
        if lattice is None:
            return VerificationResult(
                outcome=VerificationOutcome.REJECT,
                level=2,
                reason="no trust lattice available",
            )

        # Determine level from sender trust
        sender_trust: TypedTrustScore = lattice.get_trust(delta.source_id)
        level = sender_trust.verification_level()

        # Circuit breaker override (ref 1280)
        if self._circuit_breaker is not None and self._circuit_breaker.is_tripped():
            level = 2

        # Level 3 -- quarantined, reject outright
        if level == 3:
            return VerificationResult(
                outcome=VerificationOutcome.REJECT,
                level=3,
                reason="sender quarantined",
            )

        # All levels: signature check
        pco = delta.pco
        if not pco.verify(state, lattice, verification_level=0):
            self._record_counter_evidence(lattice, delta.source_id, "invalid_delta")
            return VerificationResult(
                outcome=VerificationOutcome.REJECT,
                level=level,
                reason="signature verification failed",
            )

        # Level 0 -- signature sufficient, schedule async full verify
        if level == 0:
            self._enqueue_async(delta, level)
            return VerificationResult(
                outcome=VerificationOutcome.ACCEPT,
                level=0,
                async_pending=True,
            )

        # Level 1 -- signature + Merkle root
        if level == 1:
            if not pco.verify(state, lattice, verification_level=1):
                self._record_counter_evidence(
                    lattice, delta.source_id, "merkle_divergence",
                )
                return VerificationResult(
                    outcome=VerificationOutcome.REJECT,
                    level=1,
                    reason="Merkle root inconsistency",
                )
            self._enqueue_async(delta, level)
            return VerificationResult(
                outcome=VerificationOutcome.ACCEPT,
                level=1,
                async_pending=True,
            )

        # Level 2 -- full PCO verification
        if not pco.verify(state, lattice, verification_level=2):
            self._record_counter_evidence(lattice, delta.source_id, "invalid_delta")
            return VerificationResult(
                outcome=VerificationOutcome.REJECT,
                level=2,
                reason="full PCO verification failed",
            )
        return VerificationResult(
            outcome=VerificationOutcome.ACCEPT,
            level=2,
        )

    # -- async followup (ref 1014-1022) ------------------------------------

    def run_async_followup(
        self,
        state: object,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        *,
        batch_size: int = 32,
    ) -> List[Tuple[ProjectionDelta, VerificationResult]]:
        """Re-verify queued deltas at Level 2.

        Returns a list of (delta, result) pairs.  Failures trigger trust
        drops on the original sender (escalation, ref 1270).
        """
        lattice = trust_lattice or self._trust_lattice
        results: List[Tuple[ProjectionDelta, VerificationResult]] = []
        processed = 0

        while self._async_queue and processed < batch_size:
            delta, original_level = self._async_queue.popleft()
            processed += 1

            pco = delta.pco
            if lattice is not None and not pco.verify(
                state, lattice, verification_level=2,
            ):
                # Anomaly from previously trusted peer -- escalate
                self._record_counter_evidence(
                    lattice, delta.source_id, "invalid_delta",
                )
                results.append((
                    delta,
                    VerificationResult(
                        outcome=VerificationOutcome.REJECT,
                        level=2,
                        reason=f"async re-verify failed (was level {original_level})",
                    ),
                ))
            else:
                results.append((
                    delta,
                    VerificationResult(
                        outcome=VerificationOutcome.ACCEPT,
                        level=2,
                    ),
                ))

        return results

    # -- introspection -----------------------------------------------------

    @property
    def pending_async_count(self) -> int:
        return len(self._async_queue)

    def drain_async_queue(self) -> List[Tuple[ProjectionDelta, int]]:
        items = list(self._async_queue)
        self._async_queue.clear()
        return items

    # -- internal ----------------------------------------------------------

    def _enqueue_async(self, delta: ProjectionDelta, level: int) -> None:
        self._async_queue.append((delta, level))

    def _record_counter_evidence(
        self,
        lattice: Optional[DeltaTrustLattice],
        peer_id: str,
        evidence_type: str,
    ) -> None:
        if lattice is None:
            return
        record = getattr(lattice, "_record_counter_evidence", None)
        if record is not None:
            record(peer_id, evidence_type)
