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

"""Post-partition trust reconciliation protocol.

Addresses Georgiou §C5: when a network partition isolates high-trust
nodes in the minority partition, the majority's trust scores for those
nodes decay (no evidence received).  When the partition heals, there
is a trust reconciliation problem.

The GCounter merge (element-wise maximum) is mathematically correct —
it preserves all evidence from both partitions.  But the derived trust
score (after homeostasis normalisation) may temporarily demote
previously-trusted nodes because the normalising constant increased
when the partitions merge (more total evidence in the combined state).

Solution — graduated reconciliation:

  Phase 1: Merge state (standard CRDT merge).
    All GCounter dimensions take element-wise maximum.  This is
    automatic and correct.

  Phase 2: Grace period.
    For a configurable number of rounds after partition heal, the
    homeostasis normaliser uses the pre-merge budget (smaller) rather
    than the post-merge budget (larger).  This prevents sudden trust
    score drops for nodes that were active in only one partition.

  Phase 3: Evidence catch-up.
    Nodes from the minority partition get a temporary evidence
    multiplier (similar to warm-up) to accelerate their trust
    recovery to pre-partition levels.

  Phase 4: Steady state.
    After the grace period, normal homeostasis resumes with the
    merged budget.  Trust scores stabilise at their natural levels.

Technical effect (UK patent): prevents transient trust demotion of
legitimate nodes after network partition healing through a graduated
normalisation transition protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# -- Partition event -------------------------------------------------------

@dataclass(frozen=True)
class PartitionEvent:
    """Record of a detected partition heal."""
    timestamp: float
    local_peers: FrozenSet[str]
    remote_peers: FrozenSet[str]
    pre_merge_budget: float
    post_merge_budget: float


# -- Reconciliation state --------------------------------------------------

@dataclass
class ReconciliationState:
    """Per-peer reconciliation tracking."""
    peer_id: str
    pre_partition_trust: float
    post_merge_trust: float
    grace_rounds_remaining: int
    evidence_multiplier: float = 1.0
    reconciled: bool = False


# -- Reconciler ------------------------------------------------------------

class PartitionReconciler:
    """Manage trust reconciliation after network partition healing.

    Parameters
    ----------
    grace_rounds :
        Number of rounds to use pre-merge normalisation budget.
    evidence_boost :
        Temporary evidence multiplier for minority partition peers.
    detection_threshold :
        Minimum peer overlap change to classify as partition heal.
    """

    def __init__(
        self,
        grace_rounds: int = 10,
        evidence_boost: float = 2.0,
        detection_threshold: float = 0.2,
    ) -> None:
        self._grace_rounds = grace_rounds
        self._evidence_boost = evidence_boost
        self._detection_threshold = detection_threshold
        self._events: List[PartitionEvent] = []
        self._active: Dict[str, ReconciliationState] = {}

    # -- partition detection -----------------------------------------------

    def detect_partition_heal(
        self,
        known_peers_before: Set[str],
        known_peers_after: Set[str],
        trust_scores: Dict[str, float],
        budget_before: float,
        budget_after: float,
        now: Optional[float] = None,
    ) -> Optional[PartitionEvent]:
        """Detect if a significant set of new peers appeared (partition heal).

        Returns a PartitionEvent if detected, None otherwise.
        """
        now = now or time.time()
        new_peers = known_peers_after - known_peers_before
        if not new_peers:
            return None

        overlap_change = len(new_peers) / max(len(known_peers_after), 1)
        if overlap_change < self._detection_threshold:
            return None

        event = PartitionEvent(
            timestamp=now,
            local_peers=frozenset(known_peers_before),
            remote_peers=frozenset(new_peers),
            pre_merge_budget=budget_before,
            post_merge_budget=budget_after,
        )
        self._events.append(event)

        for pid in new_peers:
            pre_trust = trust_scores.get(pid, 0.5)
            self._active[pid] = ReconciliationState(
                peer_id=pid,
                pre_partition_trust=pre_trust,
                post_merge_trust=pre_trust,
                grace_rounds_remaining=self._grace_rounds,
                evidence_multiplier=self._evidence_boost,
            )

        return event

    # -- round progression -------------------------------------------------

    def advance_round(self) -> List[str]:
        """Advance reconciliation by one round.

        Returns list of peer_ids that completed reconciliation.
        """
        completed = []
        for pid, state in list(self._active.items()):
            if state.reconciled:
                continue
            state.grace_rounds_remaining -= 1
            if state.grace_rounds_remaining <= 0:
                state.evidence_multiplier = 1.0
                state.reconciled = True
                completed.append(pid)
            else:
                decay = state.grace_rounds_remaining / self._grace_rounds
                state.evidence_multiplier = 1.0 + (self._evidence_boost - 1.0) * decay
        return completed

    # -- query interface ---------------------------------------------------

    def get_evidence_multiplier(self, peer_id: str) -> float:
        """Current evidence multiplier for a peer (1.0 if not reconciling)."""
        state = self._active.get(peer_id)
        if state and not state.reconciled:
            return state.evidence_multiplier
        return 1.0

    def get_normalisation_budget(
        self,
        peer_id: str,
        current_budget: float,
    ) -> float:
        """Effective normalisation budget during grace period.

        During grace period, returns a blend of pre-merge and post-merge
        budgets to prevent sudden trust drops.
        """
        state = self._active.get(peer_id)
        if not state or state.reconciled:
            return current_budget

        event = self._events[-1] if self._events else None
        if not event:
            return current_budget

        progress = 1.0 - (state.grace_rounds_remaining / max(self._grace_rounds, 1))
        return event.pre_merge_budget + progress * (
            event.post_merge_budget - event.pre_merge_budget
        )

    def is_reconciling(self, peer_id: str) -> bool:
        state = self._active.get(peer_id)
        return state is not None and not state.reconciled

    @property
    def active_reconciliations(self) -> int:
        return sum(1 for s in self._active.values() if not s.reconciled)

    @property
    def partition_events(self) -> List[PartitionEvent]:
        return list(self._events)

    def cleanup_completed(self) -> int:
        """Remove completed reconciliation records."""
        to_remove = [pid for pid, s in self._active.items() if s.reconciled]
        for pid in to_remove:
            del self._active[pid]
        return len(to_remove)

    def __repr__(self) -> str:
        return (
            f"PartitionReconciler(active={self.active_reconciliations}, "
            f"events={len(self._events)})"
        )
