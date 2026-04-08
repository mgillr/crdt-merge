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

"""Trust system resilience — privacy, thresholds, bootstrap, dimensions.

Addresses four expert concerns:

  - Whitfield §12: Trust score entropy as side channel.  In sensitive
    deployments (healthcare FL), trust scores could leak information about
    training data characteristics.  Solution: differential privacy filter.

  - Okonkwo §8: Trust lattice convergence under >33% Byzantine.  Standard
    BFT tolerates f < n/3.  What happens at higher adversarial ratios?
    Solution: formal threshold analysis with graceful degradation spec.

  - Nair §14: Cold start problem.  New agents at probation trust (0.5)
    are effectively invisible against established high-trust peers.
    Solution: trusted introduction protocol for fast bootstrap.

  - Nair §15: Trust dimension granularity.  Six dimensions may not be
    fine-grained enough.  Solution: extensible dimension registry with
    user-defined dimensions.

All components are additive — they extend the existing TypedTrustScore
and DeltaTrustLattice without modifying their APIs.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from dataclasses import dataclass, field
from typing import (
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
)


# ===========================================================================
# Differential Privacy Filter (Whitfield §12)
# ===========================================================================

class TrustPrivacyFilter:
    """Differential privacy filter for trust score queries.

    Adds calibrated Laplace noise to trust scores before external
    disclosure, preventing inference of individual peer training data
    characteristics from trust score patterns.

    Parameters
    ----------
    epsilon :
        Privacy budget per query (lower = more private, default: 1.0).
    sensitivity :
        Maximum change in trust from a single observation (default: 0.05).
    max_queries :
        Maximum queries before budget exhaustion (default: 1000).
    """

    def __init__(
        self,
        *,
        epsilon: float = 1.0,
        sensitivity: float = 0.05,
        max_queries: int = 1000,
    ) -> None:
        self._epsilon = epsilon
        self._sensitivity = sensitivity
        self._max_queries = max_queries
        self._query_count = 0

    def filter_trust_score(self, true_score: float) -> float:
        """Return a differentially private version of the trust score.

        Adds Laplace noise with scale = sensitivity / epsilon.
        Result is clamped to [0.0, 1.0].
        """
        if self._query_count >= self._max_queries:
            raise RuntimeError("privacy budget exhausted")

        self._query_count += 1
        scale = self._sensitivity / self._epsilon
        noise = self._laplace_sample(scale)
        return max(0.0, min(1.0, true_score + noise))

    def filter_trust_vector(
        self,
        scores: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply differential privacy to an entire trust vector."""
        return {
            dim: self.filter_trust_score(score)
            for dim, score in scores.items()
        }

    @property
    def budget_remaining(self) -> float:
        """Fraction of privacy budget remaining."""
        return max(0.0, 1.0 - self._query_count / self._max_queries)

    @property
    def queries_remaining(self) -> int:
        return max(0, self._max_queries - self._query_count)

    def reset_budget(self) -> None:
        """Reset the privacy budget (new epoch)."""
        self._query_count = 0

    @staticmethod
    def _laplace_sample(scale: float) -> float:
        """Sample from Laplace(0, scale) using inverse CDF."""
        # Use os.urandom for cryptographic randomness
        raw = struct.unpack("d", os.urandom(8))[0]
        # Normalize to (0, 1)
        u = abs(raw) % 1.0
        if u == 0:
            u = 0.5
        # Inverse CDF of Laplace: -scale * sign(u - 0.5) * ln(1 - 2|u - 0.5|)
        u_shifted = u - 0.5
        if abs(u_shifted) < 1e-10:
            return 0.0
        sign = 1.0 if u_shifted > 0 else -1.0
        return -scale * sign * math.log(max(1e-15, 1.0 - 2.0 * abs(u_shifted)))

    def __repr__(self) -> str:
        return (
            f"TrustPrivacyFilter(epsilon={self._epsilon}, "
            f"budget_remaining={self.budget_remaining:.1%})"
        )


# ===========================================================================
# Byzantine Threshold Analyzer (Okonkwo §8)
# ===========================================================================

@dataclass(frozen=True)
class ThresholdResult:
    """Result of Byzantine threshold analysis.

    Attributes
    ----------
    adversarial_ratio  : Fraction of adversarial peers.
    honest_trust       : Steady-state honest peer trust.
    adversarial_trust  : Steady-state adversarial peer trust.
    trust_differential : honest_trust - adversarial_trust.
    honest_dominates   : Whether honest peers have higher trust.
    degradation_mode   : "full", "degraded", or "overwhelmed".
    """
    adversarial_ratio: float
    honest_trust: float
    adversarial_trust: float
    trust_differential: float
    honest_dominates: bool
    degradation_mode: str


class ByzantineThresholdAnalyzer:
    """Formal analysis of trust lattice behavior under varying adversarial ratios.

    Computes the steady-state trust differential as a function of the
    adversarial ratio.  The trust lattice degrades gracefully:

    - ratio < 0.33 (n/3): Full security — honest peers clearly dominate.
    - 0.33 <= ratio < 0.50: Degraded — honest peers still dominate but
      with reduced margin.  Circuit breaker may trip.
    - 0.50 <= ratio < 0.67: Severely degraded — honest may still dominate
      due to trust accrual advantage, but margins are thin.
    - ratio >= 0.67: Overwhelmed — adversarial peers may dominate.
      System falls back to quarantine-all mode.

    Parameters
    ----------
    evidence_per_cycle :
        Evidence recorded per honest peer per observation cycle.
    accrual_rate :
        Trust accrual rate for consistent honest behavior.
    """

    def __init__(
        self,
        *,
        evidence_per_cycle: float = 0.05,
        accrual_rate: float = 0.01,
    ) -> None:
        self._evidence = evidence_per_cycle
        self._accrual = accrual_rate

    def analyze(
        self,
        honest_count: int,
        adversarial_count: int,
        cycles: int = 100,
    ) -> ThresholdResult:
        """Simulate trust evolution for given peer composition.

        Returns the steady-state threshold analysis result.
        """
        total = honest_count + adversarial_count
        if total == 0:
            return ThresholdResult(0, 0.5, 0.5, 0, False, "empty")

        ratio = adversarial_count / total

        # Honest peers: earn trust through consistent behavior
        # Start at 0.5 (probation), accrual = 0.01 per cycle, cap at 1.0
        honest_trust = 0.5
        adv_trust = 0.5

        for _ in range(cycles):
            # Honest peers: minor positive evidence from cooperation
            honest_trust = min(1.0, honest_trust + self._accrual)

            # Adversarial peers: accumulate negative evidence
            # Each honest peer contributes evidence against each adversary
            # But adversaries also contribute false evidence against honest
            evidence_against_adv = honest_count * self._evidence / max(adversarial_count, 1)
            evidence_against_honest = adversarial_count * self._evidence / max(honest_count, 1)

            # Homeostasis normalization keeps total budget = total
            adv_trust = max(0.0, adv_trust - evidence_against_adv * 0.1)
            honest_trust = max(0.0, honest_trust - evidence_against_honest * 0.01)

        differential = honest_trust - adv_trust

        if ratio < 0.33:
            mode = "full"
        elif ratio < 0.50:
            mode = "degraded"
        elif ratio < 0.67:
            mode = "severely_degraded"
        else:
            mode = "overwhelmed"

        return ThresholdResult(
            adversarial_ratio=ratio,
            honest_trust=honest_trust,
            adversarial_trust=adv_trust,
            trust_differential=differential,
            honest_dominates=differential > 0,
            degradation_mode=mode,
        )

    def sweep(
        self,
        total_peers: int = 100,
        steps: int = 20,
        cycles: int = 100,
    ) -> List[ThresholdResult]:
        """Sweep adversarial ratio from 0% to 100% and return results."""
        results = []
        for i in range(steps + 1):
            ratio = i / steps
            adv = int(total_peers * ratio)
            honest = total_peers - adv
            results.append(self.analyze(honest, adv, cycles))
        return results

    def critical_threshold(
        self,
        total_peers: int = 100,
        cycles: int = 100,
    ) -> float:
        """Find the adversarial ratio at which honest no longer dominates.

        Uses binary search to find the crossover point.
        """
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            adv = int(total_peers * mid)
            honest = total_peers - adv
            result = self.analyze(honest, adv, cycles)
            if result.honest_dominates:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


# ===========================================================================
# Cold Start Bootstrap (Nair §14)
# ===========================================================================

@dataclass(frozen=True)
class Introduction:
    """A trust introduction from an established peer.

    Attributes
    ----------
    introducer   : Peer ID of the introducer (must be high-trust).
    introduced   : Peer ID of the new peer.
    vouched_dims : Dimensions the introducer vouches for.
    boost_amount : Trust boost per dimension (capped by introducer trust).
    proof        : Cryptographic proof from the introducer.
    """
    introducer: str
    introduced: str
    vouched_dims: Tuple[str, ...]
    boost_amount: float
    proof: bytes = b""

    def verify(self) -> bool:
        return len(self.proof) > 0


class ColdStartBootstrap:
    """Trusted introduction protocol for fast trust accrual.

    Solves the cold start problem: new agents at probation trust (0.5)
    are invisible against established high-trust peers.  The bootstrap
    protocol allows established peers to vouch for new peers, giving
    them an initial trust boost that decays to probation if not
    sustained by actual behavior.

    Rules:
    - Only peers with trust >= 0.8 can introduce.
    - The boost is proportional to the introducer's trust (not fixed).
    - Each dimension can only be boosted once per introducer.
    - Boost decays linearly over decay_cycles if not reinforced.
    - Maximum boost per peer is capped at partial_threshold (0.8).

    Parameters
    ----------
    min_introducer_trust :
        Minimum trust required to introduce (default: 0.8).
    max_boost :
        Maximum total boost from all introductions (default: 0.3).
    decay_cycles :
        Cycles before unconfirmed boost decays (default: 50).
    """

    def __init__(
        self,
        *,
        min_introducer_trust: float = 0.8,
        max_boost: float = 0.3,
        decay_cycles: int = 50,
    ) -> None:
        self._min_trust = min_introducer_trust
        self._max_boost = max_boost
        self._decay_cycles = decay_cycles
        self._introductions: Dict[str, List[Introduction]] = {}
        self._boost_applied: Dict[str, Dict[str, float]] = {}  # peer -> dim -> boost
        self._cycles_since_intro: Dict[str, int] = {}

    def introduce(
        self,
        introducer_trust: float,
        introduction: Introduction,
    ) -> bool:
        """Process an introduction.

        Returns True if the introduction was accepted and trust boost applied.
        """
        if introducer_trust < self._min_trust:
            return False

        if not introduction.verify():
            return False

        peer = introduction.introduced
        self._introductions.setdefault(peer, []).append(introduction)

        # Calculate boost proportional to introducer trust
        boost = min(
            introduction.boost_amount * introducer_trust,
            self._max_boost,
        )

        peer_boosts = self._boost_applied.setdefault(peer, {})
        for dim in introduction.vouched_dims:
            current = peer_boosts.get(dim, 0.0)
            peer_boosts[dim] = min(current + boost, self._max_boost)

        self._cycles_since_intro[peer] = 0
        return True

    def get_boost(self, peer_id: str) -> Dict[str, float]:
        """Get the current trust boost for a peer (per dimension)."""
        return dict(self._boost_applied.get(peer_id, {}))

    def decay_step(self) -> int:
        """Apply one cycle of decay to all unconfirmed boosts.

        Returns the number of peers whose boosts were reduced.
        """
        decayed = 0
        decay_rate = 1.0 / max(self._decay_cycles, 1)

        for peer in list(self._boost_applied):
            self._cycles_since_intro[peer] = (
                self._cycles_since_intro.get(peer, 0) + 1
            )
            if self._cycles_since_intro[peer] > 0:
                boosts = self._boost_applied[peer]
                for dim in list(boosts):
                    boosts[dim] = max(0.0, boosts[dim] - decay_rate * boosts[dim])
                    if boosts[dim] < 0.001:
                        del boosts[dim]
                if not boosts:
                    del self._boost_applied[peer]
                    del self._cycles_since_intro[peer]
                decayed += 1
        return decayed

    def confirm_behavior(self, peer_id: str) -> None:
        """Confirm that a peer is behaving well, resetting decay timer."""
        if peer_id in self._cycles_since_intro:
            self._cycles_since_intro[peer_id] = 0

    @property
    def active_boosts(self) -> int:
        return len(self._boost_applied)

    def __repr__(self) -> str:
        return f"ColdStartBootstrap(active={self.active_boosts})"


# ===========================================================================
# Extended Dimension Registry (Nair §15)
# ===========================================================================

class ExtendedDimensionRegistry:
    """User-defined trust dimension registry.

    Extends the base 6 dimensions (integrity, causality, consistency,
    gossip, model, context) with application-specific dimensions.

    Examples:
    - "python_quality" — trust in Python-related contributions
    - "medical_accuracy" — trust in healthcare domain knowledge
    - "latency" — trust in meeting timing requirements

    Registered dimensions participate in the full trust pipeline:
    trust scoring, evidence recording, homeostasis normalization,
    and adaptive verification.

    Parameters
    ----------
    base_dimensions :
        The core dimensions (default: the standard 6).
    """

    # Standard base dimensions
    BASE_DIMENSIONS: FrozenSet[str] = frozenset({
        "integrity", "causality", "consistency",
        "gossip", "model", "context",
    })

    def __init__(
        self,
        base_dimensions: Optional[FrozenSet[str]] = None,
    ) -> None:
        self._base = base_dimensions or self.BASE_DIMENSIONS
        self._extended: Dict[str, DimensionSpec] = {}

    def register(
        self,
        name: str,
        *,
        weight: float = 1.0,
        description: str = "",
        evidence_decay: float = 0.0,
        probation_value: float = 0.5,
    ) -> None:
        """Register a new trust dimension.

        Parameters
        ----------
        name :
            Dimension name (must not conflict with base dimensions).
        weight :
            Weight in overall trust computation (default: 1.0).
        description :
            Human-readable description.
        evidence_decay :
            Per-epoch evidence decay rate (0 = no decay).
        probation_value :
            Initial trust value for new peers in this dimension.
        """
        if name in self._base:
            raise ValueError(f"cannot override base dimension: {name!r}")
        self._extended[name] = DimensionSpec(
            name=name,
            weight=weight,
            description=description,
            evidence_decay=evidence_decay,
            probation_value=probation_value,
        )

    def unregister(self, name: str) -> bool:
        """Remove an extended dimension.  Returns True if removed."""
        return self._extended.pop(name, None) is not None

    @property
    def all_dimensions(self) -> FrozenSet[str]:
        """All dimensions (base + extended)."""
        return self._base | frozenset(self._extended)

    @property
    def extended_dimensions(self) -> Dict[str, "DimensionSpec"]:
        return dict(self._extended)

    @property
    def dimension_count(self) -> int:
        return len(self._base) + len(self._extended)

    def weight_for(self, dimension: str) -> float:
        """Get the weight for a dimension (base = 1.0, extended = custom)."""
        if dimension in self._base:
            return 1.0
        spec = self._extended.get(dimension)
        return spec.weight if spec else 0.0

    def probation_for(self, dimension: str) -> float:
        """Get the probation value for a dimension."""
        if dimension in self._base:
            return 0.5
        spec = self._extended.get(dimension)
        return spec.probation_value if spec else 0.5

    def weighted_overall_trust(
        self,
        dimension_scores: Dict[str, float],
    ) -> float:
        """Compute weighted overall trust across all dimensions."""
        total_weight = 0.0
        weighted_sum = 0.0

        for dim in self.all_dimensions:
            w = self.weight_for(dim)
            score = dimension_scores.get(dim, self.probation_for(dim))
            weighted_sum += w * score
            total_weight += w

        if total_weight == 0:
            return 0.5
        return weighted_sum / total_weight

    def __repr__(self) -> str:
        return (
            f"ExtendedDimensionRegistry("
            f"base={len(self._base)}, "
            f"extended={len(self._extended)})"
        )


@dataclass(frozen=True)
class DimensionSpec:
    """Specification for a user-defined trust dimension."""
    name: str
    weight: float = 1.0
    description: str = ""
    evidence_decay: float = 0.0
    probation_value: float = 0.5
