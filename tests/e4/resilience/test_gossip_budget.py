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

"""Tests for gossip bandwidth budget analyser."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "source"))

from crdt_merge.e4.resilience.gossip_budget import (
    HierarchicalAggregator,
    SparseTrustDelta,
    AdaptiveGossipRate,
    estimate_bandwidth,
    BandwidthEstimate,
)


class TestEstimateBandwidth:

    def test_small_network_recommends_full(self):
        est = estimate_bandwidth(100)
        assert est.recommended_strategy == "full"

    def test_medium_network_recommends_sparse(self):
        est = estimate_bandwidth(50_000)
        assert est.recommended_strategy == "sparse"

    def test_large_network_recommends_regional(self):
        est = estimate_bandwidth(10_000_000)
        assert est.recommended_strategy == "regional"

    def test_regional_much_smaller_than_full(self):
        est = estimate_bandwidth(10_000_000)
        assert est.regional_summary_bytes < est.full_state_bytes / 1000

    def test_sparse_smaller_than_full(self):
        est = estimate_bandwidth(10_000, churn_rate=0.01)
        assert est.sparse_delta_bytes < est.full_state_bytes


class TestSparseTrustDelta:

    def test_serialize_roundtrip(self):
        delta = SparseTrustDelta(epoch=42)
        delta.add("peer-1", (0.8, 0.7, 0.6, 0.5, 0.9))
        delta.add("peer-2", (0.3, 0.4, 0.5, 0.6, 0.7))
        data = delta.serialize()
        restored = SparseTrustDelta.deserialize(data)
        assert restored.epoch == 42
        assert restored.change_count == 2
        assert abs(restored.changed_peers["peer-1"][0] - 0.8) < 1e-10

    def test_wire_size_compact(self):
        delta = SparseTrustDelta(epoch=1)
        delta.add("p1", (0.5,) * 5)
        assert delta.wire_size < 100

    def test_empty_delta(self):
        delta = SparseTrustDelta(epoch=0)
        data = delta.serialize()
        restored = SparseTrustDelta.deserialize(data)
        assert restored.change_count == 0


class TestHierarchicalAggregator:

    def test_assign_peers(self):
        agg = HierarchicalAggregator(region_count=10)
        for i in range(100):
            agg.assign_peer(f"peer-{i}", (0.8, 0.7, 0.6, 0.5, 0.9))
        assert agg.peer_count == 100
        assert agg.region_count <= 10

    def test_compute_summaries(self):
        agg = HierarchicalAggregator(region_count=5)
        for i in range(50):
            agg.assign_peer(f"p-{i}", (0.5 + i * 0.01,) * 5)
        summaries = agg.compute_summaries(epoch=1)
        assert len(summaries) <= 5
        assert all(s.peer_count > 0 for s in summaries)

    def test_wire_size_scales_with_regions(self):
        agg = HierarchicalAggregator(region_count=100)
        for i in range(10_000):
            agg.assign_peer(f"p-{i}", (0.5,) * 5)
        size = agg.total_wire_size()
        # Should be much less than full state (10K * 40 = 400KB)
        assert size < 50_000

    def test_update_peer(self):
        agg = HierarchicalAggregator(region_count=5)
        agg.assign_peer("p1", (0.5,) * 5)
        agg.update_peer("p1", (0.9,) * 5)
        summaries = agg.compute_summaries()
        assert any(s.trust_mean > 0.8 for s in summaries)

    def test_remove_peer(self):
        agg = HierarchicalAggregator(region_count=5)
        agg.assign_peer("p1", (0.5,) * 5)
        agg.assign_peer("p2", (0.5,) * 5)
        agg.remove_peer("p1")
        assert agg.peer_count == 1


class TestAdaptiveGossipRate:

    def test_default_interval(self):
        rate = AdaptiveGossipRate(base_interval=30.0)
        assert abs(rate.current_interval() - 30.0) < 0.01

    def test_high_variance_accelerates(self):
        rate = AdaptiveGossipRate(base_interval=30.0, variance_threshold=0.01)
        for _ in range(10):
            rate.observe_variance(0.1)  # 10x threshold
        assert rate.current_interval() < 30.0

    def test_low_variance_decelerates(self):
        rate = AdaptiveGossipRate(base_interval=30.0, variance_threshold=0.01)
        for _ in range(10):
            rate.observe_variance(0.001)  # below threshold
        assert rate.current_interval() > 30.0

    def test_respects_bounds(self):
        rate = AdaptiveGossipRate(min_interval=5.0, max_interval=120.0)
        for _ in range(50):
            rate.observe_variance(100.0)  # extreme
        assert rate.current_interval() >= 5.0
        rate2 = AdaptiveGossipRate(min_interval=5.0, max_interval=120.0)
        for _ in range(50):
            rate2.observe_variance(0.0)
        assert rate2.current_interval() <= 120.0
