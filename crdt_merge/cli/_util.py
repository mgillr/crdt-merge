# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Shared file I/O helpers and error formatting for the crdt-merge CLI."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Extra-package mapping
# ---------------------------------------------------------------------------

EXTRA_PACKAGES: dict[str, list[str]] = {
    "fast": ["polars", "orjson", "xxhash"],
    "pandas": ["pandas"],
    "model": ["numpy"],
    "gpu": ["torch"],
    "crypto": ["cryptography"],
    "datasets": ["datasets"],
    "flower": ["flwr"],
}

# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def format_error(msg: str, hint: str | None = None) -> str:
    """Format an error message cleanly, with an optional hint."""
    text = f"Error: {msg}"
    if hint:
        text += f"\n  Hint: {hint}"
    return text


def format_dependency_error(package: str, extra: str) -> str:
    """Return a human-readable dependency-missing message.

    Example output:
        The 'numpy' package is required. Install with: pip install crdt-merge[model]
    """
    return (
        f"The '{package}' package is required. "
        f"Install with: pip install crdt-merge[{extra}]"
    )


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_EXT_FORMAT_MAP: dict[str, str] = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".parquet": "parquet",
}


def detect_format(path: str) -> str:
    """Map a file path's extension to a canonical format name.

    Returns one of: ``csv``, ``json``, ``jsonl``, ``parquet``.
    Raises ``ValueError`` for unrecognised extensions.
    """
    if path == "-":
        return "json"  # default for stdin/stdout
    ext = Path(path).suffix.lower()
    fmt = _EXT_FORMAT_MAP.get(ext)
    if fmt is None:
        raise ValueError(
            format_error(
                f"Unrecognised file extension '{ext}'",
                hint="Supported extensions: .csv, .json, .jsonl, .ndjson, .parquet",
            )
        )
    return fmt


# ---------------------------------------------------------------------------
# Optional-import helpers
# ---------------------------------------------------------------------------


def _try_import(name: str):
    """Attempt to import *name*; return the module or ``None``."""
    try:
        import importlib

        return importlib.import_module(name)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_csv(path: str) -> list[dict]:
    """Load CSV, preferring pandas when available for better type coercion."""
    pd = _try_import("pandas")
    if pd is not None:
        try:
            df = pd.read_csv(path)
            return df.to_dict("records")
        except Exception:
            pass  # fall through to stdlib

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError(
        format_error(
            "JSON root must be an object or array of objects",
            hint=f"Got {type(data).__name__}",
        )
    )


def _load_jsonl(path: str) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    format_error(
                        f"Invalid JSON on line {lineno}",
                        hint=str(exc),
                    )
                ) from exc
    return records


def _load_parquet(path: str) -> list[dict]:
    pl = _try_import("polars")
    if pl is not None:
        return pl.read_parquet(path).to_dicts()

    pd = _try_import("pandas")
    if pd is not None:
        return pd.read_parquet(path).to_dict("records")

    raise ImportError(
        format_error(
            "No parquet reader available",
            hint="pip install crdt-merge[fast] or crdt-merge[pandas]",
        )
    )


def _load_stdin() -> list[dict]:
    """Read from stdin, auto-detecting JSON vs CSV by the first character."""
    raw = sys.stdin.read()
    if not raw.strip():
        return []

    first_char = raw.lstrip()[0]
    if first_char in ("{", "["):
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        raise ValueError(
            format_error("Stdin JSON root must be an object or array of objects")
        )
    else:
        reader = csv.DictReader(io.StringIO(raw))
        return list(reader)


def load_data(path: str) -> list[dict]:
    """Load data from *path*, dispatching on file extension.

    Use ``"-"`` to read from stdin (auto-detects JSON or CSV).
    """
    if path == "-":
        return _load_stdin()

    fmt = detect_format(path)
    loaders = {
        "csv": _load_csv,
        "json": _load_json,
        "jsonl": _load_jsonl,
        "parquet": _load_parquet,
    }
    loader = loaders.get(fmt)
    if loader is None:
        raise ValueError(format_error(f"No loader for format '{fmt}'"))
    return loader(path)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _write_csv(data: list[dict], fh: Any) -> None:
    if not data:
        return
    fieldnames = list(data[0].keys())
    writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)


def _write_json(data: list[dict], fh: Any) -> None:
    json.dump(data, fh, indent=2, default=str, ensure_ascii=False)
    fh.write("\n")


def _write_jsonl(data: list[dict], fh: Any) -> None:
    for record in data:
        fh.write(json.dumps(record, default=str, ensure_ascii=False))
        fh.write("\n")


def _write_parquet(data: list[dict], path: str) -> None:
    pl = _try_import("polars")
    if pl is not None:
        pl.DataFrame(data).write_parquet(path)
        return

    pd = _try_import("pandas")
    if pd is not None:
        pd.DataFrame(data).to_parquet(path, index=False)
        return

    raise ImportError(
        format_error(
            "No parquet writer available",
            hint="pip install crdt-merge[fast] or crdt-merge[pandas]",
        )
    )


def write_data(
    data: list[dict],
    path: str,
    format: str | None = None,
) -> None:
    """Write *data* to *path*.

    Parameters
    ----------
    data:
        List of dicts to write.
    path:
        Destination file path, or ``"-"`` for stdout.
    format:
        Explicit format (``csv``, ``json``, ``jsonl``, ``parquet``).
        Detected from *path* extension when ``None``.
    """
    if format is None:
        format = detect_format(path) if path != "-" else "json"

    # Parquet is binary — handle separately (cannot write to stdout easily).
    if format == "parquet":
        if path == "-":
            raise ValueError(
                format_error(
                    "Cannot write parquet to stdout",
                    hint="Specify an output file path instead.",
                )
            )
        _write_parquet(data, path)
        return

    writers = {
        "csv": _write_csv,
        "json": _write_json,
        "jsonl": _write_jsonl,
    }
    writer_fn = writers.get(format)
    if writer_fn is None:
        raise ValueError(format_error(f"Unsupported output format '{format}'"))

    if path == "-":
        writer_fn(data, sys.stdout)
        sys.stdout.flush()
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer_fn(data, fh)
