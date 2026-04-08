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

"""Strategy drift discriminator — separate non-stationarity from attacks.

Addresses Kowalski §C11 and §C12: in multi-agent RL, policy changes are
normal (exploration, curriculum learning, self-play adaptation).  E4's
trust system penalises sudden behavioral changes, which could unfairly
demote agents undergoing legitimate strategy shifts.

The circuit breaker (ref §829) triggers on trust velocity — but velocity
from a strategy shift looks identical to velocity from an attack.  We
need to discriminate.

Detection strategy — two-phase analysis:

  Phase 1: Behavioral fingerprint.
    Track a rolling histogram of an agent's contribution characteristics
    (delta magnitudes, parameter regions modified, frequency patterns).
    A strategy shift produces a coherent change in the fingerprint
    (correlated across dimensions).  An attack produces an incoherent
    change (e.g., magnitudes spike but regions stay the same).

  Phase 2: Cohort correlation.
    If multiple agents shift strategy simultaneously (common in
    curriculum learning), the shifts will be correlated.  Correlated
    shifts are more likely legitimate.  Uncorrelated shifts from a
    single agent against a stable background are more suspicious.

Output: a ``DriftVerdict`` that the trust system can use to modulate
its response — suppress trust penalty for likely-legitimate shifts,
amplify penalty for likely-attack shifts.

Technical effect (UK patent): prevents false positive trust demotion
of agents undergoing legitimate strategy evolution by discriminating
coherent behavioral drift from adversarial perturbation.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple


# -- Behavioral fingerprint ------------------------------------------------

@dataclass
class BehavioralFingerprint:
    """Rolling characterisation of an agent's contributions."""
    magnitude_histogram: List[int] = field(default_factory=lambda: [0] * 10)
    region_histogram: List[int] = field(default_factory=lambda: [0] * 8)
    frequency: float = 0.0
    total_contributions: int = 0

    def record(self, magnitude: float, region: int) -> None:
        bucket = min(int(magnitude * 10), 9)
        self.magnitude_histogram[bucket] += 1
        self.region_histogram[region % 8] += 1
        self.total_contributions += 1

    def normalised_magnitude(self) -> List[float]:
        total = sum(self.magnitude_histogram)
        if total == 0:
            return [0.0] * 10
        return [c / total for c in self.magnitude_histogram]

    def normalised_region(self) -> List[float]:
        total = sum(self.region_histogram)
        if total == 0:
            return [0.0] * 8
        return [c / total for c in self.region_histogram]


# -- Drift verdict ---------------------------------------------------------

@dataclass(frozen=True)
class DriftVerdict:
    """Discrimination result for a detected behavioral change."""
    agent_id: str
    is_drift: bool          # True = likely strategy shift, False = likely attack
    confidence: float       # 0.0 to 1.0
    coherence_score: float  # high = correlated change across dimensions
    cohort_correlation: float  # high = other agents shifting similarly
    recommended_action: str  # "suppress_penalty", "normal", "amplify_penalty"


# -- Strategy drift discriminator ------------------------------------------

class StrategyDriftDiscriminator:
    """Discriminate legitimate strategy shifts from adversarial changes.

    Parameters
    ----------
    window_size :
        Rolling window for fingerprint computation.
    coherence_threshold :
        Minimum cross-dimension correlation to classify as drift.
    cohort_threshold :
        Minimum fraction of agents shifting to classify as cohort drift.
    """

    def __init__(
        self,
        window_size: int = 50,
        coherence_threshold: float = 0.6,
        cohort_threshold: float = 0.3,
    ) -> None:
        self._window = window_size
        self._coherence_threshold = coherence_threshold
        self._cohort_threshold = cohort_threshold
        self._current: Dict[str, BehavioralFingerprint] = {}
        self._history: Dict[str, Deque[BehavioralFingerprint]] = defaultdict(
            lambda: deque(maxlen=10),
        )
        self._contribution_buffer: Dict[str, List[Tuple[float, int]]] = defaultdict(list)

    # -- contribution recording --------------------------------------------

    def record_contribution(
        self,
        agent_id: str,
        magnitude: float,
        region: int,
    ) -> None:
        """Record a single contribution from an agent."""
        if agent_id not in self._current:
            self._current[agent_id] = BehavioralFingerprint()
        self._current[agent_id].record(magnitude, region)
        buf = self._contribution_buffer[agent_id]
        buf.append((magnitude, region))
        if len(buf) >= self._window:
            self._rotate_fingerprint(agent_id)

    # -- drift analysis ----------------------------------------------------

    def analyse(self, agent_id: str) -> DriftVerdict:
        """Analyse whether an agent's recent behavior indicates drift or attack."""
        history = self._history.get(agent_id)
        current = self._current.get(agent_id)

        if not history or not current:
            return DriftVerdict(
                agent_id, False, 0.0, 0.0, 0.0, "normal",
            )

        prev = history[-1]
        coherence = self._compute_coherence(prev, current)
        cohort = self._compute_cohort_correlation(agent_id)

        is_drift = coherence > self._coherence_threshold
        confidence = min(1.0, (coherence + cohort) / 2.0)

        if is_drift and cohort > self._cohort_threshold:
            action = "suppress_penalty"
        elif is_drift:
            action = "suppress_penalty"
        elif coherence < 0.3:
            action = "amplify_penalty"
        else:
            action = "normal"

        return DriftVerdict(
            agent_id, is_drift, confidence,
            coherence, cohort, action,
        )

    def analyse_all(self) -> Dict[str, DriftVerdict]:
        """Analyse all known agents."""
        return {aid: self.analyse(aid) for aid in self._current}

    @property
    def agent_count(self) -> int:
        return len(self._current)

    # -- internal ----------------------------------------------------------

    def _rotate_fingerprint(self, agent_id: str) -> None:
        """Archive current fingerprint and start fresh."""
        if agent_id in self._current:
            self._history[agent_id].append(self._current[agent_id])
        self._current[agent_id] = BehavioralFingerprint()
        self._contribution_buffer[agent_id] = []

    def _compute_coherence(
        self,
        prev: BehavioralFingerprint,
        current: BehavioralFingerprint,
    ) -> float:
        """Cross-dimension correlation of behavioral change.

        High coherence = change is correlated across magnitude and region
        dimensions (typical of strategy shift).  Low coherence = change
        is concentrated in one dimension (typical of attack).
        """
        mag_prev = prev.normalised_magnitude()
        mag_curr = current.normalised_magnitude()
        reg_prev = prev.normalised_region()
        reg_curr = current.normalised_region()

        mag_delta = [abs(a - b) for a, b in zip(mag_prev, mag_curr)]
        reg_delta = [abs(a - b) for a, b in zip(reg_prev, reg_curr)]

        mag_change = sum(mag_delta)
        reg_change = sum(reg_delta)

        if mag_change < 0.01 and reg_change < 0.01:
            return 0.0

        total = mag_change + reg_change
        if total < 0.01:
            return 0.0

        balance = 1.0 - abs(mag_change - reg_change) / total
        return balance

    def _compute_cohort_correlation(self, agent_id: str) -> float:
        """Fraction of other agents showing similar behavioral shifts."""
        if len(self._current) < 2:
            return 0.0

        target = self._current.get(agent_id)
        if not target:
            return 0.0

        target_mag = target.normalised_magnitude()
        similar = 0
        total = 0

        for aid, fp in self._current.items():
            if aid == agent_id:
                continue
            total += 1
            other_mag = fp.normalised_magnitude()
            cos_sim = _cosine_similarity(target_mag, other_mag)
            if cos_sim > 0.7:
                similar += 1

        return similar / max(total, 1)

    def __repr__(self) -> str:
        return f"StrategyDriftDiscriminator(agents={self.agent_count})"


# -- util ------------------------------------------------------------------

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (na * nb)
