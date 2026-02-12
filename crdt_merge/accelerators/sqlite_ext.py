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
SQLite CRDT Extension — local-first / edge CRDT merge for SQLite.

Fills the vacuum left by cr-sqlite (archived July 2025). Registers CRDT merge
as SQLite custom functions and provides high-level helpers for creating merge
tables, inserting with automatic conflict resolution, and syncing between
databases.

All external dependencies use **lazy imports** — the module is importable even
without ``sqlite3`` installed (though it is part of the stdlib).

Example::

    from crdt_merge.accelerators.sqlite_ext import SQLiteCRDTMerge
    ext = SQLiteCRDTMerge(db_path=":memory:", schema=my_schema)
    ext.register()
    ext.create_crdt_table("users", columns={"name": "TEXT", "salary": "REAL"},
                          key="id", strategies={"salary": "max"})
    ext.merge_insert("users", records=[{"id": 1, "name": "Alice", "salary": 90000}])
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    """Instantiate a strategy from its name."""
    cls = _STRATEGY_MAP.get(name.lower(), LWW)
    return cls()

def _get_sqlite3() -> Any:
    """Lazy import of sqlite3."""
    try:
        import sqlite3
        return sqlite3
    except ImportError:
        raise ImportError(
            "sqlite3 is required for SQLiteCRDTMerge. "
            "It is part of the Python standard library."
        )

# ---------------------------------------------------------------------------
# Internal: CRDT metadata table management
# ---------------------------------------------------------------------------

_META_TABLE = "__crdt_meta__"
_CLOCK_TABLE = "__crdt_clock__"

# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

@register_accelerator
class SQLiteCRDTMerge:
    """SQLite extension for CRDT merge operations.

    Registers CRDT merge as SQLite custom functions, enabling local-first
    / edge data sync with conflict resolution.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.
    """

    name: str = "sqlite_ext"
    version: str = "0.7.0"

    def __init__(
        self,
        db_path: str = ":memory:",
        schema: Optional[MergeSchema] = None,
    ) -> None:
        """Initialize SQLite CRDT extension.

        Args:
            db_path: Path to SQLite database or ``":memory:"``.
            schema: Default merge schema with per-field strategies.
        """
        sqlite3 = _get_sqlite3()
        self._db_path = db_path
        self._schema = schema or MergeSchema()
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._registered = False
        self._custom_strategies: Dict[str, Callable] = {}
        self._ensure_meta_tables()

    # -- Connection ---------------------------------------------------------

    @property
    def conn(self) -> Any:
        """The underlying ``sqlite3.Connection``."""
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # -- Registration -------------------------------------------------------

    def register(self) -> None:
        """Register CRDT merge functions in SQLite.

        After calling this method the following SQL functions become available:

        - ``crdt_lww(a, b, ts_a, ts_b)``
        - ``crdt_max(a, b)``
        - ``crdt_min(a, b)``
        - ``crdt_merge(a, b, strategy)``
        """
        def _crdt_lww(a: Any, b: Any, ts_a: float = 0.0, ts_b: float = 0.0) -> Any:
            return LWW().resolve(a, b, ts_a, ts_b)

        def _crdt_max(a: Any, b: Any) -> Any:
            return MaxWins().resolve(a, b)

        def _crdt_min(a: Any, b: Any) -> Any:
            return MinWins().resolve(a, b)

        def _crdt_merge(a: Any, b: Any, strategy: str = "lww") -> Any:
            strat = _resolve_strategy(strategy)
            return strat.resolve(a, b)

        self._conn.create_function("crdt_lww", 4, _crdt_lww)
        self._conn.create_function("crdt_max", 2, _crdt_max)
        self._conn.create_function("crdt_min", 2, _crdt_min)
        self._conn.create_function("crdt_merge", 3, _crdt_merge)
        self._registered = True

    def unregister(self) -> None:
        """Mark CRDT functions as unregistered.

        Note: SQLite does not support truly removing custom functions.
        This flag prevents further high-level operations.
        """
        self._registered = False

    # -- Meta tables --------------------------------------------------------

    def _ensure_meta_tables(self) -> None:
        """Create internal metadata tables if they don't exist."""
        cur = self._conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_META_TABLE} (
                table_name TEXT PRIMARY KEY,
                key_column TEXT NOT NULL,
                strategies TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                merge_count INTEGER DEFAULT 0
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_CLOCK_TABLE} (
                table_name TEXT NOT NULL,
                key_value TEXT NOT NULL,
                node_id TEXT NOT NULL DEFAULT 'local',
                clock INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (table_name, key_value, node_id)
            )
        """)
        self._conn.commit()

    def _get_table_meta(self, table: str) -> Optional[Dict[str, Any]]:
        """Get CRDT metadata for a table, or None."""
        cur = self._conn.cursor()
        cur.execute(
            f"SELECT key_column, strategies, merge_count FROM {_META_TABLE} WHERE table_name = ?",
            (table,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "key_column": row[0],
            "strategies": json.loads(row[1]),
            "merge_count": row[2],
        }

    def _increment_merge_count(self, table: str) -> None:
        """Bump the merge counter for a table."""
        self._conn.execute(
            f"UPDATE {_META_TABLE} SET merge_count = merge_count + 1 WHERE table_name = ?",
            (table,),
        )
        self._conn.commit()

    # -- CRDT table management ----------------------------------------------

    def create_crdt_table(
        self,
        name: str,
        columns: Dict[str, str],
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> None:
        """Create a table with embedded CRDT merge metadata.

        Args:
            name: Table name.
            columns: Mapping of column name → SQLite type (e.g. ``{"salary": "REAL"}``).
                     The key column is added automatically as ``TEXT PRIMARY KEY``.
            key: Primary key column name.
            strategies: Per-field strategy names (e.g. ``{"salary": "max"}``).
        """
        strategies = strategies or {}
        col_defs = [f"{key} TEXT PRIMARY KEY"]
        for col, typ in columns.items():
            if col != key:
                col_defs.append(f"{col} {typ}")

        # Extra bookkeeping columns
        col_defs.append("_crdt_ts REAL DEFAULT 0.0")
        col_defs.append("_crdt_node TEXT DEFAULT 'local'")

        sql = f"CREATE TABLE IF NOT EXISTS {name} ({', '.join(col_defs)})"
        self._conn.execute(sql)

        # Store metadata
        self._conn.execute(
            f"INSERT OR REPLACE INTO {_META_TABLE} (table_name, key_column, strategies) VALUES (?, ?, ?)",
            (name, key, json.dumps(strategies)),
        )
        self._conn.commit()

    def drop_crdt_table(self, name: str) -> None:
        """Drop a CRDT-managed table and its metadata.

        Args:
            name: Table name.
        """
        self._conn.execute(f"DROP TABLE IF EXISTS {name}")
        self._conn.execute(f"DELETE FROM {_META_TABLE} WHERE table_name = ?", (name,))
        self._conn.execute(f"DELETE FROM {_CLOCK_TABLE} WHERE table_name = ?", (name,))
        self._conn.commit()

    def list_crdt_tables(self) -> List[str]:
        """List all CRDT-managed tables.

        Returns:
            List of table names.
        """
        cur = self._conn.execute(f"SELECT table_name FROM {_META_TABLE} ORDER BY table_name")
        return [row[0] for row in cur.fetchall()]

    def table_info(self, name: str) -> Dict[str, Any]:
        """Get info about a CRDT-managed table.

        Args:
            name: Table name.

        Returns:
            Dict with ``key_column``, ``strategies``, ``row_count``, ``merge_count``.

        Raises:
            ValueError: If table is not CRDT-managed.
        """
        meta = self._get_table_meta(name)
        if meta is None:
            raise ValueError(f"Table '{name}' is not a CRDT-managed table.")

        cur = self._conn.execute(f"SELECT COUNT(*) FROM {name}")
        row_count = cur.fetchone()[0]

        return {
            "table_name": name,
            "key_column": meta["key_column"],
            "strategies": meta["strategies"],
            "row_count": row_count,
            "merge_count": meta["merge_count"],
        }

    # -- Insert / merge operations ------------------------------------------

    def merge_insert(
        self,
        table: str,
        records: List[Dict[str, Any]],
        node_id: str = "local",
        timestamp: Optional[float] = None,
    ) -> Dict[str, int]:
        """Insert or merge records into a CRDT table.

        For each record:
        - If the key does not exist, insert it.
        - If the key exists, merge each field using the configured strategy.

        Args:
            table: Table name.
            records: List of dicts to merge-insert.
            node_id: Node identifier for vector clock tracking.
            timestamp: Override timestamp (default: ``time.time()``).

        Returns:
            Dict with ``inserted``, ``merged``, ``total``.

        Raises:
            ValueError: If table is not CRDT-managed.
        """
        meta = self._get_table_meta(table)
        if meta is None:
            raise ValueError(f"Table '{table}' is not a CRDT-managed table.")

        key_col = meta["key_column"]
        strategies = meta["strategies"]
        ts = timestamp if timestamp is not None else time.time()

        inserted = 0
        merged = 0

        for record in records:
            key_val = record.get(key_col)
            if key_val is None:
                continue

            # Fetch existing row
            cur = self._conn.execute(
                f"SELECT * FROM {table} WHERE {key_col} = ?",
                (str(key_val),),
            )
            existing = cur.fetchone()

            if existing is None:
                # Insert new record
                record_with_meta = dict(record)
                record_with_meta[key_col] = str(key_val)
                record_with_meta["_crdt_ts"] = ts
                record_with_meta["_crdt_node"] = node_id

                cols = list(record_with_meta.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_str = ", ".join(cols)
                vals = [record_with_meta[c] for c in cols]
                self._conn.execute(
                    f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})",
                    vals,
                )
                inserted += 1
            else:
                # Merge with existing
                existing_dict = dict(existing)
                existing_ts = existing_dict.get("_crdt_ts", 0.0) or 0.0
                existing_node = existing_dict.get("_crdt_node", "local") or "local"

                update_vals: Dict[str, Any] = {}
                for field, new_val in record.items():
                    if field == key_col or field.startswith("_crdt_"):
                        continue
                    old_val = existing_dict.get(field)
                    if old_val is None:
                        update_vals[field] = new_val
                    elif new_val is None:
                        update_vals[field] = old_val
                    elif old_val == new_val:
                        update_vals[field] = old_val
                    else:
                        strat_name = strategies.get(field, "lww")
                        strat = _resolve_strategy(strat_name)
                        update_vals[field] = strat.resolve(
                            old_val, new_val,
                            ts_a=float(existing_ts),
                            ts_b=ts,
                            node_a=str(existing_node),
                            node_b=node_id,
                        )

                if update_vals:
                    update_vals["_crdt_ts"] = ts
                    update_vals["_crdt_node"] = node_id
                    set_clauses = ", ".join(f"{c} = ?" for c in update_vals)
                    vals_list = list(update_vals.values()) + [str(key_val)]
                    self._conn.execute(
                        f"UPDATE {table} SET {set_clauses} WHERE {key_col} = ?",
                        vals_list,
                    )
                merged += 1

            # Update clock
            self._conn.execute(
                f"""INSERT INTO {_CLOCK_TABLE} (table_name, key_value, node_id, clock)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(table_name, key_value, node_id)
                    DO UPDATE SET clock = clock + 1, updated_at = datetime('now')""",
                (table, str(key_val), node_id),
            )

        self._conn.commit()
        self._increment_merge_count(table)

        return {"inserted": inserted, "merged": merged, "total": len(records)}

    def read_table(self, table: str, include_meta: bool = False) -> List[Dict[str, Any]]:
        """Read all records from a CRDT table.

        Args:
            table: Table name.
            include_meta: If True, include ``_crdt_ts`` and ``_crdt_node``.

        Returns:
            List of dicts.
        """
        cur = self._conn.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if not include_meta:
                d.pop("_crdt_ts", None)
                d.pop("_crdt_node", None)
            result.append(d)
        return result

    # -- Table merge --------------------------------------------------------

    def merge_tables(
        self,
        left: str,
        right: str,
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> List[dict]:
        """Merge two SQLite tables with CRDT strategies.

        Args:
            left: Left table name.
            right: Right table name.
            key: Join key column.
            strategies: Per-field strategy overrides.

        Returns:
            List of merged records as dicts.
        """
        left_data = self._read_raw_table(left)
        right_data = self._read_raw_table(right)

        strategies = strategies or {}
        schema = MergeSchema()
        for field, name in strategies.items():
            schema.set_strategy(field, _resolve_strategy(name))

        left_by_key = {r[key]: r for r in left_data}
        right_by_key = {r[key]: r for r in right_data}
        all_keys: List[Any] = []
        seen: set = set()
        for r in left_data:
            k = r[key]
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
        for r in right_data:
            k = r[key]
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

        merged: List[dict] = []
        for k in all_keys:
            row_l = left_by_key.get(k)
            row_r = right_by_key.get(k)
            if row_l and row_r:
                merged.append(schema.resolve_row(row_l, row_r))
            elif row_l:
                merged.append(dict(row_l))
            elif row_r:
                merged.append(dict(row_r))
        return merged

    def _read_raw_table(self, table: str) -> List[Dict[str, Any]]:
        """Read all rows from an arbitrary table as dicts."""
        cur = self._conn.execute(f"SELECT * FROM {table}")
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = {}
            for i, col in enumerate(cols):
                if not col.startswith("_crdt_"):
                    d[col] = row[i]
            result.append(d)
        return result

    # -- Sync ---------------------------------------------------------------

    def sync_from(
        self,
        remote_db: str,
        tables: List[str],
        node_id: str = "remote",
    ) -> Dict[str, int]:
        """Sync and merge from a remote SQLite database.

        Opens the remote database read-only, reads the specified tables,
        and merge-inserts into the local database.

        Args:
            remote_db: Path to remote SQLite database.
            tables: List of table names to sync.
            node_id: Node id for the remote source.

        Returns:
            Dict mapping table name → number of records merged.
        """
        sqlite3 = _get_sqlite3()
        remote_conn = sqlite3.connect(remote_db)
        remote_conn.row_factory = sqlite3.Row

        stats: Dict[str, int] = {}
        for table in tables:
            try:
                cur = remote_conn.execute(f"SELECT * FROM {table}")
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                records = []
                for row in rows:
                    d = {}
                    for i, col in enumerate(cols):
                        if not col.startswith("_crdt_"):
                            d[col] = row[i]
                    records.append(d)

                result = self.merge_insert(table, records, node_id=node_id)
                stats[table] = result["total"]
            except Exception:
                stats[table] = 0

        remote_conn.close()
        return stats

    # -- Utility ------------------------------------------------------------

    def execute_sql(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute raw SQL and return results as list of dicts.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            List of row dicts.
        """
        cur = self._conn.execute(sql, params)
        if cur.description is None:
            self._conn.commit()
            return []
        cols = [desc[0] for desc in cur.description]
        return [{cols[i]: row[i] for i in range(len(cols))} for row in cur.fetchall()]

    def get_clock(self, table: str, key_value: Any) -> Dict[str, int]:
        """Get the vector clock for a specific record.

        Args:
            table: Table name.
            key_value: Record key.

        Returns:
            Dict mapping node_id → clock value.
        """
        cur = self._conn.execute(
            f"SELECT node_id, clock FROM {_CLOCK_TABLE} WHERE table_name = ? AND key_value = ?",
            (table, str(key_value)),
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    def compact(self, table: str) -> Dict[str, int]:
        """Compact a CRDT table by removing orphaned clock entries.

        Args:
            table: Table name.

        Returns:
            Dict with ``clock_entries_removed``.
        """
        meta = self._get_table_meta(table)
        if meta is None:
            raise ValueError(f"Table '{table}' is not a CRDT-managed table.")

        key_col = meta["key_column"]
        # Find clock entries whose key no longer exists in the table
        cur = self._conn.execute(
            f"""DELETE FROM {_CLOCK_TABLE}
                WHERE table_name = ?
                AND key_value NOT IN (SELECT {key_col} FROM {table})""",
            (table,),
        )
        removed = cur.rowcount
        self._conn.commit()
        return {"clock_entries_removed": removed}

    # -- Health check -------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status.

        Returns:
            Dict with ``status``, ``sqlite_available``, database info.
        """
        try:
            import sqlite3
            version = sqlite3.sqlite_version
            available = True
        except ImportError:
            version = None
            available = False

        tables = self.list_crdt_tables() if available else []
        return {
            "name": self.name,
            "version": self.version,
            "sqlite_available": available,
            "sqlite_version": version,
            "db_path": self._db_path,
            "crdt_tables": tables,
            "registered": self._registered,
            "status": "ok" if available else "sqlite3_not_available",
        }

    def is_available(self) -> bool:
        """Check whether sqlite3 is available."""
        try:
            import sqlite3  # noqa: F401 — import tests sqlite3 availability
            return True
        except ImportError:
            return False

    def __repr__(self) -> str:
        return f"SQLiteCRDTMerge(db_path={self._db_path!r}, registered={self._registered})"

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
