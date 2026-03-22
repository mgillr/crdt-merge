# crdt_merge.audit — Immutable Audit Log with Hash Chaining

> **Module**: `crdt_merge/audit.py` | **Layer**: 5 — Enterprise | **Version**: 0.9.4

---

## Overview

Provides a tamper-evident, append-only audit log for merge operations using SHA-256 hash chains. Each entry links to the previous via its hash, forming a verifiable chain similar to a blockchain. The module includes `AuditEntry` (a frozen dataclass for individual log records), `AuditLog` (the append-only log with chain verification and filtering), and `AuditedMerge` (a convenience wrapper that calls `crdt_merge.merge()` and automatically records every invocation).

---

## Quick Start

```python
from crdt_merge.audit import AuditLog, AuditedMerge

# Create an audit log and perform an audited merge
audited = AuditedMerge(node_id="edge-1")

left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
right = [{"id": 1, "name": "Alicia"}, {"id": 3, "name": "Carol"}]

result, entry = audited.merge(left, right, key="id")
print(f"Merged {len(result)} records, audit entry: {entry.entry_id}")
print(f"Chain valid: {audited.audit_log.verify_chain()}")
```

---

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `_GENESIS_HASH` | `"genesis"` | Sentinel `prev_hash` value for the first entry in a chain. |
| `_VALID_OPERATIONS` | `frozenset({"merge", "encrypt", "decrypt", "unmerge", "key_rotate", "custom"})` | Recognised operation labels. |

---

## Module-Level Functions

### `_hash_data(data: Any) → str`

Compute SHA-256 hex digest of JSON-serialized data.

**Parameters:**
- `data` (`Any`): Data to hash. Serialized via `json.dumps(data, sort_keys=True, default=str)`.

**Returns:** `str` — SHA-256 hex digest string.

---

### `_compute_entry_hash(entry_id, timestamp, operation, node_id, input_hash, output_hash, prev_hash) → str`

Deterministic hash over all identity fields of an entry.

**Parameters:**
- `entry_id` (`str`): Unique entry identifier.
- `timestamp` (`float`): Wall-clock time.
- `operation` (`str`): Operation type.
- `node_id` (`str`): Node identifier.
- `input_hash` (`str`): SHA-256 digest of input data.
- `output_hash` (`str`): SHA-256 digest of output data.
- `prev_hash` (`str`): Hash of the preceding entry.

**Returns:** `str` — SHA-256 hex digest of the concatenated payload string `"{entry_id}:{timestamp}:{operation}:{node_id}:{input_hash}:{output_hash}:{prev_hash}"`.

---

## Classes

### `AuditEntry`

Single immutable audit log entry with cryptographic chain link. This is a **frozen dataclass** — instances cannot be modified after creation.

```python
@dataclass(frozen=True)
class AuditEntry:
    entry_id: str
    timestamp: float
    operation: str
    node_id: str
    input_hash: str
    output_hash: str
    metadata: Dict[str, Any]
    prev_hash: str
    entry_hash: str
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `entry_id` | `str` | Unique identifier (UUID4). |
| `timestamp` | `float` | Wall-clock time when the entry was created. |
| `operation` | `str` | Type of operation recorded (e.g. `"merge"`, `"encrypt"`). |
| `node_id` | `str` | Identifier of the node that performed the operation. |
| `input_hash` | `str` | SHA-256 digest of the operation's input data. |
| `output_hash` | `str` | SHA-256 digest of the operation's output data. |
| `metadata` | `Dict[str, Any]` | Arbitrary operation-specific details. |
| `prev_hash` | `str` | Hash of the preceding entry (`"genesis"` for the first). |
| `entry_hash` | `str` | SHA-256 digest computed over all identity fields. |

**Methods:**

#### `to_dict() → Dict[str, Any]`

Return a JSON-serialisable dictionary representation.

**Returns:** `Dict[str, Any]` — Dictionary with all fields.

**Example:**
```python
entry_data = entry.to_dict()
import json
print(json.dumps(entry_data, indent=2))
```

---

#### `from_dict(d: Dict[str, Any]) → AuditEntry` *(classmethod)*

Reconstruct an `AuditEntry` from a dictionary.

**Parameters:**
- `d` (`Dict[str, Any]`): Dictionary containing all entry fields.

**Returns:** `AuditEntry` — Reconstructed entry instance.

---

#### `verify() → bool`

Check that `entry_hash` matches the recomputed hash over all identity fields.

**Returns:** `bool` — `True` if the hash is valid.

**Example:**
```python
assert entry.verify(), "Entry hash tampered!"
```

---

### `AuditLog`

Append-only audit log with SHA-256 hash chaining. Each entry's `prev_hash` references the `entry_hash` of the preceding entry. The first entry uses the sentinel value `"genesis"` as its `prev_hash`.

```python
class AuditLog:
    def __init__(self, node_id: str = "default") -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `node_id` | `str` | `"default"` | Default node identifier stamped on new entries. |

**Properties:**

| Name | Type | Description |
|------|------|-------------|
| `entries` | `List[AuditEntry]` | Shallow copy of the entry list. |
| `node_id` | `str` | The node identifier for this log. |

**Supports:** `len()`, `iter()`, `repr()`.

**Methods:**

#### `log_merge(left_records, right_records, result_records, schema=None, **kwargs) → AuditEntry`

Record a merge operation. Computes input and output hashes from the provided data and stores merge-specific metadata (record counts, schema info).

**Parameters:**
- `left_records` (`Any`): Left dataset.
- `right_records` (`Any`): Right dataset.
- `result_records` (`Any`): Merged result.
- `schema` (`Any`, optional): Optional merge schema (serialized to metadata).
- `**kwargs` (`Any`): Additional metadata key/value pairs.

**Returns:** `AuditEntry` — The newly created entry.

**Example:**
```python
log = AuditLog(node_id="node-1")

left = [{"id": 1, "val": "a"}]
right = [{"id": 1, "val": "b"}]
result = [{"id": 1, "val": "b"}]

entry = log.log_merge(left, right, result)
print(f"Logged merge: {entry.entry_id}")
print(f"Metadata: {entry.metadata}")
# Metadata includes: left_count, right_count, result_count
```

---

#### `log_operation(operation, input_data=None, output_data=None, **metadata) → AuditEntry`

Record an arbitrary named operation.

**Parameters:**
- `operation` (`str`): Label such as `"encrypt"`, `"decrypt"`, `"unmerge"`, etc.
- `input_data` (`Any`, optional): Input payload (hashed, not stored).
- `output_data` (`Any`, optional): Output payload (hashed, not stored).
- `**metadata` (`Any`): Additional key/value pairs stored on the entry.

**Returns:** `AuditEntry` — The newly created entry.

**Example:**
```python
entry = log.log_operation("encrypt", input_data={"field": "ssn"}, encrypted=True)
```

---

#### `verify_chain() → bool`

Verify the integrity of the entire hash chain. Returns `True` when the log is empty, or when every entry's `entry_hash` is correctly computed and every entry's `prev_hash` matches the previous entry's `entry_hash`.

**Returns:** `bool` — `True` if the chain is intact.

**Example:**
```python
log = AuditLog()
log.log_operation("merge", input_data="test")
log.log_operation("encrypt", input_data="test2")
assert log.verify_chain()
```

---

#### `get_entries(operation=None, since=None, until=None) → List[AuditEntry]`

Return entries matching the given filters.

**Parameters:**
- `operation` (`Optional[str]`): If provided, only entries of this type are returned.
- `since` (`Optional[float]`): Minimum timestamp (inclusive).
- `until` (`Optional[float]`): Maximum timestamp (inclusive).

**Returns:** `List[AuditEntry]` — Matching entries.

**Example:**
```python
merge_entries = log.get_entries(operation="merge")
recent = log.get_entries(since=time.time() - 3600)
```

---

#### `export_log(filepath=None) → str`

Serialise the log to a JSON string. If `filepath` is provided, the JSON is also written to that path.

**Parameters:**
- `filepath` (`Optional[str]`): Optional filesystem path to write the JSON.

**Returns:** `str` — JSON string of the full log.

**Example:**
```python
json_str = log.export_log("/tmp/audit_log.json")
```

---

#### `import_log(data: str) → AuditLog` *(classmethod)*

Deserialise an `AuditLog` from a JSON string. Raises `ValueError` if chain verification fails after import.

**Parameters:**
- `data` (`str`): JSON string produced by `export_log()`.

**Returns:** `AuditLog` — Reconstructed log.

**Example:**
```python
json_str = log.export_log()
restored_log = AuditLog.import_log(json_str)
assert restored_log.verify_chain()
```

---

### `AuditedMerge`

Convenience wrapper that calls `crdt_merge.merge()` and automatically records every invocation in an `AuditLog`.

```python
class AuditedMerge:
    def __init__(
        self,
        audit_log: Optional[AuditLog] = None,
        node_id: str = "default",
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `audit_log` | `Optional[AuditLog]` | `None` | Existing log to append to. A new one is created when `None`. |
| `node_id` | `str` | `"default"` | Node identifier for log entries. |

**Properties:**

| Name | Type | Description |
|------|------|-------------|
| `audit_log` | `AuditLog` | The underlying audit log instance. |

**Methods:**

#### `merge(left, right, key, schema=None, **kwargs) → Tuple[Any, AuditEntry]`

Execute `crdt_merge.merge()` and log the result.

**Parameters:**
- `left` (`Any`): Left dataset (list of dicts, DataFrame, etc.).
- `right` (`Any`): Right dataset.
- `key` (`Any`): Key column(s) for the merge.
- `schema` (`Any`, optional): Optional `MergeSchema` governing field strategies.
- `**kwargs` (`Any`): Forwarded to `crdt_merge.merge()`.

**Returns:** `Tuple[Any, AuditEntry]` — A tuple of `(merged_result, audit_entry)`.

**Example:**
```python
from crdt_merge.audit import AuditedMerge

audited = AuditedMerge(node_id="edge-1")

left = [{"id": 1, "score": 10}, {"id": 2, "score": 20}]
right = [{"id": 1, "score": 15}, {"id": 3, "score": 30}]

result, entry = audited.merge(left, right, key="id")
print(f"Merged records: {result}")
print(f"Audit entry operation: {entry.operation}")  # "merge"
print(f"Chain intact: {audited.audit_log.verify_chain()}")  # True
print(f"Total logged: {len(audited.audit_log)}")  # 1
```
