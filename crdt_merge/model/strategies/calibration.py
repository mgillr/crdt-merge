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

"""Post-Calibration model-merge strategies.

Implements 2 strategies:

22. WeightScopeAlignment    — Normalize weight distributions, align scopes, merge
23. RepresentationSurgery   — Post-merge representation correction
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies import register_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _from_array,
    _get_np,
    _normalize_weights,
    _to_array,
)


# ---------------------------------------------------------------------------
# Pure-Python vector helpers
# ---------------------------------------------------------------------------

def _py_add(a: list, b: list) -> list:
    return [x + y for x, y in zip(a, b)]


def _py_sub(a: list, b: list) -> list:
    return [x - y for x, y in zip(a, b)]


def _py_scale(a: list, s: float) -> list:
    return [x * s for x in a]


def _py_zeros(n: int) -> list:
    return [0.0] * n


def _py_mean(a: list) -> float:
    return sum(a) / len(a) if a else 0.0


def _py_std(a: list) -> float:
    if len(a) < 2:
        return 0.0
    m = _py_mean(a)
    return math.sqrt(sum((x - m) ** 2 for x in a) / len(a))


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
# 22. WeightScopeAlignment
# ===================================================================

@register_strategy("weight_scope_alignment")
class WeightScopeAlignment(ModelMergeStrategy):
    """Weight Scope Alignment: Normalize weight distributions → align → merge (2024).

    Normalizes each model's parameters to a target scope (z-score, min-max,
    or unit norm), averages in normalized space, then rescales to the
    target distribution.
    """

    @property
    def name(self) -> str:
        return "weight_scope_alignment"

    @property
    def category(self) -> str:
        return "Post-Calibration"

    @property
    def paper_reference(self) -> str:
        return "2024 — Weight Distribution Scope Alignment"

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

        scope_method: str = kwargs.get("scope_method", "zscore")
        target_distribution: str = kwargs.get("target_distribution", "mean")
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]

            # Compute target distribution stats
            if target_distribution == "first":
                target_mean = np.mean(arrs[0])
                target_std = np.std(arrs[0])
                target_min = np.min(arrs[0])
                target_max = np.max(arrs[0])
            elif target_distribution == "base" and base is not None:
                base_arr = _to_array(base).astype(float)
                target_mean = np.mean(base_arr)
                target_std = np.std(base_arr)
                target_min = np.min(base_arr)
                target_max = np.max(base_arr)
            else:  # "mean" — average stats across all inputs
                target_mean = np.mean([np.mean(a) for a in arrs])
                target_std = np.mean([np.std(a) for a in arrs])
                target_min = np.mean([np.min(a) for a in arrs])
                target_max = np.mean([np.max(a) for a in arrs])

            # Normalize each model
            normalized = []
            for a in arrs:
                if scope_method == "zscore":
                    m = np.mean(a)
                    s = np.std(a)
                    if s < 1e-12:
                        normalized.append(np.zeros_like(a))
                    else:
                        normalized.append((a - m) / s)
                elif scope_method == "minmax":
                    lo = np.min(a)
                    hi = np.max(a)
                    rng = hi - lo
                    if rng < 1e-12:
                        normalized.append(np.zeros_like(a))
                    else:
                        normalized.append((a - lo) / rng)
                else:  # "unit"
                    norm = np.linalg.norm(a)
                    if norm < 1e-12:
                        normalized.append(np.zeros_like(a))
                    else:
                        normalized.append(a / norm)

            # Average in normalized space
            merged_norm = np.zeros_like(arrs[0])
            for w, n_arr in zip(norm_w, normalized):
                merged_norm += w * n_arr

            # Rescale to target distribution
            if scope_method == "zscore":
                target_std_safe = max(target_std, 1e-12)
                result = merged_norm * target_std_safe + target_mean
            elif scope_method == "minmax":
                rng_target = target_max - target_min
                result = merged_norm * rng_target + target_min
            else:  # "unit"
                target_norm = np.mean([np.linalg.norm(a) for a in arrs])
                result = merged_norm * target_norm

            return _from_array(result, original)
        else:
            # Pure Python
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])

            if target_distribution == "first":
                t_mean = _py_mean(flats[0])
                t_std = _py_std(flats[0])
            elif target_distribution == "base" and base is not None:
                bf, _ = _flatten(_to_array(base))
                t_mean = _py_mean(bf)
                t_std = _py_std(bf)
            else:
                t_mean = sum(_py_mean(f) for f in flats) / len(flats)
                t_std = sum(_py_std(f) for f in flats) / len(flats)

            # Normalize
            normalized = []
            for flat in flats:
                m = _py_mean(flat)
                s = _py_std(flat)
                if scope_method == "zscore":
                    if s < 1e-12:
                        normalized.append(_py_zeros(d))
                    else:
                        normalized.append([(x - m) / s for x in flat])
                elif scope_method == "minmax":
                    lo = min(flat)
                    hi = max(flat)
                    rng_val = hi - lo
                    if rng_val < 1e-12:
                        normalized.append(_py_zeros(d))
                    else:
                        normalized.append([(x - lo) / rng_val for x in flat])
                else:  # "unit"
                    norm = math.sqrt(sum(x * x for x in flat))
                    if norm < 1e-12:
                        normalized.append(_py_zeros(d))
                    else:
                        normalized.append([x / norm for x in flat])

            # Average
            merged_norm = _py_zeros(d)
            for w, n_flat in zip(norm_w, normalized):
                merged_norm = _py_add(merged_norm, _py_scale(n_flat, w))

            # Rescale
            t_std_safe = max(t_std, 1e-12)
            result = [x * t_std_safe + t_mean for x in merged_norm]

            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)


# ===================================================================
# 23. RepresentationSurgery
# ===================================================================

@register_strategy("representation_surgery")
class RepresentationSurgery(ModelMergeStrategy):
    """Post-merge representation correction (2024).

    Analyzes the merged distribution, identifies distortions relative
    to the input average, and corrects them.

    Correction methods:
    - ``"center"``: subtract mean drift (merged_mean - avg_input_mean)
    - ``"rescale"``: match variance to average input variance
    - ``"whiten"``: decorrelate (for 2D tensors only)
    """

    @property
    def name(self) -> str:
        return "representation_surgery"

    @property
    def category(self) -> str:
        return "Post-Calibration"

    @property
    def paper_reference(self) -> str:
        return "2024 — Post-Merge Representation Surgery"

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

        correction_method: str = kwargs.get("correction_method", "center")
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]

            # Step 1: Weighted average merge
            merged = np.zeros_like(arrs[0])
            for w, a in zip(norm_w, arrs):
                merged += w * a

            # Step 2: Compute average-of-inputs statistics
            avg_input_mean = np.mean([np.mean(a) for a in arrs])
            avg_input_var = np.mean([np.var(a) for a in arrs])

            # Step 3: Apply correction
            if correction_method == "center":
                drift = np.mean(merged) - avg_input_mean
                result = merged - drift

            elif correction_method == "rescale":
                merged_var = np.var(merged)
                if merged_var < 1e-12:
                    result = merged
                else:
                    scale = math.sqrt(avg_input_var / merged_var)
                    merged_mean = np.mean(merged)
                    result = (merged - merged_mean) * scale + avg_input_mean

            elif correction_method == "whiten":
                if merged.ndim == 2 and min(merged.shape) > 1:
                    # Decorrelate columns
                    merged_mean_vec = np.mean(merged, axis=0)
                    centered = merged - merged_mean_vec
                    cov = centered.T @ centered / max(merged.shape[0] - 1, 1)
                    try:
                        eigenvalues, eigenvectors = np.linalg.eigh(cov)
                        eigenvalues = np.maximum(eigenvalues, 1e-12)
                        whitening = eigenvectors @ np.diag(1.0 / np.sqrt(eigenvalues)) @ eigenvectors.T
                        # Rescale to match original variance
                        target_scale = math.sqrt(avg_input_var) if avg_input_var > 0 else 1.0
                        result = (centered @ whitening) * target_scale + avg_input_mean
                    except np.linalg.LinAlgError:
                        result = merged
                else:
                    # For 1D: fall back to rescale
                    merged_var = np.var(merged)
                    if merged_var < 1e-12:
                        result = merged
                    else:
                        scale = math.sqrt(avg_input_var / merged_var)
                        merged_mean = np.mean(merged)
                        result = (merged - merged_mean) * scale + avg_input_mean
            else:
                result = merged

            return _from_array(result, original)
        else:
            # Pure Python
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])

            # Weighted average
            merged = _py_zeros(d)
            for w, flat in zip(norm_w, flats):
                merged = _py_add(merged, _py_scale(flat, w))

            # Average-of-inputs statistics
            input_means = [_py_mean(f) for f in flats]
            avg_input_mean = sum(input_means) / len(input_means)

            input_vars = [_py_std(f) ** 2 for f in flats]
            avg_input_var = sum(input_vars) / len(input_vars)

            if correction_method == "center":
                drift = _py_mean(merged) - avg_input_mean
                result = [x - drift for x in merged]

            elif correction_method == "rescale":
                merged_var = _py_std(merged) ** 2
                if merged_var < 1e-12:
                    result = merged
                else:
                    scale = math.sqrt(avg_input_var / merged_var)
                    merged_mean = _py_mean(merged)
                    result = [(x - merged_mean) * scale + avg_input_mean for x in merged]

            else:
                # "whiten" falls back to rescale for 1D
                merged_var = _py_std(merged) ** 2
                if merged_var < 1e-12:
                    result = merged
                else:
                    scale = math.sqrt(avg_input_var / merged_var)
                    merged_mean = _py_mean(merged)
                    result = [(x - merged_mean) * scale + avg_input_mean for x in merged]

            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)
