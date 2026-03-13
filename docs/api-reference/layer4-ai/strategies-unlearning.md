# Unlearning

> Unlearning model-merge strategies.

**Source:** `crdt_merge/model/strategies/unlearning.py`  
**Lines of Code:** 307

## Overview

Implements 2 strategies:

20. NegativeMerge       — Weight negation for unlearning (NegMerge)
21. SplitUnlearnMerge   — Split → unlearn → merge

## Classes

### `NegativeMerge(ModelMergeStrategy)`

NegMerge: Weight negation for unlearning (ICML 2025).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `SplitUnlearnMerge(ModelMergeStrategy)`

Split → Unlearn → Merge (2025).

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

Defined in `crdt_merge/model/strategies/unlearning.py`.

### `_py_sub()`

```python
_py_sub(a: list, b: list) -> list
```

Defined in `crdt_merge/model/strategies/unlearning.py`.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Defined in `crdt_merge/model/strategies/unlearning.py`.

### `_py_zeros()`

```python
_py_zeros(n: int) -> list
```

Defined in `crdt_merge/model/strategies/unlearning.py`.

### `_flatten()`

```python
_flatten(arr: Any)
```

Flatten array-like to 1-D. Returns (flat, shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape)
```

Defined in `crdt_merge/model/strategies/unlearning.py`.


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 1
- Inherited methods: 2 inherited properties
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 16.7%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
