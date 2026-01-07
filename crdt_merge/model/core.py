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

"""Core ModelCRDT class and ModelMergeSchema for per-layer strategy assignment.

Example::

    from crdt_merge.model import ModelCRDT, ModelMergeSchema

    schema = ModelMergeSchema(strategies={
        "layers.0-15.self_attn": "slerp",
        "layers.*.mlp": "linear",
        "default": "linear",
    })
    crdt = ModelCRDT(schema)
    result = crdt.merge([model_a, model_b], weights=[0.6, 0.4])
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from crdt_merge.model.strategies import get_strategy
from crdt_merge.model.strategies.base import (
    MergeResult,
    ModelMergeStrategy,
    _normalize_weights,
    _to_array,
    _from_array,
)

__all__ = ["ModelMerge", "ModelCRDT", "ModelMergeSchema", "MergeResult"]

# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

# Matches patterns like "layers.0-15.self_attn"
_RANGE_RE = re.compile(
    r"^(?P<prefix>.*?)(?P<start>\d+)-(?P<end>\d+)(?P<suffix>.*)$"
)


def _is_range_pattern(pattern: str) -> bool:
    """Check if *pattern* contains a numeric range like ``0-15``."""
    return bool(_RANGE_RE.search(pattern))


def _is_regex_pattern(pattern: str) -> bool:
    """Heuristic: treat as regex if it contains regex-specific chars not used in glob."""
    # Glob uses * and ?, but regex uses things like ^, $, +, {, |, etc.
    regex_chars = {'^', '$', '+', '|', '{', '}', '(', ')'}
    return any(c in pattern for c in regex_chars)


def _range_matches(pattern: str, layer_name: str) -> bool:
    """Check if *layer_name* matches a range pattern like ``layers.0-15.self_attn``."""
    m = _RANGE_RE.search(pattern)
    if not m:
        return False
    prefix = m.group("prefix")
    start = int(m.group("start"))
    end = int(m.group("end"))
    suffix = m.group("suffix")

    # Build regex: prefix + \d+ + suffix
    # where the digit must be in [start, end]
    num_re = re.compile(
        r"^" + re.escape(prefix) + r"(\d+)" + re.escape(suffix) + r"$"
    )
    nm = num_re.match(layer_name)
    if not nm:
        return False
    num = int(nm.group(1))
    return start <= num <= end


def _regex_matches(pattern: str, layer_name: str) -> bool:
    """Attempt regex match."""
    try:
        return bool(re.fullmatch(pattern, layer_name))
    except re.error:
        return False


# ---------------------------------------------------------------------------
# ModelMergeSchema
# ---------------------------------------------------------------------------

class ModelMergeSchema:
    """Maps layer-name patterns to merge strategies.

    Pattern matching priority: **exact > glob > range > regex > default**.

    Parameters
    ----------
    strategies : dict[str, str | ModelMergeStrategy]
        Mapping from patterns to strategy names or instances.
        Use ``"default"`` key for the fallback strategy.
    """

    def __init__(
        self,
        strategies: Dict[str, Union[str, ModelMergeStrategy]],
    ) -> None:
        self._raw: Dict[str, Union[str, ModelMergeStrategy]] = dict(strategies)

        # Separate patterns by type for priority resolution
        self._exact: Dict[str, Union[str, ModelMergeStrategy]] = {}
        self._glob: Dict[str, Union[str, ModelMergeStrategy]] = {}
        self._range: Dict[str, Union[str, ModelMergeStrategy]] = {}
        self._regex: Dict[str, Union[str, ModelMergeStrategy]] = {}
        self._default: Optional[Union[str, ModelMergeStrategy]] = None

        for pat, strat in strategies.items():
            if pat == "default":
                self._default = strat
            elif '*' in pat or '?' in pat or '[' in pat:
                # Glob patterns (checked before range so bracket ranges
                # like ``[0-3]`` are treated as globs, not numeric ranges)
                self._glob[pat] = strat
            elif _is_range_pattern(pat):
                self._range[pat] = strat
            elif _is_regex_pattern(pat):
                self._regex[pat] = strat
            else:
                self._exact[pat] = strat

    # ------------------------------------------------------------------

    def _resolve(self, val: Union[str, ModelMergeStrategy]) -> ModelMergeStrategy:
        """Resolve a strategy value to an instance."""
        if isinstance(val, ModelMergeStrategy):
            return val
        return get_strategy(val)

    def strategy_for(self, layer_name: str) -> ModelMergeStrategy:
        """Return the strategy that applies to *layer_name*.

        Resolution order: exact match → glob → range → regex → default.

        Raises
        ------
        KeyError
            If no pattern matches and no default is set.
        """
        # 1. Exact
        if layer_name in self._exact:
            return self._resolve(self._exact[layer_name])

        # 2. Glob
        for pat, strat in self._glob.items():
            if fnmatch.fnmatch(layer_name, pat):
                return self._resolve(strat)

        # 3. Range
        for pat, strat in self._range.items():
            if _range_matches(pat, layer_name):
                return self._resolve(strat)

        # 4. Regex
        for pat, strat in self._regex.items():
            if _regex_matches(pat, layer_name):
                return self._resolve(strat)

        # 5. Default
        if self._default is not None:
            return self._resolve(self._default)

        raise KeyError(
            f"No strategy matches layer '{layer_name}' and no default set"
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

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
    def from_dict(cls, d: Dict[str, str]) -> "ModelMergeSchema":
        """Deserialize from a plain dict."""
        return cls(strategies=d)

    def __repr__(self) -> str:
        return f"ModelMergeSchema({self.to_dict()!r})"


# ---------------------------------------------------------------------------
# ModelCRDT
# ---------------------------------------------------------------------------

class ModelMerge:
    """Main entry-point for schema-driven model merging.

    Applies per-layer merge strategies according to a
    :class:`ModelMergeSchema`. Includes runtime CRDT-law verification
    via :meth:`verify`.

    .. deprecated:: 0.8.1
       The former name ``ModelCRDT`` is retained as a backward-compatible
       alias but will be removed in v1.0.  Prefer ``ModelMerge``.

    Parameters
    ----------
    schema : ModelMergeSchema
        Defines which strategy applies to each layer.
    """

    def __init__(self, schema: ModelMergeSchema) -> None:
        self.schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def merge(
        self,
        models: List[Any],
        base_model: Any = None,
        weights: Optional[List[float]] = None,
        output_path: Optional[str] = None,
        **kwargs: Any,
    ) -> MergeResult:
        """Merge multiple models according to the schema.

        Parameters
        ----------
        models : list
            List of state-dicts (``dict[str, array-like]``).
        base_model : dict | None
            Optional base model state-dict for delta strategies.
        weights : list[float] | None
            Per-model weights; ``None`` for uniform.
        output_path : str | None
            Reserved for future use (save merged model to path).
        **kwargs
            Forwarded to individual strategy ``merge`` calls.

        Returns
        -------
        MergeResult
        """
        state_dicts = [self._load_model(m) for m in models]
        base_sd = self._load_model(base_model) if base_model is not None else None

        if not state_dicts:
            return MergeResult(tensor={}, metadata={"layers": 0})

        if len(state_dicts) == 1:
            return MergeResult(
                tensor=dict(state_dicts[0]),
                metadata={"layers": len(state_dicts[0]), "single_passthrough": True},
            )

        # Collect all layer names (union)
        all_layers = _ordered_union(sd.keys() for sd in state_dicts)

        layer_map = self._match_layers_from_names(all_layers)

        merged_sd: Dict[str, Any] = {}
        meta_layers: Dict[str, str] = {}

        for layer_name in all_layers:
            strategy = layer_map[layer_name]
            tensors = [sd[layer_name] for sd in state_dicts if layer_name in sd]
            base_t = base_sd.get(layer_name) if base_sd else None

            # Adjust weights for models that have this layer
            layer_weights = weights
            if weights is not None and len(tensors) < len(state_dicts):
                layer_weights = [
                    w for w, sd in zip(weights, state_dicts) if layer_name in sd
                ]

            merged_t, _ = self._merge_layer(
                layer_name, tensors, strategy, layer_weights, base_t, **kwargs,
            )
            merged_sd[layer_name] = merged_t
            meta_layers[layer_name] = strategy.name

        return MergeResult(
            tensor=merged_sd,
            metadata={"layers": len(merged_sd), "strategies_used": meta_layers},
        )

    def merge_with_provenance(
        self,
        models: List[Any],
        base_model: Any = None,
        weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> MergeResult:
        """Same as :meth:`merge` but also populates ``provenance`` in the result."""
        state_dicts = [self._load_model(m) for m in models]
        base_sd = self._load_model(base_model) if base_model is not None else None

        if not state_dicts:
            return MergeResult(tensor={}, provenance={}, metadata={"layers": 0})

        all_layers = _ordered_union(sd.keys() for sd in state_dicts)
        layer_map = self._match_layers_from_names(all_layers)

        merged_sd: Dict[str, Any] = {}
        provenance: Dict[str, Any] = {}
        meta_layers: Dict[str, str] = {}

        for layer_name in all_layers:
            strategy = layer_map[layer_name]
            tensors = [sd[layer_name] for sd in state_dicts if layer_name in sd]
            base_t = base_sd.get(layer_name) if base_sd else None

            layer_weights = weights
            if weights is not None and len(tensors) < len(state_dicts):
                layer_weights = [
                    w for w, sd in zip(weights, state_dicts) if layer_name in sd
                ]

            merged_t, prov = self._merge_layer(
                layer_name, tensors, strategy, layer_weights, base_t,
                track_provenance=True, **kwargs,
            )
            merged_sd[layer_name] = merged_t
            provenance[layer_name] = prov
            meta_layers[layer_name] = strategy.name

        return MergeResult(
            tensor=merged_sd,
            provenance=provenance,
            metadata={"layers": len(merged_sd), "strategies_used": meta_layers},
        )

    def verify(
        self,
        strategy: Optional[str] = None,
        gen_fn: Optional[Callable] = None,
        trials: int = 100,
    ) -> Dict[str, Any]:
        """Verify CRDT properties of strategies in the schema.

        Parameters
        ----------
        strategy : str | None
            If given, verify only this strategy name. Otherwise verify all
            strategies referenced by the schema.
        gen_fn : callable | None
            Tensor generator for verification trials.
        trials : int
            Number of trials per property.

        Returns
        -------
        dict
            ``{strategy_name: verify_result}``
        """
        if strategy is not None:
            strat = get_strategy(strategy)
            return {strategy: strat.verify_crdt(gen_fn=gen_fn, trials=trials)}

        # Gather unique strategies from schema
        seen: Dict[str, ModelMergeStrategy] = {}
        for pat, val in self.schema._raw.items():
            if isinstance(val, ModelMergeStrategy):
                seen[val.name] = val
            else:
                if val not in seen:
                    seen[val] = get_strategy(val)

        results: Dict[str, Any] = {}
        for name, strat in seen.items():
            results[name] = strat.verify_crdt(gen_fn=gen_fn, trials=trials)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_model(model: Any) -> Dict[str, Any]:
        """Load a state-dict from various sources.

        Currently supports:
        - dict — returned as-is
        - None — empty dict
        """
        if model is None:
            return {}
        if isinstance(model, dict):
            return model
        raise TypeError(
            f"Unsupported model type {type(model).__name__}. "
            "Expected dict state_dict."
        )

    def _match_layers_from_names(
        self, layer_names,
    ) -> Dict[str, ModelMergeStrategy]:
        """Resolve schema for a list of layer names."""
        return {name: self.schema.strategy_for(name) for name in layer_names}

    @staticmethod
    def _merge_layer(
        layer_name: str,
        tensors: list,
        strategy: ModelMergeStrategy,
        weights: Optional[List[float]],
        base: Any,
        track_provenance: bool = False,
        **kwargs: Any,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Merge tensors for a single layer.

        Returns
        -------
        tuple[merged_tensor, provenance_dict]
        """
        if not tensors:
            return None, {}

        if len(tensors) == 1:
            prov = {"source": "single", "strategy": strategy.name} if track_provenance else {}
            return tensors[0], prov

        original_type = tensors[0]

        merged = strategy.merge(tensors, weights=weights, base=base, **kwargs)

        prov: Dict[str, Any] = {}
        if track_provenance:
            norm_w = _normalize_weights(weights, len(tensors))
            prov = {
                "strategy": strategy.name,
                "num_sources": len(tensors),
                "weights": norm_w,
            }

        return merged, prov


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _ordered_union(iterables) -> List[str]:
    """Return an ordered union of keys from multiple iterables (preserving first-seen order)."""
    seen = set()
    result = []
    for it in iterables:
        for k in it:
            if k not in seen:
                seen.add(k)
                result.append(k)
    return result

# Backward-compatible alias (deprecated — will be removed in v1.0)
ModelCRDT = ModelMerge
