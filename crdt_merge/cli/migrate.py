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

"""MergeKit YAML → crdt-merge Python migration tool.

Converts MergeKit configuration files into equivalent crdt-merge Python code.

Usage:
    crdt-merge migrate config.yaml --output merge_pipeline.py

Programmatic:
    from crdt_merge.cli.migrate import migrate_config
    python_code = migrate_config("config.yaml")
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Mapping from MergeKit merge_method to crdt-merge strategy names
# ---------------------------------------------------------------------------

METHOD_TO_STRATEGY: Dict[str, str] = {
    "linear": "linear",
    "slerp": "slerp",
    "ties": "ties",
    "dare_ties": "dare_ties",
    "dare_linear": "dare",
    "task_arithmetic": "task_arithmetic",
    "passthrough": "linear",
}

# Human-friendly class-like names for code generation comments
METHOD_DISPLAY: Dict[str, str] = {
    "linear": "WeightAverage / Linear",
    "slerp": "SLERP",
    "ties": "TIES",
    "dare_ties": "DARE+TIES",
    "dare_linear": "DARE",
    "task_arithmetic": "TaskArithmetic",
    "passthrough": "Passthrough (linear)",
}

# ---------------------------------------------------------------------------
# Basic YAML parser (zero external deps)
# ---------------------------------------------------------------------------


def _parse_value(raw: str) -> Any:
    """Parse a scalar YAML value to the appropriate Python type."""
    raw = raw.strip()
    if not raw or raw == "~" or raw.lower() == "null":
        return None
    if raw.lower() in ("true", "yes", "on"):
        return True
    if raw.lower() in ("false", "no", "off"):
        return False
    # Quoted strings
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    # Numeric
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _indent_level(line: str) -> int:
    """Return leading-space count of *line*."""
    return len(line) - len(line.lstrip(" "))


def _parse_basic_yaml(path: str) -> dict:
    """Parse a simple YAML file without external dependencies.

    Handles the subset of YAML used by MergeKit configs:
    - Key: value pairs
    - Lists with ``- `` prefix
    - Nested dicts via indentation
    - Scalar types: str, int, float, bool, null
    """
    with open(path) as f:
        text = f.read()
    return parse_basic_yaml_string(text)


def parse_basic_yaml_string(text: str) -> Any:
    """Parse a YAML string into nested Python objects (dict/list/scalar).

    This handles the *subset* of YAML commonly found in MergeKit configs.
    """
    lines: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(raw_line.rstrip())

    if not lines:
        return {}

    return _parse_block(lines, 0, 0)[0]


def _parse_block(
    lines: List[str], start: int, base_indent: int
) -> Tuple[Any, int]:
    """Recursively parse a YAML block starting at *start*.

    Returns ``(parsed_value, next_line_index)``.
    """
    if start >= len(lines):
        return {}, start

    first = lines[start]
    stripped = first.strip()

    # Detect whether the block is a list or a mapping
    if stripped.startswith("- "):
        return _parse_list(lines, start, base_indent)
    else:
        return _parse_mapping(lines, start, base_indent)


def _parse_list(
    lines: List[str], start: int, base_indent: int
) -> Tuple[list, int]:
    result: list = []
    idx = start
    while idx < len(lines):
        line = lines[idx]
        indent = _indent_level(line)
        if indent < base_indent:
            break
        stripped = line.strip()
        if not stripped.startswith("- "):
            if indent == base_indent:
                break
            idx += 1
            continue

        item_text = stripped[2:].strip()
        # Check if it's "- key: value" (inline dict start)
        if ":" in item_text:
            # Reconstruct as a mapping block with deeper indent
            sub_indent = indent + 2
            # First key-value is inline
            sub_lines = [" " * sub_indent + item_text]
            idx += 1
            # Gather continuation lines at deeper indent
            while idx < len(lines):
                nxt = lines[idx]
                nxt_indent = _indent_level(nxt)
                if nxt_indent <= indent:
                    break
                sub_lines.append(nxt)
                idx += 1
            val, _ = _parse_mapping(sub_lines, 0, sub_indent)
            result.append(val)
        elif item_text:
            result.append(_parse_value(item_text))
            idx += 1
        else:
            # List item whose value is a nested block on next lines
            idx += 1
            if idx < len(lines):
                child_indent = _indent_level(lines[idx])
                val, idx = _parse_block(lines, idx, child_indent)
                result.append(val)
    return result, idx


def _parse_mapping(
    lines: List[str], start: int, base_indent: int
) -> Tuple[dict, int]:
    result: dict = {}
    idx = start
    while idx < len(lines):
        line = lines[idx]
        indent = _indent_level(line)
        if indent < base_indent:
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        colon_pos = stripped.find(":")
        if colon_pos == -1:
            idx += 1
            continue
        key = stripped[:colon_pos].strip()
        rest = stripped[colon_pos + 1 :].strip()
        if rest:
            result[key] = _parse_value(rest)
            idx += 1
        else:
            # Value is a nested block
            idx += 1
            if idx < len(lines):
                child_indent = _indent_level(lines[idx])
                if child_indent > indent:
                    val, idx = _parse_block(lines, idx, child_indent)
                    result[key] = val
                else:
                    result[key] = None
            else:
                result[key] = None
    return result, idx


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_yaml_config(path: str) -> dict:
    """Load a YAML config file.

    Uses PyYAML when available; falls back to a zero-dependency basic parser
    that handles the subset of YAML found in MergeKit configs.
    """
    try:
        import yaml  # type: ignore[import-untyped]

        with open(path) as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]
    except ImportError:
        return _parse_basic_yaml(path)


def load_yaml_string(text: str) -> dict:
    """Parse a YAML string into a dict.

    Uses PyYAML when available; falls back to basic parser.
    """
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text)  # type: ignore[no-any-return]
    except ImportError:
        return parse_basic_yaml_string(text)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------


def _python_repr(val: Any) -> str:
    """Return a Python-literal repr safe for code generation."""
    if val is None:
        return "None"
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, str):
        return repr(val)
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, list):
        inner = ", ".join(_python_repr(v) for v in val)
        return f"[{inner}]"
    if isinstance(val, dict):
        inner = ", ".join(
            f"{_python_repr(k)}: {_python_repr(v)}" for k, v in val.items()
        )
        return "{" + inner + "}"
    return repr(val)


def migrate_config(config_path: str) -> str:
    """Convert a MergeKit YAML config to crdt-merge Python code.

    Args:
        config_path: Path to MergeKit YAML config file.

    Returns:
        Python source code string using crdt-merge APIs.
    """
    config = load_yaml_config(config_path)
    return _generate_code(config)


def migrate_config_string(yaml_text: str) -> str:
    """Convert a MergeKit YAML string to crdt-merge Python code.

    Args:
        yaml_text: MergeKit YAML configuration as a string.

    Returns:
        Python source code string using crdt-merge APIs.
    """
    config = load_yaml_string(yaml_text)
    return _generate_code(config)


def _generate_code(config: dict) -> str:
    """Generate crdt-merge Python code from a parsed MergeKit config dict."""

    merge_method = config.get("merge_method", config.get("method", "linear"))
    strategy_name = METHOD_TO_STRATEGY.get(merge_method, merge_method)
    display_name = METHOD_DISPLAY.get(merge_method, merge_method)

    models: list = config.get("models", [])
    parameters: dict = config.get("parameters", {})
    slices: list = config.get("slices", [])
    base_model: Optional[str] = config.get("base_model")
    dtype: Optional[str] = config.get("dtype")

    # Extract model paths and weights
    model_paths: List[str] = []
    model_weights: List[float] = []
    for m in models:
        if isinstance(m, dict):
            model_paths.append(str(m.get("model", m.get("path", "unknown"))))
            model_weights.append(float(m.get("weight", 1.0)))
        elif isinstance(m, str):
            model_paths.append(m)
            model_weights.append(1.0)

    lines: List[str] = []
    lines.append(f'"""Auto-generated by crdt-merge migrate from MergeKit config.')
    lines.append(f"")
    lines.append(f"Original merge method: {merge_method} ({display_name})")
    lines.append(f'"""')
    lines.append("")
    lines.append("from crdt_merge.model.core import ModelMergeSchema")
    lines.append(
        "from crdt_merge.model.formats import import_mergekit_config, export_mergekit_config"
    )
    lines.append(
        "from crdt_merge.model.strategies import get_strategy, list_strategies"
    )
    lines.append("")
    lines.append("# ---- Model paths ----")
    for i, path in enumerate(model_paths):
        weight = model_weights[i] if i < len(model_weights) else 1.0
        lines.append(f"MODEL_{i} = {_python_repr(path)}  # weight={weight}")
    if not model_paths:
        lines.append("# No models specified in config")
    lines.append("")

    if base_model:
        lines.append(f"BASE_MODEL = {_python_repr(base_model)}")
        lines.append("")

    # Build strategies dict
    strategies: Dict[str, str] = {"default": strategy_name}
    if slices:
        for sl in slices:
            if isinstance(sl, dict):
                layer_range = sl.get("filter", sl.get("layer_range"))
                slice_method = sl.get("merge_method", merge_method)
                slice_strategy = METHOD_TO_STRATEGY.get(slice_method, slice_method)
                if layer_range:
                    strategies[str(layer_range)] = slice_strategy

    lines.append("# ---- Merge schema ----")
    lines.append(f"schema = ModelMergeSchema(strategies={_python_repr(strategies)})")
    lines.append("")

    if parameters:
        lines.append("# ---- Parameters ----")
        lines.append(f"parameters = {_python_repr(parameters)}")
        lines.append("")

    if dtype:
        lines.append(f"dtype = {_python_repr(dtype)}")
        lines.append("")

    # Strategy retrieval
    lines.append("# ---- Strategy ----")
    lines.append(f"strategy = get_strategy({_python_repr(strategy_name)})")
    lines.append("")

    # Verification
    lines.append("# ---- Verification ----")
    lines.append("print(f'Schema: {schema}')")
    lines.append("print(f'Strategy: {strategy}')")
    if model_paths:
        lines.append(
            f"print(f'Models: {', '.join(model_paths)}')"
        )
    lines.append("print('Migration complete ✅')")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Schema conversion (wraps model.formats)
# ---------------------------------------------------------------------------


def migrate_config_to_schema(
    config_path: str,
) -> tuple:
    """Convert a MergeKit config file to a ``ModelMergeSchema`` object.

    Uses the existing ``import_mergekit_config`` from ``crdt_merge.model.formats``.

    Args:
        config_path: Path to a MergeKit YAML config file.

    Returns:
        Tuple of ``(ModelMergeSchema, extra_config_dict)``.
    """
    from crdt_merge.model.formats import import_mergekit_config

    with open(config_path) as f:
        config_text = f.read()
    return import_mergekit_config(config_text)


def migrate_string_to_schema(
    yaml_text: str,
) -> tuple:
    """Convert a MergeKit YAML string to a ``ModelMergeSchema`` object.

    Args:
        yaml_text: MergeKit YAML configuration string.

    Returns:
        Tuple of ``(ModelMergeSchema, extra_config_dict)``.
    """
    from crdt_merge.model.formats import import_mergekit_config

    return import_mergekit_config(yaml_text)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cli_migrate(args: list) -> None:
    """CLI entry point for the ``migrate`` command."""
    if not args or args[0] in ("-h", "--help"):
        print("Usage: crdt-merge migrate <config.yaml> [options]")
        print()
        print("Options:")
        print("  --output FILE   Write generated Python code to FILE")
        print("  --schema        Print the ModelMergeSchema instead of code")
        print("  -h, --help      Show this help message")
        if not args or args[0] in ("-h", "--help"):
            sys.exit(0)
        sys.exit(1)

    config_path = args[0]
    output_path: Optional[str] = None
    schema_mode = False

    # Parse options
    i = 1
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--schema":
            schema_mode = True
            i += 1
        else:
            print(f"Warning: unknown option {args[i]!r}")
            i += 1

    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    if schema_mode:
        schema, extra = migrate_config_to_schema(config_path)
        print(f"Schema: {schema}")
        print(f"Strategy: {extra.get('crdt_strategy', 'unknown')}")
        print(f"Models: {extra.get('model_paths', [])}")
        return

    code = migrate_config(config_path)

    if output_path:
        with open(output_path, "w") as f:
            f.write(code)
        print(f"✅ Generated: {output_path}")
    else:
        print(code)
