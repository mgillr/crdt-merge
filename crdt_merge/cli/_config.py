# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Configuration loading for the crdt-merge CLI.

Config is resolved with the following precedence (later wins):

1. Built-in defaults (:func:`default_config`)
2. Global config at ``~/.crdt-merge.toml``
3. Project config at ``./.crdt-merge.toml`` (current working directory)
4. Explicit path passed via ``--config`` / ``-c``
5. ``CRDT_MERGE_*`` environment variables
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from crdt_merge.cli._compat import load_toml

__all__ = [
    "load_config",
    "get_config_paths",
    "default_config",
    "write_default_config",
]

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_GLOBAL_PATH = os.path.expanduser("~/.crdt-merge.toml")
_PROJECT_PATH = os.path.join(os.getcwd(), ".crdt-merge.toml")


def default_config() -> Dict[str, Any]:
    """Return the built-in default configuration dictionary."""
    return {
        "cli": {"format": "table", "color": True, "pager": False},
        "merge": {"prefer": "latest", "dedup": False},
        "model": {"dtype": "float16", "default_strategy": "linear"},
        "hub": {"token": ""},
        "crypto": {"backend": "auto"},
    }


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict.

    Nested dicts are merged; all other values in *override* replace those
    in *base*.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


# ---------------------------------------------------------------------------
# Environment variable mapping
# ---------------------------------------------------------------------------

def _apply_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to *config* (mutates in place).

    Mapping
    -------
    - ``CRDT_MERGE_FORMAT``  -> ``cli.format``
    - ``CRDT_MERGE_COLOR``   -> ``cli.color``  (``"0"`` / ``"false"`` -> False)
    - ``CRDT_MERGE_KEY``     -> ``merge.key``
    - ``HUGGINGFACE_TOKEN`` or ``HF_TOKEN`` -> ``hub.token``
    """
    fmt = os.environ.get("CRDT_MERGE_FORMAT")
    if fmt is not None:
        config.setdefault("cli", {})["format"] = fmt

    color = os.environ.get("CRDT_MERGE_COLOR")
    if color is not None:
        config.setdefault("cli", {})["color"] = color.lower() not in (
            "0",
            "false",
            "no",
            "off",
        )

    key = os.environ.get("CRDT_MERGE_KEY")
    if key is not None:
        config.setdefault("merge", {})["key"] = key

    # Hub token: HUGGINGFACE_TOKEN takes precedence over HF_TOKEN.
    token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if token is not None:
        config.setdefault("hub", {})["token"] = token

    return config


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_config_paths() -> List[str]:
    """Return the list of config file paths that currently exist on disk."""
    paths: List[str] = []
    if os.path.isfile(_GLOBAL_PATH):
        paths.append(_GLOBAL_PATH)
    project = os.path.join(os.getcwd(), ".crdt-merge.toml")
    if os.path.isfile(project):
        paths.append(project)
    return paths


def load_config(explicit_path: str | None = None) -> Dict[str, Any]:
    """Load and merge configuration from all sources.

    Resolution order (later overrides earlier):

    1. Built-in defaults
    2. ``~/.crdt-merge.toml`` (global)
    3. ``./.crdt-merge.toml`` (project-level)
    4. *explicit_path* (if provided)
    5. ``CRDT_MERGE_*`` environment variables

    Parameters
    ----------
    explicit_path:
        Optional path to a TOML config file passed via ``--config``.

    Returns
    -------
    dict
        Fully resolved configuration dictionary.
    """
    config = default_config()

    # Layer 1 & 2: global and project config files.
    for path in (_GLOBAL_PATH, os.path.join(os.getcwd(), ".crdt-merge.toml")):
        if os.path.isfile(path):
            try:
                file_config = load_toml(path)
                config = _deep_merge(config, file_config)
            except Exception:
                # Silently skip malformed config files; the CLI will still
                # function with defaults.
                pass

    # Layer 3: explicit path.
    if explicit_path is not None:
        if not os.path.isfile(explicit_path):
            raise FileNotFoundError(
                f"Config file not found: {explicit_path}"
            )
        file_config = load_toml(explicit_path)
        config = _deep_merge(config, file_config)

    # Layer 4: environment variables.
    _apply_env(config)

    return config


def write_default_config(path: str) -> None:
    """Write the default configuration as TOML to *path*.

    Creates parent directories if they do not exist.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    config = default_config()

    lines: List[str] = [
        "# crdt-merge configuration",
        "# See: https://docs.crdt-merge.dev/configuration",
        "",
    ]

    for section, values in config.items():
        lines.append(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                lines.append(f"{key} = {_toml_value(val)}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


def _toml_value(val: Any) -> str:
    """Format a Python value as a TOML literal."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        inner = ", ".join(_toml_value(v) for v in val)
        return f"[{inner}]"
    return f'"{val}"'
