# Base

> ModelMergeStrategy abstract base class.

**Source:** `crdt_merge/model/strategies/base.py`  
**Lines of Code:** 395

## Overview

All model merge strategies inherit from this. Provides:
- Common interface for merge operations
- CRDT property declaration
- Paper reference metadata
- Runtime verification hooks

## Classes

### `CRDTTier(str, Enum)`

Classification of a strategy's CRDT compliance.

**Class Attributes:**

- `TRUE_CRDT` — `'TRUE_CRDT'`
- `PARTIAL_CRDT` — `'PARTIAL_CRDT'`
- `NOT_CRDT` — `'NOT_CRDT'`

### `MergeResult`

Result of a model merge operation.

**Class Attributes:**

- `tensor` — `Any`
- `provenance` — `Optional[Dict[str, Any]] = None`
- `metadata` — `Dict[str, Any] = field(default_factory=dict)`

### `ModelMergeStrategy(ABC)`

Abstract base for all model-merge strategies.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | Merge a list of array-like tensors into one. |
| `name` | `name() -> str` | Short unique identifier for this strategy (e.g. ``'slerp'``). |
| `category` | `category() -> str` | Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``). |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | CRDT property declaration. |
| `paper_reference` | `paper_reference() -> str` | Academic citation or URL for the strategy's paper. |
| `crdt_tier` | `crdt_tier() -> CRDTTier` | Auto-classify this strategy's CRDT compliance tier. |
| `verify_crdt` | `verify_crdt(gen_fn = None, trials: int = 100, base_gen_fn = None) -> Dict[str, Any]` | Empirically verify CRDT properties via random trials. |

## Functions

### `_get_np()`

```python
_get_np()
```

Return numpy if available, else None.

### `_get_torch()`

```python
_get_torch()
```

Return torch if available, else None.

### `_to_array()`

```python
_to_array(tensor: Any) -> Any
```

Convert any tensor-like to a workable array.

### `_from_array()`

```python
_from_array(array: Any, original: Any) -> Any
```

Convert *array* back to the same type as *original*.

### `_normalize_weights()`

```python
_normalize_weights(weights: Optional[List[float]], n: int) -> List[float]
```

Normalize *weights* to sum to 1.  If *weights* is ``None``, return uniform.

### `_approx_equal()`

```python
_approx_equal(a: Any, b: Any, tol: float = 1e-07) -> bool
```

Element-wise approximate equality for array-like objects.


## Analysis Notes
