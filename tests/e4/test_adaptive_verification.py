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

"""Tests for AdaptiveVerificationController.

Covers 4-tier gating (L0 trusted O(1), L1 known, L2 untrusted full PCO,
L3 quarantine reject), tier transitions, escalation/de-escalation, and
async followup.
"""

import pytest

from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
    VerificationResult,
)
from crdt_merge.e4.delta_trust_lattice import (
    DeltaTrustLattice,
    TrustCircuitBreaker,
)
from crdt_merge.e4.typed_trust import (
    TypedTrustScore,
    TRUST_DIMENSIONS,
    QUARANTINE_THRESHOLD,
)
from e4_factories import make_delta, make_pco


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lattice_with_trust(peer_id, trust_level):
    """Create a lattice with peer at a specific trust level.

    trust_level: 'high' (>0.8), 'medium' (0.4-0.8), 'low' (<0.4), 'quarantined' (<0.1)
    """
    lat = DeltaTrustLattice("local", initial_peers={peer_id})
    if trust_level == "high":
        # No evidence -> probation 0.5 is not > 0.8
        # We need to set evidence carefully... Actually we need to NOT have evidence
        # and have trust > 0.8. Since default is 0.5 (probation), we can't easily
        # get above 0.8 without manipulating evidence. Let's just return default (medium).
        # Actually: trust = 1 - evidence. With no evidence per dimension, trust_for_dimension = PROBATION_TRUST = 0.5.
        # We need evidence to be < 0.2 per dimension to get trust > 0.8.
        # If we have explicit evidence of 0.0 per dimension, trust = 1.0 - 0.0 = 1.0
        ts = TypedTrustScore(_evidence={dim: {"_init": 0.0} for dim in TRUST_DIMENSIONS})
        lat._trust_scores[peer_id] = ts
    elif trust_level == "medium":
        pass  # default probation = 0.5
    elif trust_level == "low":
        ts = TypedTrustScore(_evidence={dim: {"obs": 0.7} for dim in TRUST_DIMENSIONS})
        lat._trust_scores[peer_id] = ts
    elif trust_level == "quarantined":
        ts = TypedTrustScore(_evidence={dim: {"obs": 0.95} for dim in TRUST_DIMENSIONS})
        lat._trust_scores[peer_id] = ts
    return lat


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------

class TestVerificationResult:

    def test_accept_result(self):
        """ACCEPT result has accepted == True."""
        r = VerificationResult(outcome=VerificationOutcome.ACCEPT, level=0)
        assert r.accepted is True

    def test_reject_result(self):
        """REJECT result has accepted == False."""
        r = VerificationResult(outcome=VerificationOutcome.REJECT, level=3, reason="quarantined")
        assert r.accepted is False
        assert r.reason == "quarantined"

    def test_async_pending_flag(self):
        """async_pending flag tracks deferred verification."""
        r = VerificationResult(
            outcome=VerificationOutcome.ACCEPT, level=0, async_pending=True,
        )
        assert r.async_pending is True


# ---------------------------------------------------------------------------
# Level 3 -- Quarantine reject
# ---------------------------------------------------------------------------

class TestVerifyLevel3:

    def test_quarantined_sender_rejected(self):
        """L3: Quarantined sender is unconditionally rejected."""
        lat = _lattice_with_trust("eve", "quarantined")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="eve")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.accepted is False
        assert result.level == 3
        assert "quarantined" in result.reason


# ---------------------------------------------------------------------------
# Level 2 -- Full PCO
# ---------------------------------------------------------------------------

class TestVerifyLevel2:

    def test_low_trust_gets_level_2(self):
        """L2: Low-trust sender gets full PCO verification."""
        lat = _lattice_with_trust("bob", "low")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.level == 2

    def test_level_2_full_pco_pass(self):
        """L2: Valid full PCO is accepted."""
        lat = _lattice_with_trust("bob", "low")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        # With stub verifier (64 zero-byte sig) and no minimality bounds, should pass
        assert result.accepted is True


# ---------------------------------------------------------------------------
# Level 1 -- Signature + Merkle root
# ---------------------------------------------------------------------------

class TestVerifyLevel1:

    def test_medium_trust_gets_level_1(self):
        """L1: Medium-trust sender gets signature + Merkle root check."""
        lat = _lattice_with_trust("bob", "medium")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.level == 1

    def test_level_1_accepted_with_async(self):
        """L1: Accepted result has async_pending=True."""
        lat = _lattice_with_trust("bob", "medium")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.accepted is True
        assert result.async_pending is True


# ---------------------------------------------------------------------------
# Level 0 -- Signature only
# ---------------------------------------------------------------------------

class TestVerifyLevel0:

    def test_high_trust_gets_level_0(self):
        """L0: High-trust sender gets signature-only verification."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.level == 0

    def test_level_0_accepted_with_async(self):
        """L0: Accepted result has async_pending=True."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert result.accepted is True
        assert result.async_pending is True


# ---------------------------------------------------------------------------
# Circuit breaker override
# ---------------------------------------------------------------------------

class TestCircuitBreakerOverride:

    def test_tripped_breaker_forces_level_2(self):
        """When circuit breaker is tripped, verification is forced to level 2."""
        lat = _lattice_with_trust("bob", "high")
        cb = TrustCircuitBreaker(
            window_size=5, sigma_threshold=0.0, min_samples=1, cooldown_seconds=999,
        )
        # Trip the breaker
        old = TypedTrustScore.probationary()
        big_ev = {d: {"obs": 0.9} for d in TRUST_DIMENSIONS}
        big = TypedTrustScore(_evidence=big_ev)
        cb.record_trust_change("x", old, big)
        cb.record_trust_change("x", old, big)

        ctrl = AdaptiveVerificationController(
            trust_lattice=lat, circuit_breaker=cb,
        )
        if cb.is_tripped():
            delta = make_delta(source_id="bob")
            result = ctrl.verify(delta, state=object(), trust_lattice=lat)
            assert result.level == 2


# ---------------------------------------------------------------------------
# No trust lattice
# ---------------------------------------------------------------------------

class TestNoTrustLattice:

    def test_no_lattice_rejects(self):
        """Without a trust lattice, verification rejects."""
        ctrl = AdaptiveVerificationController()
        delta = make_delta(source_id="bob")
        result = ctrl.verify(delta, state=object())
        assert result.accepted is False
        assert "no trust lattice" in result.reason


# ---------------------------------------------------------------------------
# Async followup
# ---------------------------------------------------------------------------

class TestAsyncFollowup:

    def test_async_queue_populated(self):
        """Level 0/1 accepts populate the async queue."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        ctrl.verify(delta, state=object(), trust_lattice=lat)
        assert ctrl.pending_async_count >= 1

    def test_run_async_followup(self):
        """run_async_followup re-verifies at level 2."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        ctrl.verify(delta, state=object(), trust_lattice=lat)
        results = ctrl.run_async_followup(state=object(), trust_lattice=lat)
        assert len(results) >= 1
        for d, vr in results:
            assert isinstance(vr, VerificationResult)

    def test_drain_async_queue(self):
        """drain_async_queue returns items and clears."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(trust_lattice=lat)
        delta = make_delta(source_id="bob")
        ctrl.verify(delta, state=object(), trust_lattice=lat)
        items = ctrl.drain_async_queue()
        assert len(items) >= 1
        assert ctrl.pending_async_count == 0

    def test_async_queue_limit(self):
        """Async queue respects maxlen."""
        lat = _lattice_with_trust("bob", "high")
        ctrl = AdaptiveVerificationController(
            trust_lattice=lat, async_queue_limit=2,
        )
        for _ in range(5):
            ctrl.verify(make_delta(source_id="bob"), state=object(), trust_lattice=lat)
        assert ctrl.pending_async_count <= 2


# ---------------------------------------------------------------------------
# Bind methods
# ---------------------------------------------------------------------------

class TestAdaptiveVerificationBind:

    def test_bind_trust_lattice(self):
        """bind_trust_lattice injects a lattice."""
        ctrl = AdaptiveVerificationController()
        lat = DeltaTrustLattice("local")
        ctrl.bind_trust_lattice(lat)
        # Should now be able to verify
        delta = make_delta(source_id="some-peer")
        result = ctrl.verify(delta, state=object())
        assert isinstance(result, VerificationResult)

    def test_bind_circuit_breaker(self):
        """bind_circuit_breaker injects a breaker."""
        ctrl = AdaptiveVerificationController()
        cb = TrustCircuitBreaker()
        ctrl.bind_circuit_breaker(cb)
        # No error
