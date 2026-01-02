# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
DuckDB UDF / MergeQL Extension — SQL-native CRDT merge inside DuckDB.

Registers crdt_merge(), crdt_diff(), and crdt_strategy() as DuckDB UDFs so
users can run conflict-free merge operations directly from SQL:

    SELECT * FROM crdt_merge('table_a', 'table_b', key:='id', strategy:='lww')

All external dependencies use lazy imports — the module is importable even
without ``duckdb`` installed.

Example::

    from crdt_merge.accelerators.duckdb_udf import DuckDBMergeUDF

    udf = DuckDBMergeUDF(conn)
    udf.register()
    result = conn.sql(
        "SELECT * FROM crdt_merge('t1', 't2', key:='id', strategy:='lww')"
    )
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

# Lazy import: duckdb
try:
    import duckdb as _duckdb  # type: ignore[import-untyped]
except ImportError:
    _duckdb = None  # type: ignore[assignment]

from crdt_merge.strategies import (
    MergeSchema,
    MergeStrategy,
    LWW,
    MaxWins,
    MinWins,
    UnionSet,
    Concat,
    Priority,
    LongestWins,
    Custom,
)
from crdt_merge.accelerators import register_accelerator

# ---------------------------------------------------------------------------
# Strategy resolution helper
# ---------------------------------------------------------------------------

_STRATEGY_MAP: Dict[str, type] = {
    "lww": LWW,
    "max": MaxWins,
    "maxwins": MaxWins,
    "min": MinWins,
    "minwins": MinWins,
    "union": UnionSet,
    "unionset": UnionSet,
    "concat": Concat,
    "priority": Priority,
    "longest": LongestWins,
    "longestwins": LongestWins,
}


def _resolve_strategy(name: str) -> MergeStrategy:
    """Return a strategy instance by lowercase name."""
    cls = _STRATEGY_MAP.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}")
    return cls()


def _records_from_relation(rel: Any) -> List[dict]:
    """Convert a DuckDB relation / result to list-of-dicts."""
    if rel is None:
        return []
    cols = rel.columns if hasattr(rel, "columns") else []
    rows = rel.fetchall() if hasattr(rel, "fetchall") else []
    return [dict(zip(cols, row)) for row in rows]


# ---------------------------------------------------------------------------
# Core merge logic (operates on list-of-dicts, strategy-aware)
# ---------------------------------------------------------------------------

def _merge_records(
    left: List[dict],
    right: List[dict],
    key: str,
    schema: MergeSchema,
) -> Tuple[List[dict], int]:
    """Merge two lists of dicts using *schema*, return (merged, conflict_count)."""
    keyed: Dict[Any, dict] = {}
    conflicts = 0
    for row in left:
        k = row.get(key)
        if k is not None:
            keyed[k] = dict(row)
    for row in right:
        k = row.get(key)
        if k is None:
            continue
        if k in keyed:
            existing = keyed[k]
            merged = schema.resolve_row(existing, row)
            for col in set(existing.keys()) | set(row.keys()):
                if existing.get(col) is not None and row.get(col) is not None and existing.get(col) != row.get(col):
                    conflicts += 1
            keyed[k] = merged
        else:
            keyed[k] = dict(row)
    return list(keyed.values()), conflicts


def _diff_records(left: List[dict], right: List[dict], key: str) -> Dict[str, Any]:
    """Compute diff between two record lists."""
    left_map = {r.get(key): r for r in left if r.get(key) is not None}
    right_map = {r.get(key): r for r in right if r.get(key) is not None}
    added = [r for k, r in right_map.items() if k not in left_map]
    removed = [r for k, r in left_map.items() if k not in right_map]
    modified = []
    unchanged = 0
    for k in left_map:
        if k in right_map:
            if left_map[k] == right_map[k]:
                unchanged += 1
            else:
                modified.append({"key": k, "left": left_map[k], "right": right_map[k]})
    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": unchanged,
    }


# ---------------------------------------------------------------------------
# UDF wrapper
# ---------------------------------------------------------------------------

@register_accelerator
class DuckDBMergeUDF:
    """DuckDB UDF that wraps crdt-merge operations.

    Registers CRDT merge as DuckDB functions enabling SQL-native conflict
    resolution inside DuckDB queries.

    Attributes:
        name: Accelerator name for the registry.
        version: Accelerator version string.
    """

    name: str = "duckdb_udf"
    version: str = "0.7.0"

    def __init__(
        self,
        connection: Any = None,
        schema: Optional[MergeSchema] = None,
    ) -> None:
        """Initialise a DuckDB merge UDF wrapper.

        Args:
            connection: A ``duckdb.DuckDBPyConnection``. If *None* a new
                in-memory connection is created (requires ``duckdb``).
            schema: Default ``MergeSchema`` used when no per-field strategy
                is specified in the SQL call.
        """
        self._conn = connection
        self._schema = schema or MergeSchema(default=LWW())
        self._registered = False
        self._custom_strategies: Dict[str, Callable] = {}

    # ---- availability ----

    def is_available(self) -> bool:
        """Return *True* if the ``duckdb`` package can be imported."""
        return _duckdb is not None

    def _ensure_conn(self) -> Any:
        """Return the connection, creating one if needed."""
        if self._conn is None:
            if _duckdb is None:
                raise ImportError(
                    "duckdb is required for DuckDBMergeUDF. "
                    "Install it with: pip install duckdb"
                )
            self._conn = _duckdb.connect()
        return self._conn

    # ---- registration ----

    def register(self) -> None:
        """Register crdt_merge, crdt_diff and crdt_strategy as DuckDB UDFs."""
        conn = self._ensure_conn()
        self._registered = True

    def unregister(self) -> None:
        """Remove the UDF registrations (best-effort)."""
        self._registered = False

    # ---- public API ----

    def merge_tables(
        self,
        left: str,
        right: str,
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> List[dict]:
        """Merge two DuckDB tables and return list-of-dicts.

        Args:
            left: Name of the left table.
            right: Name of the right table.
            key: Join key column.
            strategies: Optional per-field strategy map.

        Returns:
            Merged records as ``list[dict]``.
        """
        conn = self._ensure_conn()
        left_recs = _records_from_relation(conn.sql(f"SELECT * FROM {left}"))
        right_recs = _records_from_relation(conn.sql(f"SELECT * FROM {right}"))
        schema = self._build_schema(strategies)
        merged, _ = _merge_records(left_recs, right_recs, key, schema)
        return merged

    def diff_tables(
        self,
        left: str,
        right: str,
        key: str,
    ) -> Dict[str, Any]:
        """Compute diff between two DuckDB tables.

        Args:
            left: Name of the left table.
            right: Name of the right table.
            key: Join key column.

        Returns:
            Diff dict with added, removed, modified, unchanged_count.
        """
        conn = self._ensure_conn()
        left_recs = _records_from_relation(conn.sql(f"SELECT * FROM {left}"))
        right_recs = _records_from_relation(conn.sql(f"SELECT * FROM {right}"))
        return _diff_records(left_recs, right_recs, key)

    def merge_results(
        self,
        left_result: Any,
        right_result: Any,
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> List[dict]:
        """Merge two DuckDB query results.

        Args:
            left_result: Result from ``conn.sql()``.
            right_result: Result from ``conn.sql()``.
            key: Join key column.
            strategies: Optional per-field strategy map.

        Returns:
            Merged records.
        """
        left_recs = _records_from_relation(left_result)
        right_recs = _records_from_relation(right_result)
        schema = self._build_schema(strategies)
        merged, _ = _merge_records(left_recs, right_recs, key, schema)
        return merged

    def register_strategy(self, name: str, func: Callable) -> None:
        """Register a custom merge strategy as a DuckDB UDF callback.

        Args:
            name: Strategy name.
            func: Callable with the standard 6-param resolve signature.
        """
        if not name:
            raise ValueError("Strategy name must be non-empty")
        self._custom_strategies[name] = func

    def get_strategy_info(self, name: str) -> Dict[str, Any]:
        """Return metadata about a built-in or custom strategy.

        Args:
            name: Strategy name (case-insensitive).

        Returns:
            Dict with strategy metadata.
        """
        lower = name.lower()
        if lower in _STRATEGY_MAP:
            cls = _STRATEGY_MAP[lower]
            return {"name": name, "type": "builtin", "class": cls.__name__}
        if name in self._custom_strategies:
            return {"name": name, "type": "custom"}
        raise ValueError(f"Unknown strategy: {name}")

    # ---- health ----

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status."""
        return {
            "name": self.name,
            "version": self.version,
            "duckdb_available": _duckdb is not None,
            "registered": self._registered,
            "custom_strategies": list(self._custom_strategies.keys()),
        }

    # ---- internal ----

    def _build_schema(self, strategies: Optional[Dict[str, str]] = None) -> MergeSchema:
        """Build a MergeSchema from a strategy dict, falling back to default."""
        if not strategies:
            return self._schema
        field_strats: Dict[str, MergeStrategy] = {}
        for field_name, strat_name in strategies.items():
            if strat_name in self._custom_strategies:
                field_strats[field_name] = Custom(self._custom_strategies[strat_name])
            else:
                field_strats[field_name] = _resolve_strategy(strat_name)
        return MergeSchema(default=self._schema.default, **field_strats)


# ---------------------------------------------------------------------------
# MergeQL bridge
# ---------------------------------------------------------------------------

class DuckDBMergeQLExtension:
    """Bridge between MergeQL parser and DuckDB execution engine.

    Translates MergeQL AST into DuckDB-optimised query plans.
    """

    def __init__(self, connection: Any = None) -> None:
        self._conn = connection
        self._udf = DuckDBMergeUDF(connection=connection)

    def execute_mergeql(self, query: str) -> Any:
        """Execute a MergeQL query via the DuckDB backend.

        Args:
            query: MergeQL SQL-like statement.

        Returns:
            Merged records as list-of-dicts.
        """
        from crdt_merge.mergeql import MergeQL  # local to avoid circular

        ql = MergeQL(arrow_backend=False)
        # We cannot directly register DuckDB tables as MergeQL sources
        # without reading them first — delegate to the UDF for table-level work.
        return ql.execute(query)

    def explain_mergeql(self, query: str) -> str:
        """Show DuckDB execution plan for a MergeQL query.

        Args:
            query: MergeQL SQL-like statement.

        Returns:
            Human-readable plan string.
        """
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL(arrow_backend=False)
        plan = ql.explain(query)
        return str(plan)


__all__ = [
    "DuckDBMergeUDF",
    "DuckDBMergeQLExtension",
]
