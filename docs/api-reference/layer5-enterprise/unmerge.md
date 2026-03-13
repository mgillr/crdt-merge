# crdt_merge.unmerge — Reversible Merge Engine

> **Module**: `crdt_merge/unmerge.py` | **Layer**: 5 — Enterprise | **Version**: 0.9.3

---

## Overview

Provides three complementary capabilities for reversing merge operations: `UnmergeEngine` reverses tabular merges using the provenance trail, restoring records to their pre-merge state. `ModelUnmerge` subtracts a model's contribution from merged weights via negmerge, surgical zeroing, or proportional rescaling. `GDPRForget` is a GDPR "right to be forgotten" wrapper that combines data-level and model-level unmerge with compliance reporting. All operations require provenance metadata — without a trail there is no reliable way to attribute contributions to their sources.

---

## Quick Start

```python
from crdt_merge.unmerge import UnmergeEngine, GDPRForget

# Tabular unmerge — remove source "b" contributions
engine = UnmergeEngine()
# merged_data and provenance come from merge_with_provenance()
unmerged = engine.unmerge(merged_data, provenance, remove_source="b", key_field="id")

# GDPR forget
gdpr = GDPRForget()
result = gdpr.forget_data(merged_data, provenance, contributor="b")
report = gdpr.compliance_report()
print(report.to_json())
```

---

## Data Classes

### `UnmergeReport`

Result of verifying a tabular unmerge operation.

```python
@dataclass
class UnmergeReport:
    success: bool
    records_removed: int
    records_remaining: int
    residual_data: int          # bytes of residual from removed source
    source_removed: str
    timestamp: str
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `success` | `bool` | `True` if no residual data from the removed source remains. |
| `records_removed` | `int` | Number of records removed. |
| `records_remaining` | `int` | Number of records in the unmerged result. |
| `residual_data` | `int` | Estimated bytes of residual data from the removed source. |
| `source_removed` | `str` | Identifier of the removed source. |
| `timestamp` | `str` | UTC ISO-8601 timestamp of the verification. |

---

### `ResidualReport`

Measures how much influence a removed model still has in the cleaned state.

```python
@dataclass
class ResidualReport:
    influence_score: float        # 0.0 = clean, 1.0 = fully present
    parameters_checked: int
    parameters_with_residual: int
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `influence_score` | `float` | Average cosine similarity across layers. 0.0 = clean, 1.0 = fully present. |
| `parameters_checked` | `int` | Number of layers/parameters compared. |
| `parameters_with_residual` | `int` | Number of layers with cosine similarity > 0.01. |

---

### `ForgetResult`

Outcome of a single GDPR forget operation.

```python
@dataclass
class ForgetResult:
    success: bool
    data_records_removed: int
    model_influence_removed: bool
    compliance_timestamp: str
    contributor: str
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `success` | `bool` | Whether the forget operation succeeded. |
| `data_records_removed` | `int` | Number of data records removed. |
| `model_influence_removed` | `bool` | Whether model-level influence was removed. |
| `compliance_timestamp` | `str` | UTC ISO-8601 timestamp. |
| `contributor` | `str` | Identifier of the contributor that was forgotten. |

---

### `GDPRComplianceReport`

Aggregate compliance report across all forget requests.

```python
@dataclass
class GDPRComplianceReport:
    requests_processed: list
    total_records_removed: int
    total_models_cleaned: int
    generated_at: str
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `requests_processed` | `list` | List of per-request result dicts. |
| `total_records_removed` | `int` | Total data records removed across all requests. |
| `total_models_cleaned` | `int` | Total models cleaned across all requests. |
| `generated_at` | `str` | UTC ISO-8601 timestamp of report generation. |

**Methods:**

#### `to_dict() → dict`

Serialise to a plain dictionary.

#### `to_json() → str`

Serialise to a JSON string (indented).

---

## Classes

### `UnmergeEngine`

Reverse a tabular merge using the provenance trail. Given the merged output, its provenance log, and the name of a source to remove (`"a"` or `"b"`), produces the dataset as it would have looked had that source never participated in the merge.

```python
class UnmergeEngine:
    def __init__(self) -> None
```

Takes **no arguments**.

**Provenance convention** (from `merge_with_provenance`):
- `MergeRecord.origin` — `"unique_a"`, `"unique_b"`, or `"merged"`
- `MergeDecision.source` — `"a_only"`, `"b_only"`, `"both_equal"`, or `"conflict_resolved"`
- For `conflict_resolved` decisions: `value` holds B's contribution, `alternative` holds A's contribution (LWW default).

**Methods:**

#### `unmerge(merged_data, provenance, remove_source, key_field="id") → List[dict]`

Remove all contributions from the specified source and return the rest.

**Parameters:**
- `merged_data` (`List[dict]`): Merged records (list of dicts).
- `provenance`: `ProvenanceLog` or `list[MergeRecord]` from the original merge.
- `remove_source` (`str`): Source identifier — `"a"` or `"b"`.
- `key_field` (`str`): Name of the key column. Default: `"id"`.

**Returns:** `List[dict]` — Records remaining after the source is removed, with conflict resolutions reversed where the removed source had won.

**Example:**
```python
from crdt_merge.unmerge import UnmergeEngine

engine = UnmergeEngine()

# After a merge with provenance:
# merged_data = merge_with_provenance(left, right, key="id")
unmerged = engine.unmerge(merged_data, provenance, remove_source="b")
print(f"Records remaining: {len(unmerged)}")
```

---

#### `verify_unmerge(original_merged, unmerged, removed_source, provenance) → UnmergeReport`

Verify that the unmerged result contains no residual data from the removed source.

**Parameters:**
- `original_merged` (`List[dict]`): The original merged dataset.
- `unmerged` (`List[dict]`): The unmerged result.
- `removed_source` (`str`): Source identifier that was removed.
- `provenance`: Provenance log from the original merge.

**Returns:** `UnmergeReport` — Summary of the verification.

**Example:**
```python
unmerged = engine.unmerge(merged, provenance, "b")
report = engine.verify_unmerge(merged, unmerged, "b", provenance)
print(f"Clean: {report.success}")
print(f"Records removed: {report.records_removed}")
print(f"Residual bytes: {report.residual_data}")
```

---

#### `unmerge_delta(delta, provenance, remove_source) → Delta`

Return a copy of a `Delta` with contributions from the specified source stripped.

**Parameters:**
- `delta`: A `crdt_merge.delta.Delta` instance.
- `provenance`: `ProvenanceLog` or list of `MergeRecord`.
- `remove_source` (`str`): Source identifier to remove (`"a"` or `"b"`).

**Returns:** `Delta` — Filtered delta with the removed source's operations excluded.

---

### `ModelUnmerge`

Remove a model's contribution from merged weights. Supports three methods:

| Method | Formula | Description |
|--------|---------|-------------|
| `negmerge` | `cleaned = merged − α · removed` | Subtract scaled contribution. α = `removed_weight / total_weight`. |
| `surgical` | `cleaned = merged − removed` | Zero out the contribution entirely. |
| `proportional` | `cleaned = (merged − ratio · removed) × scale` | Remove proportionally and rescale remaining weights. |

```python
class ModelUnmerge:
    def __init__(self) -> None
```

Takes **no arguments**.

**Methods:**

#### `unmerge_model(merged_state, provenance, remove_model, method="negmerge") → dict`

Remove a model's contribution from the merged state.

**Parameters:**
- `merged_state`: Either a `CRDTMergeState` or a plain `dict` mapping layer names to tensor-like objects (lists or numpy arrays).
- `provenance`: Provenance metadata — a `ProvenanceLog`, a list of dicts from `CRDTMergeState.provenance()`, or `None` when the state carries provenance internally.
- `remove_model` (`str`): The `model_id` of the contributor to remove.
- `method` (`str`): One of `"negmerge"`, `"surgical"`, or `"proportional"`. Default: `"negmerge"`.

**Returns:** `dict` — Mapping of layer names to cleaned tensors.

**Raises:** `ValueError` if `method` is not one of the three supported methods. `TypeError` if `merged_state` is not a `CRDTMergeState` or dict.

**Example:**
```python
from crdt_merge.unmerge import ModelUnmerge

mu = ModelUnmerge()

# Plain dict of layer tensors
merged_state = {
    "layer1": [1.0, 2.0, 3.0],
    "model_a": [0.5, 1.0, 1.5],
}

provenance = [
    {"model_id": "model_a", "weight": 0.5},
    {"model_id": "model_b", "weight": 0.5},
]

cleaned = mu.unmerge_model(merged_state, provenance, "model_a", method="negmerge")
print(cleaned)
```

---

#### `measure_residual(cleaned_state, original_model) → ResidualReport`

Measure how much of the original model remains in the cleaned state using cosine similarity between corresponding layers.

**Parameters:**
- `cleaned_state` (`dict`): Dict of layer names to cleaned tensors.
- `original_model` (`dict`): Dict of layer names to the removed model's original tensors.

**Returns:** `ResidualReport` — Influence score (0.0 = clean, 1.0 = fully present).

**Example:**
```python
residual = mu.measure_residual(cleaned, {"layer1": [0.5, 1.0, 1.5]})
print(f"Influence: {residual.influence_score:.4f}")
print(f"Layers with residual: {residual.parameters_with_residual}")
```

---

### `GDPRForget`

GDPR "right to be forgotten" implementation. Wraps `UnmergeEngine` and `ModelUnmerge` with compliance metadata, timestamped audit entries, and report generation.

```python
class GDPRForget:
    def __init__(
        self,
        engine: Optional[UnmergeEngine] = None,
        model_unmerge: Optional[ModelUnmerge] = None,
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `engine` | `Optional[UnmergeEngine]` | `None` | Tabular unmerge engine. A new one is created when `None`. |
| `model_unmerge` | `Optional[ModelUnmerge]` | `None` | Model unmerge engine. A new one is created when `None`. |

**Methods:**

#### `forget_data(merged_data, provenance, contributor, key_field="id") → ForgetResult`

Remove a contributor's data records and return a compliance result.

**Parameters:**
- `merged_data` (`List[dict]`): The current merged dataset.
- `provenance`: Provenance log from the original merge.
- `contributor` (`str`): Source identifier (`"a"` or `"b"`).
- `key_field` (`str`): Key column name. Default: `"id"`.

**Returns:** `ForgetResult`

---

#### `forget_training_data(model_state, provenance, data_to_forget, method="negmerge") → ForgetResult`

Remove a model contributor's influence from the merged model state.

**Parameters:**
- `model_state`: `CRDTMergeState` or dict of layer tensors.
- `provenance`: Provenance metadata.
- `data_to_forget` (`str`): The `model_id` of the contributor to forget.
- `method` (`str`): Unmerge method. Default: `"negmerge"`.

**Returns:** `ForgetResult`

---

#### `compliance_report() → GDPRComplianceReport`

Generate a compliance report covering all forget operations performed by this instance.

**Returns:** `GDPRComplianceReport`

**Example:**
```python
from crdt_merge.unmerge import GDPRForget

gdpr = GDPRForget()

# Forget tabular data
result1 = gdpr.forget_data(merged_data, provenance, contributor="b")
print(f"Records removed: {result1.data_records_removed}")

# Forget model contributions
result2 = gdpr.forget_training_data(
    model_state, model_provenance, data_to_forget="model_b"
)
print(f"Model cleaned: {result2.model_influence_removed}")

# Generate compliance report
report = gdpr.compliance_report()
print(report.to_json())
# {
#   "requests_processed": [...],
#   "total_records_removed": ...,
#   "total_models_cleaned": ...,
#   "generated_at": "2026-04-01T16:00:00Z"
# }
```
