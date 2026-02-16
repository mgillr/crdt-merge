# `crdt_merge/accelerators/sqlite_ext.py`

> SQLite CRDT Extension — local-first / edge CRDT merge for SQLite.

Fills the vacuum left by cr-sqlite (archived July 2025). Registers CRDT merge
as SQLite custom functions and provides high-level helpers for creating merge
tables, inserting with automatic conflict resolution, and syncing between
dat

**Source:** `crdt_merge/accelerators/sqlite_ext.py` | **Lines:** 685

---

## Constants

- `_META_TABLE` = `'__crdt_meta__'`
- `_CLOCK_TABLE` = `'__crdt_clock__'`

## Classes

### `class SQLiteCRDTMerge`

SQLite extension for CRDT merge operations.

    Registers CRDT merge as SQLite custom functions, enabling local-first
    / edge data sync with conflict resolution.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.

- `name`: `str`
- `version`: `str`

**Methods:**

#### `SQLiteCRDTMerge.__init__(self, db_path: str = ':memory:', schema: Optional[MergeSchema] = None) → None`

Initialize SQLite CRDT extension.

        Args:
            db_path: Path to SQLite database or ``":memory:"``.
            schema: Default merge schema with per-field strategies.

#### `SQLiteCRDTMerge.conn(self) → Any`

The underlying ``sqlite3.Connection``.

#### `SQLiteCRDTMerge.close(self) → None`

Close the database connection.

#### `SQLiteCRDTMerge.register(self) → None`

Register CRDT merge functions in SQLite.

        After calling this method the following SQL functions become available:

        - ``crdt_lww(a, b, ts_a, ts_b)``
        - ``crdt_max(a, b)``
        - ``crdt_min(a, b)``
        - ``crdt_merge(a, b, strategy)``

#### `SQLiteCRDTMerge.unregister(self) → None`

Mark CRDT functions as unregistered.

        Note: SQLite does not support truly removing custom functions.
        This flag prevents further high-level operations.

#### `SQLiteCRDTMerge._ensure_meta_tables(self) → None`

Create internal metadata tables if they don't exist.

#### `SQLiteCRDTMerge._get_table_meta(self, table: str) → Optional[Dict[str, Any]]`

Get CRDT metadata for a table, or None.

#### `SQLiteCRDTMerge._increment_merge_count(self, table: str) → None`

Bump the merge counter for a table.

#### `SQLiteCRDTMerge.create_crdt_table(self, name: str, columns: Dict[str, str], key: str, strategies: Optional[Dict[str, str]] = None) → None`

Create a table with embedded CRDT merge metadata.

        Args:
            name: Table name.
            columns: Mapping of column name → SQLite type (e.g. ``{"salary": "REAL"}``).
                     The key column is added automatically as ``TEXT PRIMARY KEY``.
            key: Primary key column name.
            strategies: Per-field strategy names (e.g. ``{"salary": "max"}``).

#### `SQLiteCRDTMerge.drop_crdt_table(self, name: str) → None`

Drop a CRDT-managed table and its metadata.

        Args:
            name: Table name.

#### `SQLiteCRDTMerge.list_crdt_tables(self) → List[str]`

List all CRDT-managed tables.

        Returns:
            List of table names.

#### `SQLiteCRDTMerge.table_info(self, name: str) → Dict[str, Any]`

Get info about a CRDT-managed table.

        Args:
            name: Table name.

        Returns:
            Dict with ``key_column``, ``strategies``, ``row_count``, ``merge_count``.

        Raises:
            ValueError: If table is not CRDT-managed.

#### `SQLiteCRDTMerge.merge_insert(self, table: str, records: List[Dict[str, Any]], node_id: str = 'local', timestamp: Optional[float] = None) → Dict[str, int]`

Insert or merge records into a CRDT table.

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

#### `SQLiteCRDTMerge.read_table(self, table: str, include_meta: bool = False) → List[Dict[str, Any]]`

Read all records from a CRDT table.

        Args:
            table: Table name.
            include_meta: If True, include ``_crdt_ts`` and ``_crdt_node``.

        Returns:
            List of dicts.

#### `SQLiteCRDTMerge.merge_tables(self, left: str, right: str, key: str, strategies: Optional[Dict[str, str]] = None) → List[dict]`

Merge two SQLite tables with CRDT strategies.

        Args:
            left: Left table name.
            right: Right table name.
            key: Join key column.
            strategies: Per-field strategy overrides.

        Returns:
            List of merged records as dicts.

#### `SQLiteCRDTMerge._read_raw_table(self, table: str) → List[Dict[str, Any]]`

Read all rows from an arbitrary table as dicts.

#### `SQLiteCRDTMerge.sync_from(self, remote_db: str, tables: List[str], node_id: str = 'remote') → Dict[str, int]`

Sync and merge from a remote SQLite database.

        Opens the remote database read-only, reads the specified tables,
        and merge-inserts into the local database.

        Args:
            remote_db: Path to remote SQLite database.
            tables: List of table names to sync.
            node_id: Node id for the remote source.

        Returns:
            Dict mapping table name → number of records merged.

#### `SQLiteCRDTMerge.execute_sql(self, sql: str, params: tuple = ()) → List[Dict[str, Any]]`

Execute raw SQL and return results as list of dicts.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            List of row dicts.

#### `SQLiteCRDTMerge.get_clock(self, table: str, key_value: Any) → Dict[str, int]`

Get the vector clock for a specific record.

        Args:
            table: Table name.
            key_value: Record key.

        Returns:
            Dict mapping node_id → clock value.

#### `SQLiteCRDTMerge.compact(self, table: str) → Dict[str, int]`

Compact a CRDT table by removing orphaned clock entries.

        Args:
            table: Table name.

        Returns:
            Dict with ``clock_entries_removed``.

#### `SQLiteCRDTMerge.health_check(self) → Dict[str, Any]`

Return health / readiness status.

        Returns:
            Dict with ``status``, ``sqlite_available``, database info.

#### `SQLiteCRDTMerge.is_available(self) → bool`

Check whether sqlite3 is available.

#### `SQLiteCRDTMerge.__repr__(self) → str`

*No docstring*

#### `SQLiteCRDTMerge.__del__(self) → None`

*No docstring*


## Functions

### `_resolve_strategy(name: str) → MergeStrategy`

Instantiate a strategy from its name.

### `_get_sqlite3() → Any`

Lazy import of sqlite3.

