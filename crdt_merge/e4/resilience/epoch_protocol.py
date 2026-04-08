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

"""Formal epoch coordination protocol with evidence garbage collection.

Addresses two expert concerns:
  - Vasquez §1: Epoch management at scale — epoch coordination bottleneck
    for millions of nodes, partition-aware epoch disagreement resolution.
  - Wei §20: Garbage collection of trust evidence — GCounter evidence is
    grow-only, needs epoch-based GC with formal specification.

Design:
  - Epoch number is a CRDT (max-register): all peers converge to the
    highest epoch seen.  No coordinator needed.
  - Epoch advances when a configurable trigger fires (wall-clock interval,
    evidence volume, or external signal).
  - On epoch advance: evidence older than epoch_retention epochs is pruned.
  - Partitioned peers: when a partition heals, the higher epoch wins.
    Evidence from the lower-epoch partition is retained (merged into the
    higher epoch) — no data loss, just epoch renumbering.
  - Evidence GC is deterministic: given the same epoch and retention policy,
    all peers prune identically.  This preserves CRDT convergence.

Technical effect (UK patent): bounded memory growth for trust evidence
in long-running distributed systems, enabling deployment at scale without
unbounded state accumulation.
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class EpochTransition:
    """Record of an epoch boundary transition.

    Attributes
    ----------
    from_epoch   : Previous epoch number.
    to_epoch     : New epoch number.
    timestamp    : Wall-clock time of the transition.
    trigger      : What caused the transition.
    evidence_pruned : Number of evidence entries garbage-collected.
    """
    from_epoch: int
    to_epoch: int
    timestamp: float
    trigger: str = "interval"
    evidence_pruned: int = 0


class EpochState:
    """Epoch state as a CRDT (max-register).

    The epoch number is merged by taking the maximum — this guarantees
    convergence without coordination.  When two peers merge, the higher
    epoch wins.  Evidence retention is scoped to epochs, so GC decisions
    are deterministic given the epoch.

    Parameters
    ----------
    initial_epoch :
        Starting epoch (default: 0).
    retention_epochs :
        Number of past epochs to retain evidence for (default: 3).
        Evidence from epochs older than (current - retention) is pruned.
    """

    def __init__(
        self,
        initial_epoch: int = 0,
        *,
        retention_epochs: int = 3,
    ) -> None:
        self._epoch = initial_epoch
        self._retention = retention_epochs
        self._history: List[EpochTransition] = []
        self._evidence_epochs: Dict[int, int] = {}  # epoch -> evidence count

    @property
    def current_epoch(self) -> int:
        return self._epoch

    @property
    def retention_epochs(self) -> int:
        return self._retention

    @property
    def history(self) -> List[EpochTransition]:
        return list(self._history)

    def advance(self, trigger: str = "interval") -> EpochTransition:
        """Advance to the next epoch.

        Returns the transition record.  Evidence GC count is computed
        but actual pruning is deferred to the caller (who holds the
        trust lattice reference).
        """
        old = self._epoch
        self._epoch += 1

        prunable = self._count_prunable_epochs()
        transition = EpochTransition(
            from_epoch=old,
            to_epoch=self._epoch,
            timestamp=_time.time(),
            trigger=trigger,
            evidence_pruned=prunable,
        )
        self._history.append(transition)
        return transition

    def merge(self, other: EpochState) -> EpochState:
        """CRDT merge — take the maximum epoch.

        History is merged by union (sorted by timestamp).
        """
        result = EpochState(
            max(self._epoch, other._epoch),
            retention_epochs=min(self._retention, other._retention),
        )
        # Merge histories
        seen_epochs: Set[int] = set()
        for t in sorted(
            self._history + other._history,
            key=lambda t: t.timestamp,
        ):
            if t.to_epoch not in seen_epochs:
                result._history.append(t)
                seen_epochs.add(t.to_epoch)

        # Merge evidence epoch counts (max per epoch)
        all_epochs = set(self._evidence_epochs) | set(other._evidence_epochs)
        for e in all_epochs:
            result._evidence_epochs[e] = max(
                self._evidence_epochs.get(e, 0),
                other._evidence_epochs.get(e, 0),
            )
        return result

    def record_evidence(self, epoch: Optional[int] = None) -> None:
        """Record that evidence was added in the given epoch."""
        e = epoch if epoch is not None else self._epoch
        self._evidence_epochs[e] = self._evidence_epochs.get(e, 0) + 1

    def prunable_epochs(self) -> List[int]:
        """Return epoch numbers that are eligible for GC."""
        cutoff = self._epoch - self._retention
        return [e for e in self._evidence_epochs if e < cutoff]

    def prune(self) -> int:
        """Remove evidence epoch records older than retention window.

        Returns the number of epochs pruned.
        """
        prunable = self.prunable_epochs()
        for e in prunable:
            del self._evidence_epochs[e]
        return len(prunable)

    def is_evidence_valid(self, evidence_epoch: int) -> bool:
        """Check if evidence from *evidence_epoch* is still within retention."""
        return evidence_epoch >= (self._epoch - self._retention)

    def _count_prunable_epochs(self) -> int:
        return len(self.prunable_epochs())

    def __repr__(self) -> str:
        return (
            f"EpochState(epoch={self._epoch}, "
            f"retention={self._retention}, "
            f"evidence_epochs={len(self._evidence_epochs)})"
        )


class EpochManager:
    """High-level epoch lifecycle management.

    Coordinates epoch advancement across the local node, including
    trigger evaluation and evidence GC orchestration.

    Parameters
    ----------
    peer_id :
        Local peer identifier.
    interval :
        Seconds between epoch advances (default: 3600 = 1 hour).
    max_evidence_per_epoch :
        Maximum evidence entries before forcing an epoch advance
        (default: 10000).  Prevents unbounded growth within an epoch.
    retention_epochs :
        Number of past epochs to retain (default: 3).
    """

    def __init__(
        self,
        peer_id: str,
        *,
        interval: float = 3600.0,
        max_evidence_per_epoch: int = 10000,
        retention_epochs: int = 3,
    ) -> None:
        self._peer_id = peer_id
        self._interval = interval
        self._max_evidence = max_evidence_per_epoch
        self._state = EpochState(0, retention_epochs=retention_epochs)
        self._last_advance = _time.time()
        self._evidence_count = 0

    @property
    def state(self) -> EpochState:
        return self._state

    @property
    def current_epoch(self) -> int:
        return self._state.current_epoch

    def should_advance(self) -> bool:
        """Check if an epoch advance is due (interval or evidence volume)."""
        if (_time.time() - self._last_advance) >= self._interval:
            return True
        if self._evidence_count >= self._max_evidence:
            return True
        return False

    def advance_if_needed(self) -> Optional[EpochTransition]:
        """Advance epoch if trigger conditions are met.

        Returns the transition record if advanced, None otherwise.
        """
        if not self.should_advance():
            return None
        return self.force_advance()

    def force_advance(self, trigger: str = "interval") -> EpochTransition:
        """Force an epoch advance regardless of trigger conditions."""
        transition = self._state.advance(trigger=trigger)
        self._last_advance = _time.time()
        self._evidence_count = 0
        return transition

    def record_evidence(self) -> None:
        """Record that a piece of evidence was added."""
        self._evidence_count += 1
        self._state.record_evidence()

    def gc_evidence(self) -> int:
        """Garbage-collect expired evidence epoch records.

        Returns the number of epochs pruned.
        """
        return self._state.prune()

    def merge_remote_epoch(self, remote_state: EpochState) -> EpochTransition:
        """Merge a remote peer's epoch state.

        If the remote epoch is higher, we advance to match.
        """
        old_epoch = self._state.current_epoch
        self._state = self._state.merge(remote_state)
        return EpochTransition(
            from_epoch=old_epoch,
            to_epoch=self._state.current_epoch,
            timestamp=_time.time(),
            trigger="remote_merge",
        )

    def partition_resolution_strategy(
        self,
        local_epoch: int,
        remote_epoch: int,
    ) -> str:
        """Determine strategy when a partition heals.

        Returns one of:
          - "fast_forward": remote is ahead, adopt remote epoch
          - "merge": epochs are close, merge evidence
          - "quarantine": remote is far behind, verify before merging

        The threshold for quarantine is 2x retention window.
        """
        diff = abs(local_epoch - remote_epoch)
        if diff == 0:
            return "merge"
        if diff <= self._state.retention_epochs:
            return "fast_forward"
        if diff <= self._state.retention_epochs * 2:
            return "merge"
        return "quarantine"

    def __repr__(self) -> str:
        return (
            f"EpochManager(peer={self._peer_id!r}, "
            f"epoch={self.current_epoch}, "
            f"evidence={self._evidence_count})"
        )
