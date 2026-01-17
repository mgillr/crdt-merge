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

"""Tests for Dev 5 modules: LoRA, Pipeline, Provenance, Heatmap.

~140 tests covering all four modules.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

# Ensure basic strategies are registered
import crdt_merge.model.strategies.basic  # noqa: F401

from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
from crdt_merge.model.pipeline import MergePipeline, PipelineResult
from crdt_merge.model.provenance import (
    LayerProvenance,
    ProvenanceSummary,
    ProvenanceTracker,
    compute_conflict_score,
    compute_contribution,
    export_provenance,
)
from crdt_merge.model.heatmap import ConflictHeatmap

# ===========================================================================
# Fixtures / helpers
# ===========================================================================

def _make_adapter(modules, rank=4, in_f=8, out_f=8, seed=0):
    """Create a simple adapter dict."""
    rng = np.random.RandomState(seed)
    adapter = {}
    for mod in modules:
        adapter[mod] = {
            "lora_A": rng.randn(rank, in_f),
            "lora_B": rng.randn(out_f, rank),
        }
    return adapter

def _make_model(layers, size=8, seed=0):
    """Create a simple model state_dict."""
    rng = np.random.RandomState(seed)
    return {layer: rng.randn(size, size) for layer in layers}

# ===========================================================================
# LoRA Tests (~35)
# ===========================================================================

class TestLoRAMergeSchema:
    """Tests for LoRAMergeSchema."""

    def test_default_strategy(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        s = schema.strategy_for("any_module")
        assert s.name == "weight_average"

    def test_specific_module_strategy(self):
        schema = LoRAMergeSchema(strategies={
            "default": "weight_average",
            "q_proj": "linear",
        })
        assert schema.strategy_for("q_proj").name == "linear"
        assert schema.strategy_for("v_proj").name == "weight_average"

    def test_no_default_raises(self):
        schema = LoRAMergeSchema(strategies={"q_proj": "weight_average"})
        with pytest.raises(KeyError):
            schema.strategy_for("unknown_module")

    def test_to_dict(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average", "q_proj": "linear"})
        d = schema.to_dict()
        assert d["default"] == "weight_average"
        assert d["q_proj"] == "linear"

    def test_from_dict(self):
        d = {"default": "weight_average", "q_proj": "linear"}
        schema = LoRAMergeSchema.from_dict(d)
        assert schema.strategy_for("q_proj").name == "linear"
        assert schema.strategy_for("v_proj").name == "weight_average"

    def test_roundtrip(self):
        original = {"default": "weight_average", "q_proj": "linear"}
        schema = LoRAMergeSchema.from_dict(original)
        assert schema.to_dict() == original

    def test_repr(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        r = repr(schema)
        assert "LoRAMergeSchema" in r
        assert "weight_average" in r

    def test_substring_match(self):
        schema = LoRAMergeSchema(strategies={
            "default": "weight_average",
            "attn": "linear",
        })
        assert schema.strategy_for("self_attn.q_proj").name == "linear"

class TestLoRAMerge:
    """Tests for LoRAMerge."""

    def test_basic_two_adapter_merge(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj", "v_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj", "v_proj"], rank=4, seed=2)
        merged = merger.merge_adapters([a1, a2])
        assert "q_proj" in merged
        assert "v_proj" in merged
        assert "lora_A" in merged["q_proj"]
        assert "lora_B" in merged["q_proj"]

    def test_three_adapter_merge_with_weights(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        adapters = [_make_adapter(["q_proj"], rank=4, seed=i) for i in range(3)]
        merged = merger.merge_adapters(adapters, weights=[0.5, 0.3, 0.2])
        assert "q_proj" in merged

    def test_rank_harmonization_max(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        merged = merger.merge_adapters([a1, a2], rank_strategy="max")
        shape = merged["q_proj"]["lora_A"].shape
        assert shape[0] == 4  # max rank

    def test_rank_harmonization_min(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        merged = merger.merge_adapters([a1, a2], rank_strategy="min")
        shape = merged["q_proj"]["lora_A"].shape
        assert shape[0] == 2  # min rank

    def test_rank_harmonization_mean(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, seed=1)
        a2 = _make_adapter(["q_proj"], rank=6, seed=2)
        merged = merger.merge_adapters([a1, a2], rank_strategy="mean")
        shape = merged["q_proj"]["lora_A"].shape
        assert shape[0] == 4  # mean of 2 and 6

    def test_rank_harmonization_adaptive(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, seed=1)
        a2 = _make_adapter(["q_proj"], rank=6, seed=2)
        merged = merger.merge_adapters([a1, a2], weights=[0.8, 0.2], rank_strategy="adaptive")
        shape = merged["q_proj"]["lora_A"].shape
        # weighted: 0.8*2 + 0.2*6 = 2.8 -> round(2.8) = 3
        assert shape[0] == 3

    def test_per_module_strategy(self):
        schema = LoRAMergeSchema(strategies={
            "default": "weight_average",
            "q_proj": "linear",
        })
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj", "v_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj", "v_proj"], rank=4, seed=2)
        merged = merger.merge_adapters([a1, a2])
        assert "q_proj" in merged
        assert "v_proj" in merged

    def test_apply_to_base(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["layer0"], rank=4, in_f=8, out_f=8, seed=1)
        a2 = _make_adapter(["layer0"], rank=4, in_f=8, out_f=8, seed=2)
        merged_adapter = merger.merge_adapters([a1, a2])

        base_model = {"layer0": np.zeros((8, 8))}
        result = merger.apply_to_base(merged_adapter, base_model)
        # Should be base + lora_B @ lora_A
        expected = merged_adapter["layer0"]["lora_B"] @ merged_adapter["layer0"]["lora_A"]
        np.testing.assert_allclose(result["layer0"], expected, atol=1e-6)

    def test_apply_to_base_preserves_other_layers(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        merged_adapter = _make_adapter(["layer0"], rank=4, in_f=8, out_f=8, seed=1)
        base_model = {"layer0": np.ones((8, 8)), "layer1": np.ones((8, 8))}
        result = merger.apply_to_base(merged_adapter, base_model)
        assert "layer1" in result
        np.testing.assert_array_equal(result["layer1"], np.ones((8, 8)))

    def test_provenance_tracking(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        merged, prov = merger.merge_adapters_with_provenance([a1, a2])
        assert "q_proj" in prov
        assert "contribution_map" in prov["q_proj"]
        assert "dominant_source" in prov["q_proj"]

    def test_provenance_contribution_sum(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        adapters = [_make_adapter(["q_proj"], rank=4, seed=i) for i in range(3)]
        _, prov = merger.merge_adapters_with_provenance(adapters)
        total = sum(prov["q_proj"]["contribution_map"].values())
        assert abs(total - 1.0) < 1e-6

    def test_empty_adapters(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        merged = merger.merge_adapters([])
        assert merged == {}

    def test_single_adapter(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        merged = merger.merge_adapters([a1])
        assert "q_proj" in merged
        np.testing.assert_array_equal(
            merged["q_proj"]["lora_A"], a1["q_proj"]["lora_A"]
        )

    def test_mismatched_module_names_union(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj", "k_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj", "v_proj"], rank=4, seed=2)
        merged = merger.merge_adapters([a1, a2])
        # Union of module names
        assert "q_proj" in merged
        assert "k_proj" in merged
        assert "v_proj" in merged

    def test_merge_result_shapes_match(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, in_f=16, out_f=16, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, in_f=16, out_f=16, seed=2)
        merged = merger.merge_adapters([a1, a2])
        assert merged["q_proj"]["lora_A"].shape == (4, 16)
        assert merged["q_proj"]["lora_B"].shape == (16, 4)

    def test_uniform_weights(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        # No weights = uniform
        m1 = merger.merge_adapters([a1, a2])
        m2 = merger.merge_adapters([a1, a2], weights=[1.0, 1.0])
        np.testing.assert_allclose(
            m1["q_proj"]["lora_A"], m2["q_proj"]["lora_A"], atol=1e-6
        )

    def test_lora_schema_to_dict_from_dict_roundtrip(self):
        d = {"default": "weight_average", "q_proj": "linear", "v_proj": "slerp"}
        schema = LoRAMergeSchema.from_dict(d)
        assert schema.to_dict() == d

    def test_same_rank_no_harmonization_effect(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        for strat in ("max", "min", "mean"):
            merged = merger.merge_adapters([a1, a2], rank_strategy=strat)
            assert merged["q_proj"]["lora_A"].shape[0] == 4

    def test_weighted_merge_differs_from_uniform(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        m_uniform = merger.merge_adapters([a1, a2])
        m_weighted = merger.merge_adapters([a1, a2], weights=[0.9, 0.1])
        # They should generally differ
        assert not np.allclose(
            m_uniform["q_proj"]["lora_A"], m_weighted["q_proj"]["lora_A"]
        )

    def test_provenance_single_adapter(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        merged, prov = merger.merge_adapters_with_provenance([a1])
        assert prov["q_proj"]["num_sources"] == 1
        assert prov["q_proj"]["contribution_map"][0] == 1.0

    def test_provenance_empty_adapters(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        merged, prov = merger.merge_adapters_with_provenance([])
        assert merged == {}
        assert prov == {}

    def test_apply_to_base_weight_key(self):
        """apply_to_base also checks module_name.weight key."""
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        adapter = _make_adapter(["attn"], rank=4, in_f=8, out_f=8, seed=1)
        base_model = {"attn.weight": np.zeros((8, 8))}
        result = merger.apply_to_base(adapter, base_model)
        assert "attn.weight" in result
        expected = adapter["attn"]["lora_B"] @ adapter["attn"]["lora_A"]
        np.testing.assert_allclose(result["attn.weight"], expected, atol=1e-6)

    def test_rank_strategy_unknown(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        with pytest.raises(ValueError, match="Unknown rank_strategy"):
            merger.merge_adapters([a1, a2], rank_strategy="invalid")

# ===========================================================================
# Pipeline Tests (~30)
# ===========================================================================

class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_creation(self):
        pr = PipelineResult(
            final_model={"a": 1},
            stage_results={"s1": {"a": 1}},
            pipeline_provenance={"a": {"stage": "s1"}},
            execution_order=["s1"],
        )
        assert pr.final_model == {"a": 1}
        assert pr.execution_order == ["s1"]

class TestMergePipeline:
    """Tests for MergePipeline."""

    def test_simple_two_stage_pipeline(self):
        m_a = _make_model(["layer0", "layer1"], seed=1)
        m_b = _make_model(["layer0", "layer1"], seed=2)
        m_c = _make_model(["layer0", "layer1"], seed=3)

        pipeline = MergePipeline(stages=[
            {"name": "stage1", "strategy": "weight_average", "models": [m_a, m_b]},
            {"name": "stage2", "strategy": "weight_average", "models": ["$stage1", m_c]},
        ])
        result = pipeline.execute()
        assert "layer0" in result.final_model
        assert "layer1" in result.final_model
        assert result.execution_order == ["stage1", "stage2"]

    def test_three_stage_with_references(self):
        models = [_make_model(["layer0"], seed=i) for i in range(4)]
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [models[0], models[1]]},
            {"name": "s2", "strategy": "weight_average", "models": [models[2], models[3]]},
            {"name": "s3", "strategy": "weight_average", "models": ["$s1", "$s2"]},
        ])
        result = pipeline.execute()
        assert "s1" in result.stage_results
        assert "s2" in result.stage_results
        assert "s3" in result.stage_results
        assert result.execution_order == ["s1", "s2", "s3"]

    def test_cycle_detection(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": ["$s2"]},
            {"name": "s2", "strategy": "weight_average", "models": ["$s1"]},
        ])
        errors = pipeline.validate()
        assert any("Cycle" in e or "cycle" in e.lower() for e in errors)

    def test_self_reference_cycle(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": ["$s1"]},
        ])
        errors = pipeline.validate()
        assert any("Cycle" in e or "cycle" in e.lower() for e in errors)

    def test_missing_reference(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": ["$nonexistent"]},
        ])
        errors = pipeline.validate()
        assert any("nonexistent" in e for e in errors)

    def test_execute_raises_on_invalid(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": ["$nonexistent"]},
        ])
        with pytest.raises(ValueError, match="validation failed"):
            pipeline.execute()

    def test_final_model_is_last_stage(self):
        m_a = _make_model(["layer0"], seed=1)
        m_b = _make_model(["layer0"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a, m_b]},
        ])
        result = pipeline.execute()
        assert result.final_model == result.stage_results["s1"]

    def test_pipeline_provenance_tracks_stages(self):
        m_a = _make_model(["layer0", "layer1"], seed=1)
        m_b = _make_model(["layer0", "layer1"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a, m_b]},
        ])
        result = pipeline.execute()
        assert "layer0" in result.pipeline_provenance
        assert result.pipeline_provenance["layer0"]["produced_by_stage"] == "s1"

    def test_to_dict(self):
        m = _make_model(["l0"], seed=1)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m, "$s0"]},
        ])
        d = pipeline.to_dict()
        assert "stages" in d
        assert d["stages"][0]["name"] == "s1"
        assert "<state_dict>" in d["stages"][0]["models"]
        assert "$s0" in d["stages"][0]["models"]

    def test_from_dict(self):
        d = {
            "stages": [
                {"name": "s1", "strategy": "weight_average", "models": ["<state_dict>", "$s0"]},
            ]
        }
        pipeline = MergePipeline.from_dict(d)
        assert len(pipeline._stages) == 1

    def test_to_dict_from_dict_roundtrip(self):
        d = {
            "stages": [
                {"name": "s1", "strategy": "weight_average", "models": ["<state_dict>", "$s0"]},
                {"name": "s2", "strategy": "linear", "models": ["$s1"]},
            ]
        }
        pipeline = MergePipeline.from_dict(d)
        d2 = pipeline.to_dict()
        assert d2["stages"][0]["name"] == "s1"
        assert d2["stages"][1]["name"] == "s2"

    def test_duplicate_stage_names(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": []},
            {"name": "s1", "strategy": "weight_average", "models": []},
        ])
        errors = pipeline.validate()
        assert any("Duplicate" in e or "duplicate" in e.lower() for e in errors)

    def test_stage_with_weights(self):
        m_a = _make_model(["layer0"], seed=1)
        m_b = _make_model(["layer0"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a, m_b], "weights": [0.7, 0.3]},
        ])
        result = pipeline.execute()
        assert "layer0" in result.final_model

    def test_single_model_stage(self):
        m_a = _make_model(["layer0"], seed=1)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a]},
        ])
        result = pipeline.execute()
        np.testing.assert_array_equal(result.final_model["layer0"], m_a["layer0"])

    def test_empty_pipeline(self):
        pipeline = MergePipeline(stages=[])
        errors = pipeline.validate()
        # No stages = valid but empty
        assert errors == []

    def test_stage_with_base_reference(self):
        base = _make_model(["layer0"], seed=0)
        m_a = _make_model(["layer0"], seed=1)
        m_b = _make_model(["layer0"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a, m_b], "base": base},
        ])
        result = pipeline.execute()
        assert "layer0" in result.final_model

    def test_execution_order_respects_deps(self):
        m = _make_model(["l"], seed=0)
        pipeline = MergePipeline(stages=[
            {"name": "s2", "strategy": "weight_average", "models": ["$s1", m]},
            {"name": "s1", "strategy": "weight_average", "models": [m, m]},
        ])
        result = pipeline.execute()
        # s1 must be executed before s2
        idx_s1 = result.execution_order.index("s1")
        idx_s2 = result.execution_order.index("s2")
        assert idx_s1 < idx_s2

    def test_complex_dag(self):
        """A diamond DAG: s1,s2 -> s3,s4 -> s5"""
        m = _make_model(["l"], seed=0)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m, m]},
            {"name": "s2", "strategy": "weight_average", "models": [m, m]},
            {"name": "s3", "strategy": "weight_average", "models": ["$s1", "$s2"]},
            {"name": "s4", "strategy": "weight_average", "models": ["$s1", "$s2"]},
            {"name": "s5", "strategy": "weight_average", "models": ["$s3", "$s4"]},
        ])
        result = pipeline.execute()
        order = result.execution_order
        assert order.index("s1") < order.index("s3")
        assert order.index("s2") < order.index("s3")
        assert order.index("s3") < order.index("s5")
        assert order.index("s4") < order.index("s5")

    def test_provenance_strategy_recorded(self):
        m_a = _make_model(["layer0"], seed=1)
        m_b = _make_model(["layer0"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "linear", "models": [m_a, m_b]},
        ])
        result = pipeline.execute()
        assert result.pipeline_provenance["layer0"]["strategy"] == "linear"

    def test_missing_name_field(self):
        pipeline = MergePipeline(stages=[
            {"strategy": "weight_average", "models": []},
        ])
        errors = pipeline.validate()
        assert any("name" in e.lower() or "missing" in e.lower() for e in errors)

# ===========================================================================
# Provenance Tests (~40)
# ===========================================================================

class TestComputeContribution:
    """Tests for compute_contribution."""

    def test_uniform_weights(self):
        tensors = [np.ones(4), np.ones(4)]
        contrib = compute_contribution(tensors, None, "weight_average")
        assert abs(contrib[0] - 0.5) < 1e-6
        assert abs(contrib[1] - 0.5) < 1e-6

    def test_custom_weights(self):
        tensors = [np.ones(4), np.ones(4)]
        contrib = compute_contribution(tensors, [0.7, 0.3], "weight_average")
        assert abs(contrib[0] - 0.7) < 1e-6
        assert abs(contrib[1] - 0.3) < 1e-6

    def test_empty_tensors(self):
        contrib = compute_contribution([], None, "weight_average")
        assert contrib == {}

    def test_single_tensor(self):
        contrib = compute_contribution([np.ones(4)], None, "weight_average")
        assert abs(contrib[0] - 1.0) < 1e-6

    def test_three_models(self):
        tensors = [np.ones(4)] * 3
        contrib = compute_contribution(tensors, None, "weight_average")
        for i in range(3):
            assert abs(contrib[i] - 1.0 / 3) < 1e-6

class TestComputeConflictScore:
    """Tests for compute_conflict_score."""

    def test_identical_tensors_zero_conflict(self):
        t = np.ones(10)
        score = compute_conflict_score([t, t.copy(), t.copy()])
        assert score == 0.0

    def test_opposing_tensors_high_conflict(self):
        t1 = np.ones(100) * 5
        t2 = -np.ones(100) * 5
        score = compute_conflict_score([t1, t2])
        assert score > 0.5

    def test_single_tensor_zero_conflict(self):
        score = compute_conflict_score([np.ones(10)])
        assert score == 0.0

    def test_score_range(self):
        rng = np.random.RandomState(42)
        for _ in range(20):
            tensors = [rng.randn(50) for _ in range(3)]
            score = compute_conflict_score(tensors)
            assert 0.0 <= score <= 1.0

    def test_empty_list(self):
        score = compute_conflict_score([])
        assert score == 0.0

class TestLayerProvenance:
    """Tests for LayerProvenance dataclass."""

    def test_creation(self):
        lp = LayerProvenance(
            layer_name="layer0",
            strategy_used="weight_average",
            dominant_source=0,
            contribution_map={0: 0.6, 1: 0.4},
            conflict_score=0.3,
        )
        assert lp.layer_name == "layer0"
        assert lp.dominant_source == 0
        assert lp.metadata == {}

    def test_with_metadata(self):
        lp = LayerProvenance(
            layer_name="layer0",
            strategy_used="ties",
            dominant_source=1,
            contribution_map={0: 0.3, 1: 0.7},
            conflict_score=0.5,
            metadata={"trimmed_fraction": 0.2},
        )
        assert lp.metadata["trimmed_fraction"] == 0.2

class TestProvenanceTracker:
    """Tests for ProvenanceTracker."""

    def test_track_single_merge(self):
        tracker = ProvenanceTracker()
        tensors = [np.ones(10), np.ones(10) * 2]
        prov = tracker.track_merge("layer0", tensors, None, "weight_average")
        assert isinstance(prov, LayerProvenance)
        assert prov.layer_name == "layer0"
        assert prov.strategy_used == "weight_average"

    def test_track_multiple_layers(self):
        tracker = ProvenanceTracker()
        for i in range(5):
            tensors = [np.ones(10) * (i + 1), np.ones(10) * (i + 2)]
            tracker.track_merge(f"layer{i}", tensors, None, "weight_average")
        summary = tracker.summary()
        assert len(summary.per_layer) == 5

    def test_contribution_map_sums_to_one(self):
        tracker = ProvenanceTracker()
        tensors = [np.ones(10), np.ones(10) * 2, np.ones(10) * 3]
        prov = tracker.track_merge("layer0", tensors, None, "weight_average")
        total = sum(prov.contribution_map.values())
        assert abs(total - 1.0) < 1e-6

    def test_conflict_score_in_range(self):
        tracker = ProvenanceTracker()
        rng = np.random.RandomState(42)
        for i in range(10):
            tensors = [rng.randn(20) for _ in range(3)]
            prov = tracker.track_merge(f"layer{i}", tensors, None, "weight_average")
            assert 0.0 <= prov.conflict_score <= 1.0

    def test_dominant_source_correct(self):
        tracker = ProvenanceTracker()
        tensors = [np.ones(10), np.ones(10)]
        prov = tracker.track_merge("layer0", tensors, [0.8, 0.2], "weight_average")
        assert prov.dominant_source == 0

    def test_summary_aggregation(self):
        tracker = ProvenanceTracker()
        # Low conflict
        tracker.track_merge("low", [np.ones(10), np.ones(10)], None, "weight_average")
        # High conflict
        tracker.track_merge("high", [np.ones(100) * 5, -np.ones(100) * 5], None, "weight_average")
        summary = tracker.summary()
        assert 0.0 <= summary.overall_conflict <= 1.0
        assert summary.layer_conflict_ranking[0] == "high"

    def test_summary_empty_tracker(self):
        tracker = ProvenanceTracker()
        summary = tracker.summary()
        assert summary.overall_conflict == 0.0
        assert summary.per_layer == {}

    def test_summary_dominant_model(self):
        tracker = ProvenanceTracker()
        for i in range(5):
            tensors = [np.ones(10), np.ones(10)]
            tracker.track_merge(f"layer{i}", tensors, [0.8, 0.2], "weight_average")
        summary = tracker.summary()
        assert summary.dominant_model == 0

    def test_summary_layer_conflict_ranking_order(self):
        tracker = ProvenanceTracker()
        # Create layers with known conflict ordering
        tracker.track_merge("zero_conflict", [np.ones(10), np.ones(10)], None, "weight_average")
        tracker.track_merge("some_conflict", [np.ones(100) * 2, -np.ones(100) * 2], None, "weight_average")
        summary = tracker.summary()
        # "some_conflict" should be ranked first (higher conflict)
        assert summary.layer_conflict_ranking[0] == "some_conflict"

    def test_track_with_custom_weights(self):
        tracker = ProvenanceTracker()
        tensors = [np.ones(10), np.ones(10) * 2]
        prov = tracker.track_merge("l0", tensors, [0.3, 0.7], "weight_average")
        assert abs(prov.contribution_map[0] - 0.3) < 1e-6
        assert abs(prov.contribution_map[1] - 0.7) < 1e-6

    def test_track_preserves_layer_order(self):
        tracker = ProvenanceTracker()
        names = ["alpha", "beta", "gamma"]
        for n in names:
            tracker.track_merge(n, [np.ones(10)], None, "weight_average")
        summary = tracker.summary()
        assert list(summary.per_layer.keys()) == names

class TestExportProvenance:
    """Tests for export_provenance."""

    def test_export_json(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("layer0", [np.ones(10), np.ones(10) * 2], None, "weight_average")
        tracker.track_merge("layer1", [np.ones(10), np.ones(10) * 3], None, "linear")
        summary = tracker.summary()
        json_str = export_provenance(summary, format="json")
        data = json.loads(json_str)
        assert "overall_conflict" in data
        assert "layers" in data
        assert "layer0" in data["layers"]
        assert "layer1" in data["layers"]

    def test_export_csv(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("layer0", [np.ones(10), np.ones(10) * 2], None, "weight_average")
        summary = tracker.summary()
        csv_str = export_provenance(summary, format="csv")
        lines = csv_str.strip().split("\n")
        assert lines[0] == "layer_name,strategy_used,dominant_source,conflict_score"
        assert "layer0" in lines[1]

    def test_export_json_roundtrip(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10)], None, "weight_average")
        summary = tracker.summary()
        json_str = export_provenance(summary, format="json")
        data = json.loads(json_str)
        assert data["dominant_model"] == summary.dominant_model

    def test_export_invalid_format(self):
        tracker = ProvenanceTracker()
        summary = tracker.summary()
        with pytest.raises(ValueError, match="Unsupported format"):
            export_provenance(summary, format="xml")

    def test_export_csv_multiple_layers(self):
        tracker = ProvenanceTracker()
        for i in range(5):
            tracker.track_merge(f"layer{i}", [np.ones(10), np.ones(10) * (i + 1)], None, "weight_average")
        summary = tracker.summary()
        csv_str = export_provenance(summary, format="csv")
        lines = csv_str.strip().split("\n")
        assert len(lines) == 6  # header + 5 data rows

    def test_export_json_conflict_ranking(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("low", [np.ones(10), np.ones(10)], None, "weight_average")
        tracker.track_merge("high", [np.ones(100) * 5, -np.ones(100) * 5], None, "weight_average")
        summary = tracker.summary()
        data = json.loads(export_provenance(summary, format="json"))
        assert data["layer_conflict_ranking"][0] == "high"

# ===========================================================================
# Heatmap Tests (~35)
# ===========================================================================

class TestConflictHeatmapFromMerge:
    """Tests for ConflictHeatmap.from_merge."""

    def test_basic_construction(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10) * 2], None, "weight_average")
        tracker.track_merge("l1", [np.ones(10), np.ones(10) * 3], None, "weight_average")
        summary = tracker.summary()
        hm = ConflictHeatmap.from_merge(summary)
        assert hm.num_layers == 2
        assert hm.num_models == 2

    def test_layer_conflicts_keys(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("alpha", [np.ones(10), np.ones(10) * 2], None, "weight_average")
        tracker.track_merge("beta", [np.ones(10), np.ones(10) * 3], None, "weight_average")
        summary = tracker.summary()
        hm = ConflictHeatmap.from_merge(summary)
        assert set(hm.layer_conflicts.keys()) == {"alpha", "beta"}

    def test_overall_conflict(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10)], None, "weight_average")
        summary = tracker.summary()
        hm = ConflictHeatmap.from_merge(summary)
        assert hm.overall_conflict == summary.overall_conflict

    def test_model_contributions(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10)], [0.7, 0.3], "weight_average")
        summary = tracker.summary()
        hm = ConflictHeatmap.from_merge(summary)
        contrib = hm.model_contributions
        assert "l0" in contrib
        assert abs(contrib["l0"][0] - 0.7) < 1e-6

    def test_empty_summary(self):
        summary = ProvenanceSummary(
            overall_conflict=0.0,
            dominant_model=0,
            layer_conflict_ranking=[],
            per_layer={},
        )
        hm = ConflictHeatmap.from_merge(summary)
        assert hm.num_layers == 0
        assert hm.overall_conflict == 0.0

class TestConflictHeatmapFromModels:
    """Tests for ConflictHeatmap.from_models."""

    def test_basic_construction(self):
        m1 = _make_model(["l0", "l1"], seed=1)
        m2 = _make_model(["l0", "l1"], seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        assert hm.num_layers == 2
        assert hm.num_models == 2

    def test_identical_models_low_conflict(self):
        m = _make_model(["l0"], seed=1)
        hm = ConflictHeatmap.from_models([m, m.copy()])
        assert hm.overall_conflict < 0.01

    def test_different_models_nonzero_conflict(self):
        m1 = {"l0": np.ones(100) * 5}
        m2 = {"l0": -np.ones(100) * 5}
        hm = ConflictHeatmap.from_models([m1, m2])
        assert hm.overall_conflict > 0.0

    def test_with_base_model(self):
        base = {"l0": np.zeros(10)}
        m1 = {"l0": np.ones(10)}
        m2 = {"l0": np.ones(10) * 2}
        hm = ConflictHeatmap.from_models([m1, m2], base=base)
        assert hm.num_layers == 1

    def test_empty_models(self):
        hm = ConflictHeatmap.from_models([])
        assert hm.num_layers == 0
        assert hm.overall_conflict == 0.0

    def test_layer_conflicts_keys_match(self):
        layers = ["attn.weight", "mlp.weight", "norm.weight"]
        m1 = _make_model(layers, seed=1)
        m2 = _make_model(layers, seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        assert set(hm.layer_conflicts.keys()) == set(layers)

    def test_three_models(self):
        models = [_make_model(["l0"], seed=i) for i in range(3)]
        hm = ConflictHeatmap.from_models(models)
        assert hm.num_models == 3

class TestConflictHeatmapMethods:
    """Tests for ConflictHeatmap methods."""

    def _build_heatmap(self, n_layers=5):
        tracker = ProvenanceTracker()
        rng = np.random.RandomState(42)
        for i in range(n_layers):
            t1 = rng.randn(50) * (i + 1)
            t2 = rng.randn(50) * (i + 1)
            tracker.track_merge(f"layer{i}", [t1, t2], None, "weight_average")
        summary = tracker.summary()
        return ConflictHeatmap.from_merge(summary)

    def test_most_conflicted_layers(self):
        hm = self._build_heatmap(10)
        most = hm.most_conflicted_layers(3)
        assert len(most) == 3
        # Sorted descending
        assert most[0][1] >= most[1][1] >= most[2][1]

    def test_least_conflicted_layers(self):
        hm = self._build_heatmap(10)
        least = hm.least_conflicted_layers(3)
        assert len(least) == 3
        # Sorted ascending
        assert least[0][1] <= least[1][1] <= least[2][1]

    def test_most_conflicted_more_than_available(self):
        hm = self._build_heatmap(3)
        most = hm.most_conflicted_layers(10)
        assert len(most) == 3

    def test_parameter_detail(self):
        m1 = {"l0": np.array([1.0, 2.0, -3.0, 4.0])}
        m2 = {"l0": np.array([1.0, -2.0, -3.0, -4.0])}
        hm = ConflictHeatmap.from_models([m1, m2])
        detail = hm.parameter_detail("l0")
        assert len(detail.variance_map) == 4
        assert 0.0 <= detail.sign_agreement <= 1.0
        assert detail.magnitude_spread >= 0.0

    def test_parameter_detail_sign_agreement_range(self):
        rng = np.random.RandomState(42)
        m1 = {"l0": rng.randn(100)}
        m2 = {"l0": rng.randn(100)}
        hm = ConflictHeatmap.from_models([m1, m2])
        detail = hm.parameter_detail("l0")
        assert 0.0 <= detail.sign_agreement <= 1.0

    def test_parameter_detail_perfect_agreement(self):
        t = np.ones(10)
        hm = ConflictHeatmap.from_models([{"l0": t}, {"l0": t.copy()}])
        detail = hm.parameter_detail("l0")
        assert detail.sign_agreement == 1.0

    def test_parameter_detail_unknown_layer(self):
        hm = ConflictHeatmap.from_models([{"l0": np.ones(10)}])
        with pytest.raises(KeyError):
            hm.parameter_detail("nonexistent")

    def test_to_json(self):
        hm = self._build_heatmap(3)
        json_str = hm.to_json()
        data = json.loads(json_str)
        assert "num_layers" in data
        assert "layer_conflicts" in data
        assert data["num_layers"] == 3

    def test_to_json_write_file(self, tmp_path):
        hm = self._build_heatmap(3)
        path = str(tmp_path / "heatmap.json")
        hm.to_json(path)
        with open(path) as f:
            data = json.load(f)
        assert data["num_layers"] == 3

    def test_to_csv(self):
        hm = self._build_heatmap(3)
        csv_str = hm.to_csv()
        lines = csv_str.strip().split("\n")
        assert lines[0] == "layer_name,conflict_score"
        assert len(lines) == 4  # header + 3 rows

    def test_to_csv_write_file(self, tmp_path):
        hm = self._build_heatmap(3)
        path = str(tmp_path / "heatmap.csv")
        hm.to_csv(path)
        with open(path) as f:
            content = f.read()
        assert "layer_name" in content

    def test_to_dict(self):
        hm = self._build_heatmap(3)
        d = hm.to_dict()
        assert d["num_layers"] == 3
        assert d["num_models"] == 2
        assert "layer_conflicts" in d
        assert "model_contributions" in d

    def test_to_dict_roundtrip(self):
        hm = self._build_heatmap(3)
        d = hm.to_dict()
        # Reconstruct
        hm2 = ConflictHeatmap(
            layer_conflicts=d["layer_conflicts"],
            model_contributions={
                k: {int(ki): vi for ki, vi in v.items()}
                for k, v in d["model_contributions"].items()
            },
            num_models=d["num_models"],
        )
        assert hm2.num_layers == hm.num_layers
        assert abs(hm2.overall_conflict - hm.overall_conflict) < 1e-6

    def test_conflict_scores_nonnegative(self):
        hm = self._build_heatmap(10)
        for _, score in hm.layer_conflicts.items():
            assert score >= 0.0

    def test_single_model_heatmap(self):
        """Single model → from_models works but conflict should be 0."""
        m = _make_model(["l0", "l1"], seed=1)
        hm = ConflictHeatmap.from_models([m])
        # Single model — no conflict possible
        assert hm.num_models == 1

    def test_large_layer_count(self):
        layers = [f"layer{i}" for i in range(50)]
        m1 = _make_model(layers, seed=1)
        m2 = _make_model(layers, seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        assert hm.num_layers == 50
        most = hm.most_conflicted_layers(5)
        assert len(most) == 5

# ===========================================================================
# Additional LoRA Tests (bring total ~35)
# ===========================================================================

class TestLoRAMergeExtra:
    """Additional LoRA tests."""

    def test_multiple_modules_different_ranks(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        rng = np.random.RandomState(10)
        a1 = {
            "q_proj": {"lora_A": rng.randn(2, 8), "lora_B": rng.randn(8, 2)},
            "v_proj": {"lora_A": rng.randn(4, 8), "lora_B": rng.randn(8, 4)},
        }
        a2 = {
            "q_proj": {"lora_A": rng.randn(4, 8), "lora_B": rng.randn(8, 4)},
            "v_proj": {"lora_A": rng.randn(2, 8), "lora_B": rng.randn(8, 2)},
        }
        merged = merger.merge_adapters([a1, a2], rank_strategy="max")
        assert merged["q_proj"]["lora_A"].shape[0] == 4
        assert merged["v_proj"]["lora_A"].shape[0] == 4

    def test_apply_to_base_new_module(self):
        """Module not in base gets stored as new key."""
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        adapter = _make_adapter(["new_layer"], rank=4, in_f=8, out_f=8, seed=1)
        base_model = {"other_layer": np.zeros((8, 8))}
        result = merger.apply_to_base(adapter, base_model)
        assert "new_layer" in result
        assert "other_layer" in result

    def test_lora_merge_deterministic(self):
        """Same inputs → same output."""
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        m1 = merger.merge_adapters([a1, a2])
        m2 = merger.merge_adapters([a1, a2])
        np.testing.assert_array_equal(m1["q_proj"]["lora_A"], m2["q_proj"]["lora_A"])

    def test_merge_five_adapters(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        adapters = [_make_adapter(["q_proj"], rank=4, seed=i) for i in range(5)]
        merged = merger.merge_adapters(adapters)
        assert "q_proj" in merged

    def test_rank_harmonization_lora_b_shape(self):
        """lora_B rank dimension also gets harmonized."""
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=2, in_f=8, out_f=8, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, in_f=8, out_f=8, seed=2)
        merged = merger.merge_adapters([a1, a2], rank_strategy="max")
        assert merged["q_proj"]["lora_B"].shape == (8, 4)

    def test_provenance_weighted_dominant(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        _, prov = merger.merge_adapters_with_provenance([a1, a2], weights=[0.1, 0.9])
        assert prov["q_proj"]["dominant_source"] == 1

    def test_provenance_strategy_name(self):
        schema = LoRAMergeSchema(strategies={"default": "linear"})
        merger = LoRAMerge(schema)
        a1 = _make_adapter(["q_proj"], rank=4, seed=1)
        a2 = _make_adapter(["q_proj"], rank=4, seed=2)
        _, prov = merger.merge_adapters_with_provenance([a1, a2])
        assert prov["q_proj"]["strategy"] == "linear"

# ===========================================================================
# Additional Pipeline Tests (bring total ~30)
# ===========================================================================

class TestMergePipelineExtra:
    """Additional pipeline tests."""

    def test_no_models_stage(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": []},
        ])
        result = pipeline.execute()
        assert result.final_model == {}

    def test_pipeline_preserves_all_layers(self):
        m_a = _make_model(["l0", "l1", "l2"], seed=1)
        m_b = _make_model(["l0", "l1", "l2"], seed=2)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m_a, m_b]},
        ])
        result = pipeline.execute()
        assert set(result.final_model.keys()) == {"l0", "l1", "l2"}

    def test_stage_results_all_present(self):
        m = _make_model(["l0"], seed=0)
        pipeline = MergePipeline(stages=[
            {"name": "a", "strategy": "weight_average", "models": [m, m]},
            {"name": "b", "strategy": "weight_average", "models": [m, m]},
            {"name": "c", "strategy": "weight_average", "models": ["$a", "$b"]},
        ])
        result = pipeline.execute()
        assert set(result.stage_results.keys()) == {"a", "b", "c"}

    def test_validate_valid_pipeline(self):
        m = _make_model(["l0"], seed=0)
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [m, m]},
            {"name": "s2", "strategy": "weight_average", "models": ["$s1", m]},
        ])
        errors = pipeline.validate()
        assert errors == []

    def test_base_as_stage_reference(self):
        m = _make_model(["l0"], seed=0)
        pipeline = MergePipeline(stages=[
            {"name": "base_stage", "strategy": "weight_average", "models": [m, m]},
            {"name": "s1", "strategy": "weight_average", "models": [m, m], "base": "$base_stage"},
        ])
        result = pipeline.execute()
        assert "l0" in result.final_model

    def test_base_reference_unknown_error(self):
        pipeline = MergePipeline(stages=[
            {"name": "s1", "strategy": "weight_average", "models": [], "base": "$unknown"},
        ])
        errors = pipeline.validate()
        assert any("unknown" in e for e in errors)

# ===========================================================================
# Additional Provenance Tests (bring total ~40)
# ===========================================================================

class TestProvenanceExtra:
    """Additional provenance tests."""

    def test_conflict_score_symmetry(self):
        """compute_conflict_score(a,b) == compute_conflict_score(b,a)"""
        rng = np.random.RandomState(42)
        a = rng.randn(50)
        b = rng.randn(50)
        s1 = compute_conflict_score([a, b])
        s2 = compute_conflict_score([b, a])
        assert abs(s1 - s2) < 1e-10

    def test_conflict_three_identical(self):
        t = np.ones(20) * 3
        score = compute_conflict_score([t, t, t])
        assert score == 0.0

    def test_tracker_overwrite_layer(self):
        """Tracking same layer name twice overwrites."""
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10)], None, "weight_average")
        tracker.track_merge("l0", [np.ones(10), np.ones(10) * 5], None, "linear")
        summary = tracker.summary()
        assert len(summary.per_layer) == 1
        assert summary.per_layer["l0"].strategy_used == "linear"

    def test_export_json_has_all_fields(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("l0", [np.ones(10), np.ones(10) * 2], [0.6, 0.4], "weight_average")
        summary = tracker.summary()
        data = json.loads(export_provenance(summary))
        layer_data = data["layers"]["l0"]
        assert "strategy_used" in layer_data
        assert "dominant_source" in layer_data
        assert "contribution_map" in layer_data
        assert "conflict_score" in layer_data

    def test_contribution_with_extreme_weights(self):
        tensors = [np.ones(10), np.ones(10)]
        contrib = compute_contribution(tensors, [100.0, 0.0001], "weight_average")
        assert contrib[0] > 0.99

    def test_summary_with_many_layers(self):
        tracker = ProvenanceTracker()
        rng = np.random.RandomState(42)
        for i in range(20):
            tensors = [rng.randn(30), rng.randn(30)]
            tracker.track_merge(f"layer{i}", tensors, None, "weight_average")
        summary = tracker.summary()
        assert len(summary.layer_conflict_ranking) == 20
        assert len(summary.per_layer) == 20

    def test_contribution_sums_to_one_many_models(self):
        tensors = [np.ones(10)] * 7
        contrib = compute_contribution(tensors, None, "weight_average")
        total = sum(contrib.values())
        assert abs(total - 1.0) < 1e-6

    def test_export_csv_format(self):
        tracker = ProvenanceTracker()
        tracker.track_merge("layer.0.attn", [np.ones(10), np.ones(10)], None, "weight_average")
        summary = tracker.summary()
        csv = export_provenance(summary, format="csv")
        assert "layer.0.attn" in csv
        assert "weight_average" in csv

# ===========================================================================
# Additional Heatmap Tests (bring total ~35)
# ===========================================================================

class TestConflictHeatmapExtra:
    """Additional heatmap tests."""

    def test_from_models_contributions_sum_to_one(self):
        m1 = _make_model(["l0"], seed=1)
        m2 = _make_model(["l0"], seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        contrib = hm.model_contributions["l0"]
        total = sum(contrib.values())
        assert abs(total - 1.0) < 1e-6

    def test_heatmap_json_parseable(self):
        m1 = _make_model(["l0", "l1"], seed=1)
        m2 = _make_model(["l0", "l1"], seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        data = json.loads(hm.to_json())
        assert isinstance(data["layer_conflicts"], dict)

    def test_least_conflicted_sorted(self):
        models = [_make_model([f"l{i}" for i in range(10)], seed=s) for s in range(3)]
        hm = ConflictHeatmap.from_models(models)
        least = hm.least_conflicted_layers(5)
        scores = [s for _, s in least]
        assert scores == sorted(scores)

    def test_most_conflicted_sorted(self):
        models = [_make_model([f"l{i}" for i in range(10)], seed=s) for s in range(3)]
        hm = ConflictHeatmap.from_models(models)
        most = hm.most_conflicted_layers(5)
        scores = [s for _, s in most]
        assert scores == sorted(scores, reverse=True)

    def test_parameter_detail_variance_nonnegative(self):
        m1 = {"l0": np.array([1.0, -2.0, 3.0])}
        m2 = {"l0": np.array([-1.0, 2.0, -3.0])}
        hm = ConflictHeatmap.from_models([m1, m2])
        detail = hm.parameter_detail("l0")
        assert all(v >= 0 for v in detail.variance_map)

    def test_csv_has_all_layers(self):
        layers = ["a", "b", "c"]
        m1 = _make_model(layers, seed=1)
        m2 = _make_model(layers, seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        csv = hm.to_csv()
        for layer in layers:
            assert layer in csv

    def test_from_merge_matches_from_models_structure(self):
        """Both constructors produce same structural properties."""
        m1 = _make_model(["l0", "l1"], seed=1)
        m2 = _make_model(["l0", "l1"], seed=2)

        # from_models
        hm1 = ConflictHeatmap.from_models([m1, m2])

        # from_merge
        tracker = ProvenanceTracker()
        for name in ["l0", "l1"]:
            tracker.track_merge(name, [m1[name], m2[name]], None, "weight_average")
        hm2 = ConflictHeatmap.from_merge(tracker.summary())

        assert hm1.num_layers == hm2.num_layers
        assert set(hm1.layer_conflicts.keys()) == set(hm2.layer_conflicts.keys())

    def test_overall_conflict_equals_mean(self):
        m1 = _make_model(["l0", "l1"], seed=1)
        m2 = _make_model(["l0", "l1"], seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        expected = sum(hm.layer_conflicts.values()) / len(hm.layer_conflicts)
        assert abs(hm.overall_conflict - expected) < 1e-10

    def test_parameter_detail_magnitude_spread_nonneg(self):
        m1 = {"l0": np.array([1.0, 2.0, 3.0])}
        m2 = {"l0": np.array([4.0, 5.0, 6.0])}
        hm = ConflictHeatmap.from_models([m1, m2])
        detail = hm.parameter_detail("l0")
        assert detail.magnitude_spread >= 0.0

    def test_to_dict_overall_conflict_matches(self):
        m1 = _make_model(["l0"], seed=1)
        m2 = _make_model(["l0"], seed=2)
        hm = ConflictHeatmap.from_models([m1, m2])
        d = hm.to_dict()
        assert abs(d["overall_conflict"] - hm.overall_conflict) < 1e-10
