# crdt_merge.model.provenance — Per-Parameter Provenance Tracking

**Module**: `crdt_merge/model/provenance.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.strategies.base`

---

## Overview

Per-parameter provenance tracking for model merges. Tracks which source model contributed most to each layer of a merged model, computes conflict scores, and exports provenance reports in JSON/CSV.

```python
from crdt_merge.model.provenance import ProvenanceTracker

tracker = ProvenanceTracker()
prov = tracker.track_merge("layer.0.weight", tensors, weights, "weight_average", result)
summary = tracker.summary()
print(export_provenance(summary, format="json"))
```

---

## Classes

### ProvenanceTracker

```python
class ProvenanceTracker:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `track_merge()` | `track_merge(layer_name, tensors, weights, strategy_name, result=None) -> LayerProvenance` | Track provenance for a single layer merge |
| `summary()` | `summary() -> ProvenanceSummary` | Aggregated provenance across all tracked layers |

### LayerProvenance

```python
@dataclass
class LayerProvenance:
    layer_name: str
    strategy_used: str
    dominant_source: int
    contribution_map: Dict[int, float]
    conflict_score: float
    metadata: Dict[str, Any]
```

### ProvenanceSummary

```python
@dataclass
class ProvenanceSummary:
    overall_conflict: float
    dominant_model: int
    layer_conflict_ranking: List[str]
    per_layer: Dict[str, LayerProvenance]
```

---

## Functions

### `compute_contribution(tensors, weights, strategy_name) → Dict[int, float]`

Compute per-model contribution fractions. For weight-based strategies, contribution equals the normalized weight.

### `compute_conflict_score(tensors) → float`

Compute conflict score between tensors from different models. Conflict = mean(variance across models) / (mean(magnitude) + ε), clamped to [0, 1].

### `export_provenance(summary, format="json") → str`

Export provenance summary to JSON or CSV string.

---

## Shadow Dependencies

### 3 NumPy / PyTorch Tensor Conversion Operations

The `model/provenance.py` module uses 3 implicit tensor operations that constitute shadow dependencies on NumPy:

| Method | Location | Purpose |
|--------|----------|---------|
| `.ravel()` | `compute_conflict_score()` | Flattens multi-dimensional tensors to 1-D arrays for element-wise variance computation. Called via `np.asarray(_to_array(t), dtype=float).ravel()`. |
| `np.stack()` | `compute_conflict_score()` | Stacks flattened tensor arrays along axis 0 to create an (n_models, n_params) matrix for vectorized variance and magnitude computation. |
| `np.var()` / `np.mean()` / `np.abs()` | `compute_conflict_score()` | Computes per-parameter variance, mean magnitude, and absolute values across models for conflict scoring. |

#### Notes

- All operations are **standard NumPy array methods** — no direct PyTorch dependency exists in this module.
- The module imports `_to_array` and `_get_np` from `crdt_merge.model.strategies.base`, which handles the NumPy availability check.
- When NumPy is unavailable, the module falls back to a pure-Python implementation that manually flattens nested lists and computes variance/magnitude with list comprehensions.
- PyTorch tensors passed through `_to_array()` are implicitly converted via `np.asarray()`, which triggers PyTorch's `__array__` protocol (`.detach().cpu().numpy()`).

---

## Analysis Notes

### RREA Findings
- Entropy profile: Low (shadow deps present)
- Shadow dependencies: `.ravel()`, `np.stack()`, `np.var()`/`np.mean()`/`np.abs()` — all standard NumPy operations
- Chokepoint status: None
