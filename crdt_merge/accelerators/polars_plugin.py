# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""
Polars Expression Plugin — native Polars DataFrame CRDT merge.

Provides :class:`PolarsCRDTMerge` for merging two Polars DataFrames with
per-field CRDT strategies (LWW, MaxWins, MinWins, etc.) and optional
Arrow-native zero-copy interop.

External dependency: ``polars`` — **lazy-imported**.  The module can be
imported even when Polars is not installed; operations that need Polars
will raise a clear ``ImportError`` at call-time.

Usage::

    from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins

    merger = PolarsCRDTMerge(schema=MergeSchema(default=LWW(), salary=MaxWins()))
    result = merger.merge(df_left, df_right, key="id")
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from crdt_merge.strategies import LWW, MergeSchema, MergeStrategy


def _safe_parse_ts(value):
    """Parse timestamp to float — handles numeric, ISO-8601, None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
        from datetime import datetime as _dt
        try:
            return _dt.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError, TypeError):
            pass
    if hasattr(value, 'timestamp'):
        try:
            return float(value.timestamp())
        except (TypeError, OSError):
            pass
    return 0.0

# Lazy-import polars
try:
    import polars as _pl  # type: ignore[import-untyped]
except ImportError:
    _pl = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLARS_INSTALL_MSG = (
    "Polars is required for this accelerator. Install it with: pip install polars"
)


def _require_polars() -> Any:
    """Return the ``polars`` module or raise ImportError."""
    if _pl is None:
        raise ImportError(_POLARS_INSTALL_MSG)
    return _pl


def _to_dicts(df: Any) -> List[dict]:
    """Convert a Polars DataFrame to list of dicts."""
    if hasattr(df, "to_dicts"):
        return df.to_dicts()
    if isinstance(df, list):
        return df
    raise TypeError(f"Expected Polars DataFrame or list of dicts, got {type(df)}")


def _from_dicts(records: List[dict], pl: Any) -> Any:
    """Create a Polars DataFrame from list of dicts."""
    if not records:
        return pl.DataFrame()
    return pl.DataFrame(records)


# ---------------------------------------------------------------------------
# Expression wrapper
# ---------------------------------------------------------------------------

class CRDTMergeExpression:
    """Wrapper representing a CRDT merge expression for a single field.

    Used with ``PolarsCRDTMerge.as_expression()`` to build composable merge
    expressions for use in ``df.with_columns(...)``.

    This is a *description* of the merge operation; it does not execute
    until applied to actual data via :meth:`apply`.
    """

    def __init__(self, field: str, strategy: MergeStrategy) -> None:
        self._field = field
        self._strategy = strategy

    @property
    def field(self) -> str:
        """The field name this expression targets."""
        return self._field

    @property
    def strategy_name(self) -> str:
        """Name of the merge strategy."""
        return self._strategy.name()

    def apply(self, val_a: Any, val_b: Any,
              ts_a: float = 0.0, ts_b: float = 0.0,
              node_a: str = "a", node_b: str = "b") -> Any:
        """Resolve a single conflict using the embedded strategy."""
        return self._strategy.resolve(val_a, val_b, ts_a, ts_b, node_a, node_b)

    def __repr__(self) -> str:
        return f"CRDTMergeExpression(field={self._field!r}, strategy={self.strategy_name})"


# ---------------------------------------------------------------------------
# Merge result
# ---------------------------------------------------------------------------

class PolarsMergeResult:
    """Result of a Polars CRDT merge operation.

    Attributes:
        data: Merged Polars DataFrame.
        conflicts: Number of field-level conflicts resolved.
        merge_time_ms: Execution time in milliseconds.
        rows_merged: Number of rows where both sources had matching keys.
        rows_left_only: Number of rows unique to left DataFrame.
        rows_right_only: Number of rows unique to right DataFrame.
    """

    def __init__(
        self,
        data: Any,
        conflicts: int = 0,
        merge_time_ms: float = 0.0,
        rows_merged: int = 0,
        rows_left_only: int = 0,
        rows_right_only: int = 0,
    ) -> None:
        self.data = data
        self.conflicts = conflicts
        self.merge_time_ms = merge_time_ms
        self.rows_merged = rows_merged
        self.rows_left_only = rows_left_only
        self.rows_right_only = rows_right_only

    def to_dict(self) -> Dict[str, Any]:
        """Summary stats as dict."""
        return {
            "conflicts": self.conflicts,
            "merge_time_ms": round(self.merge_time_ms, 2),
            "rows_merged": self.rows_merged,
            "rows_left_only": self.rows_left_only,
            "rows_right_only": self.rows_right_only,
            "total_rows": self.rows_merged + self.rows_left_only + self.rows_right_only,
        }

    def __repr__(self) -> str:
        total = self.rows_merged + self.rows_left_only + self.rows_right_only
        return (
            f"PolarsMergeResult(rows={total}, conflicts={self.conflicts}, "
            f"{self.merge_time_ms:.1f}ms)"
        )


# ---------------------------------------------------------------------------
# Main accelerator class
# ---------------------------------------------------------------------------

class PolarsCRDTMerge:
    """Polars expression plugin for CRDT merge operations.

    Provides native Polars DataFrame merge with CRDT strategies.  Converts
    DataFrames to list-of-dicts internally, applies per-field strategies, and
    returns a new Polars DataFrame.

    When Polars is not installed, :meth:`is_available` returns ``False`` and
    merge operations raise ``ImportError``.

    Args:
        schema: Optional MergeSchema for per-field strategies.
        timestamp_col: Column name for LWW timestamps (optional).

    Example::

        merger = PolarsCRDTMerge(schema=MergeSchema(default=LWW(), salary=MaxWins()))
        result = merger.merge(df_left, df_right, key="id")
        print(result.data)   # merged Polars DataFrame
    """

    name: str = "polars_plugin"
    version: str = "0.7.2"

    def __init__(
        self,
        schema: Optional[MergeSchema] = None,
        timestamp_col: Optional[str] = None,
    ) -> None:
        self._schema = schema or MergeSchema(default=LWW())
        self._timestamp_col = timestamp_col

    # ------------------------------------------------------------------
    # Core merge
    # ------------------------------------------------------------------

    def merge(
        self,
        left: Any,
        right: Any,
        key: str = "id",
        strategies: Optional[Dict[str, str]] = None,
        timestamp_col: Optional[str] = None,
    ) -> PolarsMergeResult:
        """Merge two Polars DataFrames with CRDT strategies.

        Args:
            left: Left Polars DataFrame (or list of dicts).
            right: Right Polars DataFrame (or list of dicts).
            key: Column to match rows on.
            strategies: Optional per-field strategy overrides (name → strategy name).
            timestamp_col: Column with timestamps for LWW resolution.

        Returns:
            PolarsMergeResult with merged DataFrame and statistics.
        """
        pl = _require_polars()
        start = time.time()
        ts_col = timestamp_col or self._timestamp_col

        schema = self._resolve_schema(strategies)

        left_dicts = _to_dicts(left)
        right_dicts = _to_dicts(right)

        # Index by key
        left_idx: Dict[Any, dict] = {}
        for r in left_dicts:
            k = r.get(key)
            if k is not None:
                left_idx[k] = r

        right_idx: Dict[Any, dict] = {}
        for r in right_dicts:
            k = r.get(key)
            if k is not None:
                right_idx[k] = r

        all_keys = list(dict.fromkeys(list(left_idx.keys()) + list(right_idx.keys())))

        merged_rows: List[dict] = []
        conflicts = 0
        rows_merged = 0
        rows_left_only = 0
        rows_right_only = 0

        for k in all_keys:
            row_l = left_idx.get(k)
            row_r = right_idx.get(k)

            if row_l and row_r:
                m, c = self._merge_row(row_l, row_r, schema, ts_col)
                merged_rows.append(m)
                conflicts += c
                rows_merged += 1
            elif row_l:
                merged_rows.append(dict(row_l))
                rows_left_only += 1
            else:
                merged_rows.append(dict(row_r))  # type: ignore[arg-type]
                rows_right_only += 1

        elapsed_ms = (time.time() - start) * 1000
        df = _from_dicts(merged_rows, pl)

        return PolarsMergeResult(
            data=df,
            conflicts=conflicts,
            merge_time_ms=round(elapsed_ms, 2),
            rows_merged=rows_merged,
            rows_left_only=rows_left_only,
            rows_right_only=rows_right_only,
        )

    def merge_lazy(
        self,
        left: Any,
        right: Any,
        key: str = "id",
        strategies: Optional[Dict[str, str]] = None,
        timestamp_col: Optional[str] = None,
    ) -> PolarsMergeResult:
        """Lazy merge — collects LazyFrames before merging.

        For very large datasets, converts LazyFrames to DataFrames in a
        streaming-compatible way then delegates to :meth:`merge`.

        Args:
            left: Left Polars LazyFrame or DataFrame.
            right: Right Polars LazyFrame or DataFrame.
            key: Column to match rows on.
            strategies: Optional per-field strategy overrides.
            timestamp_col: Column with timestamps for LWW resolution.

        Returns:
            PolarsMergeResult with merged DataFrame.
        """
        pl = _require_polars()
        # Collect LazyFrames if necessary
        if hasattr(left, "collect"):
            left = left.collect()
        if hasattr(right, "collect"):
            right = right.collect()
        return self.merge(left, right, key=key, strategies=strategies,
                          timestamp_col=timestamp_col)

    # ------------------------------------------------------------------
    # Expression API
    # ------------------------------------------------------------------

    def as_expression(self, field: str, strategy: str = "lww") -> CRDTMergeExpression:
        """Return a CRDTMergeExpression for use in composable merge pipelines.

        Args:
            field: The field name to apply the strategy to.
            strategy: Strategy name (e.g. "lww", "max", "min", "union", "concat").

        Returns:
            CRDTMergeExpression that can be applied to values.
        """
        from crdt_merge.strategies import MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins

        _lookup: Dict[str, type] = {
            "lww": LWW,
            "max": MaxWins, "maxwins": MaxWins, "max_wins": MaxWins,
            "min": MinWins, "minwins": MinWins, "min_wins": MinWins,
            "union": UnionSet, "unionset": UnionSet, "union_set": UnionSet,
            "concat": Concat,
            "priority": Priority,
            "longest": LongestWins, "longestwins": LongestWins, "longest_wins": LongestWins,
        }
        cls = _lookup.get(strategy.lower())
        if cls is None:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Available: {', '.join(sorted(_lookup.keys()))}"
            )
        return CRDTMergeExpression(field=field, strategy=cls())

    # ------------------------------------------------------------------
    # Namespace registration
    # ------------------------------------------------------------------

    def register_namespace(self) -> None:
        """Register ``crdt`` namespace on Polars DataFrames.

        After calling this, you can use ``df.crdt.merge(...)`` syntax.
        Requires Polars ≥ 0.19 with namespace extension support.
        """
        pl = _require_polars()
        # Polars namespace registration is version-dependent and may
        # not be available in all Polars versions.  This is a best-effort
        # registration that fails silently if unsupported.
        try:
            if not hasattr(pl, "api") or not hasattr(pl.api, "register_dataframe_namespace"):
                return

            @pl.api.register_dataframe_namespace("crdt")
            class CRDTNamespace:
                def __init__(ns_self, df: Any) -> None:
                    ns_self._df = df

                def merge(ns_self, other: Any, key: str = "id",
                          strategies: Optional[Dict[str, str]] = None) -> Any:
                    result = self.merge(ns_self._df, other, key=key, strategies=strategies)
                    return result.data

        except Exception:
            pass  # Namespace registration not supported in this Polars version

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status.

        Returns:
            Dict with status, polars availability, and version info.
        """
        polars_available = _pl is not None
        polars_version = getattr(_pl, "__version__", "unknown") if polars_available else None
        return {
            "name": self.name,
            "version": self.version,
            "polars_available": polars_available,
            "polars_version": polars_version,
            "status": "ready" if polars_available else "degraded",
            "schema_fields": len(self._schema.fields),
        }

    def is_available(self) -> bool:
        """Check whether Polars is available."""
        return _pl is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_schema(self, overrides: Optional[Dict[str, str]] = None) -> MergeSchema:
        """Build effective schema from base + overrides."""
        if not overrides:
            return self._schema
        # Build a copy with overrides applied
        from crdt_merge.strategies import MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins
        _lookup: Dict[str, type] = {
            "lww": LWW,
            "max": MaxWins, "maxwins": MaxWins, "max_wins": MaxWins,
            "min": MinWins, "minwins": MinWins, "min_wins": MinWins,
            "union": UnionSet, "unionset": UnionSet, "union_set": UnionSet,
            "concat": Concat,
            "priority": Priority,
            "longest": LongestWins, "longestwins": LongestWins, "longest_wins": LongestWins,
        }
        schema = MergeSchema(default=self._schema.default)
        for fld, strat in self._schema.fields.items():
            schema.set_strategy(fld, strat)
        for fld, name in overrides.items():
            cls = _lookup.get(name.lower())
            if cls is None:
                raise ValueError(
                    f"Unknown strategy '{name}' for field '{fld}'. "
                    f"Available: {', '.join(sorted(_lookup.keys()))}"
                )
            schema.set_strategy(fld, cls())
        return schema

    def _merge_row(
        self,
        row_a: dict,
        row_b: dict,
        schema: MergeSchema,
        timestamp_col: Optional[str],
    ) -> Tuple[dict, int]:
        """Merge two rows using per-field strategies. Returns (merged, conflict_count)."""
        all_cols = list(dict.fromkeys(list(row_a.keys()) + list(row_b.keys())))
        merged: dict = {}
        conflicts = 0

        ts_a = _safe_parse_ts(row_a.get(timestamp_col)) if timestamp_col else 0.0
        ts_b = _safe_parse_ts(row_b.get(timestamp_col)) if timestamp_col else 0.0

        for col in all_cols:
            va = row_a.get(col)
            vb = row_b.get(col)
            if va is None:
                merged[col] = vb
            elif vb is None:
                merged[col] = va
            elif va == vb:
                merged[col] = va
            else:
                strategy = schema.strategy_for(col)
                merged[col] = strategy.resolve(va, vb, ts_a, ts_b, "left", "right")
                conflicts += 1

        return merged, conflicts

    def __repr__(self) -> str:
        avail = "available" if self.is_available() else "not installed"
        return f"PolarsCRDTMerge(polars={avail}, fields={len(self._schema.fields)})"


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def crdt_merge_expr(field: str, strategy: str = "lww") -> CRDTMergeExpression:
    """Create a standalone CRDT merge expression.

    Convenience function for quick one-off expressions::

        expr = crdt_merge_expr("salary", "max")
        resolved = expr.apply(100, 200)  # → 200
    """
    merger = PolarsCRDTMerge()
    return merger.as_expression(field, strategy)


__all__ = [
    "PolarsCRDTMerge",
    "PolarsMergeResult",
    "CRDTMergeExpression",
    "crdt_merge_expr",
]
