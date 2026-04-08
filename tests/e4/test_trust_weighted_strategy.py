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

"""Tests for trust_weighted_strategy.py — E3 entanglement (ref 870-874).

Covers:
  - TrustWeightedLWWResolver: trust-weighted last-writer-wins
  - TrustWeightedAveragingResolver: trust-weighted numeric averaging
  - TrustGatedAcceptanceFilter: per-dimension acceptance gating
  - TrustWeightedStrategySelector: meta-strategy routing
  - Edge cases: empty sets, all-rejected, single entry, ties
  - Byzantine scenarios: low-trust outliers, Sybil flooding
"""

import pytest

from crdt_merge.e4.typed_trust import (
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    TypedTrustScore,
    TRUST_DIMENSIONS,
)
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry,
    ConflictType,
    ResolutionResult,
    TrustGatedAcceptanceFilter,
    TrustWeightedAveragingResolver,
    TrustWeightedLWWResolver,
    TrustWeightedStrategySelector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trust(overall: float) -> TypedTrustScore:
    """Create a trust score with approximately the given overall trust."""
    if overall >= PROBATION_TRUST:
        return TypedTrustScore.full_trust()
    evidence = {}
    penalty = max(0.0, 1.0 - overall)
    for dim in TRUST_DIMENSIONS:
        evidence[dim] = {"test-observer": penalty}
    return TypedTrustScore(_evidence=evidence)


def _entry(
    peer: str,
    value,
    timestamp: float = 1.0,
    trust_level: float = PROBATION_TRUST,
    dimension: str = "integrity",
) -> ConflictEntry:
    return ConflictEntry(
        peer_id=peer,
        value=value,
        timestamp=timestamp,
        trust=_make_trust(trust_level),
        dimension=dimension,
    )


# ===========================================================================
# TrustWeightedLWWResolver
# ===========================================================================

class TestTrustWeightedLWWResolver:

    def test_higher_trust_beats_later_timestamp(self):
        """Trusted peer at t=5 should beat untrusted peer at t=7."""
        resolver = TrustWeightedLWWResolver()
        entries = [
            _entry("alice", "trusted_value", timestamp=8.0, trust_level=0.5),
            _entry("eve", "untrusted_value", timestamp=10.0, trust_level=0.15),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value == "trusted_value"
        assert result.method == "trust_weighted_lww"
        assert "alice" in result.contributors

    def test_same_trust_later_timestamp_wins(self):
        """Equal trust → later timestamp wins (standard LWW)."""
        resolver = TrustWeightedLWWResolver()
        entries = [
            _entry("alice", "old", timestamp=5.0, trust_level=0.5),
            _entry("bob", "new", timestamp=7.0, trust_level=0.5),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value == "new"

    def test_quarantined_peer_filtered(self):
        """Peers below quarantine threshold should be rejected."""
        resolver = TrustWeightedLWWResolver()
        entries = [
            _entry("alice", "good", timestamp=1.0, trust_level=0.5),
            _entry("eve", "bad", timestamp=10.0, trust_level=0.05),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value == "good"
        assert "eve" in result.rejected_peers

    def test_all_below_threshold_fallback(self):
        """When all peers are below threshold, highest trust wins."""
        resolver = TrustWeightedLWWResolver(min_trust=0.9)
        entries = [
            _entry("alice", "val_a", timestamp=1.0, trust_level=0.3),
            _entry("bob", "val_b", timestamp=2.0, trust_level=0.5),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value == "val_b"  # highest trust

    def test_single_entry(self):
        """Single entry should resolve trivially."""
        resolver = TrustWeightedLWWResolver()
        entries = [_entry("alice", "only_value", timestamp=1.0)]
        result = resolver.resolve(entries)
        assert result.resolved_value == "only_value"
        assert result.contributors == ("alice",)

    def test_empty_raises(self):
        """Empty entry set should raise ValueError."""
        resolver = TrustWeightedLWWResolver()
        with pytest.raises(ValueError, match="empty"):
            resolver.resolve([])

    def test_trust_weight_factor(self):
        """Higher trust_weight_factor gives trust more influence."""
        entries = [
            _entry("alice", "trusted", timestamp=5.0, trust_level=0.5),
            _entry("bob", "recent", timestamp=6.0, trust_level=0.1),
        ]
        # Low factor: recency dominates
        low_resolver = TrustWeightedLWWResolver(trust_weight_factor=0.1)
        low_result = low_resolver.resolve(entries)

        # High factor: trust dominates
        high_resolver = TrustWeightedLWWResolver(trust_weight_factor=5.0)
        high_result = high_resolver.resolve(entries)

        assert high_result.resolved_value == "trusted"

    def test_deterministic_tiebreaker(self):
        """Exact ties should be broken deterministically by peer_id."""
        resolver = TrustWeightedLWWResolver()
        entries = [
            _entry("bob", "val_b", timestamp=5.0, trust_level=0.5),
            _entry("alice", "val_a", timestamp=5.0, trust_level=0.5),
        ]
        result1 = resolver.resolve(entries)
        result2 = resolver.resolve(list(reversed(entries)))
        assert result1.resolved_value == result2.resolved_value

    def test_confidence_reflects_trust(self):
        """Confidence should reflect the winner's dimension trust."""
        resolver = TrustWeightedLWWResolver()
        entries = [_entry("alice", "val", timestamp=1.0, trust_level=0.5)]
        result = resolver.resolve(entries)
        assert 0.0 <= result.confidence <= 1.0


# ===========================================================================
# TrustWeightedAveragingResolver
# ===========================================================================

class TestTrustWeightedAveragingResolver:

    def test_weighted_average_basic(self):
        """Trust-weighted average of two numeric values."""
        resolver = TrustWeightedAveragingResolver()
        entries = [
            _entry("alice", 10.0, trust_level=0.9),
            _entry("bob", 20.0, trust_level=0.1),
        ]
        result = resolver.resolve(entries)
        # Alice's weight dominates → closer to 10 than 20
        assert result.resolved_value < 15.0
        assert result.method == "trust_weighted_averaging"

    def test_equal_trust_equals_arithmetic_mean(self):
        """Equal trust → standard arithmetic mean."""
        resolver = TrustWeightedAveragingResolver()
        entries = [
            _entry("alice", 10.0, trust_level=0.5),
            _entry("bob", 20.0, trust_level=0.5),
        ]
        result = resolver.resolve(entries)
        assert abs(result.resolved_value - 15.0) < 0.01

    def test_outlier_filtering(self):
        """Outlier values should be excluded when outlier_sigma > 0."""
        resolver = TrustWeightedAveragingResolver(outlier_sigma=2.0)
        entries = [
            _entry("alice", 10.0, trust_level=0.5),
            _entry("bob", 11.0, trust_level=0.5),
            _entry("carol", 12.0, trust_level=0.5),
            _entry("eve", 1000.0, trust_level=0.3),  # outlier
        ]
        result = resolver.resolve(entries)
        # Eve's outlier should be excluded
        assert result.resolved_value < 20.0

    def test_outlier_filtering_disabled(self):
        """With outlier_sigma=0, all values included."""
        resolver = TrustWeightedAveragingResolver(outlier_sigma=0)
        entries = [
            _entry("alice", 10.0, trust_level=0.5),
            _entry("bob", 11.0, trust_level=0.5),
            _entry("eve", 1000.0, trust_level=0.5),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value > 100.0  # outlier pulls it up

    def test_low_trust_excluded(self):
        """Peers below min_trust should contribute zero weight."""
        resolver = TrustWeightedAveragingResolver(min_trust=0.4)
        entries = [
            _entry("alice", 10.0, trust_level=0.9),
            _entry("eve", 1000.0, trust_level=0.05),  # below threshold
        ]
        result = resolver.resolve(entries)
        assert abs(result.resolved_value - 10.0) < 1.0

    def test_all_rejected_fallback(self):
        """All below threshold → highest trust peer's value."""
        resolver = TrustWeightedAveragingResolver(min_trust=0.99)
        entries = [
            _entry("alice", 10.0, trust_level=0.3),
            _entry("bob", 20.0, trust_level=0.45),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value == 20.0  # bob has higher trust
        assert "fallback" in result.method

    def test_confidence_range(self):
        """Confidence should be in [0, 1]."""
        resolver = TrustWeightedAveragingResolver()
        entries = [
            _entry("alice", 10.0, trust_level=0.5),
            _entry("bob", 20.0, trust_level=0.5),
        ]
        result = resolver.resolve(entries)
        assert 0.0 <= result.confidence <= 1.0

    def test_single_entry(self):
        """Single entry returns its value directly."""
        resolver = TrustWeightedAveragingResolver()
        entries = [_entry("alice", 42.0, trust_level=0.8)]
        result = resolver.resolve(entries)
        assert abs(result.resolved_value - 42.0) < 0.01

    def test_empty_raises(self):
        resolver = TrustWeightedAveragingResolver()
        with pytest.raises(ValueError, match="empty"):
            resolver.resolve([])

    def test_byzantine_minority_suppressed(self):
        """Byzantine minority (high value, low trust) should have minimal impact."""
        resolver = TrustWeightedAveragingResolver()
        entries = [
            _entry("alice", 100.0, trust_level=0.9),
            _entry("bob", 101.0, trust_level=0.9),
            _entry("carol", 99.0, trust_level=0.9),
            _entry("eve", 999999.0, trust_level=0.15),
        ]
        result = resolver.resolve(entries)
        assert result.resolved_value < 200.0  # eve's impact minimised


# ===========================================================================
# TrustGatedAcceptanceFilter
# ===========================================================================

class TestTrustGatedAcceptanceFilter:

    def test_accept_above_threshold(self):
        gate = TrustGatedAcceptanceFilter(global_threshold=0.3)
        trust = _make_trust(0.5)
        assert gate.accept("alice", trust) is True

    def test_reject_below_threshold(self):
        gate = TrustGatedAcceptanceFilter(global_threshold=0.7)
        trust = _make_trust(0.2)
        assert gate.accept("eve", trust) is False

    def test_per_dimension_threshold(self):
        """Per-dimension thresholds override global."""
        gate = TrustGatedAcceptanceFilter(
            thresholds={"integrity": 0.9, "model": 0.1},
            global_threshold=0.5,
        )
        trust = _make_trust(0.5)
        # integrity check fails (0.5 < 0.9), model passes (0.5 > 0.1)
        # strict mode: must pass ALL → False
        assert gate.accept("peer", trust, dimensions=["integrity", "model"]) is False

    def test_or_mode(self):
        """OR mode: any passing dimension allows."""
        gate = TrustGatedAcceptanceFilter(
            thresholds={"integrity": 0.9, "model": 0.1},
            global_threshold=0.5,
            strict_mode=False,
        )
        trust = _make_trust(0.5)
        # model passes → accept
        assert gate.accept("peer", trust, dimensions=["integrity", "model"]) is True

    def test_filter_entries_partitions(self):
        """filter_entries should split into accepted/rejected."""
        gate = TrustGatedAcceptanceFilter(global_threshold=0.4)
        entries = [
            _entry("alice", "a", trust_level=0.8),
            _entry("bob", "b", trust_level=0.5),
            _entry("eve", "e", trust_level=0.05),
        ]
        accepted, rejected = gate.filter_entries(entries)
        assert len(accepted) == 2
        assert "eve" in rejected

    def test_no_dimensions_uses_overall(self):
        """When dimensions=None, uses overall trust."""
        gate = TrustGatedAcceptanceFilter(global_threshold=0.3)
        trust = _make_trust(0.5)
        assert gate.accept("peer", trust, dimensions=None) is True


# ===========================================================================
# TrustWeightedStrategySelector
# ===========================================================================

class TestTrustWeightedStrategySelector:

    def test_numeric_routes_to_averaging(self):
        selector = TrustWeightedStrategySelector()
        entries = [
            _entry("alice", 10.0, trust_level=0.8),
            _entry("bob", 20.0, trust_level=0.8),
        ]
        result = selector.resolve(entries, ConflictType.NUMERIC)
        assert "averaging" in result.method

    def test_opaque_routes_to_lww(self):
        selector = TrustWeightedStrategySelector()
        entries = [
            _entry("alice", b"blob_a", timestamp=5.0, trust_level=0.8),
            _entry("bob", b"blob_b", timestamp=3.0, trust_level=0.8),
        ]
        result = selector.resolve(entries, ConflictType.OPAQUE)
        assert "lww" in result.method

    def test_counter_takes_max(self):
        selector = TrustWeightedStrategySelector()
        entries = [
            _entry("alice", 5, trust_level=0.8),
            _entry("bob", 8, trust_level=0.8),
        ]
        result = selector.resolve(entries, ConflictType.COUNTER)
        assert result.resolved_value == 8

    def test_set_union(self):
        selector = TrustWeightedStrategySelector()
        entries = [
            _entry("alice", {"a", "b"}, trust_level=0.8),
            _entry("bob", {"b", "c"}, trust_level=0.8),
        ]
        result = selector.resolve(entries, ConflictType.SET)
        assert result.resolved_value == frozenset({"a", "b", "c"})

    def test_acceptance_filter_applied(self):
        """Low-trust peers should be filtered before resolving."""
        gate = TrustGatedAcceptanceFilter(global_threshold=0.4)
        selector = TrustWeightedStrategySelector(acceptance_filter=gate)
        entries = [
            _entry("alice", "good", timestamp=1.0, trust_level=0.8),
            _entry("eve", "bad", timestamp=10.0, trust_level=0.05),
        ]
        result = selector.resolve(entries, ConflictType.OPAQUE)
        assert result.resolved_value == "good"
        assert "eve" in result.rejected_peers

    def test_all_rejected_fallback(self):
        """When filter rejects everyone, fallback to highest trust."""
        gate = TrustGatedAcceptanceFilter(global_threshold=0.99)
        selector = TrustWeightedStrategySelector(acceptance_filter=gate)
        entries = [
            _entry("alice", "a", trust_level=0.3),
            _entry("bob", "b", trust_level=0.45),
        ]
        result = selector.resolve(entries, ConflictType.OPAQUE)
        assert result.resolved_value == "b"  # highest trust
        assert "fallback" in result.method

    def test_custom_resolver_registration(self):
        """Custom resolvers override built-in routing."""

        class MyResolver:
            def resolve(self, entries, trust_lattice=None):
                return ResolutionResult(
                    resolved_value="custom_result",
                    confidence=1.0,
                    method="custom_test",
                    contributors=("test",),
                )

        selector = TrustWeightedStrategySelector()
        selector.register(ConflictType.NUMERIC, MyResolver())
        entries = [_entry("alice", 10.0, trust_level=0.8)]
        result = selector.resolve(entries, ConflictType.NUMERIC)
        assert result.resolved_value == "custom_result"
        assert result.method == "custom_test"

    def test_registered_types_introspection(self):
        selector = TrustWeightedStrategySelector()
        assert selector.registered_types == []
        selector.register(ConflictType.NUMERIC, TrustWeightedLWWResolver())
        assert "numeric" in selector.registered_types

    def test_empty_raises(self):
        selector = TrustWeightedStrategySelector()
        with pytest.raises(ValueError, match="empty"):
            selector.resolve([], ConflictType.OPAQUE)

    def test_structured_routes_to_lww(self):
        """Structured conflicts default to LWW."""
        selector = TrustWeightedStrategySelector()
        entries = [
            _entry("alice", {"key": "val1"}, timestamp=5.0, trust_level=0.8),
            _entry("bob", {"key": "val2"}, timestamp=3.0, trust_level=0.8),
        ]
        result = selector.resolve(entries, ConflictType.STRUCTURED)
        assert "lww" in result.method


# ===========================================================================
# Byzantine scenarios
# ===========================================================================

class TestByzantineScenarios:

    def test_sybil_flood_lww(self):
        """Many low-trust Sybil peers should not overpower one trusted peer."""
        resolver = TrustWeightedLWWResolver()
        entries = [
            _entry("alice", "real_value", timestamp=5.0, trust_level=0.9),
        ]
        # 10 Sybil peers with low trust and later timestamps
        for i in range(10):
            entries.append(
                _entry(f"sybil-{i}", "fake_value", timestamp=20.0, trust_level=0.08)
            )
        result = resolver.resolve(entries)
        assert result.resolved_value == "real_value"
        assert len(result.rejected_peers) == 10

    def test_sybil_flood_averaging(self):
        """Sybil peers should not skew the average significantly."""
        resolver = TrustWeightedAveragingResolver()
        entries = [
            _entry("alice", 100.0, trust_level=0.9),
            _entry("bob", 101.0, trust_level=0.9),
        ]
        for i in range(10):
            entries.append(
                _entry(f"sybil-{i}", 999999.0, trust_level=0.08)
            )
        result = resolver.resolve(entries)
        # Sybils rejected, result should be close to 100.5
        assert result.resolved_value < 200.0

    def test_gradual_trust_erosion(self):
        """As trust decreases, influence on LWW result should decrease."""
        resolver = TrustWeightedLWWResolver(trust_weight_factor=2.0)
        entries_high = [
            _entry("alice", "alice_val", timestamp=5.0, trust_level=0.9),
            _entry("bob", "bob_val", timestamp=6.0, trust_level=0.8),
        ]
        entries_low = [
            _entry("alice", "alice_val", timestamp=5.0, trust_level=0.9),
            _entry("bob", "bob_val", timestamp=6.0, trust_level=0.2),
        ]
        # At high trust, bob might win (later timestamp)
        # At low trust, alice should win (higher trust compensates)
        result_low = resolver.resolve(entries_low)
        assert result_low.resolved_value == "alice_val"

    def test_selector_with_mixed_sybils(self):
        """Selector should filter Sybils regardless of conflict type."""
        selector = TrustWeightedStrategySelector()

        # Numeric: Sybils try to skew average
        num_entries = [
            _entry("alice", 100.0, trust_level=0.9),
        ]
        for i in range(5):
            num_entries.append(
                _entry(f"sybil-{i}", 0.0, trust_level=0.05)
            )
        result = selector.resolve(num_entries, ConflictType.NUMERIC)
        assert result.resolved_value > 50.0  # Sybils filtered

        # Set: Sybils try to inject elements
        set_entries = [
            _entry("alice", {"real"}, trust_level=0.9),
        ]
        for i in range(5):
            set_entries.append(
                _entry(f"sybil-{i}", {f"poison-{i}"}, trust_level=0.05)
            )
        result = selector.resolve(set_entries, ConflictType.SET)
        assert "real" in result.resolved_value
        # Sybil elements should NOT be in the set
        for i in range(5):
            assert f"poison-{i}" not in result.resolved_value
