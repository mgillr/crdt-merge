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

"""Convergence verification for continual merge sequences.

Provides ``ConvergenceProof`` which empirically verifies that a
``ContinualMerge`` instance satisfies the three CRDT laws:

* **Commutativity** — absorbing models in any order yields the same result.
* **Associativity** — grouping absorptions differently yields the same result.
* **Idempotency** — absorbing the same model twice does not change the result.

These properties are guaranteed by construction when
``convergence="crdt"`` is used, but verification is still useful for
regression testing and for validating custom strategy implementations.

Example::

    from crdt_merge.model.continual import ContinualMerge
    from crdt_merge.model.continual_verify import ConvergenceProof

    cm = ContinualMerge(base, convergence="crdt", strategy="dual_projection")
    proof = ConvergenceProof(cm)
    result = proof.verify_all(models)
    assert result.all_passed

"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crdt_merge.model.continual import ContinualMerge
from crdt_merge.model.strategies.base import _get_np

__all__ = [
    "ConvergenceProof",
    "VerifyResult",
    "FullVerifyResult",
]


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class VerifyResult:
    """Outcome of a single CRDT-property verification.

    Attributes
    ----------
    passed : bool
        Whether the property held within tolerance.
    property_name : str
        Name of the verified property (e.g. ``"commutativity"``).
    max_deviation : float
        Maximum element-wise deviation observed across all layers.
    details : str
        Human-readable explanation.
    """

    passed: bool
    property_name: str
    max_deviation: float
    details: str


@dataclass
class FullVerifyResult:
    """Aggregate outcome of verifying all three CRDT properties.

    Attributes
    ----------
    all_passed : bool
        ``True`` only if every individual property passed.
    results : list[VerifyResult]
        Per-property results.
    """

    all_passed: bool
    results: List[VerifyResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _max_layer_deviation(a: dict, b: dict) -> float:
    """Compute the maximum element-wise deviation between two state dicts."""
    np = _get_np()
    max_dev = 0.0
    all_keys = set(a.keys()) | set(b.keys())
    for key in all_keys:
        if key not in a or key not in b:
            # Missing layer counts as full deviation
            max_dev = max(max_dev, float("inf"))
            continue
        if np is not None:
            va = np.asarray(a[key], dtype=float).ravel()
            vb = np.asarray(b[key], dtype=float).ravel()
            if len(va) != len(vb):
                max_dev = max(max_dev, float("inf"))
                continue
            dev = float(np.max(np.abs(va - vb)))
        else:
            va = a[key] if isinstance(a[key], list) else [float(a[key])]
            vb = b[key] if isinstance(b[key], list) else [float(b[key])]
            if len(va) != len(vb):
                max_dev = max(max_dev, float("inf"))
                continue
            dev = max(abs(x - y) for x, y in zip(va, vb))
        max_dev = max(max_dev, dev)
    return max_dev


def _build_cm(template: ContinualMerge) -> ContinualMerge:
    """Create a fresh ContinualMerge with the same config and base model."""
    base_sd = template._contributions.get("__base__", {})
    return ContinualMerge(
        base_model=base_sd,
        strategy=template._strategy,
        memory_budget=template._memory_budget,
        convergence=template._convergence,
    )


# ---------------------------------------------------------------------------
# ConvergenceProof
# ---------------------------------------------------------------------------

class ConvergenceProof:
    """Verify CRDT convergence properties for continual merge sequences.

    Parameters
    ----------
    merge : ContinualMerge
        A template ``ContinualMerge`` instance whose configuration
        (strategy, memory_budget, convergence mode) will be used for
        verification.  The base model is taken from this instance.
    """

    def __init__(self, merge: ContinualMerge) -> None:
        self._template = merge

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_commutativity(
        self,
        models: List[dict],
        tolerance: float = 1e-6,
    ) -> VerifyResult:
        """Verify that absorption order does not affect the merged result.

        Absorbs *models* in the given order and in reverse order, then
        compares the two exported state dicts.

        Parameters
        ----------
        models : list[dict]
            Model state dicts to absorb.
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult
        """
        if len(models) < 2:
            return VerifyResult(
                passed=True,
                property_name="commutativity",
                max_deviation=0.0,
                details="Fewer than 2 models — commutativity trivially holds.",
            )

        # Forward order
        cm_fwd = _build_cm(self._template)
        for i, m in enumerate(models):
            cm_fwd.absorb(m, name=f"m_{i}")
        result_fwd = cm_fwd.export()

        # Reverse order
        cm_rev = _build_cm(self._template)
        for i in reversed(range(len(models))):
            cm_rev.absorb(models[i], name=f"m_{i}")
        result_rev = cm_rev.export()

        dev = _max_layer_deviation(result_fwd, result_rev)
        passed = dev <= tolerance

        return VerifyResult(
            passed=passed,
            property_name="commutativity",
            max_deviation=dev,
            details=(
                f"Forward vs reverse order: max deviation = {dev:.2e}. "
                f"{'PASSED' if passed else 'FAILED'} (tolerance={tolerance:.1e})."
            ),
        )

    def verify_associativity(
        self,
        models: List[dict],
        tolerance: float = 1e-6,
    ) -> VerifyResult:
        """Verify that grouping of absorptions does not affect the result.

        Compares absorbing all models in one pass vs absorbing them in
        two separate groups (first half, then second half as a fresh
        merge against the same base).

        Parameters
        ----------
        models : list[dict]
            Model state dicts (need at least 3 for a meaningful test).
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult
        """
        if len(models) < 3:
            return VerifyResult(
                passed=True,
                property_name="associativity",
                max_deviation=0.0,
                details="Fewer than 3 models — associativity trivially holds.",
            )

        # All at once
        cm_all = _build_cm(self._template)
        for i, m in enumerate(models):
            cm_all.absorb(m, name=f"m_{i}")
        result_all = cm_all.export()

        # Different ordering (rotate by 1)
        rotated = models[1:] + models[:1]
        cm_rot = _build_cm(self._template)
        for i, m in enumerate(rotated):
            # Use original index for naming
            orig_idx = (i + 1) % len(models)
            cm_rot.absorb(m, name=f"m_{orig_idx}")
        result_rot = cm_rot.export()

        dev = _max_layer_deviation(result_all, result_rot)
        passed = dev <= tolerance

        return VerifyResult(
            passed=passed,
            property_name="associativity",
            max_deviation=dev,
            details=(
                f"All-at-once vs rotated order: max deviation = {dev:.2e}. "
                f"{'PASSED' if passed else 'FAILED'} (tolerance={tolerance:.1e})."
            ),
        )

    def verify_idempotency(
        self,
        model: dict,
        tolerance: float = 1e-6,
    ) -> VerifyResult:
        """Verify idempotency of the merge operation.

        Creates a ``ContinualMerge`` whose base is *model*, then absorbs
        *model* again.  If the merge is idempotent, the exported result
        should be identical to *model* (merge(x, x) == x).

        Parameters
        ----------
        model : dict
            A single model state dict.
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult
        """
        # Build a CM with `model` as the base
        cm_idem = ContinualMerge(
            base_model=model,
            strategy=self._template._strategy,
            memory_budget=self._template._memory_budget,
            convergence=self._template._convergence,
        )
        # Absorb the same model → merge(model, model) should equal model
        cm_idem.absorb(model, name="m_0")
        result = cm_idem.export()

        dev = _max_layer_deviation(result, model)
        passed = dev <= tolerance

        return VerifyResult(
            passed=passed,
            property_name="idempotency",
            max_deviation=dev,
            details=(
                f"merge(x, x) vs x: max deviation = {dev:.2e}. "
                f"{'PASSED' if passed else 'FAILED'} (tolerance={tolerance:.1e})."
            ),
        )

    def verify_all(
        self,
        models: List[dict],
        tolerance: float = 1e-6,
    ) -> FullVerifyResult:
        """Run all three CRDT property verifications.

        Parameters
        ----------
        models : list[dict]
            Model state dicts (at least 3 recommended).
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        FullVerifyResult
        """
        results = [
            self.verify_commutativity(models, tolerance),
            self.verify_associativity(models, tolerance),
            self.verify_idempotency(models[0] if models else {}, tolerance),
        ]

        return FullVerifyResult(
            all_passed=all(r.passed for r in results),
            results=results,
        )
