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

"""Conflict heatmaps for model merge analysis (🦄 Unicorn Feature #4).

Visualize parameter-level conflict across models, compatible with
D3.js / Plotly for interactive exploration.

Example::

    from crdt_merge.model.heatmap import ConflictHeatmap
    from crdt_merge.model.provenance import ProvenanceTracker

    tracker = ProvenanceTracker()
    # ... track merges ...
    summary = tracker.summary()
    heatmap = ConflictHeatmap.from_merge(summary)
    print(heatmap.most_conflicted_layers(5))
    heatmap.to_json("conflict.json")
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from crdt_merge.model.strategies.base import _get_np, _to_array
from crdt_merge.model.provenance import ProvenanceSummary, compute_conflict_score

__all__ = ["ConflictHeatmap"]

# ---------------------------------------------------------------------------
# LayerDetail
# ---------------------------------------------------------------------------

@dataclass
class LayerDetail:
    """Detailed parameter-level analysis for a single layer.

    Attributes
    ----------
    variance_map : list[float]
        Per-parameter variance across models.
    sign_agreement : float
        Fraction of parameters where all models agree on sign [0, 1].
    magnitude_spread : float
        Standard deviation of magnitudes across models.
    """

    variance_map: List[float]
    sign_agreement: float
    magnitude_spread: float

# ---------------------------------------------------------------------------
# ConflictHeatmap
# ---------------------------------------------------------------------------

class ConflictHeatmap:
    """Conflict heatmap over model layers.

    Use :meth:`from_merge` to build from provenance data, or
    :meth:`from_models` to compute directly from model state_dicts.
    """

    def __init__(
        self,
        layer_conflicts: Dict[str, float],
        model_contributions: Dict[str, Dict[int, float]],
        num_models: int,
        raw_tensors: Optional[Dict[str, List]] = None,
    ) -> None:
        self._layer_conflicts = layer_conflicts
        self._model_contributions = model_contributions
        self._num_models = num_models
        self._raw_tensors = raw_tensors or {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_merge(cls, provenance_summary: ProvenanceSummary) -> "ConflictHeatmap":
        """Build heatmap from provenance data.

        Parameters
        ----------
        provenance_summary : ProvenanceSummary
            Output from :meth:`ProvenanceTracker.summary`.
        """
        layer_conflicts: Dict[str, float] = {}
        model_contributions: Dict[str, Dict[int, float]] = {}
        num_models = 0

        for name, lp in provenance_summary.per_layer.items():
            layer_conflicts[name] = lp.conflict_score
            model_contributions[name] = dict(lp.contribution_map)
            if lp.contribution_map:
                num_models = max(num_models, max(lp.contribution_map.keys()) + 1)

        return cls(
            layer_conflicts=layer_conflicts,
            model_contributions=model_contributions,
            num_models=num_models,
        )

    @classmethod
    def from_models(
        cls,
        models: List[Dict[str, Any]],
        base: Optional[Dict[str, Any]] = None,
    ) -> "ConflictHeatmap":
        """Compute heatmap directly from model state_dicts.

        Parameters
        ----------
        models : list[dict]
            List of model state_dicts.
        base : dict | None
            Optional base model. If provided, conflicts are computed
            on deltas (model - base).
        """
        if not models:
            return cls(
                layer_conflicts={},
                model_contributions={},
                num_models=0,
            )

        # Collect all layer names
        all_layers = []
        seen = set()
        for m in models:
            for k in m:
                if k not in seen:
                    seen.add(k)
                    all_layers.append(k)

        n = len(models)
        layer_conflicts: Dict[str, float] = {}
        model_contributions: Dict[str, Dict[int, float]] = {}
        raw_tensors: Dict[str, List] = {}

        for layer_name in all_layers:
            tensors = []
            indices = []
            for i, m in enumerate(models):
                if layer_name in m:
                    t = m[layer_name]
                    if base is not None and layer_name in base:
                        # Compute delta
                        np = _get_np()
                        t_arr = _to_array(t)
                        b_arr = _to_array(base[layer_name])
                        if np is not None:
                            import numpy
                            t_arr = numpy.asarray(t_arr, dtype=float)
                            b_arr = numpy.asarray(b_arr, dtype=float)
                            t = t_arr - b_arr
                        else:
                            if isinstance(t_arr, list) and isinstance(b_arr, list):
                                t = [a - b for a, b in zip(t_arr, b_arr)]
                    tensors.append(t)
                    indices.append(i)

            if tensors:
                conflict = compute_conflict_score(tensors)
                layer_conflicts[layer_name] = conflict

                # Contribution based on L2 norms
                contrib: Dict[int, float] = {}
                np = _get_np()
                norms = []
                for idx, t in zip(indices, tensors):
                    arr = _to_array(t)
                    if np is not None:
                        import numpy
                        norm = float(numpy.linalg.norm(numpy.asarray(arr, dtype=float).ravel()))
                    else:
                        flat = arr if isinstance(arr, list) else [float(arr)]
                        if flat and isinstance(flat[0], list):
                            flat = [x for row in flat for x in row]
                        norm = math.sqrt(sum(x * x for x in flat))
                    norms.append((idx, norm))

                total_norm = sum(n for _, n in norms) or 1.0
                for idx, norm in norms:
                    contrib[idx] = norm / total_norm

                model_contributions[layer_name] = contrib
                raw_tensors[layer_name] = tensors

        return cls(
            layer_conflicts=layer_conflicts,
            model_contributions=model_contributions,
            num_models=n,
            raw_tensors=raw_tensors,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def layer_conflicts(self) -> Dict[str, float]:
        """Per-layer conflict scores."""
        return dict(self._layer_conflicts)

    @property
    def model_contributions(self) -> Dict[str, Dict[int, float]]:
        """Per-layer per-model contribution fractions."""
        return {k: dict(v) for k, v in self._model_contributions.items()}

    @property
    def num_layers(self) -> int:
        """Number of layers in the heatmap."""
        return len(self._layer_conflicts)

    @property
    def num_models(self) -> int:
        """Number of models being compared."""
        return self._num_models

    @property
    def overall_conflict(self) -> float:
        """Mean conflict score across all layers."""
        if not self._layer_conflicts:
            return 0.0
        return sum(self._layer_conflicts.values()) / len(self._layer_conflicts)

    def most_conflicted_layers(self, n: int = 10) -> List[Tuple[str, float]]:
        """Return the *n* most conflicted layers.

        Returns
        -------
        list[tuple[str, float]]
            (layer_name, conflict_score) sorted descending.
        """
        sorted_layers = sorted(
            self._layer_conflicts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_layers[:n]

    def least_conflicted_layers(self, n: int = 10) -> List[Tuple[str, float]]:
        """Return the *n* least conflicted layers.

        Returns
        -------
        list[tuple[str, float]]
            (layer_name, conflict_score) sorted ascending.
        """
        sorted_layers = sorted(
            self._layer_conflicts.items(),
            key=lambda x: x[1],
        )
        return sorted_layers[:n]

    # ------------------------------------------------------------------
    # Parameter detail
    # ------------------------------------------------------------------

    def parameter_detail(self, layer_name: str) -> LayerDetail:
        """Get detailed parameter-level analysis for a layer.

        Parameters
        ----------
        layer_name : str
            Name of the layer to analyze.

        Returns
        -------
        LayerDetail

        Raises
        ------
        KeyError
            If layer_name is not in the heatmap.
        """
        if layer_name not in self._layer_conflicts:
            raise KeyError(f"Layer '{layer_name}' not found in heatmap")

        if layer_name not in self._raw_tensors or not self._raw_tensors[layer_name]:
            return LayerDetail(
                variance_map=[],
                sign_agreement=1.0,
                magnitude_spread=0.0,
            )

        np_mod = _get_np()
        tensors = self._raw_tensors[layer_name]

        if np_mod is not None:
            import numpy as np
            arrays = [np.asarray(_to_array(t), dtype=float).ravel() for t in tensors]
            min_len = min(len(a) for a in arrays)
            if min_len == 0:
                return LayerDetail(variance_map=[], sign_agreement=1.0, magnitude_spread=0.0)
            arrays = [a[:min_len] for a in arrays]
            stacked = np.stack(arrays, axis=0)

            # Variance map
            variance_map = np.var(stacked, axis=0).tolist()

            # Sign agreement
            signs = np.sign(stacked)
            # For each parameter, check if all models agree on sign
            agreement = np.all(signs == signs[0:1, :], axis=0)
            sign_agreement = float(np.mean(agreement))

            # Magnitude spread
            magnitudes = np.abs(stacked)
            magnitude_spread = float(np.mean(np.std(magnitudes, axis=0)))

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
                return LayerDetail(variance_map=[], sign_agreement=1.0, magnitude_spread=0.0)
            flat = [f[:min_len] for f in flat]
            n = len(flat)

            variance_map = []
            agree_count = 0
            mag_stds = []

            for j in range(min_len):
                vals = [flat[i][j] for i in range(n)]
                mean = sum(vals) / n
                var = sum((v - mean) ** 2 for v in vals) / n
                variance_map.append(var)

                # Sign agreement
                signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in vals]
                if all(s == signs[0] for s in signs):
                    agree_count += 1

                # Magnitude spread
                mags = [abs(v) for v in vals]
                mag_mean = sum(mags) / n
                mag_var = sum((m - mag_mean) ** 2 for m in mags) / n
                mag_stds.append(math.sqrt(mag_var))

            sign_agreement = agree_count / min_len if min_len > 0 else 1.0
            magnitude_spread = sum(mag_stds) / len(mag_stds) if mag_stds else 0.0

        return LayerDetail(
            variance_map=variance_map,
            sign_agreement=sign_agreement,
            magnitude_spread=magnitude_spread,
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_json(self, path: Optional[str] = None) -> str:
        """Export heatmap as JSON (D3/Plotly compatible).

        Parameters
        ----------
        path : str | None
            If provided, also write to this file path.

        Returns
        -------
        str
            JSON string.
        """
        data = self.to_dict()
        json_str = json.dumps(data, indent=2)
        if path:
            with open(path, "w") as f:
                f.write(json_str)
        return json_str

    def to_csv(self, path: Optional[str] = None) -> str:
        """Export heatmap as CSV.

        Parameters
        ----------
        path : str | None
            If provided, also write to this file path.

        Returns
        -------
        str
            CSV string.
        """
        lines = ["layer_name,conflict_score"]
        for name in sorted(self._layer_conflicts.keys()):
            score = self._layer_conflicts[name]
            lines.append(f"{name},{score:.6f}")
        csv_str = "\n".join(lines)
        if path:
            with open(path, "w") as f:
                f.write(csv_str)
        return csv_str

    def to_dict(self) -> Dict[str, Any]:
        """Export heatmap as a plain dict.

        Returns
        -------
        dict
        """
        return {
            "num_layers": self.num_layers,
            "num_models": self.num_models,
            "overall_conflict": self.overall_conflict,
            "layer_conflicts": dict(self._layer_conflicts),
            "model_contributions": {
                k: {str(ki): vi for ki, vi in v.items()}
                for k, v in self._model_contributions.items()
            },
        }
