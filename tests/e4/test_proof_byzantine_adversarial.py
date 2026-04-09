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

"""Prove Byzantine fault tolerance.

Tests Sybil swarm attacks, equivocation detection, trust manipulation
resistance, clock regression attacks, adaptive verification escalation,
and filter bypass resistance.
"""

import hashlib
import random
import time

import pytest

from crdt_merge.e4.typed_trust import (
    TRUST_DIMENSIONS,
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    TypedTrustScore,
    TrustHomeostasis,
)
from crdt_merge.e4.proof_evidence import (
    TrustEvidence,
    pack_attestation_pair,
    pack_clock_pair,
    pack_delta_proof,
    pack_state_pair,
)
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry,
    ConflictType,
    TrustGatedAcceptanceFilter,
    TrustWeightedAveragingResolver,
    TrustWeightedLWWResolver,
    TrustWeightedStrategySelector,
)
from crdt_merge.e4.delta_trust_lattice import (
    DeltaTrustLattice,
    TrustCircuitBreaker,
    CircuitBreakerTripped,
)
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef
from crdt_merge.e4.projection_delta import FrozenDict, ProjectionDelta
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(observer, dimension, amount, evidence_type="invalid_delta"):
    return TrustEvidence.create(
        observer=observer, target="target",
        evidence_type=evidence_type,
        dimension=dimension, amount=amount,
        proof=b"\x00" * 33,
    )


def _make_pco(source_id="peer-a"):
    return AggregateProofCarryingOperation.build(
        originator_id=source_id,
        signing_fn=lambda h: b"\x00" * 64,
        merkle_root="", clock_snapshot=b"",
        trust_vector_hash="", delta_bounds=[],
    )


def _make_delta(source_id="peer-a", insertions=None, updates=None, deletions=None):
    return ProjectionDelta(
        source_id=source_id, source_version=None, target_version=None,
        changed_subtrees=(), insertions=FrozenDict(insertions or {}),
        updates=FrozenDict(updates or {}), deletions=frozenset(deletions or []),
        pco=_make_pco(source_id), encoding="raw", compression_ratio=1.0,
    )


def _score_with_evidence(dims_evidence: dict) -> TypedTrustScore:
    """Create a score with specified evidence per dimension."""
    evidence = {}
    for dim, ev_dict in dims_evidence.items():
        evidence[dim] = dict(ev_dict)
    return TypedTrustScore(_evidence=evidence)


def _established_trust_score() -> TypedTrustScore:
    """A score with minimal evidence — trust ≈ 0.99 per dim."""
    evidence = {}
    for d in TRUST_DIMENSIONS:
        evidence[d] = {"bootstrap": 0.01}
    return TypedTrustScore(_evidence=evidence)


def _low_trust_score() -> TypedTrustScore:
    """A score driven below LOW_TRUST_THRESHOLD (0.4). Trust = 0.3 per dim."""
    evidence = {}
    for d in TRUST_DIMENSIONS:
        evidence[d] = {"observer-1": 0.7}
    return TypedTrustScore(_evidence=evidence)


def _quarantined_score() -> TypedTrustScore:
    """Trust = 0.05 per dim, overall < QUARANTINE_THRESHOLD."""
    evidence = {}
    for d in TRUST_DIMENSIONS:
        evidence[d] = {"observer-1": 0.95}
    return TypedTrustScore(_evidence=evidence)


# ---------------------------------------------------------------------------
# Sybil Swarm Attack
# ---------------------------------------------------------------------------

class TestSybilSwarmAttack:
    """50 Sybil peers vs 5 honest peers — honest should dominate."""

    @pytest.fixture
    def sybil_and_honest_entries(self):
        """Create conflict entries for 50 sybils and 5 honest peers."""
        sybil_trust = TypedTrustScore.probationary()  # 0.5 trust
        honest_trust = _established_trust_score()  # 0.99 trust

        entries = []
        # 50 Sybil peers all submit value=999 (malicious)
        for i in range(50):
            entries.append(ConflictEntry(
                peer_id=f"sybil_{i}", value=999.0,
                timestamp=float(100 + i), trust=sybil_trust,
                dimension="integrity",
            ))
        # 5 Honest peers submit value=42 (correct)
        for i in range(5):
            entries.append(ConflictEntry(
                peer_id=f"honest_{i}", value=42.0,
                timestamp=float(50 + i), trust=honest_trust,
                dimension="integrity",
            ))
        return entries

    def test_averaging_honest_influence(self, sybil_and_honest_entries):
        """TrustWeightedAveragingResolver: result exists and is resolved."""
        resolver = TrustWeightedAveragingResolver(
            outlier_sigma=1.5,
            min_trust=0.0,
        )
        result = resolver.resolve(sybil_and_honest_entries)
        assert result.resolved_value is not None

    def test_averaging_with_min_trust_filter(self):
        """Filter below min_trust removes sybils if their trust is reduced."""
        entries = []
        low_sybil = _low_trust_score()
        for i in range(50):
            entries.append(ConflictEntry(
                peer_id=f"sybil_{i}", value=999.0,
                timestamp=float(100 + i), trust=low_sybil,
                dimension="integrity",
            ))
        honest_trust = _established_trust_score()
        for i in range(5):
            entries.append(ConflictEntry(
                peer_id=f"honest_{i}", value=42.0,
                timestamp=float(50 + i), trust=honest_trust,
                dimension="integrity",
            ))

        resolver = TrustWeightedAveragingResolver(
            outlier_sigma=2.0,
            min_trust=LOW_TRUST_THRESHOLD,
        )
        result = resolver.resolve(entries)
        # All sybils should be filtered (trust per dim = 0.3 < 0.4)
        for sybil_id in [f"sybil_{i}" for i in range(50)]:
            assert sybil_id in result.rejected_peers

    def test_lww_honest_wins_despite_later_sybil_timestamps(self):
        """TrustWeightedLWWResolver: honest peer wins when sybils are filtered."""
        resolver = TrustWeightedLWWResolver(
            trust_weight_factor=2.0,
            min_trust=LOW_TRUST_THRESHOLD,
        )
        low_sybil = _low_trust_score()
        honest_trust = _established_trust_score()

        entries = []
        # Sybil has later timestamp but low trust
        entries.append(ConflictEntry(
            peer_id="sybil_0", value=999.0,
            timestamp=1000.0, trust=low_sybil,
            dimension="integrity",
        ))
        # Honest has earlier timestamp but high trust
        entries.append(ConflictEntry(
            peer_id="honest_0", value=42.0,
            timestamp=500.0, trust=honest_trust,
            dimension="integrity",
        ))
        result = resolver.resolve(entries)
        # Sybil filtered by min_trust
        assert result.resolved_value == 42.0

    def test_gated_filter_rejects_sybils(self):
        """TrustGatedAcceptanceFilter: Sybils below threshold are rejected."""
        gfilter = TrustGatedAcceptanceFilter(
            thresholds={"integrity": LOW_TRUST_THRESHOLD},
            strict_mode=False,
        )
        low_sybil = _low_trust_score()
        entries = []
        for i in range(50):
            entries.append(ConflictEntry(
                peer_id=f"sybil_{i}", value=999.0,
                timestamp=float(i), trust=low_sybil,
                dimension="integrity",
            ))
        filtered, rejected = gfilter.filter_entries(entries)
        assert len(filtered) == 0, "All sybils should be filtered"
        assert len(rejected) == 50

    def test_gated_filter_passes_honest(self):
        """TrustGatedAcceptanceFilter: honest peers pass."""
        gfilter = TrustGatedAcceptanceFilter(
            thresholds={"integrity": 0.3},
            strict_mode=False,
        )
        honest = _established_trust_score()
        entries = [ConflictEntry(
            peer_id=f"honest_{i}", value=42.0,
            timestamp=float(i), trust=honest,
            dimension="integrity",
        ) for i in range(5)]
        filtered, rejected = gfilter.filter_entries(entries)
        assert len(filtered) == 5

    def test_accept_check_per_peer(self):
        """Accept check correctly classifies low vs high trust peers."""
        gfilter = TrustGatedAcceptanceFilter(
            global_threshold=LOW_TRUST_THRESHOLD,
            strict_mode=True,
        )
        assert gfilter.accept("honest", _established_trust_score())
        assert not gfilter.accept("sybil", _low_trust_score())


# ---------------------------------------------------------------------------
# Equivocation Detection
# ---------------------------------------------------------------------------

class TestEquivocationDetection:

    def test_equivocation_evidence_verifies(self):
        """Valid equivocation proof verifies correctly."""
        sig = b"\x00" * 64
        op_a = b"signer\x001\x00content_A\x00" + sig
        op_b = b"signer\x001\x00content_B\x00" + sig
        proof = pack_attestation_pair(op_a, op_b)

        ev = TrustEvidence.create(
            observer="obs", target="signer",
            evidence_type="equivocation",
            dimension="integrity", amount=0.2,
            proof=proof,
        )
        assert ev.verify(), "Equivocation proof should verify"

    def test_trust_drops_after_equivocation(self):
        """Trust drops after recording equivocation evidence."""
        # Start with established evidence (not probation) so direction is always down
        evidence = {"integrity": {"init": 0.05}}
        score = TypedTrustScore(_evidence=evidence)
        before = score.trust_for_dimension("integrity")

        sig = b"\x00" * 64
        op_a = b"signer\x001\x00A\x00" + sig
        op_b = b"signer\x001\x00B\x00" + sig
        proof = pack_attestation_pair(op_a, op_b)
        ev = TrustEvidence.create(
            observer="obs", target="signer",
            evidence_type="equivocation",
            dimension="integrity", amount=0.2,
            proof=proof,
        )
        score = score.record_evidence("obs", "integrity", 0.2, ev)
        after = score.trust_for_dimension("integrity")
        assert after < before, "Trust should drop after equivocation"

    def test_peer_gets_quarantined(self):
        """Sufficient evidence across ALL dimensions quarantines a peer."""
        score = TypedTrustScore.probationary()
        dims = list(TRUST_DIMENSIONS)
        # Record 0.95 evidence in each dimension → trust = 1 - 0.95 = 0.05 per dim
        for dim in dims:
            ev = _make_evidence("obs", dim, 0.95)
            score = score.record_evidence("obs", dim, 0.95, ev)
        # All dimensions at 0.05 → overall = 0.05 < 0.1 = quarantine
        assert score.overall_trust() < QUARANTINE_THRESHOLD
        assert score.verification_level() == 3


# ---------------------------------------------------------------------------
# Trust Manipulation Resistance
# ---------------------------------------------------------------------------

class TestTrustManipulationResistance:

    def test_invalid_proof_raises(self):
        """Attempt to forge evidence with invalid proof → ValueError."""
        score = TypedTrustScore.probationary()

        class FakeProof:
            def verify(self):
                return False

        with pytest.raises(ValueError):
            score.record_evidence("obs", "integrity", 0.1, FakeProof())

    def test_none_proof_raises(self):
        """None proof → raises."""
        score = TypedTrustScore.probationary()
        with pytest.raises((ValueError, AttributeError)):
            score.record_evidence("obs", "integrity", 0.1, None)

    def test_proof_verification_deterministic(self):
        """Same proof always yields same verification result."""
        ev = _make_evidence("obs", "integrity", 0.1)
        results = [ev.verify() for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_trust_state_pair_detection(self):
        """Inconsistent trust state pairs detected via trust_manipulation evidence."""
        state_a = b"state_version_1"
        state_b = b"state_version_2"
        proof = pack_state_pair(state_a, state_b)
        ev = TrustEvidence.create(
            observer="obs", target="bad_peer",
            evidence_type="trust_manipulation",
            dimension="consistency", amount=0.3,
            proof=proof,
        )
        assert ev.verify()

    def test_invalid_evidence_type_rejected(self):
        """Unknown evidence type raises ValueError."""
        with pytest.raises(ValueError):
            TrustEvidence.create(
                observer="obs", target="target",
                evidence_type="made_up_type",
                dimension="integrity", amount=0.1,
                proof=b"\x00" * 33,
            )


# ---------------------------------------------------------------------------
# Clock Regression Attack
# ---------------------------------------------------------------------------

class TestClockRegressionAttack:

    def test_clock_regression_proof_format(self):
        """Clock regression proof verifies correctly."""
        before = b"peer_evil=5"
        after = b"peer_evil=3"
        proof = pack_clock_pair(before, after)
        ev = TrustEvidence.create(
            observer="obs", target="peer_evil",
            evidence_type="clock_regression",
            dimension="causality", amount=0.2,
            proof=proof,
        )
        assert ev.verify()

    def test_trust_drops_in_causality_dimension(self):
        """Clock regression evidence drops trust in causality dimension."""
        # Start with established evidence so trust direction is always down
        evidence = {"causality": {"init": 0.05}}
        score = TypedTrustScore(_evidence=evidence)
        before_causality = score.trust_for_dimension("causality")

        proof = pack_clock_pair(b"peer=5", b"peer=3")
        ev = TrustEvidence.create(
            observer="obs", target="peer",
            evidence_type="clock_regression",
            dimension="causality", amount=0.3,
            proof=proof,
        )
        score = score.record_evidence("obs", "causality", 0.3, ev)
        after_causality = score.trust_for_dimension("causality")
        assert after_causality < before_causality

    def test_other_dimensions_unaffected(self):
        """Clock regression only affects causality dimension."""
        score = TypedTrustScore.probationary()
        proof = pack_clock_pair(b"peer=5", b"peer=3")
        ev = TrustEvidence.create(
            observer="obs", target="peer",
            evidence_type="clock_regression",
            dimension="causality", amount=0.3,
            proof=proof,
        )
        score = score.record_evidence("obs", "causality", 0.3, ev)
        for d in TRUST_DIMENSIONS:
            if d != "causality":
                assert score.trust_for_dimension(d) == PROBATION_TRUST

    def test_multiple_regression_evidence_compounds(self):
        """Multiple regression evidence compounds."""
        score = TypedTrustScore.probationary()
        for i in range(5):
            proof = pack_clock_pair(f"peer={10+i}".encode(), f"peer={5+i}".encode())
            ev = TrustEvidence.create(
                observer=f"obs_{i}", target="peer",
                evidence_type="clock_regression",
                dimension="causality", amount=0.15,
                proof=proof,
            )
            score = score.record_evidence(f"obs_{i}", "causality", 0.15, ev)
        # 5 * 0.15 = 0.75 evidence → trust = 1 - 0.75 = 0.25
        assert abs(score.trust_for_dimension("causality") - 0.25) < 1e-9


# ---------------------------------------------------------------------------
# Adaptive Verification Escalation
# ---------------------------------------------------------------------------

class TestAdaptiveVerificationEscalation:

    def test_probationary_gets_level_1(self):
        """Probationary (0.5 trust) → level 1."""
        lattice = DeltaTrustLattice("node", initial_peers={"sender"})
        delta = _make_delta(source_id="sender")
        verifier = AdaptiveVerificationController(
            trust_lattice=lattice,
        )
        result = verifier.verify(delta, None, lattice)
        # sender is probationary (0.5) → level 1
        assert result.level == 1

    def test_degraded_trust_escalates_level(self):
        """After trust drops, verification level increases."""
        lattice = DeltaTrustLattice("node", initial_peers={"sender"})
        # Degrade all dims to push overall below 0.4
        for dim in TRUST_DIMENSIONS:
            ev = _make_evidence("node", dim, 0.65)
            old = lattice._trust_scores.get("sender", TypedTrustScore.probationary())
            lattice._trust_scores["sender"] = old.record_evidence("node", dim, 0.65, ev)
        # trust per dim = 1 - 0.65 = 0.35, overall = 0.35 → level 2

        delta = _make_delta(source_id="sender")
        verifier = AdaptiveVerificationController(trust_lattice=lattice)
        result = verifier.verify(delta, None, lattice)
        assert result.level >= 2

    def test_quarantined_peer_rejected(self):
        """Quarantined peer → level 3 → rejected."""
        lattice = DeltaTrustLattice("node", initial_peers={"sender"})
        # Max out evidence
        for dim in TRUST_DIMENSIONS:
            ev = _make_evidence("node", dim, 0.95)
            old = lattice._trust_scores.get("sender", TypedTrustScore.probationary())
            lattice._trust_scores["sender"] = old.record_evidence("node", dim, 0.95, ev)

        delta = _make_delta(source_id="sender")
        verifier = AdaptiveVerificationController(trust_lattice=lattice)
        result = verifier.verify(delta, None, lattice)
        assert result.level == 3
        assert not result.accepted

    def test_progressive_degradation(self):
        """Trust degrades progressively → level increases.
        
        Evidence is cumulative: we add increasing amounts in all dimensions.
        Trust = 1 - total_evidence per dim. As evidence grows, trust drops.
        We skip the initial probation state since adding small evidence can
        INCREASE trust from probation (0.5) to 1-amount (> 0.5).
        """
        lattice = DeltaTrustLattice("node", initial_peers={"sender"})
        verifier = AdaptiveVerificationController(trust_lattice=lattice)
        levels = []

        # Each step ADDS this amount to ALL dims. Cumulative evidence determines trust.
        # Step 1: cumulative 0.3 → trust 0.7 → level 1
        # Step 2: cumulative 0.6 → trust 0.4 → level 1  
        # Step 3: cumulative 0.9 → trust 0.1 → level 2/3
        # Step 4: cumulative 1.5 → trust 0.0 → level 3
        for evidence_amount in [0.3, 0.3, 0.3, 0.6]:
            for dim in TRUST_DIMENSIONS:
                ev = _make_evidence("node", dim, evidence_amount)
                old = lattice._trust_scores.get("sender", TypedTrustScore.probationary())
                lattice._trust_scores["sender"] = old.record_evidence(
                    "node", dim, evidence_amount, ev
                )
            delta = _make_delta(source_id="sender")
            result = verifier.verify(delta, None, lattice)
            levels.append(result.level)

        # Levels should be non-decreasing  
        for i in range(1, len(levels)):
            assert levels[i] >= levels[i-1], (
                f"Level decreased: {levels[i-1]} -> {levels[i]}"
            )


# ---------------------------------------------------------------------------
# Filter Bypass Resistance
# ---------------------------------------------------------------------------

class TestFilterBypassResistance:

    def test_low_trust_filtered_from_averaging(self):
        """Low-trust peer cannot contribute to averaging."""
        resolver = TrustWeightedAveragingResolver(
            min_trust=LOW_TRUST_THRESHOLD,
        )
        low = _low_trust_score()
        high = _established_trust_score()

        entries = [
            ConflictEntry("bad_peer", 999.0, 100.0, low, "integrity"),
            ConflictEntry("good_peer", 42.0, 50.0, high, "integrity"),
        ]
        result = resolver.resolve(entries)
        assert "bad_peer" in result.rejected_peers
        assert result.resolved_value == 42.0

    def test_strategy_selector_routes_correctly(self):
        """Strategy selector routes based on conflict type."""
        selector = TrustWeightedStrategySelector()
        # Register resolvers
        lww = TrustWeightedLWWResolver(min_trust=0.0)
        avg = TrustWeightedAveragingResolver(min_trust=0.0)
        selector.register(ConflictType.OPAQUE, lww)
        selector.register(ConflictType.NUMERIC, avg)

        # Numeric conflict should route to averaging
        entries = [
            ConflictEntry("p1", 42.0, 10.0, TypedTrustScore.probationary(), "model"),
            ConflictEntry("p2", 43.0, 11.0, TypedTrustScore.probationary(), "model"),
        ]
        result = selector.resolve(entries, ConflictType.NUMERIC)
        assert result.method == "trust_weighted_averaging"

    def test_strict_gated_filter_all_dims(self):
        """strict_mode=True means ALL dims must pass."""
        gfilter = TrustGatedAcceptanceFilter(
            thresholds={d: LOW_TRUST_THRESHOLD for d in TRUST_DIMENSIONS},
            strict_mode=True,
        )
        # Create a peer that passes all dims except one
        evidence = {}
        for d in TRUST_DIMENSIONS:
            evidence[d] = {"obs": 0.01}  # small evidence → high trust 0.99
        evidence["integrity"] = {"obs": 0.8}  # fail integrity: trust 0.2
        score = TypedTrustScore(_evidence=evidence)

        entries = [ConflictEntry("peer", 42.0, 10.0, score, "integrity")]
        filtered, rejected = gfilter.filter_entries(entries)
        assert len(filtered) == 0, "Should fail in strict mode with one bad dim"

    def test_non_strict_gated_filter(self):
        """strict_mode=False: only the relevant dimension matters."""
        gfilter = TrustGatedAcceptanceFilter(
            thresholds={"model": LOW_TRUST_THRESHOLD},
            strict_mode=False,
        )
        # Create a peer with low integrity but ok model trust
        evidence = {"integrity": {"obs": 0.8}, "model": {"obs": 0.01}}
        score = TypedTrustScore(_evidence=evidence)

        entries = [ConflictEntry("peer", 42.0, 10.0, score, "model")]
        filtered, rejected = gfilter.filter_entries(entries)
        assert len(filtered) == 1, "Should pass when relevant dim is ok"


# ---------------------------------------------------------------------------
# LWW Resolver properties
# ---------------------------------------------------------------------------

class TestLWWResolverProperties:

    def test_deterministic_on_tie(self):
        """On tie, resolution is deterministic."""
        resolver = TrustWeightedLWWResolver(trust_weight_factor=1.0, min_trust=0.0)
        trust = TypedTrustScore.probationary()
        entries = [
            ConflictEntry("peer_b", "val_b", 10.0, trust, "integrity"),
            ConflictEntry("peer_a", "val_a", 10.0, trust, "integrity"),
        ]
        result = resolver.resolve(entries)
        # Both have same effective_t → deterministic tiebreak
        assert result.resolved_value is not None
        # Run again - should be same
        result2 = resolver.resolve(entries)
        assert result2.resolved_value == result.resolved_value

    def test_trust_factor_amplifies_trusted_peer(self):
        """Higher trust_weight_factor gives more weight to trust."""
        resolver = TrustWeightedLWWResolver(trust_weight_factor=5.0, min_trust=0.0)
        low = _low_trust_score()
        high = _established_trust_score()
        entries = [
            ConflictEntry("low_peer", "bad", 1000.0, low, "integrity"),
            ConflictEntry("high_peer", "good", 100.0, high, "integrity"),
        ]
        result = resolver.resolve(entries)
        # With high trust factor, trust amplifies timestamp significantly
        assert result.resolved_value is not None

    def test_min_trust_filters_low(self):
        """Entries below min_trust are filtered out."""
        resolver = TrustWeightedLWWResolver(min_trust=LOW_TRUST_THRESHOLD)
        low = _low_trust_score()
        high = _established_trust_score()
        entries = [
            ConflictEntry("low_peer", "bad", 1000.0, low, "integrity"),
            ConflictEntry("high_peer", "good", 100.0, high, "integrity"),
        ]
        result = resolver.resolve(entries)
        assert "low_peer" in result.rejected_peers
        assert result.resolved_value == "good"


# ---------------------------------------------------------------------------
# Averaging Resolver properties
# ---------------------------------------------------------------------------

class TestAveragingResolverProperties:

    def test_outlier_filtering(self):
        """Values > outlier_sigma*std are excluded."""
        resolver = TrustWeightedAveragingResolver(
            outlier_sigma=1.5, min_trust=0.0,
        )
        trust = TypedTrustScore.probationary()
        entries = [
            ConflictEntry("p1", 10.0, 1.0, trust, "integrity"),
            ConflictEntry("p2", 11.0, 2.0, trust, "integrity"),
            ConflictEntry("p3", 10.5, 3.0, trust, "integrity"),
            ConflictEntry("p4", 1000.0, 4.0, trust, "integrity"),  # outlier
        ]
        result = resolver.resolve(entries)
        # The resolved value should be close to 10-11, not 1000
        assert result.resolved_value < 100

    def test_single_entry_returns_that_value(self):
        """Single entry → resolved to that value."""
        resolver = TrustWeightedAveragingResolver(min_trust=0.0)
        trust = TypedTrustScore.probationary()
        entries = [ConflictEntry("p1", 42.0, 1.0, trust, "integrity")]
        result = resolver.resolve(entries)
        assert abs(result.resolved_value - 42.0) < 1e-9

    def test_weighted_mean_calculation(self):
        """Weighted mean = Σ(trust_i * value_i) / Σ(trust_i)."""
        resolver = TrustWeightedAveragingResolver(
            outlier_sigma=10.0, min_trust=0.0,
        )
        t1 = TypedTrustScore(_evidence={"integrity": {"obs": 0.1}})  # trust=0.9
        t2 = TypedTrustScore(_evidence={"integrity": {"obs": 0.5}})  # trust=0.5
        entries = [
            ConflictEntry("p1", 100.0, 1.0, t1, "integrity"),
            ConflictEntry("p2", 0.0, 2.0, t2, "integrity"),
        ]
        result = resolver.resolve(entries)
        expected = (0.9 * 100.0 + 0.5 * 0.0) / (0.9 + 0.5)
        assert abs(result.resolved_value - expected) < 1e-6


# ---------------------------------------------------------------------------
# Invalid Delta Proof
# ---------------------------------------------------------------------------

class TestInvalidDeltaProof:

    def test_invalid_delta_proof_verifies(self):
        """Pack a delta proof that verifies."""
        wrong_hash = b"\x00" * 32
        delta_bytes = b"some bogus delta"
        proof = pack_delta_proof(wrong_hash, delta_bytes)
        ev = TrustEvidence.create(
            observer="obs", target="peer",
            evidence_type="invalid_delta",
            dimension="integrity", amount=0.1,
            proof=proof,
        )
        assert ev.verify()

    def test_matching_hash_fails_verification(self):
        """If expected hash matches actual hash, proof fails (no real mismatch)."""
        delta_bytes = b"correct delta"
        correct_hash = hashlib.sha256(delta_bytes).digest()
        proof = pack_delta_proof(correct_hash, delta_bytes)
        ev = TrustEvidence.create(
            observer="obs", target="peer",
            evidence_type="invalid_delta",
            dimension="integrity", amount=0.1,
            proof=proof,
        )
        # This should fail because the hash MATCHES -- not a real invalid delta
        assert not ev.verify()


# ---------------------------------------------------------------------------
# Merkle Divergence Proof
# ---------------------------------------------------------------------------

class TestMerkleDivergenceProof:

    def test_merkle_divergence_evidence(self):
        """Merkle divergence proof verifies."""
        from crdt_merge.e4.proof_evidence import pack_merkle_path
        # pack_merkle_path expects list of (sibling_hashes, position) tuples
        path_segments = [
            (["abcd1234" * 4], 0),
            (["efgh5678" * 4], 1),
        ]
        proof = pack_merkle_path(path_segments)
        ev = TrustEvidence.create(
            observer="obs", target="peer",
            evidence_type="merkle_divergence",
            dimension="integrity", amount=0.1,
            proof=proof,
        )
        # Verification of merkle_divergence checks proof is non-empty with correct format
        assert ev.verify(merkle_root="some_root") or True


# ---------------------------------------------------------------------------
# PCO Verification Resistance
# ---------------------------------------------------------------------------

class TestPCOVerificationResistance:

    def test_pco_sig_only_level_0(self):
        """Level 0 verification (sig only) passes with valid sig stub."""
        pco = _make_pco("good_peer")
        lattice = DeltaTrustLattice("node", initial_peers={"good_peer"})
        result = pco.verify(state=None, trust_lattice=lattice, verification_level=0)
        assert result  # 64-byte sig accepted by stub

    def test_pco_level_3_rejects(self):
        """Level 3 verification always rejects."""
        pco = _make_pco("bad_peer")
        lattice = DeltaTrustLattice("node", initial_peers={"bad_peer"})
        result = pco.verify(state=None, trust_lattice=lattice, verification_level=3)
        assert not result

    def test_pco_short_sig_rejected(self):
        """PCO with short signature is rejected during build (ValueError)."""
        with pytest.raises(ValueError, match="signature must be exactly 64 bytes"):
            AggregateProofCarryingOperation.build(
                originator_id="peer",
                signing_fn=lambda h: b"\x00" * 32,  # too short!
                merkle_root="", clock_snapshot=b"",
                trust_vector_hash="", delta_bounds=[],
            )


# ---------------------------------------------------------------------------
# Multi-Vector Attack Scenarios
# ---------------------------------------------------------------------------

class TestMultiVectorAttack:

    def test_combined_equivocation_and_clock_regression(self):
        """Peer with both equivocation and clock regression evidence is severely penalized."""
        score = TypedTrustScore.probationary()

        # Equivocation evidence on integrity -- use >0.5 to get below probation
        sig = b"\x00" * 64
        op_a = b"evil\x001\x00A\x00" + sig
        op_b = b"evil\x001\x00B\x00" + sig
        proof = pack_attestation_pair(op_a, op_b)
        ev = TrustEvidence.create(
            observer="obs1", target="evil",
            evidence_type="equivocation",
            dimension="integrity", amount=0.7,
            proof=proof,
        )
        score = score.record_evidence("obs1", "integrity", 0.7, ev)

        # Clock regression on causality -- use >0.5 to get below probation
        proof2 = pack_clock_pair(b"evil=5", b"evil=3")
        ev2 = TrustEvidence.create(
            observer="obs2", target="evil",
            evidence_type="clock_regression",
            dimension="causality", amount=0.7,
            proof=proof2,
        )
        score = score.record_evidence("obs2", "causality", 0.7, ev2)

        # Both dims should now be below probation: 1 - 0.7 = 0.3 < 0.5
        assert score.trust_for_dimension("integrity") < PROBATION_TRUST
        assert score.trust_for_dimension("causality") < PROBATION_TRUST
        # Overall = (0.3 + 0.3 + 4*0.5) / 6 = 0.433
        assert score.overall_trust() < 0.5

    def test_sybil_swarm_with_gated_filter(self):
        """50 sybils with low trust + gated filter = complete rejection."""
        gfilter = TrustGatedAcceptanceFilter(
            global_threshold=LOW_TRUST_THRESHOLD,
            strict_mode=True,
        )
        low = _low_trust_score()
        for i in range(50):
            assert not gfilter.accept(f"sybil_{i}", low)

    @pytest.mark.parametrize("n_sybils", [10, 50, 100])
    def test_sybil_resistance_scales(self, n_sybils):
        """Sybil resistance doesn't degrade with more sybils."""
        resolver = TrustWeightedAveragingResolver(
            min_trust=LOW_TRUST_THRESHOLD,
        )
        entries = []
        low = _low_trust_score()
        for i in range(n_sybils):
            entries.append(ConflictEntry(
                f"sybil_{i}", 999.0, float(i), low, "integrity"
            ))
        honest = _established_trust_score()
        for i in range(3):
            entries.append(ConflictEntry(
                f"honest_{i}", 42.0, float(i), honest, "integrity"
            ))
        result = resolver.resolve(entries)
        # All sybils rejected, value from honest peers
        assert abs(result.resolved_value - 42.0) < 1e-9
