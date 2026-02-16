# Hf

> HuggingFace Hub operations for model merging with CRDT verification.

**Source:** `crdt_merge/hub/hf.py`  
**Lines of Code:** 333

## Overview

HuggingFace Hub operations for model merging with CRDT verification.

## Classes

### `HFMergeResult`

Result of a Hub-based model merge operation.

**Class Attributes:**

- `state_dict` — `dict`
- `provenance` — `Optional[ProvenanceSummary]`
- `model_card` — `str`
- `repo_url` — `Optional[str] = None`

### `HFMergeHub`

Push, pull, and merge models on HuggingFace Hub with CRDT verification.

**Constructor:**

```python
HFMergeHub(token: Optional[str] = None, cache_dir: Optional[str] = None)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge` | `merge(sources: List[str], strategy: str = 'weight_average', weights: Optional[List[float]] = None, destination: Optional[str] = None, auto_model_card: bool = True, private: bool = False, commit_message: Optional[str] = None) -> HFMergeResult` | Merge models from HuggingFace Hub with CRDT-verified provenance. |
| `pull_weights` | `pull_weights(repo_id: str, revision: Optional[str] = None) -> dict` | Download model weights from a HuggingFace Hub repository. |
| `push_weights` | `push_weights(state_dict: dict, repo_id: str, model_card: Optional[str] = None, commit_message: str = 'Upload merged model', private: bool = False) -> str` | Push model weights to a HuggingFace Hub repository. |
| `list_merge_models` | `list_merge_models(author: Optional[str] = None, limit: int = 20) -> List[dict]` | List models on HuggingFace Hub tagged with merge metadata. |

**Internal Methods:**

- `_hub_api()` — Return a HfApi instance. Isolated for easy mocking in tests.

## Functions

### `_require_hf_hub()`

```python
_require_hf_hub()
```

Lazy-import huggingface_hub, raising a clear error if missing.

## Constants / Module Variables

- `_HF_INSTALL_MSG` — `'huggingface_hub is required for HuggingFace Hub integration. Install it with: pip install huggin...`


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 3
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 88.9%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
