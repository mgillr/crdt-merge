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

"""LoRA adapter merging with per-module strategy assignment.

Supports rank harmonization (max/min/mean/adaptive), per-module merge
strategies via :class:`LoRAMergeSchema`, and provenance tracking.

Example::

    from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

    schema = LoRAMergeSchema(strategies={"default": "weight_average"})
    merger = LoRAMerge(schema)
    merged = merger.merge_adapters([adapter_a, adapter_b], weights=[0.7, 0.3])
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from crdt_merge.model.strategies import get_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _normalize_weights,
    _to_array,
    _from_array,
    _get_np,
)

__all__ = ["LoRAMerge", "LoRAMergeSchema"]

# ---------------------------------------------------------------------------
# Pure-Python matrix helpers (numpy-optional)
# ---------------------------------------------------------------------------

def _np():
    """Return numpy or None."""
    return _get_np()

def _zeros(rows: int, cols: int):
    """Create a zero matrix."""
    np = _np()
    if np is not None:
        return np.zeros((rows, cols), dtype=float)
    return [[0.0] * cols for _ in range(rows)]

def _get_shape(m) -> Tuple[int, int]:
    """Return (rows, cols) for a 2-D array-like."""
    np = _np()
    if np is not None and hasattr(m, 'shape'):
        arr = _to_array(m)
        if arr.ndim == 2:
            return tuple(arr.shape)
        elif arr.ndim == 1:
            return (1, arr.shape[0])
    # plain list
    if isinstance(m, list):
        if not m:
            return (0, 0)
        if isinstance(m[0], list):
            return (len(m), len(m[0]))
        return (1, len(m))
    return (0, 0)

def _to_2d(m) -> Any:
    """Ensure m is a 2-D array."""
    np = _np()
    arr = _to_array(m)
    if np is not None and hasattr(arr, 'ndim'):
        if arr.ndim == 1:
            return arr.reshape(1, -1)
        return arr
    if isinstance(arr, list) and arr and not isinstance(arr[0], list):
        return [arr]
    return arr

def _matmul(a, b):
    """Matrix multiply two 2-D arrays."""
    np = _np()
    a2 = _to_2d(a)
    b2 = _to_2d(b)
    if np is not None and hasattr(a2, '__matmul__'):
        return a2 @ b2
    # Pure Python fallback
    rows_a = len(a2)
    cols_a = len(a2[0]) if rows_a > 0 else 0
    cols_b = len(b2[0]) if len(b2) > 0 else 0
    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for k in range(cols_a):
            for j in range(cols_b):
                result[i][j] += a2[i][k] * b2[k][j]
    return result

def _add_matrices(a, b):
    """Element-wise add two 2-D arrays."""
    np = _np()
    aa = _to_2d(a)
    bb = _to_2d(b)
    if np is not None and hasattr(aa, '__add__'):
        return aa + bb
    rows = len(aa)
    cols = len(aa[0]) if rows > 0 else 0
    return [[aa[i][j] + bb[i][j] for j in range(cols)] for i in range(rows)]

def _svd_truncate(matrix, target_rank: int):
    """Truncate a matrix to target_rank via SVD (keep top singular values)."""
    np = _np()
    arr = _to_2d(matrix)
    if np is not None and hasattr(arr, 'shape'):
        U, S, Vt = np.linalg.svd(arr, full_matrices=False)
        k = min(target_rank, len(S))
        return U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
    # Pure Python: just slice rows/cols (approximate)
    rows = len(arr)
    cols = len(arr[0]) if rows > 0 else 0
    k = min(target_rank, rows, cols)
    return [row[:k] for row in arr[:k]] if k > 0 else arr

# ---------------------------------------------------------------------------
# Rank harmonization
# ---------------------------------------------------------------------------

def _harmonize_rank_lora_a(matrices: List, target_rank: int, strategy: str):
    """Harmonize lora_A matrices to target_rank.

    lora_A has shape (rank, in_features). Harmonize along axis 0.
    """
    np = _np()
    results = []
    for m in matrices:
        arr = _to_2d(m)
        if np is not None and hasattr(arr, 'shape'):
            current_rank = arr.shape[0]
            in_features = arr.shape[1]
            if current_rank == target_rank:
                results.append(arr)
            elif current_rank < target_rank:
                # Pad with zeros
                pad = np.zeros((target_rank - current_rank, in_features), dtype=float)
                results.append(np.vstack([arr, pad]))
            else:
                # Truncate (keep top rows by SVD or simply first rows)
                if strategy == "min":
                    # Simple truncation -- keep top singular value components
                    U, S, Vt = np.linalg.svd(arr, full_matrices=False)
                    k = target_rank
                    results.append(U[:k, :k] @ np.diag(S[:k]) @ Vt[:k, :])
                else:
                    results.append(arr[:target_rank, :])
        else:
            # Pure Python
            current_rank = len(arr)
            in_features = len(arr[0]) if current_rank > 0 else 0
            if current_rank == target_rank:
                results.append(arr)
            elif current_rank < target_rank:
                for _ in range(target_rank - current_rank):
                    arr.append([0.0] * in_features)
                results.append(arr)
            else:
                results.append(arr[:target_rank])
    return results

def _harmonize_rank_lora_b(matrices: List, target_rank: int, strategy: str):
    """Harmonize lora_B matrices to target_rank.

    lora_B has shape (out_features, rank). Harmonize along axis 1.
    """
    np = _np()
    results = []
    for m in matrices:
        arr = _to_2d(m)
        if np is not None and hasattr(arr, 'shape'):
            out_features = arr.shape[0]
            current_rank = arr.shape[1]
            if current_rank == target_rank:
                results.append(arr)
            elif current_rank < target_rank:
                pad = np.zeros((out_features, target_rank - current_rank), dtype=float)
                results.append(np.hstack([arr, pad]))
            else:
                if strategy == "min":
                    U, S, Vt = np.linalg.svd(arr, full_matrices=False)
                    k = target_rank
                    results.append(U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :k])
                else:
                    results.append(arr[:, :target_rank])
        else:
            # Pure Python
            out_features = len(arr)
            current_rank = len(arr[0]) if out_features > 0 else 0
            if current_rank == target_rank:
                results.append(arr)
            elif current_rank < target_rank:
                results.append([row + [0.0] * (target_rank - current_rank) for row in arr])
            else:
                results.append([row[:target_rank] for row in arr])
    return results

def _compute_target_rank(ranks: List[int], strategy: str, weights: Optional[List[float]] = None) -> int:
    """Compute the target rank from a list of ranks."""
    if not ranks:
        return 0
    if strategy == "max":
        return max(ranks)
    elif strategy == "min":
        return min(ranks)
    elif strategy == "mean":
        return max(1, round(sum(ranks) / len(ranks)))
    elif strategy == "adaptive":
        # Weighted average of ranks by model weights
        if weights is None:
            weights = [1.0 / len(ranks)] * len(ranks)
        w = _normalize_weights(weights, len(ranks))
        return max(1, round(sum(r * wt for r, wt in zip(ranks, w))))
    else:
        raise ValueError(f"Unknown rank_strategy: {strategy}")

# ---------------------------------------------------------------------------
# LoRAMergeSchema
# ---------------------------------------------------------------------------

class LoRAMergeSchema:
    """Maps adapter module names to merge strategies.

    Similar to :class:`ModelMergeSchema` but keyed by LoRA module names
    (e.g., ``q_proj``, ``v_proj``, ``default``).

    Parameters
    ----------
    strategies : dict[str, str | ModelMergeStrategy]
        Mapping from module name patterns to strategy names or instances.
        Use ``"default"`` key for the fallback strategy.
    """

    def __init__(self, strategies: Dict[str, Union[str, ModelMergeStrategy]]) -> None:
        self._raw: Dict[str, Union[str, ModelMergeStrategy]] = dict(strategies)
        self._default: Optional[Union[str, ModelMergeStrategy]] = strategies.get("default")
        self._specific: Dict[str, Union[str, ModelMergeStrategy]] = {
            k: v for k, v in strategies.items() if k != "default"
        }

    def _resolve(self, val: Union[str, ModelMergeStrategy]) -> ModelMergeStrategy:
        """Resolve a strategy value to an instance."""
        if isinstance(val, ModelMergeStrategy):
            return val
        return get_strategy(val)

    def strategy_for(self, module_name: str) -> ModelMergeStrategy:
        """Return the strategy that applies to *module_name*.

        Resolution: exact match on module name → default.

        Raises
        ------
        KeyError
            If no match and no default.
        """
        # Check for exact or substring matches
        for pat, strat in self._specific.items():
            if pat == module_name or pat in module_name:
                return self._resolve(strat)
        if self._default is not None:
            return self._resolve(self._default)
        raise KeyError(
            f"No strategy matches module '{module_name}' and no default set"
        )

    def to_dict(self) -> Dict[str, str]:
        """Serialize to a plain dict (strategy names only)."""
        out: Dict[str, str] = {}
        for pat, strat in self._raw.items():
            if isinstance(strat, ModelMergeStrategy):
                out[pat] = strat.name
            else:
                out[pat] = strat
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "LoRAMergeSchema":
        """Deserialize from a plain dict."""
        return cls(strategies=d)

    def __repr__(self) -> str:
        return f"LoRAMergeSchema({self.to_dict()!r})"

# ---------------------------------------------------------------------------
# LoRAMerge
# ---------------------------------------------------------------------------

class LoRAMerge:
    """Merge LoRA adapters with rank harmonization and per-module strategies.

    Parameters
    ----------
    schema : LoRAMergeSchema
        Defines which strategy applies to each adapter module.
    """

    def __init__(self, schema: LoRAMergeSchema) -> None:
        self.schema = schema

    def merge_adapters(
        self,
        adapters: List[Dict[str, Dict[str, Any]]],
        weights: Optional[List[float]] = None,
        rank_strategy: str = "max",
    ) -> Dict[str, Dict[str, Any]]:
        """Merge multiple LoRA adapters into one.

        Parameters
        ----------
        adapters : list[dict]
            Each adapter maps module_name → {"lora_A": tensor, "lora_B": tensor}.
        weights : list[float] | None
            Per-adapter weights; ``None`` for uniform.
        rank_strategy : str
            How to harmonize ranks: "max", "min", "mean", "adaptive".

        Returns
        -------
        dict
            Merged adapter: module_name → {"lora_A": tensor, "lora_B": tensor}.
        """
        if not adapters:
            return {}

        if len(adapters) == 1:
            return dict(adapters[0])

        # Collect all module names (union)
        all_modules = _ordered_module_union(adapters)

        merged: Dict[str, Dict[str, Any]] = {}
        for module_name in all_modules:
            merged[module_name] = self._merge_module(
                module_name, adapters, weights, rank_strategy,
            )
        return merged

    def merge_adapters_with_provenance(
        self,
        adapters: List[Dict[str, Dict[str, Any]]],
        weights: Optional[List[float]] = None,
        rank_strategy: str = "max",
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Merge adapters and return provenance information.

        Returns
        -------
        tuple[dict, dict]
            (merged_adapter, provenance_per_module)
        """
        if not adapters:
            return {}, {}

        if len(adapters) == 1:
            prov = {}
            for mod in adapters[0]:
                prov[mod] = {
                    "strategy": "passthrough",
                    "num_sources": 1,
                    "dominant_source": 0,
                    "contribution_map": {0: 1.0},
                }
            return dict(adapters[0]), prov

        all_modules = _ordered_module_union(adapters)
        merged: Dict[str, Dict[str, Any]] = {}
        provenance: Dict[str, Dict[str, Any]] = {}

        norm_weights = _normalize_weights(weights, len(adapters)) if weights else None

        for module_name in all_modules:
            merged[module_name] = self._merge_module(
                module_name, adapters, weights, rank_strategy,
            )

            # Build provenance
            sources = [i for i, a in enumerate(adapters) if module_name in a]
            strategy = self.schema.strategy_for(module_name)
            w = norm_weights if norm_weights else _normalize_weights(None, len(sources))

            # Contribution map: model index → fraction
            contrib = {}
            if norm_weights:
                for idx in sources:
                    contrib[idx] = norm_weights[idx]
                total = sum(contrib.values())
                if total > 0:
                    contrib = {k: v / total for k, v in contrib.items()}
            else:
                for idx in sources:
                    contrib[idx] = 1.0 / len(sources) if sources else 0.0

            dominant = max(contrib, key=contrib.get) if contrib else 0
            provenance[module_name] = {
                "strategy": strategy.name,
                "num_sources": len(sources),
                "dominant_source": dominant,
                "contribution_map": contrib,
                "sources": sources,
            }

        return merged, provenance

    def apply_to_base(
        self,
        merged_adapter: Dict[str, Dict[str, Any]],
        base_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply a merged LoRA adapter to a base model.

        Computes ``θ = θ_base + lora_B @ lora_A`` for each module.

        Parameters
        ----------
        merged_adapter : dict
            Module name → {"lora_A": tensor, "lora_B": tensor}.
        base_model : dict
            Base model state_dict (layer_name → tensor).

        Returns
        -------
        dict
            Updated state_dict.
        """
        result = dict(base_model)
        for module_name, lora_data in merged_adapter.items():
            lora_a = lora_data.get("lora_A")
            lora_b = lora_data.get("lora_B")
            if lora_a is None or lora_b is None:
                continue
            # Compute delta = lora_B @ lora_A
            delta = _matmul(lora_b, lora_a)
            # Find matching base layer
            if module_name in result:
                result[module_name] = _add_matrices(result[module_name], delta)
            else:
                # Try common naming: module_name + ".weight"
                weight_key = f"{module_name}.weight"
                if weight_key in result:
                    result[weight_key] = _add_matrices(result[weight_key], delta)
                else:
                    # Store as new key
                    result[module_name] = delta
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _merge_module(
        self,
        module_name: str,
        adapters: List[Dict],
        weights: Optional[List[float]],
        rank_strategy: str,
    ) -> Dict[str, Any]:
        """Merge a single module across adapters."""
        # Gather this module's data from each adapter
        module_data = []
        source_indices = []
        for i, adapter in enumerate(adapters):
            if module_name in adapter:
                module_data.append(adapter[module_name])
                source_indices.append(i)

        if not module_data:
            return {"lora_A": _zeros(1, 1), "lora_B": _zeros(1, 1)}

        if len(module_data) == 1:
            return dict(module_data[0])

        strategy = self.schema.strategy_for(module_name)

        # Get ranks from each adapter for this module
        ranks = []
        for md in module_data:
            a_shape = _get_shape(md.get("lora_A", []))
            ranks.append(a_shape[0])  # rank is first dim of lora_A

        # Compute target rank
        src_weights = None
        if weights is not None:
            src_weights = [weights[i] for i in source_indices]
        target_rank = _compute_target_rank(ranks, rank_strategy, src_weights)

        # Harmonize ranks for lora_A and lora_B
        lora_a_list = [md.get("lora_A") for md in module_data]
        lora_b_list = [md.get("lora_B") for md in module_data]

        lora_a_harmonized = _harmonize_rank_lora_a(lora_a_list, target_rank, rank_strategy)
        lora_b_harmonized = _harmonize_rank_lora_b(lora_b_list, target_rank, rank_strategy)

        # Build normalized weights for this subset
        merge_weights = _normalize_weights(src_weights, len(module_data))

        # Merge lora_A matrices using strategy
        merged_a = strategy.merge(lora_a_harmonized, weights=merge_weights)
        merged_b = strategy.merge(lora_b_harmonized, weights=merge_weights)

        return {"lora_A": merged_a, "lora_B": merged_b}

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _ordered_module_union(adapters: List[Dict]) -> List[str]:
    """Return ordered union of all module names across adapters."""
    seen = set()
    result = []
    for adapter in adapters:
        for key in adapter:
            if key not in seen:
                seen.add(key)
                result.append(key)
    return result
