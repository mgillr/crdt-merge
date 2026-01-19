# HuggingFace Datasets Adapter

Merge and dedup HuggingFace Datasets.

## Quick Example

```python
from crdt_merge.datasets_ext import merge_datasets, dedup_dataset
merged = merge_datasets("user/dataset-a", "user/dataset-b", key="id")
```

---

## API Reference

## `crdt_merge.datasets_ext`

> HuggingFace Datasets integration for crdt-merge.

**Module:** `crdt_merge.datasets_ext`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `dedup_dataset(dataset: 'Any', columns: 'Optional[List[str]]' = None, method: 'str' = 'exact', threshold: 'float' = 0.85) -> 'Any'`

Deduplicate a HuggingFace Dataset.

#### `merge_datasets(dataset_a: 'Any', dataset_b: 'Any', key: 'Optional[str]' = None, timestamp_col: 'Optional[str]' = None, prefer: 'str' = 'latest', dedup: 'bool' = True) -> 'Any'`

Merge two HuggingFace Dataset objects using CRDT semantics.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
