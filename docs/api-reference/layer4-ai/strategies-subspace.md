# Subspace

> Subspace / Sparsification model-merge strategies.

**Source:** `crdt_merge/model/strategies/subspace.py`  
**Lines of Code:** 1148

## Overview

Implements 9 strategies that work on task vectors (deltas from a base model):

5.  TIESMerge          — Trim, Elect sign, Disjoint merge
6.  DareDropAndRescale — Random drop + rescale (DARE)
7.  DellaDropElectLowRank — Magnitude-aware DARE (DELLA)
8.  DareTiesHybrid     — DARE dropping + TIES sign election
9.  ModelBreadcrumbs   — Sparse binary masks + task vector aggregation
10. EMRMerge           — Elect, Mask, Rescale (tuning-free)
11. SpectralTruncationAdaptiveRescaling (STAR)
12. SVDKnotTying       — Align SVD bases + merge
13. AdaptiveRankPruning (AdaRank)

## Classes

### `TIESMerge(ModelMergeStrategy)`

TIES-Merging: Trim, Elect sign, Disjoint merge (Yadav et al., NeurIPS 2023).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `DareDropAndRescale(ModelMergeStrategy)`

DARE: Drop And REscale (Yu et al., 2024 — Language Models are Super Mario).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `DellaDropElectLowRank(ModelMergeStrategy)`

DELLA-Merging: DARE + magnitude-aware dropping (Bansal, 2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `DareTiesHybrid(ModelMergeStrategy)`

DARE-TIES: DARE dropping + TIES sign election (Community hybrid, 2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `ModelBreadcrumbs(ModelMergeStrategy)`

Model Breadcrumbs: Sparse masks + task vector aggregation (Davari & Belilovsky, 2023).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `EMRMerge(ModelMergeStrategy)`

EMR-Merging: Elect, Mask, Rescale (Huang et al., 2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `SpectralTruncationAdaptiveRescaling(ModelMergeStrategy)`

STAR: SVD decompose, truncate, rescale, reconstruct (2025).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `SVDKnotTying(ModelMergeStrategy)`

SVD Knot Tying: Align SVD bases, merge in aligned space (2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `AdaptiveRankPruning(ModelMergeStrategy)`

AdaRank: Per-layer adaptive rank selection + pruned merge (ICLR 2026).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

## Functions

### `_py_add()`

```python
_py_add(a: list, b: list) -> list
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_py_sub()`

```python
_py_sub(a: list, b: list) -> list
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_py_zeros()`

```python
_py_zeros(n: int) -> list
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_py_abs()`

```python
_py_abs(a: list) -> list
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_py_percentile()`

```python
_py_percentile(values: list, pct: float) -> float
```

Compute percentile from a sorted list of values.

### `_flatten()`

```python
_flatten(arr: Any)
```

Flatten array-like to 1-D. Returns (flat, shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape)
```

Defined in `crdt_merge/model/strategies/subspace.py`.

### `_require_base()`

```python
_require_base(base: Any) -> None
```

Raise if base_model is missing.

### `_compute_task_vectors_np()`

```python
_compute_task_vectors_np(tensors, base, np)
```

Compute task vectors as numpy arrays.

### `_compute_task_vectors_py()`

```python
_compute_task_vectors_py(tensors, base)
```

Compute task vectors as plain lists.


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: 9 inherited properties
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 21.5%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
