# Weighted

> Weighted / Importance model-merge strategies.

**Source:** `crdt_merge/model/strategies/weighted.py`  
**Lines of Code:** 538

## Overview

Implements 4 strategies:

14. FisherMerge          — Fisher-weighted averaging
15. RegressionMean       — Closed-form regression mean (RegMean)
16. AdaptiveMerging      — Entropy-based adaptive coefficients (AdaMerging)
17. DifferentiableAdaptiveMerging — Gradient-free coefficient optimization (DAM)

## Classes

### `FisherMerge(ModelMergeStrategy)`

Fisher-weighted averaging (Matena & Raffel, 2022).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `RegressionMean(ModelMergeStrategy)`

RegMean: Dataless knowledge fusion via regularized regression mean (Jin et al., 2023).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `AdaptiveMerging(ModelMergeStrategy)`

AdaMerging: Entropy-based adaptive merge coefficients (Yang et al., 2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `DifferentiableAdaptiveMerging(ModelMergeStrategy)`

DAM: Differentiable Adaptive Merging via gradient-free coefficient optimization (2024).

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

Defined in `crdt_merge/model/strategies/weighted.py`.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Defined in `crdt_merge/model/strategies/weighted.py`.

### `_py_zeros()`

```python
_py_zeros(n: int) -> list
```

Defined in `crdt_merge/model/strategies/weighted.py`.

### `_py_mul()`

```python
_py_mul(a: list, b: list) -> list
```

Element-wise multiplication.

### `_flatten()`

```python
_flatten(arr: Any)
```

Flatten array-like to 1-D. Returns (flat, shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape)
```

Defined in `crdt_merge/model/strategies/weighted.py`.


## Analysis Notes
