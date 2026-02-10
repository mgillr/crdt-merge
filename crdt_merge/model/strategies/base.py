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

"""ModelMergeStrategy abstract base class.

All model merge strategies inherit from this. Provides:
- Common interface for merge operations
- CRDT property declaration
- Paper reference metadata
- Runtime verification hooks
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

__all__ = [
    "CRDTTier",
    "MergeResult",
    "ModelMergeStrategy",
]

class CRDTTier(str, Enum):
    """Classification of a strategy's CRDT compliance.

    TRUE_CRDT     — Satisfies commutativity, associativity, and idempotency.
                    Safe for fully decentralised merge in any order.
    PARTIAL_CRDT  — Satisfies at least one CRDT law but not all three.
                    Safe for restricted merge topologies (e.g. star, hub-and-spoke).
    NOT_CRDT      — Satisfies none of the three CRDT laws (or is stochastic).
                    Requires a centralised merge coordinator.
    """

    TRUE_CRDT = "TRUE_CRDT"
    PARTIAL_CRDT = "PARTIAL_CRDT"
    NOT_CRDT = "NOT_CRDT"

# ---------------------------------------------------------------------------
# Lazy optional imports
# ---------------------------------------------------------------------------

def _get_np():
    """Return numpy if available, else None."""
    try:
        import numpy as np
        return np
    except ImportError:
        return None

def _get_torch():
    """Return torch if available, else None."""
    try:
        import torch
        return torch
    except ImportError:
        return None

# ---------------------------------------------------------------------------
# MergeResult
# ---------------------------------------------------------------------------

@dataclass
class MergeResult:
    """Result of a model merge operation.

    Attributes:
        tensor: The merged tensor (array-like).
        provenance: Optional per-parameter provenance mapping.
        metadata: Strategy-specific metadata dict.
    """

    tensor: Any
    provenance: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_array(tensor: Any) -> Any:
    """Convert any tensor-like to a workable array.

    Priority:
    1. If it's a torch Tensor → convert to numpy (detach+cpu first).
    2. If it's a numpy ndarray → pass through.
    3. If it's a plain list/tuple → convert to numpy if available, else keep.
    """
    np = _get_np()
    torch = _get_torch()

    if torch is not None and isinstance(tensor, torch.Tensor):
        return tensor.detach().cpu().numpy()

    if np is not None:
        if isinstance(tensor, np.ndarray):
            return tensor
        # list / tuple → numpy
        try:
            return np.asarray(tensor, dtype=float)
        except (TypeError, ValueError):
            return tensor

    # Fallback: no numpy — work with plain lists
    if isinstance(tensor, (list, tuple)):
        return list(tensor)
    return tensor

def _from_array(array: Any, original: Any) -> Any:
    """Convert *array* back to the same type as *original*.

    If *original* was a torch Tensor we return a torch Tensor.
    If *original* was a plain list we return a list.
    Otherwise we return as-is (numpy).
    """
    torch = _get_torch()
    np = _get_np()

    if torch is not None and isinstance(original, torch.Tensor):
        if np is not None and isinstance(array, np.ndarray):
            return torch.from_numpy(array).to(original.device)
        return torch.tensor(array, device=original.device)

    if isinstance(original, list):
        if np is not None and isinstance(array, np.ndarray):
            return array.tolist()
        return list(array) if not isinstance(array, list) else array

    if isinstance(original, tuple):
        if np is not None and isinstance(array, np.ndarray):
            return tuple(array.tolist())
        return tuple(array) if not isinstance(array, tuple) else array

    return array

def _normalize_weights(weights: Optional[List[float]], n: int) -> List[float]:
    """Normalize *weights* to sum to 1.  If *weights* is ``None``, return uniform."""
    if weights is None:
        if n == 0:
            return []
        return [1.0 / n] * n

    if len(weights) != n:
        raise ValueError(
            f"weights length ({len(weights)}) != number of tensors ({n})"
        )

    total = sum(weights)
    if total == 0:
        raise ValueError("Sum of weights must not be zero")

    return [w / total for w in weights]

# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class ModelMergeStrategy(ABC):
    """Abstract base for all model-merge strategies.

    Subclasses MUST implement:
    - ``merge``
    - ``name``        (property)
    - ``category``    (property)
    - ``crdt_properties`` (property)

    Subclasses SHOULD implement:
    - ``paper_reference`` (property, default ``""``)
    """

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Merge a list of array-like tensors into one.

        Parameters
        ----------
        tensors : list
            List of array-like objects (numpy, torch, or plain lists).
        weights : list[float] | None
            Per-tensor weights; ``None`` for uniform.
        base : Any | None
            Optional base tensor for delta-based strategies.
        **kwargs
            Strategy-specific parameters.

        Returns
        -------
        Any
            The merged tensor (same type as first input element).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Short unique identifier for this strategy (e.g. ``'slerp'``)."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``)."""
        ...

    @property
    @abstractmethod
    def crdt_properties(self) -> Dict[str, Any]:
        """CRDT property declaration.

        Must return a dict with at least:
        ``{"commutative": bool, "associative": bool, "idempotent": bool}``
        Values may also be ``"conditional"`` to indicate conditional compliance.
        """
        ...

    @property
    def paper_reference(self) -> str:
        """Academic citation or URL for the strategy's paper."""
        return ""

    @property
    def crdt_tier(self) -> CRDTTier:
        """Auto-classify this strategy's CRDT compliance tier.

        Based on the declared ``crdt_properties``:
        - All three True  →  TRUE_CRDT
        - At least one True  →  PARTIAL_CRDT
        - None True  →  NOT_CRDT
        """
        props = self.crdt_properties
        bools = [
            props.get("commutative") is True,
            props.get("associative") is True,
            props.get("idempotent") is True,
        ]
        if all(bools):
            return CRDTTier.TRUE_CRDT
        if any(bools):
            return CRDTTier.PARTIAL_CRDT
        return CRDTTier.NOT_CRDT

    # ------------------------------------------------------------------
    # Runtime CRDT verification
    # ------------------------------------------------------------------

    def verify_crdt(
        self,
        gen_fn=None,
        trials: int = 100,
        base_gen_fn=None,
    ) -> Dict[str, Any]:
        """Empirically verify CRDT properties via random trials.

        Parameters
        ----------
        gen_fn : callable | None
            ``gen_fn()`` should return a random array-like tensor.
            Defaults to generating random 10-element lists.
        trials : int
            Number of random trials per property.
        base_gen_fn : callable | None
            ``base_gen_fn()`` should return a random base tensor.
            If ``None`` and the strategy requires ``base=``, a base
            tensor is auto-generated via ``gen_fn()``.

        Returns
        -------
        dict
            ``{"commutative": bool, "associative": bool, "idempotent": bool,
              "failures": {...}}``
        """

        if gen_fn is None:
            def gen_fn():
                return [random.random() for _ in range(10)]

        # Detect if this strategy requires a base tensor
        _needs_base = False
        try:
            test_a, test_b = gen_fn(), gen_fn()
            self.merge([test_a, test_b])
        except (ValueError, TypeError) as exc:
            if "base" in str(exc).lower():
                _needs_base = True

        def _make_base():
            if base_gen_fn is not None:
                return base_gen_fn()
            return gen_fn()

        def _merge(tensors, *, base_override=None):
            if _needs_base:
                return self.merge(tensors, base=(base_override if base_override is not None else _make_base()))
            return self.merge(tensors)

        results: Dict[str, Any] = {
            "commutative": True,
            "associative": True,
            "idempotent": True,
            "needs_base": _needs_base,
            "failures": {
                "commutative": 0,
                "associative": 0,
                "idempotent": 0,
            },
        }

        for _ in range(trials):
            a, b, c = gen_fn(), gen_fn(), gen_fn()
            # Use a CONSISTENT base for all merge calls within a single trial
            trial_base = _make_base() if _needs_base else None

            # --- commutativity: merge([a, b]) == merge([b, a]) ---
            try:
                ab = _merge([a, b], base_override=trial_base)
                ba = _merge([b, a], base_override=trial_base)
                if not _approx_equal(ab, ba):
                    results["commutative"] = False
                    results["failures"]["commutative"] += 1
            except Exception:
                results["commutative"] = False
                results["failures"]["commutative"] += 1

            # --- associativity: merge([merge([a,b]), c]) == merge([a, merge([b,c])]) ---
            try:
                ab = _merge([a, b], base_override=trial_base)
                ab_c = _merge([ab, c], base_override=trial_base)
                bc = _merge([b, c], base_override=trial_base)
                a_bc = _merge([a, bc], base_override=trial_base)
                if not _approx_equal(ab_c, a_bc):
                    results["associative"] = False
                    results["failures"]["associative"] += 1
            except Exception:
                results["associative"] = False
                results["failures"]["associative"] += 1

            # --- idempotency: merge([a, a]) == a ---
            try:
                aa = _merge([a, a], base_override=trial_base)
                if not _approx_equal(aa, a):
                    results["idempotent"] = False
                    results["failures"]["idempotent"] += 1
            except Exception:
                results["idempotent"] = False
                results["failures"]["idempotent"] += 1

        return results

def _approx_equal(a: Any, b: Any, tol: float = 1e-7) -> bool:
    """Element-wise approximate equality for array-like objects."""
    np = _get_np()

    # Convert to comparable forms
    def _to_list(x):
        if np is not None and isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, (list, tuple)):
            return list(x)
        torch = _get_torch()
        if torch is not None and isinstance(x, torch.Tensor):
            return x.detach().cpu().tolist()
        return x

    la, lb = _to_list(a), _to_list(b)

    if isinstance(la, list) and isinstance(lb, list):
        if len(la) != len(lb):
            return False
        return all(abs(x - y) < tol for x, y in zip(la, lb))

    # scalar
    try:
        return abs(la - lb) < tol
    except TypeError:
        return la == lb
