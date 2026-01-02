# SPDX-License-Identifier: BUSL-1.1
#
# Copyright 2026 Ryan Gillespie
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.model.strategies.basic — 4 basic merge strategies.

Covers: WeightAverage, SLERP, TaskArithmetic, LinearInterpolation.
Target: ~100 tests.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Import strategies (this triggers registration via @register_strategy)
# ---------------------------------------------------------------------------

from crdt_merge.model.strategies.basic import (
    LinearInterpolation,
    SphericalLinearInterpolation,
    TaskArithmetic,
    WeightAverage,
)
from crdt_merge.model.strategies import get_strategy, list_strategies
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _approx_equal,
    _normalize_weights,
)
from crdt_merge.model.core import ModelCRDT, ModelMergeSchema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEED = 42


def _rand_vec(n: int = 10, seed: int | None = None) -> list:
    """Return a random list of *n* floats in [0, 1)."""
    rng = random.Random(seed)
    return [rng.random() for _ in range(n)]


def _rand_np(n: int = 10, seed: int | None = None) -> np.ndarray:
    """Return a random numpy array of *n* floats."""
    rng = np.random.RandomState(seed if seed is not None else SEED)
    return rng.rand(n)


def _approx(a, b, tol=1e-6) -> bool:
    """Check approximate equality for arrays/lists."""
    return _approx_equal(a, b, tol=tol)


# ===================================================================
# WeightAverage
# ===================================================================

class TestWeightAverage:
    """Tests for the WeightAverage strategy."""

    def setup_method(self):
        self.s = WeightAverage()

    # --- basic merges ---

    def test_two_models_uniform(self):
        a = [1.0, 2.0, 3.0]
        b = [3.0, 4.0, 5.0]
        result = self.s.merge([a, b])
        assert _approx(result, [2.0, 3.0, 4.0])

    def test_two_models_custom_weights(self):
        a = [0.0, 0.0, 0.0]
        b = [10.0, 10.0, 10.0]
        result = self.s.merge([a, b], weights=[0.3, 0.7])
        assert _approx(result, [7.0, 7.0, 7.0])

    def test_three_models_uniform(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        c = [0.0, 0.0]
        result = self.s.merge([a, b, c])
        expected = [1.0 / 3, 1.0 / 3]
        assert _approx(result, expected)

    def test_three_models_custom_weights(self):
        a = [10.0]
        b = [20.0]
        c = [30.0]
        result = self.s.merge([a, b, c], weights=[1.0, 2.0, 3.0])
        # normalized: [1/6, 2/6, 3/6] => 10/6 + 40/6 + 90/6 = 140/6 ≈ 23.333
        expected = [10 * (1 / 6) + 20 * (2 / 6) + 30 * (3 / 6)]
        assert _approx(result, expected)

    def test_single_model(self):
        a = [5.0, 6.0]
        result = self.s.merge([a])
        assert result == [5.0, 6.0]

    def test_empty_tensors(self):
        result = self.s.merge([])
        assert result == []

    def test_uniform_weights_default(self):
        """No weights => uniform."""
        a = [2.0, 4.0]
        b = [4.0, 8.0]
        result = self.s.merge([a, b])
        assert _approx(result, [3.0, 6.0])

    def test_weights_mismatch_raises(self):
        with pytest.raises(ValueError):
            self.s.merge([[1.0], [2.0]], weights=[0.5])

    def test_zero_weights_raises(self):
        with pytest.raises(ValueError):
            self.s.merge([[1.0], [2.0]], weights=[0.0, 0.0])

    # --- CRDT properties ---

    def test_commutativity_random(self):
        rng = random.Random(SEED)
        for _ in range(10):
            a = [rng.random() for _ in range(10)]
            b = [rng.random() for _ in range(10)]
            ab = self.s.merge([a, b])
            ba = self.s.merge([b, a])
            assert _approx(ab, ba), f"Commutativity failed"

    def test_associativity_nary(self):
        """N-ary merge is order-independent (commutativity extends to N>2)."""
        rng = random.Random(SEED)
        for _ in range(10):
            a = [rng.random() for _ in range(5)]
            b = [rng.random() for _ in range(5)]
            c = [rng.random() for _ in range(5)]
            abc = self.s.merge([a, b, c])
            bca = self.s.merge([b, c, a])
            cab = self.s.merge([c, a, b])
            assert _approx(abc, bca), "N-ary merge not order-independent"
            assert _approx(abc, cab), "N-ary merge not order-independent"

    def test_associativity_weighted(self):
        """Weighted average with explicit weights is associative in N-ary form."""
        rng = random.Random(SEED + 1)
        for _ in range(10):
            a = [rng.random() for _ in range(5)]
            b = [rng.random() for _ in range(5)]
            c = [rng.random() for _ in range(5)]
            w = [rng.random() + 0.1, rng.random() + 0.1, rng.random() + 0.1]
            abc = self.s.merge([a, b, c], weights=w)
            # Same weights but different input order + matching weight reorder
            bca = self.s.merge([b, c, a], weights=[w[1], w[2], w[0]])
            assert _approx(abc, bca), "Weighted N-ary merge not order-independent"

    def test_idempotency(self):
        a = [3.0, 7.0, 1.0]
        result = self.s.merge([a, a])
        assert _approx(result, a)

    # --- type preservation ---

    def test_list_in_list_out(self):
        result = self.s.merge([[1.0, 2.0], [3.0, 4.0]])
        assert isinstance(result, list)

    def test_numpy_in_numpy_out(self):
        a = np.array([1.0, 2.0])
        b = np.array([3.0, 4.0])
        result = self.s.merge([a, b])
        assert isinstance(result, np.ndarray)

    # --- properties ---

    def test_name(self):
        assert self.s.name == "weight_average"

    def test_category(self):
        assert self.s.category == "averaging"

    def test_paper_reference(self):
        assert "McMahan" in self.s.paper_reference

    def test_crdt_properties_declared(self):
        props = self.s.crdt_properties
        assert props["commutative"] is True
        assert props["associative"] is True
        assert props["idempotent"] is True


# ===================================================================
# SLERP
# ===================================================================

class TestSLERP:
    """Tests for the SphericalLinearInterpolation (SLERP) strategy."""

    def setup_method(self):
        self.s = SphericalLinearInterpolation()

    # --- basic merges ---

    def test_two_models_default_t(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = self.s.merge([a, b], t=0.5)
        # At t=0.5, midpoint on unit circle between (1,0) and (0,1) is
        # (cos(π/4), sin(π/4)) scaled by linearly-interpolated magnitude
        mid_mag = 0.5 * 1.0 + 0.5 * 1.0  # = 1.0
        expected = [math.cos(math.pi / 4) * mid_mag, math.sin(math.pi / 4) * mid_mag]
        assert _approx(result, expected, tol=1e-5)

    def test_t_zero_returns_first(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = self.s.merge([a, b], t=0.0)
        assert _approx(result, a, tol=1e-5)

    def test_t_one_returns_second(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = self.s.merge([a, b], t=1.0)
        assert _approx(result, b, tol=1e-5)

    def test_t_half_midpoint(self):
        """At t=0.5, result should be equidistant from both inputs on the sphere."""
        a = [3.0, 0.0]
        b = [0.0, 3.0]
        result = self.s.merge([a, b], t=0.5)
        # Both magnitude 3, angle 90°
        # SLERP midpoint direction = (cos45, sin45), magnitude = 3
        expected = [3.0 * math.cos(math.pi / 4), 3.0 * math.sin(math.pi / 4)]
        assert _approx(result, expected, tol=1e-5)

    def test_parallel_vectors_linear_fallback(self):
        """When vectors are parallel (same direction), SLERP falls back to LERP."""
        a = [2.0, 0.0, 0.0]
        b = [4.0, 0.0, 0.0]
        result = self.s.merge([a, b], t=0.5)
        assert _approx(result, [3.0, 0.0, 0.0], tol=1e-5)

    def test_zero_vectors(self):
        a = [0.0, 0.0, 0.0]
        b = [0.0, 0.0, 0.0]
        result = self.s.merge([a, b], t=0.5)
        assert _approx(result, [0.0, 0.0, 0.0])

    def test_one_zero_vector(self):
        a = [0.0, 0.0]
        b = [4.0, 3.0]
        result = self.s.merge([a, b], t=0.5)
        # norm_a ≈ 0 → return b * t
        expected = [2.0, 1.5]
        assert _approx(result, expected, tol=1e-5)

    def test_three_models_pairwise(self):
        """N>2 applies pairwise sequentially."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        c = [1.0, 1.0]
        # Should not raise
        result = self.s.merge([a, b, c], t=0.5)
        assert len(result) == 2

    def test_single_model(self):
        a = [5.0, 6.0]
        result = self.s.merge([a])
        assert result == [5.0, 6.0]

    def test_empty_tensors(self):
        result = self.s.merge([])
        assert result == []

    def test_commutativity_at_t_half(self):
        """SLERP is commutative at t=0.5."""
        rng = random.Random(SEED)
        for _ in range(10):
            a = [rng.random() + 0.1 for _ in range(8)]
            b = [rng.random() + 0.1 for _ in range(8)]
            ab = self.s.merge([a, b], t=0.5)
            ba = self.s.merge([b, a], t=0.5)
            assert _approx(ab, ba, tol=1e-5), "SLERP not commutative at t=0.5"

    def test_idempotency(self):
        a = [3.0, 4.0, 1.0]
        result = self.s.merge([a, a], t=0.5)
        assert _approx(result, a, tol=1e-5)

    # --- type preservation ---

    def test_list_in_list_out(self):
        result = self.s.merge([[1.0, 0.0], [0.0, 1.0]], t=0.5)
        assert isinstance(result, list)

    def test_numpy_in_numpy_out(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        result = self.s.merge([a, b], t=0.5)
        assert isinstance(result, np.ndarray)

    # --- properties ---

    def test_name(self):
        assert self.s.name == "slerp"

    def test_category(self):
        assert self.s.category == "interpolation"

    def test_paper_reference(self):
        assert "Shoemake" in self.s.paper_reference

    def test_crdt_properties_declared(self):
        props = self.s.crdt_properties
        assert props["commutative"] == "conditional"
        assert props["associative"] is False
        assert props["idempotent"] is True

    def test_antiparallel_vectors(self):
        """Vectors pointing in opposite directions."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        result = self.s.merge([a, b], t=0.5)
        # Anti-parallel: omega = pi, sin(pi) ≈ 0, should still produce a result
        assert len(result) == 2


# ===================================================================
# TaskArithmetic
# ===================================================================

class TestTaskArithmetic:
    """Tests for the TaskArithmetic strategy."""

    def setup_method(self):
        self.s = TaskArithmetic()

    # --- base model required ---

    def test_no_base_raises(self):
        with pytest.raises(ValueError, match="base"):
            self.s.merge([[1.0, 2.0]])

    def test_no_base_explicit_none_raises(self):
        with pytest.raises(ValueError, match="base"):
            self.s.merge([[1.0]], base=None)

    # --- basic merges ---

    def test_single_model_default_scaling(self):
        base = [1.0, 1.0, 1.0]
        model = [3.0, 2.0, 4.0]
        result = self.s.merge([model], base=base)
        # task_vec = [2, 1, 3], scale=1.0 → base + task_vec = model
        assert _approx(result, model)

    def test_two_models(self):
        base = [0.0, 0.0]
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = self.s.merge([a, b], base=base)
        # task_a = [1,0], task_b = [0,1] → base + [1,1] = [1,1]
        assert _approx(result, [1.0, 1.0])

    def test_three_models(self):
        base = [0.0, 0.0, 0.0]
        a = [1.0, 0.0, 0.0]
        b = [0.0, 2.0, 0.0]
        c = [0.0, 0.0, 3.0]
        result = self.s.merge([a, b, c], base=base)
        assert _approx(result, [1.0, 2.0, 3.0])

    def test_scaling_coefficients(self):
        base = [0.0, 0.0]
        a = [2.0, 0.0]
        b = [0.0, 4.0]
        result = self.s.merge([a, b], base=base, scaling_coefficients=[0.5, 0.25])
        # task_a = [2,0]*0.5 = [1,0], task_b = [0,4]*0.25 = [0,1] → [1,1]
        assert _approx(result, [1.0, 1.0])

    def test_scaling_coefficients_mismatch(self):
        with pytest.raises(ValueError, match="scaling_coefficients"):
            self.s.merge([[1.0]], base=[0.0], scaling_coefficients=[0.5, 0.5])

    def test_empty_tensors_returns_base(self):
        base = [5.0, 6.0]
        result = self.s.merge([], base=base)
        assert result == base

    def test_negative_scaling(self):
        """Negative scaling inverts the task vector (unlearning)."""
        base = [0.0]
        model = [10.0]
        result = self.s.merge([model], base=base, scaling_coefficients=[-1.0])
        # task_vec = [10], scale = -1 → base + (-10) = [-10]
        assert _approx(result, [-10.0])

    def test_task_vector_correctness(self):
        """Verify task vectors are computed as (model - base)."""
        base = [5.0, 5.0, 5.0]
        model = [7.0, 3.0, 5.0]
        result = self.s.merge([model], base=base, scaling_coefficients=[2.0])
        # task = [2, -2, 0], scaled = [4, -4, 0], result = base + scaled = [9, 1, 5]
        assert _approx(result, [9.0, 1.0, 5.0])

    # --- CRDT properties ---

    def test_commutativity_random(self):
        """Task arithmetic is commutative over task vectors."""
        rng = random.Random(SEED)
        base = [rng.random() for _ in range(8)]
        for _ in range(10):
            a = [rng.random() for _ in range(8)]
            b = [rng.random() for _ in range(8)]
            ab = self.s.merge([a, b], base=base)
            ba = self.s.merge([b, a], base=base)
            assert _approx(ab, ba), "Task arithmetic not commutative"

    def test_associativity(self):
        """Associativity: merge([a,b],c) == merge(a,[b,c])."""
        base = [0.0, 0.0, 0.0]
        a = [1.0, 0.0, 0.0]
        b = [0.0, 2.0, 0.0]
        c = [0.0, 0.0, 3.0]
        # merge([a,b,c]) should be same regardless of grouping
        # Since all task vectors are additive, merge([a,b,c]) = base + sum(task_vecs)
        abc = self.s.merge([a, b, c], base=base)
        # Verify via direct computation
        expected = [1.0, 2.0, 3.0]
        assert _approx(abc, expected)

    # --- type preservation ---

    def test_list_in_list_out(self):
        result = self.s.merge([[2.0, 3.0]], base=[1.0, 1.0])
        assert isinstance(result, list)

    def test_numpy_in_numpy_out(self):
        a = np.array([2.0, 3.0])
        base = np.array([1.0, 1.0])
        result = self.s.merge([a], base=base)
        assert isinstance(result, np.ndarray)

    # --- properties ---

    def test_name(self):
        assert self.s.name == "task_arithmetic"

    def test_category(self):
        assert self.s.category == "task_vector"

    def test_paper_reference(self):
        assert "Ilharco" in self.s.paper_reference

    def test_crdt_properties_declared(self):
        props = self.s.crdt_properties
        assert props["commutative"] is True
        assert props["associative"] is True
        assert props["idempotent"] is False


# ===================================================================
# LinearInterpolation
# ===================================================================

class TestLinearInterpolation:
    """Tests for the LinearInterpolation (LERP) strategy."""

    def setup_method(self):
        self.s = LinearInterpolation()

    # --- basic merges ---

    def test_two_models_default_t(self):
        a = [0.0, 0.0]
        b = [10.0, 10.0]
        result = self.s.merge([a, b])
        assert _approx(result, [5.0, 5.0])

    def test_two_models_custom_t(self):
        a = [0.0, 0.0]
        b = [10.0, 10.0]
        result = self.s.merge([a, b], t=0.3)
        assert _approx(result, [3.0, 3.0])

    def test_t_zero_returns_first(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = self.s.merge([a, b], t=0.0)
        assert _approx(result, a)

    def test_t_one_returns_second(self):
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = self.s.merge([a, b], t=1.0)
        assert _approx(result, b)

    def test_three_models_pairwise(self):
        a = [0.0]
        b = [10.0]
        c = [20.0]
        result = self.s.merge([a, b, c], t=0.5)
        # First: lerp(0, 10, 0.5) = 5.0
        # Then:  lerp(5, 20, 0.5) = 12.5
        assert _approx(result, [12.5])

    def test_single_model(self):
        a = [5.0, 6.0]
        result = self.s.merge([a])
        assert result == [5.0, 6.0]

    def test_empty_tensors(self):
        result = self.s.merge([])
        assert result == []

    # --- CRDT properties ---

    def test_commutativity_at_t_half(self):
        rng = random.Random(SEED)
        for _ in range(10):
            a = [rng.random() for _ in range(10)]
            b = [rng.random() for _ in range(10)]
            ab = self.s.merge([a, b], t=0.5)
            ba = self.s.merge([b, a], t=0.5)
            assert _approx(ab, ba), "LERP not commutative at t=0.5"

    def test_not_commutative_at_t_not_half(self):
        a = [0.0]
        b = [10.0]
        ab = self.s.merge([a, b], t=0.3)
        ba = self.s.merge([b, a], t=0.3)
        # ab = 3.0, ba = 7.0, not equal
        assert not _approx(ab, ba)

    def test_idempotency(self):
        a = [3.0, 7.0, 1.5]
        result = self.s.merge([a, a], t=0.5)
        assert _approx(result, a)

    # --- type preservation ---

    def test_list_in_list_out(self):
        result = self.s.merge([[1.0, 2.0], [3.0, 4.0]])
        assert isinstance(result, list)

    def test_numpy_in_numpy_out(self):
        a = np.array([1.0, 2.0])
        b = np.array([3.0, 4.0])
        result = self.s.merge([a, b])
        assert isinstance(result, np.ndarray)

    # --- properties ---

    def test_name(self):
        assert self.s.name == "linear"

    def test_category(self):
        assert self.s.category == "interpolation"

    def test_paper_reference(self):
        assert "Wortsman" in self.s.paper_reference

    def test_crdt_properties_declared(self):
        props = self.s.crdt_properties
        assert props["commutative"] == "conditional"
        assert props["associative"] is False
        assert props["idempotent"] is True


# ===================================================================
# Integration Tests
# ===================================================================

class TestRegistryIntegration:
    """All 4 strategies are accessible via the registry."""

    def test_weight_average_registered(self):
        s = get_strategy("weight_average")
        assert isinstance(s, WeightAverage)

    def test_slerp_registered(self):
        s = get_strategy("slerp")
        assert isinstance(s, SphericalLinearInterpolation)

    def test_task_arithmetic_registered(self):
        s = get_strategy("task_arithmetic")
        assert isinstance(s, TaskArithmetic)

    def test_linear_registered(self):
        s = get_strategy("linear")
        assert isinstance(s, LinearInterpolation)

    def test_all_four_in_list(self):
        names = list_strategies()
        for expected in ("weight_average", "slerp", "task_arithmetic", "linear"):
            assert expected in names, f"{expected} not in registry"

    def test_unknown_strategy_raises(self):
        with pytest.raises(KeyError):
            get_strategy("nonexistent_strategy_xyz")


class TestModelCRDTIntegration:
    """Integration with ModelCRDT and ModelMergeSchema."""

    def test_model_crdt_weight_average(self):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        crdt = ModelCRDT(schema)
        model_a = {"layer1": [1.0, 2.0], "layer2": [3.0, 4.0]}
        model_b = {"layer1": [3.0, 4.0], "layer2": [5.0, 6.0]}
        result = crdt.merge([model_a, model_b])
        assert _approx(result.tensor["layer1"], [2.0, 3.0])
        assert _approx(result.tensor["layer2"], [4.0, 5.0])

    def test_model_crdt_linear(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        crdt = ModelCRDT(schema)
        model_a = {"w": [0.0, 0.0]}
        model_b = {"w": [10.0, 10.0]}
        result = crdt.merge([model_a, model_b], t=0.5)
        assert _approx(result.tensor["w"], [5.0, 5.0])

    def test_model_crdt_slerp(self):
        schema = ModelMergeSchema(strategies={"default": "slerp"})
        crdt = ModelCRDT(schema)
        model_a = {"w": [1.0, 0.0]}
        model_b = {"w": [0.0, 1.0]}
        result = crdt.merge([model_a, model_b], t=0.5)
        r = result.tensor["w"]
        assert len(r) == 2
        # Both components should be near cos(45°) ≈ 0.707
        assert abs(r[0] - r[1]) < 0.01

    def test_model_crdt_task_arithmetic(self):
        schema = ModelMergeSchema(strategies={"default": "task_arithmetic"})
        crdt = ModelCRDT(schema)
        base = {"w": [0.0, 0.0]}
        model_a = {"w": [1.0, 0.0]}
        model_b = {"w": [0.0, 1.0]}
        result = crdt.merge([model_a, model_b], base_model=base)
        assert _approx(result.tensor["w"], [1.0, 1.0])

    def test_model_crdt_mixed_strategies(self):
        """Different layers use different strategies."""
        schema = ModelMergeSchema(strategies={
            "attn.*": "weight_average",
            "mlp.*": "linear",
            "default": "weight_average",
        })
        crdt = ModelCRDT(schema)
        model_a = {"attn.q": [2.0], "mlp.w": [0.0]}
        model_b = {"attn.q": [4.0], "mlp.w": [10.0]}
        result = crdt.merge([model_a, model_b], t=0.5)
        assert _approx(result.tensor["attn.q"], [3.0])
        assert _approx(result.tensor["mlp.w"], [5.0])


class TestProvenanceTracking:
    """Provenance tracking with each strategy."""

    def test_provenance_weight_average(self):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        crdt = ModelCRDT(schema)
        model_a = {"layer": [1.0, 2.0]}
        model_b = {"layer": [3.0, 4.0]}
        result = crdt.merge_with_provenance([model_a, model_b])
        assert result.provenance is not None
        assert "layer" in result.provenance
        prov = result.provenance["layer"]
        assert prov["strategy"] == "weight_average"
        assert prov["num_sources"] == 2

    def test_provenance_linear(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        crdt = ModelCRDT(schema)
        model_a = {"w": [1.0]}
        model_b = {"w": [2.0]}
        result = crdt.merge_with_provenance([model_a, model_b], t=0.5)
        prov = result.provenance["w"]
        assert prov["strategy"] == "linear"

    def test_provenance_slerp(self):
        schema = ModelMergeSchema(strategies={"default": "slerp"})
        crdt = ModelCRDT(schema)
        model_a = {"w": [1.0, 0.0]}
        model_b = {"w": [0.0, 1.0]}
        result = crdt.merge_with_provenance([model_a, model_b], t=0.5)
        prov = result.provenance["w"]
        assert prov["strategy"] == "slerp"

    def test_provenance_task_arithmetic(self):
        schema = ModelMergeSchema(strategies={"default": "task_arithmetic"})
        crdt = ModelCRDT(schema)
        base = {"w": [0.0]}
        model_a = {"w": [1.0]}
        model_b = {"w": [2.0]}
        result = crdt.merge_with_provenance([model_a, model_b], base_model=base)
        prov = result.provenance["w"]
        assert prov["strategy"] == "task_arithmetic"
        assert prov["num_sources"] == 2

    def test_provenance_has_weights(self):
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        crdt = ModelCRDT(schema)
        model_a = {"w": [1.0]}
        model_b = {"w": [2.0]}
        result = crdt.merge_with_provenance([model_a, model_b], weights=[0.3, 0.7])
        prov = result.provenance["w"]
        assert "weights" in prov
        assert abs(sum(prov["weights"]) - 1.0) < 1e-6


class TestLargePerformance:
    """Performance tests with large tensors."""

    def test_weight_average_10k(self):
        a = list(range(10000))
        b = list(range(10000, 20000))
        s = WeightAverage()
        result = s.merge([a, b])
        assert len(result) == 10000
        assert _approx([result[0]], [5000.0])

    def test_weight_average_10k_numpy(self):
        a = np.arange(10000, dtype=float)
        b = np.arange(10000, 20000, dtype=float)
        s = WeightAverage()
        result = s.merge([a, b])
        assert len(result) == 10000
        assert isinstance(result, np.ndarray)

    def test_linear_10k(self):
        a = np.zeros(10000)
        b = np.ones(10000)
        s = LinearInterpolation()
        result = s.merge([a, b], t=0.5)
        assert isinstance(result, np.ndarray)
        assert abs(result.mean() - 0.5) < 1e-6

    def test_slerp_10k(self):
        rng = np.random.RandomState(42)
        a = rng.rand(10000) + 0.1
        b = rng.rand(10000) + 0.1
        s = SphericalLinearInterpolation()
        result = s.merge([a, b], t=0.5)
        assert isinstance(result, np.ndarray)
        assert len(result) == 10000

    def test_task_arithmetic_10k(self):
        base = np.zeros(10000)
        a = np.ones(10000)
        b = np.ones(10000) * 2
        s = TaskArithmetic()
        result = s.merge([a, b], base=base)
        assert isinstance(result, np.ndarray)
        assert abs(result.mean() - 3.0) < 1e-6


class TestEdgeCases:
    """Cross-strategy edge case tests."""

    def test_all_strategies_handle_single_element(self):
        a = [42.0]
        b = [84.0]
        for name in ("weight_average", "slerp", "linear"):
            s = get_strategy(name)
            result = s.merge([a, b])
            assert len(result) == 1

    def test_task_arithmetic_single_element_with_base(self):
        s = get_strategy("task_arithmetic")
        result = s.merge([[10.0]], base=[5.0])
        assert _approx(result, [10.0])

    def test_all_strategies_are_subclass(self):
        for name in ("weight_average", "slerp", "task_arithmetic", "linear"):
            s = get_strategy(name)
            assert isinstance(s, ModelMergeStrategy)

    def test_verify_crdt_weight_average(self):
        """WeightAverage should pass CRDT verification."""
        s = WeightAverage()
        report = s.verify_crdt(trials=20)
        assert report["commutative"] is True
        assert report["idempotent"] is True

    def test_verify_crdt_slerp_idempotent(self):
        """SLERP should be idempotent."""
        s = SphericalLinearInterpolation()
        # verify_crdt uses default t=0.5 via merge([a,a])
        report = s.verify_crdt(trials=20)
        assert report["idempotent"] is True

    def test_strategies_by_category(self):
        """list_strategies_by_category should group correctly."""
        from crdt_merge.model.strategies import list_strategies_by_category
        cats = list_strategies_by_category()
        assert "averaging" in cats
        assert "interpolation" in cats
        assert "weight_average" in cats["averaging"]

    def test_weight_average_many_models(self):
        """Weight average with 10 models."""
        models = [[float(i)] for i in range(10)]
        s = WeightAverage()
        result = s.merge(models)
        # Uniform average of 0..9 = 4.5
        assert _approx(result, [4.5])

    def test_linear_identical_models(self):
        """LERP of identical models returns the same model."""
        a = [1.0, 2.0, 3.0]
        s = LinearInterpolation()
        result = s.merge([a, a], t=0.7)
        assert _approx(result, a)

    def test_slerp_identical_models(self):
        """SLERP of identical models returns the same model."""
        a = [1.0, 2.0, 3.0]
        s = SphericalLinearInterpolation()
        result = s.merge([a, a], t=0.3)
        assert _approx(result, a, tol=1e-5)
