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

"""
CRDT-powered DataFrame merge — conflict-free merge of any two DataFrames.

Supports pandas and polars. Handles:
  - Row-level merge by key column (matched rows: LWW per cell)
  - Rows unique to either side: preserved
  - Schema divergence: union of columns, missing filled with None
  - Deduplication: exact and fuzzy
  - Timestamp columns: used for LWW resolution when available

Usage:
    from crdt_merge import merge
    merged = merge(df_a, df_b, key="id")
"""

from __future__ import annotations
import hashlib
import time
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .core import LWWRegister

__all__ = ["merge", "diff"]

def _parse_timestamp(value: Any) -> float:
    """Parse a timestamp value to float. Handles numeric, ISO-8601, datetime, and None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
        # Try ISO-8601 parsing
        from datetime import datetime as _dt
        try:
            s = value.replace("Z", "+00:00")
            dt = _dt.fromisoformat(s)
            return dt.timestamp()
        except (ValueError, AttributeError, TypeError):
            pass
    # Try .timestamp() method (datetime objects)
    if hasattr(value, 'timestamp'):
        try:
            return float(value.timestamp())
        except (TypeError, OSError):
            pass
    return 0.0

def _normalize_key(key: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """Convert key to list form. None → None, 'id' → ['id'], ['id','name'] → ['id','name']."""
    if key is None:
        return None
    if isinstance(key, str):
        return [key]
    if isinstance(key, (list, tuple)):
        if len(key) == 0:
            raise ValueError("key list must not be empty")
        return list(key)
    raise TypeError(f"key must be str, List[str], or None, got {type(key)}")

def _make_composite_key(record: Dict[str, Any], key_cols: List[str]) -> Any:
    """Extract composite key as tuple. Single key returns the raw value for backward compat."""
    if len(key_cols) == 1:
        return record.get(key_cols[0])
    return tuple(record.get(k) for k in key_cols)

def _validate_key_columns(records: List[Dict[str, Any]], key_cols: List[str]) -> None:
    """Validate key columns exist. Raises KeyError with helpful message."""
    if not records:
        return
    first = records[0]
    missing = [k for k in key_cols if k not in first]
    if missing:
        raise KeyError(f"Key columns not found in records: {missing}. Available: {list(first.keys())}")

def _to_records(df: Any) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Convert pandas or polars DataFrame to list of dicts. Returns (records, columns, lib).

    DEF-022: For large DataFrames, consider using _try_vectorized_merge() fast-path
    which avoids this conversion entirely by using native DataFrame operations.
    """
    lib = type(df).__module__.split('.')[0]
    if lib == 'pandas':
        return df.to_dict('records'), list(df.columns), 'pandas'
    elif lib == 'polars':
        return df.to_dicts(), df.columns, 'polars'
    elif isinstance(df, list) and all(isinstance(r, dict) for r in df):
        cols = list({k for r in df for k in r})
        return df, cols, 'dicts'
    else:
        raise TypeError(f"Unsupported type: {type(df)}. Use pandas DataFrame, polars DataFrame, or list of dicts.")

def _try_vectorized_merge(
    df_a: Any, df_b: Any, key: str, prefer: str
) -> Any:
    """DEF-022: Vectorized fast-path for simple pandas/polars merges.

    Returns merged DataFrame using native operations when possible,
    or None if the merge requires dict-based path (schema, fuzzy, etc).
    """
    lib = type(df_a).__module__.split('.')[0]
    if lib == 'pandas':
        try:
            import pandas as pd
            # Use pandas merge with indicator to identify sources
            merged = pd.merge(df_a, df_b, on=key, how='outer', indicator=True, suffixes=('_a', '_b'))
            # For matched rows, resolve conflicts per column
            result_cols = list(dict.fromkeys(list(df_a.columns) + [c for c in df_b.columns if c not in df_a.columns]))
            result = pd.DataFrame()
            result[key] = merged[key]
            for col in result_cols:
                if col == key:
                    continue
                col_a = f"{col}_a" if f"{col}_a" in merged.columns else col
                col_b = f"{col}_b" if f"{col}_b" in merged.columns else col
                if col_a == col_b:
                    # Column only in one source
                    result[col] = merged[col]
                else:
                    # Both sources have this column — apply prefer logic
                    va = merged[col_a] if col_a in merged.columns else None
                    vb = merged[col_b] if col_b in merged.columns else None
                    if va is not None and vb is not None:
                        if prefer == "a":
                            result[col] = va.where(va.notna(), vb)
                        else:  # "b" or "latest"
                            result[col] = vb.where(vb.notna(), va)
                    elif va is not None:
                        result[col] = va
                    else:
                        result[col] = vb
            return result[result_cols]
        except Exception:
            return None
    return None

def _from_records(records: List[Dict[str, Any]], columns: List[str], lib: str) -> Any:
    """Convert records back to the original DataFrame type."""
    if lib == 'pandas':
        import pandas as pd
        df = pd.DataFrame(records)
        # Reorder columns: original order first, then new columns
        existing = [c for c in columns if c in df.columns]
        new_cols = [c for c in df.columns if c not in columns]
        return df[existing + new_cols]
    elif lib == 'polars':
        import polars as pl
        return pl.DataFrame(records)
    else:
        return records

def _row_hash(row: dict, exclude_keys: Optional[set] = None) -> str:
    """Deterministic hash of a row for dedup."""
    exclude = exclude_keys or set()
    parts = []
    for k in sorted(row.keys()):
        if k not in exclude:
            parts.append(f"{k}={row[k]}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

def merge(
    df_a: Any,
    df_b: Any,
    key: Optional[Union[str, List[str]]] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = "latest",
    dedup: bool = True,
    fuzzy_dedup: bool = False,
    fuzzy_threshold: float = 0.85,
    schema: Optional[Any] = None,
) -> Any:
    """
    Merge two DataFrames using CRDT semantics — conflict-free, deterministic, order-independent.

    Args:
        df_a: First DataFrame (pandas, polars, or list of dicts)
        df_b: Second DataFrame
        key: Column to match rows on. If None, performs append + dedup.
        timestamp_col: Column with timestamps for LWW resolution. If None, df_b wins ties.
        prefer: "latest" (default) or "a" or "b" — how to resolve conflicts when no timestamp.
        dedup: If True, remove exact duplicate rows in output.
        fuzzy_dedup: If True, also remove near-duplicate rows (requires key).
        fuzzy_threshold: Similarity threshold for fuzzy dedup (0.0 to 1.0).

    Returns:
        Merged DataFrame in same type as df_a.
    """
    _VALID_PREFER = {"latest", "a", "b"}
    if prefer not in _VALID_PREFER:
        raise ValueError(f"Invalid prefer={prefer!r}. Must be one of: {sorted(_VALID_PREFER)}")

    records_a, cols_a, lib_a = _to_records(df_a)
    records_b, cols_b, lib_b = _to_records(df_b)

    all_columns = list(dict.fromkeys(cols_a + [c for c in cols_b if c not in cols_a]))

    key_cols = _normalize_key(key)

    if key_cols is None:
        # No key: append all rows then dedup
        merged = records_a + records_b
        if dedup:
            merged = _dedup_records(merged, all_columns)
        return _from_records(merged, all_columns, lib_a)

    # Validate key columns exist
    _validate_key_columns(records_a, key_cols)
    _validate_key_columns(records_b, key_cols)

    # Build index by key for both sides; track None-key rows separately
    index_a: Dict[Any, Dict[str, Any]] = {}
    none_key_rows: List[Dict[str, Any]] = []
    dup_count_a = 0
    for r in records_a:
        k = _make_composite_key(r, key_cols)
        if k is None or (isinstance(k, tuple) and any(v is None for v in k)):
            none_key_rows.append(r)
        elif k in index_a:
            dup_count_a += 1
            index_a[k] = r  # keep last (backwards compatible)
        else:
            index_a[k] = r

    index_b: Dict[Any, Dict[str, Any]] = {}
    dup_count_b = 0
    for r in records_b:
        k = _make_composite_key(r, key_cols)
        if k is None or (isinstance(k, tuple) and any(v is None for v in k)):
            none_key_rows.append(r)
        elif k in index_b:
            dup_count_b += 1
            index_b[k] = r
        else:
            index_b[k] = r

    if dup_count_a + dup_count_b > 0:
        warnings.warn(
            f"Duplicate keys found: {dup_count_a} in df_a, {dup_count_b} in df_b. "
            f"Only the last row per key is kept. Deduplicate inputs for deterministic results.",
            UserWarning,
            stacklevel=2,
        )

    all_keys = list(dict.fromkeys(list(index_a.keys()) + list(index_b.keys())))
    merged = []

    for k in all_keys:
        row_a = index_a.get(k)
        row_b = index_b.get(k)

        if row_a and not row_b:
            merged.append(row_a)
        elif row_b and not row_a:
            merged.append(row_b)
        else:
            # Both sides have this key — CRDT merge per cell
            merged_row = _merge_rows(row_a, row_b, all_columns, timestamp_col, prefer, schema)
            merged.append(merged_row)

    # Append rows that had None key values (preserved as unique rows)
    merged.extend(none_key_rows)

    if dedup:
        # Include key columns in dedup hash — rows with different keys are always distinct
        merged = _dedup_records(merged, all_columns)

    if fuzzy_dedup and key_cols:
        merged = _fuzzy_dedup_records(merged, key_cols[0], all_columns, fuzzy_threshold)

    return _from_records(merged, all_columns, lib_a)

def _merge_rows(
    row_a: dict, row_b: dict, columns: List[str],
    timestamp_col: Optional[str], prefer: str, schema: Optional[Any] = None
) -> dict:
    """Merge two rows using LWW Register semantics per cell."""
    result = {}
    ts_a = _parse_timestamp(row_a.get(timestamp_col)) if timestamp_col else 0.0
    ts_b = _parse_timestamp(row_b.get(timestamp_col)) if timestamp_col else 0.0

    for col in columns:
        val_a = row_a.get(col)
        val_b = row_b.get(col)

        if val_a is None and val_b is not None:
            result[col] = val_b
        elif val_b is None and val_a is not None:
            result[col] = val_a
        elif val_a == val_b:
            result[col] = val_a
        else:
            # Conflict — resolve with schema strategy if available
            if schema is not None:
                strategy = schema.strategy_for(col)
                result[col] = strategy.resolve(val_a, val_b, ts_a, ts_b, "a", "b")
            elif timestamp_col:
                reg_a = LWWRegister(val_a, ts_a, "a")
                reg_b = LWWRegister(val_b, ts_b, "b")
                result[col] = reg_a.merge(reg_b).value
            elif prefer == "b":
                result[col] = val_b
            elif prefer == "a":
                result[col] = val_a
            else:  # "latest" — b wins as the "newer" source
                result[col] = val_b

    return result

def _dedup_records(
    records: List[dict], columns: List[str],
    exclude_keys: Optional[set] = None
) -> List[dict]:
    """Remove exact duplicate rows."""
    seen = set()
    unique = []
    for r in records:
        h = _row_hash(r, exclude_keys)
        if h not in seen:
            seen.add(h)
            unique.append(r)
    return unique

def _fuzzy_dedup_records(
    records: List[dict], key: str, columns: List[str],
    threshold: float
) -> List[dict]:
    """Remove near-duplicate rows based on text similarity of non-key columns."""
    if not records:
        return records

    def _text_of(row: dict) -> str:
        return " ".join(str(v) for k, v in sorted(row.items()) if k != key and v is not None)

    def _bigrams(s: str) -> set:
        s = s.lower()
        return {s[i:i+2] for i in range(len(s)-1)} if len(s) >= 2 else {s}

    def _similarity(a: str, b: str) -> float:
        ba, bb = _bigrams(a), _bigrams(b)
        if not ba or not bb:
            return 0.0
        return 2 * len(ba & bb) / (len(ba) + len(bb))

    unique = [records[0]]
    texts = [_text_of(records[0])]

    for r in records[1:]:
        t = _text_of(r)
        is_dup = False
        for existing_text in texts:
            if _similarity(t, existing_text) >= threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(r)
            texts.append(t)

    return unique

def diff(df_a: Any, df_b: Any, key: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Show what changed between two DataFrames.

    Returns dict with:
        added: rows in B not in A
        removed: rows in A not in B
        modified: rows where key matches but values differ (with old/new)
        unchanged: count of identical rows
    """
    records_a, cols_a, lib_a = _to_records(df_a)
    records_b, cols_b, _ = _to_records(df_b)

    key_cols = _normalize_key(key)
    _validate_key_columns(records_a, key_cols)
    _validate_key_columns(records_b, key_cols)

    index_a: Dict[Any, Dict[str, Any]] = {}
    for r in records_a:
        k = _make_composite_key(r, key_cols)
        if k is not None and not (isinstance(k, tuple) and any(v is None for v in k)):
            index_a[k] = r

    index_b: Dict[Any, Dict[str, Any]] = {}
    for r in records_b:
        k = _make_composite_key(r, key_cols)
        if k is not None and not (isinstance(k, tuple) and any(v is None for v in k)):
            index_b[k] = r

    added = [r for k, r in index_b.items() if k not in index_a]
    removed = [r for k, r in index_a.items() if k not in index_b]
    modified = []
    unchanged = 0

    for k in set(index_a) & set(index_b):
        if index_a[k] == index_b[k]:
            unchanged += 1
        else:
            changes = {}
            all_cols = set(index_a[k]) | set(index_b[k])
            for col in all_cols:
                va = index_a[k].get(col)
                vb = index_b[k].get(col)
                if va != vb:
                    changes[col] = {"old": va, "new": vb}
            modified.append({"key": k, "changes": changes})

    return {
        "added": _from_records(added, cols_b, lib_a) if added else _from_records([], cols_b, lib_a),
        "removed": _from_records(removed, cols_a, lib_a) if removed else _from_records([], cols_a, lib_a),
        "modified": modified,
        "unchanged": unchanged,
        "summary": f"+{len(added)} added, -{len(removed)} removed, ~{len(modified)} modified, ={unchanged} unchanged"
    }
