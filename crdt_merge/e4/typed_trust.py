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

"""Multi-dimensional typed trust scores with homeostatic normalization.

Implements the typed trust lattice (ref 820) from the E4 architecture.
Each peer carries a trust vector across six dimensions, backed by
GCounter-based evidence tracking per observer. Trust scores are CRDTs:
merge is element-wise max per dimension per observer.

Trust homeostasis (ref 828) maintains a conserved budget across all peers,
preventing inflation in long-running clusters while preserving rank order.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional


# -- Trust dimensions ---------------------------------------------------

TRUST_DIMENSIONS: FrozenSet[str] = frozenset({
    "integrity",    # Merkle hash violations (ref 822)
    "causality",    # Vector clock regressions (ref 823)
    "consistency",  # CRDT invariant violations (ref 824)
    "gossip",       # Stale / invalid gossip entries (ref 825)
    "model",        # Model parameter anomalies (ref 826)
    "context",      # Context merge conflicts
})

# -- Thresholds (ref 896-899) ------------------------------------------

PROBATION_TRUST = 0.5
QUARANTINE_THRESHOLD = 0.1
LOW_TRUST_THRESHOLD = 0.4
PARTIAL_THRESHOLD = 0.8


# -- TypedTrustScore ----------------------------------------------------

@dataclass
class TypedTrustScore:
    # Resilience: optional differential privacy filter (v0.9.5.1)
    _privacy_filter = None

    @classmethod
    def enable_privacy_filtering(cls, epsilon: float = 1.0, **kwargs):
        """Enable differential privacy for trust score queries.

        Adds calibrated Laplace noise to trust scores when queried by
        external systems, preventing trust score inference attacks
        while maintaining CRDT convergence properties.

        The noise is calibrated so that:
        - Internal CRDT operations use exact scores (no noise).
        - External queries receive epsilon-differentially private scores.
        - Aggregate trust ordering is preserved with high probability.

        See: resilience/trust_resilience.py (addresses Whitfield §12)
        """
        from crdt_merge.e4.resilience.trust_resilience import TrustPrivacyFilter
        cls._privacy_filter = TrustPrivacyFilter(epsilon=epsilon, **kwargs)

    @classmethod
    def disable_privacy_filtering(cls):
        """Disable differential privacy filtering."""
        cls._privacy_filter = None

    """Multi-dimensional trust score with GCounter evidence tracking.

    Each dimension maps observer IDs to accumulated negative-evidence
    counters.  Trust for a dimension = max(0, 1 - total_evidence).
    The structure is a CRDT: merge takes the element-wise max per
    dimension per observer (GCounter semantics).
    """

    _evidence: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # -- constructors ---------------------------------------------------

    @classmethod
    def probationary(cls) -> TypedTrustScore:
        """Return a score at the probation level (no evidence yet)."""
        return cls(_evidence={})

    @classmethod
    def full_trust(cls) -> TypedTrustScore:
        """Return a score representing zero observed violations."""
        return cls(_evidence={})

    # -- per-dimension trust --------------------------------------------

    def trust_for_dimension(self, dimension: str) -> float:
        """Trust in *dimension*, range [0.0, 1.0].

        Dimensions with no evidence default to PROBATION_TRUST for new
        peers.  Once any observer records evidence, the dimension is
        tracked explicitly.
        """
        obs = self._evidence.get(dimension)
        if obs is None:
            return PROBATION_TRUST
        total = sum(obs.values())
        return max(0.0, 1.0 - total)

    def overall_trust(self) -> float:
        """Weighted mean across all six dimensions."""
        return sum(self.trust_for_dimension(d) for d in TRUST_DIMENSIONS) / len(TRUST_DIMENSIONS)

    # Convenience alias used by higher-level APIs
    composite = overall_trust

    # -- adaptive immune level (ref 895) --------------------------------

    def verification_level(self) -> int:
        """Adaptive immune verification level.

        0 -- trust > 0.8  : signature only, O(1)
        1 -- trust 0.4-0.8: signature + Merkle root, O(1)
        2 -- trust < 0.4  : full aggregate PCO, O(k log n)
        3 -- trust < 0.1  : reject, O(1)
        """
        # Round to 12 decimal places to avoid floating-point boundary errors.
        # Without this, overall_trust() returning 0.7999999999999999 instead
        # of 0.8 would cause a trust level downgrade on an exact boundary.
        t = round(self.overall_trust(), 12)
        if t < QUARANTINE_THRESHOLD:
            return 3
        if t < LOW_TRUST_THRESHOLD:
            return 2
        if t < PARTIAL_THRESHOLD:
            return 1
        return 0

    # -- evidence recording (GCounter increment) ------------------------

    def record_evidence(
        self,
        observer: str,
        dimension: str,
        amount: float,
        proof: object,
    ) -> TypedTrustScore:
        """Record verified negative evidence from *observer*.

        Returns a **new** TypedTrustScore (immutable-style API).
        The *proof* object must expose a ``verify()`` method that
        returns True; otherwise ``ValueError`` is raised.
        """
        if not getattr(proof, "verify", lambda: False)():
            raise ValueError("evidence proof failed verification")

        new_ev = _deep_copy_evidence(self._evidence)
        dim_obs = new_ev.setdefault(dimension, {})
        current = dim_obs.get(observer, 0.0)
        # GCounter: monotonically increasing
        dim_obs[observer] = max(current, current + amount)
        return TypedTrustScore(_evidence=new_ev)

    # -- CRDT merge (element-wise max) ----------------------------------

    def merge(self, other: TypedTrustScore) -> TypedTrustScore:
        """CRDT merge -- element-wise max per dimension per observer."""
        merged: Dict[str, Dict[str, float]] = {}
        all_dims = set(self._evidence) | set(other._evidence)
        for dim in all_dims:
            s_obs = self._evidence.get(dim, {})
            o_obs = other._evidence.get(dim, {})
            dim_merged: Dict[str, float] = {}
            for obs in set(s_obs) | set(o_obs):
                dim_merged[obs] = max(s_obs.get(obs, 0.0), o_obs.get(obs, 0.0))
            merged[dim] = dim_merged
        return TypedTrustScore(_evidence=merged)

    # -- serialization helpers ------------------------------------------

    def serialize(self) -> bytes:
        """Compact deterministic serialization for Merkle binding."""
        parts: list[str] = []
        for dim in sorted(TRUST_DIMENSIONS):
            score = self.trust_for_dimension(dim)
            parts.append(f"{dim}:{score:.6f}")
        return "|".join(parts).encode("utf-8")

    def hash(self) -> str:
        """SHA-256 hex digest of the serialized trust vector."""
        import hashlib
        return hashlib.sha256(self.serialize()).hexdigest()

    # -- repr -----------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TypedTrustScore(overall={self.overall_trust():.3f}, "
            f"level={self.verification_level()})"
        )


# -- TrustHomeostasis (ref 828) -----------------------------------------

class TrustHomeostasis:
    """Conserved-budget normalization across all peers.

    After every observation cycle the total trust in each dimension is
    rescaled so that ``sum(trust_d) == peer_count`` for every dimension
    *d*.  This prevents inflation while preserving rank order.
    """

    @staticmethod
    def normalize(
        scores: Dict[str, TypedTrustScore],
        peer_count: int,
    ) -> Dict[str, TypedTrustScore]:
        """Return a new dict of rescaled trust scores.

        The normalization works in evidence-space: since trust = 1 - evidence,
        we adjust evidence totals so that ``sum(1 - evidence_d) == peer_count``
        across peers for each dimension.  If total raw trust is already zero
        the dimension is left unchanged (all peers quarantined).
        """
        if not scores or peer_count <= 0:
            return dict(scores)

        # Collect raw trust per dimension
        dim_raw: Dict[str, Dict[str, float]] = {}
        for dim in TRUST_DIMENSIONS:
            dim_raw[dim] = {
                pid: ts.trust_for_dimension(dim) for pid, ts in scores.items()
            }

        # Compute per-dimension scale factors
        scale: Dict[str, float] = {}
        for dim in TRUST_DIMENSIONS:
            total = sum(dim_raw[dim].values())
            if total > 0:
                scale[dim] = peer_count / total
            else:
                scale[dim] = 1.0

        # Rebuild evidence dicts with adjusted values
        result: Dict[str, TypedTrustScore] = {}
        for pid, ts in scores.items():
            new_ev: Dict[str, Dict[str, float]] = {}
            for dim in TRUST_DIMENSIONS:
                raw_trust = dim_raw[dim].get(pid, PROBATION_TRUST)
                scaled_trust = min(1.0, max(0.0, raw_trust * scale[dim]))
                # trust = 1 - evidence  =>  evidence = 1 - scaled_trust
                # Distribute evidence uniformly to a synthetic observer
                target_ev = max(0.0, 1.0 - scaled_trust)

                orig_obs = ts._evidence.get(dim, {})
                if orig_obs:
                    orig_total = sum(orig_obs.values())
                    if orig_total > 0:
                        ev_scale = target_ev / orig_total
                        new_ev[dim] = {
                            obs: val * ev_scale for obs, val in orig_obs.items()
                        }
                    else:
                        new_ev[dim] = dict(orig_obs)
                elif target_ev > 0:
                    new_ev[dim] = {"_homeostasis": target_ev}

            result[pid] = TypedTrustScore(_evidence=new_ev)

        return result


# -- helpers ------------------------------------------------------------

def _deep_copy_evidence(
    evidence: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    return {dim: dict(obs) for dim, obs in evidence.items()}
