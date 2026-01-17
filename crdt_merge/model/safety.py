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

"""Safety-critical layer detection for model merging.

Identifies layers with high cross-model variance that may carry safety-relevant
information and warrant special handling during merges.

Example::

    from crdt_merge.model.safety import SafetyAnalyzer

    analyzer = SafetyAnalyzer()
    report = analyzer.safety_report([model_a, model_b])
    print(report.risk_score)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies.base import _get_np

__all__ = ["SafetyAnalyzer", "SafetyReport"]

def _compute_variance(values: List[float]) -> float:
    """Compute population variance of a list of floats."""
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n

def _tensor_mean(tensor: Any) -> float:
    """Compute mean of a tensor-like object."""
    np = _get_np()
    if np is not None:
        arr = np.asarray(tensor, dtype=float)
        return float(arr.mean())
    if isinstance(tensor, (list, tuple)):
        flat = _flatten(tensor)
        return sum(flat) / len(flat) if flat else 0.0
    return float(tensor)

def _tensor_variance(tensor: Any) -> float:
    """Compute variance of a tensor-like object."""
    np = _get_np()
    if np is not None:
        arr = np.asarray(tensor, dtype=float)
        return float(arr.var())
    if isinstance(tensor, (list, tuple)):
        flat = _flatten(tensor)
        if not flat:
            return 0.0
        mean = sum(flat) / len(flat)
        return sum((x - mean) ** 2 for x in flat) / len(flat)
    return 0.0

def _flatten(lst) -> List[float]:
    """Flatten a nested list to a flat list of floats."""
    result = []
    if isinstance(lst, (list, tuple)):
        for item in lst:
            result.extend(_flatten(item))
    else:
        result.append(float(lst))
    return result

@dataclass
class SafetyReport:
    """Comprehensive safety analysis of a model merge.

    Attributes
    ----------
    safety_layers : list[str]
        Names of detected safety-critical layers.
    layer_variance : dict[str, float]
        Variance of each layer across models.
    risk_score : float
        Overall merge risk on a 0.0 (safe) to 1.0 (risky) scale.
    recommendation : str
        Human-readable safety recommendation.
    """

    safety_layers: List[str]
    layer_variance: Dict[str, float]
    risk_score: float
    recommendation: str

class SafetyAnalyzer:
    """Detect safety-critical layers based on cross-model variance.

    Layers with high variance across models may encode safety-relevant
    knowledge (alignment, RLHF tuning, guardrails) and should be
    treated carefully during merging.
    """

    def __init__(self) -> None:
        pass

    def _compute_layer_variances(
        self,
        models: List[dict],
        base_model: Optional[dict] = None,
    ) -> Dict[str, float]:
        """Compute cross-model variance per layer.

        For each layer, computes the mean value per model, then measures
        variance of those means across models.
        """
        # Collect all layer names
        all_layers: List[str] = []
        seen = set()
        for m in models:
            for k in m:
                if k not in seen:
                    seen.add(k)
                    all_layers.append(k)

        layer_variance: Dict[str, float] = {}

        for layer in all_layers:
            means = []
            for m in models:
                if layer in m:
                    means.append(_tensor_mean(m[layer]))

            if len(means) < 2:
                layer_variance[layer] = 0.0
            else:
                layer_variance[layer] = _compute_variance(means)

        return layer_variance

    def detect_safety_layers(
        self,
        models: List[dict],
        base_model: Optional[dict] = None,
        threshold: float = 0.1,
    ) -> List[str]:
        """Auto-detect safety-critical layers.

        Parameters
        ----------
        models : list[dict]
            List of model state_dicts to compare.
        base_model : dict | None
            Optional base model for reference.
        threshold : float
            Variance threshold above which a layer is considered safety-critical.

        Returns
        -------
        list[str]
            Names of layers exceeding the variance threshold.
        """
        layer_variance = self._compute_layer_variances(models, base_model)

        safety_layers = [
            layer for layer, var in layer_variance.items()
            if var > threshold
        ]

        return safety_layers

    def safety_report(
        self,
        models: List[dict],
        base_model: Optional[dict] = None,
    ) -> SafetyReport:
        """Generate a comprehensive safety analysis.

        Parameters
        ----------
        models : list[dict]
            List of model state_dicts to analyze.
        base_model : dict | None
            Optional base model for reference.

        Returns
        -------
        SafetyReport
        """
        layer_variance = self._compute_layer_variances(models, base_model)

        # Detect safety layers at default threshold
        safety_layers = [
            layer for layer, var in layer_variance.items()
            if var > 0.1
        ]

        # Compute overall risk score
        if not layer_variance:
            risk_score = 0.0
        else:
            variances = list(layer_variance.values())
            max_var = max(variances) if variances else 0.0
            mean_var = sum(variances) / len(variances)

            # Risk is a combination of max and mean variance
            # Capped at 1.0
            risk_score = min(1.0, (max_var * 0.7 + mean_var * 0.3))

        # Generate recommendation
        if risk_score < 0.1:
            recommendation = (
                "Low risk: Models are highly similar. "
                "Standard merging should be safe."
            )
        elif risk_score < 0.4:
            recommendation = (
                "Moderate risk: Some layers show divergence. "
                "Consider using per-layer strategies for safety-critical layers: "
                + ", ".join(safety_layers[:5])
                if safety_layers else
                "Moderate risk: Some layers show divergence. "
                "Review layer-level differences before merging."
            )
        elif risk_score < 0.7:
            recommendation = (
                "High risk: Significant layer divergence detected. "
                "Use conservative merge strategies (e.g., slerp) for "
                f"{len(safety_layers)} safety-critical layers. "
                "Manual review recommended."
            )
        else:
            recommendation = (
                "Very high risk: Models are substantially different. "
                f"{len(safety_layers)} layers flagged as safety-critical. "
                "Consider whether merging is appropriate. "
                "If proceeding, use protective strategies and thorough evaluation."
            )

        return SafetyReport(
            safety_layers=safety_layers,
            layer_variance=layer_variance,
            risk_score=risk_score,
            recommendation=recommendation,
        )
