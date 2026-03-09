# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer

"""Tests for crdt_merge.flower_plugin — Flower integration plugin."""

from __future__ import annotations

import pytest

from crdt_merge.flower_plugin import (
    CRDTStrategy,
    FlowerAggregator,
    FlowerCRDTClient,
    _HAS_FLWR,
)


# ==========================================================================
# CRDTStrategy tests
# ==========================================================================

class TestCRDTStrategyInit:
    """1. CRDTStrategy initialization defaults."""

    def test_default_values(self):
        s = CRDTStrategy()
        assert s.merge_key == "layer_name"
        assert s.conflict_resolution == "lww"
        assert s.min_clients == 2
        assert s.min_available == 2

    def test_custom_values(self):
        s = CRDTStrategy(
            merge_key="param_name",
            conflict_resolution="max",
            min_clients=5,
            min_available=3,
        )
        assert s.merge_key == "param_name"
        assert s.conflict_resolution == "max"
        assert s.min_clients == 5
        assert s.min_available == 3


class TestCRDTStrategyAggregateFit:
    """2. CRDTStrategy aggregate_fit with mock results."""

    def test_aggregate_fit_basic(self):
        s = CRDTStrategy()
        results = [
            ("client_a", {"layer1": [1, 2], "layer2": 10}),
            ("client_b", {"layer1": [3, 4], "layer2": 20}),
        ]
        merged, metrics = s.aggregate_fit(server_round=1, results=results, failures=[])
        assert isinstance(merged, dict)
        assert "layer1" in merged
        assert "layer2" in merged
        assert metrics["merged_clients"] == 2
        assert metrics["server_round"] == 1
        assert metrics["failures"] == 0

    def test_aggregate_fit_empty(self):
        s = CRDTStrategy()
        merged, metrics = s.aggregate_fit(server_round=1, results=[], failures=[])
        assert merged == {}
        assert metrics["merged"] == 0

    def test_aggregate_fit_with_failures(self):
        s = CRDTStrategy()
        results = [("c1", {"a": 1})]
        merged, metrics = s.aggregate_fit(
            server_round=2, results=results, failures=["err1", "err2"]
        )
        assert metrics["failures"] == 2

    def test_aggregate_fit_dict_items(self):
        """Results as plain dicts (not tuples)."""
        s = CRDTStrategy()
        results = [
            ("c1", {"x": 1}),
            ("c2", {"y": 2}),
        ]
        merged, _ = s.aggregate_fit(server_round=1, results=results, failures=[])
        assert "x" in merged
        assert "y" in merged


class TestCRDTMergeParameters:
    """3. CRDTStrategy _crdt_merge_parameters merges dicts."""

    def test_merge_two_dicts(self):
        s = CRDTStrategy()
        params = [
            {"layer1": [1.0, 2.0], "bias1": 0.5},
            {"layer1": [3.0, 4.0], "bias2": 0.7},
        ]
        merged = s._crdt_merge_parameters(params)
        assert "layer1" in merged
        assert "bias1" in merged
        assert "bias2" in merged

    def test_merge_lww_scalars(self):
        s = CRDTStrategy(conflict_resolution="lww")
        params = [{"lr": 0.01}, {"lr": 0.001}]
        merged = s._crdt_merge_parameters(params)
        assert merged["lr"] == 0.001  # LWW: last wins

    def test_merge_max_scalars(self):
        s = CRDTStrategy(conflict_resolution="max")
        params = [{"score": 0.8}, {"score": 0.9}]
        merged = s._crdt_merge_parameters(params)
        assert merged["score"] == 0.9

    def test_merge_min_scalars(self):
        s = CRDTStrategy(conflict_resolution="min")
        params = [{"loss": 0.5}, {"loss": 0.3}]
        merged = s._crdt_merge_parameters(params)
        assert merged["loss"] == 0.3

    def test_merge_nested_dicts(self):
        s = CRDTStrategy()
        params = [
            {"model": {"encoder": {"dim": 128}}},
            {"model": {"encoder": {"dim": 256}, "decoder": {"dim": 64}}},
        ]
        merged = s._crdt_merge_parameters(params)
        assert merged["model"]["encoder"]["dim"] == 256
        assert merged["model"]["decoder"]["dim"] == 64

    def test_merge_single(self):
        s = CRDTStrategy()
        params = [{"a": 1, "b": 2}]
        merged = s._crdt_merge_parameters(params)
        assert merged == {"a": 1, "b": 2}

    def test_merge_empty_list(self):
        s = CRDTStrategy()
        merged = s._crdt_merge_parameters([])
        assert merged == {}

    def test_merge_lists_elementwise(self):
        s = CRDTStrategy(conflict_resolution="max")
        params = [{"w": [1, 2, 3]}, {"w": [4, 0, 5]}]
        merged = s._crdt_merge_parameters(params)
        assert merged["w"] == [4, 2, 5]


class TestCRDTStrategyStats:
    """4. CRDTStrategy get_merge_stats."""

    def test_initial_stats(self):
        s = CRDTStrategy()
        stats = s.get_merge_stats()
        assert stats["rounds_completed"] == 0
        assert stats["total_merges"] == 0
        assert stats["total_clients_seen"] == 0
        assert stats["last_merge_timestamp"] is None
        assert stats["conflict_resolution"] == "lww"
        assert stats["merge_key"] == "layer_name"
        assert "has_flower" in stats

    def test_stats_after_aggregate(self):
        s = CRDTStrategy()
        results = [("c1", {"a": 1}), ("c2", {"b": 2})]
        s.aggregate_fit(server_round=1, results=results, failures=[])
        stats = s.get_merge_stats()
        assert stats["rounds_completed"] == 1
        assert stats["total_merges"] >= 1
        assert stats["total_clients_seen"] == 2
        assert stats["last_merge_timestamp"] is not None


# ==========================================================================
# FlowerCRDTClient tests
# ==========================================================================

class TestFlowerCRDTClientMerge:
    """5. FlowerCRDTClient merge_update combines params."""

    def test_merge_update_basic(self):
        client = FlowerCRDTClient(node_id="client_1")
        local = {"layer1": [0.5, 0.6], "bias": 0.1}
        global_p = {"layer1": [0.1, 0.2], "lr": 0.01}
        merged = client.merge_update(local, global_p)
        assert "layer1" in merged
        assert "bias" in merged
        assert "lr" in merged

    def test_merge_update_lww_local_wins(self):
        """Local params override global (local = 'b' in LWW)."""
        client = FlowerCRDTClient(node_id="c1", conflict_resolution="lww")
        local = {"x": 100}
        global_p = {"x": 1}
        merged = client.merge_update(local, global_p)
        assert merged["x"] == 100  # local is 'b' (later)

    def test_merge_update_increments_count(self):
        client = FlowerCRDTClient(node_id="c1")
        assert client._merge_count == 0
        client.merge_update({"a": 1}, {"b": 2})
        assert client._merge_count == 1
        client.merge_update({"c": 3}, {"d": 4})
        assert client._merge_count == 2


class TestFlowerCRDTClientProperties:
    """6. FlowerCRDTClient get_properties."""

    def test_get_properties(self):
        client = FlowerCRDTClient(node_id="node_42", merge_key="param")
        props = client.get_properties()
        assert props["node_id"] == "node_42"
        assert props["merge_key"] == "param"
        assert props["merge_count"] == 0
        assert "has_flower" in props

    def test_properties_after_merge(self):
        client = FlowerCRDTClient(node_id="c1")
        client.merge_update({"a": 1}, {"b": 2})
        props = client.get_properties()
        assert props["merge_count"] == 1
        assert props["last_merge_timestamp"] is not None


# ==========================================================================
# FlowerAggregator tests
# ==========================================================================

class TestFlowerAggregatorCycle:
    """7. FlowerAggregator add/aggregate cycle."""

    def test_add_and_aggregate(self):
        agg = FlowerAggregator()
        agg.add_result("c1", {"layer1": [0.1, 0.2]})
        agg.add_result("c2", {"layer1": [0.3, 0.4]})
        merged = agg.aggregate()
        assert "layer1" in merged
        assert isinstance(merged["layer1"], list)

    def test_aggregate_empty(self):
        agg = FlowerAggregator()
        assert agg.aggregate() == {}


class TestFlowerAggregatorMultiClient:
    """8. FlowerAggregator with multiple clients."""

    def test_three_clients(self):
        agg = FlowerAggregator(conflict_resolution="lww")
        agg.add_result("c1", {"a": 1, "b": 10})
        agg.add_result("c2", {"a": 2, "c": 20})
        agg.add_result("c3", {"a": 3, "d": 30})
        merged = agg.aggregate()
        assert merged["a"] == 3  # LWW — last client wins
        assert merged["b"] == 10
        assert merged["c"] == 20
        assert merged["d"] == 30

    def test_three_clients_max(self):
        agg = FlowerAggregator(conflict_resolution="max")
        agg.add_result("c1", {"score": 0.7})
        agg.add_result("c2", {"score": 0.9})
        agg.add_result("c3", {"score": 0.8})
        merged = agg.aggregate()
        assert merged["score"] == 0.9

    def test_with_num_examples_and_metadata(self):
        agg = FlowerAggregator()
        agg.add_result("c1", {"w": 1}, num_examples=100, metadata={"epoch": 5})
        agg.add_result("c2", {"w": 2}, num_examples=200, metadata={"epoch": 3})
        stats = agg.get_stats()
        assert stats["total_examples"] == 300
        assert len(stats["client_ids"]) == 2


class TestFlowerAggregatorReset:
    """9. FlowerAggregator reset clears state."""

    def test_reset(self):
        agg = FlowerAggregator()
        agg.add_result("c1", {"x": 1})
        agg.add_result("c2", {"y": 2})
        assert len(agg._results) == 2
        agg.reset()
        assert len(agg._results) == 0
        assert len(agg._client_ids) == 0
        assert agg.aggregate() == {}


# ==========================================================================
# Serialization tests
# ==========================================================================

class TestToDict:
    """10. All classes to_dict serialization."""

    def test_strategy_to_dict(self):
        s = CRDTStrategy(merge_key="mk", conflict_resolution="max", min_clients=3)
        d = s.to_dict()
        assert d["type"] == "CRDTStrategy"
        assert d["merge_key"] == "mk"
        assert d["conflict_resolution"] == "max"
        assert d["min_clients"] == 3
        assert "stats" in d

    def test_client_to_dict(self):
        c = FlowerCRDTClient(node_id="n1", merge_key="layer")
        d = c.to_dict()
        assert d["type"] == "FlowerCRDTClient"
        assert d["node_id"] == "n1"
        assert "properties" in d

    def test_aggregator_to_dict(self):
        a = FlowerAggregator(conflict_resolution="min")
        a.add_result("c1", {"x": 1})
        d = a.to_dict()
        assert d["type"] == "FlowerAggregator"
        assert d["conflict_resolution"] == "min"
        assert d["pending_results"] == 1
        assert "stats" in d


# ==========================================================================
# Standalone mode (no Flower)
# ==========================================================================

class TestStandaloneMode:
    """11. Works without flwr installed (standalone mode)."""

    def test_strategy_works_standalone(self):
        s = CRDTStrategy()
        results = [("c1", {"a": 1}), ("c2", {"b": 2})]
        merged, metrics = s.aggregate_fit(server_round=1, results=results, failures=[])
        assert "a" in merged
        assert "b" in merged

    def test_configure_fit_returns_list_standalone(self):
        s = CRDTStrategy()
        config = s.configure_fit(server_round=1)
        assert isinstance(config, list)

    def test_configure_evaluate_returns_list_standalone(self):
        s = CRDTStrategy()
        config = s.configure_evaluate(server_round=1)
        assert isinstance(config, list)

    def test_aggregate_evaluate_standalone(self):
        s = CRDTStrategy()
        results = [("c1", {"loss": 0.5}), ("c2", {"loss": 0.3})]
        loss, metrics = s.aggregate_evaluate(server_round=1, results=results, failures=[])
        assert isinstance(loss, float)
        assert loss == pytest.approx(0.4)

    def test_aggregate_evaluate_empty(self):
        s = CRDTStrategy()
        loss, metrics = s.aggregate_evaluate(server_round=1, results=[], failures=[])
        assert loss == 0.0

    def test_client_standalone(self):
        c = FlowerCRDTClient(node_id="standalone")
        merged = c.merge_update({"w": [1, 2]}, {"w": [3, 4]})
        assert "w" in merged

    def test_aggregator_standalone(self):
        a = FlowerAggregator()
        a.add_result("c1", {"p": 1})
        result = a.aggregate()
        assert result == {"p": 1}


# ==========================================================================
# Edge cases
# ==========================================================================

class TestEdgeCases:
    """12. Edge cases: empty params, single client, etc."""

    def test_merge_empty_dicts(self):
        s = CRDTStrategy()
        merged = s._crdt_merge_parameters([{}, {}])
        assert merged == {}

    def test_merge_with_none_values(self):
        s = CRDTStrategy()
        merged = s._crdt_merge_parameters([{"a": None}, {"a": 1}])
        assert merged["a"] == 1

    def test_merge_none_with_value(self):
        s = CRDTStrategy()
        merged = s._crdt_merge_parameters([{"a": 1}, {"a": None}])
        assert merged["a"] == 1

    def test_single_client_aggregate(self):
        s = CRDTStrategy()
        results = [("c1", {"weight": [0.5]})]
        merged, metrics = s.aggregate_fit(server_round=1, results=results, failures=[])
        assert merged == {"weight": [0.5]}

    def test_aggregator_single_client(self):
        agg = FlowerAggregator()
        agg.add_result("c1", {"x": 42})
        assert agg.aggregate() == {"x": 42}

    def test_client_merge_with_empty_global(self):
        client = FlowerCRDTClient()
        merged = client.merge_update({"a": 1}, {})
        assert merged == {"a": 1}

    def test_client_merge_with_empty_local(self):
        client = FlowerCRDTClient()
        merged = client.merge_update({}, {"b": 2})
        assert merged == {"b": 2}

    def test_avg_conflict_resolution(self):
        s = CRDTStrategy(conflict_resolution="avg")
        merged = s._crdt_merge_parameters([{"val": 10.0}, {"val": 20.0}])
        assert merged["val"] == pytest.approx(15.0)

    def test_different_length_lists(self):
        s = CRDTStrategy()
        merged = s._crdt_merge_parameters([{"w": [1, 2]}, {"w": [3, 4, 5]}])
        # LWW for different lengths → last wins
        assert merged["w"] == [3, 4, 5]

    def test_repr_strategy(self):
        s = CRDTStrategy()
        assert "CRDTStrategy" in repr(s)

    def test_repr_client(self):
        c = FlowerCRDTClient(node_id="n1")
        assert "FlowerCRDTClient" in repr(c)

    def test_repr_aggregator(self):
        a = FlowerAggregator()
        assert "FlowerAggregator" in repr(a)
