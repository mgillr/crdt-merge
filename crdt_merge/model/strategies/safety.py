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

"""Safety-Aware model-merge strategies.

Implements 2 strategies:

24. SafeMerge   — Freeze safety-critical params, merge rest
25. LEDMerge    — Layer-wise Evaluation-Driven best-source selection
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

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


def _py_scale(a: list, s: float) -> list:
    return [x * s for x in a]


def _py_zeros(n: int) -> list:
    return [0.0] * n


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
# 24. SafeMerge
# ===================================================================

@register_strategy("safe_merge")
class SafeMerge(ModelMergeStrategy):
    """Safety-preserving model merging (2025).

    Identifies safety-critical parameters and freezes them (uses base
    model's values), then merges the remaining parameters via averaging.

    When ``safety_layers="auto"``, identifies safety-critical params
    as those with highest variance across models.
    """

    @property
    def name(self) -> str:
        return "safe_merge"

    @property
    def category(self) -> str:
        return "Safety-Aware"

    @property
    def paper_reference(self) -> str:
        return "2025 — Safety-Preserving Model Merging"

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
        if base is None:
            raise ValueError("SafeMerge requires a base model tensor (base=...)")

        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        safety_threshold: float = kwargs.get("safety_threshold", 0.1)
        base_index: int = kwargs.get("base_index", 0)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        base_arr = _to_array(base)
        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(base_arr, np.ndarray):
            base_f = base_arr.astype(float).ravel()
            d = base_f.size
            shape = base_arr.shape
            arrs = [a.astype(float).ravel() for a in arrays]

            # Compute per-param variance across models
            stacked = [a for a in arrs]
            mean_arr = sum(a for a in stacked) / len(stacked)
            variance = sum((a - mean_arr) ** 2 for a in stacked) / len(stacked)

            # Safety threshold: freeze top safety_threshold fraction of high-variance params
            if variance.max() > 0:
                k = max(1, int(d * safety_threshold))
                sorted_var = sorted(variance)
                threshold = sorted_var[max(0, d - k)]
                safety_mask = variance >= threshold  # True = safety-critical → freeze
            else:
                safety_mask = [False] * d

            # Merge: frozen params use base, rest use weighted average
            merged = sum(w * a for w, a in zip(norm_w, arrs))
            result = []
            for j in range(d):
                if safety_mask[j] if isinstance(safety_mask, list) else safety_mask[j]:
                    result.append(base_f[j])
                else:
                    result.append(merged[j])

            import numpy as np_mod
            result = np_mod.array(result).reshape(shape)
            return _from_array(result, original)
        else:
            b_flat, b_shape = _flatten(base_arr)
            d = len(b_flat)

            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            # Compute per-param variance
            mean_vals = [sum(f[j] for f in flats) / len(flats) for j in range(d)]
            variance = [sum((f[j] - mean_vals[j]) ** 2 for f in flats) / len(flats) for j in range(d)]

            # Safety mask
            max_var = max(variance) if variance else 0
            if max_var > 0:
                k = max(1, int(d * safety_threshold))
                sorted_var = sorted(variance)
                threshold = sorted_var[max(0, d - k)]
                safety_mask = [variance[j] >= threshold for j in range(d)]
            else:
                safety_mask = [False] * d

            # Weighted average
            merged = _py_zeros(d)
            for w, flat in zip(norm_w, flats):
                merged = _py_add(merged, _py_scale(flat, w))

            # Apply safety mask
            result = [b_flat[j] if safety_mask[j] else merged[j] for j in range(d)]

            result = _unflatten(result, b_shape)
            return _from_array(result, original)


# ===================================================================
# 25. LEDMerge (Layer-wise Evaluation-Driven)
# ===================================================================

@register_strategy("led_merge")
class LEDMerge(ModelMergeStrategy):
    """LEDMerge: Layer-wise Evaluation-Driven best-source selection (2025).

    For each parameter position, picks the source closest to the mean
    (lowest L2 distance). With an optional ``eval_fn``, evaluates each
    source per position and picks the best.
    """

    @property
    def name(self) -> str:
        return "led_merge"

    @property
    def category(self) -> str:
        return "Safety-Aware"

    @property
    def paper_reference(self) -> str:
        return "2025 — Layer-wise Evaluation-Driven Merging (LED)"

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

        eval_fn: Optional[Callable] = kwargs.get("eval_fn", None)
        original = tensors[0]
        np = _get_np()

        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float).ravel() for a in arrays]
            d = arrs[0].size
            shape = arrays[0].shape if hasattr(arrays[0], 'shape') else None

            # Compute mean
            mean_arr = sum(a for a in arrs) / len(arrs)

            if eval_fn is not None:
                # Evaluate per-element, pick best (tie-break: smallest value)
                result = []
                for j in range(d):
                    best_val = arrs[0][j]
                    best_score = eval_fn(arrs[0][j])
                    for a in arrs[1:]:
                        score = eval_fn(a[j])
                        if score > best_score or (score == best_score and a[j] < best_val):
                            best_score = score
                            best_val = a[j]
                    result.append(best_val)
                import numpy as np_mod
                result = np_mod.array(result)
            else:
                # Pick source closest to mean per element (tie-break: smallest value)
                result = []
                for j in range(d):
                    best_val = arrs[0][j]
                    best_dist = abs(arrs[0][j] - mean_arr[j])
                    for a in arrs[1:]:
                        dist = abs(a[j] - mean_arr[j])
                        if dist < best_dist or (dist == best_dist and a[j] < best_val):
                            best_dist = dist
                            best_val = a[j]
                    result.append(best_val)
                import numpy as np_mod
                result = np_mod.array(result)

            if shape is not None:
                result = result.reshape(shape)
            return _from_array(result, original)
        else:
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(flats[0])

            # Compute mean
            mean_vals = [sum(f[j] for f in flats) / len(flats) for j in range(d)]

            if eval_fn is not None:
                result = []
                for j in range(d):
                    best_val = flats[0][j]
                    best_score = eval_fn(flats[0][j])
                    for f in flats[1:]:
                        score = eval_fn(f[j])
                        if score > best_score or (score == best_score and f[j] < best_val):
                            best_score = score
                            best_val = f[j]
                    result.append(best_val)
            else:
                result = []
                for j in range(d):
                    best_val = flats[0][j]
                    best_dist = abs(flats[0][j] - mean_vals[j])
                    for f in flats[1:]:
                        dist = abs(f[j] - mean_vals[j])
                        if dist < best_dist or (dist == best_dist and f[j] < best_val):
                            best_dist = dist
                            best_val = f[j]
                    result.append(best_val)

            _, shape = _flatten(_to_array(original))
            result = _unflatten(result, shape)
            return _from_array(result, original)
