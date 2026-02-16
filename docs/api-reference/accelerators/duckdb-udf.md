# `crdt_merge/accelerators/duckdb_udf.py`

> DuckDB UDF / MergeQL Extension — SQL-native CRDT merge inside DuckDB.

Registers crdt_merge(), crdt_diff(), and crdt_strategy() as DuckDB UDFs so
users can run conflict-free merge operations directly from SQL:

    SELECT * FROM crdt_merge('table_a', 'table_b', key:='id', strategy:='lww')

All exter

**Source:** `crdt_merge/accelerators/duckdb_udf.py` | **Lines:** 391

---

**Exports (`__all__`):** `['DuckDBMergeUDF', 'DuckDBMergeQLExtension']`

## Classes

### `class DuckDBMergeUDF`

DuckDB UDF that wraps crdt-merge operations.

    Registers CRDT merge as DuckDB functions enabling SQL-native conflict
    resolution inside DuckDB queries.

    Attributes:
        name: Accelerator name for the registry.
        version: Accelerator version string.

- `name`: `str`
- `version`: `str`

**Methods:**

#### `DuckDBMergeUDF.__init__(self, connection: Any = None, schema: Optional[MergeSchema] = None) → None`

Initialise a DuckDB merge UDF wrapper.

        Args:
            connection: A ``duckdb.DuckDBPyConnection``. If *None* a new
                in-memory connection is created (requires ``duckdb``).
            schema: Default ``MergeSchema`` used when no per-field strategy
                is specified in the SQL call.

#### `DuckDBMergeUDF.is_available(self) → bool`

Return *True* if the ``duckdb`` package can be imported.

#### `DuckDBMergeUDF._ensure_conn(self) → Any`

Return the connection, creating one if needed.

#### `DuckDBMergeUDF.register(self) → None`

Register crdt_merge, crdt_diff and crdt_strategy as DuckDB UDFs.

#### `DuckDBMergeUDF.unregister(self) → None`

Remove the UDF registrations (best-effort).

#### `DuckDBMergeUDF.merge_tables(self, left: str, right: str, key: str, strategies: Optional[Dict[str, str]] = None) → List[dict]`

Merge two DuckDB tables and return list-of-dicts.

        Args:
            left: Name of the left table.
            right: Name of the right table.
            key: Join key column.
            strategies: Optional per-field strategy map.

        Returns:
            Merged records as ``list[dict]``.

#### `DuckDBMergeUDF.diff_tables(self, left: str, right: str, key: str) → Dict[str, Any]`

Compute diff between two DuckDB tables.

        Args:
            left: Name of the left table.
            right: Name of the right table.
            key: Join key column.

        Returns:
            Diff dict with added, removed, modified, unchanged_count.

#### `DuckDBMergeUDF.merge_results(self, left_result: Any, right_result: Any, key: str, strategies: Optional[Dict[str, str]] = None) → List[dict]`

Merge two DuckDB query results.

        Args:
            left_result: Result from ``conn.sql()``.
            right_result: Result from ``conn.sql()``.
            key: Join key column.
            strategies: Optional per-field strategy map.

        Returns:
            Merged records.

#### `DuckDBMergeUDF.register_strategy(self, name: str, func: Callable) → None`

Register a custom merge strategy as a DuckDB UDF callback.

        Args:
            name: Strategy name.
            func: Callable with the standard 6-param resolve signature.

#### `DuckDBMergeUDF.get_strategy_info(self, name: str) → Dict[str, Any]`

Return metadata about a built-in or custom strategy.

        Args:
            name: Strategy name (case-insensitive).

        Returns:
            Dict with strategy metadata.

#### `DuckDBMergeUDF.health_check(self) → Dict[str, Any]`

Return health / readiness status.

#### `DuckDBMergeUDF._build_schema(self, strategies: Optional[Dict[str, str]] = None) → MergeSchema`

Build a MergeSchema from a strategy dict, falling back to default.


### `class DuckDBMergeQLExtension`

Bridge between MergeQL parser and DuckDB execution engine.

    Translates MergeQL AST into DuckDB-optimised query plans.


**Methods:**

#### `DuckDBMergeQLExtension.__init__(self, connection: Any = None) → None`

*No docstring*

#### `DuckDBMergeQLExtension.execute_mergeql(self, query: str) → Any`

Execute a MergeQL query via the DuckDB backend.

        Args:
            query: MergeQL SQL-like statement.

        Returns:
            Merged records as list-of-dicts.

#### `DuckDBMergeQLExtension.explain_mergeql(self, query: str) → str`

Show DuckDB execution plan for a MergeQL query.

        Args:
            query: MergeQL SQL-like statement.

        Returns:
            Human-readable plan string.


## Functions

### `_resolve_strategy(name: str) → MergeStrategy`

Return a strategy instance by lowercase name.

### `_records_from_relation(rel: Any) → List[dict]`

Convert a DuckDB relation / result to list-of-dicts.

### `_merge_records(left: List[dict], right: List[dict], key: str, schema: MergeSchema) → Tuple[List[dict], int]`

Merge two lists of dicts using *schema*, return (merged, conflict_count).

### `_diff_records(left: List[dict], right: List[dict], key: str) → Dict[str, Any]`

Compute diff between two record lists.

