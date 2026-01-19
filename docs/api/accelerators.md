# Ecosystem Accelerators

8 accelerators: DuckDB UDF, dbt, DuckLake, Polars Plugin, Arrow Flight, Airbyte, SQLite, Streamlit.

## Quick Example

```python
from crdt_merge.accelerators.duckdb_udf import DuckDBMergeUDF
udf = DuckDBMergeUDF()
udf.register(connection)
```

---

## API Reference

## `crdt_merge.accelerators`

> crdt-merge Accelerators — ecosystem integrations for the modern data stack.

**Module:** `crdt_merge.accelerators`

### Classes

#### `AcceleratorProtocol(*args, **kwargs)`

Base protocol for all crdt-merge accelerators.

**Methods:**

- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Check whether external dependencies are available.

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Protocol()`

Base class for protocol classes.

### Functions

#### `get_accelerator(name: 'str') -> 'type'`

Get a registered accelerator class by name.

#### `list_accelerators() -> 'List[str]'`

List all registered accelerator names.

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.

#### `runtime_checkable(cls)`

Mark a protocol class as a runtime protocol.


## `crdt_merge.accelerators.airbyte`

> Airbyte Custom Destination Connector — write Airbyte streams through CRDT merge.

**Module:** `crdt_merge.accelerators.airbyte`

### Classes

#### `AirbyteMergeDestination(*, stream_configs: 'Optional[Dict[str, StreamConfig]]' = None, schema: 'Optional[Any]' = None, default_key: 'str' = 'id', default_strategy: 'str' = 'lww') -> 'None'`

Airbyte custom destination connector with CRDT merge semantics.

**Methods:**

- `check_connection(self, config: 'Dict[str, Any]') -> 'Tuple[bool, Optional[str]]'` — Validate the connection configuration.
- `clear_stream(self, stream_name: 'str') -> 'None'` — Clear all records in a stream.
- `configure_stream(self, stream_name: 'str', *, key_column: 'Optional[str]' = None, strategies: 'Optional[Dict[str, str]]' = None, default_strategy: 'Optional[str]' = None, timestamp_column: 'str' = '_ab_emitted_at', provenance_enabled: 'bool' = False) -> 'None'` — Configure merge settings for a specific stream.
- `get_spec(self) -> 'Dict[str, Any]'` — Return the Airbyte connector specification.
- `get_state(self) -> 'Dict[str, Any]'` — Return current connector state.
- `get_write_results(self) -> 'List[WriteResult]'` — Return all write results since initialisation.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Always available — no hard external deps.
- `list_streams(self) -> 'List[str]'` — Return names of all active streams.
- `read_stream(self, stream_name: 'str') -> 'List[Dict[str, Any]]'` — Read all merged records from a stream.
- `write(self, stream_name: 'str', records: 'List[Dict[str, Any]]', *, timestamp: 'Optional[float]' = None) -> 'WriteResult'` — Write records to a stream, merging with existing data.
- `write_messages(self, messages: 'Iterator[AirbyteMessage]') -> 'Iterator[AirbyteMessage]'` — Process a stream of Airbyte messages.

#### `AirbyteMessage(type: 'str', record: 'Optional[Dict[str, Any]]' = None, state: 'Optional[Dict[str, Any]]' = None, log: 'Optional[Dict[str, Any]]' = None, spec: 'Optional[Dict[str, Any]]' = None, connection_status: 'Optional[Dict[str, Any]]' = None) -> None`

Simplified Airbyte protocol message.

**Methods:**


#### `AirbyteRecordMessage(stream: 'str', data: 'Dict[str, Any]', emitted_at: 'float' = 0.0, namespace: 'Optional[str]' = None) -> None`

An individual Airbyte record.

**Methods:**


#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `StreamConfig(key_column: 'str', strategies: 'Dict[str, str]' = <factory>, default_strategy: 'str' = 'lww', timestamp_column: 'str' = '_ab_emitted_at', provenance_enabled: 'bool' = False) -> None`

Per-stream CRDT merge configuration.

**Methods:**

- `resolve_strategy_name(self, column: 'str') -> 'str'` — Return the strategy name for a given column.

#### `WriteResult(stream_name: 'str', records_written: 'int', records_merged: 'int', conflicts_resolved: 'int', merge_time_ms: 'float' = 0.0) -> None`

Result of a write operation.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — Serialise to plain dict.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.


## `crdt_merge.accelerators.dbt_package`

> dbt Package Generator — generate cross-database dbt macros for CRDT merge.

**Module:** `crdt_merge.accelerators.dbt_package`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `DbtMergeGenerator(*, warehouse: 'Optional[str]' = None) -> 'None'`

Generate dbt macros and models for CRDT merge operations.

**Methods:**

- `generate_macro(self, sources: 'List[str]', key: 'str', strategies: 'Dict[str, str]', *, timestamp_column: 'str' = '_merged_at', macro_name: 'Optional[str]' = None, separator: 'str' = ',', priority_lists: 'Optional[Dict[str, List[str]]]' = None) -> 'str'` — Generate a dbt Jinja macro for CRDT merge.
- `generate_model(self, model_name: 'str', sources: 'List[str]', key: 'str', strategies: 'Dict[str, str]', *, materialization: 'str' = 'table', timestamp_column: 'str' = '_merged_at') -> 'str'` — Generate a pre-built dbt model SQL file.
- `generate_packages_yml(self, *, package_name: 'str' = 'crdt_merge', version: 'Optional[str]' = None) -> 'str'` — Generate a dbt ``packages.yml`` snippet.
- `generate_resolver_macros(self) -> 'str'` — Generate the full set of resolver helper macros.
- `generate_schema_yml(self, model_name: 'str', key: 'str', strategies: 'Dict[str, str]', *, description: 'Optional[str]' = None) -> 'str'` — Generate a dbt ``schema.yml`` entry for a merge model.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — dbt macros have no runtime dependencies — always available.
- `list_supported_strategies(self) -> 'List[str]'` — Return list of supported strategy names.
- `list_supported_warehouses(self) -> 'List[str]'` — Return list of supported warehouse targets.

#### `MacroConfig(sources: 'List[str]', key: 'str', strategies: 'Dict[str, str]', timestamp_column: 'str' = '_merged_at', macro_name: 'Optional[str]' = None, warehouse: 'Optional[str]' = None, separator: 'str' = ',', priority_lists: 'Dict[str, List[str]]' = <factory>) -> None`

Configuration for a generated dbt macro.

**Methods:**


#### `ModelConfig(name: 'str', sources: 'List[str]', key: 'str', strategies: 'Dict[str, str]', materialization: 'str' = 'table', timestamp_column: 'str' = '_merged_at') -> None`

Configuration for a pre-built dbt model.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.


## `crdt_merge.accelerators.duckdb_udf`

> DuckDB UDF / MergeQL Extension — SQL-native CRDT merge inside DuckDB.

**Module:** `crdt_merge.accelerators.duckdb_udf`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Concat(separator: 'str' = ' | ', dedup: 'bool' = True)`

Concatenate both values with dedup. Sorted for commutativity.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Custom(fn: 'Callable')`

User-provided merge function.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `DuckDBMergeQLExtension(connection: 'Any' = None) -> 'None'`

Bridge between MergeQL parser and DuckDB execution engine.

**Methods:**

- `execute_mergeql(self, query: 'str') -> 'Any'` — Execute a MergeQL query via the DuckDB backend.
- `explain_mergeql(self, query: 'str') -> 'str'` — Show DuckDB execution plan for a MergeQL query.

#### `DuckDBMergeUDF(connection: 'Any' = None, schema: 'Optional[MergeSchema]' = None) -> 'None'`

DuckDB UDF that wraps crdt-merge operations.

**Methods:**

- `diff_tables(self, left: 'str', right: 'str', key: 'str') -> 'Dict[str, Any]'` — Compute diff between two DuckDB tables.
- `get_strategy_info(self, name: 'str') -> 'Dict[str, Any]'` — Return metadata about a built-in or custom strategy.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Return *True* if the ``duckdb`` package can be imported.
- `merge_results(self, left_result: 'Any', right_result: 'Any', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'List[dict]'` — Merge two DuckDB query results.
- `merge_tables(self, left: 'str', right: 'str', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'List[dict]'` — Merge two DuckDB tables and return list-of-dicts.
- `register(self) -> 'None'` — Register crdt_merge, crdt_diff and crdt_strategy as DuckDB UDFs.
- `register_strategy(self, name: 'str', func: 'Callable') -> 'None'` — Register a custom merge strategy as a DuckDB UDF callback.
- `unregister(self) -> 'None'` — Remove the UDF registrations (best-effort).

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LongestWins()`

Longer string wins. Equal length falls back to LWW.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MaxWins()`

Higher value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `MinWins()`

Lower value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Priority(levels: 'List[str]')`

Ranked priority — higher index in the priority list wins.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `UnionSet(separator: 'str' = ',')`

Merge separated values as a set union. Sorted for determinism.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

### Functions

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.


## `crdt_merge.accelerators.ducklake`

> DuckLake Semantic Conflict Layer — field-level conflict resolution for

**Module:** `crdt_merge.accelerators.ducklake`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `AuditEntry(key: 'Any', field: 'str', source: 'str', strategy: 'str', value: 'Any', alternative: 'Any' = None, timestamp: 'Optional[float]' = None) -> None`

Audit trail entry for a single record.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

#### `Branch(name: 'str', source_snapshot: 'str', data: 'List[dict]' = <factory>, created_at: 'Optional[float]' = None) -> None`

Represents a branch in the DuckLake snapshot tree.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

#### `DuckLakeConflictResolver(connection: 'Any' = None, schema: 'Optional[MergeSchema]' = None) -> 'None'`

Semantic conflict resolution for DuckLake snapshots.

**Methods:**

- `audit_trail(self, key: 'Optional[Any]' = None) -> 'List[Dict[str, Any]]'` — Get audit trail — which source won each field and why.
- `branch(self, snapshot: 'Any', branch_name: 'str') -> 'str'` — Create a branch from a snapshot.
- `clear_audit(self) -> 'None'` — Clear the audit trail.
- `detect_changes(self, snapshot_a: 'Any', snapshot_b: 'Any', key: 'str' = 'id') -> 'SnapshotDiff'` — Detect field-level changes between two snapshots using Merkle hashing.
- `get_branch_data(self, branch_name: 'str') -> 'List[dict]'` — Get the data from a branch.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Check whether DuckDB is available.
- `list_branches(self) -> 'List[Dict[str, Any]]'` — List all branches with metadata.
- `list_snapshots(self) -> 'List[str]'` — List registered snapshot names.
- `merge_branches(self, branch_a: 'str', branch_b: 'str', key: 'str' = 'id') -> 'MergeResult'` — Merge two branches with CRDT conflict resolution.
- `merge_snapshots(self, left: 'Any', right: 'Any', key: 'str' = 'id') -> 'MergeResult'` — Merge two snapshots with field-level CRDT resolution.
- `register_snapshot(self, name: 'str', data: 'Any') -> 'None'` — Register a named snapshot for later merge operations.
- `resolve_with_sql(self, query: 'str', key: 'str' = 'id') -> 'MergeResult'` — Execute a SQL query on the DuckDB connection and merge results.
- `update_branch(self, branch_name: 'str', data: 'List[dict]') -> 'None'` — Update a branch's data (simulates a write to the branch).

#### `FieldChange(key: 'Any', field: 'str', value_a: 'Any', value_b: 'Any', resolved_value: 'Optional[Any]' = None, strategy: 'Optional[str]' = None) -> None`

A single field-level change between two snapshots.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeResult(data: 'List[dict]', conflicts_resolved: 'int' = 0, merge_time_ms: 'float' = 0.0, rows_merged: 'int' = 0, rows_left_only: 'int' = 0, rows_right_only: 'int' = 0, field_changes: 'List[FieldChange]' = <factory>) -> None`

Result of a DuckLake snapshot merge.

**Properties:**

- `total_rows` — 

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `SnapshotDiff(added_keys: 'List[Any]' = <factory>, removed_keys: 'List[Any]' = <factory>, modified_fields: 'List[FieldChange]' = <factory>) -> None`

Diff between two snapshots at the field level.

**Properties:**

- `is_identical` — 
- `num_changes` — 

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — 

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.accelerators.flight_server`

> Arrow Flight Merge-as-a-Service — gRPC-based merge server.

**Module:** `crdt_merge.accelerators.flight_server`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Concat(separator: 'str' = ' | ', dedup: 'bool' = True)`

Concatenate both values with dedup. Sorted for commutativity.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Custom(fn: 'Callable')`

User-provided merge function.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `FlightMergeClient(location: 'str') -> 'None'`

Client for the Arrow Flight merge service.

**Methods:**

- `close(self) -> 'None'` — Close the client connection.
- `merge(self, left: 'Any', right: 'Any', key: 'str' = 'id', strategies: 'Optional[Dict[str, str]]' = None) -> 'Any'` — Send two tables to the merge server and receive merged result.

#### `FlightMergeServer(host: 'str' = '0.0.0.0', port: 'int' = 8815, default_schema: 'Optional[MergeSchema]' = None) -> 'None'`

Arrow Flight server for merge-as-a-service.

**Methods:**

- `do_exchange(self, context: 'Any', descriptor: 'Any', reader: 'Any', writer: 'Any') -> 'None'` — Handle DoExchange RPC — receive two streams, return merged stream.
- `do_get(self, context: 'Any', ticket: 'Any') -> 'Any'` — Handle DoGet — retrieve previously merged results.
- `do_merge(self, left: 'Any', right: 'Any', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'Tuple[Any, int]'` — Merge two Arrow tables (or list-of-dicts) directly.
- `health_check(self) -> 'Dict[str, Any]'` — 
- `is_available(self) -> 'bool'` — Return True if pyarrow.flight is importable.
- `list_flights(self, context: 'Any' = None, criteria: 'Any' = None) -> 'List[Dict[str, Any]]'` — List available merge endpoints.
- `serve(self) -> 'None'` — Start the Flight server (blocking).
- `start(self) -> 'None'` — Start the Flight server in a background thread.
- `stop(self) -> 'None'` — Stop the Flight server.

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LongestWins()`

Longer string wins. Equal length falls back to LWW.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MaxWins()`

Higher value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `MinWins()`

Lower value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Priority(levels: 'List[str]')`

Ranked priority — higher index in the priority list wins.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `UnionSet(separator: 'str' = ',')`

Merge separated values as a set union. Sorted for determinism.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

### Functions

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.


## `crdt_merge.accelerators.polars_plugin`

> Polars Expression Plugin — native Polars DataFrame CRDT merge.

**Module:** `crdt_merge.accelerators.polars_plugin`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `CRDTMergeExpression(field: 'str', strategy: 'MergeStrategy') -> 'None'`

Wrapper representing a CRDT merge expression for a single field.

**Properties:**

- `field` — The field name this expression targets.
- `strategy_name` — Name of the merge strategy.

**Methods:**

- `apply(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a single conflict using the embedded strategy.

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `PolarsCRDTMerge(schema: 'Optional[MergeSchema]' = None, timestamp_col: 'Optional[str]' = None) -> 'None'`

Polars expression plugin for CRDT merge operations.

**Methods:**

- `as_expression(self, field: 'str', strategy: 'str' = 'lww') -> 'CRDTMergeExpression'` — Return a CRDTMergeExpression for use in composable merge pipelines.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Check whether Polars is available.
- `merge(self, left: 'Any', right: 'Any', key: 'str' = 'id', strategies: 'Optional[Dict[str, str]]' = None, timestamp_col: 'Optional[str]' = None) -> 'PolarsMergeResult'` — Merge two Polars DataFrames with CRDT strategies.
- `merge_lazy(self, left: 'Any', right: 'Any', key: 'str' = 'id', strategies: 'Optional[Dict[str, str]]' = None, timestamp_col: 'Optional[str]' = None) -> 'PolarsMergeResult'` — Lazy merge — collects LazyFrames before merging.
- `register_namespace(self) -> 'None'` — Register ``crdt`` namespace on Polars DataFrames.

#### `PolarsMergeResult(data: 'Any', conflicts: 'int' = 0, merge_time_ms: 'float' = 0.0, rows_merged: 'int' = 0, rows_left_only: 'int' = 0, rows_right_only: 'int' = 0) -> 'None'`

Result of a Polars CRDT merge operation.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — Summary stats as dict.

### Functions

#### `crdt_merge_expr(field: 'str', strategy: 'str' = 'lww') -> 'CRDTMergeExpression'`

Create a standalone CRDT merge expression.


## `crdt_merge.accelerators.sqlite_ext`

> SQLite CRDT Extension — local-first / edge CRDT merge for SQLite.

**Module:** `crdt_merge.accelerators.sqlite_ext`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Concat(separator: 'str' = ' | ', dedup: 'bool' = True)`

Concatenate both values with dedup. Sorted for commutativity.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Custom(fn: 'Callable')`

User-provided merge function.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LongestWins()`

Longer string wins. Equal length falls back to LWW.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MaxWins()`

Higher value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `MinWins()`

Lower value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Priority(levels: 'List[str]')`

Ranked priority — higher index in the priority list wins.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `SQLiteCRDTMerge(db_path: 'str' = ':memory:', schema: 'Optional[MergeSchema]' = None) -> 'None'`

SQLite extension for CRDT merge operations.

**Properties:**

- `conn` — The underlying ``sqlite3.Connection``.

**Methods:**

- `close(self) -> 'None'` — Close the database connection.
- `compact(self, table: 'str') -> 'Dict[str, int]'` — Compact a CRDT table by removing orphaned clock entries.
- `create_crdt_table(self, name: 'str', columns: 'Dict[str, str]', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'None'` — Create a table with embedded CRDT merge metadata.
- `drop_crdt_table(self, name: 'str') -> 'None'` — Drop a CRDT-managed table and its metadata.
- `execute_sql(self, sql: 'str', params: 'tuple' = ()) -> 'List[Dict[str, Any]]'` — Execute raw SQL and return results as list of dicts.
- `get_clock(self, table: 'str', key_value: 'Any') -> 'Dict[str, int]'` — Get the vector clock for a specific record.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Check whether sqlite3 is available.
- `list_crdt_tables(self) -> 'List[str]'` — List all CRDT-managed tables.
- `merge_insert(self, table: 'str', records: 'List[Dict[str, Any]]', node_id: 'str' = 'local', timestamp: 'Optional[float]' = None) -> 'Dict[str, int]'` — Insert or merge records into a CRDT table.
- `merge_tables(self, left: 'str', right: 'str', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'List[dict]'` — Merge two SQLite tables with CRDT strategies.
- `read_table(self, table: 'str', include_meta: 'bool' = False) -> 'List[Dict[str, Any]]'` — Read all records from a CRDT table.
- `register(self) -> 'None'` — Register CRDT merge functions in SQLite.
- `sync_from(self, remote_db: 'str', tables: 'List[str]', node_id: 'str' = 'remote') -> 'Dict[str, int]'` — Sync and merge from a remote SQLite database.
- `table_info(self, name: 'str') -> 'Dict[str, Any]'` — Get info about a CRDT-managed table.
- `unregister(self) -> 'None'` — Mark CRDT functions as unregistered.

#### `UnionSet(separator: 'str' = ',')`

Merge separated values as a set union. Sorted for determinism.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

### Functions

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.


## `crdt_merge.accelerators.streamlit_ui`

> Streamlit Visual Merge UI — interactive conflict resolution component.

**Module:** `crdt_merge.accelerators.streamlit_ui`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Concat(separator: 'str' = ' | ', dedup: 'bool' = True)`

Concatenate both values with dedup. Sorted for commutativity.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Custom(fn: 'Callable')`

User-provided merge function.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LWW()`

Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `LongestWins()`

Longer string wins. Equal length falls back to LWW.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MaxWins()`

Higher value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `MergeSchema(default: 'Optional[MergeStrategy]' = None, **field_strategies: 'MergeStrategy')`

Declarative per-field strategy mapping.

**Properties:**

- `default` — 
- `fields` — 

**Methods:**

- `from_dict(d: 'dict') -> 'MergeSchema'` — Deserialize schema from dict.
- `resolve_row(self, row_a: 'dict', row_b: 'dict', timestamp_col: 'Optional[str]' = None, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'dict'` — Merge two rows using per-field strategies.
- `set_strategy(self, field: 'str', strategy: 'MergeStrategy') -> 'None'` — Set strategy for a specific field.
- `strategy_for(self, field: 'str') -> 'MergeStrategy'` — Get the strategy for a field, or the default.
- `to_dict(self) -> 'dict'` — Serialize schema to dict for storage/transmission.

#### `MergeStrategy()`

Base class for merge strategies. Subclass and implement resolve().

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — Resolve a conflict between two values. Must be commutative, associative, idempotent.

#### `MinWins()`

Lower value wins. Works with numbers and comparable types.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `Priority(levels: 'List[str]')`

Ranked priority — higher index in the priority list wins.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

#### `StreamlitMergeUI(schema: 'Optional[MergeSchema]' = None, title: 'str' = 'CRDT Merge Conflict Resolution') -> 'None'`

Streamlit component for visual merge conflict resolution.

**Methods:**

- `export_parquet(self, data: 'List[dict]', filename: 'str' = 'merged.parquet') -> 'None'` — Export merged results to downloadable Parquet file.
- `health_check(self) -> 'Dict[str, Any]'` — Return health / readiness status.
- `is_available(self) -> 'bool'` — Check whether streamlit is available.
- `render(self, left: 'Any', right: 'Any', key: 'str', strategies: 'Optional[Dict[str, str]]' = None) -> 'Optional[List[dict]]'` — Render the merge UI in Streamlit and return resolved data.
- `render_conflicts(self, conflicts: 'List[Dict[str, Any]]') -> 'None'` — Render a conflict heatmap visualization.
- `render_provenance(self, provenance: 'List[Dict[str, Any]]') -> 'None'` — Render provenance trail for merged records.

#### `UnionSet(separator: 'str' = ',')`

Merge separated values as a set union. Sorted for determinism.

**Methods:**

- `name(self) -> 'str'` — 
- `resolve(self, val_a: 'Any', val_b: 'Any', ts_a: 'float' = 0.0, ts_b: 'float' = 0.0, node_a: 'str' = 'a', node_b: 'str' = 'b') -> 'Any'` — 

### Functions

#### `register_accelerator(cls: 'type') -> 'type'`

Decorator to register an accelerator.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
