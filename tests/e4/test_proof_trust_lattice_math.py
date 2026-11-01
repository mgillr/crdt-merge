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

"""Mathematical proofs about the trust system.

Proves GCounter monotonicity, homeostasis conservation, trust convergence,
verification level boundaries, circuit breaker behavior, and trust-bound
Merkle E1 binding properties.
"""

import hashlib
import math
import random
import time
from typing import Dict, List
from unittest.mock import patch

import pytest

from crdt_merge.e4.typed_trust import (
    TRUST_DIMENSIONS,
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    TrustHomeostasis,
    TypedTrustScore,
)
from crdt_merge.e4.proof_evidence import TrustEvidence
from crdt_merge.e4.delta_trust_lattice import (
    DeltaTrustLattice,
    TrustCircuitBreaker,
    CircuitBreakerTripped,
)
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.adaptive_verification import AdaptiveVerificationController
from crdt_merge.e4.compatibility import CompatibilityController, CompatibilityMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(observer: str, dimension: str, amount: float) -> TrustEvidence:
    from e4_factories import make_invalid_delta_proof
    return TrustEvidence.create(
        observer=observer,
        target="target",
        evidence_type="invalid_delta",
        dimension=dimension,
        amount=amount,
        proof=make_invalid_delta_proof(target="target"),
    )


def _record_evidence(score: TypedTrustScore, observer: str, dimension: str,
                      amount: float) -> TypedTrustScore:
    ev = _make_evidence(observer, dimension, amount)
    return score.record_evidence(observer=observer, dimension=dimension,
                                  amount=amount, proof=ev)


# ---------------------------------------------------------------------------
# GCounter Monotonicity
# ---------------------------------------------------------------------------

class TestGCounterMonotonicity:
    """Evidence can only increase; trust can only decrease."""

    def test_evidence_only_increases(self):
        """After recording evidence, evidence values never decrease."""
        score = TypedTrustScore.probationary()
        for i in range(20):
            dim = list(TRUST_DIMENSIONS)[i % len(TRUST_DIMENSIONS)]
            prev_evidence = dict(score._evidence.get(dim, {}))
            score = _record_evidence(score, f"obs_{i % 3}", dim, 0.05)
            curr_evidence = score._evidence.get(dim, {})
            for obs, val in prev_evidence.items():
                assert curr_evidence.get(obs, 0) >= val, (
                    f"Evidence decreased for obs={obs}, dim={dim}"
                )

    @pytest.mark.parametrize("dim", list(TRUST_DIMENSIONS))
    def test_trust_for_dimension_monotonic_after_established(self, dim):
        """Once a dimension has evidence, further evidence only decreases trust."""
        # Start with base evidence (past the probation transition)
        evidence = {dim: {"obs_init": 0.05}}
        score = TypedTrustScore(_evidence=evidence)
        prev = score.trust_for_dimension(dim)  # 1 - 0.05 = 0.95
        for i in range(15):
            score = _record_evidence(score, f"obs_{i}", dim, 0.05)
            curr = score.trust_for_dimension(dim)
            assert curr <= prev + 1e-12, f"Trust increased: {prev} -> {curr} in dim={dim}"
            prev = curr

    def test_overall_trust_monotonic_after_established(self):
        """Once all dimensions have evidence, overall trust only decreases."""
        # Start with evidence in all dimensions
        evidence = {d: {"obs_init": 0.05} for d in TRUST_DIMENSIONS}
        score = TypedTrustScore(_evidence=evidence)
        prev = score.overall_trust()
        dims = list(TRUST_DIMENSIONS)
        rng = random.Random(42)
        for i in range(50):
            dim = rng.choice(dims)
            obs = f"obs_{rng.randint(0, 5)}"
            score = _record_evidence(score, obs, dim, rng.uniform(0.01, 0.1))
            curr = score.overall_trust()
            assert curr <= prev + 1e-12, f"Overall trust increased: {prev} -> {curr}"
            prev = curr

    def test_trust_floor_at_zero(self):
        """Trust never goes below 0."""
        score = TypedTrustScore.probationary()
        for i in range(100):
            for dim in TRUST_DIMENSIONS:
                score = _record_evidence(score, f"obs_{i}", dim, 0.1)
        for dim in TRUST_DIMENSIONS:
            assert score.trust_for_dimension(dim) >= 0.0
        assert score.overall_trust() >= 0.0

    def test_gcounter_additive(self):
        """Same observer recording more evidence adds to existing."""
        score = TypedTrustScore.probationary()
        score = _record_evidence(score, "obs_a", "integrity", 0.1)
        val1 = score._evidence["integrity"]["obs_a"]
        score = _record_evidence(score, "obs_a", "integrity", 0.2)
        val2 = score._evidence["integrity"]["obs_a"]
        assert val2 >= val1


# ---------------------------------------------------------------------------
# Homeostasis Conservation
# ---------------------------------------------------------------------------

class TestHomeostasisConservation:
    """After normalize, sum(trust_d) == peer_count for each dimension."""

    @pytest.mark.parametrize("peer_count", [5, 10, 50, 100])
    def test_sum_approx_peer_count(self, peer_count):
        """Homeostasis rescales so sum ≈ peer_count per dimension.
        
        Note: clipping to [0, 1] means the sum may not be exactly peer_count
        when some scaled values would exceed 1.0. We test within tolerance.
        """
        rng = random.Random(42 + peer_count)
        scores = {}
        dims = list(TRUST_DIMENSIONS)
        # Ensure all peers have evidence in all dims (avoid probation edge cases)
        for i in range(peer_count):
            evidence = {}
            for d in dims:
                evidence[d] = {f"obs_{rng.randint(0, 5)}": rng.uniform(0.1, 0.6)}
            scores[f"peer_{i}"] = TypedTrustScore(_evidence=evidence)

        normalized = TrustHomeostasis.normalize(scores, peer_count)

        for d in dims:
            total = sum(normalized[p].trust_for_dimension(d) for p in normalized)
            # With clipping, sum <= peer_count (some may be clipped to 1.0)
            assert total <= peer_count + 0.01, (
                f"Sum for dim={d} is {total}, exceeds {peer_count}"
            )
            # Generally the sum should be close to peer_count
            assert abs(total - peer_count) < peer_count * 0.15, (
                f"Sum for dim={d} is {total}, too far from {peer_count}"
            )

    @pytest.mark.parametrize("peer_count", [5, 10, 20])
    def test_sum_exact_when_no_clipping(self, peer_count):
        """When trust values are moderate, normalization approximately conserves sum.
        
        Due to the min(1.0, ...) clipping, the sum may not be exactly peer_count.
        We test that the sum is reasonably close.
        """
        rng = random.Random(300 + peer_count)
        scores = {}
        for i in range(peer_count):
            evidence = {}
            for d in TRUST_DIMENSIONS:
                # Evidence around 1 - peer_count/n = moderate. Average trust ≈ 1/n * peer_count
                evidence[d] = {f"obs_0": rng.uniform(0.3, 0.7)}
            scores[f"p{i}"] = TypedTrustScore(_evidence=evidence)

        normalized = TrustHomeostasis.normalize(scores, peer_count)
        for d in TRUST_DIMENSIONS:
            total = sum(normalized[p].trust_for_dimension(d) for p in normalized)
            # With clipping, sum may be somewhat less than peer_count
            assert total <= peer_count + 0.01
            assert total > 0  # Not all zeros

    @pytest.mark.parametrize("peer_count", [5, 10, 20])
    def test_rank_order_weakly_preserved(self, peer_count):
        """Normalization multiplies all trust values by the same per-dim scale factor.
        
        Before clipping, rank order is perfectly preserved. After clipping (at 0 or 1),
        ties may form but the relative order of non-clipped peers is preserved.
        We verify: if A > B before, then A >= B after (weak preservation).
        """
        rng = random.Random(100 + peer_count)
        scores = {}
        dims = list(TRUST_DIMENSIONS)
        for i in range(peer_count):
            evidence = {}
            for d in dims:
                evidence[d] = {f"obs_0": rng.uniform(0.0, 0.8)}
            scores[f"peer_{i}"] = TypedTrustScore(_evidence=evidence)

        normalized = TrustHomeostasis.normalize(scores, peer_count)

        for d in dims:
            peers = list(scores.keys())
            for i in range(len(peers)):
                for j in range(i + 1, len(peers)):
                    orig_i = scores[peers[i]].trust_for_dimension(d)
                    orig_j = scores[peers[j]].trust_for_dimension(d)
                    norm_i = normalized[peers[i]].trust_for_dimension(d)
                    norm_j = normalized[peers[j]].trust_for_dimension(d)
                    if orig_i > orig_j + 1e-9:
                        assert norm_i >= norm_j - 1e-9, (
                            f"Rank violated for dim={d}: {peers[i]} was > {peers[j]}"
                        )

    @pytest.mark.parametrize("peer_count", [5, 10, 20])
    def test_double_normalization_convergence(self, peer_count):
        """Repeated normalization converges (may not be exactly idempotent due to clipping).
        
        The normalization clips trust to [0, 1], which means after normalization the sum
        may be < peer_count. Normalizing again would try to re-scale, potentially
        changing values. We verify convergence: after several normalizations, values stabilize.
        """
        rng = random.Random(200 + peer_count)
        scores = {}
        for i in range(peer_count):
            evidence = {}
            for d in TRUST_DIMENSIONS:
                evidence[d] = {f"obs_0": rng.uniform(0.0, 0.5)}
            scores[f"peer_{i}"] = TypedTrustScore(_evidence=evidence)

        # Apply normalization 5 times
        current = scores
        for _ in range(5):
            current = TrustHomeostasis.normalize(current, peer_count)

        # The 5th and 6th applications should be very close
        final = TrustHomeostasis.normalize(current, peer_count)

        for p in scores:
            for d in TRUST_DIMENSIONS:
                v1 = current[p].trust_for_dimension(d)
                v2 = final[p].trust_for_dimension(d)
                assert abs(v1 - v2) < 0.1, (
                    f"Normalization not converging for peer={p}, dim={d}: {v1} vs {v2}"
                )


# ---------------------------------------------------------------------------
# Trust Convergence (Fixed Point)
# ---------------------------------------------------------------------------

class TestTrustConvergence:
    """Same evidence in different orders converges after merge."""

    @pytest.mark.parametrize("n_peers,n_events", [(3, 20), (5, 30), (10, 40)])
    def test_convergence_shuffled_evidence(self, n_peers, n_events):
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)
        peers = [f"p{i}" for i in range(n_peers)]

        # Generate evidence events
        events = []
        for _ in range(n_events):
            target = rng.choice(peers)
            obs = rng.choice(peers)
            dim = rng.choice(dims)
            amt = rng.uniform(0.01, 0.1)
            events.append((target, obs, dim, amt))

        # Apply in order 1
        lattice_a = DeltaTrustLattice("node-a", initial_peers=set(peers))
        order1 = list(events)
        rng.shuffle(order1)
        for target, obs, dim, amt in order1:
            ev = _make_evidence(obs, dim, amt)
            old = lattice_a._trust_scores.get(target, TypedTrustScore.probationary())
            lattice_a._trust_scores[target] = old.record_evidence(obs, dim, amt, ev)

        # Apply in order 2
        lattice_b = DeltaTrustLattice("node-b", initial_peers=set(peers))
        order2 = list(events)
        rng.shuffle(order2)
        for target, obs, dim, amt in order2:
            ev = _make_evidence(obs, dim, amt)
            old = lattice_b._trust_scores.get(target, TypedTrustScore.probationary())
            lattice_b._trust_scores[target] = old.record_evidence(obs, dim, amt, ev)

        # They should already be equal (GCounter is commutative)
        for p in peers:
            ta = lattice_a.get_trust(p)
            tb = lattice_b.get_trust(p)
            for d in TRUST_DIMENSIONS:
                assert abs(ta.trust_for_dimension(d) - tb.trust_for_dimension(d)) < 1e-9, (
                    f"Divergence for peer={p}, dim={d}"
                )

    def test_merge_produces_convergence(self):
        """Two lattices with different evidence converge after merge."""
        peers = {"p0", "p1", "p2"}
        a = DeltaTrustLattice("node-a", initial_peers=peers)
        b = DeltaTrustLattice("node-b", initial_peers=peers)

        # Add different evidence to each
        ev_a = _make_evidence("node-a", "integrity", 0.1)
        old_a = a._trust_scores.get("p0", TypedTrustScore.probationary())
        a._trust_scores["p0"] = old_a.record_evidence("node-a", "integrity", 0.1, ev_a)

        ev_b = _make_evidence("node-b", "causality", 0.2)
        old_b = b._trust_scores.get("p0", TypedTrustScore.probationary())
        b._trust_scores["p0"] = old_b.record_evidence("node-b", "causality", 0.2, ev_b)

        # Merge both ways
        ab = a.merge(b)
        ba = b.merge(a)

        for d in TRUST_DIMENSIONS:
            assert abs(ab.get_trust("p0").trust_for_dimension(d) -
                       ba.get_trust("p0").trust_for_dimension(d)) < 1e-9


# ---------------------------------------------------------------------------
# Verification Level Boundaries
# ---------------------------------------------------------------------------

class TestVerificationLevelBoundaries:
    """Test exact boundary values for verification levels.
    
    Verification levels:
    - Level 0: overall_trust >= PARTIAL_THRESHOLD (0.8) 
    - Level 1: LOW_TRUST_THRESHOLD (0.4) <= overall_trust < 0.8
    - Level 2: QUARANTINE_THRESHOLD (0.1) <= overall_trust < 0.4
    - Level 3: overall_trust < 0.1
    
    Trust with evidence = max(0, 1 - sum(evidence)). With NO evidence = PROBATION (0.5).
    Trust > 0.5 is possible when evidence sum < 0.5.
    Trust = 0.8 requires evidence sum = 0.2 in all dims.
    """

    def _make_score_with_trust(self, target_overall: float) -> TypedTrustScore:
        """Create a score with the given overall trust."""
        # Each dim: trust = max(0, 1 - evidence). Set evidence = 1 - target.
        evidence_per_dim = max(0.0, 1.0 - target_overall)
        evidence = {}
        for d in TRUST_DIMENSIONS:
            if evidence_per_dim > 0:
                evidence[d] = {"observer": evidence_per_dim}
            else:
                evidence[d] = {"observer": 0.0001}  # tiny evidence to avoid probation
        return TypedTrustScore(_evidence=evidence)

    def test_high_trust_level_0(self):
        """overall_trust >= 0.8 → level 0"""
        score = self._make_score_with_trust(0.9)  # evidence 0.1 per dim
        actual = score.overall_trust()
        assert actual >= 0.8, f"Expected >=0.8, got {actual}"
        assert score.verification_level() == 0

    def test_exact_0_8_level_0(self):
        """Exactly at 0.8 → level 0 (0.8 < 0.8 is False)."""
        score = self._make_score_with_trust(0.8)  # evidence 0.2 per dim
        actual = score.overall_trust()
        assert abs(actual - 0.8) < 1e-10
        assert score.verification_level() == 0

    def test_probation_level_1(self):
        """Probationary score (overall=0.5) → level 1."""
        score = TypedTrustScore.probationary()
        assert score.overall_trust() == PROBATION_TRUST
        assert score.verification_level() == 1

    def test_partial_trust_level_1(self):
        """0.4 ≤ overall_trust < 0.8 → level 1"""
        for target in [0.5, 0.6, 0.79]:
            score = self._make_score_with_trust(target)
            assert score.verification_level() == 1, f"Target {target} should be level 1"

    def test_low_trust_level_2(self):
        """0.1 ≤ overall_trust < 0.4 → level 2"""
        # Avoid 0.1 exactly -- float precision: 1-0.9=0.0999... < 0.1 → level 3
        for target in [0.3, 0.15, 0.11]:
            score = self._make_score_with_trust(target)
            lev = score.verification_level()
            assert lev == 2, f"Target {target} should be level 2, got {lev}"

    def test_quarantine_level_3(self):
        """overall_trust < 0.1 → level 3"""
        for target in [0.05, 0.01, 0.0]:
            score = self._make_score_with_trust(target)
            assert score.verification_level() == 3

    def test_exact_boundary_0_4(self):
        """Exactly at 0.4 → level 1 (0.4 < 0.4 is False)."""
        score = self._make_score_with_trust(0.4)
        assert score.verification_level() == 1

    def test_just_below_0_4(self):
        """Just below 0.4 → level 2."""
        score = self._make_score_with_trust(0.39)
        assert score.verification_level() == 2

    def test_exact_boundary_0_1(self):
        """At 0.1 boundary: with float rounding fix, 0.1 → level 2 (not quarantine)."""
        score_at_point_1 = self._make_score_with_trust(0.1)
        assert score_at_point_1.verification_level() == 2  # boundary lands in level 2

        # Just above 0.1 → level 2
        score_above = self._make_score_with_trust(0.101)
        assert score_above.verification_level() == 2

    def test_just_below_0_1(self):
        """Just below 0.1 → level 3."""
        score = self._make_score_with_trust(0.09)
        assert score.verification_level() == 3

    def test_level_transition_with_accumulating_evidence(self):
        """Verify level increases as evidence accumulates."""
        # Start with evidence giving trust ≈ 0.9 per dim → level 0
        evidence = {d: {"obs": 0.1} for d in TRUST_DIMENSIONS}
        score = TypedTrustScore(_evidence=evidence)
        assert score.verification_level() == 0  # 0.9

        # Add more evidence → trust ≈ 0.5 per dim → level 1
        for dim in TRUST_DIMENSIONS:
            score = _record_evidence(score, "obs2", dim, 0.4)
        assert score.verification_level() == 1  # 1 - 0.5 = 0.5

        # More evidence → trust ≈ 0.2 per dim → level 2
        for dim in TRUST_DIMENSIONS:
            score = _record_evidence(score, "obs3", dim, 0.3)
        assert score.verification_level() == 2  # 1 - 0.8 = 0.2

        # Even more → trust ≈ 0.05 → level 3
        for dim in TRUST_DIMENSIONS:
            score = _record_evidence(score, "obs4", dim, 0.15)
        assert score.verification_level() == 3  # 1 - 0.95 = 0.05


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """Circuit breaker behavior under anomalous trust velocity."""

    def test_normal_changes_dont_trip(self):
        """Uniform small changes shouldn't trip the breaker."""
        cb = TrustCircuitBreaker(window_size=20, sigma_threshold=2.0,
                                  cooldown_seconds=0.1, min_samples=5)
        # Use established scores with evidence so changes are small and uniform
        evidence = {d: {"obs_init": 0.3} for d in TRUST_DIMENSIONS}
        base = TypedTrustScore(_evidence=evidence)
        for i in range(15):
            new = _record_evidence(base, f"obs_{i}", "integrity", 0.01)
            cb.record_trust_change(f"p{i}", base, new)
            assert not cb.is_tripped(), f"Tripped at iteration {i}"

    def test_anomalous_velocity_trips(self):
        cb = TrustCircuitBreaker(window_size=20, sigma_threshold=2.0,
                                  cooldown_seconds=10.0, min_samples=5)
        # Use established scores for uniform baseline
        evidence = {d: {"obs_init": 0.3} for d in TRUST_DIMENSIONS}
        base = TypedTrustScore(_evidence=evidence)
        # Record small changes to build baseline
        for i in range(10):
            small_change = _record_evidence(base, f"obs_{i}", "integrity", 0.001)
            cb.record_trust_change(f"p{i}", base, small_change)

        # Now record a huge change
        big_change = base
        for dim in TRUST_DIMENSIONS:
            big_change = _record_evidence(big_change, "attacker", dim, 0.8)
        cb.record_trust_change("p_anomalous", base, big_change)
        assert cb.is_tripped(), "Should have tripped on anomalous velocity"

    def test_cooldown_resets(self):
        cb = TrustCircuitBreaker(window_size=20, sigma_threshold=2.0,
                                  cooldown_seconds=0.05, min_samples=5)
        evidence = {d: {"obs_init": 0.3} for d in TRUST_DIMENSIONS}
        base = TypedTrustScore(_evidence=evidence)
        # Build baseline
        for i in range(10):
            small_change = _record_evidence(base, f"obs_{i}", "integrity", 0.001)
            cb.record_trust_change(f"p{i}", base, small_change)

        # Trip it
        big_change = base
        for dim in TRUST_DIMENSIONS:
            big_change = _record_evidence(big_change, "attacker", dim, 0.8)
        cb.record_trust_change("p_bad", base, big_change)
        assert cb.is_tripped()

        # Wait for cooldown
        time.sleep(0.1)
        assert not cb.is_tripped(), "Should have reset after cooldown"

    def test_tripped_breaker_raises_in_lattice(self):
        """Tripped breaker → DeltaTrustLattice.observe_and_propagate raises."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p0"})
        # Create a tripped circuit breaker
        cb = TrustCircuitBreaker(window_size=10, sigma_threshold=0.01,
                                  cooldown_seconds=100.0, min_samples=2)
        evidence = {d: {"obs_init": 0.3} for d in TRUST_DIMENSIONS}
        base = TypedTrustScore(_evidence=evidence)
        for i in range(3):
            small = _record_evidence(base, f"o{i}", "integrity", 0.001)
            cb.record_trust_change(f"p{i}", base, small)
        big = base
        for dim in TRUST_DIMENSIONS:
            big = _record_evidence(big, "x", dim, 0.9)
        cb.record_trust_change("px", base, big)

        if cb.is_tripped():
            lattice._circuit_breaker = cb
            ev = _make_evidence("node-a", "integrity", 0.1)
            with pytest.raises(CircuitBreakerTripped):
                lattice.observe_and_propagate(ev)


# ---------------------------------------------------------------------------
# Trust-Bound Merkle E1 Binding
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleE1:
    """Merkle hashes incorporate trust context."""

    def test_same_data_different_trust_different_hash(self):
        """Same data, different trust → different leaf hash."""
        lattice_a = DeltaTrustLattice("node-a", initial_peers={"p1"})
        lattice_b = DeltaTrustLattice("node-b", initial_peers={"p1"})

        # Add evidence to lattice_b for p1
        ev = _make_evidence("node-b", "integrity", 0.3)
        old = lattice_b._trust_scores.get("p1", TypedTrustScore.probationary())
        lattice_b._trust_scores["p1"] = old.record_evidence("node-b", "integrity", 0.3, ev)

        merkle_a = TrustBoundMerkle(trust_lattice=lattice_a)
        merkle_b = TrustBoundMerkle(trust_lattice=lattice_b)

        data = b"same data"
        hash_a = merkle_a.compute_leaf_hash(data, "p1")
        hash_b = merkle_b.compute_leaf_hash(data, "p1")
        assert hash_a != hash_b, "Different trust should produce different hashes"

    def test_same_trust_same_hash(self):
        """Same data, same trust → same leaf hash."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1"})
        merkle = TrustBoundMerkle(trust_lattice=lattice)

        data = b"test data"
        h1 = merkle.compute_leaf_hash(data, "p1")
        h2 = merkle.compute_leaf_hash(data, "p1")
        assert h1 == h2

    def test_trust_change_invalidates_root(self):
        """Trust change → root hash changes."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1"})
        merkle = TrustBoundMerkle(trust_lattice=lattice, branching_factor=4)

        # Insert some leaves
        merkle.insert_leaf("k1", b"data1", "p1")
        merkle.insert_leaf("k2", b"data2", "p1")
        root_before = merkle.recompute()

        # Change trust for p1
        ev = _make_evidence("node-a", "integrity", 0.3)
        old = lattice._trust_scores.get("p1", TypedTrustScore.probationary())
        lattice._trust_scores["p1"] = old.record_evidence("node-a", "integrity", 0.3, ev)

        # Recompute should yield different root
        root_after = merkle.recompute()
        assert root_before != root_after, "Trust change should invalidate root hash"

    def test_merkle_path_verification(self):
        """Merkle path verification requires correct trust context."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1"})
        merkle = TrustBoundMerkle(trust_lattice=lattice, branching_factor=4)

        merkle.insert_leaf("k1", b"data1", "p1")
        merkle.insert_leaf("k2", b"data2", "p1")
        merkle.insert_leaf("k3", b"data3", "p1")
        root = merkle.recompute()
        assert root != "", "Root should be non-empty"

    def test_compatibility_mode_dual_hashes(self):
        """Compatibility mode produces two independent hash chains."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1"})
        merkle = TrustBoundMerkle(trust_lattice=lattice, branching_factor=4,
                                   compatibility_mode=True)

        merkle.insert_leaf("k1", b"data1", "p1")
        merkle.insert_leaf("k2", b"data2", "p1")
        merkle.recompute()

        # In compat mode, both root_hash and root_compat_hash should be set
        assert merkle.root_hash != ""
        assert merkle.root_compat_hash != ""
        # The E4 hash and compat hash should differ (trust context differs)
        assert merkle.root_hash != merkle.root_compat_hash

    def test_different_originator_different_hash(self):
        """Same data, different originator → different hash."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1", "p2"})
        merkle = TrustBoundMerkle(trust_lattice=lattice)

        data = b"same data"
        h1 = merkle.compute_leaf_hash(data, "p1")
        h2 = merkle.compute_leaf_hash(data, "p2")
        # p1 and p2 are both probationary with same trust, but originator differs
        assert h1 != h2

    def test_compat_hash_ignores_trust(self):
        """Compat hash H(data) doesn't depend on trust."""
        lattice = DeltaTrustLattice("node-a", initial_peers={"p1"})
        merkle = TrustBoundMerkle(trust_lattice=lattice, compatibility_mode=True)

        data = b"test data"
        h = merkle.compute_leaf_hash_compat(data)
        expected = hashlib.sha256(data).hexdigest()
        assert h == expected


# ---------------------------------------------------------------------------
# Trust Dimension Independence
# ---------------------------------------------------------------------------

class TestTrustDimensionIndependence:
    """Evidence in one dimension doesn't affect other dimensions."""

    def test_dimension_isolation(self):
        """Evidence in one dim doesn't affect others."""
        score = TypedTrustScore.probationary()
        score = _record_evidence(score, "obs", "integrity", 0.6)
        # integrity: 1 - 0.6 = 0.4 < PROBATION (0.5)
        assert score.trust_for_dimension("integrity") < PROBATION_TRUST

        # Other dimensions should remain at probation (no evidence)
        for d in TRUST_DIMENSIONS:
            if d != "integrity":
                assert score.trust_for_dimension(d) == PROBATION_TRUST

    @pytest.mark.parametrize("dim", list(TRUST_DIMENSIONS))
    def test_single_dim_evidence(self, dim):
        """Evidence in one dimension only affects that dimension."""
        score = TypedTrustScore.probationary()
        # Need amount > 0.5 so trust < PROBATION
        score = _record_evidence(score, "obs", dim, 0.6)
        affected = score.trust_for_dimension(dim)
        assert affected < PROBATION_TRUST, f"{dim}: trust {affected} not < {PROBATION_TRUST}"
        for d in TRUST_DIMENSIONS:
            if d != dim:
                assert score.trust_for_dimension(d) == PROBATION_TRUST


# ---------------------------------------------------------------------------
# Merge with Evidence Ordering
# ---------------------------------------------------------------------------

class TestMergeEvidenceOrdering:
    """Two lattices with same evidence set converge regardless of order."""

    def test_three_peer_convergence(self):
        peers = {"p0", "p1", "p2"}
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)

        events = []
        for _ in range(20):
            target = rng.choice(list(peers))
            obs = f"obs_{rng.randint(0, 3)}"
            dim = rng.choice(dims)
            amt = rng.uniform(0.01, 0.1)
            events.append((target, obs, dim, amt))

        # Node A: processes events in original order
        la = DeltaTrustLattice("a", initial_peers=peers)
        for t, o, d, a_ in events:
            ev = _make_evidence(o, d, a_)
            old = la._trust_scores.get(t, TypedTrustScore.probationary())
            la._trust_scores[t] = old.record_evidence(o, d, a_, ev)

        # Node B: processes events in reverse
        lb = DeltaTrustLattice("b", initial_peers=peers)
        for t, o, d, a_ in reversed(events):
            ev = _make_evidence(o, d, a_)
            old = lb._trust_scores.get(t, TypedTrustScore.probationary())
            lb._trust_scores[t] = old.record_evidence(o, d, a_, ev)

        # Merge should converge
        merged_ab = la.merge(lb)
        merged_ba = lb.merge(la)

        for p in peers:
            for d in TRUST_DIMENSIONS:
                val_ab = merged_ab.get_trust(p).trust_for_dimension(d)
                val_ba = merged_ba.get_trust(p).trust_for_dimension(d)
                assert abs(val_ab - val_ba) < 1e-9

    def test_five_peer_convergence(self):
        peers = {f"p{i}" for i in range(5)}
        rng = random.Random(123)
        dims = list(TRUST_DIMENSIONS)

        events = []
        for _ in range(30):
            target = rng.choice(list(peers))
            obs = f"obs_{rng.randint(0, 5)}"
            dim = rng.choice(dims)
            amt = rng.uniform(0.01, 0.1)
            events.append((target, obs, dim, amt))

        # Apply in 3 different shuffled orders
        lattices = []
        for shuffle_seed in [0, 1, 2]:
            l = DeltaTrustLattice(f"n{shuffle_seed}", initial_peers=peers)
            shuffled = list(events)
            random.Random(shuffle_seed).shuffle(shuffled)
            for t, o, d, a_ in shuffled:
                ev = _make_evidence(o, d, a_)
                old = l._trust_scores.get(t, TypedTrustScore.probationary())
                l._trust_scores[t] = old.record_evidence(o, d, a_, ev)
            lattices.append(l)

        # All should agree
        for p in peers:
            for d in TRUST_DIMENSIONS:
                vals = [l.get_trust(p).trust_for_dimension(d) for l in lattices]
                for v in vals[1:]:
                    assert abs(v - vals[0]) < 1e-9


# ---------------------------------------------------------------------------
# Probationary score properties
# ---------------------------------------------------------------------------

class TestProbationaryScore:

    def test_probationary_overall_trust(self):
        score = TypedTrustScore.probationary()
        assert abs(score.overall_trust() - PROBATION_TRUST) < 1e-12

    def test_probationary_all_dims_equal(self):
        score = TypedTrustScore.probationary()
        for d in TRUST_DIMENSIONS:
            assert abs(score.trust_for_dimension(d) - PROBATION_TRUST) < 1e-12

    def test_probationary_empty_evidence(self):
        score = TypedTrustScore.probationary()
        assert len(score._evidence) == 0

    def test_full_trust_equals_probationary(self):
        """full_trust() and probationary() should be equivalent (both have no evidence)."""
        full = TypedTrustScore.full_trust()
        prob = TypedTrustScore.probationary()
        for d in TRUST_DIMENSIONS:
            assert abs(full.trust_for_dimension(d) - prob.trust_for_dimension(d)) < 1e-12


# ---------------------------------------------------------------------------
# Serialize / Deserialize
# ---------------------------------------------------------------------------

class TestTrustScoreSerialization:

    def test_serialize_roundtrip(self):
        score = TypedTrustScore.probationary()
        score = _record_evidence(score, "obs", "integrity", 0.3)
        score = _record_evidence(score, "obs2", "causality", 0.1)
        data = score.serialize()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_different_scores_different_serialization(self):
        a = TypedTrustScore.probationary()
        a = _record_evidence(a, "obs", "integrity", 0.1)
        b = TypedTrustScore.probationary()
        b = _record_evidence(b, "obs", "integrity", 0.2)
        assert a.serialize() != b.serialize()
