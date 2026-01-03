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

"""MergeKit / FusionBench compatibility layer.

Provides import/export of MergeKit-style YAML configurations and
bidirectional strategy name mapping.

Example::

    from crdt_merge.model.formats import import_mergekit_config, export_mergekit_config

    schema, extra = import_mergekit_config({
        "merge_method": "ties",
        "models": [{"model": "path/a"}, {"model": "path/b"}],
        "parameters": {"density": 0.5},
    })
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from crdt_merge.model.core import ModelMergeSchema

__all__ = [
    "import_mergekit_config",
    "export_mergekit_config",
    "STRATEGY_MAP",
    "REVERSE_STRATEGY_MAP",
]

# ---------------------------------------------------------------------------
# Bidirectional strategy name mapping
# ---------------------------------------------------------------------------

# MergeKit name → crdt-merge name
STRATEGY_MAP: Dict[str, str] = {
    "linear": "linear",
    "slerp": "slerp",
    "ties": "ties",
    "dare_ties": "dare_ties",
    "task_arithmetic": "task_arithmetic",
    "dare_linear": "dare",
}

# crdt-merge name → MergeKit name
REVERSE_STRATEGY_MAP: Dict[str, str] = {v: k for k, v in STRATEGY_MAP.items()}
# Ensure dare maps back properly (dare -> dare_linear)
REVERSE_STRATEGY_MAP["dare"] = "dare_linear"


def _map_to_crdt(mergekit_name: str) -> str:
    """Map a MergeKit strategy name to crdt-merge equivalent."""
    return STRATEGY_MAP.get(mergekit_name, mergekit_name)


def _map_to_mergekit(crdt_name: str) -> str:
    """Map a crdt-merge strategy name to MergeKit equivalent."""
    return REVERSE_STRATEGY_MAP.get(crdt_name, crdt_name)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _parse_yaml_string(yaml_str: str) -> dict:
    """Parse a YAML string into a dict. Uses yaml if available, else basic parsing."""
    try:
        import yaml
        return yaml.safe_load(yaml_str)
    except ImportError:
        # Basic fallback for simple YAML
        raise ImportError(
            "PyYAML is required to parse YAML strings. "
            "Install with: pip install pyyaml"
        )


def import_mergekit_config(
    config: Union[dict, str],
) -> Tuple[ModelMergeSchema, dict]:
    """Parse a MergeKit-style config into a ModelMergeSchema.

    Parameters
    ----------
    config : dict | str
        MergeKit configuration as a dict or YAML string.

    Returns
    -------
    tuple[ModelMergeSchema, dict]
        ``(schema, extra_config)`` where ``extra_config`` contains model
        paths, slices, parameters, and other MergeKit-specific fields.
    """
    if isinstance(config, str):
        config = _parse_yaml_string(config)

    if not isinstance(config, dict):
        raise TypeError(f"Expected dict or YAML string, got {type(config).__name__}")

    # Extract merge method
    merge_method = config.get("merge_method", config.get("method", "linear"))
    crdt_strategy = _map_to_crdt(merge_method)

    # Extract parameters
    parameters = config.get("parameters", {})

    # Extract model info
    models = config.get("models", [])
    model_paths = []
    model_weights = []
    for m in models:
        if isinstance(m, dict):
            model_paths.append(m.get("model", m.get("path", "")))
            model_weights.append(m.get("weight", 1.0))
        elif isinstance(m, str):
            model_paths.append(m)
            model_weights.append(1.0)

    # Extract slices for per-layer strategies
    slices = config.get("slices", [])
    strategies: Dict[str, str] = {}

    if slices:
        for sl in slices:
            sources = sl.get("sources", [])
            layer_range = sl.get("filter", sl.get("layer_range", None))
            slice_method = sl.get("merge_method", merge_method)
            slice_crdt = _map_to_crdt(slice_method)

            if layer_range:
                # Convert MergeKit layer range to pattern
                pattern = layer_range
                strategies[pattern] = slice_crdt
            else:
                # Apply to default
                strategies["default"] = slice_crdt

    # Set default strategy
    if "default" not in strategies:
        strategies["default"] = crdt_strategy

    schema = ModelMergeSchema(strategies=strategies)

    extra_config: dict = {
        "model_paths": model_paths,
        "model_weights": model_weights,
        "parameters": parameters,
        "merge_method": merge_method,
        "crdt_strategy": crdt_strategy,
    }

    if slices:
        extra_config["slices"] = slices
    if "base_model" in config:
        extra_config["base_model"] = config["base_model"]
    if "dtype" in config:
        extra_config["dtype"] = config["dtype"]

    return schema, extra_config


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_mergekit_config(
    schema: ModelMergeSchema,
    models: Optional[List[str]] = None,
) -> dict:
    """Convert a ModelMergeSchema back to MergeKit format.

    Parameters
    ----------
    schema : ModelMergeSchema
        The schema to export.
    models : list[str] | None
        Optional list of model paths to include.

    Returns
    -------
    dict
        MergeKit-compatible configuration dict.
    """
    raw = schema.to_dict()

    # Determine primary merge method from default or first strategy
    default_strategy = raw.get("default", None)
    if default_strategy is None:
        # Use the first strategy as the default
        first_key = next(iter(raw), None)
        default_strategy = raw.get(first_key, "linear") if first_key else "linear"

    mergekit_method = _map_to_mergekit(default_strategy)

    config: dict = {
        "merge_method": mergekit_method,
    }

    # Add models
    if models:
        config["models"] = [{"model": m} for m in models]

    # Add slices for non-default strategies
    slices = []
    for pattern, strategy_name in raw.items():
        if pattern == "default":
            continue
        mk_method = _map_to_mergekit(strategy_name)
        slice_entry: dict = {
            "filter": pattern,
            "merge_method": mk_method,
            "sources": [],
        }
        slices.append(slice_entry)

    if slices:
        config["slices"] = slices

    # Add parameters (empty by default, strategies may need specific ones)
    config["parameters"] = {}

    return config
