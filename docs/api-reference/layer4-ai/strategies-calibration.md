# Calibration

> Post-Calibration model-merge strategies.

**Source:** `crdt_merge/model/strategies/calibration.py`  
**Lines of Code:** 413

## Overview

Implements 2 strategies:

22. WeightScopeAlignment    — Normalize weight distributions, align scopes, merge
23. RepresentationSurgery   — Post-merge representation correction

## Classes

### `WeightScopeAlignment(ModelMergeStrategy)`

Weight Scope Alignment: Normalize weight distributions → align → merge (2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `RepresentationSurgery(ModelMergeStrategy)`

Post-merge representation correction (2024).

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

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_py_sub()`

```python
_py_sub(a: list, b: list) -> list
```

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_py_zeros()`

```python
_py_zeros(n: int) -> list
```

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_py_mean()`

```python
_py_mean(a: list) -> float
```

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_py_std()`

```python
_py_std(a: list) -> float
```

Defined in `crdt_merge/model/strategies/calibration.py`.

### `_flatten()`

```python
_flatten(arr: Any)
```

Flatten array-like to 1-D. Returns (flat, shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape)
```

Defined in `crdt_merge/model/strategies/calibration.py`.


## Analysis Notes
