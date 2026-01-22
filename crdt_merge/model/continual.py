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

"""Continual/sequential model merge — absorb updates without catastrophic forgetting.

Supports two convergence modes:

* **default** (``convergence=None``): weighted average with memory-budget
  decay.  Order of absorption matters (not CRDT).
* **CRDT** (``convergence="crdt"``): backed by ``CRDTMergeState`` per
  layer, guaranteeing commutativity, associativity, and idempotency
  of the full merge sequence.

Example::

    from crdt_merge.model.continual import ContinualMerge

    cm = ContinualMerge(base_model={"layer.weight": [1.0, 2.0]})
    cm.absorb({"layer.weight": [3.0, 4.0]}, name="finetune_v1")
    merged = cm.export()

    # CRDT-backed mode
    cm_crdt = ContinualMerge(
        base_model={"layer.weight": [1.0, 2.0]},
        convergence="crdt",
        strategy="dual_projection",
    )
    cm_crdt.absorb({"layer.weight": [3.0, 4.0]}, name="ft_v1")
    assert cm_crdt.verify_convergence()

"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies.base import _to_array, _from_array, _get_np

__all__ = ["ContinualMerge", "StabilityResult"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StabilityResult:
    """Result of measuring how much of a model's contribution is retained.

    Attributes
    ----------
    retention : float
        Overall retention score in [0, 1].  1.0 means the model's changes
        are fully preserved in the merged output; 0.0 means none are.
    per_layer : dict[str, float]
        Per-layer retention scores.
    """

    retention: float
    per_layer: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _weighted_add(a: Any, b: Any, wa: float, wb: float) -> Any:
    """Compute wa*a + wb*b element-wise."""
    np = _get_np()
    if np is not None:
        aa = np.asarray(a, dtype=float)
        bb = np.asarray(b, dtype=float)
        return (wa * aa + wb * bb).tolist()
    # Fallback: plain lists
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return [wa * x + wb * y for x, y in zip(a, b)]
    # Scalars
    return wa * a + wb * b


def _scale(tensor: Any, s: float) -> Any:
    """Multiply tensor by scalar."""
    np = _get_np()
    if np is not None:
        return (np.asarray(tensor, dtype=float) * s).tolist()
    if isinstance(tensor, (list, tuple)):
        return [x * s for x in tensor]
    return tensor * s


def _cosine_similarity(a: Any, b: Any) -> float:
    """Cosine similarity between two array-likes, clamped to [0, 1]."""
    np = _get_np()
    if np is not None:
        aa = np.asarray(a, dtype=float).ravel()
        bb = np.asarray(b, dtype=float).ravel()
        dot = float(np.dot(aa, bb))
        na = float(np.linalg.norm(aa))
        nb = float(np.linalg.norm(bb))
        if na < 1e-15 or nb < 1e-15:
            return 1.0  # zero vectors treated as identical
        return max(0.0, min(1.0, dot / (na * nb)))
    # Pure Python
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na < 1e-15 or nb < 1e-15:
            return 1.0
        return max(0.0, min(1.0, dot / (na * nb)))
    return 1.0


# ---------------------------------------------------------------------------
# ContinualMerge
# ---------------------------------------------------------------------------

class ContinualMerge:
    """Absorb model updates over time without catastrophic forgetting.

    Parameters
    ----------
    base_model : dict
        Initial state_dict to start from.
    strategy : str
        Merge strategy name (e.g. ``"weight_average"``, ``"dual_projection"``).
    memory_budget : float
        Fraction 0.0-1.0 controlling how much weight older models retain.
        1.0 = equal weight to all absorbed models, 0.1 = heavily favor recent.
    convergence : str | None
        Convergence mode.  ``"crdt"`` enables CRDT-backed merging via
        ``CRDTMergeState`` per layer, guaranteeing order-independent
        convergence.  ``None`` (default) uses the classic weighted-average
        path for full backward compatibility.
    """

    def __init__(
        self,
        base_model: dict,
        strategy: str = "weight_average",
        memory_budget: float = 1.0,
        convergence: Optional[str] = None,
    ) -> None:
        self._strategy = strategy
        self._memory_budget = max(0.01, min(1.0, memory_budget))
        self._convergence = convergence

        # Store individual contributions for replace semantics
        self._contributions: Dict[str, dict] = {}
        self._weights: Dict[str, float] = {}
        self._order: List[str] = []
        self._history: List[dict] = []

        # Absorb base model
        base_name = "__base__"
        self._contributions[base_name] = copy.deepcopy(base_model)
        self._weights[base_name] = 1.0
        self._order.append(base_name)

        # CRDT state per layer (populated lazily when convergence="crdt")
        self._crdt_states: Dict[str, Any] = {}
        if self._convergence == "crdt":
            self._init_crdt_states(base_model, base_name)

    # ------------------------------------------------------------------
    # CRDT state management
    # ------------------------------------------------------------------

    def _init_crdt_states(self, base_model: dict, model_name: str) -> None:
        """Initialize CRDTMergeState for each layer from the base model."""
        from crdt_merge.model.crdt_state import CRDTMergeState

        for layer_name, tensor in base_model.items():
            state = CRDTMergeState(self._strategy)
            state.add(tensor, model_id=model_name, weight=1.0)
            self._crdt_states[layer_name] = state

    def _add_to_crdt(self, model: dict, name: str, weight: float) -> None:
        """Add a model's layers to the per-layer CRDT states."""
        from crdt_merge.model.crdt_state import CRDTMergeState

        for layer_name, tensor in model.items():
            if layer_name not in self._crdt_states:
                state = CRDTMergeState(self._strategy)
                # Add base for this layer if available
                base_sd = self._contributions.get("__base__", {})
                if layer_name in base_sd:
                    state.add(
                        base_sd[layer_name],
                        model_id="__base__",
                        weight=self._weights.get("__base__", 1.0),
                    )
                self._crdt_states[layer_name] = state
            self._crdt_states[layer_name].add(
                tensor, model_id=name, weight=weight,
            )

    def _remove_from_crdt(self, name: str) -> None:
        """Remove a model from all per-layer CRDT states."""
        for state in self._crdt_states.values():
            state.remove(name)

    # ------------------------------------------------------------------
    # Public API (backward-compatible)
    # ------------------------------------------------------------------

    def absorb(
        self,
        model: dict,
        weight: float = 1.0,
        name: Optional[str] = None,
        replace: Optional[str] = None,
    ) -> None:
        """Absorb a model update into the current merged state.

        Parameters
        ----------
        model : dict
            State dict of the model to absorb.
        weight : float
            Contribution weight for this model.
        name : str | None
            Optional name for this contribution (for tracking/replace).
        replace : str | None
            If given, remove the named model's contribution before absorbing.
        """
        replaced = None
        if replace and replace in self._contributions:
            if self._convergence == "crdt":
                self._remove_from_crdt(replace)
            del self._contributions[replace]
            del self._weights[replace]
            self._order.remove(replace)
            replaced = replace

        if name is None:
            name = f"model_{len(self._order)}"

        # Ensure unique name
        orig_name = name
        counter = 1
        while name in self._contributions:
            name = f"{orig_name}_{counter}"
            counter += 1

        self._contributions[name] = copy.deepcopy(model)
        self._weights[name] = weight
        self._order.append(name)

        if self._convergence == "crdt":
            self._add_to_crdt(model, name, weight)

        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "weight": weight,
            "replaced": replaced,
        })

    def export(self) -> dict:
        """Return the current merged state_dict."""
        if self._convergence == "crdt":
            return self._export_crdt()
        return self._export_classic()

    @property
    def history(self) -> List[dict]:
        """List of absorption events."""
        return list(self._history)

    @property
    def current_weights(self) -> Dict[str, float]:
        """Effective contribution weight of each absorbed model (after decay)."""
        ew = self._compute_effective_weights()
        total = sum(ew.values())
        if total == 0:
            return {k: 0.0 for k in ew}
        return {k: v / total for k, v in ew.items()}

    def reset(self, base_model: dict) -> None:
        """Restart from a new base model, clearing all history."""
        self._contributions.clear()
        self._weights.clear()
        self._order.clear()
        self._history.clear()
        self._crdt_states.clear()

        base_name = "__base__"
        self._contributions[base_name] = copy.deepcopy(base_model)
        self._weights[base_name] = 1.0
        self._order.append(base_name)

        if self._convergence == "crdt":
            self._init_crdt_states(base_model, base_name)

    # ------------------------------------------------------------------
    # New v0.8.3 methods
    # ------------------------------------------------------------------

    def verify_convergence(self) -> bool:
        """Check whether the current merge configuration guarantees CRDT convergence.

        Returns ``True`` when *all* of these hold:

        1. ``convergence="crdt"`` was set at construction.
        2. Per-layer CRDT states have been initialised.
        3. The underlying strategy declares ``commutative=True``,
           ``associative=True``, and ``idempotent=True`` (or the CRDT
           state container provides those guarantees).

        Returns
        -------
        bool
        """
        if self._convergence != "crdt":
            return False
        if not self._crdt_states:
            return False
        # The CRDTMergeState container guarantees convergence by construction
        # (set-union semantics), regardless of the underlying strategy.
        return True

    def measure_stability(self, model_name: str) -> StabilityResult:
        """Measure how much of *model_name*'s contribution is retained.

        For each layer, computes the cosine similarity between the
        model's task vector (delta from base) and the merged task vector.
        A score of 1.0 means the model's change direction is perfectly
        preserved; 0.0 means it was entirely lost.

        Parameters
        ----------
        model_name : str
            Name of a previously absorbed model.

        Returns
        -------
        StabilityResult

        Raises
        ------
        KeyError
            If *model_name* was not absorbed.
        """
        if model_name not in self._contributions:
            raise KeyError(
                f"Model '{model_name}' not found.  "
                f"Known: {[n for n in self._order if n != '__base__']}"
            )

        base_sd = self._contributions.get("__base__", {})
        model_sd = self._contributions[model_name]
        merged_sd = self.export()

        per_layer: Dict[str, float] = {}
        for layer_name in model_sd:
            if layer_name not in base_sd or layer_name not in merged_sd:
                per_layer[layer_name] = 0.0
                continue

            np = _get_np()
            if np is not None:
                base_arr = np.asarray(base_sd[layer_name], dtype=float).ravel()
                model_arr = np.asarray(model_sd[layer_name], dtype=float).ravel()
                merged_arr = np.asarray(merged_sd[layer_name], dtype=float).ravel()
            else:
                base_arr = base_sd[layer_name]
                model_arr = model_sd[layer_name]
                merged_arr = merged_sd[layer_name]

            # Task vectors (delta from base)
            if np is not None:
                model_delta = model_arr - base_arr
                merged_delta = merged_arr - base_arr
            else:
                model_delta = [m - b for m, b in zip(model_arr, base_arr)]
                merged_delta = [m - b for m, b in zip(merged_arr, base_arr)]

            per_layer[layer_name] = _cosine_similarity(model_delta, merged_delta)

        if per_layer:
            overall = sum(per_layer.values()) / len(per_layer)
        else:
            overall = 0.0

        return StabilityResult(retention=overall, per_layer=per_layer)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _export_crdt(self) -> dict:
        """Export via CRDT state — order-independent resolution."""
        merged: dict = {}
        for layer_name, state in self._crdt_states.items():
            merged[layer_name] = state.resolve()
            # Convert numpy arrays to lists for consistency
            np = _get_np()
            if np is not None and hasattr(merged[layer_name], "tolist"):
                merged[layer_name] = merged[layer_name].tolist()
        return merged

    def _export_classic(self) -> dict:
        """Export using the classic weighted-average path."""
        if not self._contributions:
            return {}

        # Apply memory budget decay
        effective_weights = self._compute_effective_weights()
        total_w = sum(effective_weights.values())
        if total_w == 0:
            total_w = 1.0

        # Collect all layer names
        all_layers: List[str] = []
        seen: set = set()
        for name in self._order:
            for layer in self._contributions[name]:
                if layer not in seen:
                    seen.add(layer)
                    all_layers.append(layer)

        merged: dict = {}
        for layer in all_layers:
            accum = None
            for model_name in self._order:
                sd = self._contributions[model_name]
                if layer not in sd:
                    continue
                ew = effective_weights[model_name] / total_w
                if accum is None:
                    accum = _scale(sd[layer], ew)
                else:
                    accum = _weighted_add(accum, sd[layer], 1.0, ew)
            merged[layer] = accum

        return merged

    def _compute_effective_weights(self) -> Dict[str, float]:
        """Compute effective weights with memory budget decay."""
        n = len(self._order)
        effective = {}
        for i, name in enumerate(self._order):
            base_weight = self._weights[name]
            if self._memory_budget >= 1.0:
                effective[name] = base_weight
            else:
                age = n - 1 - i
                decay = math.pow(self._memory_budget, age)
                effective[name] = base_weight * decay
        return effective
