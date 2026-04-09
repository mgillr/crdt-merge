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

"""Shared Polars merge kernel — zero-copy, Rust-compiled strategy resolution.

This module provides the fast path for crdt-merge: the full outer join AND
strategy resolution both happen inside Polars' Rust engine.  Five of eight
built-in strategies compile to pure Polars expressions (MaxWins, MinWins,
LWW, Concat, LongestWins); the remaining three (Custom, Priority, UnionSet)
use Polars ``map_elements`` with the Python callback — still much faster
than the baseline because the join itself is in Rust.

Install the fast extra to enable::

    pip install crdt-merge[fast]

When polars is not installed every caller falls back to the pure-Python path
automatically.  Zero breaking changes.

.. note:: Dead code analysis (Issue #42)

   Static analysis may flag ~41 apparent dead-code candidates in this module.
   These are **false positives** — the functions/methods are part of the Polars
   expression-builder API pattern:

   - ``strategy_to_expr()`` builds Polars expressions dynamically; each branch
     (MaxWins, MinWins, LWW, Concat, LongestWins, fallback) is dispatched at
     runtime via ``_is_strategy()`` and called by ``polars_merge_arrow()`` /
     ``polars_merge_dicts()``.
   - ``_wrap_null()``, ``_resolve_row()`` are closures returned inside
     ``strategy_to_expr()`` — they execute inside the Polars engine.
   - ``_get_field_strategy()`` is called from both merge kernels.
   - ``polars_merge_dicts()`` is the primary entry point for accelerators.

   All exported symbols (``HAS_POLARS``, ``polars_merge_arrow``,
   ``polars_merge_dicts``, ``strategy_to_expr``) are used by ``arrow.py``
   and accelerator modules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

__all__ = [
    "HAS_POLARS",
    "polars_merge_arrow",
    "polars_merge_dicts",
    "strategy_to_expr",
]

# ---------------------------------------------------------------------------
# Optional import
# ---------------------------------------------------------------------------

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:  # pragma: no cover
    pl = None  # type: ignore[assignment]  # fallback when polars not installed
    HAS_POLARS = False

try:
    import pyarrow as pa

    HAS_ARROW = True
except ImportError:  # pragma: no cover
    pa = None  # type: ignore[assignment]  # fallback when pyarrow not installed
    HAS_ARROW = False

# ---------------------------------------------------------------------------
# Strategy → Polars expression compiler
# ---------------------------------------------------------------------------

def _is_strategy(strategy: Any, name: str) -> bool:
    """Check strategy type by class name to avoid circular imports."""
    return type(strategy).__name__ == name

def strategy_to_expr(
    col: str,
    strategy: Any,
    timestamp_col: Optional[str] = None,
    suffix: str = "_right",
    left_dtype: Optional["pl.DataType"] = None,
) -> "pl.Expr":
    """Compile a MergeStrategy into a Polars expression.

    For vectorizable strategies (LWW, MaxWins, MinWins, Concat, LongestWins)
    the expression runs entirely in Rust.  For others (Custom, Priority,
    UnionSet) we fall back to ``map_elements`` which still benefits from the
    Rust join.

    Parameters
    ----------
    col : str
        Column name (left-side).
    strategy : MergeStrategy
        The strategy instance to compile.
    timestamp_col : str, optional
        Timestamp column for LWW resolution.
    suffix : str
        Suffix appended to right-side columns by the join (default "_right").

    Returns
    -------
    pl.Expr
        A Polars expression that resolves conflicts for *col*.
    """
    left = pl.col(col)
    right = pl.col(f"{col}{suffix}")

    # Null handling wrapper: if only one side has data, take it.
    def _wrap_null(inner_expr: "pl.Expr") -> "pl.Expr":
        return (
            pl.when(left.is_null() & right.is_null())
            .then(pl.lit(None))
            .when(left.is_null())
            .then(right)
            .when(right.is_null())
            .then(left)
            .otherwise(inner_expr)
            .alias(col)
        )

    # ── MaxWins ──────────────────────────────────────────────
    if _is_strategy(strategy, "MaxWins"):
        return _wrap_null(pl.max_horizontal(left, right))

    # ── MinWins ──────────────────────────────────────────────
    if _is_strategy(strategy, "MinWins"):
        return _wrap_null(pl.min_horizontal(left, right))

    # ── LWW (Last Writer Wins) ───────────────────────────────
    if _is_strategy(strategy, "LWW"):
        if timestamp_col:
            ts_l = pl.col(timestamp_col)
            ts_r = pl.col(f"{timestamp_col}{suffix}")
            # Tie-break: deterministic value-based comparison for CRDT commutativity
            tie_expr = (
                pl.when(left.cast(pl.Utf8) >= right.cast(pl.Utf8)).then(left)
                .otherwise(right)
            )
            inner = (
                pl.when(ts_r > ts_l).then(right)
                .when(ts_l > ts_r).then(left)
                .otherwise(tie_expr)
            )
            return _wrap_null(inner)
        # No timestamp → deterministic value-based tie-break for CRDT commutativity
        tie_expr = (
            pl.when(left.cast(pl.Utf8) >= right.cast(pl.Utf8)).then(left)
            .otherwise(right)
        )
        return _wrap_null(tie_expr)

    # ── Concat ───────────────────────────────────────────────
    if _is_strategy(strategy, "Concat"):
        sep = getattr(strategy, "separator", ", ")
        inner = pl.concat_str(
            [left.cast(pl.Utf8).fill_null(""), right.cast(pl.Utf8).fill_null("")],
            separator=sep,
        )
        return _wrap_null(inner)

    # ── LongestWins ──────────────────────────────────────────
    if _is_strategy(strategy, "LongestWins"):
        inner = (
            pl.when(left.cast(pl.Utf8).str.len_chars() >= right.cast(pl.Utf8).str.len_chars())
            .then(left)
            .otherwise(right)
        )
        return _wrap_null(inner)

    # ── Fallback: map_elements (Custom, Priority, UnionSet) ──
    # Still faster than baseline: the join is Rust, only resolution is Python.
    # We must infer the correct Polars return dtype from the left column.
    def _resolve_row(row: dict) -> Any:
        va = row.get(col)
        vb = row.get(f"{col}{suffix}")
        if va is None:
            return vb
        if vb is None:
            return va
        return strategy.resolve(va, vb)

    # Use the left column's actual dtype so map_elements returns typed data.
    _rdtype = left_dtype if left_dtype is not None else pl.Utf8
    return (
        pl.struct([left, right])
        .map_elements(_resolve_row, return_dtype=_rdtype)
        .alias(col)
    )

# ---------------------------------------------------------------------------
# Core merge kernel -- Arrow tables
# ---------------------------------------------------------------------------

def polars_merge_arrow(
    left: "pa.Table",
    right: "pa.Table",
    key: str,
    schema: Any,
    timestamp_col: Optional[str] = None,
) -> Tuple["pa.Table", int]:
    """Merge two Arrow tables using the Polars engine.

    Parameters
    ----------
    left, right : pa.Table
        Input Arrow tables.
    key : str
        Join key column.
    schema : MergeSchema
        Per-field strategy configuration.
    timestamp_col : str, optional
        Column name for LWW timestamps.

    Returns
    -------
    tuple[pa.Table, int]
        (merged_table, conflict_count)

    Raises
    ------
    ImportError
        If polars is not installed.
    """
    if not HAS_POLARS:
        raise ImportError(
            "polars is required for the fast merge engine. "
            "Install with: pip install crdt-merge[fast]"
        )

    suffix = "_right"

    # Zero-copy Arrow → Polars via Arrow C Data Interface
    left_pl = pl.from_arrow(left)
    right_pl = pl.from_arrow(right)

    # ── Full outer join in Rust ──────────────────────────────
    joined = left_pl.join(
        right_pl,
        on=key,
        how="full",
        suffix=suffix,
        coalesce=True,
    )

    # ── Count conflicts (rows where both sides had the key) ──
    # After coalesced full join, right-side columns are non-null when
    # the right had that key.  We detect conflicts by checking if ANY
    # non-key column has both left and right values.
    data_cols = [c for c in left_pl.columns if c != key and f"{c}{suffix}" in joined.columns]
    if data_cols:
        first_col = data_cols[0]
        both_mask = (
            joined[first_col].is_not_null() & joined[f"{first_col}{suffix}"].is_not_null()
        )
        conflict_count = int(both_mask.sum())
    else:
        conflict_count = 0

    # ── Compile strategy expressions ─────────────────────────
    exprs: List[pl.Expr] = [pl.col(key)]  # always keep the key

    # Get default strategy

    for col in left_pl.columns:
        if col == key:
            continue
        if col == timestamp_col:
            continue  # skip timestamp col from output (used for LWW only)
        right_col_name = f"{col}{suffix}"
        if right_col_name not in joined.columns:
            # Column only in left
            exprs.append(pl.col(col))
            continue
        # Get per-field strategy, fall back to default
        field_strategy = _get_field_strategy(schema, col)
        if field_strategy is None:
            # No strategy → coalesce (prefer right, like LWW with no ts)
            exprs.append(pl.coalesce([pl.col(right_col_name), pl.col(col)]).alias(col))
        else:
            col_dtype = joined.schema.get(col, pl.Utf8)
            exprs.append(strategy_to_expr(col, field_strategy, timestamp_col, suffix, left_dtype=col_dtype))

    # Add columns only in right (not in left)
    for col in right_pl.columns:
        if col == key or col == timestamp_col:
            continue
        right_col_name = f"{col}{suffix}"
        if col not in left_pl.columns and right_col_name in joined.columns:
            exprs.append(pl.col(right_col_name).alias(col))
        elif col not in left_pl.columns and col in joined.columns:
            exprs.append(pl.col(col))

    # ── Execute plan (single Rust pass) ──────────────────────
    result_pl = joined.select(exprs)

    # Zero-copy Polars → Arrow
    result_arrow = result_pl.to_arrow()

    logger.debug(
        "polars_merge_arrow: %d left + %d right → %d merged (%d conflicts)",
        left.num_rows,
        right.num_rows,
        result_arrow.num_rows,
        conflict_count,
    )

    return result_arrow, conflict_count

# ---------------------------------------------------------------------------
# Core merge kernel -- List[dict] (for accelerators)
# ---------------------------------------------------------------------------

def polars_merge_dicts(
    left_rows: List[dict],
    right_rows: List[dict],
    key: str,
    schema: Any,
    timestamp_col: Optional[str] = None,
) -> Tuple[List[dict], int]:
    """Merge two lists of dicts using the Polars engine.

    This is the entry point for accelerators that work with Python dicts.
    Converts to Polars, merges in Rust, converts back to dicts.

    Parameters
    ----------
    left_rows, right_rows : list[dict]
        Input rows as Python dictionaries.
    key : str
        Join key column.
    schema : MergeSchema
        Per-field strategy configuration.
    timestamp_col : str, optional
        Column name for LWW timestamps.

    Returns
    -------
    tuple[list[dict], int]
        (merged_rows, conflict_count)
    """
    if not HAS_POLARS:
        raise ImportError(
            "polars is required for the fast merge engine. "
            "Install with: pip install crdt-merge[fast]"
        )

    if not left_rows and not right_rows:
        return [], 0
    if not left_rows:
        return list(right_rows), 0
    if not right_rows:
        return list(left_rows), 0

    suffix = "_right"

    left_pl = pl.DataFrame(left_rows)
    right_pl = pl.DataFrame(right_rows)

    # Full outer join in Rust
    joined = left_pl.join(
        right_pl,
        on=key,
        how="full",
        suffix=suffix,
        coalesce=True,
    )

    # Count conflicts
    data_cols = [c for c in left_pl.columns if c != key and f"{c}{suffix}" in joined.columns]
    if data_cols:
        first_col = data_cols[0]
        both_mask = (
            joined[first_col].is_not_null() & joined[f"{first_col}{suffix}"].is_not_null()
        )
        conflict_count = int(both_mask.sum())
    else:
        conflict_count = 0

    # Compile strategy expressions
    exprs: List[pl.Expr] = [pl.col(key)]

    for col in left_pl.columns:
        if col == key or col == timestamp_col:
            continue
        right_col_name = f"{col}{suffix}"
        if right_col_name not in joined.columns:
            exprs.append(pl.col(col))
            continue
        field_strategy = _get_field_strategy(schema, col)
        if field_strategy is None:
            exprs.append(pl.coalesce([pl.col(right_col_name), pl.col(col)]).alias(col))
        else:
            col_dtype = joined.schema.get(col, pl.Utf8)
            exprs.append(strategy_to_expr(col, field_strategy, timestamp_col, suffix, left_dtype=col_dtype))

    for col in right_pl.columns:
        if col == key or col == timestamp_col:
            continue
        right_col_name = f"{col}{suffix}"
        if col not in left_pl.columns and right_col_name in joined.columns:
            exprs.append(pl.col(right_col_name).alias(col))
        elif col not in left_pl.columns and col in joined.columns:
            exprs.append(pl.col(col))

    # Execute in Rust
    result_pl = joined.select(exprs)

    return result_pl.to_dicts(), conflict_count

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_field_strategy(schema: Any, field: str) -> Any:
    """Extract per-field strategy from a MergeSchema.

    Uses the official ``strategy_for()`` API which returns the per-field
    strategy if set, otherwise falls back to the schema default.
    """
    if hasattr(schema, "strategy_for"):
        return schema.strategy_for(field)
    # Fallback for non-standard schema objects
    if hasattr(schema, "_strategies"):
        strats = schema._strategies
        if isinstance(strats, dict) and field in strats:
            return strats[field]
    if hasattr(schema, "default"):
        return schema.default
    return None
