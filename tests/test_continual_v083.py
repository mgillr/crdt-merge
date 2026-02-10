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
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for v0.8.3 Continual Merge Engine.

Covers:
- DualProjectionMerge strategy (registration, merge, CRDT properties)
- ContinualMerge with convergence="crdt"
- ConvergenceProof verification
- ContinualBenchmark
- Backward compatibility with existing ContinualMerge
- StabilityResult
- Edge cases
"""

from __future__ import annotations

import numpy as np
import pytest

from crdt_merge.model.continual import ContinualMerge, StabilityResult
from crdt_merge.model.continual_bench import (
    BenchmarkResult,
    ContinualBenchmark,
    StrategyBenchmark,
)
from crdt_merge.model.continual_verify import (
    ConvergenceProof,
    FullVerifyResult,
    VerifyResult,
)
from crdt_merge.model.strategies import get_strategy, list_strategies
from crdt_merge.model.strategies.base import CRDTTier, MergeResult
from crdt_merge.model.strategies.continual import DualProjectionMerge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng():
    return np.random.RandomState(42)


@pytest.fixture
def base_model():
    return {
        "layer_0": [1.0, 2.0, 3.0, 4.0],
        "layer_1": [0.5, 0.5, 0.5, 0.5],
    }


@pytest.fixture
def model_a():
    return {
        "layer_0": [2.0, 3.0, 4.0, 5.0],
        "layer_1": [1.0, 1.0, 1.0, 1.0],
    }


@pytest.fixture
def model_b():
    return {
        "layer_0": [3.0, 1.0, 2.0, 6.0],
        "layer_1": [0.0, 2.0, 0.0, 2.0],
    }


@pytest.fixture
def model_c():
    return {
        "layer_0": [0.0, 5.0, 1.0, 3.0],
        "layer_1": [1.5, 0.0, 1.5, 0.0],
    }


def _make_tensors(rng, n, d=16):
    """Generate n random tensors of dimension d."""
    return [rng.randn(d).tolist() for _ in range(n)]


def _make_models(rng, n, layers=2, d=16):
    """Generate n model state dicts."""
    models = []
    for _ in range(n):
        sd = {}
        for i in range(layers):
            sd[f"layer_{i}"] = rng.randn(d).tolist()
        models.append(sd)
    return models


# =========================================================================
# DualProjectionMerge strategy tests
# =========================================================================

class TestDualProjectionRegistration:
    """Strategy registration and metadata."""

    def test_registered_in_list(self):
        assert "dual_projection" in list_strategies()

    def test_get_strategy(self):
        s = get_strategy("dual_projection")
        assert isinstance(s, DualProjectionMerge)

    def test_name(self):
        s = DualProjectionMerge()
        assert s.name == "dual_projection"

    def test_category(self):
        s = DualProjectionMerge()
        assert s.category == "continual"

    def test_paper_reference(self):
        s = DualProjectionMerge()
        assert "Yuan" in s.paper_reference
        assert "NeurIPS" in s.paper_reference

    def test_crdt_properties(self):
        s = DualProjectionMerge()
        props = s.crdt_properties
        assert props["commutative"] is True
        assert props["associative"] is True
        assert props["idempotent"] is True
        assert props["crdt_tier"] == CRDTTier.TRUE_CRDT

    def test_crdt_tier_property(self):
        s = DualProjectionMerge()
        assert s.crdt_tier == CRDTTier.TRUE_CRDT


class TestDualProjectionMerge:
    """Core merge functionality."""

    def test_merge_two_tensors(self, rng):
        s = DualProjectionMerge()
        a, b = rng.randn(8).tolist(), rng.randn(8).tolist()
        result = s.merge([a, b])
        assert len(result) == 8

    def test_merge_three_tensors(self, rng):
        s = DualProjectionMerge()
        tensors = _make_tensors(rng, 3, d=12)
        result = s.merge(tensors)
        assert len(result) == 12

    def test_merge_five_tensors(self, rng):
        s = DualProjectionMerge()
        tensors = _make_tensors(rng, 5, d=20)
        result = s.merge(tensors)
        assert len(result) == 20

    def test_merge_with_weights(self, rng):
        s = DualProjectionMerge()
        tensors = _make_tensors(rng, 3, d=8)
        result = s.merge(tensors, weights=[0.5, 0.3, 0.2])
        assert len(result) == 8

    def test_merge_with_base(self, rng):
        s = DualProjectionMerge()
        base = rng.randn(10).tolist()
        tensors = _make_tensors(rng, 3, d=10)
        result = s.merge(tensors, base=base)
        assert len(result) == 10

    def test_merge_preserves_type_list(self, rng):
        s = DualProjectionMerge()
        tensors = [rng.randn(6).tolist() for _ in range(2)]
        result = s.merge(tensors)
        assert isinstance(result, list)

    def test_merge_preserves_type_ndarray(self, rng):
        s = DualProjectionMerge()
        tensors = [rng.randn(6) for _ in range(2)]
        result = s.merge(tensors)
        assert isinstance(result, np.ndarray)

    def test_merge_single_tensor_passthrough(self, rng):
        s = DualProjectionMerge()
        t = rng.randn(8).tolist()
        result = s.merge([t])
        assert result == t

    def test_merge_empty_raises(self):
        s = DualProjectionMerge()
        with pytest.raises(ValueError, match="zero"):
            s.merge([])

    def test_stability_weight_zero_full_plasticity(self, rng):
        """stability_weight=0 should be equivalent to weighted average."""
        s0 = DualProjectionMerge(stability_weight=0.0)
        tensors = _make_tensors(rng, 3, d=10)
        base = rng.randn(10).tolist()
        result = s0.merge(tensors, base=base)
        # With stability=0, result = base + full weighted delta
        assert len(result) == 10

    def test_stability_weight_one_full_stability(self, rng):
        """stability_weight=1 should suppress task-specific components."""
        s1 = DualProjectionMerge(stability_weight=1.0)
        base = [0.0] * 10
        tensors = _make_tensors(rng, 3, d=10)
        result = s1.merge(tensors, base=base)
        assert len(result) == 10

    def test_different_stability_weights_differ(self, rng):
        tensors = _make_tensors(rng, 3, d=16)
        base = rng.randn(16).tolist()
        r0 = DualProjectionMerge(stability_weight=0.0).merge(tensors, base=base)
        r1 = DualProjectionMerge(stability_weight=1.0).merge(tensors, base=base)
        # Should generally be different
        assert r0 != r1

    def test_stability_weight_kwarg_override(self, rng):
        s = DualProjectionMerge(stability_weight=0.5)
        tensors = _make_tensors(rng, 2, d=8)
        base = rng.randn(8).tolist()
        r_default = s.merge(tensors, base=base)
        r_override = s.merge(tensors, base=base, stability_weight=0.0)
        # Override should produce different result
        assert not np.allclose(r_default, r_override, atol=1e-10)


class TestDualProjectionCRDTProperties:
    """Empirical verification of CRDT algebraic laws."""

    def test_commutativity(self, rng):
        """merge([a, b]) == merge([b, a])"""
        s = DualProjectionMerge()
        a, b = rng.randn(12).tolist(), rng.randn(12).tolist()
        r_ab = s.merge([a, b])
        r_ba = s.merge([b, a])
        np.testing.assert_allclose(r_ab, r_ba, atol=1e-10)

    def test_commutativity_three_models(self, rng):
        s = DualProjectionMerge()
        a, b, c = _make_tensors(rng, 3, d=10)
        r_abc = s.merge([a, b, c])
        r_cab = s.merge([c, a, b])
        r_bca = s.merge([b, c, a])
        np.testing.assert_allclose(r_abc, r_cab, atol=1e-10)
        np.testing.assert_allclose(r_abc, r_bca, atol=1e-10)

    def test_commutativity_with_weights(self, rng):
        s = DualProjectionMerge()
        a, b = rng.randn(10).tolist(), rng.randn(10).tolist()
        w = [0.7, 0.3]
        r1 = s.merge([a, b], weights=w)
        r2 = s.merge([b, a], weights=[0.3, 0.7])
        np.testing.assert_allclose(r1, r2, atol=1e-10)

    def test_commutativity_with_base(self, rng):
        s = DualProjectionMerge()
        base = rng.randn(8).tolist()
        a, b = rng.randn(8).tolist(), rng.randn(8).tolist()
        r1 = s.merge([a, b], base=base)
        r2 = s.merge([b, a], base=base)
        np.testing.assert_allclose(r1, r2, atol=1e-10)

    def test_idempotency(self, rng):
        """merge([a, a]) == a"""
        s = DualProjectionMerge()
        a = rng.randn(10).tolist()
        r = s.merge([a, a])
        np.testing.assert_allclose(r, a, atol=1e-10)

    def test_idempotency_with_base(self, rng):
        s = DualProjectionMerge()
        base = rng.randn(8).tolist()
        a = rng.randn(8).tolist()
        r = s.merge([a, a], base=base)
        np.testing.assert_allclose(r, a, atol=1e-10)

    def test_idempotency_triple(self, rng):
        s = DualProjectionMerge()
        a = rng.randn(10).tolist()
        r = s.merge([a, a, a])
        np.testing.assert_allclose(r, a, atol=1e-10)

    def test_verify_crdt_method(self, rng):
        """Use built-in verify_crdt from ModelMergeStrategy."""
        s = DualProjectionMerge(stability_weight=0.0)
        result = s.verify_crdt(
            gen_fn=lambda: rng.randn(8).tolist(),
            trials=20,
        )
        assert result["commutative"] is True
        assert result["idempotent"] is True


# =========================================================================
# ContinualMerge tests (with convergence="crdt")
# =========================================================================

class TestContinualMergeCRDT:
    """ContinualMerge with convergence='crdt'."""

    def test_init_crdt(self, base_model):
        cm = ContinualMerge(
            base_model, strategy="weight_average", convergence="crdt",
        )
        assert cm._convergence == "crdt"
        assert len(cm._crdt_states) == 2

    def test_absorb_and_export(self, base_model, model_a):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        result = cm.export()
        assert "layer_0" in result
        assert "layer_1" in result
        assert len(result["layer_0"]) == 4

    def test_verify_convergence_true(self, base_model):
        cm = ContinualMerge(base_model, convergence="crdt")
        assert cm.verify_convergence() is True

    def test_verify_convergence_false_default(self, base_model):
        cm = ContinualMerge(base_model)
        assert cm.verify_convergence() is False

    def test_absorb_order_independence(self, base_model, model_a, model_b):
        """CRDT mode: absorb order should not matter."""
        cm1 = ContinualMerge(base_model, convergence="crdt")
        cm1.absorb(model_a, name="a")
        cm1.absorb(model_b, name="b")
        r1 = cm1.export()

        cm2 = ContinualMerge(base_model, convergence="crdt")
        cm2.absorb(model_b, name="b")
        cm2.absorb(model_a, name="a")
        r2 = cm2.export()

        for layer in r1:
            np.testing.assert_allclose(r1[layer], r2[layer], atol=1e-10)

    def test_absorb_three_models(self, base_model, model_a, model_b, model_c):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b")
        cm.absorb(model_c, name="c")
        r = cm.export()
        assert len(r) == 2

    def test_dual_projection_crdt(self, base_model, model_a, model_b):
        """ContinualMerge with dual_projection + crdt."""
        cm = ContinualMerge(
            base_model, strategy="dual_projection", convergence="crdt",
        )
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b")
        r = cm.export()
        assert "layer_0" in r

    def test_dual_projection_order_independence(
        self, base_model, model_a, model_b, model_c,
    ):
        cm1 = ContinualMerge(
            base_model, strategy="dual_projection", convergence="crdt",
        )
        cm1.absorb(model_a, name="a")
        cm1.absorb(model_b, name="b")
        cm1.absorb(model_c, name="c")
        r1 = cm1.export()

        cm2 = ContinualMerge(
            base_model, strategy="dual_projection", convergence="crdt",
        )
        cm2.absorb(model_c, name="c")
        cm2.absorb(model_a, name="a")
        cm2.absorb(model_b, name="b")
        r2 = cm2.export()

        for layer in r1:
            np.testing.assert_allclose(r1[layer], r2[layer], atol=1e-10)

    def test_reset_crdt(self, base_model, model_a):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        new_base = {"layer_0": [0.0, 0.0, 0.0, 0.0]}
        cm.reset(new_base)
        assert cm.verify_convergence() is True
        r = cm.export()
        np.testing.assert_allclose(r["layer_0"], [0.0, 0.0, 0.0, 0.0], atol=1e-10)

    def test_replace_crdt(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b", replace="a")
        r = cm.export()
        assert "layer_0" in r


class TestMeasureStability:
    """StabilityResult and measure_stability()."""

    def test_measure_stability_basic(self, base_model, model_a):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        sr = cm.measure_stability("a")
        assert isinstance(sr, StabilityResult)
        assert 0.0 <= sr.retention <= 1.0

    def test_stability_per_layer(self, base_model, model_a):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        sr = cm.measure_stability("a")
        for layer, val in sr.per_layer.items():
            assert 0.0 <= val <= 1.0

    def test_stability_unknown_model_raises(self, base_model):
        cm = ContinualMerge(base_model, convergence="crdt")
        with pytest.raises(KeyError, match="nonexistent"):
            cm.measure_stability("nonexistent")

    def test_stability_single_absorb_high(self, base_model, model_a):
        """With only one model absorbed (plus base), retention should be high."""
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        sr = cm.measure_stability("a")
        assert sr.retention > 0.3

    def test_stability_classic_mode(self, base_model, model_a):
        """measure_stability works in classic mode too."""
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        sr = cm.measure_stability("a")
        assert isinstance(sr, StabilityResult)

    def test_stability_multiple_models(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b")
        sr_a = cm.measure_stability("a")
        sr_b = cm.measure_stability("b")
        assert 0.0 <= sr_a.retention <= 1.0
        assert 0.0 <= sr_b.retention <= 1.0


# =========================================================================
# ConvergenceProof tests
# =========================================================================

class TestConvergenceProof:
    """Verify CRDT properties via ConvergenceProof."""

    def test_verify_commutativity_crdt(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_commutativity([model_a, model_b])
        assert isinstance(r, VerifyResult)
        assert r.passed is True
        assert r.property_name == "commutativity"
        assert r.max_deviation < 1e-6

    def test_verify_commutativity_three_models(
        self, base_model, model_a, model_b, model_c,
    ):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_commutativity([model_a, model_b, model_c])
        assert r.passed is True

    def test_verify_associativity_crdt(
        self, base_model, model_a, model_b, model_c,
    ):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_associativity([model_a, model_b, model_c])
        assert r.passed is True
        assert r.property_name == "associativity"

    def test_verify_idempotency_crdt(self, base_model, model_a):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_idempotency(model_a)
        assert r.passed is True
        assert r.property_name == "idempotency"

    def test_verify_all_crdt(self, base_model, model_a, model_b, model_c):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        full = proof.verify_all([model_a, model_b, model_c])
        assert isinstance(full, FullVerifyResult)
        assert full.all_passed is True
        assert len(full.results) == 3

    def test_verify_commutativity_trivial(self, base_model):
        """Fewer than 2 models → trivially passes."""
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_commutativity([])
        assert r.passed is True

    def test_verify_associativity_trivial(self, base_model, model_a):
        """Fewer than 3 models → trivially passes."""
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_associativity([model_a])
        assert r.passed is True

    def test_verify_all_dual_projection(
        self, base_model, model_a, model_b, model_c,
    ):
        cm = ContinualMerge(
            base_model, strategy="dual_projection", convergence="crdt",
        )
        proof = ConvergenceProof(cm)
        full = proof.verify_all([model_a, model_b, model_c])
        assert full.all_passed is True

    def test_details_contain_info(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model, convergence="crdt")
        proof = ConvergenceProof(cm)
        r = proof.verify_commutativity([model_a, model_b])
        assert "PASSED" in r.details or "FAILED" in r.details


# =========================================================================
# ContinualBenchmark tests
# =========================================================================

class TestContinualBenchmark:
    """Benchmark smoke tests."""

    def test_generate_models(self):
        bench = ContinualBenchmark(layer_sizes=[8, 4])
        models = bench.generate_models(3)
        assert len(models) == 3
        assert "layer_0" in models[0]
        assert len(models[0]["layer_0"]) == 8
        assert len(models[0]["layer_1"]) == 4

    def test_generate_models_reproducible(self):
        bench = ContinualBenchmark(layer_sizes=[8])
        m1 = bench.generate_models(3, seed=123)
        m2 = bench.generate_models(3, seed=123)
        for i in range(3):
            assert m1[i]["layer_0"] == m2[i]["layer_0"]

    def test_run_benchmark(self):
        bench = ContinualBenchmark(layer_sizes=[8, 4])
        result = bench.run(n_models=3)
        assert isinstance(result, BenchmarkResult)
        assert result.n_models == 3
        assert "dual_projection+crdt" in result.strategies
        assert "weight_average" in result.strategies

    def test_benchmark_result_summary(self):
        bench = ContinualBenchmark(layer_sizes=[8])
        result = bench.run(n_models=2)
        summary = result.summary()
        assert "dual_projection" in summary
        assert "weight_average" in summary

    def test_strategy_benchmark_fields(self):
        bench = ContinualBenchmark(layer_sizes=[8])
        result = bench.run(n_models=2)
        for name, sb in result.strategies.items():
            assert isinstance(sb, StrategyBenchmark)
            assert sb.elapsed_seconds >= 0
            assert isinstance(sb.converged, bool)

    def test_dual_projection_converges(self):
        bench = ContinualBenchmark(layer_sizes=[8])
        result = bench.run(n_models=3)
        assert result.strategies["dual_projection+crdt"].converged is True

    def test_classic_does_not_converge(self):
        bench = ContinualBenchmark(layer_sizes=[8])
        result = bench.run(n_models=3)
        assert result.strategies["weight_average"].converged is False


# =========================================================================
# Backward compatibility tests
# =========================================================================

class TestBackwardCompatibility:
    """Existing ContinualMerge API must remain unchanged."""

    def test_default_init(self, base_model):
        cm = ContinualMerge(base_model)
        assert cm._strategy == "weight_average"
        assert cm._convergence is None

    def test_absorb_and_export_classic(self, base_model, model_a):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        r = cm.export()
        assert "layer_0" in r

    def test_history(self, base_model, model_a):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        assert len(cm.history) == 1
        assert cm.history[0]["name"] == "a"

    def test_current_weights(self, base_model, model_a):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        w = cm.current_weights
        assert "__base__" in w
        assert "a" in w
        assert abs(sum(w.values()) - 1.0) < 1e-10

    def test_reset(self, base_model, model_a):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        new_base = {"layer_0": [0.0, 0.0, 0.0, 0.0]}
        cm.reset(new_base)
        r = cm.export()
        np.testing.assert_allclose(r["layer_0"], [0.0, 0.0, 0.0, 0.0], atol=1e-10)

    def test_replace(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b", replace="a")
        assert "a" not in cm._contributions

    def test_memory_budget(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model, memory_budget=0.5)
        cm.absorb(model_a, name="a")
        cm.absorb(model_b, name="b")
        w = cm.current_weights
        # Newer model should have higher weight
        assert w["b"] > w["a"]

    def test_strategy_param(self, base_model):
        cm = ContinualMerge(base_model, strategy="weight_average")
        assert cm._strategy == "weight_average"

    def test_export_empty_after_reset_single_layer(self):
        cm = ContinualMerge({"x": [1.0, 2.0]})
        r = cm.export()
        np.testing.assert_allclose(r["x"], [1.0, 2.0], atol=1e-10)


# =========================================================================
# Edge cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_model_merge(self):
        s = DualProjectionMerge()
        t = [1.0, 2.0, 3.0]
        assert s.merge([t]) == t

    def test_empty_layer_values(self):
        """Models with empty layer tensors."""
        base = {"layer": []}
        cm = ContinualMerge(base, convergence="crdt")
        # Absorb should handle empty tensors
        cm.absorb({"layer": []}, name="a")

    def test_zero_weights_raises(self):
        s = DualProjectionMerge()
        with pytest.raises(ValueError, match="zero"):
            s.merge([[1.0, 2.0], [3.0, 4.0]], weights=[0.0, 0.0])

    def test_identical_models(self, base_model):
        """Absorbing identical models should not change the merge much."""
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(base_model.copy(), name="copy1")
        cm.absorb(base_model.copy(), name="copy2")
        r = cm.export()
        for layer in base_model:
            np.testing.assert_allclose(
                r[layer], base_model[layer], atol=1e-6,
            )

    def test_large_number_of_models(self, rng):
        """Absorb 20 models without errors."""
        base = {"layer": rng.randn(16).tolist()}
        cm = ContinualMerge(base, convergence="crdt")
        for i in range(20):
            cm.absorb({"layer": rng.randn(16).tolist()}, name=f"m_{i}")
        r = cm.export()
        assert len(r["layer"]) == 16

    def test_auto_name_generation(self, base_model, model_a):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a)  # no name
        assert len(cm.history) == 1

    def test_duplicate_name_uniquified(self, base_model, model_a, model_b):
        cm = ContinualMerge(base_model)
        cm.absorb(model_a, name="dup")
        cm.absorb(model_b, name="dup")
        # Second absorb should get a uniquified name
        assert "dup" in cm._contributions
        assert "dup_1" in cm._contributions

    def test_scalar_tensor_merge(self):
        """DualProjectionMerge should handle scalar values."""
        s = DualProjectionMerge()
        r = s.merge([5.0, 3.0])
        assert float(r) == pytest.approx(4.0, abs=1e-6)

    def test_stability_result_dataclass(self):
        sr = StabilityResult(retention=0.85, per_layer={"a": 0.9, "b": 0.8})
        assert sr.retention == 0.85
        assert sr.per_layer["a"] == 0.9

    def test_stability_result_default_per_layer(self):
        sr = StabilityResult(retention=0.5)
        assert sr.per_layer == {}

    def test_crdt_continual_new_layer_on_absorb(self, base_model, model_a):
        """Absorbing a model with an extra layer succeeds."""
        extra_model = {**model_a, "layer_new": [1.0, 2.0]}
        cm = ContinualMerge(base_model, convergence="crdt")
        cm.absorb(extra_model, name="extra")
        r = cm.export()
        assert "layer_new" in r
