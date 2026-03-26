# crdt_merge.arrow — Apache Arrow Engine

**Module**: `crdt_merge/arrow.py`
**Layer**: 2 — Merge Engines
**LOC**: 728 *(corrected 2026-03-31 — was 969 from inventory; AST-verified actual: 728)*
**Dependencies**: `crdt_merge.strategies`, `crdt_merge.schema_evolution`, `pyarrow`

---

## Overview

High-performance merge engine using Apache Arrow columnar format with vectorized compute kernels.

---

## Classes

### Arrow
Main Arrow merge engine.

```python
class Arrow:
    def __init__(self, schema: Optional[MergeSchema] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(table_a: pa.Table, table_b: pa.Table, key: str) -> pa.Table` | Merge two Arrow tables |
| `merge_batches()` | `merge_batches(batches: List[pa.RecordBatch], key: str) -> pa.Table` | Merge multiple batches |

### ArrowBatch
Batch processing for Arrow record batches.

```python
class ArrowBatch:
    def __init__(self, batch_size: int = 10000) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `process()` | `process(reader: pa.RecordBatchReader, key: str, schema: MergeSchema) -> pa.Table` | Process batches from reader |

## Functions

### arrow_merge()
```python
def arrow_merge(table_a: pa.Table, table_b: pa.Table, key: str,
                schema: Optional[MergeSchema] = None) -> pa.Table
```
Convenience function for one-shot Arrow table merge.


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class ArrowMerge`

Arrow-native CRDT merge engine.

    Merges two or more Arrow tables using configurable per-column CRDT
    strategies.  Supports keyed merges, streaming batch merges, and
    file-based IPC merges.

    Parameters
    ----------
    schema : MergeSchema or None
        Per-column merge strategies.  Falls back to LWW for every column
        when *None*.
    timestamp_col : str or None
        Name of the column that carries row timestamps for LWW resolution.
    



### `ArrowMerge.timestamp_col(self) → Optional[str]`

Return the configured timestamp column name.

**Returns:** `Optional[str]`



### `write_ipc(table: Any, path: str) → str`

Write a ``pa.Table`` to an Arrow IPC file.

    Parameters
    ----------
    table :
        The table to write.
    path :
        Output file path.

    Returns
    -------
    str
        The output path.
    

**Parameters:**
- `table` (`Any`)
- `path` (`str`)

**Returns:** `str`



### `read_ipc(path: str) → Any`

Read an Arrow IPC file and return a ``pa.Table``.

    Parameters
    ----------
    path :
        Path to the IPC file.

    Returns
    -------
    pa.Table
    

**Parameters:**
- `path` (`str`)

**Returns:** `Any`



### `arrow_schema_info(table: Any) → Dict[str, str]`

Return a dict mapping column names to Arrow type strings.

    Parameters
    ----------
    table :
        A ``pa.Table`` or ``pa.RecordBatch``.

    Returns
    -------
    dict[str, str]
    

**Parameters:**
- `table` (`Any`)

**Returns:** `Dict[str, str]`

---

## RREA Chokepoint Analysis (2026-03-31)

`arrow.py` contains the **highest-entropy chokepoint** in all of Layer 2. The following undocumented symbols were identified by RREA Ping Entropy analysis:

| Symbol | Entropy (H) | Role |
|--------|-------------|------|
| `_ensure_table` | **0.6232** | 🔴 **#1 Layer 2 chokepoint** — validates/converts input to pa.Table |
| `_import_pyarrow` | 0.5976 | Lazy import guard for pyarrow |
| `_arrow_type_string` | 0.5203 | Convert Arrow type to string representation |
| `_schema_dict` | 0.5203 | Extract schema as dict from Arrow table |
| `ArrowMerge.timestamp_col` | 0.4547 | Property — configured timestamp column |
| `ArrowMerge` | 0.4547 | Class — Arrow-native CRDT merge engine |
| `ArrowMerge.schema` | 0.4547 | Property — merge schema configuration |
| `_has_pyarrow` | 0.396 | Boolean flag — pyarrow availability check |

> **`_ensure_table` (H=0.6232) is the single highest-entropy chokepoint in Layer 2.** It is the convergence point for all Arrow merge operations — every path through `arrow.py` flows through this function. It needs thorough documentation covering input validation, type coercion, and error handling.

> **`ArrowMerge` class** and its properties (`timestamp_col`, `schema`) are partially documented above but were flagged as chokepoints (H=0.4547) due to high fan-in from parquet.py and upper layers.

---

## Internal Chokepoints

*Identified by RREA Ping Entropy analysis (2026-03-31). These private functions are convergence points for all Arrow merge operations.*

### `_ensure_table(obj, pa)` — H=0.6232

**The single highest-entropy chokepoint in Layer 2.**

Converts the input `obj` to a `pa.Table`, handling three input types:

| Input type | Conversion |
|-----------|------------|
| `pa.Table` | Returned unchanged (identity pass-through) |
| `pa.RecordBatch` | Wrapped via `pa.Table.from_batches([obj])` |
| `list[dict]` | Converted via `pa.Table.from_pylist(obj)`; empty list → `pa.table({})` |

Raises `TypeError` for any other input type, including `list[non-dict]`.

**Data flow:** Every public entry point (`ArrowMerge.merge()`, `ArrowMerge.merge_batches()`, `arrow_merge()`, `arrow_merge_tables()`, `table_to_batches()`, `write_ipc()`, `arrow_schema_info()`, `compare_arrow_schemas()`) calls `_ensure_table` before any processing. This makes it the single point of input validation for the entire Arrow engine.

**Stability:** Frozen internal API — signature and coercion rules are load-bearing for all Arrow merge paths.

---

### `_import_pyarrow()` — H=0.5976

Lazy import guard for the optional `pyarrow` dependency. Attempts `import pyarrow` and returns the module object on success. Raises `ImportError` with an actionable install message (`pip install pyarrow`) on failure.

**Data flow:** Called at the start of every Arrow operation that requires the `pyarrow` module. Paired with `_has_pyarrow()` (H=0.396) which returns a boolean without raising.

**Design rationale:** Lazy import keeps `crdt_merge` importable even when PyArrow is not installed, enabling the pure-Python `dataframe.merge()` fallback path.

---

### `_arrow_type_string(arrow_type)` — H=0.5203

Converts a `pyarrow` data type to its string representation via `str(arrow_type)`. Used internally by `_schema_dict()` to build `{column_name: type_string}` mappings for schema comparison and evolution.

**Data flow:** Called by `_schema_dict()` → consumed by `ArrowMerge._evolve_schemas()`, `arrow_schema_info()`, and `compare_arrow_schemas()`. All schema-level operations depend on this type mapping.

**Stability:** Trivial wrapper, but changing the string representation would break schema evolution compatibility checks.

---

### Layer 2 Chokepoint Summary (arrow.py)

| # | Symbol | H (Combined) | Fan-in | Role |
|---|--------|-------------|--------|------|
| 1 | `_ensure_table` | **0.6232** | 8 public entry points | Input validation/coercion for all Arrow operations |
| 2 | `_import_pyarrow` | 0.5976 | All Arrow operations | Lazy import guard — fail-fast with clear error |
| 3 | `_arrow_type_string` | 0.5203 | Schema comparison paths | Type-to-string mapping for schema evolution |
| 4 | `_schema_dict` | 0.5203 | Schema comparison paths | Table schema extraction |
| 5 | `ArrowMerge` | 0.4547 | Parquet, upper layers | Primary engine class |
| 6 | `ArrowMerge.timestamp_col` | 0.4547 | LWW resolution | Timestamp column configuration |
| 7 | `ArrowMerge.schema` | 0.4547 | Strategy dispatch | MergeSchema accessor |
| 8 | `_has_pyarrow` | 0.396 | `arrow_merge()` fallback | Boolean availability check |

## GDEPA Runtime-Only Symbols

Runtime introspection discovered symbols invisible to static AST analysis in this module. These are included in the 15 runtime-only symbols across Layer 2.

