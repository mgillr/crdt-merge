# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Python version compatibility helpers for the CLI.

Provides a TOML parser that uses ``tomllib`` (Python 3.11+) with a
hand-written fallback for Python 3.9–3.10 that handles the subset of
TOML used by crdt-merge config files.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, IO

__all__ = ["load_toml", "load_toml_string"]


# ---------------------------------------------------------------------------
# TOML loading -- prefer stdlib tomllib, fallback to minimal parser
# ---------------------------------------------------------------------------

def load_toml(path: str) -> Dict[str, Any]:
    """Load a TOML file and return a dict."""
    if sys.version_info >= (3, 11):
        import tomllib
        with open(path, "rb") as f:
            return tomllib.load(f)
    return _parse_toml_file(path)


def load_toml_string(text: str) -> Dict[str, Any]:
    """Parse a TOML string and return a dict."""
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(text)
    return _parse_toml_string(text)


# ---------------------------------------------------------------------------
# Minimal TOML parser for Python 3.9–3.10
# Handles: bare keys, dotted keys, string/int/float/bool values,
# [section] headers, [[array-of-tables]], inline arrays, inline tables.
# Does NOT handle: multi-line strings, datetime, escape sequences.
# ---------------------------------------------------------------------------

def _parse_toml_file(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return _parse_toml_string(f.read())


def _parse_toml_string(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current_section = result

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # [section] or [[array-of-tables]]
        if line.startswith("["):
            if line.startswith("[[") and line.endswith("]]"):
                section_path = line[2:-2].strip()
                current_section = _ensure_array_table(result, section_path)
            elif line.endswith("]"):
                section_path = line[1:-1].strip()
                current_section = _ensure_section(result, section_path)
            continue

        # key = value
        eq_pos = line.find("=")
        if eq_pos == -1:
            continue

        key = line[:eq_pos].strip().strip('"').strip("'")
        raw_val = line[eq_pos + 1:].strip()

        # Strip inline comment (not inside strings)
        if not raw_val.startswith('"') and not raw_val.startswith("'"):
            comment_pos = raw_val.find("#")
            if comment_pos > 0:
                raw_val = raw_val[:comment_pos].strip()

        current_section[key] = _parse_value(raw_val)

    return result


def _ensure_section(root: dict, path: str) -> dict:
    """Navigate into nested sections, creating dicts as needed."""
    parts = [p.strip().strip('"').strip("'") for p in path.split(".")]
    current = root
    for part in parts:
        if part not in current:
            current[part] = {}
        current = current[part]
    return current


def _ensure_array_table(root: dict, path: str) -> dict:
    """Navigate into an array-of-tables, appending a new dict."""
    parts = [p.strip().strip('"').strip("'") for p in path.split(".")]
    current = root
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    last = parts[-1]
    if last not in current:
        current[last] = []
    if isinstance(current[last], list):
        new_table: dict = {}
        current[last].append(new_table)
        return new_table
    return current[last]


def _parse_value(raw: str) -> Any:
    """Parse a TOML scalar or inline collection."""
    if not raw:
        return ""

    # Quoted strings
    if raw.startswith('"""') or raw.startswith("'''"):
        return raw[3:-3]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]

    # Inline array
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = _split_array(inner)
        return [_parse_value(item.strip()) for item in items]

    # Inline table
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1].strip()
        if not inner:
            return {}
        result = {}
        for pair in _split_array(inner):
            pair = pair.strip()
            eq = pair.find("=")
            if eq == -1:
                continue
            k = pair[:eq].strip().strip('"').strip("'")
            v = pair[eq + 1:].strip()
            result[k] = _parse_value(v)
        return result

    # Booleans
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False

    # Numbers
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _split_array(s: str) -> list:
    """Split a comma-separated string, respecting nested brackets and quotes."""
    items = []
    depth = 0
    current = []
    in_str = False
    str_char = ""

    for ch in s:
        if in_str:
            current.append(ch)
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_char = ch
            current.append(ch)
        elif ch in ("[", "{"):
            depth += 1
            current.append(ch)
        elif ch in ("]", "}"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)

    if current:
        items.append("".join(current))
    return items
