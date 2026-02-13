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

"""Subspace / Sparsification model-merge strategies.

Implements 9 strategies that work on task vectors (deltas from a base model):

5.  TIESMerge          — Trim, Elect sign, Disjoint merge
6.  DareDropAndRescale — Random drop + rescale (DARE)
7.  DellaDropElectLowRank — Magnitude-aware DARE (DELLA)
8.  DareTiesHybrid     — DARE dropping + TIES sign election
9.  ModelBreadcrumbs   — Sparse binary masks + task vector aggregation
10. EMRMerge           — Elect, Mask, Rescale (tuning-free)
11. SpectralTruncationAdaptiveRescaling (STAR)
12. SVDKnotTying       — Align SVD bases + merge
13. AdaptiveRankPruning (AdaRank)
"""

from __future__ import annotations

import math
import random as _random_module
import warnings
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies import register_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _from_array,
    _get_np,
    _normalize_weights,
    _to_array,
)

__all__ = [
    "TIESMerge",
    "DareDropAndRescale",
    "DellaDropElectLowRank",
    "DareTiesHybrid",
    "ModelBreadcrumbs",
    "EMRMerge",
    "SpectralTruncationAdaptiveRescaling",
    "SVDKnotTying",
    "AdaptiveRankPruning",
]

# ---------------------------------------------------------------------------
# Pure-Python vector helpers
# ---------------------------------------------------------------------------

def _py_add(a: list, b: list) -> list:
    """Element-wise addition of two equal-length lists."""
    return [x + y for x, y in zip(a, b)]

def _py_sub(a: list, b: list) -> list:
    """Element-wise subtraction: ``a[i] - b[i]``."""
    return [x - y for x, y in zip(a, b)]

def _py_scale(a: list, s: float) -> list:
    """Scale every element of a list by scalar *s*."""
    return [x * s for x in a]

def _py_zeros(n: int) -> list:
    """Return a list of *n* zeros."""
    return [0.0] * n

def _py_abs(a: list) -> list:
    """Element-wise absolute value."""
    return [abs(x) for x in a]

def _py_percentile(values: list, pct: float) -> float:
    """Compute percentile from a sorted list of values."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return s[f]
    return s[f] * (c - k) + s[c] * (k - f)

def _flatten(arr: Any):
    """Flatten array-like to 1-D. Returns (flat, shape)."""
    np = _get_np()
    if np is not None and isinstance(arr, np.ndarray):
        return arr.ravel().astype(float), arr.shape
    if isinstance(arr, list) and arr and isinstance(arr[0], list):
        flat = []
        rows = len(arr)
        cols = len(arr[0]) if arr else 0
        for row in arr:
            flat.extend(row)
        return flat, (rows, cols)
    if isinstance(arr, list):
        return [float(x) for x in arr], None
    return arr, None

def _unflatten(flat: Any, shape):
    """Restore a flat array to its original *shape*.

    Args:
        flat: 1-D array or list produced by :func:`_flatten`.
        shape: Original shape tuple, or ``None`` to return *flat* as-is.

    Returns:
        Reshaped array matching the original dimensionality.
    """
    if shape is None:
        return flat
    np = _get_np()
    if np is not None and isinstance(flat, np.ndarray):
        return flat.reshape(shape)
    if isinstance(shape, tuple) and len(shape) == 2:
        rows, cols = shape
        return [flat[i * cols:(i + 1) * cols] for i in range(rows)]
    return flat

def _require_base(base: Any) -> None:
    """Raise if base_model is missing."""
    if base is None:
        raise ValueError("Strategy requires base_model parameter")

# ---------------------------------------------------------------------------
# Task-vector helpers
# ---------------------------------------------------------------------------

def _compute_task_vectors_np(tensors, base, np):
    """Compute task vectors as numpy arrays."""
    b = _to_array(base).astype(float)
    return [_to_array(t).astype(float) - b for t in tensors], b

def _compute_task_vectors_py(tensors, base):
    """Compute task vectors as plain lists."""
    b_flat, b_shape = _flatten(_to_array(base))
    tvs = []
    for t in tensors:
        t_flat, _ = _flatten(_to_array(t))
        tvs.append(_py_sub(t_flat, b_flat))
    return tvs, b_flat, b_shape

# ===================================================================
# 5. TIESMerge
# ===================================================================

@register_strategy("ties")
class TIESMerge(ModelMergeStrategy):
    """TIES-Merging: Trim, Elect sign, Disjoint merge (Yadav et al., NeurIPS 2023)."""

    @property
    def name(self) -> str:
        return "ties"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Yadav et al., NeurIPS 2023 — Resolving Interference When Merging Models (TIES-Merging)"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for TIES merging."""
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors via Trim, Elect Sign, Disjoint merge (TIES).

        Three-step process: (1) *Trim* — zero out low-magnitude entries in
        each task vector, keeping only the top ``density`` fraction.
        (2) *Elect sign* — determine a consensus sign per parameter position
        via majority vote or magnitude-weighted vote. (3) *Merge* — average
        only the task-vector entries whose sign matches the elected sign.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                density (float): Fraction of entries to keep after trimming
                    (default 0.2).
                majority_sign_method (str): ``"count"`` or ``"magnitude"``
                    (default ``"count"``).

        Returns:
            Merged tensor: base + averaged sign-consistent trimmed task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        density = kwargs.get("density", 0.2)
        majority_sign_method = kwargs.get("majority_sign_method", "count")
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            n = len(tvs)
            d = tvs[0].size
            flat_tvs = [tv.ravel() for tv in tvs]

            # Trim: zero out small-magnitude params
            trimmed = []
            for tv in flat_tvs:
                abs_tv = np.abs(tv)
                nonzero_abs = abs_tv[abs_tv > 0]
                if len(nonzero_abs) == 0:
                    trimmed.append(tv.copy())
                    continue
                threshold = np.percentile(nonzero_abs, (1.0 - density) * 100)
                mask = abs_tv >= threshold
                trimmed.append(tv * mask)

            # Elect sign
            if majority_sign_method == "magnitude":
                sign_sum = np.zeros(d)
                for w, tv in zip(norm_w, trimmed):
                    sign_sum += w * tv
                elected_sign = np.sign(sign_sum)
            else:  # count
                sign_votes = np.zeros(d)
                for tv in trimmed:
                    sign_votes += np.sign(tv)
                elected_sign = np.sign(sign_votes)

            # Merge: average only params matching elected sign
            merged = np.zeros(d)
            counts = np.zeros(d)
            for w, tv in zip(norm_w, trimmed):
                agree = np.sign(tv) == elected_sign
                nonzero = tv != 0
                mask = agree & nonzero
                merged += w * tv * mask
                counts += mask.astype(float)

            counts = np.maximum(counts, 1.0)
            merged = merged / counts

            result = b.ravel() + merged
            result = result.reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            n = len(tvs)
            d = len(tvs[0])

            # Trim
            trimmed = []
            for tv in tvs:
                abs_tv = _py_abs(tv)
                nonzero_abs = [v for v in abs_tv if v > 0]
                if not nonzero_abs:
                    trimmed.append(tv[:])
                    continue
                threshold = _py_percentile(nonzero_abs, 1.0 - density)
                trimmed.append([v if abs(v) >= threshold else 0.0 for v in tv])

            # Elect sign
            if majority_sign_method == "magnitude":
                sign_sum = _py_zeros(d)
                for w, tv in zip(norm_w, trimmed):
                    sign_sum = _py_add(sign_sum, _py_scale(tv, w))
                elected_sign = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in sign_sum]
            else:
                sign_votes = _py_zeros(d)
                for tv in trimmed:
                    sv = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in tv]
                    sign_votes = _py_add(sign_votes, sv)
                elected_sign = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in sign_votes]

            # Merge
            merged = _py_zeros(d)
            counts = _py_zeros(d)
            for w, tv in zip(norm_w, trimmed):
                for j in range(d):
                    tv_sign = 1.0 if tv[j] > 0 else (-1.0 if tv[j] < 0 else 0.0)
                    if tv_sign == elected_sign[j] and tv[j] != 0.0:
                        merged[j] += w * tv[j]
                        counts[j] += 1.0

            result = []
            for j in range(d):
                c = max(counts[j], 1.0)
                result.append(b_flat[j] + merged[j] / c)

            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 6. DareDropAndRescale (DARE)
# ===================================================================

@register_strategy("dare")
class DareDropAndRescale(ModelMergeStrategy):
    """DARE: Drop And REscale (Yu et al., 2024 — Language Models are Super Mario)."""

    @property
    def name(self) -> str:
        return "dare"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Yu et al., 2024 — Language Models are Super Mario"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for DARE merging."""
        return {"commutative": False, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors using DARE: randomly drop task-vector entries and rescale.

        For each task vector, independently drops each entry with probability
        ``drop_rate``, then rescales surviving entries by ``1 / (1 − drop_rate)``
        to preserve the expected magnitude. The rescaled task vectors are
        weighted-summed and added to the base.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                drop_rate (float): Probability of dropping each entry
                    (default 0.9).
                seed (int): RNG seed for reproducibility (default 42).

        Returns:
            Merged tensor: base + rescaled sparse task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        drop_rate = kwargs.get("drop_rate", 0.9)
        seed = kwargs.get("seed", 42)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            d = tvs[0].size
            rng = _random_module.Random(seed)
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            merged = np.zeros_like(b.ravel(), dtype=float)
            for w, tv in zip(norm_w, tvs):
                flat = tv.ravel()
                mask = np.array([1.0 if rng.random() >= drop_rate else 0.0 for _ in range(d)])
                merged += w * flat * mask * rescale

            result = (b.ravel() + merged).reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            rng = _random_module.Random(seed)
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            merged = _py_zeros(d)
            for w, tv in zip(norm_w, tvs):
                masked = [tv[j] * rescale if rng.random() >= drop_rate else 0.0 for j in range(d)]
                merged = _py_add(merged, _py_scale(masked, w))

            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 7. DellaDropElectLowRank (DELLA)
# ===================================================================

@register_strategy("della")
class DellaDropElectLowRank(ModelMergeStrategy):
    """DELLA-Merging: DARE + magnitude-aware dropping (Bansal, 2024)."""

    @property
    def name(self) -> str:
        return "della"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Bansal, 2024 — DELLA-Merging"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for DELLA merging."""
        return {"commutative": False, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors using DELLA: magnitude-aware DARE dropping.

        Unlike vanilla DARE, DELLA assigns higher drop probability to
        low-magnitude entries (less important) and lower drop probability to
        high-magnitude entries, controlled by ``epsilon``. Surviving entries
        are rescaled by ``1 / (1 − drop_rate)``.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                drop_rate (float): Base drop probability (default 0.9).
                epsilon (float): Additive offset for drop probability to
                    ensure minimum dropping (default 0.1).
                seed (int): RNG seed for reproducibility (default 42).

        Returns:
            Merged tensor: base + magnitude-aware sparse task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        drop_rate = kwargs.get("drop_rate", 0.9)
        epsilon = kwargs.get("epsilon", 0.1)
        seed = kwargs.get("seed", 42)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            d = tvs[0].size
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            merged = np.zeros_like(b.ravel(), dtype=float)
            for idx, (w, tv) in enumerate(zip(norm_w, tvs)):
                flat = tv.ravel().copy()
                rng = _random_module.Random(seed + idx)
                abs_flat = np.abs(flat)
                max_mag = abs_flat.max() if abs_flat.max() > 0 else 1.0
                # Lower magnitude → higher drop probability
                # drop_prob = drop_rate * (1 - abs_flat / max_mag) + epsilon
                # clamp to [0, 1]
                drop_prob = drop_rate * (1.0 - abs_flat / max_mag)
                drop_prob = np.clip(drop_prob + epsilon, 0.0, 1.0)
                # But ensure average drop rate is approximately drop_rate
                mask = np.array([1.0 if rng.random() >= drop_prob[j] else 0.0 for j in range(d)])
                merged += w * flat * mask * rescale

            result = (b.ravel() + merged).reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            merged = _py_zeros(d)
            for idx, (w, tv) in enumerate(zip(norm_w, tvs)):
                rng = _random_module.Random(seed + idx)
                abs_tv = _py_abs(tv)
                max_mag = max(abs_tv) if max(abs_tv) > 0 else 1.0
                masked = []
                for j in range(d):
                    dp = drop_rate * (1.0 - abs_tv[j] / max_mag) + epsilon
                    dp = max(0.0, min(1.0, dp))
                    if rng.random() >= dp:
                        masked.append(tv[j] * rescale)
                    else:
                        masked.append(0.0)
                merged = _py_add(merged, _py_scale(masked, w))

            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 8. DareTiesHybrid (DARE-TIES)
# ===================================================================

@register_strategy("dare_ties")
class DareTiesHybrid(ModelMergeStrategy):
    """DARE-TIES: DARE dropping + TIES sign election (Community hybrid, 2024)."""

    @property
    def name(self) -> str:
        return "dare_ties"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Community hybrid, 2024 — DARE-TIES"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for DARE-TIES merging."""
        return {"commutative": False, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors using DARE-TIES: DARE dropping followed by TIES sign election.

        Combines DARE's random drop-and-rescale with TIES's trim-elect-merge
        pipeline. First drops entries randomly with rescaling, then trims by
        magnitude, elects a consensus sign, and averages only sign-agreeing
        entries.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                drop_rate (float): DARE drop probability (default 0.9).
                density (float): TIES trim density (default 0.2).
                seed (int): RNG seed for reproducibility (default 42).

        Returns:
            Merged tensor combining DARE sparsification with TIES conflict resolution.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        drop_rate = kwargs.get("drop_rate", 0.9)
        density = kwargs.get("density", 0.2)
        seed = kwargs.get("seed", 42)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            d = tvs[0].size
            rng = _random_module.Random(seed)
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            # DARE-style drop
            dropped = []
            for tv in tvs:
                flat = tv.ravel()
                mask = np.array([1.0 if rng.random() >= drop_rate else 0.0 for _ in range(d)])
                dropped.append(flat * mask * rescale)

            # TIES-style trim
            trimmed = []
            for tv in dropped:
                abs_tv = np.abs(tv)
                nonzero_abs = abs_tv[abs_tv > 0]
                if len(nonzero_abs) == 0:
                    trimmed.append(tv.copy())
                    continue
                threshold = np.percentile(nonzero_abs, (1.0 - density) * 100)
                mask = abs_tv >= threshold
                trimmed.append(tv * mask)

            # Elect sign
            sign_votes = np.zeros(d)
            for tv in trimmed:
                sign_votes += np.sign(tv)
            elected_sign = np.sign(sign_votes)

            # Merge sign-agreeing
            merged = np.zeros(d)
            counts = np.zeros(d)
            for w, tv in zip(norm_w, trimmed):
                agree = np.sign(tv) == elected_sign
                nonzero = tv != 0
                mask = agree & nonzero
                merged += w * tv * mask
                counts += mask.astype(float)

            counts = np.maximum(counts, 1.0)
            merged = merged / counts

            result = (b.ravel() + merged).reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            rng = _random_module.Random(seed)
            rescale = 1.0 / (1.0 - drop_rate) if drop_rate < 1.0 else 1.0

            # DARE-style drop
            dropped = []
            for tv in tvs:
                dropped.append([tv[j] * rescale if rng.random() >= drop_rate else 0.0 for j in range(d)])

            # TIES-style trim
            trimmed = []
            for tv in dropped:
                abs_tv = _py_abs(tv)
                nonzero_abs = [v for v in abs_tv if v > 0]
                if not nonzero_abs:
                    trimmed.append(tv[:])
                    continue
                threshold = _py_percentile(nonzero_abs, 1.0 - density)
                trimmed.append([v if abs(v) >= threshold else 0.0 for v in tv])

            # Elect sign
            sign_votes = _py_zeros(d)
            for tv in trimmed:
                sv = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in tv]
                sign_votes = _py_add(sign_votes, sv)
            elected_sign = [1.0 if v > 0 else (-1.0 if v < 0 else 0.0) for v in sign_votes]

            # Merge
            merged = _py_zeros(d)
            counts = _py_zeros(d)
            for w, tv in zip(norm_w, trimmed):
                for j in range(d):
                    tv_sign = 1.0 if tv[j] > 0 else (-1.0 if tv[j] < 0 else 0.0)
                    if tv_sign == elected_sign[j] and tv[j] != 0.0:
                        merged[j] += w * tv[j]
                        counts[j] += 1.0

            result = []
            for j in range(d):
                c = max(counts[j], 1.0)
                result.append(b_flat[j] + merged[j] / c)

            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 9. ModelBreadcrumbs
# ===================================================================

@register_strategy("model_breadcrumbs")
class ModelBreadcrumbs(ModelMergeStrategy):
    """Model Breadcrumbs: Sparse masks + task vector aggregation (Davari & Belilovsky, 2023)."""

    @property
    def name(self) -> str:
        return "model_breadcrumbs"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Davari & Belilovsky, 2023 — Model Breadcrumbs"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for Model Breadcrumbs merging."""
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors using sparse binary masks over task vectors.

        Creates a binary mask per task vector (by magnitude threshold or
        random selection), zeroes out masked entries, then computes a
        weighted sum of the sparse task vectors on top of the base model.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                sparsity (float): Fraction of entries to zero out
                    (default 0.9, keeping 10 %).
                mask_method (str): ``"magnitude"`` or ``"random"``
                    (default ``"magnitude"``).
                seed (int): RNG seed for random masking (default 42).

        Returns:
            Merged tensor: base + weighted sparse task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        sparsity = kwargs.get("sparsity", 0.9)
        mask_method = kwargs.get("mask_method", "magnitude")
        seed = kwargs.get("seed", 42)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        keep_fraction = 1.0 - sparsity
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            d = tvs[0].size

            masked_tvs = []
            for idx, tv in enumerate(tvs):
                flat = tv.ravel()
                if mask_method == "random":
                    rng = _random_module.Random(seed + idx)
                    mask = np.array([1.0 if rng.random() < keep_fraction else 0.0 for _ in range(d)])
                else:  # magnitude
                    abs_flat = np.abs(flat)
                    if abs_flat.max() == 0:
                        mask = np.ones(d)
                    else:
                        threshold = np.percentile(abs_flat, sparsity * 100)
                        mask = (abs_flat >= threshold).astype(float)
                masked_tvs.append(flat * mask)

            merged = np.zeros(d)
            for w, tv in zip(norm_w, masked_tvs):
                merged += w * tv

            result = (b.ravel() + merged).reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])

            masked_tvs = []
            for idx, tv in enumerate(tvs):
                if mask_method == "random":
                    rng = _random_module.Random(seed + idx)
                    mask = [1.0 if rng.random() < keep_fraction else 0.0 for _ in range(d)]
                else:
                    abs_tv = _py_abs(tv)
                    max_abs = max(abs_tv) if abs_tv else 0
                    if max_abs == 0:
                        mask = [1.0] * d
                    else:
                        threshold = _py_percentile(abs_tv, sparsity)
                        mask = [1.0 if abs(tv[j]) >= threshold else 0.0 for j in range(d)]
                masked_tvs.append([tv[j] * mask[j] for j in range(d)])

            merged = _py_zeros(d)
            for w, tv in zip(norm_w, masked_tvs):
                merged = _py_add(merged, _py_scale(tv, w))

            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 10. EMRMerge
# ===================================================================

@register_strategy("emr")
class EMRMerge(ModelMergeStrategy):
    """EMR-Merging: Elect, Mask, Rescale (Huang et al., 2024)."""

    @property
    def name(self) -> str:
        return "emr"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "Huang et al., 2024 — EMR-Merging"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for EMR merging."""
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors via Elect, Mask, Rescale (EMR).

        Three phases: (1) *Elect* — keep the top ``elect_ratio`` fraction
        of each task vector by magnitude. (2) *Mask* — combine elected
        entries across models. (3) *Rescale* — multiply the merged result
        by ``d / active_count`` (capped at ``1 / elect_ratio``) to
        compensate for sparsity.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                importance_metric (str): Currently only ``"magnitude"``
                    (default ``"magnitude"``).
                elect_ratio (float): Fraction of entries to elect per model
                    (default 0.3).

        Returns:
            Merged and rescaled tensor: base + rescaled elected task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        importance_metric = kwargs.get("importance_metric", "magnitude")
        elect_ratio = kwargs.get("elect_ratio", 0.3)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            d = tvs[0].size

            # Elect: keep top elect_ratio params per model
            elected = []
            for tv in tvs:
                flat = tv.ravel()
                abs_flat = np.abs(flat)
                if abs_flat.max() == 0:
                    elected.append(flat.copy())
                    continue
                threshold = np.percentile(abs_flat, (1.0 - elect_ratio) * 100)
                mask = abs_flat >= threshold
                elected.append(flat * mask)

            # Mask: remove redundant (params present in all models)
            # Keep params that are elected in at least one model
            presence = np.zeros(d)
            for e in elected:
                presence += (e != 0).astype(float)

            # Rescale: adjust to preserve distribution
            merged = np.zeros(d)
            for w, e in zip(norm_w, elected):
                merged += w * e

            # Rescale factor: account for sparsity
            active = (merged != 0).astype(float)
            total_active = active.sum()
            if total_active > 0:
                scale_factor = d / total_active
                # Cap rescaling to avoid extreme values
                scale_factor = min(scale_factor, 1.0 / elect_ratio)
                merged = merged * scale_factor

            result = (b.ravel() + merged).reshape(b.shape)
            return _from_array(result, original)
        else:
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])

            elected = []
            for tv in tvs:
                abs_tv = _py_abs(tv)
                max_abs = max(abs_tv) if abs_tv else 0
                if max_abs == 0:
                    elected.append(tv[:])
                    continue
                threshold = _py_percentile(abs_tv, 1.0 - elect_ratio)
                elected.append([tv[j] if abs(tv[j]) >= threshold else 0.0 for j in range(d)])

            merged = _py_zeros(d)
            for w, e in zip(norm_w, elected):
                merged = _py_add(merged, _py_scale(e, w))

            total_active = sum(1.0 for v in merged if v != 0)
            if total_active > 0:
                scale_factor = min(d / total_active, 1.0 / elect_ratio)
                merged = _py_scale(merged, scale_factor)

            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 11. STAR — Spectral Truncation Adaptive Rescaling
# ===================================================================

@register_strategy("star")
class SpectralTruncationAdaptiveRescaling(ModelMergeStrategy):
    """STAR: SVD decompose, truncate, rescale, reconstruct (2025)."""

    @property
    def name(self) -> str:
        return "star"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "2025 — Spectral Truncation Adaptive Rescaling (STAR)"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for STAR merging."""
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors via spectral truncation with adaptive rescaling (STAR).

        For 2-D+ tensors: decomposes each task vector with SVD, truncates
        to the top ``rank_fraction`` singular values, optionally rescales to
        preserve the original Frobenius energy, then weighted-averages the
        truncated task vectors. For 1-D tensors: applies magnitude-based
        truncation instead.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                rank_fraction (float): Fraction of singular values to retain
                    (default 0.5).
                rescale_method (str): ``"energy"`` to preserve Frobenius norm,
                    or ``"none"`` (default ``"energy"``).

        Returns:
            Merged tensor: base + rescaled rank-truncated task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        rank_fraction = kwargs.get("rank_fraction", 0.5)
        rescale_method = kwargs.get("rescale_method", "energy")
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            shape = b.shape
            is_1d = (b.ndim == 1) or (b.ndim > 1 and min(b.shape) == 1)

            if is_1d:
                # 1D: magnitude truncation
                flat_b = b.ravel()
                truncated_tvs = []
                for tv in tvs:
                    flat = tv.ravel()
                    abs_flat = np.abs(flat)
                    if abs_flat.max() == 0:
                        truncated_tvs.append(flat)
                        continue
                    k = max(1, int(len(flat) * rank_fraction))
                    threshold = np.sort(abs_flat)[::-1][min(k - 1, len(flat) - 1)]
                    mask = abs_flat >= threshold
                    trunc = flat * mask
                    # Rescale
                    if rescale_method == "energy":
                        orig_energy = np.sum(flat ** 2)
                        trunc_energy = np.sum(trunc ** 2)
                        if trunc_energy > 0:
                            trunc = trunc * math.sqrt(orig_energy / trunc_energy)
                    truncated_tvs.append(trunc)

                merged = np.zeros_like(flat_b)
                for w, tv in zip(norm_w, truncated_tvs):
                    merged += w * tv
                result = (flat_b + merged).reshape(shape)
                return _from_array(result, original)
            else:
                # 2D+: SVD truncation
                truncated_tvs = []
                for tv in tvs:
                    mat = tv.reshape(shape) if tv.shape != shape else tv
                    if mat.ndim != 2:
                        # Reshape to 2D
                        orig_shape = mat.shape
                        mat = mat.reshape(mat.shape[0], -1)
                    else:
                        orig_shape = None

                    try:
                        U, S, Vt = np.linalg.svd(mat, full_matrices=False)
                    except np.linalg.LinAlgError:
                        truncated_tvs.append(tv.ravel())
                        continue

                    k = max(1, int(len(S) * rank_fraction))
                    S_trunc = S.copy()
                    S_trunc[k:] = 0.0

                    if rescale_method == "energy":
                        orig_energy = np.sum(S ** 2)
                        trunc_energy = np.sum(S_trunc ** 2)
                        if trunc_energy > 0:
                            S_trunc = S_trunc * math.sqrt(orig_energy / trunc_energy)

                    reconstructed = U @ np.diag(S_trunc) @ Vt
                    if orig_shape is not None:
                        reconstructed = reconstructed.reshape(orig_shape)
                    truncated_tvs.append(reconstructed.ravel())

                merged = np.zeros(b.size)
                for w, tv in zip(norm_w, truncated_tvs):
                    merged += w * tv.ravel()
                result = (b.ravel() + merged).reshape(shape)
                return _from_array(result, original)
        else:
            # No numpy: fall back to simple averaging with warning
            warnings.warn("STAR requires numpy for SVD; falling back to simple averaging.")
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            merged = _py_zeros(d)
            for w, tv in zip(norm_w, tvs):
                merged = _py_add(merged, _py_scale(tv, w))
            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 12. SVDKnotTying
# ===================================================================

@register_strategy("svd_knot_tying")
class SVDKnotTying(ModelMergeStrategy):
    """SVD Knot Tying: Align SVD bases, merge in aligned space (2024)."""

    @property
    def name(self) -> str:
        return "svd_knot_tying"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "2024 — SVD Knot Tying: Aligning Merge Subspaces"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for SVD Knot Tying."""
        return {"commutative": True, "associative": False, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors by aligning SVD bases then averaging in aligned space.

        Decomposes each task vector via SVD, aligns left singular vectors
        to a reference decomposition using Procrustes rotation, reconstructs
        in the aligned basis, and computes a weighted average. For 1-D
        tensors, falls back to simple weighted averaging.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                alignment_method (str): ``"procrustes"`` (default) or
                    ``"none"`` to skip alignment.
                rank (int | None): Number of singular values to retain.
                    ``None`` retains all (default ``None``).

        Returns:
            Merged tensor: base + aligned weighted task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        alignment_method = kwargs.get("alignment_method", "procrustes")
        rank = kwargs.get("rank", None)
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            shape = b.shape
            is_1d = (b.ndim == 1) or (b.ndim > 1 and min(b.shape) == 1)

            if is_1d:
                # 1D: simple weighted average
                flat_b = b.ravel()
                merged = np.zeros_like(flat_b)
                for w, tv in zip(norm_w, tvs):
                    merged += w * tv.ravel()
                result = (flat_b + merged).reshape(shape)
                return _from_array(result, original)

            # 2D+: SVD alignment
            decomps = []
            for tv in tvs:
                mat = tv.reshape(shape) if tv.shape != shape else tv
                if mat.ndim != 2:
                    mat = mat.reshape(mat.shape[0], -1)
                try:
                    U, S, Vt = np.linalg.svd(mat, full_matrices=False)
                    r = rank if rank is not None else len(S)
                    r = min(r, len(S))
                    decomps.append((U[:, :r], S[:r], Vt[:r, :]))
                except np.linalg.LinAlgError:
                    decomps.append(None)

            if not decomps or all(d is None for d in decomps):
                # Fallback
                merged = np.zeros(b.size)
                for w, tv in zip(norm_w, tvs):
                    merged += w * tv.ravel()
                result = (b.ravel() + merged).reshape(shape)
                return _from_array(result, original)

            # Use first valid decomposition as reference
            ref_idx = next(i for i, d in enumerate(decomps) if d is not None)
            U_ref, S_ref, Vt_ref = decomps[ref_idx]

            # Align and merge
            aligned_mats = []
            for idx, decomp in enumerate(decomps):
                if decomp is None:
                    aligned_mats.append(tvs[idx].ravel())
                    continue
                U_i, S_i, Vt_i = decomp

                if alignment_method == "procrustes" and idx != ref_idx:
                    # Procrustes alignment: find R that minimizes ||U_ref - U_i @ R||
                    min_cols = min(U_ref.shape[1], U_i.shape[1])
                    M = U_i[:, :min_cols].T @ U_ref[:, :min_cols]
                    try:
                        Um, _, Vm = np.linalg.svd(M, full_matrices=False)
                        R = Um @ Vm
                        U_aligned = U_i[:, :min_cols] @ R
                        # Reconstruct
                        mat = U_aligned @ np.diag(S_i[:min_cols]) @ Vt_i[:min_cols, :]
                    except np.linalg.LinAlgError:
                        mat = U_i @ np.diag(S_i) @ Vt_i
                else:
                    mat = U_i @ np.diag(S_i) @ Vt_i

                aligned_mats.append(mat.ravel())

            merged = np.zeros(b.size)
            for w, mat in zip(norm_w, aligned_mats):
                flat = mat.ravel() if hasattr(mat, 'ravel') else np.array(mat).ravel()
                merged += w * flat

            result = (b.ravel() + merged).reshape(shape)
            return _from_array(result, original)
        else:
            warnings.warn("SVDKnotTying requires numpy for SVD; falling back to simple averaging.")
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            merged = _py_zeros(d)
            for w, tv in zip(norm_w, tvs):
                merged = _py_add(merged, _py_scale(tv, w))
            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)

# ===================================================================
# 13. AdaptiveRankPruning (AdaRank)
# ===================================================================

@register_strategy("adarank")
class AdaptiveRankPruning(ModelMergeStrategy):
    """AdaRank: Per-layer adaptive rank selection + pruned merge (ICLR 2026)."""

    @property
    def name(self) -> str:
        return "adarank"

    @property
    def category(self) -> str:
        return "Subspace / Sparsification"

    @property
    def paper_reference(self) -> str:
        return "ICLR 2026 — AdaRank: Adaptive Rank Pruning for Model Merging"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT algebraic properties for AdaRank merging."""
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge tensors with per-layer adaptive rank selection and pruning.

        For 2-D+ tensors: decomposes via SVD, automatically selects the
        rank that captures 90 % of spectral energy (or uses ``target_rank``),
        zeroes out lower singular values, then weighted-averages the pruned
        task vectors. For 1-D tensors: applies magnitude-based pruning
        retaining the top-energy entries.

        Args:
            tensors: Model parameter tensors to merge.
            weights: Optional per-model importance weights.
            base: Base model tensor (required).
            **kwargs: Additional keyword arguments:
                target_rank (int | "auto"): Rank to retain per task vector.
                    ``"auto"`` selects rank capturing 90 % energy (default).
                importance (str): Importance metric for auto rank — ``"energy"``
                    or ``"variance"`` (default ``"energy"``).

        Returns:
            Merged tensor: base + rank-pruned weighted task vectors.

        Raises:
            ValueError: If *base* is ``None``.
        """
        _require_base(base)
        if not tensors:
            return base
        if len(tensors) == 1:
            return tensors[0]

        target_rank = kwargs.get("target_rank", "auto")
        importance = kwargs.get("importance", "energy")
        norm_w = _normalize_weights(weights, len(tensors))
        original = tensors[0]
        np = _get_np()

        if np is not None:
            tvs, b = _compute_task_vectors_np(tensors, base, np)
            shape = b.shape
            is_1d = (b.ndim == 1) or (b.ndim > 1 and min(b.shape) == 1)

            if is_1d:
                # 1D: magnitude-based pruning
                flat_b = b.ravel()
                pruned_tvs = []
                for tv in tvs:
                    flat = tv.ravel()
                    abs_flat = np.abs(flat)
                    if abs_flat.max() == 0:
                        pruned_tvs.append(flat)
                        continue
                    if target_rank == "auto":
                        # Keep components explaining 90% of energy
                        sorted_abs = np.sort(abs_flat)[::-1]
                        total_energy = np.sum(sorted_abs ** 2)
                        cumulative = np.cumsum(sorted_abs ** 2)
                        k = np.searchsorted(cumulative, 0.9 * total_energy) + 1
                        k = min(k, len(flat))
                    else:
                        k = min(int(target_rank), len(flat))

                    threshold = np.sort(abs_flat)[::-1][min(k - 1, len(flat) - 1)]
                    mask = abs_flat >= threshold
                    pruned_tvs.append(flat * mask)

                merged = np.zeros_like(flat_b)
                for w, tv in zip(norm_w, pruned_tvs):
                    merged += w * tv
                result = (flat_b + merged).reshape(shape)
                return _from_array(result, original)
            else:
                # 2D+: SVD-based rank pruning
                pruned_tvs = []
                for tv in tvs:
                    mat = tv.reshape(shape) if tv.shape != shape else tv
                    orig_nd_shape = None
                    if mat.ndim != 2:
                        orig_nd_shape = mat.shape
                        mat = mat.reshape(mat.shape[0], -1)

                    try:
                        U, S, Vt = np.linalg.svd(mat, full_matrices=False)
                    except np.linalg.LinAlgError:
                        pruned_tvs.append(tv.ravel())
                        continue

                    if target_rank == "auto":
                        total_energy = np.sum(S ** 2)
                        if total_energy == 0:
                            pruned_tvs.append(tv.ravel())
                            continue
                        if importance == "variance":
                            cumulative = np.cumsum(S ** 2) / total_energy
                        else:  # energy
                            cumulative = np.cumsum(S ** 2) / total_energy
                        k = np.searchsorted(cumulative, 0.9) + 1
                        k = min(k, len(S))
                    else:
                        k = min(int(target_rank), len(S))

                    S_pruned = S.copy()
                    S_pruned[k:] = 0.0
                    reconstructed = U @ np.diag(S_pruned) @ Vt
                    if orig_nd_shape is not None:
                        reconstructed = reconstructed.reshape(orig_nd_shape)
                    pruned_tvs.append(reconstructed.ravel())

                merged = np.zeros(b.size)
                for w, tv in zip(norm_w, pruned_tvs):
                    merged += w * tv
                result = (b.ravel() + merged).reshape(shape)
                return _from_array(result, original)
        else:
            warnings.warn("AdaRank requires numpy for SVD; falling back to simple averaging.")
            tvs, b_flat, b_shape = _compute_task_vectors_py(tensors, base)
            d = len(tvs[0])
            merged = _py_zeros(d)
            for w, tv in zip(norm_w, tvs):
                merged = _py_add(merged, _py_scale(tv, w))
            result = _py_add(b_flat, merged)
            result = _unflatten(result, b_shape)
            return _from_array(result, original)
