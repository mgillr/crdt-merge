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

"""Basic model-merge strategies: WeightAverage, SLERP, TaskArithmetic, LinearInterpolation.

These four strategies form the core toolbox for deterministic, CRDT-aware
model merging. Each strategy is auto-registered via ``@register_strategy``.
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
# Pure-Python vector helpers (used when numpy is unavailable)
# ---------------------------------------------------------------------------

def _py_dot(a: list, b: list) -> float:
    """Dot product of two flat lists."""
    return sum(x * y for x, y in zip(a, b))


def _py_norm(a: list) -> float:
    """L2 norm of a flat list."""
    return math.sqrt(sum(x * x for x in a))


def _py_scale(a: list, s: float) -> list:
    """Scalar multiplication."""
    return [x * s for x in a]


def _py_add(a: list, b: list) -> list:
    """Element-wise addition."""
    return [x + y for x, y in zip(a, b)]


def _py_sub(a: list, b: list) -> list:
    """Element-wise subtraction."""
    return [x - y for x, y in zip(a, b)]


def _py_zeros_like(a: list) -> list:
    """Return a list of zeros with the same length."""
    return [0.0] * len(a)


def _flatten(arr: Any) -> Any:
    """Flatten an array-like to 1-D, return (flat, original_shape)."""
    np = _get_np()
    if np is not None and isinstance(arr, np.ndarray):
        return arr.ravel(), arr.shape
    # plain list – assume already flat or flatten recursively
    if isinstance(arr, list) and arr and isinstance(arr[0], list):
        # 2-D list -> flatten
        flat = []
        rows = len(arr)
        cols = len(arr[0]) if arr else 0
        for row in arr:
            flat.extend(row)
        return flat, (rows, cols)
    return arr, None


def _unflatten(flat: Any, shape) -> Any:
    """Restore shape from _flatten."""
    if shape is None:
        return flat
    np = _get_np()
    if np is not None and isinstance(flat, np.ndarray):
        return flat.reshape(shape)
    # plain list 2-D
    if isinstance(shape, tuple) and len(shape) == 2:
        rows, cols = shape
        return [flat[i * cols:(i + 1) * cols] for i in range(rows)]
    return flat


# ===================================================================
# 1. WeightAverage
# ===================================================================

@register_strategy("weight_average")
class WeightAverage(ModelMergeStrategy):
    """Federated-averaging style weighted average (McMahan et al., 2017).

    ``θ_merged = Σ(αᵢ · θᵢ)``  where ``Σαᵢ = 1``.
    """

    @property
    def name(self) -> str:
        return "weight_average"

    @property
    def category(self) -> str:
        return "averaging"

    @property
    def paper_reference(self) -> str:
        return "McMahan et al., 2017 — Communication-Efficient Learning of Deep Networks from Decentralized Data"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": True}

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

        np = _get_np()
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        arrays = [_to_array(t) for t in tensors]

        if np is not None and isinstance(arrays[0], np.ndarray):
            result = np.zeros_like(arrays[0], dtype=float)
            for w, a in zip(norm_w, arrays):
                result = result + w * a.astype(float)
            return _from_array(result, original)

        # Pure-python fallback — flat lists
        result = _py_zeros_like(arrays[0])
        for w, a in zip(norm_w, arrays):
            result = _py_add(result, _py_scale(a, w))
        return _from_array(result, original)


# ===================================================================
# 2. SphericalLinearInterpolation (SLERP)
# ===================================================================

@register_strategy("slerp")
class SphericalLinearInterpolation(ModelMergeStrategy):
    """Spherical linear interpolation (Shoemake 1985, applied to LLMs 2024).

    ``SLERP(θ₁, θ₂, t) = sin((1-t)Ω)/sin(Ω) · θ₁ + sin(tΩ)/sin(Ω) · θ₂``
    where ``Ω = arccos(θ₁·θ₂ / (|θ₁|·|θ₂|))``.
    """

    @property
    def name(self) -> str:
        return "slerp"

    @property
    def category(self) -> str:
        return "interpolation"

    @property
    def paper_reference(self) -> str:
        return "Shoemake, 1985 — Animating Rotation with Quaternion Curves"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": "conditional", "associative": False, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        t = kwargs.get("t", 0.5)
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        original = tensors[0]

        # Pairwise sequential application for N > 2
        result = tensors[0]
        for i in range(1, len(tensors)):
            result = self._slerp_pair(result, tensors[i], t)

        return _from_array(_to_array(result), original)

    def _slerp_pair(self, a: Any, b: Any, t: float) -> Any:
        """SLERP between two tensors."""
        np = _get_np()
        arr_a = _to_array(a)
        arr_b = _to_array(b)

        # Flatten for dot product
        flat_a, shape_a = _flatten(arr_a)
        flat_b, _ = _flatten(arr_b)

        if np is not None and isinstance(flat_a, np.ndarray):
            return self._slerp_np(flat_a, flat_b, t, shape_a, np)
        return self._slerp_py(flat_a, flat_b, t, shape_a)

    @staticmethod
    def _slerp_np(a, b, t: float, shape, np):
        """SLERP using numpy."""
        a = a.astype(float)
        b = b.astype(float)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        # Handle zero vectors
        if norm_a < 1e-12 and norm_b < 1e-12:
            return _unflatten(np.zeros_like(a), shape)
        if norm_a < 1e-12:
            return _unflatten(b * t, shape)
        if norm_b < 1e-12:
            return _unflatten(a * (1.0 - t), shape)

        # Normalize
        unit_a = a / norm_a
        unit_b = b / norm_b

        # Clamp dot product to [-1, 1]
        dot = float(np.clip(np.dot(unit_a, unit_b), -1.0, 1.0))
        omega = math.acos(dot)

        # If vectors are (anti-)parallel, fall back to linear interpolation
        if abs(omega) < 1e-8:
            result = (1.0 - t) * a + t * b
            return _unflatten(result, shape)

        sin_omega = math.sin(omega)
        coeff_a = math.sin((1.0 - t) * omega) / sin_omega
        coeff_b = math.sin(t * omega) / sin_omega

        # Interpolate on unit sphere, then scale magnitudes
        merged_dir = coeff_a * unit_a + coeff_b * unit_b
        merged_mag = (1.0 - t) * norm_a + t * norm_b
        result = merged_dir * merged_mag

        return _unflatten(result, shape)

    @staticmethod
    def _slerp_py(a: list, b: list, t: float, shape):
        """SLERP pure-python."""
        norm_a = _py_norm(a)
        norm_b = _py_norm(b)

        # Handle zero vectors
        if norm_a < 1e-12 and norm_b < 1e-12:
            return _unflatten(_py_zeros_like(a), shape)
        if norm_a < 1e-12:
            return _unflatten(_py_scale(b, t), shape)
        if norm_b < 1e-12:
            return _unflatten(_py_scale(a, 1.0 - t), shape)

        unit_a = _py_scale(a, 1.0 / norm_a)
        unit_b = _py_scale(b, 1.0 / norm_b)

        dot = max(-1.0, min(1.0, _py_dot(unit_a, unit_b)))
        omega = math.acos(dot)

        if abs(omega) < 1e-8:
            result = _py_add(_py_scale(a, 1.0 - t), _py_scale(b, t))
            return _unflatten(result, shape)

        sin_omega = math.sin(omega)
        coeff_a = math.sin((1.0 - t) * omega) / sin_omega
        coeff_b = math.sin(t * omega) / sin_omega

        merged_dir = _py_add(_py_scale(unit_a, coeff_a), _py_scale(unit_b, coeff_b))
        merged_mag = (1.0 - t) * norm_a + t * norm_b
        result = _py_scale(merged_dir, merged_mag)

        return _unflatten(result, shape)


# ===================================================================
# 3. TaskArithmetic
# ===================================================================

@register_strategy("task_arithmetic")
class TaskArithmetic(ModelMergeStrategy):
    """Task arithmetic merge (Ilharco et al., 2023).

    ``θ_merged = θ_base + Σ(αᵢ · τᵢ)`` where ``τᵢ = θᵢ - θ_base``.
    """

    @property
    def name(self) -> str:
        return "task_arithmetic"

    @property
    def category(self) -> str:
        return "task_vector"

    @property
    def paper_reference(self) -> str:
        return "Ilharco et al., 2023 — Editing Models with Task Arithmetic"

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
            raise ValueError(
                "TaskArithmetic requires a base model tensor (base=...). "
                "Provide the pre-trained base for task-vector computation."
            )

        scaling = kwargs.get("scaling_coefficients", None)

        if not tensors:
            return base
        if len(tensors) == 1 and scaling is None:
            # Single model with default scaling=1.0 → θ_base + (θ₁ - θ_base) = θ₁
            pass

        np = _get_np()
        original = tensors[0]
        base_arr = _to_array(base)
        arrays = [_to_array(t) for t in tensors]

        # Scaling coefficients default to 1.0 each
        if scaling is None:
            scaling = [1.0] * len(tensors)
        elif len(scaling) != len(tensors):
            raise ValueError(
                f"scaling_coefficients length ({len(scaling)}) != "
                f"number of tensors ({len(tensors)})"
            )

        if np is not None and isinstance(base_arr, np.ndarray):
            base_f = base_arr.astype(float)
            result = base_f.copy()
            for s, a in zip(scaling, arrays):
                task_vec = a.astype(float) - base_f
                result = result + s * task_vec
            return _from_array(result, original)

        # Pure-python fallback
        result = list(base_arr) if not isinstance(base_arr, list) else list(base_arr)
        # Convert to float
        result = [float(x) for x in result]
        for s, a in zip(scaling, arrays):
            task_vec = _py_sub([float(x) for x in a], [float(x) for x in base_arr])
            scaled = _py_scale(task_vec, s)
            result = _py_add(result, scaled)
        return _from_array(result, original)


# ===================================================================
# 4. LinearInterpolation
# ===================================================================

@register_strategy("linear")
class LinearInterpolation(ModelMergeStrategy):
    """Linear interpolation / model soups (Wortsman et al., 2022).

    ``θ_merged = (1 - t) · θ₁ + t · θ₂``
    """

    @property
    def name(self) -> str:
        return "linear"

    @property
    def category(self) -> str:
        return "interpolation"

    @property
    def paper_reference(self) -> str:
        return "Wortsman et al., 2022 — Model soups: averaging weights of multiple fine-tuned models improves accuracy without increasing inference time"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": "conditional", "associative": False, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        t = kwargs.get("t", 0.5)
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        original = tensors[0]

        # Pairwise sequential for N > 2
        result = tensors[0]
        for i in range(1, len(tensors)):
            result = self._lerp_pair(result, tensors[i], t)

        return _from_array(_to_array(result), original)

    @staticmethod
    def _lerp_pair(a: Any, b: Any, t: float) -> Any:
        """Linear interpolation between two tensors."""
        np = _get_np()
        arr_a = _to_array(a)
        arr_b = _to_array(b)

        if np is not None and isinstance(arr_a, np.ndarray):
            result = (1.0 - t) * arr_a.astype(float) + t * arr_b.astype(float)
            return result

        # Pure-python
        return _py_add(
            _py_scale([float(x) for x in arr_a], 1.0 - t),
            _py_scale([float(x) for x in arr_b], t),
        )
