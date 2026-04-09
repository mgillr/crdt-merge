#!/usr/bin/env python3

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

"""Integration tests for the full model merge pipeline.

Tests the end-to-end flow:  ModelMerge → schema resolution → per-layer merge.

Run with:
    pip install numpy pytest
    pytest tests/test_merge_pipeline_integration.py -v
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from crdt_merge.model import ModelMerge, ModelCRDT, ModelMergeSchema, MergeResult
from crdt_merge.model.strategies import get_strategy, list_strategies
from crdt_merge.model.strategies.base import CRDTTier

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state_dict(layers, size=16, seed=0):
    """Generate a model state dict with random weights."""
    rng = np.random.RandomState(seed)
    return {layer: rng.randn(size).tolist() for layer in layers}

LAYERS = [f"layer{i}.weight" for i in range(4)]

@pytest.fixture
def models():
    return [_make_state_dict(LAYERS, seed=s) for s in range(3)]

@pytest.fixture
def base_model():
    return _make_state_dict(LAYERS, seed=999)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestModelMergeBackwardCompat:
    """Ensure ModelCRDT alias works identically to ModelMerge."""

    def test_alias_is_same_class(self):
        assert ModelCRDT is ModelMerge

    def test_alias_instantiation(self):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        crdt = ModelCRDT(schema)
        merge = ModelMerge(schema)
        assert type(crdt) is type(merge)

class TestBasicMergePipeline:
    """Test end-to-end merge with various strategies."""

    @pytest.mark.parametrize("strategy", [
        "weight_average", "fisher_merge", "regression_mean",
        "weight_scope_alignment", "representation_surgery",
        "safe_merge", "led_merge",
    ])
    def test_merge_produces_result(self, models, base_model, strategy):
        schema = ModelMergeSchema(strategies={"default": strategy})
        merger = ModelMerge(schema)
        result = merger.merge(models, base_model=base_model)

        assert isinstance(result, MergeResult)
        assert result.tensor is not None
        assert len(result.tensor) == len(LAYERS)

    @pytest.mark.parametrize("strategy", [
        "weight_average", "fisher_merge", "regression_mean",
    ])
    def test_single_call_nway_is_commutative(self, models, strategy):
        """N-way merge in a single call should be commutative."""
        schema = ModelMergeSchema(strategies={"default": strategy})
        merger = ModelMerge(schema)

        result_abc = merger.merge(models)
        result_cba = merger.merge(list(reversed(models)))

        for layer in LAYERS:
            a = np.array(result_abc.tensor[layer])
            b = np.array(result_cba.tensor[layer])
            assert np.allclose(a, b, atol=1e-6), (
                f"{strategy}: N-way merge not commutative for {layer}"
            )

class TestMultiStrategySchema:
    """Test schemas that assign different strategies to different layers."""

    def test_mixed_strategies(self, models, base_model):
        schema = ModelMergeSchema(strategies={
            "layer0.*": "weight_average",
            "layer1.*": "fisher_merge",
            "default": "regression_mean",
        })
        merger = ModelMerge(schema)
        result = merger.merge(models, base_model=base_model)

        assert isinstance(result, MergeResult)
        assert len(result.tensor) == len(LAYERS)

    def test_provenance_tracking(self, models, base_model):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        merger = ModelMerge(schema)
        result = merger.merge_with_provenance(models, base_model=base_model)

        assert result.provenance is not None
        for layer in LAYERS:
            assert layer in result.provenance
            assert result.provenance[layer]["strategy"] == "weight_average"

class TestVerifyMethod:
    """Test the verify() method on ModelMerge with the fixed verify_crdt."""

    def test_verify_weight_average(self):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        merger = ModelMerge(schema)
        results = merger.verify(strategy="weight_average", trials=20)

        wa = results["weight_average"]
        assert wa["commutative"] is True
        assert wa["idempotent"] is True
        # Associativity should fail for pairwise application
        assert wa["associative"] is False

    def test_verify_task_arithmetic_with_base(self):
        """Verify that task_arithmetic can now be tested (BUG-001 fixed)."""
        schema = ModelMergeSchema(strategies={"default": "task_arithmetic"})
        merger = ModelMerge(schema)
        results = merger.verify(strategy="task_arithmetic", trials=20)

        ta = results["task_arithmetic"]
        # Should no longer raise ValueError -- base is auto-generated
        assert "needs_base" in ta
        assert ta["needs_base"] is True
        assert ta["commutative"] is True

class TestCRDTTierClassification:
    """Verify all strategies have correct tier classification."""

    def test_no_true_crdt_strategies(self):
        """Currently no strategy satisfies all three CRDT laws."""
        for name in list_strategies():
            s = get_strategy(name)
            if s.crdt_tier == CRDTTier.TRUE_CRDT:
                # If any strategy claims TRUE_CRDT, verify it actually passes
                props = s.crdt_properties
                assert props.get("commutative") is True
                assert props.get("associative") is True
                assert props.get("idempotent") is True

    def test_stochastic_strategies_are_not_crdt(self):
        for name in ["evolutionary_merge", "dare", "della", "dare_ties"]:
            s = get_strategy(name)
            assert s.crdt_tier == CRDTTier.NOT_CRDT, (
                f"{name} should be NOT_CRDT but is {s.crdt_tier}"
            )

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
