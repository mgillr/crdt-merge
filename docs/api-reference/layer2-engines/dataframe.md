# crdt_merge.dataframe — DataFrame Merge Engine

**Module**: `crdt_merge/dataframe.py`
**Layer**: 2 — Merge Engines
**LOC**: 355 *(corrected 2026-03-31 — was 444 from inventory; AST-verified actual: 355)*
**Dependencies**: `crdt_merge.strategies`, `crdt_merge.schema_evolution`, `pandas` (optional), `polars` (optional)

---

## Overview

The primary merge engine for tabular data. Merges two DataFrames row-by-row using CRDT strategies, matching rows by a specified key column. Supports pandas, polars, and plain `list[dict]` inputs.

---

## Quick Start

```python
import pandas as pd
from crdt_merge.dataframe import merge, diff
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet

# Two DataFrames from different replicas
df_a = pd.DataFrame({
    "id": [1, 2],
    "name": ["Alice", "Charlie"],
    "score": [80, 70],
    "tags": ["python,sql", "java"],
})
df_b = pd.DataFrame({
    "id": [1, 3],
    "name": ["Bob", "Diana"],
    "score": [90, 85],
    "tags": ["python,rust", "go"],
})

# Define per-column merge strategies
schema = MergeSchema(default=LWW(), score=MaxWins(), tags=UnionSet())

# Merge — rows matched by "id", conflicts resolved per strategy
result = merge(df_a, df_b, key="id", schema=schema)
# Row 1: score=90 (MaxWins), tags="python,rust,sql" (UnionSet)
# Row 2: only in df_a — passed through
# Row 3: only in df_b — passed through

# Diff — see what changed between two DataFrames
changes = diff(df_a, df_b, key="id")
print(changes["summary"])  # "+1 added, -1 removed, ~1 modified, =0 unchanged"
```

---

## Functions

### merge()
```python
def merge(
    df_a: Any,
    df_b: Any,
    key: Optional[Union[str, List[str]]] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = "latest",
    dedup: bool = True,
    fuzzy_dedup: bool = False,
    fuzzy_threshold: float = 0.85,
    schema: Optional[MergeSchema] = None,
) -> Any
```

**Parameters**:
- `df_a`, `df_b`: Input DataFrames (pandas, polars, or `list[dict]`).
- `key` (`str | List[str] | None`): Column(s) to match rows on. If `None`, performs append + dedup. Supports composite keys via list.
- `timestamp_col` (`str | None`): Column containing timestamps for LWW resolution. Auto-detects `"_ts"` if present in both inputs.
- `prefer` (`str`): Conflict resolution when no timestamp: `"latest"` (deterministic value-based), `"a"`, or `"b"`. Default: `"latest"`.
- `dedup` (`bool`): If `True`, remove exact duplicate rows in output. Default: `True`.
- `fuzzy_dedup` (`bool`): If `True`, also remove near-duplicate rows (requires key). Default: `False`.
- `fuzzy_threshold` (`float`): Similarity threshold for fuzzy dedup (0.0–1.0). Default: `0.85`.
- `schema` (`MergeSchema | None`): Per-field strategies. Default: all LWW.

**Returns**: Merged DataFrame containing:
- Rows only in `df_a`: included as-is
- Rows only in `df_b`: included as-is
- Rows in both: merged per-field using schema strategies

**Example**:
```python
import pandas as pd
from crdt_merge import merge, MergeSchema, LWW, MaxWins

df_a = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Charlie"], "score": [80, 70]})
df_b = pd.DataFrame({"id": [1, 3], "name": ["Bob", "Diana"], "score": [90, 85]})

schema = MergeSchema(name=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema)
# Row 1: name="Bob" (LWW), score=90 (MaxWins)
# Row 2: name="Charlie", score=70 (only in df_a)
# Row 3: name="Diana", score=85 (only in df_b)
```

### diff()
```python
def diff(
    df_a: DataFrame,
    df_b: DataFrame,
    key: str
) -> DiffResult
```
Compute differences between two DataFrames.

**Parameters**:
- `df_a`, `df_b`: Input DataFrames (pandas, polars, or `list[dict]`).
- `key` (`str | List[str]`): Column(s) to match rows on.

**Returns**: `dict` with keys:
- `added`: DataFrame of rows in `df_b` not in `df_a`
- `removed`: DataFrame of rows in `df_a` not in `df_b`
- `modified`: List of `{"key": ..., "changes": {col: {"old": ..., "new": ...}}}` dicts
- `unchanged`: Count of identical rows
- `summary`: Human-readable summary string (e.g., `"+1 added, -1 removed, ~1 modified, =0 unchanged"`)

**Example**:
```python
import pandas as pd
from crdt_merge.dataframe import diff

df_a = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Charlie"]})
df_b = pd.DataFrame({"id": [1, 3], "name": ["Bob", "Diana"]})

result = diff(df_a, df_b, key="id")
print(result["summary"])  # "+1 added, -1 removed, ~1 modified, =0 unchanged"
print(result["modified"])  # [{"key": 1, "changes": {"name": {"old": "Alice", "new": "Bob"}}}]
```

---

## RREA Chokepoint Analysis (2026-03-31)

The following undocumented private symbols were identified as chokepoints by RREA Ping Entropy analysis:

| Symbol | Entropy (H) | Role |
|--------|-------------|------|
| `_to_records` | 0.5982 | Convert DataFrame to list of dicts for internal merge |
| `_validate_key_columns` | 0.5982 | Validate key column presence before merge |
| `_make_composite_key` | 0.5982 | Build composite key from multiple columns |
| `_normalize_key` | 0.5982 | Normalize key values for consistent matching |
| `_from_records` | 0.5982 | Reconstruct DataFrame from merged records |
| `merge` | 0.3853 | Public entry point — high fan-in from upper layers |

> ⚠️ **5 private helpers** (`_to_records`, `_validate_key_columns`, `_make_composite_key`, `_normalize_key`, `_from_records`) form a critical internal pipeline. All have H=0.5982, indicating they are convergence points for multiple call paths.

---

## Internal Chokepoints

*Identified by RREA Ping Entropy analysis (2026-03-31). These 5 private helpers form the data normalization pipeline that every DataFrame merge flows through.*

All five functions share H=0.5982, indicating they are equi-critical convergence points in the merge data flow. They execute in sequence: normalize key → validate → convert to records → merge → reconstruct.

### `_to_records(df)` — H=0.5982

Converts a pandas DataFrame, polars DataFrame, or `list[dict]` into a uniform internal representation: `(records: List[Dict], columns: List[str], lib: str)`.

| Input type | Detection | Conversion |
|-----------|-----------|------------|
| pandas DataFrame | `type(df).__module__` starts with `'pandas'` | `df.to_dict('records')` |
| polars DataFrame | `type(df).__module__` starts with `'polars'` | `df.to_dicts()` |
| `list[dict]` | `isinstance` check | Passed through; columns extracted via set union |

Raises `TypeError` for unsupported types.

**Data flow:** Called at the top of both `merge()` and `diff()`. Every merge operation begins with this conversion. For large DataFrames, `_try_vectorized_merge()` provides a fast-path that bypasses this conversion entirely using native DataFrame operations.

---

### `_validate_key_columns(records, key_cols)` — H=0.5982

Validates that all specified key columns exist in the first record of the dataset. Raises `KeyError` with a diagnostic message listing missing columns and available columns if validation fails. No-ops on empty record lists.

**Data flow:** Called immediately after `_to_records()` for both sides of the merge. Prevents silent key mismatches that would produce incorrect merge results.

---

### `_normalize_key(key)` — H=0.5982

Normalizes the user-supplied key parameter into a canonical `List[str]` form:

| Input | Output |
|-------|--------|
| `None` | `None` (append-and-dedup mode) |
| `"id"` | `["id"]` |
| `["id", "name"]` | `["id", "name"]` |
| `[]` | Raises `ValueError` |

**Data flow:** Called at the start of `merge()` and `diff()` to canonicalize the key before index construction.

---

### `_make_composite_key(record, key_cols)` — H=0.5982

Extracts the composite key value from a record dict. For single-column keys, returns the raw value (preserving backward compatibility with simple key comparisons). For multi-column keys, returns a `tuple` of values.

**Data flow:** Called in the inner loop of `merge()` and `diff()` to build the `{key → row}` index for both sides. Performance-sensitive — executes once per row per side.

---

### `_from_records(records, columns, lib)` — H=0.5982

Reconstructs the output DataFrame from the merged records list, restoring the original DataFrame type:

| `lib` | Reconstruction |
|-------|---------------|
| `'pandas'` | `pd.DataFrame(records)` with column reordering (original columns first, new columns appended) |
| `'polars'` | `pl.DataFrame(records)` |
| `'dicts'` | Returns `records` as-is |

**Data flow:** Called at the end of `merge()` and `diff()` to produce the final output. The column reordering for pandas preserves the column order from the left-side input.

---

### Layer 2 Chokepoint Summary (dataframe.py)

| # | Symbol | H (Combined) | Role |
|---|--------|-------------|------|
| 1 | `_to_records` | 0.5982 | DataFrame → dict conversion (entry gate) |
| 2 | `_validate_key_columns` | 0.5982 | Key column presence validation |
| 3 | `_make_composite_key` | 0.5982 | Composite key extraction (inner loop) |
| 4 | `_normalize_key` | 0.5982 | Key parameter canonicalization |
| 5 | `_from_records` | 0.5982 | Dict → DataFrame reconstruction (exit gate) |
| 6 | `merge` | 0.3853 | Public entry point — high fan-in from upper layers |

## GDEPA Runtime-Only Symbols

Runtime introspection discovered symbols invisible to static AST analysis in this module. These are included in the 15 runtime-only symbols across Layer 2.
