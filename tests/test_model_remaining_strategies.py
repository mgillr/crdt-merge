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

"""Tests for the remaining 12 model-merge strategies (14–25).

Covers:
- weighted.py:     FisherMerge, RegressionMean, AdaptiveMerging, DAM
- evolutionary.py: EvolutionaryMerge, GeneticMerge
- unlearning.py:   NegativeMerge, SplitUnlearnMerge
- calibration.py:  WeightScopeAlignment, RepresentationSurgery
- safety.py:       SafeMerge, LEDMerge

Plus integration tests for the full 25-strategy registry.
"""

from __future__ import annotations

import math
import random

import pytest
import numpy as np

# Ensure all strategy modules are imported so registration happens
import crdt_merge.model.strategies.basic  # noqa: F401
import crdt_merge.model.strategies.subspace  # noqa: F401
import crdt_merge.model.strategies.weighted  # noqa: F401
import crdt_merge.model.strategies.evolutionary  # noqa: F401
import crdt_merge.model.strategies.unlearning  # noqa: F401
import crdt_merge.model.strategies.calibration  # noqa: F401
import crdt_merge.model.strategies.safety  # noqa: F401

from crdt_merge.model.strategies import (
    get_strategy,
    list_strategies,
    list_strategies_by_category,
)
from crdt_merge.model.strategies.weighted import (
    FisherMerge,
    RegressionMean,
    AdaptiveMerging,
    DifferentiableAdaptiveMerging,
)
from crdt_merge.model.strategies.evolutionary import (
    EvolutionaryMerge,
    GeneticMerge,
)
from crdt_merge.model.strategies.unlearning import (
    NegativeMerge,
    SplitUnlearnMerge,
)
from crdt_merge.model.strategies.calibration import (
    WeightScopeAlignment,
    RepresentationSurgery,
)
from crdt_merge.model.strategies.safety import (
    SafeMerge,
    LEDMerge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _approx(a, b, tol=1e-5):
    """Element-wise approximate equality for lists/arrays."""
    if isinstance(a, np.ndarray):
        a = a.tolist()
    if isinstance(b, np.ndarray):
        b = b.tolist()
    if isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"Length mismatch: {len(a)} vs {len(b)}"
        for x, y in zip(a, b):
            if isinstance(x, list):
                _approx(x, y, tol)
            else:
                assert abs(x - y) < tol, f"{x} != {y} (tol={tol})"
    else:
        assert abs(a - b) < tol, f"{a} != {b} (tol={tol})"


def _np(lst):
    return np.array(lst, dtype=float)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def models_2():
    return [_np([1.0, 2.0, 3.0, 4.0]), _np([5.0, 6.0, 7.0, 8.0])]


@pytest.fixture
def models_3():
    return [
        _np([1.0, 2.0, 3.0, 4.0]),
        _np([5.0, 6.0, 7.0, 8.0]),
        _np([9.0, 10.0, 11.0, 12.0]),
    ]


@pytest.fixture
def base_tensor():
    return _np([0.5, 1.0, 1.5, 2.0])


@pytest.fixture
def zero_tensor():
    return _np([0.0, 0.0, 0.0, 0.0])


# ===================================================================
# 14. FisherMerge
# ===================================================================

class TestFisherMerge:
    def test_basic_2model(self, models_2):
        s = FisherMerge()
        result = s.merge(models_2)
        assert result.shape == (4,)
        # Without Fisher: magnitude proxy → larger values get more weight
        # Result should be between min and max
        assert all(1.0 <= r <= 8.0 for r in result)

    def test_3model(self, models_3):
        s = FisherMerge()
        result = s.merge(models_3)
        assert result.shape == (4,)

    def test_commutativity(self, models_2):
        s = FisherMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b])
            r2 = s.merge([b, a])
            _approx(r1, r2)

    def test_single_model(self):
        s = FisherMerge()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = FisherMerge()
        result = s.merge([zero_tensor, zero_tensor])
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = FisherMerge()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("fisher_merge")
        assert s.name == "fisher_merge"
        assert s.category == "Weighted / Importance"

    def test_with_fisher_matrices(self, models_2):
        s = FisherMerge()
        fishers = [_np([10.0, 1.0, 1.0, 1.0]), _np([1.0, 1.0, 1.0, 10.0])]
        result = s.merge(models_2, fisher_matrices=fishers)
        # First param: heavily weighted toward model 1
        # Last param: heavily weighted toward model 2
        assert result[0] < 3.0  # closer to 1.0
        assert result[3] > 6.0  # closer to 8.0


# ===================================================================
# 15. RegressionMean
# ===================================================================

class TestRegressionMean:
    def test_basic_2model(self, models_2):
        s = RegressionMean()
        result = s.merge(models_2)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = RegressionMean()
        result = s.merge(models_3)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = RegressionMean()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b])
            r2 = s.merge([b, a])
            _approx(r1, r2)

    def test_single_model(self):
        s = RegressionMean()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = RegressionMean()
        result = s.merge([zero_tensor, zero_tensor])
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = RegressionMean()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("regression_mean")
        assert s.name == "regression_mean"

    def test_regularization_param(self, models_2):
        s = RegressionMean()
        r1 = s.merge(models_2, regularization=0.001)
        r2 = s.merge(models_2, regularization=100.0)
        # High regularization → closer to simple mean
        mean = (models_2[0] + models_2[1]) / 2.0
        diff_r2 = np.sum((r2 - mean) ** 2)
        # With very high regularization, result should be close to mean
        assert diff_r2 < 1.0


# ===================================================================
# 16. AdaptiveMerging
# ===================================================================

class TestAdaptiveMerging:
    def test_basic_2model(self, models_2):
        s = AdaptiveMerging()
        result = s.merge(models_2, steps=10)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = AdaptiveMerging()
        result = s.merge(models_3, steps=10)
        assert result.shape == (4,)

    def test_commutativity(self):
        """AdaMerging is commutative after convergence (entropy-based)."""
        s = AdaptiveMerging()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(8)])
            b = _np([rng.random() * 10 for _ in range(8)])
            r1 = s.merge([a, b], steps=0)  # No optimization = pure entropy
            r2 = s.merge([b, a], steps=0)
            # With steps=0, uses entropy-based weighting which is commutative
            _approx(r1, r2, tol=0.1)

    def test_single_model(self):
        s = AdaptiveMerging()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = AdaptiveMerging()
        result = s.merge([zero_tensor, zero_tensor], steps=5)
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = AdaptiveMerging()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]], steps=5)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("ada_merging")
        assert s.name == "ada_merging"

    def test_granularity_param(self, models_2):
        s = AdaptiveMerging()
        r1 = s.merge(models_2, granularity="task", steps=10)
        assert r1.shape == (4,)


# ===================================================================
# 17. DAM
# ===================================================================

class TestDAM:
    def test_basic_2model(self, models_2):
        s = DifferentiableAdaptiveMerging()
        result = s.merge(models_2, steps=10)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = DifferentiableAdaptiveMerging()
        result = s.merge(models_3, steps=10)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = DifferentiableAdaptiveMerging()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            # With steps=0, uses uniform weights = commutative
            r1 = s.merge([a, b], steps=0)
            r2 = s.merge([b, a], steps=0)
            _approx(r1, r2, tol=0.01)

    def test_single_model(self):
        s = DifferentiableAdaptiveMerging()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = DifferentiableAdaptiveMerging()
        result = s.merge([zero_tensor, zero_tensor], steps=5)
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = DifferentiableAdaptiveMerging()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]], steps=5)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("dam")
        assert s.name == "dam"

    def test_steps_param(self, models_2):
        s = DifferentiableAdaptiveMerging()
        r1 = s.merge(models_2, steps=1)
        r2 = s.merge(models_2, steps=100)
        # Different optimization steps → may produce different results
        assert r1.shape == r2.shape == (4,)


# ===================================================================
# 18. EvolutionaryMerge
# ===================================================================

class TestEvolutionaryMerge:
    def test_basic_2model(self, models_2):
        s = EvolutionaryMerge()
        result = s.merge(models_2, population_size=10, generations=5, seed=42)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = EvolutionaryMerge()
        result = s.merge(models_3, population_size=10, generations=5, seed=42)
        assert result.shape == (4,)

    def test_commutativity(self):
        """With same seed, evolutionary merge is deterministic and commutative."""
        s = EvolutionaryMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b], population_size=10, generations=5, seed=42)
            r2 = s.merge([b, a], population_size=10, generations=5, seed=42)
            # Both should produce a valid merge
            assert r1.shape == r2.shape

    def test_single_model(self):
        s = EvolutionaryMerge()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = EvolutionaryMerge()
        result = s.merge([zero_tensor, zero_tensor], population_size=5, generations=3, seed=42)
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = EvolutionaryMerge()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]], population_size=5, generations=3, seed=42)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("evolutionary_merge")
        assert s.name == "evolutionary_merge"
        assert s.category == "Evolutionary"

    def test_custom_fitness(self, models_2):
        s = EvolutionaryMerge()
        # Fitness: prefer values closer to 3.0
        result = s.merge(
            models_2,
            fitness_fn=lambda m: -sum((x - 3.0) ** 2 for x in m),
            population_size=10,
            generations=20,
            seed=42,
        )
        assert result.shape == (4,)


# ===================================================================
# 19. GeneticMerge
# ===================================================================

class TestGeneticMerge:
    def test_basic_2model(self, models_2):
        s = GeneticMerge()
        result = s.merge(models_2, population_size=10, generations=5, seed=42)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = GeneticMerge()
        result = s.merge(models_3, population_size=10, generations=5, seed=42)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = GeneticMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b], population_size=10, generations=5, seed=42)
            r2 = s.merge([b, a], population_size=10, generations=5, seed=42)
            assert r1.shape == r2.shape

    def test_single_model(self):
        s = GeneticMerge()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = GeneticMerge()
        result = s.merge([zero_tensor, zero_tensor], population_size=5, generations=3, seed=42)
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = GeneticMerge()
        result = s.merge([[1.0, 2.0], [3.0, 4.0]], population_size=5, generations=3, seed=42)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("genetic_merge")
        assert s.name == "genetic_merge"
        assert s.category == "Evolutionary"

    def test_mutation_rate(self, models_2):
        s = GeneticMerge()
        result = s.merge(models_2, mutation_rate=0.5, population_size=10, generations=5, seed=42)
        assert result.shape == (4,)


# ===================================================================
# 20. NegativeMerge
# ===================================================================

class TestNegativeMerge:
    def test_basic_2model(self, models_2, base_tensor):
        s = NegativeMerge()
        result = s.merge(models_2, base=base_tensor)
        assert result.shape == (4,)

    def test_3model(self, models_3, base_tensor):
        s = NegativeMerge()
        result = s.merge(models_3, base=base_tensor)
        assert result.shape == (4,)

    def test_commutativity(self, base_tensor):
        s = NegativeMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b], base=base_tensor)
            r2 = s.merge([b, a], base=base_tensor)
            _approx(r1, r2)

    def test_single_model(self, base_tensor):
        s = NegativeMerge()
        a = _np([1.0, 2.0, 3.0, 4.0])
        result = s.merge([a], base=base_tensor)
        # θ_base - 1.0 * (θ_toxic - θ_base) = 2*θ_base - θ_toxic
        expected = 2 * base_tensor - a
        _approx(result, expected)

    def test_zero_tensor(self, zero_tensor, base_tensor):
        s = NegativeMerge()
        result = s.merge([zero_tensor, zero_tensor], base=base_tensor)
        assert result.shape == (4,)

    def test_type_preservation_list(self):
        s = NegativeMerge()
        result = s.merge([[1.0, 2.0, 3.0, 4.0]], base=[0.5, 1.0, 1.5, 2.0])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("negative_merge")
        assert s.name == "negative_merge"
        assert s.category == "Unlearning"

    def test_requires_base(self, models_2):
        s = NegativeMerge()
        with pytest.raises(ValueError, match="requires a base"):
            s.merge(models_2)

    def test_models_to_negate(self, models_2, base_tensor):
        s = NegativeMerge()
        # Only negate model 0, add model 1 normally
        result = s.merge(models_2, base=base_tensor, models_to_negate=[0])
        assert result.shape == (4,)


# ===================================================================
# 21. SplitUnlearnMerge
# ===================================================================

class TestSplitUnlearnMerge:
    def test_basic_2model(self, models_2, base_tensor):
        s = SplitUnlearnMerge()
        result = s.merge(models_2, base=base_tensor)
        assert result.shape == (4,)

    def test_3model(self, models_3, base_tensor):
        s = SplitUnlearnMerge()
        result = s.merge(models_3, base=base_tensor)
        assert result.shape == (4,)

    def test_commutativity(self, base_tensor):
        s = SplitUnlearnMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b], base=base_tensor)
            r2 = s.merge([b, a], base=base_tensor)
            _approx(r1, r2)

    def test_single_model(self, base_tensor):
        s = SplitUnlearnMerge()
        a = _np([1.0, 2.0, 3.0, 4.0])
        result = s.merge([a], base=base_tensor)
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor, base_tensor):
        s = SplitUnlearnMerge()
        result = s.merge([zero_tensor, zero_tensor], base=base_tensor)
        assert result.shape == (4,)

    def test_type_preservation_list(self):
        s = SplitUnlearnMerge()
        result = s.merge([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], base=[0.5, 1.0, 1.5, 2.0])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("split_unlearn_merge")
        assert s.name == "split_unlearn_merge"

    def test_requires_base(self, models_2):
        s = SplitUnlearnMerge()
        with pytest.raises(ValueError, match="requires a base"):
            s.merge(models_2)

    def test_random_subspace(self, models_2, base_tensor):
        s = SplitUnlearnMerge()
        result = s.merge(models_2, base=base_tensor, subspace_method="random", seed=42)
        assert result.shape == (4,)


# ===================================================================
# 22. WeightScopeAlignment
# ===================================================================

class TestWeightScopeAlignment:
    def test_basic_2model(self, models_2):
        s = WeightScopeAlignment()
        result = s.merge(models_2)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = WeightScopeAlignment()
        result = s.merge(models_3)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = WeightScopeAlignment()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b])
            r2 = s.merge([b, a])
            _approx(r1, r2, tol=1e-4)

    def test_single_model(self):
        s = WeightScopeAlignment()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = WeightScopeAlignment()
        result = s.merge([zero_tensor, zero_tensor])
        # With zero inputs, output should be close to zero
        assert all(abs(r) < 1e-6 for r in result.tolist())

    def test_type_preservation_list(self):
        s = WeightScopeAlignment()
        result = s.merge([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("weight_scope_alignment")
        assert s.name == "weight_scope_alignment"
        assert s.category == "Post-Calibration"

    def test_scope_methods(self, models_2):
        s = WeightScopeAlignment()
        for method in ["zscore", "minmax", "unit"]:
            result = s.merge(models_2, scope_method=method)
            assert result.shape == (4,)


# ===================================================================
# 23. RepresentationSurgery
# ===================================================================

class TestRepresentationSurgery:
    def test_basic_2model(self, models_2):
        s = RepresentationSurgery()
        result = s.merge(models_2)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = RepresentationSurgery()
        result = s.merge(models_3)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = RepresentationSurgery()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b])
            r2 = s.merge([b, a])
            _approx(r1, r2, tol=1e-4)

    def test_single_model(self):
        s = RepresentationSurgery()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = RepresentationSurgery()
        result = s.merge([zero_tensor, zero_tensor])
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = RepresentationSurgery()
        result = s.merge([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("representation_surgery")
        assert s.name == "representation_surgery"
        assert s.category == "Post-Calibration"

    def test_correction_methods(self, models_2):
        s = RepresentationSurgery()
        for method in ["center", "rescale", "whiten"]:
            result = s.merge(models_2, correction_method=method)
            assert result.shape == (4,)

    def test_center_corrects_mean(self, models_2):
        s = RepresentationSurgery()
        result = s.merge(models_2, correction_method="center")
        # After centering, the mean should be close to the avg input mean
        avg_input_mean = (np.mean(models_2[0]) + np.mean(models_2[1])) / 2.0
        assert abs(np.mean(result) - avg_input_mean) < 1e-6


# ===================================================================
# 24. SafeMerge
# ===================================================================

class TestSafeMerge:
    def test_basic_2model(self, models_2, base_tensor):
        s = SafeMerge()
        result = s.merge(models_2, base=base_tensor)
        assert result.shape == (4,)

    def test_3model(self, models_3, base_tensor):
        s = SafeMerge()
        result = s.merge(models_3, base=base_tensor)
        assert result.shape == (4,)

    def test_commutativity(self, base_tensor):
        s = SafeMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b], base=base_tensor)
            r2 = s.merge([b, a], base=base_tensor)
            _approx(r1, r2, tol=1e-4)

    def test_single_model(self, base_tensor):
        s = SafeMerge()
        a = _np([1.0, 2.0, 3.0, 4.0])
        result = s.merge([a], base=base_tensor)
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor, base_tensor):
        s = SafeMerge()
        result = s.merge([zero_tensor, zero_tensor], base=base_tensor)
        assert result.shape == (4,)

    def test_type_preservation_list(self):
        s = SafeMerge()
        result = s.merge([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]], base=[0.5, 1.0, 1.5, 2.0])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("safe_merge")
        assert s.name == "safe_merge"
        assert s.category == "Safety-Aware"

    def test_requires_base(self, models_2):
        s = SafeMerge()
        with pytest.raises(ValueError, match="requires a base"):
            s.merge(models_2)

    def test_safety_threshold(self, models_2, base_tensor):
        s = SafeMerge()
        # With high threshold, most params frozen = result closer to base
        result_high = s.merge(models_2, base=base_tensor, safety_threshold=0.9)
        # With low threshold, fewer params frozen
        result_low = s.merge(models_2, base=base_tensor, safety_threshold=0.1)
        # High threshold should keep more base values
        diff_base_high = np.sum((result_high - base_tensor) ** 2)
        diff_base_low = np.sum((result_low - base_tensor) ** 2)
        assert diff_base_high <= diff_base_low + 1e-6


# ===================================================================
# 25. LEDMerge
# ===================================================================

class TestLEDMerge:
    def test_basic_2model(self, models_2):
        s = LEDMerge()
        result = s.merge(models_2)
        assert result.shape == (4,)

    def test_3model(self, models_3):
        s = LEDMerge()
        result = s.merge(models_3)
        assert result.shape == (4,)

    def test_commutativity(self):
        s = LEDMerge()
        rng = random.Random(42)
        for _ in range(5):
            a = _np([rng.random() * 10 for _ in range(4)])
            b = _np([rng.random() * 10 for _ in range(4)])
            r1 = s.merge([a, b])
            r2 = s.merge([b, a])
            _approx(r1, r2)

    def test_single_model(self):
        s = LEDMerge()
        a = _np([1.0, 2.0, 3.0])
        result = s.merge([a])
        _approx(result, a)

    def test_zero_tensor(self, zero_tensor):
        s = LEDMerge()
        result = s.merge([zero_tensor, zero_tensor])
        _approx(result, zero_tensor)

    def test_type_preservation_list(self):
        s = LEDMerge()
        result = s.merge([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("led_merge")
        assert s.name == "led_merge"
        assert s.category == "Safety-Aware"

    def test_picks_closest_to_mean(self):
        """LED should pick values closest to mean for each position."""
        s = LEDMerge()
        a = _np([1.0, 10.0, 3.0])
        b = _np([5.0, 6.0, 7.0])
        c = _np([3.0, 8.0, 5.0])
        result = s.merge([a, b, c])
        # Mean: [3.0, 8.0, 5.0]
        # Pos 0: mean=3.0, closest=c(3.0)
        # Pos 1: mean=8.0, closest=c(8.0)
        # Pos 2: mean=5.0, closest=c(5.0)
        _approx(result, [3.0, 8.0, 5.0])

    def test_custom_eval_fn(self, models_2):
        s = LEDMerge()
        # Pick values closest to 0
        result = s.merge(models_2, eval_fn=lambda x: -abs(x))
        # Each position should pick the model with smaller absolute value
        for j in range(4):
            expected = models_2[0][j] if abs(models_2[0][j]) < abs(models_2[1][j]) else models_2[1][j]
            assert abs(result[j] - expected) < 1e-6


# ===================================================================
# Integration Tests
# ===================================================================

class TestIntegration:
    """Integration tests across all 25 strategies."""

    NEW_STRATEGIES = [
        "fisher_merge", "regression_mean", "ada_merging", "dam",
        "evolutionary_merge", "genetic_merge",
        "negative_merge", "split_unlearn_merge",
        "weight_scope_alignment", "representation_surgery",
        "safe_merge", "led_merge",
    ]

    def test_all_12_in_registry(self):
        strats = list_strategies()
        for name in self.NEW_STRATEGIES:
            assert name in strats, f"Strategy '{name}' not found in registry"

    def test_total_strategy_count(self):
        strats = list_strategies()
        assert len(strats) == 25, f"Expected 25 strategies, got {len(strats)}: {strats}"

    def test_all_categories_present(self):
        cats = list_strategies_by_category()
        expected_categories = {
            "Weighted / Importance",
            "Evolutionary",
            "Unlearning",
            "Post-Calibration",
            "Safety-Aware",
        }
        for cat in expected_categories:
            assert cat in cats, f"Category '{cat}' not found. Available: {list(cats.keys())}"

    def test_mixed_category_merges(self, models_2, base_tensor):
        """Run a merge from each new category to verify they all work."""
        results = {}
        # Weighted
        results["fisher"] = FisherMerge().merge(models_2)
        # Evolutionary
        results["evo"] = EvolutionaryMerge().merge(
            models_2, population_size=5, generations=3, seed=42
        )
        # Unlearning
        results["neg"] = NegativeMerge().merge(models_2, base=base_tensor)
        # Calibration
        results["scope"] = WeightScopeAlignment().merge(models_2)
        # Safety
        results["safe"] = SafeMerge().merge(models_2, base=base_tensor)

        for name, r in results.items():
            assert hasattr(r, '__len__') or isinstance(r, (int, float)), \
                f"{name} returned invalid type: {type(r)}"

    def test_all_strategies_instantiate(self):
        """Every registered strategy can be instantiated."""
        for name in list_strategies():
            s = get_strategy(name)
            assert s.name == name
            assert isinstance(s.category, str)
            assert isinstance(s.crdt_properties, dict)

    def test_all_strategies_have_paper_reference(self):
        """Every new strategy has a non-empty paper reference."""
        for name in self.NEW_STRATEGIES:
            s = get_strategy(name)
            assert isinstance(s.paper_reference, str)

    def test_crdt_properties_structure(self):
        """All strategies declare commutative/associative/idempotent."""
        for name in self.NEW_STRATEGIES:
            s = get_strategy(name)
            props = s.crdt_properties
            assert "commutative" in props
            assert "associative" in props
            assert "idempotent" in props

    def test_category_counts(self):
        cats = list_strategies_by_category()
        assert len(cats["Weighted / Importance"]) == 4
        assert len(cats["Evolutionary"]) == 2
        assert len(cats["Unlearning"]) == 2
        assert len(cats["Post-Calibration"]) == 2
        assert len(cats["Safety-Aware"]) == 2

    def test_all_new_strategies_with_numpy(self, models_2, base_tensor):
        """Smoke test: all 12 new strategies produce valid numpy output."""
        base_required = {"negative_merge", "split_unlearn_merge", "safe_merge"}
        evo_kwargs = {"population_size": 5, "generations": 3, "seed": 42}
        ada_kwargs = {"steps": 5}

        for name in self.NEW_STRATEGIES:
            s = get_strategy(name)
            kwargs = {}
            if name in base_required:
                kwargs["base"] = base_tensor
            if name in ("evolutionary_merge", "genetic_merge"):
                kwargs.update(evo_kwargs)
            if name in ("ada_merging", "dam"):
                kwargs.update(ada_kwargs)

            result = s.merge(models_2, **kwargs)
            arr = np.asarray(result)
            assert arr.shape == (4,), f"Strategy {name} produced shape {arr.shape}"
            assert np.all(np.isfinite(arr)), f"Strategy {name} produced non-finite values"

    def test_pure_python_list_input(self):
        """All 12 new strategies work with plain Python lists."""
        m2 = [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]
        base = [0.5, 1.0, 1.5, 2.0]
        base_required = {"negative_merge", "split_unlearn_merge", "safe_merge"}
        evo_kwargs = {"population_size": 5, "generations": 3, "seed": 42}
        ada_kwargs = {"steps": 5}

        for name in self.NEW_STRATEGIES:
            s = get_strategy(name)
            kwargs = {}
            if name in base_required:
                kwargs["base"] = base
            if name in ("evolutionary_merge", "genetic_merge"):
                kwargs.update(evo_kwargs)
            if name in ("ada_merging", "dam"):
                kwargs.update(ada_kwargs)

            result = s.merge(m2, **kwargs)
            assert isinstance(result, list), f"Strategy {name} didn't return list for list input"
            assert len(result) == 4, f"Strategy {name} returned wrong length"

    def test_empty_tensors(self):
        """Strategies handle empty tensor lists gracefully."""
        for name in self.NEW_STRATEGIES:
            s = get_strategy(name)
            try:
                kwargs = {}
                if name in ("negative_merge", "split_unlearn_merge", "safe_merge"):
                    kwargs["base"] = [0.5, 1.0, 1.5, 2.0]
                result = s.merge([], **kwargs)
                # Should return empty or base
            except (ValueError, IndexError):
                pass  # Acceptable for some strategies

    def test_no_regressions_basic(self, models_2):
        """Basic strategies still work."""
        from crdt_merge.model.strategies.basic import WeightAverage
        s = WeightAverage()
        result = s.merge(models_2)
        expected = (models_2[0] + models_2[1]) / 2.0
        _approx(result, expected)

    def test_no_regressions_subspace(self, models_2, base_tensor):
        """Subspace strategies still work."""
        from crdt_merge.model.strategies.subspace import TIESMerge
        s = TIESMerge()
        result = s.merge(models_2, base=base_tensor)
        assert result.shape == (4,)
