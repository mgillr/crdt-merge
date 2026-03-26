# crdt_merge.provenance — Provenance Tracking

**Module**: `crdt_merge/provenance.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 383
**Dependencies**: `crdt_merge.core`, `crdt_merge.strategies`

---

## Overview

Track the lineage and source of merged data. Records which values came from which sources and why specific merge decisions were made.

---

## Functions

### merge_with_provenance()
```python
def merge_with_provenance(
    df_a, df_b,
    key: str,
    schema: MergeSchema,
    source_a: str = "source_a",
    source_b: str = "source_b"
) -> Tuple[DataFrame, ProvenanceLog]
```
Merge two DataFrames with full provenance tracking.

**Returns**: Tuple of (merged DataFrame, ProvenanceLog with per-field source attribution).

### export_provenance()
```python
def export_provenance(log: ProvenanceLog, format: str = "json") -> str
```
Export provenance log. Supported formats: `"json"`, `"csv"`, `"html"`.

---

## Classes

### ProvenanceTracker

Tracks merge provenance during merge operations.

```python
class ProvenanceTracker:
    def __init__(self, source_a: str = "a", source_b: str = "b") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `record()` | `record(key: Any, field: str, source: str, value: Any, strategy: str) -> None` | Record a merge decision |
| `get_log()` | `get_log() -> ProvenanceLog` | Get the accumulated log |
| `summary()` | `summary() -> dict` | Statistics: counts by source, by strategy |

### ProvenanceLog

Immutable record of all provenance entries.

```python
class ProvenanceLog:
    entries: List[ProvenanceEntry]
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `filter_by_source()` | `filter_by_source(source: str) -> ProvenanceLog` | Filter entries by source |
| `filter_by_field()` | `filter_by_field(field: str) -> ProvenanceLog` | Filter entries by field |
| `to_dataframe()` | `to_dataframe() -> DataFrame` | Convert to DataFrame |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class MergeDecision`

Record of how a single field was resolved during merge.

    Attributes:
        field: Column/field name.
        source: Where the value came from — "a", "b", "both_equal",
                "a_only", "b_only", or "conflict_resolved".
        strategy: Name of the strategy that resolved it (e.g. "LWW", "MaxWins").
                  Empty string if no conflict resolution was needed.
        value: The final value after merge.
        alternative: The value that was NOT chosen (None if no conflict).
    

**Attributes:**
- `field`: `str`
- `source`: `str`
- `strategy`: `str`
- `value`: `Any`
- `alternative`: `Any`



### `MergeDecision.was_conflict(self) → bool`

True if this field had a real conflict that needed resolution.

**Returns:** `bool`



### `MergeDecision.to_dict(self) → dict`

Serializes this merge decision to a plain dictionary with keys: `field`, `source`, `strategy`, `value`, and `alternative`. Values are safely converted to string representations for non-serializable types.

**Returns:** `dict`



### `class MergeRecord`

Complete provenance for one merged row.

    Attributes:
        key: The primary key value of this row.
        origin: How this row entered the merge — "merged", "unique_a", or "unique_b".
        decisions: Per-field merge decisions.
        conflict_count: Number of fields that had real conflicts.
    

**Attributes:**
- `key`: `Any`
- `origin`: `str`
- `decisions`: `List[MergeDecision]`



### `MergeRecord.conflict_count(self) → int`

Computed property that returns the number of fields in this row that had a real conflict (i.e., where `MergeDecision.was_conflict()` is `True`). Fields that were equal or only present in one source are not counted.

**Returns:** `int`



### `MergeRecord.conflicts(self) → List[MergeDecision]`

Return only decisions where a real conflict was resolved.

**Returns:** `List[MergeDecision]`



### `MergeRecord.fields_from_a(self) → List[str]`

Returns a list of field names whose final merged value came from source A (either exclusively present in A or chosen from A during conflict resolution).

**Returns:** `List[str]`



### `MergeRecord.fields_from_b(self) → List[str]`

Returns a list of field names whose final merged value came from source B (either exclusively present in B or chosen from B during conflict resolution).

**Returns:** `List[str]`



### `MergeRecord.to_dict(self) → dict`

Serializes this merge record to a plain dictionary with keys: `key`, `origin`, `conflict_count`, and `decisions` (a list of `MergeDecision.to_dict()` results).

**Returns:** `dict`



### `ProvenanceLog.to_dict(self) → dict`

Serializes the full provenance log to a plain dictionary containing: `total_rows`, `merged_rows`, `unique_a_rows`, `unique_b_rows`, `total_conflicts`, `duration_ms`, and `records` (a list of per-row `MergeRecord.to_dict()` results).

**Returns:** `dict`



---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class LayerProvenance`

Provenance information for a single layer.

    Attributes
    ----------
    layer_name : str
        Name of the layer.
    strategy_used : str
        Strategy that was applied to merge this layer.
    dominant_source : int
        Index of the model that contributed most.
    contribution_map : dict[int, float]
        Mapping from model index to contribution fraction (sums to ~1.0).
    conflict_score : float
        0.0 (total agreement) to 1.0 (total conflict).
    metadata : dict
        Strategy-specific metadata.
    

**Attributes:**
- `layer_name`: `str`
- `strategy_used`: `str`
- `dominant_source`: `int`
- `contribution_map`: `Dict[int, float]`
- `conflict_score`: `float`
- `metadata`: `Dict[str, Any]`



### `class ProvenanceSummary`

Aggregated provenance across all layers.

    Attributes
    ----------
    overall_conflict : float
        Average conflict score across all layers.
    dominant_model : int
        Model index that contributed most overall.
    layer_conflict_ranking : list[str]
        Layer names sorted by conflict score (highest first).
    per_layer : dict[str, LayerProvenance]
        Per-layer provenance data.
    

**Attributes:**
- `overall_conflict`: `float`
- `dominant_model`: `int`
- `layer_conflict_ranking`: `List[str]`
- `per_layer`: `Dict[str, LayerProvenance]`



### `compute_conflict_score(tensors: list) → float`

Compute conflict score between tensors from different models.

    Conflict = mean(variance across models) / (mean(magnitude) + epsilon).
    Result is clamped to [0, 1].

    Parameters
    ----------
    tensors : list
        List of tensor-like objects from each model.

    Returns
    -------
    float
        Conflict score in [0, 1].
    

**Parameters:**
- `tensors` (`list`)

**Returns:** `float`



---

## Internal/Private API

*Discovered during Team 4 RREA re-analysis.*

### Module-Level Helper Functions

#### `_safe_repr(val: Any) -> Any`

Convert value to JSON-safe representation. Handles DataFrames, numpy arrays, and other non-serializable types.

**Parameters:**
- `val` (`Any`): Value to convert

**Returns:** `Any` — JSON-serializable representation

**RREA Classification:** SHADOW

#### `_to_dicts(data, key: str) -> list`

Convert DataFrame or list-of-dicts to list-of-dicts. Normalizes input format for merge operations.

**Parameters:**
- `data`: DataFrame or list of dicts
- `key` (`str`): Key column name

**Returns:** `list` — list of dicts

**RREA Classification:** SHADOW

#### `_resolve_with_provenance(row_a: dict, row_b: dict, key_val: Any, columns: list, schema: Optional[MergeSchema] = None, timestamp_col: Optional[str] = None, default_strategy: MergeStrategy = LWW()) -> Tuple[dict, MergeRecord]`

Merge two rows and produce full provenance record. Core internal function that drives `merge_with_provenance()`.

**Parameters:**
- `row_a` (`dict`): Row from source A
- `row_b` (`dict`): Row from source B
- `key_val` (`Any`): Primary key value
- `columns` (`list`): Column names to merge
- `schema` (`Optional[MergeSchema]`): Per-field strategy mapping
- `timestamp_col` (`Optional[str]`): Column name containing timestamps
- `default_strategy` (`MergeStrategy`): Fallback strategy (default: LWW)

**Returns:** `Tuple[dict, MergeRecord]` — (merged row dict, provenance record)

**RREA Classification:** SHADOW — **critical internal function**, undocumented dependency of `merge_with_provenance()`

---

## automatic Methods (Missing from initial docs)

### `ProvenanceLog.__repr__(self)`

Returns string representation showing record count and conflict summary.

---

## RREA Priority Analysis

| Symbol | Classification | Entropy | Reachability Score |
|--------|---------------|---------|-------------------|
| `MergeDecision` | SPECIALIZED | 0.2714 | 4.7 |
| `MergeRecord` | SPECIALIZED | 0.2714 | 4.7 |
| `ProvenanceLog` | SPECIALIZED | 0.2714 | 4.7 |
| `merge_with_provenance` | SPECIALIZED | — | Public entry point |
| `export_provenance` | SPECIALIZED | — | Public export function |
| `_resolve_with_provenance` | SHADOW | — | **Core merge logic**, undocumented |
| `_to_dicts` | SHADOW | — | Input normalization helper |
| `_safe_repr` | SHADOW | — | Serialization safety helper |

> **Provenance module** has 3 SHADOW dependencies that drive the entire merge-with-provenance pipeline.
