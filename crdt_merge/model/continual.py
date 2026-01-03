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

"""Continual/sequential model merge — absorb updates without catastrophic forgetting.

Example::

    from crdt_merge.model.continual import ContinualMerge

    cm = ContinualMerge(base_model={"layer.weight": [1.0, 2.0]})
    cm.absorb({"layer.weight": [3.0, 4.0]}, name="finetune_v1")
    merged = cm.export()
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies.base import _to_array, _from_array, _get_np

__all__ = ["ContinualMerge"]


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


class ContinualMerge:
    """Absorb model updates over time without catastrophic forgetting.

    Parameters
    ----------
    base_model : dict
        Initial state_dict to start from.
    strategy : str
        Merge strategy name (currently ``weight_average`` supported).
    memory_budget : float
        Fraction 0.0-1.0 controlling how much weight older models retain.
        1.0 = equal weight to all absorbed models, 0.1 = heavily favor recent.
    """

    def __init__(
        self,
        base_model: dict,
        strategy: str = "weight_average",
        memory_budget: float = 1.0,
    ) -> None:
        self._strategy = strategy
        self._memory_budget = max(0.01, min(1.0, memory_budget))
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

        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "weight": weight,
            "replaced": replaced,
        })

    def export(self) -> dict:
        """Return the current merged state_dict."""
        if not self._contributions:
            return {}

        # Apply memory budget decay: older models get exponentially less weight
        effective_weights = self._compute_effective_weights()

        total_w = sum(effective_weights.values())
        if total_w == 0:
            total_w = 1.0

        # Collect all layer names
        all_layers: List[str] = []
        seen = set()
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

        base_name = "__base__"
        self._contributions[base_name] = copy.deepcopy(base_model)
        self._weights[base_name] = 1.0
        self._order.append(base_name)

    def _compute_effective_weights(self) -> Dict[str, float]:
        """Compute effective weights with memory budget decay."""
        n = len(self._order)
        effective = {}
        for i, name in enumerate(self._order):
            base_weight = self._weights[name]
            if self._memory_budget >= 1.0:
                # No decay
                effective[name] = base_weight
            else:
                # Exponential decay: older models get less weight
                # Position 0 = oldest, n-1 = newest
                age = n - 1 - i  # 0 for newest, n-1 for oldest
                decay = math.pow(self._memory_budget, age)
                effective[name] = base_weight * decay
        return effective
