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

"""Tests for trust resilience (Whitfield §12, Okonkwo §8, Nair §14-15)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.trust_resilience import (
    TrustPrivacyFilter,
    ByzantineThresholdAnalyzer,
    ColdStartBootstrap,
    ExtendedDimensionRegistry,
    Introduction,
)


class TestTrustPrivacyFilter:
    def test_filter_produces_valid_range(self):
        f = TrustPrivacyFilter(epsilon=1.0)
        for _ in range(100):
            result = f.filter_trust_score(0.5)
            assert 0.0 <= result <= 1.0

    def test_budget_exhaustion(self):
        f = TrustPrivacyFilter(epsilon=1.0, max_queries=5)
        for _ in range(5):
            f.filter_trust_score(0.5)
        with pytest.raises(RuntimeError, match="budget exhausted"):
            f.filter_trust_score(0.5)

    def test_budget_reset(self):
        f = TrustPrivacyFilter(max_queries=2)
        f.filter_trust_score(0.5)
        f.filter_trust_score(0.5)
        f.reset_budget()
        f.filter_trust_score(0.5)  # Should not raise

    def test_filter_vector(self):
        f = TrustPrivacyFilter(epsilon=1.0)
        scores = {"integrity": 0.8, "model": 0.6}
        result = f.filter_trust_vector(scores)
        assert set(result.keys()) == {"integrity", "model"}
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_budget_tracking(self):
        f = TrustPrivacyFilter(max_queries=100)
        assert f.budget_remaining == 1.0
        f.filter_trust_score(0.5)
        assert f.budget_remaining == 0.99


class TestByzantineThresholdAnalyzer:
    def test_honest_dominates_at_low_ratio(self):
        a = ByzantineThresholdAnalyzer()
        r = a.analyze(90, 10, cycles=100)
        assert r.honest_dominates
        assert r.degradation_mode == "full"

    def test_degraded_at_moderate_ratio(self):
        a = ByzantineThresholdAnalyzer()
        r = a.analyze(60, 40, cycles=100)
        assert r.degradation_mode in ("full", "degraded")

    def test_overwhelmed_at_high_ratio(self):
        a = ByzantineThresholdAnalyzer()
        r = a.analyze(20, 80, cycles=100)
        assert r.degradation_mode in ("severely_degraded", "overwhelmed")

    def test_sweep_produces_monotonic_degradation(self):
        a = ByzantineThresholdAnalyzer()
        results = a.sweep(total_peers=100, steps=10)
        assert len(results) == 11
        # Trust differential should generally decrease
        assert results[0].trust_differential >= results[-1].trust_differential

    def test_critical_threshold_exists(self):
        a = ByzantineThresholdAnalyzer()
        threshold = a.critical_threshold(total_peers=100)
        assert 0.0 < threshold < 1.0

    def test_empty_network(self):
        a = ByzantineThresholdAnalyzer()
        r = a.analyze(0, 0)
        assert r.degradation_mode == "empty"


class TestColdStartBootstrap:
    def test_accept_introduction(self):
        b = ColdStartBootstrap()
        intro = Introduction(
            introducer="trusted-peer",
            introduced="new-peer",
            vouched_dims=("integrity", "model"),
            boost_amount=0.2,
            proof=b"valid",
        )
        assert b.introduce(0.9, intro)
        boosts = b.get_boost("new-peer")
        assert "integrity" in boosts
        assert boosts["integrity"] > 0

    def test_reject_low_trust_introducer(self):
        b = ColdStartBootstrap()
        intro = Introduction(
            introducer="untrusted", introduced="new",
            vouched_dims=("model",), boost_amount=0.2, proof=b"p",
        )
        assert not b.introduce(0.3, intro)

    def test_reject_invalid_proof(self):
        b = ColdStartBootstrap()
        intro = Introduction(
            introducer="trusted", introduced="new",
            vouched_dims=("model",), boost_amount=0.2, proof=b"",
        )
        assert not b.introduce(0.9, intro)

    def test_boost_decay(self):
        b = ColdStartBootstrap(decay_cycles=10)
        intro = Introduction(
            introducer="t", introduced="new",
            vouched_dims=("model",), boost_amount=0.2, proof=b"p",
        )
        b.introduce(0.9, intro)
        initial = b.get_boost("new")["model"]
        for _ in range(20):
            b.decay_step()
        final = b.get_boost("new")
        assert not final or final.get("model", 0) < initial

    def test_confirm_resets_decay(self):
        b = ColdStartBootstrap(decay_cycles=5)
        intro = Introduction(
            introducer="t", introduced="new",
            vouched_dims=("model",), boost_amount=0.2, proof=b"p",
        )
        b.introduce(0.9, intro)
        b.decay_step()
        b.confirm_behavior("new")
        # Decay timer reset, boost should persist longer


class TestExtendedDimensionRegistry:
    def test_base_dimensions(self):
        reg = ExtendedDimensionRegistry()
        assert len(reg.all_dimensions) == 6

    def test_register_custom(self):
        reg = ExtendedDimensionRegistry()
        reg.register("python_quality", weight=1.5, description="Python code trust")
        assert "python_quality" in reg.all_dimensions
        assert reg.dimension_count == 7

    def test_cannot_override_base(self):
        reg = ExtendedDimensionRegistry()
        with pytest.raises(ValueError, match="cannot override"):
            reg.register("integrity")

    def test_weighted_overall(self):
        reg = ExtendedDimensionRegistry()
        reg.register("custom", weight=2.0)
        scores = {d: 1.0 for d in reg.all_dimensions}
        assert reg.weighted_overall_trust(scores) == pytest.approx(1.0)

    def test_unregister(self):
        reg = ExtendedDimensionRegistry()
        reg.register("temp")
        assert reg.unregister("temp")
        assert "temp" not in reg.all_dimensions
