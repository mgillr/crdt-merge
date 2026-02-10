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

"""Weighted / Importance model-merge strategies.

Implements 4 strategies:

14. FisherMerge          — Fisher-weighted averaging
15. RegressionMean       — Closed-form regression mean (RegMean)
16. AdaptiveMerging      — Entropy-based adaptive coefficients (AdaMerging)
17. DifferentiableAdaptiveMerging — Gradient-free coefficient optimization (DAM)
"""

from __future__ import annotations

import math
import random as _random_module
from typing import Any, Callable, Dict, List, Optional

from crdt_merge.model.strategies import register_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _from_array,
    _get_np,
    _normalize_weights,
    _to_array,
)

__all__ = [
    "FisherMerge",
    "RegressionMean",
    "AdaptiveMerging",
    "DifferentiableAdaptiveMerging",
]

# ---------------------------------------------------------------------------
# Pure-Python vector helpers
# ---------------------------------------------------------------------------

def _py_add(a: list, b: list) -> list:
    return [x + y for x, y in zip(a, b)]

def _py_scale(a: list, s: float) -> list:
    return [x * s for x in a]

def _py_zeros(n: int) -> list:
    return [0.0] * n

def _py_mul(a: list, b: list) -> list:
    """Element-wise multiplication."""
    return [x * y for x, y in zip(a, b)]

def _flatten(arr: Any):
    """Flatten array-like to 1-D. Returns (flat, shape)."""
    np = _get_np()
    if np is not None and isinstance(arr, np.ndarray):
        return arr.ravel().astype(float), arr.shape
    if isinstance(arr, list) and arr and isinstance(arr[0], list):
        flat: list = []
        rows = len(arr)
        cols = len(arr[0]) if arr else 0
        for row in arr:
            flat.extend(row)
        return flat, (rows, cols)
    if isinstance(arr, list):
        return [float(x) for x in arr], None
    return arr, None

def _unflatten(flat: Any, shape):
    if shape is None:
        return flat
    np = _get_np()
    if np is not None and isinstance(flat, np.ndarray):
        return flat.reshape(shape)
    if isinstance(shape, tuple) and len(shape) == 2:
        rows, cols = shape
        return [flat[i * cols:(i + 1) * cols] for i in range(rows)]
    return flat

# ===================================================================
# 14. FisherMerge
# ===================================================================

@register_strategy("fisher_merge")
class FisherMerge(ModelMergeStrategy):
    """Fisher-weighted averaging (Matena & Raffel, 2022).

    ``θ = Σ(Fᵢ · θᵢ) / Σ(Fᵢ)`` where Fᵢ is the diagonal Fisher
    information matrix for model *i*.

    If no Fisher matrices are provided, falls back to magnitude-based
    importance: ``Fᵢ ≈ |θᵢ|²``.

    .. note:: CRDT compliance

       Commutative and idempotent but **not associative** under pairwise
       composition — the magnitude-based Fisher proxy ``|θ|²`` changes
       when computed on an intermediate merge result vs. the original
       tensors.  For correct N-way Fisher merging, pass all models in a
       single ``merge(...)`` call.
    """

    @property
    def name(self) -> str:
        return "fisher_merge"

    @property
    def category(self) -> str:
        return "Weighted / Importance"

    @property
    def paper_reference(self) -> str:
        return "Matena & Raffel, 2022 — Merging Models with Fisher-Weighted Averaging"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": False, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        fisher_matrices: Optional[list] = kwargs.get("fisher_matrices", None)
        compute_fisher: bool = kwargs.get("compute_fisher", False)
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]

            # Compute or use Fisher matrices
            if fisher_matrices is not None:
                fishers = [_to_array(f).astype(float) for f in fisher_matrices]
            else:
                # Magnitude-based proxy: |θ|²
                fishers = [a ** 2 for a in arrs]

            # Weighted sum: Σ(Fᵢ · θᵢ) / Σ(Fᵢ)
            numerator = np.zeros_like(arrs[0])
            denominator = np.zeros_like(arrs[0])
            for a, f in zip(arrs, fishers):
                numerator += f * a
                denominator += f

            # Avoid division by zero
            denominator = np.maximum(denominator, 1e-12)
            result = numerator / denominator
            return _from_array(result, original)
        else:
            # Pure Python
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])

            if fisher_matrices is not None:
                fishers = []
                for f in fisher_matrices:
                    ff, _ = _flatten(_to_array(f))
                    fishers.append(ff)
            else:
                fishers = [[x * x for x in flat] for flat in flats]

            numerator = _py_zeros(d)
            denominator = _py_zeros(d)
            for flat, fisher in zip(flats, fishers):
                numerator = _py_add(numerator, _py_mul(fisher, flat))
                denominator = _py_add(denominator, fisher)

            result = [n / max(den, 1e-12) for n, den in zip(numerator, denominator)]
            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)

# ===================================================================
# 15. RegressionMean (RegMean)
# ===================================================================

@register_strategy("regression_mean")
class RegressionMean(ModelMergeStrategy):
    """RegMean: Dataless knowledge fusion via regularized regression mean (Jin et al., 2023).

    Simplified diagonal case:
    ``θ = (Σ θᵢᵀθᵢ + λI)⁻¹ · Σ(θᵢᵀθᵢ · θᵢ)``

    For 1D parameters this reduces to a regularized weighted average where
    weights are proportional to θᵢ² + λ.

    .. note:: CRDT compliance

       Commutative and idempotent but **not associative** under pairwise
       composition — the self-weighted regression ``θᵢ² + λ`` changes
       when computed on an intermediate merge vs. original tensors.
       For correct N-way RegMean, pass all models in a single
       ``merge(...)`` call.
    """

    @property
    def name(self) -> str:
        return "regression_mean"

    @property
    def category(self) -> str:
        return "Weighted / Importance"

    @property
    def paper_reference(self) -> str:
        return "Jin et al., 2023 — Dataless Knowledge Fusion by Merging Weights"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": False, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        regularization: float = kwargs.get("regularization", 0.01)
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]
            # Diagonal approximation: weight_i = θᵢ² + λ
            # numerator = Σ weight_i * θᵢ, denominator = Σ weight_i
            numerator = np.zeros_like(arrs[0])
            denominator = np.zeros_like(arrs[0])
            for a in arrs:
                w_i = a ** 2 + regularization
                numerator += w_i * a
                denominator += w_i

            denominator = np.maximum(denominator, 1e-12)
            result = numerator / denominator
            return _from_array(result, original)
        else:
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])
            numerator = _py_zeros(d)
            denominator = _py_zeros(d)
            for flat in flats:
                w_i = [x * x + regularization for x in flat]
                numerator = _py_add(numerator, _py_mul(w_i, flat))
                denominator = _py_add(denominator, w_i)

            result = [n / max(den, 1e-12) for n, den in zip(numerator, denominator)]
            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)

# ===================================================================
# 16. AdaptiveMerging (AdaMerging)
# ===================================================================

@register_strategy("ada_merging")
class AdaptiveMerging(ModelMergeStrategy):
    """AdaMerging: Entropy-based adaptive merge coefficients (Yang et al., 2024).

    Without calibration data, uses an entropy-based heuristic on weight
    distributions to determine per-model merge coefficients.
    """

    @property
    def name(self) -> str:
        return "ada_merging"

    @property
    def category(self) -> str:
        return "Weighted / Importance"

    @property
    def paper_reference(self) -> str:
        return "Yang et al., 2024 — AdaMerging: Adaptive Model Merging"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": "conditional", "associative": "conditional", "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        granularity: str = kwargs.get("granularity", "task")
        learning_rate: float = kwargs.get("learning_rate", 0.01)
        steps: int = kwargs.get("steps", 100)
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]
            n = len(arrs)

            # Compute entropy-based importance per model
            entropies = []
            for a in arrs:
                flat = a.ravel()
                # Normalize to probability-like distribution
                abs_flat = np.abs(flat) + 1e-12
                p = abs_flat / abs_flat.sum()
                # Shannon entropy
                ent = -np.sum(p * np.log(p + 1e-12))
                entropies.append(ent)

            # Lower entropy → more peaked distribution → higher importance
            max_ent = max(entropies) if entropies else 1.0
            if max_ent < 1e-12:
                coeffs = [1.0 / n] * n
            else:
                inv_ent = [(max_ent - e + 1e-6) for e in entropies]
                total = sum(inv_ent)
                coeffs = [ie / total for ie in inv_ent]

            # Iterative refinement (simple gradient-free optimization)
            coeffs_arr = np.array(coeffs)
            for _ in range(steps):
                # Compute current merge
                merged = np.zeros_like(arrs[0])
                for c, a in zip(coeffs_arr, arrs):
                    merged += c * a

                # Compute variance of merged from each input
                variances = []
                for a in arrs:
                    variances.append(np.mean((merged - a) ** 2))

                # Adjust coefficients: decrease weight of high-variance models
                if max(variances) > 0:
                    inv_var = np.array([1.0 / (v + 1e-12) for v in variances])
                    target = inv_var / inv_var.sum()
                    coeffs_arr = coeffs_arr + learning_rate * (target - coeffs_arr)
                    # Re-normalize
                    coeffs_arr = np.maximum(coeffs_arr, 0.0)
                    total_c = coeffs_arr.sum()
                    if total_c > 0:
                        coeffs_arr = coeffs_arr / total_c

            result = np.zeros_like(arrs[0])
            for c, a in zip(coeffs_arr, arrs):
                result += c * a
            return _from_array(result, original)
        else:
            # Pure Python: entropy-based weighted average
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])
            n = len(flats)

            # Compute entropy per model
            entropies = []
            for flat in flats:
                abs_flat = [abs(x) + 1e-12 for x in flat]
                total_abs = sum(abs_flat)
                p = [a / total_abs for a in abs_flat]
                ent = -sum(pi * math.log(pi + 1e-12) for pi in p)
                entropies.append(ent)

            max_ent = max(entropies) if entropies else 1.0
            if max_ent < 1e-12:
                coeffs = [1.0 / n] * n
            else:
                inv_ent = [(max_ent - e + 1e-6) for e in entropies]
                total = sum(inv_ent)
                coeffs = [ie / total for ie in inv_ent]

            result = _py_zeros(d)
            for c, flat in zip(coeffs, flats):
                result = _py_add(result, _py_scale(flat, c))

            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)

# ===================================================================
# 17. DifferentiableAdaptiveMerging (DAM)
# ===================================================================

@register_strategy("dam")
class DifferentiableAdaptiveMerging(ModelMergeStrategy):
    """DAM: Differentiable Adaptive Merging via gradient-free coefficient optimization (2024).

    Optimizes merge coefficients to minimize output variance using a
    simple grid search / iterative refinement approach.
    """

    @property
    def name(self) -> str:
        return "dam"

    @property
    def category(self) -> str:
        return "Weighted / Importance"

    @property
    def paper_reference(self) -> str:
        return "2024 — Differentiable Adaptive Merging (DAM)"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": "conditional", "associative": "conditional", "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        learning_rate: float = kwargs.get("learning_rate", 0.01)
        steps: int = kwargs.get("steps", 50)
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]
            n = len(arrs)

            # Start with uniform coefficients
            coeffs = np.ones(n) / n

            for step in range(steps):
                # Current merged result
                merged = np.zeros_like(arrs[0])
                for c, a in zip(coeffs, arrs):
                    merged += c * a

                # Compute variance of merged output
                overall_var = np.var(merged)

                # Per-model distance to merged
                distances = []
                for a in arrs:
                    distances.append(np.mean((merged - a) ** 2))

                # Update: move coefficients toward models closer to merged
                if max(distances) > 0:
                    inv_dist = np.array([1.0 / (d + 1e-12) for d in distances])
                    target = inv_dist / inv_dist.sum()
                    coeffs = coeffs + learning_rate * (target - coeffs)
                    coeffs = np.maximum(coeffs, 0.0)
                    total_c = coeffs.sum()
                    if total_c > 0:
                        coeffs = coeffs / total_c

            result = np.zeros_like(arrs[0])
            for c, a in zip(coeffs, arrs):
                result += c * a
            return _from_array(result, original)
        else:
            # Pure Python fallback
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])
            n = len(flats)
            coeffs = [1.0 / n] * n

            for step in range(steps):
                merged = _py_zeros(d)
                for c, flat in zip(coeffs, flats):
                    merged = _py_add(merged, _py_scale(flat, c))

                distances = []
                for flat in flats:
                    dist = sum((m - f) ** 2 for m, f in zip(merged, flat)) / d
                    distances.append(dist)

                max_dist = max(distances)
                if max_dist > 0:
                    inv_dist = [1.0 / (dd + 1e-12) for dd in distances]
                    total_inv = sum(inv_dist)
                    target = [idd / total_inv for idd in inv_dist]
                    coeffs = [c + learning_rate * (t - c) for c, t in zip(coeffs, target)]
                    coeffs = [max(0.0, c) for c in coeffs]
                    total_c = sum(coeffs)
                    if total_c > 0:
                        coeffs = [c / total_c for c in coeffs]

            result = _py_zeros(d)
            for c, flat in zip(coeffs, flats):
                result = _py_add(result, _py_scale(flat, c))

            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)
