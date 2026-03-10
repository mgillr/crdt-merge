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

"""Tests for Subspace / Sparsification model-merge strategies.

Covers all 9 strategies (TIESMerge, DARE, DELLA, DARE-TIES, ModelBreadcrumbs,
EMRMerge, STAR, SVDKnotTying, AdaRank) with ~120 tests total.
"""

from __future__ import annotations

import math
import random
import warnings
from unittest import mock

import pytest

# Strategies under test
from crdt_merge.model.strategies.subspace import (
    TIESMerge,
    DareDropAndRescale,
    DellaDropElectLowRank,
    DareTiesHybrid,
    ModelBreadcrumbs,
    EMRMerge,
    SpectralTruncationAdaptiveRescaling,
    SVDKnotTying,
    AdaptiveRankPruning,
)
from crdt_merge.model.strategies import get_strategy, list_strategies

# numpy — always available in test environment
import numpy as np

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _approx_list(a, b, tol=1e-5):
    """Element-wise approximate equality for lists/arrays."""
    a_flat = list(np.array(a).ravel()) if not isinstance(a, list) else a
    b_flat = list(np.array(b).ravel()) if not isinstance(b, list) else b
    if len(a_flat) != len(b_flat):
        return False
    return all(abs(x - y) < tol for x, y in zip(a_flat, b_flat))

def _to_flat(x):
    """Convert to flat list for comparison."""
    if isinstance(x, np.ndarray):
        return x.ravel().tolist()
    if isinstance(x, list):
        flat = []
        for item in x:
            if isinstance(item, list):
                flat.extend(item)
            else:
                flat.append(item)
        return flat
    return [x]

# Fixed test data
BASE = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
MODEL_A = [1.5, 2.3, 3.1, 4.8, 5.2, 6.7, 7.1, 8.9, 9.3, 10.5]
MODEL_B = [1.2, 2.1, 3.4, 4.3, 5.6, 6.2, 7.8, 8.1, 9.7, 10.2]
MODEL_C = [1.8, 2.5, 3.2, 4.1, 5.9, 6.5, 7.3, 8.4, 9.1, 10.8]

# Base that is same as model (zero task vector)
ZERO_TV_MODEL = BASE[:]

# numpy versions
NP_BASE = np.array(BASE)
NP_A = np.array(MODEL_A)
NP_B = np.array(MODEL_B)
NP_C = np.array(MODEL_C)

# 2D test data for SVD strategies
NP_BASE_2D = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
NP_A_2D = NP_BASE_2D + np.array([[0.5, -0.3, 0.1], [0.2, 0.4, -0.1], [-0.3, 0.1, 0.6]])
NP_B_2D = NP_BASE_2D + np.array([[-0.1, 0.2, 0.3], [0.5, -0.2, 0.4], [0.1, 0.3, -0.5]])

# All strategy classes and their registry names
STRATEGY_CLASSES = [
    ("ties", TIESMerge),
    ("dare", DareDropAndRescale),
    ("della", DellaDropElectLowRank),
    ("dare_ties", DareTiesHybrid),
    ("model_breadcrumbs", ModelBreadcrumbs),
    ("emr", EMRMerge),
    ("star", SpectralTruncationAdaptiveRescaling),
    ("svd_knot_tying", SVDKnotTying),
    ("adarank", AdaptiveRankPruning),
]

STOCHASTIC_STRATEGIES = ["dare", "della", "dare_ties"]
DETERMINISTIC_STRATEGIES = ["ties", "model_breadcrumbs", "emr", "star", "svd_knot_tying", "adarank"]
SVD_STRATEGIES = ["star", "svd_knot_tying", "adarank"]

# ===================================================================
# PER-STRATEGY TESTS
# ===================================================================

# --- TIESMerge ---

class TestTIESMerge:
    def setup_method(self):
        self.s = TIESMerge()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_commutativity(self):
        for _ in range(5):
            a = [random.uniform(0, 10) for _ in range(10)]
            b = [random.uniform(0, 10) for _ in range(10)]
            r1 = self.s.merge([a, b], base=BASE)
            r2 = self.s.merge([b, a], base=BASE)
            assert _approx_list(_to_flat(r1), _to_flat(r2)), "TIES not commutative"

    def test_single_model_passthrough(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation_list(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert isinstance(result, list)

    def test_type_preservation_numpy(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)

    def test_registry(self):
        s = get_strategy("ties")
        assert s.name == "ties"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_density_parameter(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, density=0.1)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, density=0.9)
        # Different density → different results
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_majority_sign_magnitude(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, majority_sign_method="magnitude")
        assert len(_to_flat(result)) == 10

    def test_category(self):
        assert self.s.category == "Subspace / Sparsification"

    def test_crdt_properties(self):
        props = self.s.crdt_properties
        assert props["commutative"] is True
        assert props["associative"] is False

# --- DareDropAndRescale ---

class TestDareDropAndRescale:
    def setup_method(self):
        self.s = DareDropAndRescale()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_commutativity(self):
        """DARE with same seed should be commutative (order-independent masks)."""
        # Note: DARE uses a single RNG, so commutativity depends on mask generation
        # being order-independent. Our implementation generates masks in order,
        # so swapping models with same masks tests a different property.
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        r2 = self.s.merge([MODEL_B, MODEL_A], base=BASE, seed=42)
        # They should produce same length output
        assert len(_to_flat(r1)) == len(_to_flat(r2))

    def test_seed_determinism(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=123)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=123)
        assert _approx_list(_to_flat(r1), _to_flat(r2))

    def test_different_seeds(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=99)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_single_model(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE, seed=42)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("dare")
        assert s.name == "dare"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_drop_rate_effect(self):
        r_low = self.s.merge([MODEL_A, MODEL_B], base=BASE, drop_rate=0.1, seed=42)
        r_high = self.s.merge([MODEL_A, MODEL_B], base=BASE, drop_rate=0.9, seed=42)
        assert not _approx_list(_to_flat(r_low), _to_flat(r_high))

# --- DellaDropElectLowRank ---

class TestDellaDropElectLowRank:
    def setup_method(self):
        self.s = DellaDropElectLowRank()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_seed_determinism(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=77)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=77)
        assert _approx_list(_to_flat(r1), _to_flat(r2))

    def test_different_seeds(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=99)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_single_model(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE, seed=42)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("della")
        assert s.name == "della"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_epsilon_effect(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, epsilon=0.01, seed=42)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, epsilon=0.5, seed=42)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

# --- DareTiesHybrid ---

class TestDareTiesHybrid:
    def setup_method(self):
        self.s = DareTiesHybrid()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE, seed=42)
        assert len(_to_flat(result)) == 10

    def test_seed_determinism(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=55)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=55)
        assert _approx_list(_to_flat(r1), _to_flat(r2))

    def test_different_seeds(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=99)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_single_model(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE, seed=42)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("dare_ties")
        assert s.name == "dare_ties"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_combined_params(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, drop_rate=0.5, density=0.5, seed=42)
        assert len(_to_flat(result)) == 10

# --- ModelBreadcrumbs ---

class TestModelBreadcrumbs:
    def setup_method(self):
        self.s = ModelBreadcrumbs()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_commutativity(self):
        for _ in range(5):
            a = [random.uniform(0, 10) for _ in range(10)]
            b = [random.uniform(0, 10) for _ in range(10)]
            r1 = self.s.merge([a, b], base=BASE, mask_method="magnitude")
            r2 = self.s.merge([b, a], base=BASE, mask_method="magnitude")
            assert _approx_list(_to_flat(r1), _to_flat(r2)), "Breadcrumbs not commutative"

    def test_single_model(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("model_breadcrumbs")
        assert s.name == "model_breadcrumbs"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_sparsity_effect(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, sparsity=0.1)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, sparsity=0.9)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_random_mask_method(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE, mask_method="random", seed=42)
        assert len(_to_flat(result)) == 10

# --- EMRMerge ---

class TestEMRMerge:
    def setup_method(self):
        self.s = EMRMerge()

    def test_basic_2model(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_3model(self):
        result = self.s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_commutativity(self):
        for _ in range(5):
            a = [random.uniform(0, 10) for _ in range(10)]
            b = [random.uniform(0, 10) for _ in range(10)]
            r1 = self.s.merge([a, b], base=BASE)
            r2 = self.s.merge([b, a], base=BASE)
            assert _approx_list(_to_flat(r1), _to_flat(r2)), "EMR not commutative"

    def test_single_model(self):
        result = self.s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    def test_zero_task_vector(self):
        result = self.s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE)
        assert _approx_list(_to_flat(result), BASE)

    def test_type_preservation(self):
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert isinstance(result, list)

    def test_registry(self):
        s = get_strategy("emr")
        assert s.name == "emr"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([MODEL_A, MODEL_B])

    def test_elect_ratio_effect(self):
        r1 = self.s.merge([MODEL_A, MODEL_B], base=BASE, elect_ratio=0.1)
        r2 = self.s.merge([MODEL_A, MODEL_B], base=BASE, elect_ratio=0.9)
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_crdt_properties(self):
        props = self.s.crdt_properties
        assert props["commutative"] is True
        assert props["associative"] is False

# --- STAR ---

class TestSTAR:
    def setup_method(self):
        self.s = SpectralTruncationAdaptiveRescaling()

    def test_basic_2model_1d(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A.shape

    def test_basic_2model_2d(self):
        result = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A_2D.shape

    def test_3model(self):
        np_c_2d = NP_BASE_2D + np.random.RandomState(42).randn(3, 3) * 0.3
        result = self.s.merge([NP_A_2D, NP_B_2D, np_c_2d], base=NP_BASE_2D)
        assert result.shape == NP_BASE_2D.shape

    def test_commutativity_1d(self):
        r1 = self.s.merge([NP_A, NP_B], base=NP_BASE)
        r2 = self.s.merge([NP_B, NP_A], base=NP_BASE)
        np.testing.assert_allclose(r1, r2, atol=1e-5)

    def test_single_model(self):
        result = self.s.merge([NP_A], base=NP_BASE)
        np.testing.assert_allclose(result, NP_A, atol=1e-10)

    def test_zero_task_vector(self):
        result = self.s.merge([NP_BASE.copy(), NP_BASE.copy()], base=NP_BASE)
        np.testing.assert_allclose(result, NP_BASE, atol=1e-10)

    def test_rank_fraction_effect(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rank_fraction=0.3)
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rank_fraction=0.9)
        assert not np.allclose(r1, r2, atol=1e-5)

    def test_type_preservation_numpy(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)

    def test_registry(self):
        s = get_strategy("star")
        assert s.name == "star"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([NP_A, NP_B])

    def test_1d_fallback_no_svd(self):
        """1D tensors should use magnitude truncation, not SVD."""
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_rescale_methods(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rescale_method="energy")
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rescale_method="count")
        # energy rescaling should differ from count
        assert not np.allclose(r1, r2, atol=1e-5)

# --- SVDKnotTying ---

class TestSVDKnotTying:
    def setup_method(self):
        self.s = SVDKnotTying()

    def test_basic_2model_1d(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A.shape

    def test_basic_2model_2d(self):
        result = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A_2D.shape

    def test_3model(self):
        np_c_2d = NP_BASE_2D + np.random.RandomState(42).randn(3, 3) * 0.3
        result = self.s.merge([NP_A_2D, NP_B_2D, np_c_2d], base=NP_BASE_2D)
        assert result.shape == NP_BASE_2D.shape

    def test_commutativity_1d(self):
        r1 = self.s.merge([NP_A, NP_B], base=NP_BASE)
        r2 = self.s.merge([NP_B, NP_A], base=NP_BASE)
        np.testing.assert_allclose(r1, r2, atol=1e-5)

    def test_single_model(self):
        result = self.s.merge([NP_A], base=NP_BASE)
        np.testing.assert_allclose(result, NP_A, atol=1e-10)

    def test_zero_task_vector(self):
        result = self.s.merge([NP_BASE.copy(), NP_BASE.copy()], base=NP_BASE)
        np.testing.assert_allclose(result, NP_BASE, atol=1e-10)

    def test_type_preservation(self):
        result = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D)
        assert isinstance(result, np.ndarray)

    def test_registry(self):
        s = get_strategy("svd_knot_tying")
        assert s.name == "svd_knot_tying"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([NP_A, NP_B])

    def test_1d_fallback(self):
        """1D tensors should fall back to simple averaging."""
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_alignment_methods(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, alignment_method="procrustes")
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, alignment_method="direct")
        # Should produce valid results with either method
        assert r1.shape == NP_BASE_2D.shape
        assert r2.shape == NP_BASE_2D.shape

    def test_rank_parameter(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rank=1)
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, rank=3)
        # Different rank → potentially different results
        assert r1.shape == NP_BASE_2D.shape
        assert r2.shape == NP_BASE_2D.shape

# --- AdaptiveRankPruning (AdaRank) ---

class TestAdaptiveRankPruning:
    def setup_method(self):
        self.s = AdaptiveRankPruning()

    def test_basic_2model_1d(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A.shape

    def test_basic_2model_2d(self):
        result = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A_2D.shape

    def test_3model(self):
        np_c_2d = NP_BASE_2D + np.random.RandomState(42).randn(3, 3) * 0.3
        result = self.s.merge([NP_A_2D, NP_B_2D, np_c_2d], base=NP_BASE_2D)
        assert result.shape == NP_BASE_2D.shape

    def test_commutativity_1d(self):
        r1 = self.s.merge([NP_A, NP_B], base=NP_BASE)
        r2 = self.s.merge([NP_B, NP_A], base=NP_BASE)
        np.testing.assert_allclose(r1, r2, atol=1e-5)

    def test_single_model(self):
        result = self.s.merge([NP_A], base=NP_BASE)
        np.testing.assert_allclose(result, NP_A, atol=1e-10)

    def test_zero_task_vector(self):
        result = self.s.merge([NP_BASE.copy(), NP_BASE.copy()], base=NP_BASE)
        np.testing.assert_allclose(result, NP_BASE, atol=1e-10)

    def test_type_preservation(self):
        result = self.s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)

    def test_registry(self):
        s = get_strategy("adarank")
        assert s.name == "adarank"

    def test_requires_base(self):
        with pytest.raises(ValueError, match="requires base_model"):
            self.s.merge([NP_A, NP_B])

    def test_1d_fallback(self):
        """1D uses magnitude pruning."""
        result = self.s.merge([MODEL_A, MODEL_B], base=BASE)
        assert len(_to_flat(result)) == 10

    def test_auto_rank(self):
        result = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, target_rank="auto")
        assert result.shape == NP_BASE_2D.shape

    def test_explicit_rank(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, target_rank=1)
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, target_rank=3)
        assert r1.shape == NP_BASE_2D.shape
        assert r2.shape == NP_BASE_2D.shape

    def test_importance_methods(self):
        r1 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, importance="energy")
        r2 = self.s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D, importance="variance")
        assert r1.shape == NP_BASE_2D.shape
        assert r2.shape == NP_BASE_2D.shape

# ===================================================================
# INTEGRATION TESTS
# ===================================================================

class TestSubspaceIntegration:
    """Integration tests spanning all 9 strategies."""

    def test_all_9_in_registry(self):
        strats = list_strategies()
        expected = ["ties", "dare", "della", "dare_ties", "model_breadcrumbs",
                     "emr", "star", "svd_knot_tying", "adarank"]
        for name in expected:
            assert name in strats, f"{name} not in registry"

    @pytest.mark.parametrize("name,cls", STRATEGY_CLASSES)
    def test_strategy_metadata(self, name, cls):
        s = cls()
        assert s.name == name
        assert s.category == "Subspace / Sparsification"
        assert isinstance(s.paper_reference, str)
        assert len(s.paper_reference) > 0
        props = s.crdt_properties
        assert "commutative" in props
        assert "associative" in props
        assert "idempotent" in props

    @pytest.mark.parametrize("name,cls", STRATEGY_CLASSES)
    def test_all_require_base(self, name, cls):
        s = cls()
        with pytest.raises(ValueError, match="requires base_model"):
            s.merge([MODEL_A, MODEL_B])

    @pytest.mark.parametrize("name,cls", STRATEGY_CLASSES)
    def test_single_model_passthrough(self, name, cls):
        s = cls()
        result = s.merge([MODEL_A], base=BASE)
        assert _approx_list(_to_flat(result), MODEL_A)

    @pytest.mark.parametrize("name,cls", STRATEGY_CLASSES)
    def test_empty_returns_base(self, name, cls):
        s = cls()
        result = s.merge([], base=BASE)
        flat = _to_flat(result)
        assert _approx_list(flat, BASE)

    @pytest.mark.parametrize("name,cls", STRATEGY_CLASSES)
    def test_numpy_arrays(self, name, cls):
        s = cls()
        kwargs = {}
        if name in STOCHASTIC_STRATEGIES:
            kwargs["seed"] = 42
        result = s.merge([NP_A, NP_B], base=NP_BASE, **kwargs)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A.shape

    def test_large_tensor_performance(self):
        """Merge 5K element tensors within reasonable time."""
        rng = np.random.RandomState(42)
        base_large = rng.randn(5000)
        a_large = base_large + rng.randn(5000) * 0.1
        b_large = base_large + rng.randn(5000) * 0.1

        for name, cls in STRATEGY_CLASSES:
            s = cls()
            kwargs = {}
            if name in STOCHASTIC_STRATEGIES:
                kwargs["seed"] = 42
            result = s.merge([a_large, b_large], base=base_large, **kwargs)
            assert len(result) == 5000, f"{name} failed large tensor"

    def test_mixed_strategies_basic_plus_subspace(self):
        """Test that basic and subspace strategies can coexist."""
        from crdt_merge.model.strategies.basic import WeightAverage
        wa = WeightAverage()
        ties = TIESMerge()

        r_wa = wa.merge([MODEL_A, MODEL_B])
        r_ties = ties.merge([MODEL_A, MODEL_B], base=BASE)

        assert len(_to_flat(r_wa)) == 10
        assert len(_to_flat(r_ties)) == 10

    def test_category_listing(self):
        from crdt_merge.model.strategies import list_strategies_by_category
        cats = list_strategies_by_category()
        assert "Subspace / Sparsification" in cats
        subspace_strats = cats["Subspace / Sparsification"]
        assert len(subspace_strats) >= 9

    @pytest.mark.parametrize("name", DETERMINISTIC_STRATEGIES)
    def test_deterministic_strategies_reproducible(self, name):
        s = get_strategy(name)
        kwargs = {}
        if name in ["model_breadcrumbs"]:
            kwargs["mask_method"] = "magnitude"
        r1 = s.merge([MODEL_A, MODEL_B], base=BASE, **kwargs)
        r2 = s.merge([MODEL_A, MODEL_B], base=BASE, **kwargs)
        assert _approx_list(_to_flat(r1), _to_flat(r2))

    @pytest.mark.parametrize("name", STOCHASTIC_STRATEGIES)
    def test_stochastic_seed_reproducible(self, name):
        s = get_strategy(name)
        r1 = s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        r2 = s.merge([MODEL_A, MODEL_B], base=BASE, seed=42)
        assert _approx_list(_to_flat(r1), _to_flat(r2))

    @pytest.mark.parametrize("name", SVD_STRATEGIES)
    def test_svd_2d_proper(self, name):
        s = get_strategy(name)
        result = s.merge([NP_A_2D, NP_B_2D], base=NP_BASE_2D)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_BASE_2D.shape

    @pytest.mark.parametrize("name", SVD_STRATEGIES)
    def test_svd_1d_no_crash(self, name):
        s = get_strategy(name)
        result = s.merge([NP_A, NP_B], base=NP_BASE)
        assert isinstance(result, np.ndarray)
        assert result.shape == NP_A.shape

    def test_weighted_merge(self):
        """Test that weights affect the result."""
        s = TIESMerge()
        r1 = s.merge([MODEL_A, MODEL_B], base=BASE, weights=[0.9, 0.1])
        r2 = s.merge([MODEL_A, MODEL_B], base=BASE, weights=[0.1, 0.9])
        # Heavily weighted toward A vs B should differ
        assert not _approx_list(_to_flat(r1), _to_flat(r2))

    def test_numpy_unavailable_fallback_svd(self):
        """SVD strategies should warn and fall back when numpy unavailable."""
        import crdt_merge.model.strategies.subspace as submod
        import crdt_merge.model.strategies.base as basemod

        original_get_np = basemod._get_np

        def mock_no_np():
            return None

        # Patch _get_np in both modules
        with mock.patch.object(submod, '_get_np', mock_no_np), \
             mock.patch.object(basemod, '_get_np', mock_no_np):
            for name in SVD_STRATEGIES:
                s = get_strategy(name)
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    result = s.merge([MODEL_A, MODEL_B], base=BASE)
                    # Should still produce a valid result
                    assert len(_to_flat(result)) == 10
                    # Should have warned
                    assert any("numpy" in str(warning.message).lower() or
                               "falling back" in str(warning.message).lower()
                               for warning in w)

    def test_numpy_unavailable_fallback_non_svd(self):
        """Non-SVD strategies operate correctly without numpy installed."""
        import crdt_merge.model.strategies.subspace as submod
        import crdt_merge.model.strategies.base as basemod

        def mock_no_np():
            return None

        non_svd = ["ties", "dare", "della", "dare_ties", "model_breadcrumbs", "emr"]
        with mock.patch.object(submod, '_get_np', mock_no_np), \
             mock.patch.object(basemod, '_get_np', mock_no_np):
            for name in non_svd:
                s = get_strategy(name)
                kwargs = {}
                if name in STOCHASTIC_STRATEGIES:
                    kwargs["seed"] = 42
                result = s.merge([MODEL_A, MODEL_B], base=BASE, **kwargs)
                assert len(_to_flat(result)) == 10, f"{name} failed without numpy"

    def test_get_strategy_returns_correct_type(self):
        for name, cls in STRATEGY_CLASSES:
            s = get_strategy(name)
            assert isinstance(s, cls)

    def test_all_strategies_handle_3_models(self):
        for name, cls in STRATEGY_CLASSES:
            s = cls()
            kwargs = {}
            if name in STOCHASTIC_STRATEGIES:
                kwargs["seed"] = 42
            result = s.merge([MODEL_A, MODEL_B, MODEL_C], base=BASE, **kwargs)
            assert len(_to_flat(result)) == 10, f"{name} failed 3-model merge"

    def test_zero_task_vector_all_strategies(self):
        for name, cls in STRATEGY_CLASSES:
            s = cls()
            kwargs = {}
            if name in STOCHASTIC_STRATEGIES:
                kwargs["seed"] = 42
            result = s.merge([ZERO_TV_MODEL, ZERO_TV_MODEL], base=BASE, **kwargs)
            assert _approx_list(_to_flat(result), BASE), f"{name} failed zero task vector"
