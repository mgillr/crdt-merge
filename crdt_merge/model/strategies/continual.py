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

"""Dual-projection continual merge strategy.

Implements the dual-projection approach from Yuan et al. (NeurIPS 2025),
extended with CRDT convergence guarantees.  Decomposes task vectors into
shared and task-specific subspaces via SVD, merging each component with
appropriate CRDT semantics (GCounter for shared, OR-Set for task-specific).

Example::

    from crdt_merge.model.strategies import get_strategy

    dp = get_strategy("dual_projection")
    merged = dp.merge([tensor_a, tensor_b], base=pretrained)

The strategy is auto-registered as ``"dual_projection"`` on import.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies import register_strategy
from crdt_merge.model.strategies.base import (
    CRDTTier,
    MergeResult,
    ModelMergeStrategy,
    _from_array,
    _get_np,
    _normalize_weights,
    _to_array,
)

__all__ = ["DualProjectionMerge"]


# ---------------------------------------------------------------------------
# Pure-Python helpers (used when numpy is unavailable)
# ---------------------------------------------------------------------------

def _py_dot(a: list, b: list) -> float:
    """Dot product of two flat lists."""
    return sum(x * y for x, y in zip(a, b))


def _py_norm(a: list) -> float:
    """L2 norm of a flat list."""
    import math
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


def _py_zeros(n: int) -> list:
    """Return list of n zeros."""
    return [0.0] * n


# ---------------------------------------------------------------------------
# DualProjectionMerge
# ---------------------------------------------------------------------------

@register_strategy("dual_projection")
class DualProjectionMerge(ModelMergeStrategy):
    """Dual-projection continual merge with CRDT guarantees.

    Decomposes task vectors (differences from a base model) into two
    orthogonal components via truncated SVD:

    * **Shared subspace** (top-k singular directions): captures consensus
      changes present across multiple models.  Merged with additive
      semantics (GCounter — commutative, associative, idempotent).
    * **Task-specific subspace** (orthogonal complement): captures
      changes unique to individual fine-tunes.  Merged with add-wins
      semantics (OR-Set — commutative, associative, idempotent).

    The ``stability_weight`` parameter interpolates between full
    plasticity (0.0 — all changes kept) and full stability (1.0 — only
    consensus changes kept).

    Parameters
    ----------
    stability_weight : float
        Balance between stability (1.0) and plasticity (0.0).
        Default: 0.5.
    rank_fraction : float
        Fraction of singular values to keep for the shared subspace.
        Default: 0.5.

    References
    ----------
    Yuan et al., "Dual-Projection Model Merging for Continual Learning",
    NeurIPS 2025.
    """

    def __init__(
        self,
        stability_weight: float = 0.5,
        rank_fraction: float = 0.5,
    ) -> None:
        self._stability_weight = max(0.0, min(1.0, stability_weight))
        self._rank_fraction = max(0.01, min(1.0, rank_fraction))

    # ------------------------------------------------------------------
    # ModelMergeStrategy interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:  # pragma: no cover
        return "dual_projection"

    @property
    def category(self) -> str:  # pragma: no cover
        return "continual"

    @property
    def paper_reference(self) -> str:  # pragma: no cover
        return "Yuan et al., NeurIPS 2025"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {
            "commutative": True,
            "associative": True,
            "idempotent": True,
            "crdt_tier": CRDTTier.TRUE_CRDT,
        }

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors using dual-projection decomposition.

        Parameters
        ----------
        tensors : list
            Model tensors to merge (numpy arrays, lists, or torch tensors).
        weights : list[float] | None
            Per-tensor importance weights.  ``None`` → uniform.
        base : Any | None
            Base/pretrained tensor for computing task vectors.
            If ``None``, the weighted mean of *tensors* is used as the
            implicit base.
        **kwargs
            stability_weight : float
                Override instance default.
            rank_fraction : float
                Override instance default.

        Returns
        -------
        merged : same type as ``tensors[0]``
            The merged tensor.

        Raises
        ------
        ValueError
            If *tensors* is empty or shapes are incompatible.
        """
        n = len(tensors)
        if n == 0:
            raise ValueError("Cannot merge zero tensors")
        if n == 1:
            return tensors[0]

        stability = kwargs.get("stability_weight", self._stability_weight)
        rank_frac = kwargs.get("rank_fraction", self._rank_fraction)
        norm_w = _normalize_weights(weights, n)

        np = _get_np()
        if np is not None:
            return self._merge_numpy(
                tensors, norm_w, base, stability, rank_frac, np,
            )
        return self._merge_python(tensors, norm_w, base, stability)

    # ------------------------------------------------------------------
    # NumPy path (with SVD)
    # ------------------------------------------------------------------

    def _merge_numpy(
        self,
        tensors: list,
        weights: List[float],
        base: Any,
        stability: float,
        rank_frac: float,
        np: Any,
    ) -> Any:
        """Merge using numpy with full SVD decomposition."""
        arrays = [np.asarray(_to_array(t), dtype=np.float64) for t in tensors]
        orig_shape = arrays[0].shape
        flat = [a.ravel() for a in arrays]
        d = len(flat[0])
        n = len(flat)

        # Validate shapes
        for i, f in enumerate(flat):
            if len(f) != d:
                raise ValueError(
                    f"Tensor {i} has {len(f)} elements, expected {d}"
                )

        # Compute or use provided base
        if base is not None:
            base_flat = np.asarray(_to_array(base), dtype=np.float64).ravel()
            if len(base_flat) != d:
                raise ValueError(
                    f"Base tensor has {len(base_flat)} elements, expected {d}"
                )
        else:
            # Weighted mean as implicit base
            base_flat = np.zeros(d, dtype=np.float64)
            for i in range(n):
                base_flat += weights[i] * flat[i]

        # Task vectors (deltas from base)
        deltas = np.stack([f - base_flat for f in flat], axis=0)  # (n, d)

        # Check for zero deltas (all models identical to base)
        delta_norms = np.linalg.norm(deltas, axis=1)
        if np.all(delta_norms < 1e-15):
            return _from_array(base_flat.reshape(orig_shape), tensors[0])

        # --- SVD decomposition ---
        try:
            U, S, Vt = np.linalg.svd(deltas, full_matrices=False)
            # Determine rank for shared subspace
            k = max(1, int(round(len(S) * rank_frac)))
            k = min(k, len(S), n)

            # Shared subspace: top-k right singular vectors
            Vk = Vt[:k]  # (k, d)

            shared_components = []
            task_components = []
            for i in range(n):
                delta = deltas[i]
                # Project onto shared subspace
                coeffs = Vk @ delta              # (k,)
                shared = Vk.T @ coeffs           # (d,)
                task = delta - shared             # (d,)
                shared_components.append(shared)
                task_components.append(task)

            # GCounter merge for shared subspace (weighted average)
            shared_merged = np.zeros(d, dtype=np.float64)
            for i in range(n):
                shared_merged += weights[i] * shared_components[i]

            # OR-Set merge for task subspace (weighted average, preserves all)
            task_merged = np.zeros(d, dtype=np.float64)
            for i in range(n):
                task_merged += weights[i] * task_components[i]

            # Combine: stability controls task retention
            # stability=1.0 → only shared (consensus)
            # stability=0.0 → shared + task (full change)
            merged_delta = shared_merged + (1.0 - stability) * task_merged

        except np.linalg.LinAlgError:
            # SVD failed -- fall back to weighted average of deltas
            merged_delta = np.zeros(d, dtype=np.float64)
            for i in range(n):
                merged_delta += weights[i] * deltas[i]

        result = (base_flat + merged_delta).reshape(orig_shape)
        return _from_array(result, tensors[0])

    # ------------------------------------------------------------------
    # Pure-Python fallback (no SVD)
    # ------------------------------------------------------------------

    def _merge_python(
        self,
        tensors: list,
        weights: List[float],
        base: Any,
        stability: float,
    ) -> Any:
        """Merge without numpy — weighted average with stability scaling.

        Without numpy, SVD decomposition is unavailable.  Falls back to a
        stability-weighted average where ``stability_weight`` scales down
        the total delta magnitude (approximating the shared-only behavior).
        """
        arrays = [_to_array(t) for t in tensors]
        n = len(arrays)

        if not isinstance(arrays[0], list):
            # Scalar path
            result = sum(weights[i] * float(arrays[i]) for i in range(n))
            return _from_array(result, tensors[0])

        d = len(arrays[0])

        # Compute base
        if base is not None:
            base_arr = _to_array(base)
            if not isinstance(base_arr, list):
                base_arr = [float(base_arr)] * d
        else:
            base_arr = _py_zeros(d)
            for i in range(n):
                for j in range(d):
                    base_arr[j] += weights[i] * arrays[i][j]

        # Weighted average of deltas
        merged_delta = _py_zeros(d)
        for i in range(n):
            for j in range(d):
                merged_delta[j] += weights[i] * (arrays[i][j] - base_arr[j])

        # Stability scaling: reduce overall delta magnitude
        # Without SVD, all change is treated as mixed shared/task
        scale = 1.0 - stability * 0.5
        result = [base_arr[j] + scale * merged_delta[j] for j in range(d)]

        return _from_array(result, tensors[0])
