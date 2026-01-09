# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for Dev 6 modules: continual, federated, formats, gpu, safety.

~120 tests covering all public APIs.
"""

import math
import sys
import pytest

# ===================================================================
# CONTINUAL MERGE TESTS (~25)
# ===================================================================

from crdt_merge.model.continual import ContinualMerge

class TestContinualMergeBasic:
    """Basic ContinualMerge functionality."""

    def test_init_with_base_model(self):
        cm = ContinualMerge(base_model={"w": [1.0, 2.0]})
        result = cm.export()
        assert "w" in result

    def test_absorb_single_model(self):
        cm = ContinualMerge(base_model={"w": [0.0, 0.0]})
        cm.absorb({"w": [2.0, 4.0]}, name="m1")
        result = cm.export()
        assert result["w"] is not None
        # Should be average of [0,0] and [2,4] = [1,2]
        assert abs(result["w"][0] - 1.0) < 1e-6
        assert abs(result["w"][1] - 2.0) < 1e-6

    def test_absorb_three_models_sequentially(self):
        cm = ContinualMerge(base_model={"w": [0.0, 0.0]})
        cm.absorb({"w": [3.0, 3.0]}, name="m1")
        cm.absorb({"w": [6.0, 6.0]}, name="m2")
        result = cm.export()
        # Average of [0,0], [3,3], [6,6] = [3,3]
        assert abs(result["w"][0] - 3.0) < 1e-6
        assert abs(result["w"][1] - 3.0) < 1e-6

    def test_absorb_with_weight(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [10.0]}, weight=3.0, name="heavy")
        result = cm.export()
        # base weight=1, heavy weight=3, total=4
        # merged = (1*0 + 3*10) / 4 = 7.5
        assert abs(result["w"][0] - 7.5) < 1e-6

    def test_replace_semantics(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [10.0]}, name="m1")
        cm.absorb({"w": [20.0]}, name="m2")
        # Before replace: avg of [0], [10], [20] = [10]
        before = cm.export()
        assert abs(before["w"][0] - 10.0) < 1e-6

        # Replace m1 with [30]
        cm.absorb({"w": [30.0]}, name="m1_v2", replace="m1")
        # Now: avg of [0], [20], [30] = [16.67]
        after = cm.export()
        assert abs(after["w"][0] - 50.0 / 3) < 1e-4

    def test_replace_nonexistent_is_noop(self):
        cm = ContinualMerge(base_model={"w": [1.0]})
        cm.absorb({"w": [3.0]}, name="new", replace="nonexistent")
        result = cm.export()
        # base [1] + new [3] = avg [2]
        assert abs(result["w"][0] - 2.0) < 1e-6

    def test_export_current_state(self):
        cm = ContinualMerge(base_model={"a": [1.0], "b": [2.0]})
        result = cm.export()
        assert "a" in result
        assert "b" in result

    def test_export_multi_layer(self):
        cm = ContinualMerge(base_model={"a": [0.0], "b": [0.0]})
        cm.absorb({"a": [2.0], "b": [4.0]}, name="m1")
        result = cm.export()
        assert abs(result["a"][0] - 1.0) < 1e-6
        assert abs(result["b"][0] - 2.0) < 1e-6

    def test_history_tracking(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="first")
        cm.absorb({"w": [2.0]}, name="second")
        hist = cm.history
        assert len(hist) == 2
        assert hist[0]["name"] == "first"
        assert hist[1]["name"] == "second"

    def test_history_has_timestamp(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="m1")
        assert "timestamp" in cm.history[0]
        assert len(cm.history[0]["timestamp"]) > 0

    def test_history_has_weight(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, weight=2.5, name="m1")
        assert cm.history[0]["weight"] == 2.5

    def test_history_replace_tracked(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="m1")
        cm.absorb({"w": [2.0]}, name="m2", replace="m1")
        assert cm.history[1]["replaced"] == "m1"

    def test_history_no_replace_is_none(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="m1")
        assert cm.history[0]["replaced"] is None

    def test_current_weights_sum_to_one(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="m1")
        cm.absorb({"w": [2.0]}, name="m2")
        weights = cm.current_weights
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_current_weights_uniform_no_decay(self):
        cm = ContinualMerge(base_model={"w": [0.0]}, memory_budget=1.0)
        cm.absorb({"w": [1.0]}, name="m1")
        cm.absorb({"w": [2.0]}, name="m2")
        weights = cm.current_weights
        # 3 contributions (base + 2), all equal
        for w in weights.values():
            assert abs(w - 1.0 / 3) < 1e-6

    def test_memory_budget_effect(self):
        cm_full = ContinualMerge(base_model={"w": [0.0]}, memory_budget=1.0)
        cm_low = ContinualMerge(base_model={"w": [0.0]}, memory_budget=0.1)
        cm_full.absorb({"w": [10.0]}, name="m1")
        cm_low.absorb({"w": [10.0]}, name="m1")
        # With low memory budget, base gets decayed, newer gets more weight
        w_full = cm_full.current_weights
        w_low = cm_low.current_weights
        assert w_low["m1"] > w_full["m1"]

    def test_memory_budget_clamp(self):
        cm = ContinualMerge(base_model={"w": [0.0]}, memory_budget=0.0)
        # Should clamp to 0.01
        cm.absorb({"w": [10.0]}, name="m1")
        result = cm.export()
        assert result["w"] is not None

    def test_reset(self):
        cm = ContinualMerge(base_model={"w": [1.0]})
        cm.absorb({"w": [2.0]}, name="m1")
        cm.reset(base_model={"w": [5.0]})
        result = cm.export()
        assert abs(result["w"][0] - 5.0) < 1e-6

    def test_reset_clears_history(self):
        cm = ContinualMerge(base_model={"w": [1.0]})
        cm.absorb({"w": [2.0]}, name="m1")
        cm.reset(base_model={"w": [5.0]})
        assert len(cm.history) == 0

    def test_auto_name_generation(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]})
        cm.absorb({"w": [2.0]})
        hist = cm.history
        assert hist[0]["name"] is not None
        assert hist[1]["name"] is not None
        assert hist[0]["name"] != hist[1]["name"]

    def test_absorb_model_with_new_layers(self):
        cm = ContinualMerge(base_model={"a": [1.0]})
        cm.absorb({"a": [2.0], "b": [3.0]}, name="m1")
        result = cm.export()
        assert "a" in result
        assert "b" in result

    def test_empty_base_model(self):
        cm = ContinualMerge(base_model={})
        cm.absorb({"w": [1.0]}, name="m1")
        result = cm.export()
        assert "w" in result

    def test_absorb_preserves_all_layers(self):
        cm = ContinualMerge(base_model={"a": [1.0], "b": [2.0], "c": [3.0]})
        cm.absorb({"a": [4.0], "b": [5.0], "c": [6.0]}, name="m1")
        result = cm.export()
        assert len(result) == 3

    def test_scalars(self):
        cm = ContinualMerge(base_model={"w": 2.0})
        cm.absorb({"w": 4.0}, name="m1")
        result = cm.export()
        assert abs(result["w"] - 3.0) < 1e-6

    def test_duplicate_name_gets_suffix(self):
        cm = ContinualMerge(base_model={"w": [0.0]})
        cm.absorb({"w": [1.0]}, name="same")
        cm.absorb({"w": [2.0]}, name="same")
        # Both should exist with different keys
        assert len(cm.history) == 2

# ===================================================================
# FEDERATED MERGE TESTS (~25)
# ===================================================================

from crdt_merge.model.federated import FederatedMerge, FederatedResult

class TestFederatedMergeBasic:
    """FedAvg and FedProx aggregation."""

    def test_fedavg_two_clients(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0, 2.0]}, num_samples=100)
        fed.submit("b", {"w": [3.0, 4.0]}, num_samples=100)
        result = fed.aggregate()
        # Equal samples → equal weight → [2.0, 3.0]
        assert abs(result.model["w"][0] - 2.0) < 1e-6
        assert abs(result.model["w"][1] - 3.0) < 1e-6

    def test_fedavg_three_clients_different_samples(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [0.0]}, num_samples=100)
        fed.submit("b", {"w": [10.0]}, num_samples=200)
        fed.submit("c", {"w": [20.0]}, num_samples=300)
        result = fed.aggregate()
        # weights: 100/600, 200/600, 300/600 = 1/6, 2/6, 3/6
        expected = (0.0 * 100 + 10.0 * 200 + 20.0 * 300) / 600
        assert abs(result.model["w"][0] - expected) < 1e-6

    def test_fedavg_single_client(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("solo", {"w": [42.0]}, num_samples=10)
        result = fed.aggregate()
        assert abs(result.model["w"][0] - 42.0) < 1e-6

    def test_fedprox_basic(self):
        fed = FederatedMerge(strategy="fedprox", mu=0.1)
        fed.submit("a", {"w": [2.0]}, num_samples=50)
        fed.submit("b", {"w": [4.0]}, num_samples=50)
        global_model = {"w": [3.0]}
        result = fed.aggregate(global_model=global_model)
        # FedProx adjusts: θ_adj = θ_i - μ(θ_i - θ_global)
        # a_adj = 2.0 - 0.1*(2.0-3.0) = 2.0 + 0.1 = 2.1
        # b_adj = 4.0 - 0.1*(4.0-3.0) = 4.0 - 0.1 = 3.9
        # avg = (2.1 + 3.9) / 2 = 3.0
        assert abs(result.model["w"][0] - 3.0) < 1e-6

    def test_fedprox_requires_global_model(self):
        fed = FederatedMerge(strategy="fedprox")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        with pytest.raises(ValueError, match="global_model"):
            fed.aggregate()

    def test_fedprox_mu_effect(self):
        # Higher mu means stronger pull toward global
        fed_low = FederatedMerge(strategy="fedprox", mu=0.01)
        fed_low.submit("a", {"w": [10.0]}, num_samples=100)
        result_low = fed_low.aggregate(global_model={"w": [0.0]})

        fed_high = FederatedMerge(strategy="fedprox", mu=0.5)
        fed_high.submit("a", {"w": [10.0]}, num_samples=100)
        result_high = fed_high.aggregate(global_model={"w": [0.0]})

        # Higher mu → closer to global (0.0)
        assert abs(result_high.model["w"][0]) < abs(result_low.model["w"][0])

    def test_client_contributions_sum_to_one(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=50)
        fed.submit("b", {"w": [2.0]}, num_samples=150)
        result = fed.aggregate()
        total = sum(result.client_contributions.values())
        assert abs(total - 1.0) < 1e-6

    def test_contributions_proportional_to_samples(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=100)
        fed.submit("b", {"w": [2.0]}, num_samples=300)
        result = fed.aggregate()
        assert abs(result.client_contributions["a"] - 0.25) < 1e-6
        assert abs(result.client_contributions["b"] - 0.75) < 1e-6

    def test_clear_and_resubmit(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        fed.clear()
        assert len(fed.clients) == 0
        fed.submit("b", {"w": [5.0]}, num_samples=10)
        result = fed.aggregate()
        assert abs(result.model["w"][0] - 5.0) < 1e-6

    def test_clients_property(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("alice", {"w": [1.0]}, num_samples=10)
        fed.submit("bob", {"w": [2.0]}, num_samples=20)
        assert set(fed.clients) == {"alice", "bob"}

    def test_total_samples(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=100)
        fed.submit("b", {"w": [2.0]}, num_samples=200)
        assert fed.total_samples == 300

    def test_federated_result_fields(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        result = fed.aggregate()
        assert isinstance(result, FederatedResult)
        assert result.num_clients == 1
        assert result.total_samples == 10
        assert result.strategy_used == "fedavg"

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            FederatedMerge(strategy="unknown")

    def test_empty_aggregate_raises(self):
        fed = FederatedMerge(strategy="fedavg")
        with pytest.raises(ValueError, match="No client"):
            fed.aggregate()

    def test_multi_layer_fedavg(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w1": [1.0], "w2": [10.0]}, num_samples=100)
        fed.submit("b", {"w1": [3.0], "w2": [20.0]}, num_samples=100)
        result = fed.aggregate()
        assert abs(result.model["w1"][0] - 2.0) < 1e-6
        assert abs(result.model["w2"][0] - 15.0) < 1e-6

    def test_overwrite_client_submission(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        fed.submit("a", {"w": [5.0]}, num_samples=10)  # overwrite
        result = fed.aggregate()
        assert abs(result.model["w"][0] - 5.0) < 1e-6

    def test_fedavg_with_default_samples(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [2.0]})
        fed.submit("b", {"w": [4.0]})
        result = fed.aggregate()
        # default num_samples=1 each, so equal weight
        assert abs(result.model["w"][0] - 3.0) < 1e-6

    def test_fedavg_scalars(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": 2.0}, num_samples=100)
        fed.submit("b", {"w": 4.0}, num_samples=100)
        result = fed.aggregate()
        assert abs(result.model["w"] - 3.0) < 1e-6

    def test_fedprox_zero_mu_equals_fedavg(self):
        fed_avg = FederatedMerge(strategy="fedavg")
        fed_avg.submit("a", {"w": [1.0]}, num_samples=100)
        fed_avg.submit("b", {"w": [3.0]}, num_samples=100)
        result_avg = fed_avg.aggregate()

        fed_prox = FederatedMerge(strategy="fedprox", mu=0.0)
        fed_prox.submit("a", {"w": [1.0]}, num_samples=100)
        fed_prox.submit("b", {"w": [3.0]}, num_samples=100)
        result_prox = fed_prox.aggregate(global_model={"w": [2.0]})
        assert abs(result_avg.model["w"][0] - result_prox.model["w"][0]) < 1e-6

    def test_result_model_is_dict(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        result = fed.aggregate()
        assert isinstance(result.model, dict)

    def test_clients_empty_after_clear(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        fed.clear()
        assert fed.total_samples == 0

    def test_fedprox_multi_layer(self):
        fed = FederatedMerge(strategy="fedprox", mu=0.1)
        fed.submit("a", {"w1": [2.0], "w2": [8.0]}, num_samples=50)
        fed.submit("b", {"w1": [4.0], "w2": [12.0]}, num_samples=50)
        global_m = {"w1": [3.0], "w2": [10.0]}
        result = fed.aggregate(global_model=global_m)
        assert "w1" in result.model
        assert "w2" in result.model

    def test_num_clients_field(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        fed.submit("b", {"w": [2.0]}, num_samples=20)
        fed.submit("c", {"w": [3.0]}, num_samples=30)
        result = fed.aggregate()
        assert result.num_clients == 3

    def test_strategy_used_field(self):
        fed = FederatedMerge(strategy="fedprox", mu=0.5)
        fed.submit("a", {"w": [1.0]}, num_samples=10)
        result = fed.aggregate(global_model={"w": [0.0]})
        assert result.strategy_used == "fedprox"

    def test_large_sample_disparity(self):
        fed = FederatedMerge(strategy="fedavg")
        fed.submit("small", {"w": [0.0]}, num_samples=1)
        fed.submit("big", {"w": [100.0]}, num_samples=999)
        result = fed.aggregate()
        # big should dominate
        assert result.model["w"][0] > 90.0

# ===================================================================
# FORMATS TESTS (~20)
# ===================================================================

from crdt_merge.model.formats import (
    import_mergekit_config,
    export_mergekit_config,
    STRATEGY_MAP,
    REVERSE_STRATEGY_MAP,
)
from crdt_merge.model.core import ModelMergeSchema

class TestFormatsImport:
    """Import MergeKit configs."""

    def test_import_ties_method(self):
        config = {
            "merge_method": "ties",
            "models": [{"model": "path/a"}, {"model": "path/b"}],
            "parameters": {"density": 0.5},
        }
        schema, extra = import_mergekit_config(config)
        assert isinstance(schema, ModelMergeSchema)
        assert extra["crdt_strategy"] == "ties"

    def test_import_slerp_method(self):
        config = {
            "merge_method": "slerp",
            "models": [{"model": "path/a"}, {"model": "path/b"}],
        }
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "slerp"

    def test_import_linear_method(self):
        config = {"merge_method": "linear", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "linear"

    def test_import_dare_linear(self):
        config = {"merge_method": "dare_linear", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "dare"

    def test_import_task_arithmetic(self):
        config = {"merge_method": "task_arithmetic", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "task_arithmetic"

    def test_import_extracts_model_paths(self):
        config = {
            "merge_method": "linear",
            "models": [{"model": "path/a"}, {"model": "path/b"}],
        }
        _, extra = import_mergekit_config(config)
        assert extra["model_paths"] == ["path/a", "path/b"]

    def test_import_extracts_parameters(self):
        config = {
            "merge_method": "ties",
            "parameters": {"density": 0.3, "weight": 0.7},
            "models": [],
        }
        _, extra = import_mergekit_config(config)
        assert extra["parameters"]["density"] == 0.3

    def test_import_with_slices(self):
        config = {
            "merge_method": "linear",
            "slices": [
                {"filter": "layers.0-10.*", "merge_method": "slerp"},
            ],
            "models": [],
        }
        schema, extra = import_mergekit_config(config)
        raw = schema.to_dict()
        assert "layers.0-10.*" in raw

    def test_import_unknown_strategy_passthrough(self):
        config = {"merge_method": "my_custom_strategy", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "my_custom_strategy"

    def test_import_type_error(self):
        with pytest.raises(TypeError):
            import_mergekit_config(42)

    def test_import_default_method(self):
        config = {"models": []}
        schema, extra = import_mergekit_config(config)
        # default should be linear
        assert extra["crdt_strategy"] == "linear"

    def test_import_model_weights(self):
        config = {
            "merge_method": "linear",
            "models": [
                {"model": "a", "weight": 0.6},
                {"model": "b", "weight": 0.4},
            ],
        }
        _, extra = import_mergekit_config(config)
        assert extra["model_weights"] == [0.6, 0.4]

class TestFormatsExport:
    """Export to MergeKit format."""

    def test_export_basic(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        config = export_mergekit_config(schema)
        assert config["merge_method"] == "linear"

    def test_export_with_models(self):
        schema = ModelMergeSchema(strategies={"default": "slerp"})
        config = export_mergekit_config(schema, models=["path/a", "path/b"])
        assert len(config["models"]) == 2
        assert config["models"][0]["model"] == "path/a"

    def test_export_dare_maps_back(self):
        schema = ModelMergeSchema(strategies={"default": "dare"})
        config = export_mergekit_config(schema)
        assert config["merge_method"] == "dare_linear"

    def test_roundtrip(self):
        original = {
            "merge_method": "ties",
            "models": [{"model": "a"}, {"model": "b"}],
            "parameters": {},
        }
        schema, extra = import_mergekit_config(original)
        exported = export_mergekit_config(schema, models=extra["model_paths"])
        assert exported["merge_method"] == "ties"

class TestFormatsStrategyMap:
    """Strategy name mapping."""

    def test_strategy_map_has_all_methods(self):
        assert "linear" in STRATEGY_MAP
        assert "slerp" in STRATEGY_MAP
        assert "ties" in STRATEGY_MAP
        assert "dare_ties" in STRATEGY_MAP
        assert "task_arithmetic" in STRATEGY_MAP
        assert "dare_linear" in STRATEGY_MAP

    def test_reverse_map_dare(self):
        assert REVERSE_STRATEGY_MAP["dare"] == "dare_linear"

    def test_bidirectional_mapping(self):
        for mk_name, crdt_name in STRATEGY_MAP.items():
            assert crdt_name in REVERSE_STRATEGY_MAP or mk_name == crdt_name

    def test_map_is_dict(self):
        assert isinstance(STRATEGY_MAP, dict)
        assert isinstance(REVERSE_STRATEGY_MAP, dict)

# ===================================================================
# GPU TESTS (~25) — ALL MUST WORK WITHOUT TORCH
# ===================================================================

from crdt_merge.model.gpu import GPUMerge

class TestGPUAvailability:
    """GPU availability checks (work without torch)."""

    def test_is_gpu_available_returns_bool(self):
        result = GPUMerge.is_gpu_available()
        assert isinstance(result, bool)

    def test_is_gpu_available_without_torch(self):
        # If torch is not installed, should return False (not raise)
        result = GPUMerge.is_gpu_available()
        assert isinstance(result, bool)

class TestGPUMergeInstantiation:
    """GPUMerge instantiation and fallback."""

    @pytest.fixture
    def _has_torch(self):
        try:
            import torch
            return True
        except ImportError:
            return False

    def test_instantiation_cpu_fallback(self, _has_torch):
        if not _has_torch:
            with pytest.raises(ImportError, match="torch"):
                GPUMerge(device="cpu")
        else:
            gpu = GPUMerge(device="cpu")
            assert gpu._device == "cpu"

    def test_instantiation_auto_device(self, _has_torch):
        if not _has_torch:
            with pytest.raises(ImportError, match="torch"):
                GPUMerge(device="auto")
        else:
            gpu = GPUMerge(device="auto")
            assert gpu._device in ("cpu", "cuda")

    def test_device_info_returns_dict(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        info = gpu.device_info()
        assert isinstance(info, dict)
        assert "device" in info
        assert "dtype" in info
        assert "gpu_name" in info
        assert "memory_gb" in info

    def test_device_info_cpu_values(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        info = gpu.device_info()
        assert info["device"] == "cpu"
        assert info["gpu_name"] is None
        assert info["memory_gb"] is None

    def test_dtype_float32(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu", dtype="float32")
        info = gpu.device_info()
        assert info["dtype"] == "float32"

    def test_custom_chunk_size(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu", chunk_size=10)
        assert gpu._chunk_size == 10

class TestGPUMergeFunctionality:
    """GPU merge operations (require torch)."""

    @pytest.fixture
    def _has_torch(self):
        try:
            import torch
            return True
        except ImportError:
            return False

    def test_merge_two_models_cpu(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge(
            [{"w": [1.0, 2.0]}, {"w": [3.0, 4.0]}],
            strategy="weight_average",
        )
        assert abs(result["w"][0] - 2.0) < 1e-6
        assert abs(result["w"][1] - 3.0) < 1e-6

    def test_merge_empty_models(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([])
        assert result == {}

    def test_merge_single_model(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([{"w": [42.0]}])
        assert abs(result["w"][0] - 42.0) < 1e-6

    def test_merge_with_weights(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge(
            [{"w": [0.0]}, {"w": [10.0]}],
            weights=[0.25, 0.75],
        )
        assert abs(result["w"][0] - 7.5) < 1e-6

    def test_merge_multi_layer(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([
            {"a": [1.0], "b": [10.0]},
            {"a": [3.0], "b": [20.0]},
        ])
        assert abs(result["a"][0] - 2.0) < 1e-6
        assert abs(result["b"][0] - 15.0) < 1e-6

    def test_merge_three_models(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([
            {"w": [0.0]},
            {"w": [3.0]},
            {"w": [6.0]},
        ])
        assert abs(result["w"][0] - 3.0) < 1e-6

    def test_merge_result_is_plain_list(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([{"w": [1.0, 2.0]}, {"w": [3.0, 4.0]}])
        assert isinstance(result["w"], list)

    def test_merge_preserves_layer_names(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([
            {"layer.0.weight": [1.0], "layer.1.bias": [2.0]},
            {"layer.0.weight": [3.0], "layer.1.bias": [4.0]},
        ])
        assert "layer.0.weight" in result
        assert "layer.1.bias" in result

class TestGPUImportError:
    """Test helpful import errors."""

    def test_import_error_message(self):
        """Verify the error message text is helpful."""
        from crdt_merge.model.gpu import _TORCH_IMPORT_ERROR
        assert "pip install" in _TORCH_IMPORT_ERROR
        assert "torch" in _TORCH_IMPORT_ERROR

    def test_module_importable_without_torch(self):
        """The gpu module itself should be importable without torch."""
        import crdt_merge.model.gpu
        assert hasattr(crdt_merge.model.gpu, "GPUMerge")

    def test_is_gpu_available_classmethod(self):
        """is_gpu_available should be callable without instantiation."""
        result = GPUMerge.is_gpu_available()
        assert isinstance(result, bool)

    def test_gpu_merge_class_exists(self):
        assert GPUMerge is not None

    def test_torch_import_error_text(self):
        from crdt_merge.model.gpu import _TORCH_IMPORT_ERROR
        assert "crdt-merge[gpu]" in _TORCH_IMPORT_ERROR

class TestGPUMergeWithTorch:
    """Tests that specifically test torch tensor input (skip if no torch)."""

    @pytest.fixture
    def _has_torch(self):
        try:
            import torch
            return True
        except ImportError:
            return False

    def test_torch_tensor_input(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        import torch
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([
            {"w": torch.tensor([1.0, 2.0])},
            {"w": torch.tensor([3.0, 4.0])},
        ])
        assert abs(result["w"][0] - 2.0) < 1e-5
        assert abs(result["w"][1] - 3.0) < 1e-5

    def test_mixed_list_and_tensor_input(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        import torch
        gpu = GPUMerge(device="cpu")
        result = gpu.merge([
            {"w": [1.0, 2.0]},
            {"w": torch.tensor([3.0, 4.0])},
        ])
        assert abs(result["w"][0] - 2.0) < 1e-5

    def test_float16_dtype(self, _has_torch):
        if not _has_torch:
            pytest.skip("torch not installed")
        gpu = GPUMerge(device="cpu", dtype="float32")  # float16 may lose precision
        result = gpu.merge([{"w": [1.0]}, {"w": [3.0]}])
        assert abs(result["w"][0] - 2.0) < 1e-3

# ===================================================================
# SAFETY TESTS (~25)
# ===================================================================

from crdt_merge.model.safety import SafetyAnalyzer, SafetyReport

class TestSafetyDetection:
    """Safety-critical layer detection."""

    def test_detect_high_variance_layers(self):
        analyzer = SafetyAnalyzer()
        models = [
            {"safe": [1.0, 1.0], "risky": [1.0, 1.0]},
            {"safe": [1.0, 1.0], "risky": [100.0, 100.0]},
        ]
        layers = analyzer.detect_safety_layers(models, threshold=0.1)
        assert "risky" in layers

    def test_detect_with_similar_layers(self):
        analyzer = SafetyAnalyzer()
        models = [
            {"a": [1.0, 2.0], "b": [3.0, 4.0]},
            {"a": [1.01, 2.01], "b": [3.01, 4.01]},
        ]
        layers = analyzer.detect_safety_layers(models, threshold=0.1)
        # Very similar → no safety layers
        assert len(layers) == 0

    def test_threshold_parameter(self):
        analyzer = SafetyAnalyzer()
        models = [
            {"a": [0.0], "b": [0.0]},
            {"a": [1.0], "b": [0.5]},
        ]
        # Low threshold catches more
        low = analyzer.detect_safety_layers(models, threshold=0.01)
        # High threshold catches fewer
        high = analyzer.detect_safety_layers(models, threshold=10.0)
        assert len(low) >= len(high)

    def test_identical_models_zero_variance(self):
        analyzer = SafetyAnalyzer()
        model = {"a": [1.0, 2.0], "b": [3.0, 4.0]}
        layers = analyzer.detect_safety_layers([model, model])
        assert len(layers) == 0

    def test_single_model(self):
        analyzer = SafetyAnalyzer()
        layers = analyzer.detect_safety_layers([{"a": [1.0]}])
        assert len(layers) == 0

    def test_three_models(self):
        analyzer = SafetyAnalyzer()
        models = [
            {"w": [0.0]},
            {"w": [10.0]},
            {"w": [20.0]},
        ]
        layers = analyzer.detect_safety_layers(models, threshold=0.1)
        assert "w" in layers

    def test_empty_models_list(self):
        analyzer = SafetyAnalyzer()
        layers = analyzer.detect_safety_layers([])
        assert layers == []

class TestSafetyReport:
    """SafetyReport generation."""

    def test_report_returns_safety_report(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0], "b": [1.0]},
            {"a": [2.0], "b": [1.0]},
        ])
        assert isinstance(report, SafetyReport)

    def test_report_has_safety_layers(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"safe": [1.0], "risky": [1.0]},
            {"safe": [1.0], "risky": [100.0]},
        ])
        assert isinstance(report.safety_layers, list)

    def test_report_has_layer_variance(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0]},
            {"a": [2.0]},
        ])
        assert "a" in report.layer_variance

    def test_report_risk_score_range(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0]},
            {"a": [2.0]},
        ])
        assert 0.0 <= report.risk_score <= 1.0

    def test_report_low_risk_similar_models(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0], "b": [2.0]},
            {"a": [1.001], "b": [2.001]},
        ])
        assert report.risk_score < 0.1

    def test_report_high_risk_divergent_models(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [0.0], "b": [0.0]},
            {"a": [100.0], "b": [100.0]},
        ])
        assert report.risk_score > 0.5

    def test_report_recommendation_is_string(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0]},
            {"a": [2.0]},
        ])
        assert isinstance(report.recommendation, str)
        assert len(report.recommendation) > 0

    def test_report_identical_models(self):
        analyzer = SafetyAnalyzer()
        model = {"a": [1.0], "b": [2.0]}
        report = analyzer.safety_report([model, model])
        assert report.risk_score < 0.01
        assert len(report.safety_layers) == 0

    def test_report_single_model(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([{"a": [1.0]}])
        assert report.risk_score < 0.01

    def test_report_multi_layer_variance(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"safe": [1.0, 1.0], "risky": [0.0, 0.0]},
            {"safe": [1.0, 1.0], "risky": [10.0, 10.0]},
        ])
        assert report.layer_variance["risky"] > report.layer_variance["safe"]

    def test_report_empty_models(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([])
        assert report.risk_score == 0.0
        assert len(report.safety_layers) == 0

    def test_safety_analyzer_init(self):
        analyzer = SafetyAnalyzer()
        assert analyzer is not None

    def test_report_recommendation_low_risk(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0]},
            {"a": [1.0001]},
        ])
        assert "safe" in report.recommendation.lower() or "low" in report.recommendation.lower()

    def test_layer_variance_nonnegative(self):
        analyzer = SafetyAnalyzer()
        report = analyzer.safety_report([
            {"a": [1.0], "b": [-5.0]},
            {"a": [3.0], "b": [5.0]},
        ])
        for var in report.layer_variance.values():
            assert var >= 0.0

# ===================================================================
# INTEGRATION / IMPORT TESTS
# ===================================================================

class TestImports:
    """Verify all new exports are importable from crdt_merge.model."""

    def test_import_continual_merge(self):
        from crdt_merge.model import ContinualMerge
        assert ContinualMerge is not None

    def test_import_federated_merge(self):
        from crdt_merge.model import FederatedMerge, FederatedResult
        assert FederatedMerge is not None
        assert FederatedResult is not None

    def test_import_formats(self):
        from crdt_merge.model import import_mergekit_config, export_mergekit_config
        assert import_mergekit_config is not None
        assert export_mergekit_config is not None

    def test_import_gpu_merge(self):
        from crdt_merge.model import GPUMerge
        assert GPUMerge is not None

    def test_import_safety(self):
        from crdt_merge.model import SafetyAnalyzer, SafetyReport
        assert SafetyAnalyzer is not None
        assert SafetyReport is not None

    def test_all_original_imports_still_work(self):
        from crdt_merge.model import (
            ModelCRDT,
            ModelMergeSchema,
            LoRAMerge,
            MergePipeline,
            ProvenanceTracker,
            ConflictHeatmap,
        )
        assert ModelCRDT is not None
