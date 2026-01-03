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

"""Unlearning model-merge strategies.

Implements 2 strategies:

20. NegativeMerge       — Weight negation for unlearning (NegMerge)
21. SplitUnlearnMerge   — Split → unlearn → merge
"""

from __future__ import annotations

import math
import random as _random_module
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
# 20. NegativeMerge (NegMerge)
# ===================================================================

@register_strategy("negative_merge")
class NegativeMerge(ModelMergeStrategy):
    """NegMerge: Weight negation for unlearning (ICML 2025).

    ``θ = θ_base - α · (θ_toxic - θ_base)`` — negate unwanted task vectors.

    If ``models_to_negate`` is specified, only those models are negated;
    others are added normally.
    """

    @property
    def name(self) -> str:
        return "negative_merge"

    @property
    def category(self) -> str:
        return "Unlearning"

    @property
    def paper_reference(self) -> str:
        return "ICML 2025 — NegMerge: Weight Negation for Unlearning"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if base is None:
            raise ValueError("NegativeMerge requires a base model tensor (base=...)")

        if not tensors:
            return base
        if len(tensors) == 1:
            scaling = kwargs.get("scaling", 1.0)
            models_to_negate = kwargs.get("models_to_negate", None)
            # Single model
            np = _get_np()
            original = tensors[0]
            base_arr = _to_array(base)
            arr = _to_array(tensors[0])

            if models_to_negate is None or 0 in models_to_negate:
                # Negate
                if np is not None and isinstance(base_arr, np.ndarray):
                    base_f = base_arr.astype(float)
                    a_f = arr.astype(float)
                    result = base_f - scaling * (a_f - base_f)
                    return _from_array(result, original)
                else:
                    b_flat, b_shape = _flatten(base_arr)
                    a_flat, _ = _flatten(arr)
                    tv = _py_sub(a_flat, b_flat)
                    result = _py_sub(b_flat, _py_scale(tv, scaling))
                    result = _unflatten(result, b_shape)
                    return _from_array(result, original)
            else:
                # Add normally
                return tensors[0]

        scaling: float = kwargs.get("scaling", 1.0)
        models_to_negate: Optional[List[int]] = kwargs.get("models_to_negate", None)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        base_arr = _to_array(base)
        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(base_arr, np.ndarray):
            base_f = base_arr.astype(float)
            result = base_f.copy()
            for i, (w, a) in enumerate(zip(norm_w, arrays)):
                a_f = a.astype(float)
                tv = a_f - base_f
                if models_to_negate is None or i in models_to_negate:
                    # Negate
                    result = result - scaling * w * tv
                else:
                    # Add normally
                    result = result + w * tv
            return _from_array(result, original)
        else:
            b_flat, b_shape = _flatten(base_arr)
            flats = []
            for a in arrays:
                flat, _ = _flatten(a)
                flats.append(flat)

            d = len(b_flat)
            result = b_flat[:]

            for i, (w, flat) in enumerate(zip(norm_w, flats)):
                tv = _py_sub(flat, b_flat)
                if models_to_negate is None or i in models_to_negate:
                    scaled_tv = _py_scale(tv, -scaling * w)
                else:
                    scaled_tv = _py_scale(tv, w)
                result = _py_add(result, scaled_tv)

            result = _unflatten(result, b_shape)
            return _from_array(result, original)


# ===================================================================
# 21. SplitUnlearnMerge
# ===================================================================

@register_strategy("split_unlearn_merge")
class SplitUnlearnMerge(ModelMergeStrategy):
    """Split → Unlearn → Merge (2025).

    Splits parameters into subspaces by magnitude, unlearns targeted
    fraction, then merges the clean remainder.
    """

    @property
    def name(self) -> str:
        return "split_unlearn_merge"

    @property
    def category(self) -> str:
        return "Unlearning"

    @property
    def paper_reference(self) -> str:
        return "2025 — Sequential Split-Unlearn-Merge"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if base is None:
            raise ValueError("SplitUnlearnMerge requires a base model tensor (base=...)")

        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        target_fraction: float = kwargs.get("target_fraction", 0.1)
        subspace_method: str = kwargs.get("subspace_method", "magnitude")
        seed: int = kwargs.get("seed", 42)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        base_arr = _to_array(base)
        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(base_arr, np.ndarray):
            base_f = base_arr.astype(float).ravel()
            d = base_f.size
            shape = base_arr.shape

            # Compute task vectors
            tvs = [(a.astype(float).ravel() - base_f) for a in arrays]

            # Identify params to unlearn
            if subspace_method == "random":
                rng = _random_module.Random(seed)
                unlearn_mask = [1.0 if rng.random() < target_fraction else 0.0 for _ in range(d)]
                unlearn_mask = [bool(m) for m in unlearn_mask]
            else:
                # magnitude: unlearn the lowest-magnitude (least important) params
                # across all task vectors
                avg_magnitude = sum(abs(tv) for tv in tvs) / len(tvs)
                k = max(1, int(d * target_fraction))
                # Find threshold for bottom k params
                sorted_mag = sorted(avg_magnitude)
                threshold = sorted_mag[min(k - 1, d - 1)]
                unlearn_mask = [avg_magnitude[j] <= threshold for j in range(d)]

            # Clean merge: zero out unlearned params in task vectors
            merged = base_f.copy()
            for w, tv in zip(norm_w, tvs):
                clean_tv = tv.copy()
                for j in range(d):
                    if unlearn_mask[j]:
                        clean_tv[j] = 0.0
                merged += w * clean_tv

            result = merged.reshape(shape)
            return _from_array(result, original)
        else:
            b_flat, b_shape = _flatten(base_arr)
            d = len(b_flat)

            tvs = []
            for a in arrays:
                flat, _ = _flatten(a)
                tvs.append(_py_sub(flat, b_flat))

            if subspace_method == "random":
                rng = _random_module.Random(seed)
                unlearn_mask = [rng.random() < target_fraction for _ in range(d)]
            else:
                avg_magnitude = [sum(abs(tv[j]) for tv in tvs) / len(tvs) for j in range(d)]
                k = max(1, int(d * target_fraction))
                sorted_mag = sorted(avg_magnitude)
                threshold = sorted_mag[min(k - 1, d - 1)]
                unlearn_mask = [avg_magnitude[j] <= threshold for j in range(d)]

            result = b_flat[:]
            for w, tv in zip(norm_w, tvs):
                clean_tv = [0.0 if unlearn_mask[j] else tv[j] for j in range(d)]
                result = _py_add(result, _py_scale(clean_tv, w))

            result = _unflatten(result, b_shape)
            return _from_array(result, original)
