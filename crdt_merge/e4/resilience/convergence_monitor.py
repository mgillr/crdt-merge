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

"""Convergence bound estimation and runtime monitoring.

Addresses two expert concerns:
  - Vasquez §2: Convergence speed under partition — formal bounds on
    convergence time as function of partition duration and evidence divergence.
  - Wei §19: Convergence vs agreement — the architecture should specify
    convergence time bounds for time-sensitive applications.

Formal analysis:

The trust lattice converges via GCounter merge (element-wise max).  After
a partition heals, the number of merge rounds R needed for full convergence
satisfies:

    R <= ceil(D / (1 - e^{-lambda}))

where:
  D = diameter of the gossip overlay graph
  lambda = gossip rate (messages per peer per round)

For a random gossip overlay with n peers:
  D = O(log n)
  lambda >= 1 (standard gossip)

Therefore: R = O(log n) rounds.

With gossip round interval T (seconds), the convergence time bound is:

    T_converge <= T * ceil(log(n) / (1 - e^{-1}))
               ~= T * 1.58 * log(n)

For n = 10,000 peers at T = 1s:  T_converge ~= 1.58 * 13.3 ~= 21 seconds.
For n = 1,000,000 peers at T = 1s: T_converge ~= 1.58 * 20 ~= 31.6 seconds.

Post-partition additional factor:

    T_partition_recovery = T_converge * (1 + evidence_divergence_ratio)

where evidence_divergence_ratio = |evidence_A - evidence_B| / |evidence_A ∪ evidence_B|.

Technical effect (UK patent): provides deterministic convergence time
guarantees for trust state in distributed CRDT networks, enabling
deployment in time-sensitive agent coordination scenarios.
"""

from __future__ import annotations

import math
import time as _time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ConvergenceBound:
    """Computed convergence time bound for a given configuration.

    Attributes
    ----------
    peer_count          : Number of peers in the network.
    gossip_interval     : Seconds between gossip rounds.
    graph_diameter      : Estimated gossip overlay diameter.
    rounds_to_converge  : Number of gossip rounds for convergence.
    time_bound_seconds  : Worst-case convergence time in seconds.
    partition_factor    : Multiplier for post-partition recovery.
    post_partition_bound: Convergence time after partition heal.
    """
    peer_count: int
    gossip_interval: float
    graph_diameter: float
    rounds_to_converge: int
    time_bound_seconds: float
    partition_factor: float = 1.0
    post_partition_bound: float = 0.0

    @classmethod
    def compute(
        cls,
        peer_count: int,
        gossip_interval: float = 1.0,
        gossip_rate: float = 1.0,
        evidence_divergence_ratio: float = 0.0,
    ) -> ConvergenceBound:
        """Compute convergence bounds for given network parameters.

        Parameters
        ----------
        peer_count :
            Number of peers.
        gossip_interval :
            Seconds between gossip rounds.
        gossip_rate :
            Messages per peer per round (lambda).
        evidence_divergence_ratio :
            Ratio of divergent evidence after partition (0.0 = no partition).
        """
        if peer_count <= 1:
            return cls(
                peer_count=peer_count,
                gossip_interval=gossip_interval,
                graph_diameter=0,
                rounds_to_converge=0,
                time_bound_seconds=0,
            )

        # Gossip overlay diameter: O(log n)
        diameter = math.log2(peer_count)

        # Convergence factor: 1 / (1 - e^{-lambda})
        convergence_factor = 1.0 / (1.0 - math.exp(-gossip_rate))

        # Rounds to converge
        rounds = math.ceil(diameter * convergence_factor)

        # Time bound
        time_bound = gossip_interval * rounds

        # Partition recovery factor
        partition_factor = 1.0 + evidence_divergence_ratio
        post_partition = time_bound * partition_factor

        return cls(
            peer_count=peer_count,
            gossip_interval=gossip_interval,
            graph_diameter=diameter,
            rounds_to_converge=rounds,
            time_bound_seconds=time_bound,
            partition_factor=partition_factor,
            post_partition_bound=post_partition,
        )


class ConvergenceMonitor:
    """Runtime convergence monitoring for the trust lattice.

    Tracks actual convergence behavior and alerts when convergence
    is slower than the theoretical bound.

    Parameters
    ----------
    peer_count :
        Expected number of peers (used for bound computation).
    gossip_interval :
        Seconds between gossip rounds.
    alert_threshold :
        Multiplier on theoretical bound before alerting (default: 2.0).
    window_size :
        Number of recent convergence observations to track.
    """

    def __init__(
        self,
        peer_count: int = 100,
        *,
        gossip_interval: float = 1.0,
        alert_threshold: float = 2.0,
        window_size: int = 100,
    ) -> None:
        self._peer_count = peer_count
        self._gossip_interval = gossip_interval
        self._alert_threshold = alert_threshold
        self._window_size = window_size
        self._observations: List[float] = []
        self._alerts: List[Tuple[float, str]] = []
        self._bound = ConvergenceBound.compute(peer_count, gossip_interval)

    @property
    def theoretical_bound(self) -> ConvergenceBound:
        return self._bound

    @property
    def alerts(self) -> List[Tuple[float, str]]:
        return list(self._alerts)

    def record_convergence(self, actual_time: float) -> bool:
        """Record an observed convergence time.

        Returns True if within bounds, False if alert triggered.
        """
        self._observations.append(actual_time)
        if len(self._observations) > self._window_size:
            self._observations = self._observations[-self._window_size:]

        threshold = self._bound.time_bound_seconds * self._alert_threshold
        if actual_time > threshold:
            self._alerts.append((
                _time.time(),
                f"Convergence time {actual_time:.2f}s exceeds "
                f"threshold {threshold:.2f}s "
                f"(theoretical bound: {self._bound.time_bound_seconds:.2f}s)",
            ))
            return False
        return True

    def record_partition_recovery(
        self,
        actual_time: float,
        divergence_ratio: float,
    ) -> bool:
        """Record a post-partition convergence time.

        Returns True if within bounds, False if alert triggered.
        """
        bound = ConvergenceBound.compute(
            self._peer_count,
            self._gossip_interval,
            evidence_divergence_ratio=divergence_ratio,
        )
        threshold = bound.post_partition_bound * self._alert_threshold
        if actual_time > threshold:
            self._alerts.append((
                _time.time(),
                f"Partition recovery {actual_time:.2f}s exceeds "
                f"threshold {threshold:.2f}s "
                f"(divergence ratio: {divergence_ratio:.2f})",
            ))
            return False
        return True

    def update_peer_count(self, peer_count: int) -> None:
        """Update the peer count and recompute bounds."""
        self._peer_count = peer_count
        self._bound = ConvergenceBound.compute(
            peer_count, self._gossip_interval,
        )

    @property
    def average_convergence_time(self) -> float:
        """Average observed convergence time."""
        if not self._observations:
            return 0.0
        return sum(self._observations) / len(self._observations)

    @property
    def p99_convergence_time(self) -> float:
        """99th percentile observed convergence time."""
        if not self._observations:
            return 0.0
        sorted_obs = sorted(self._observations)
        idx = int(len(sorted_obs) * 0.99)
        return sorted_obs[min(idx, len(sorted_obs) - 1)]

    @property
    def convergence_health(self) -> str:
        """Overall convergence health assessment."""
        if not self._observations:
            return "unknown"
        avg = self.average_convergence_time
        bound = self._bound.time_bound_seconds
        if bound == 0:
            return "healthy"
        ratio = avg / bound
        if ratio <= 1.0:
            return "healthy"
        if ratio <= self._alert_threshold:
            return "degraded"
        return "critical"

    def __repr__(self) -> str:
        return (
            f"ConvergenceMonitor(peers={self._peer_count}, "
            f"bound={self._bound.time_bound_seconds:.1f}s, "
            f"health={self.convergence_health!r})"
        )
