# Hf

> HuggingFace Hub source and target adapters for merge pipelines.

**Source:** `crdt_merge/model/targets/hf.py`  
**Lines of Code:** 210

## Overview

HuggingFace Hub source and target adapters for merge pipelines.

## Classes

### `HfSource`

Load model weights from HuggingFace Hub for use in merge pipelines.

**Constructor:**

```python
HfSource(repo_id: str, revision: Optional[str] = None, token: Optional[str] = None)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `load` | `load() -> dict` | Download and load model weights from HuggingFace Hub. |

**Internal Methods:**

- `_hub_api()` — Return a HfApi instance. Isolated for easy mocking in tests.

### `HfTarget`

Push merged model weights to HuggingFace Hub.

**Constructor:**

```python
HfTarget(repo_id: str, token: Optional[str] = None, private: bool = False)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `save` | `save(state_dict: dict, model_card: Optional[str] = None, commit_message: Optional[str] = None) -> str` | Upload model weights to HuggingFace Hub. |

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
- Runtime-only symbols: 2
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 77.8%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
