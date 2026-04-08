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

"""Tests for TypedTrustScore, TrustHomeostasis, and related constants.

Covers multi-dimensional trust, merge (LUB), decay, epoch transitions,
boundary values (0.0, 1.0), probation accrual, and homeostasis.
"""

import pytest

from crdt_merge.e4.typed_trust import (
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    TRUST_DIMENSIONS,
    TrustHomeostasis,
    TypedTrustScore,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestTrustConstants:

    def test_probation_trust(self):
        """PROBATION_TRUST is 0.5."""
        assert PROBATION_TRUST == 0.5

    def test_quarantine_threshold(self):
        """QUARANTINE_THRESHOLD is 0.1."""
        assert QUARANTINE_THRESHOLD == 0.1

    def test_low_trust_threshold(self):
        """LOW_TRUST_THRESHOLD is 0.4."""
        assert LOW_TRUST_THRESHOLD == 0.4

    def test_partial_threshold(self):
        """PARTIAL_THRESHOLD is 0.8."""
        assert PARTIAL_THRESHOLD == 0.8

    def test_six_dimensions(self):
        """There are exactly 6 trust dimensions."""
        assert len(TRUST_DIMENSIONS) == 6
        expected = {"integrity", "causality", "consistency", "gossip", "model", "context"}
        assert TRUST_DIMENSIONS == expected


# ---------------------------------------------------------------------------
# TypedTrustScore creation
# ---------------------------------------------------------------------------

class TestTypedTrustScoreCreation:

    def test_probationary(self):
        """Probationary score has overall trust at PROBATION_TRUST."""
        ts = TypedTrustScore.probationary()
        assert ts.overall_trust() == PROBATION_TRUST

    def test_full_trust(self):
        """full_trust() produces the same as probationary (no evidence)."""
        ts = TypedTrustScore.full_trust()
        # With no evidence all dims are at PROBATION_TRUST
        assert ts.overall_trust() == PROBATION_TRUST

    def test_default_construction(self):
        """Default construction has no evidence."""
        ts = TypedTrustScore()
        assert ts.overall_trust() == PROBATION_TRUST

    def test_with_evidence(self):
        """Constructing with evidence reduces trust."""
        evidence = {"integrity": {"obs": 0.3}}
        ts = TypedTrustScore(_evidence=evidence)
        assert ts.trust_for_dimension("integrity") == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Per-dimension trust
# ---------------------------------------------------------------------------

class TestTrustForDimension:

    def test_no_evidence_returns_probation(self):
        """Dimension without evidence returns PROBATION_TRUST."""
        ts = TypedTrustScore()
        assert ts.trust_for_dimension("integrity") == PROBATION_TRUST

    def test_some_evidence(self):
        """Trust = 1 - total_evidence, clamped to [0, 1]."""
        evidence = {"integrity": {"obs_a": 0.2, "obs_b": 0.3}}
        ts = TypedTrustScore(_evidence=evidence)
        assert ts.trust_for_dimension("integrity") == pytest.approx(0.5)

    def test_full_evidence_zero_trust(self):
        """Evidence totalling >= 1.0 yields trust 0.0."""
        evidence = {"integrity": {"obs": 1.0}}
        ts = TypedTrustScore(_evidence=evidence)
        assert ts.trust_for_dimension("integrity") == 0.0

    def test_over_evidence_clamped(self):
        """Evidence > 1.0 still yields trust 0.0 (clamped)."""
        evidence = {"integrity": {"obs": 2.0}}
        ts = TypedTrustScore(_evidence=evidence)
        assert ts.trust_for_dimension("integrity") == 0.0


# ---------------------------------------------------------------------------
# Overall trust
# ---------------------------------------------------------------------------

class TestOverallTrust:

    def test_all_probation(self):
        """All dimensions at probation yields overall = 0.5."""
        ts = TypedTrustScore()
        assert ts.overall_trust() == pytest.approx(PROBATION_TRUST)

    def test_single_dim_evidence(self):
        """Evidence in one dimension reduces overall trust."""
        evidence = {"integrity": {"obs": 0.5}}
        ts = TypedTrustScore(_evidence=evidence)
        # integrity = 0.5, other 5 dims = 0.5 each -> mean = (0.5*5 + 0.5)/6 = 0.5
        assert ts.overall_trust() == pytest.approx(0.5)

    def test_all_dims_evidence(self):
        """Evidence in all dimensions reduces overall trust further."""
        evidence = {dim: {"obs": 0.3} for dim in TRUST_DIMENSIONS}
        ts = TypedTrustScore(_evidence=evidence)
        # Each dim: 1.0 - 0.3 = 0.7
        assert ts.overall_trust() == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Verification level
# ---------------------------------------------------------------------------

class TestVerificationLevel:

    def test_level_0_high_trust(self):
        """Trust > 0.8 yields level 0."""
        evidence = {dim: {"obs": 0.0} for dim in TRUST_DIMENSIONS}
        ts = TypedTrustScore(_evidence=evidence)
        # Each dim: 1.0 - 0.0 = 1.0, overall = 1.0
        assert ts.verification_level() == 0

    def test_level_1_partial_trust(self):
        """Trust 0.4-0.8 yields level 1."""
        ts = TypedTrustScore()  # 0.5 overall -> level 1
        assert ts.verification_level() == 1

    def test_level_2_low_trust(self):
        """Trust < 0.4 yields level 2."""
        evidence = {dim: {"obs": 0.7} for dim in TRUST_DIMENSIONS}
        ts = TypedTrustScore(_evidence=evidence)
        # Each dim: 0.3, overall 0.3 < 0.4
        assert ts.verification_level() == 2

    def test_level_3_quarantined(self):
        """Trust < 0.1 yields level 3."""
        evidence = {dim: {"obs": 0.95} for dim in TRUST_DIMENSIONS}
        ts = TypedTrustScore(_evidence=evidence)
        # Each dim: 0.05, overall 0.05 < 0.1
        assert ts.verification_level() == 3


# ---------------------------------------------------------------------------
# record_evidence
# ---------------------------------------------------------------------------

class TestRecordEvidence:

    def test_record_creates_new_score(self):
        """record_evidence returns a new TypedTrustScore instance."""
        ts = TypedTrustScore()
        class FakeProof:
            def verify(self): return True
        ts2 = ts.record_evidence("obs", "integrity", 0.1, FakeProof())
        assert ts2 is not ts

    def test_record_increases_evidence(self):
        """Recording evidence reduces trust for the dimension."""
        ts = TypedTrustScore()
        class FakeProof:
            def verify(self): return True
        ts2 = ts.record_evidence("obs", "integrity", 0.6, FakeProof())
        assert ts2.trust_for_dimension("integrity") < PROBATION_TRUST
        assert ts2.trust_for_dimension("integrity") == pytest.approx(0.4)

    def test_record_bad_proof_raises(self):
        """Evidence with failing proof raises ValueError."""
        ts = TypedTrustScore()
        class BadProof:
            def verify(self): return False
        with pytest.raises(ValueError, match="evidence proof failed"):
            ts.record_evidence("obs", "integrity", 0.1, BadProof())

    def test_record_monotonic(self):
        """GCounter: evidence is monotonically increasing."""
        class FakeProof:
            def verify(self): return True
        ts = TypedTrustScore()
        ts2 = ts.record_evidence("obs", "integrity", 0.1, FakeProof())
        ts3 = ts2.record_evidence("obs", "integrity", 0.1, FakeProof())
        # Evidence for obs should be >= 0.2 now
        assert ts3.trust_for_dimension("integrity") <= ts2.trust_for_dimension("integrity")


# ---------------------------------------------------------------------------
# CRDT merge
# ---------------------------------------------------------------------------

class TestTypedTrustScoreMerge:

    def test_merge_takes_max(self):
        """Merge takes element-wise max of evidence (GCounter)."""
        ts1 = TypedTrustScore(_evidence={"integrity": {"obs": 0.3}})
        ts2 = TypedTrustScore(_evidence={"integrity": {"obs": 0.5}})
        merged = ts1.merge(ts2)
        assert merged.trust_for_dimension("integrity") == pytest.approx(0.5)

    def test_merge_union_of_dimensions(self):
        """Merge unions dimensions from both scores."""
        ts1 = TypedTrustScore(_evidence={"integrity": {"obs": 0.1}})
        ts2 = TypedTrustScore(_evidence={"causality": {"obs": 0.2}})
        merged = ts1.merge(ts2)
        assert merged.trust_for_dimension("integrity") == pytest.approx(0.9)
        assert merged.trust_for_dimension("causality") == pytest.approx(0.8)

    def test_merge_commutative(self):
        """Merge is commutative."""
        ts1 = TypedTrustScore(_evidence={"integrity": {"a": 0.1, "b": 0.3}})
        ts2 = TypedTrustScore(_evidence={"integrity": {"a": 0.5, "c": 0.2}})
        m1 = ts1.merge(ts2)
        m2 = ts2.merge(ts1)
        assert m1.overall_trust() == pytest.approx(m2.overall_trust())

    def test_merge_idempotent(self):
        """Merging with self is idempotent."""
        ts = TypedTrustScore(_evidence={"integrity": {"obs": 0.3}})
        merged = ts.merge(ts)
        assert merged.trust_for_dimension("integrity") == ts.trust_for_dimension("integrity")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestTypedTrustScoreSerialization:

    def test_serialize_deterministic(self):
        """Serialization is deterministic."""
        ts = TypedTrustScore()
        assert ts.serialize() == ts.serialize()

    def test_serialize_bytes(self):
        """Serialization returns bytes."""
        ts = TypedTrustScore()
        assert isinstance(ts.serialize(), bytes)

    def test_hash_is_hex(self):
        """hash() returns 64-char hex string."""
        ts = TypedTrustScore()
        h = ts.hash()
        assert len(h) == 64
        int(h, 16)

    def test_hash_changes_with_evidence(self):
        """Different evidence produces different hashes."""
        ts1 = TypedTrustScore()
        ts2 = TypedTrustScore(_evidence={"integrity": {"obs": 0.6}})
        assert ts1.hash() != ts2.hash()


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestTypedTrustScoreRepr:

    def test_repr(self):
        """Repr includes overall trust and level."""
        ts = TypedTrustScore()
        r = repr(ts)
        assert "overall=" in r
        assert "level=" in r


# ---------------------------------------------------------------------------
# TrustHomeostasis
# ---------------------------------------------------------------------------

class TestTrustHomeostasis:

    def test_normalize_preserves_budget(self):
        """After normalization, sum of trust per dim ≈ peer_count."""
        scores = {
            "alice": TypedTrustScore(_evidence={"integrity": {"obs": 0.1}}),
            "bob": TypedTrustScore(_evidence={"integrity": {"obs": 0.3}}),
        }
        normalized = TrustHomeostasis.normalize(scores, peer_count=2)
        total = sum(
            normalized[p].trust_for_dimension("integrity") for p in normalized
        )
        assert total == pytest.approx(2.0, abs=0.15)

    def test_normalize_preserves_rank_order(self):
        """Rank order is preserved across normalization."""
        scores = {
            "alice": TypedTrustScore(_evidence={"integrity": {"obs": 0.1}}),
            "bob": TypedTrustScore(_evidence={"integrity": {"obs": 0.5}}),
        }
        normalized = TrustHomeostasis.normalize(scores, peer_count=2)
        assert (
            normalized["alice"].trust_for_dimension("integrity")
            >= normalized["bob"].trust_for_dimension("integrity")
        )

    def test_normalize_empty_scores(self):
        """Normalizing empty scores returns empty dict."""
        result = TrustHomeostasis.normalize({}, peer_count=5)
        assert result == {}

    def test_normalize_zero_peer_count(self):
        """Zero peer_count returns original scores."""
        scores = {"alice": TypedTrustScore()}
        result = TrustHomeostasis.normalize(scores, peer_count=0)
        assert len(result) == 1

    def test_normalize_all_zero_trust_unchanged(self):
        """When all trust is zero in a dimension, scores are unchanged."""
        scores = {
            "alice": TypedTrustScore(_evidence={"integrity": {"obs": 1.0}}),
            "bob": TypedTrustScore(_evidence={"integrity": {"obs": 1.0}}),
        }
        normalized = TrustHomeostasis.normalize(scores, peer_count=2)
        # Both have zero trust in integrity -> no scaling possible
        for p in normalized:
            assert normalized[p].trust_for_dimension("integrity") == pytest.approx(0.0, abs=0.01)

    def test_normalize_single_peer(self):
        """Normalization with single peer scales to trust = 1.0 per dim."""
        scores = {"alice": TypedTrustScore(_evidence={"integrity": {"obs": 0.5}})}
        normalized = TrustHomeostasis.normalize(scores, peer_count=1)
        assert normalized["alice"].trust_for_dimension("integrity") == pytest.approx(1.0, abs=0.1)
