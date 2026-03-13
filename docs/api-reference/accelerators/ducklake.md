# Accelerator: ducklake

**Module**: `crdt_merge/accelerators/ducklake.py`
**Category**: Accelerator Integration

---

DuckLake integration combining DuckDB with data lake storage for CRDT merge operations on lakehouse data.


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class FieldChange`

A single field-level change between two snapshots.

**Attributes:**
- `key`: `Any`
- `field`: `str`
- `value_a`: `Any`
- `value_b`: `Any`
- `resolved_value`: `Optional[Any]`
- `strategy`: `Optional[str]`



### `FieldChange.to_dict(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class SnapshotDiff`

Diff between two snapshots at the field level.

**Attributes:**
- `added_keys`: `List[Any]`
- `removed_keys`: `List[Any]`
- `modified_fields`: `List[FieldChange]`



### `SnapshotDiff.is_identical(self) → bool`

*No docstring — needs documentation.*

**Returns:** `bool`



### `SnapshotDiff.num_changes(self) → int`

*No docstring — needs documentation.*

**Returns:** `int`



### `SnapshotDiff.to_dict(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class MergeResult`

Result of a DuckLake snapshot merge.

**Attributes:**
- `data`: `List[dict]`
- `conflicts_resolved`: `int`
- `merge_time_ms`: `float`
- `rows_merged`: `int`
- `rows_left_only`: `int`
- `rows_right_only`: `int`
- `field_changes`: `List[FieldChange]`



### `MergeResult.total_rows(self) → int`

*No docstring — needs documentation.*

**Returns:** `int`



### `MergeResult.to_dict(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class AuditEntry`

Audit trail entry for a single record.

**Attributes:**
- `key`: `Any`
- `field`: `str`
- `source`: `str`
- `strategy`: `str`
- `value`: `Any`
- `alternative`: `Any`
- `timestamp`: `Optional[float]`



### `AuditEntry.to_dict(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class Branch`

Represents a branch in the DuckLake snapshot tree.

**Attributes:**
- `name`: `str`
- `source_snapshot`: `str`
- `data`: `List[dict]`
- `created_at`: `Optional[float]`



### `Branch.to_dict(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class DuckLakeConflictResolver`

Semantic conflict resolution for DuckLake snapshots.

    Provides field-level conflict resolution with configurable strategies
    for DuckLake data snapshots, extending beyond transaction-level conflict
    handling.

    Operates on in-memory snapshots (list of dicts) with optional DuckDB
    connection for SQL-based queries on the resolved data.

    Args:
        connection: Optional DuckDB connection (lazy-imported).
        schema: MergeSchema defining per-field strategies.

    Example::

        resolver = DuckLakeConflictResolver(schema=MergeSchema(
            default=LWW(), salary=MaxWins()
        ))
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
    

**Attributes:**
- `name`: `str`
- `version`: `str`



### `DuckLakeConflictResolver.register_snapshot(self, name: str, data: Any) → None`

Register a named snapshot for later merge operations.

        Args:
            name: Snapshot identifier.
            data: List of dicts, or DuckDB table name (when connection provided).
        

**Parameters:**
- `name` (`str`)
- `data` (`Any`)

**Returns:** `None`

**Raises:** `TypeError(f'Expected list of dicts or DuckDB table name (str), got {type(data)}')`



### `DuckLakeConflictResolver.list_snapshots(self) → List[str]`

List registered snapshot names.

**Returns:** `List[str]`



### `DuckLakeConflictResolver.audit_trail(self, key: Optional[Any] = None) → List[Dict[str, Any]]`

Get audit trail — which source won each field and why.

        Args:
            key: Optional key to filter audit entries for a specific record.
                 If None, returns all audit entries.

        Returns:
            List of audit entry dicts.
        

**Parameters:**
- `key` (`Optional[Any]`)

**Returns:** `List[Dict[str, Any]]`



### `DuckLakeConflictResolver.clear_audit(self) → None`

Clear the audit trail.

**Returns:** `None`



### `DuckLakeConflictResolver.branch(self, snapshot: Any, branch_name: str) → str`

Create a branch from a snapshot.

        Args:
            snapshot: Source snapshot (list of dicts or registered name).
            branch_name: Name for the new branch.

        Returns:
            Branch name.
        

**Parameters:**
- `snapshot` (`Any`)
- `branch_name` (`str`)

**Returns:** `str`



### `DuckLakeConflictResolver.list_branches(self) → List[Dict[str, Any]]`

List all branches with metadata.

**Returns:** `List[Dict[str, Any]]`



### `DuckLakeConflictResolver.get_branch_data(self, branch_name: str) → List[dict]`

Get the data from a branch.

**Parameters:**
- `branch_name` (`str`)

**Returns:** `List[dict]`

**Raises:** `KeyError(f"Branch '{branch_name}' not found")`



### `DuckLakeConflictResolver.update_branch(self, branch_name: str, data: List[dict]) → None`

Update a branch's data (simulates a write to the branch).

**Parameters:**
- `branch_name` (`str`)
- `data` (`List[dict]`)

**Returns:** `None`

**Raises:** `KeyError(f"Branch '{branch_name}' not found")`



### `DuckLakeConflictResolver.health_check(self) → Dict[str, Any]`

Return health / readiness status.

**Returns:** `Dict[str, Any]`



### `DuckLakeConflictResolver.is_available(self) → bool`

Check whether DuckDB is available.

**Returns:** `bool`

