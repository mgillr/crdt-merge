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

"""Non-IID convergence analysis for trust-model interaction.

Addresses Mitchell §C1 and Okafor §C15: the interaction between trust
convergence and model convergence under non-IID data partitions.  If
trust converges slower than the model, early rounds under-weight
valuable contributors.

Analysis framework:
  - Model trust score convergence under different data heterogeneity
    regimes (IID, mild non-IID, severe non-IID).
  - Formal bounds on trust convergence rate as a function of peer
    count, evidence rate, and gossip frequency.
  - Adaptive trust warm-up that accelerates trust convergence in
    early training rounds to match model convergence speed.

Key insight: trust convergence is O(diameter * gossip_interval) while
model convergence is O(rounds * learning_rate).  When gossip is fast
relative to training rounds, trust converges first (desirable).  When
training is fast (large LR, few rounds), trust lags (problematic).
The warm-up mechanism addresses the latter by temporarily lowering the
evidence threshold for trust growth in early rounds.

Technical effect (UK patent): decouples trust convergence rate from
model convergence rate through adaptive evidence thresholds, ensuring
trust-weighted aggregation is effective from the first training round.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# -- Convergence bound computation -----------------------------------------

@dataclass(frozen=True)
class ConvergenceBound:
    """Formal bound on convergence rate."""
    rounds_to_converge: int
    trust_gap_at_round: float
    model_gap_at_round: float
    regime: str


@dataclass
class HeterogeneityProfile:
    """Characterise non-IID data distribution across peers.

    Parameters
    ----------
    peer_count :
        Number of participating peers.
    label_skew :
        Fraction of labels present at each peer (1.0 = IID, 0.1 = severe).
    volume_skew :
        Ratio of largest to smallest local dataset (1.0 = uniform).
    feature_shift :
        Magnitude of covariate shift across peers (0.0 = none).
    """
    peer_count: int = 10
    label_skew: float = 1.0
    volume_skew: float = 1.0
    feature_shift: float = 0.0

    @property
    def regime(self) -> str:
        if self.label_skew > 0.8 and self.volume_skew < 2.0:
            return "iid"
        if self.label_skew > 0.4:
            return "mild-noniid"
        return "severe-noniid"


# -- Trust convergence analyser --------------------------------------------

class TrustConvergenceAnalyser:
    """Analyse trust-model convergence interaction.

    Parameters
    ----------
    gossip_interval :
        Rounds between gossip exchanges (lower = faster trust propagation).
    evidence_rate :
        Average evidence observations per peer per round.
    initial_trust :
        Starting trust for all peers (probationary default).
    """

    def __init__(
        self,
        gossip_interval: float = 1.0,
        evidence_rate: float = 1.0,
        initial_trust: float = 0.5,
    ) -> None:
        self._gossip_interval = max(gossip_interval, 0.1)
        self._evidence_rate = max(evidence_rate, 0.01)
        self._initial_trust = initial_trust

    def convergence_bound(
        self,
        profile: HeterogeneityProfile,
        target_trust: float = 0.8,
    ) -> ConvergenceBound:
        """Compute rounds until trust reaches target under given profile.

        Uses the exponential trust growth model:
          trust(r) = 1 - (1 - t0) * exp(-lambda * r)
        where lambda depends on evidence rate and gossip speed.
        """
        t0 = self._initial_trust
        if t0 >= target_trust:
            return ConvergenceBound(0, 0.0, 0.0, profile.regime)

        lam = self._evidence_rate / self._gossip_interval
        skew_penalty = 1.0 / max(profile.label_skew, 0.1)
        effective_lambda = lam / skew_penalty

        if effective_lambda < 1e-9:
            rounds = 10000
        else:
            ratio = (1.0 - target_trust) / (1.0 - t0)
            if ratio <= 0:
                rounds = 0
            else:
                rounds = int(math.ceil(-math.log(ratio) / effective_lambda))

        trust_gap = (1.0 - t0) * math.exp(-effective_lambda * max(rounds, 1))
        model_gap = self._estimate_model_gap(profile, rounds)

        return ConvergenceBound(rounds, trust_gap, model_gap, profile.regime)

    def convergence_trajectory(
        self,
        profile: HeterogeneityProfile,
        rounds: int = 50,
    ) -> List[Tuple[int, float, float]]:
        """Compute (round, trust_score, model_loss) trajectory.

        Returns list of (round_number, avg_trust, estimated_model_gap)
        tuples for plotting convergence dynamics.
        """
        t0 = self._initial_trust
        lam = self._evidence_rate / self._gossip_interval
        skew_penalty = 1.0 / max(profile.label_skew, 0.1)
        effective_lambda = lam / skew_penalty

        trajectory = []
        for r in range(rounds + 1):
            trust = 1.0 - (1.0 - t0) * math.exp(-effective_lambda * r)
            model_gap = self._estimate_model_gap(profile, r)
            trajectory.append((r, trust, model_gap))
        return trajectory

    def recommend_warmup(
        self,
        profile: HeterogeneityProfile,
        target_round: int = 5,
    ) -> WarmupSchedule:
        """Recommend adaptive warm-up schedule to match convergence rates.

        Returns a schedule that temporarily lowers evidence thresholds
        in early rounds so trust converges by ``target_round``.
        """
        bound = self.convergence_bound(profile, target_trust=0.75)
        if bound.rounds_to_converge <= target_round:
            return WarmupSchedule(
                boost_rounds=0,
                evidence_multiplier=1.0,
                threshold_reduction=0.0,
            )

        needed_speedup = bound.rounds_to_converge / max(target_round, 1)
        multiplier = min(needed_speedup, 5.0)
        threshold_reduction = min(0.3, 0.1 * (needed_speedup - 1))

        return WarmupSchedule(
            boost_rounds=target_round,
            evidence_multiplier=multiplier,
            threshold_reduction=threshold_reduction,
        )

    # -- internal ----------------------------------------------------------

    def _estimate_model_gap(self, profile: HeterogeneityProfile, rounds: int) -> float:
        """Rough model convergence estimate (exponential decay with skew)."""
        base_rate = 0.1
        skew_slowdown = 1.0 + (1.0 - profile.label_skew) * 2.0
        return math.exp(-base_rate * rounds / skew_slowdown)


# -- Warm-up schedule ------------------------------------------------------

@dataclass(frozen=True)
class WarmupSchedule:
    """Adaptive trust warm-up configuration.

    Parameters
    ----------
    boost_rounds :
        Number of early rounds with accelerated trust growth.
    evidence_multiplier :
        Factor by which to multiply evidence weight during boost.
    threshold_reduction :
        Amount to lower evidence acceptance threshold during boost.
    """
    boost_rounds: int
    evidence_multiplier: float
    threshold_reduction: float

    def apply(self, current_round: int, evidence_weight: float) -> float:
        """Apply warm-up boost to evidence weight for current round."""
        if current_round >= self.boost_rounds:
            return evidence_weight
        decay = 1.0 - (current_round / max(self.boost_rounds, 1))
        boost = 1.0 + (self.evidence_multiplier - 1.0) * decay
        return evidence_weight * boost

    @property
    def active(self) -> bool:
        return self.boost_rounds > 0


# -- Heterogeneity quantification -----------------------------------------

def dirichlet_skew(alpha: float, num_peers: int, num_classes: int) -> float:
    """Compute effective label skew from Dirichlet concentration.

    Standard non-IID FL benchmark uses Dir(alpha) to partition labels.
    alpha -> 0 : extreme non-IID (each peer gets one class)
    alpha -> inf : IID (uniform distribution)

    Returns label_skew in [0, 1] for use with HeterogeneityProfile.
    """
    if alpha <= 0:
        return 1.0 / num_classes
    expected_classes = num_classes * (1.0 - (1.0 - 1.0 / num_classes) ** (alpha * num_peers))
    return min(expected_classes / num_classes, 1.0)
