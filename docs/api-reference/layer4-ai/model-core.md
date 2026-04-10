# crdt_merge.model.core — Model Merge Core

**Module**: `crdt_merge/model/core.py`
**Layer**: 4 — AI / Model / Agent
**Package**: `crdt_merge.model`
**Dependencies**: `crdt_merge.core`, `crdt_merge.strategies`, `torch` (optional)

---

## Overview

Core model merge operations. Provides the primary `ModelMerge` class and `ModelMergeSchema` for declarative per-layer model merging.

---

## Classes

### ModelMerge

Primary interface for merging ML model weights.

```python
class ModelMerge:
    def __init__(self, strategy: str = "linear", **kwargs) -> None
```

**Parameters**:
- `strategy` (`str`): Merge strategy name (see model-strategies.md for all 26+).
- `**kwargs`: Strategy-specific parameters (e.g., `weights`, `alpha`).

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(models: List[dict], **kwargs) -> dict` | Merge model state dicts |
| `merge_from_files()` | `merge_from_files(paths: List[str], output: str) -> None` | Merge from checkpoint files |
| `get_strategy()` | `get_strategy() -> BaseStrategy` | Get active strategy object |
| `set_strategy()` | `set_strategy(name: str, **kwargs) -> None` | Change strategy |

### ModelMergeSchema

Per-layer strategy mapping for model weights (analogous to MergeSchema for DataFrames).

```python
class ModelMergeSchema:
    def __init__(self, default_strategy: str = "linear", **layer_strategies) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `strategy_for()` | `strategy_for(layer_name: str) -> BaseStrategy` | Get strategy for model layer |
| `set_strategy()` | `set_strategy(layer_name: str, strategy: str, **kwargs) -> None` | Set layer-specific strategy |


## Analysis Notes
