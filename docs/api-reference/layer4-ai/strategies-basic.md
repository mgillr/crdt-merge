# Basic

> Basic model-merge strategies: WeightAverage, SLERP, TaskArithmetic, LinearInterpolation.

**Source:** `crdt_merge/model/strategies/basic.py`  
**Lines of Code:** 444

## Overview

These four strategies form the core toolbox for deterministic, CRDT-aware
model merging. Each strategy is auto-registered via ``@register_strategy``.

## Classes

### `WeightAverage(ModelMergeStrategy)`

Federated-averaging style weighted average (McMahan et al., 2017).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `SphericalLinearInterpolation(ModelMergeStrategy)`

Spherical linear interpolation (Shoemake 1985, applied to LLMs 2024).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

**Internal Methods:**

- `_slerp_pair(a: Any, b: Any, t: float) -> Any` — SLERP between two tensors.
- `_slerp_np(a, b, t: float, shape, np)` — SLERP using numpy.
- `_slerp_py(a: list, b: list, t: float, shape)` — SLERP pure-python.

### `TaskArithmetic(ModelMergeStrategy)`

Task arithmetic merge (Ilharco et al., 2023).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `LinearInterpolation(ModelMergeStrategy)`

Linear interpolation / model soups (Wortsman et al., 2022).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

**Internal Methods:**

- `_lerp_pair(a: Any, b: Any, t: float) -> Any` — Linear interpolation between two tensors.

## Functions

### `_py_dot()`

```python
_py_dot(a: list, b: list) -> float
```

Dot product of two flat lists.

### `_py_norm()`

```python
_py_norm(a: list) -> float
```

L2 norm of a flat list.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Scalar multiplication.

### `_py_add()`

```python
_py_add(a: list, b: list) -> list
```

Element-wise addition.

### `_py_sub()`

```python
_py_sub(a: list, b: list) -> list
```

Element-wise subtraction.

### `_py_zeros_like()`

```python
_py_zeros_like(a: list) -> list
```

Return a list of zeros with the same length.

### `_flatten()`

```python
_flatten(arr: Any) -> Any
```

Flatten an array-like to 1-D, return (flat, original_shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape) -> Any
```

Restore shape from _flatten.


## Analysis Notes
