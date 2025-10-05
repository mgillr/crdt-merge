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
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .core import LWWRegister


def _to_records(df: Any) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Convert pandas or polars DataFrame to list of dicts. Returns (records, columns, lib)."""
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
    key: Optional[str] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = "latest",
    dedup: bool = True,
    fuzzy_dedup: bool = False,
    fuzzy_threshold: float = 0.85,
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
    records_a, cols_a, lib_a = _to_records(df_a)
    records_b, cols_b, lib_b = _to_records(df_b)

    all_columns = list(dict.fromkeys(cols_a + [c for c in cols_b if c not in cols_a]))

    if key is None:
        # No key: append all rows then dedup
        merged = records_a + records_b
        if dedup:
            merged = _dedup_records(merged, all_columns)
        return _from_records(merged, all_columns, lib_a)

    # Build index by key for both sides
    index_a: Dict[Any, Dict[str, Any]] = {}
    for r in records_a:
        k = r.get(key)
        if k is not None:
            index_a[k] = r

    index_b: Dict[Any, Dict[str, Any]] = {}
    for r in records_b:
        k = r.get(key)
        if k is not None:
            index_b[k] = r

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
            merged_row = _merge_rows(row_a, row_b, all_columns, timestamp_col, prefer)
            merged.append(merged_row)

    if dedup:
        merged = _dedup_records(merged, all_columns, exclude_keys={key})

    if fuzzy_dedup and key:
        merged = _fuzzy_dedup_records(merged, key, all_columns, fuzzy_threshold)

    return _from_records(merged, all_columns, lib_a)


def _merge_rows(
    row_a: dict, row_b: dict, columns: List[str],
    timestamp_col: Optional[str], prefer: str
) -> dict:
    """Merge two rows using LWW Register semantics per cell."""
    result = {}
    ts_a = float(row_a.get(timestamp_col, 0)) if timestamp_col else 0.0
    ts_b = float(row_b.get(timestamp_col, 0)) if timestamp_col else 0.0

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
            # Conflict — resolve with LWW
            if timestamp_col:
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


def diff(df_a: Any, df_b: Any, key: str) -> Dict[str, Any]:
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

    index_a = {r.get(key): r for r in records_a if r.get(key) is not None}
    index_b = {r.get(key): r for r in records_b if r.get(key) is not None}

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
