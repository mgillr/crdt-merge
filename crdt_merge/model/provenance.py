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

"""Per-parameter provenance tracking for model merges (🦄 Unicorn Feature #3).

Tracks which source model contributed most to each layer of a merged model,
computes conflict scores, and exports provenance reports in JSON/CSV.

Example::

    from crdt_merge.model.provenance import ProvenanceTracker

    tracker = ProvenanceTracker()
    prov = tracker.track_merge("layer.0.weight", tensors, weights, "weight_average", result)
    summary = tracker.summary()
    print(export_provenance(summary, format="json"))
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from crdt_merge.model.strategies.base import (
    _get_np,
    _normalize_weights,
    _to_array,
)

__all__ = [
    "ProvenanceTracker",
    "ProvenanceSummary",
    "LayerProvenance",
    "export_provenance",
    "compute_contribution",
    "compute_conflict_score",
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LayerProvenance:
    """Provenance information for a single layer.

    Attributes
    ----------
    layer_name : str
        Name of the layer.
    strategy_used : str
        Strategy that was applied to merge this layer.
    dominant_source : int
        Index of the model that contributed most.
    contribution_map : dict[int, float]
        Mapping from model index to contribution fraction (sums to ~1.0).
    conflict_score : float
        0.0 (total agreement) to 1.0 (total conflict).
    metadata : dict
        Strategy-specific metadata.
    """

    layer_name: str
    strategy_used: str
    dominant_source: int
    contribution_map: Dict[int, float]
    conflict_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProvenanceSummary:
    """Aggregated provenance across all layers.

    Attributes
    ----------
    overall_conflict : float
        Average conflict score across all layers.
    dominant_model : int
        Model index that contributed most overall.
    layer_conflict_ranking : list[str]
        Layer names sorted by conflict score (highest first).
    per_layer : dict[str, LayerProvenance]
        Per-layer provenance data.
    """

    overall_conflict: float
    dominant_model: int
    layer_conflict_ranking: List[str]
    per_layer: Dict[str, LayerProvenance]

# ---------------------------------------------------------------------------
# Core computation functions
# ---------------------------------------------------------------------------

def compute_contribution(
    tensors: list,
    weights: Optional[List[float]],
    strategy_name: str,
) -> Dict[int, float]:
    """Compute per-model contribution fractions.

    For weight-based strategies (weight_average, linear, slerp):
        contribution = normalized weight.
    For selection-based strategies (ties, task_arithmetic):
        contribution is estimated from weight magnitudes.

    Parameters
    ----------
    tensors : list
        List of tensor-like objects from each model.
    weights : list[float] | None
        Per-model weights.
    strategy_name : str
        Name of the merge strategy used.

    Returns
    -------
    dict[int, float]
        Model index → contribution fraction.
    """
    n = len(tensors)
    if n == 0:
        return {}

    norm_w = _normalize_weights(weights, n)

    # For most strategies, contribution ~ normalized weight
    contrib: Dict[int, float] = {}
    for i in range(n):
        contrib[i] = norm_w[i]

    return contrib

def compute_conflict_score(tensors: list) -> float:
    """Compute conflict score between tensors from different models.

    Conflict = mean(variance across models) / (mean(magnitude) + epsilon).
    Result is clamped to [0, 1].

    Parameters
    ----------
    tensors : list
        List of tensor-like objects from each model.

    Returns
    -------
    float
        Conflict score in [0, 1].
    """
    if len(tensors) < 2:
        return 0.0

    np = _get_np()
    eps = 1e-10

    if np is not None:
        arrays = [np.asarray(_to_array(t), dtype=float).ravel() for t in tensors]
        # Ensure same length
        min_len = min(len(a) for a in arrays)
        if min_len == 0:
            return 0.0
        arrays = [a[:min_len] for a in arrays]

        stacked = np.stack(arrays, axis=0)  # (n_models, n_params)
        variance = np.var(stacked, axis=0)  # per-parameter variance
        mean_var = float(np.mean(variance))
        mean_mag = float(np.mean(np.abs(stacked))) + eps

        score = mean_var / (mean_mag * mean_mag + eps)
        # Normalize with sigmoid-like clamping
        score = min(1.0, score)
        return max(0.0, score)
    else:
        # Pure Python
        flat = []
        for t in tensors:
            arr = _to_array(t)
            if isinstance(arr, list):
                if arr and isinstance(arr[0], list):
                    flat.append([x for row in arr for x in row])
                else:
                    flat.append(list(arr))
            else:
                flat.append([float(arr)])

        min_len = min(len(f) for f in flat)
        if min_len == 0:
            return 0.0
        flat = [f[:min_len] for f in flat]
        n = len(flat)

        # Compute mean per parameter
        total_var = 0.0
        total_mag = 0.0
        for j in range(min_len):
            vals = [flat[i][j] for i in range(n)]
            mean = sum(vals) / n
            var = sum((v - mean) ** 2 for v in vals) / n
            total_var += var
            total_mag += sum(abs(v) for v in vals) / n

        mean_var = total_var / min_len
        mean_mag = total_mag / min_len + eps
        score = mean_var / (mean_mag * mean_mag + eps)
        return max(0.0, min(1.0, score))

# ---------------------------------------------------------------------------
# ProvenanceTracker
# ---------------------------------------------------------------------------

class ProvenanceTracker:
    """Track provenance information across multiple layer merges.

    Usage::

        tracker = ProvenanceTracker()
        for layer_name in layer_names:
            tracker.track_merge(layer_name, tensors, weights, strategy_name, result)
        summary = tracker.summary()
    """

    def __init__(self) -> None:
        self._layers: OrderedDict[str, LayerProvenance] = OrderedDict()

    def track_merge(
        self,
        layer_name: str,
        tensors: list,
        weights: Optional[List[float]],
        strategy_name: str,
        result: Any = None,
    ) -> LayerProvenance:
        """Track a single layer merge.

        Parameters
        ----------
        layer_name : str
            Name of the layer being merged.
        tensors : list
            Source tensors (one per model).
        weights : list[float] | None
            Per-model weights.
        strategy_name : str
            Name of the merge strategy used.
        result : Any
            The merged result tensor (optional, for detailed analysis).

        Returns
        -------
        LayerProvenance
            Provenance record for this layer.
        """
        contribution = compute_contribution(tensors, weights, strategy_name)
        conflict = compute_conflict_score(tensors)

        # Determine dominant source
        dominant = 0
        if contribution:
            dominant = max(contribution, key=contribution.get)

        metadata: Dict[str, Any] = {
            "num_sources": len(tensors),
        }

        prov = LayerProvenance(
            layer_name=layer_name,
            strategy_used=strategy_name,
            dominant_source=dominant,
            contribution_map=contribution,
            conflict_score=conflict,
            metadata=metadata,
        )

        self._layers[layer_name] = prov
        return prov

    def summary(self) -> ProvenanceSummary:
        """Compute aggregated provenance summary.

        Returns
        -------
        ProvenanceSummary
        """
        if not self._layers:
            return ProvenanceSummary(
                overall_conflict=0.0,
                dominant_model=0,
                layer_conflict_ranking=[],
                per_layer={},
            )

        # Average conflict
        conflicts = [lp.conflict_score for lp in self._layers.values()]
        overall_conflict = sum(conflicts) / len(conflicts)

        # Count dominance across layers
        dominance_count: Dict[int, int] = {}
        for lp in self._layers.values():
            d = lp.dominant_source
            dominance_count[d] = dominance_count.get(d, 0) + 1

        dominant_model = max(dominance_count, key=dominance_count.get) if dominance_count else 0

        # Rank layers by conflict
        layer_conflict_ranking = sorted(
            self._layers.keys(),
            key=lambda name: self._layers[name].conflict_score,
            reverse=True,
        )

        return ProvenanceSummary(
            overall_conflict=overall_conflict,
            dominant_model=dominant_model,
            layer_conflict_ranking=layer_conflict_ranking,
            per_layer=dict(self._layers),
        )

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_provenance(summary: ProvenanceSummary, format: str = "json") -> str:
    """Export provenance summary to a string.

    Parameters
    ----------
    summary : ProvenanceSummary
        The summary to export.
    format : str
        ``"json"`` or ``"csv"``.

    Returns
    -------
    str
        Serialized provenance data.
    """
    if format == "json":
        data = {
            "overall_conflict": summary.overall_conflict,
            "dominant_model": summary.dominant_model,
            "layer_conflict_ranking": summary.layer_conflict_ranking,
            "layers": {},
        }
        for name, lp in summary.per_layer.items():
            data["layers"][name] = {
                "strategy_used": lp.strategy_used,
                "dominant_source": lp.dominant_source,
                "contribution_map": {str(k): v for k, v in lp.contribution_map.items()},
                "conflict_score": lp.conflict_score,
                "metadata": lp.metadata,
            }
        return json.dumps(data, indent=2)

    elif format == "csv":
        lines = ["layer_name,strategy_used,dominant_source,conflict_score"]
        for name, lp in summary.per_layer.items():
            lines.append(
                f"{name},{lp.strategy_used},{lp.dominant_source},{lp.conflict_score:.6f}"
            )
        return "\n".join(lines)

    else:
        raise ValueError(f"Unsupported format: {format}. Use 'json' or 'csv'.")
