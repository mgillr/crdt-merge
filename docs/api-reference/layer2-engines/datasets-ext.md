# `crdt_merge/datasets_ext.py`

> HuggingFace Datasets integration for crdt-merge.

Merge two HF datasets directly by name or Dataset objects.

**Source:** `crdt_merge/datasets_ext.py` | **Lines:** 106

---

## Functions

### `merge_datasets(dataset_a: Any, dataset_b: Any, key: Optional[str] = None, timestamp_col: Optional[str] = None, prefer: str = 'latest', dedup: bool = True) → Any`

Merge two HuggingFace Dataset objects using CRDT semantics.
    
    Args:
        dataset_a: HF Dataset object or dataset name (str)
        dataset_b: HF Dataset object or dataset name (str)
        key: Column to match rows on
        timestamp_col: Column with timestamps for LWW
        prefer: "latest", "a", or "b"
        dedup: Remove exact duplicates

    Returns:
        Merged HF Dataset

### `dedup_dataset(dataset: Any, columns: Optional[List[str]] = None, method: str = 'exact', threshold: float = 0.85) → Any`

Deduplicate a HuggingFace Dataset.
    
    Args:
        dataset: HF Dataset object or name
        columns: Columns to compare (None = all)
        method: "exact" or "fuzzy"
        threshold: Fuzzy similarity threshold

    Returns:
        Deduplicated Dataset with stats

