"""
HuggingFace Datasets integration for crdt-merge.

Merge two HF datasets directly by name or Dataset objects.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional


def merge_datasets(
    dataset_a: Any,
    dataset_b: Any,
    key: Optional[str] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = "latest",
    dedup: bool = True,
) -> Any:
    """
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
    """
    from datasets import Dataset, load_dataset

    # Load if string names provided
    if isinstance(dataset_a, str):
        dataset_a = load_dataset(dataset_a, split="train")
    if isinstance(dataset_b, str):
        dataset_b = load_dataset(dataset_b, split="train")

    # Convert to pandas, merge, convert back
    from .dataframe import merge as df_merge
    
    df_a = dataset_a.to_pandas()
    df_b = dataset_b.to_pandas()
    
    merged_df = df_merge(
        df_a, df_b,
        key=key,
        timestamp_col=timestamp_col,
        prefer=prefer,
        dedup=dedup,
    )
    
    return Dataset.from_pandas(merged_df)


def dedup_dataset(
    dataset: Any,
    columns: Optional[List[str]] = None,
    method: str = "exact",
    threshold: float = 0.85,
) -> Any:
    """
    Deduplicate a HuggingFace Dataset.
    
    Args:
        dataset: HF Dataset object or name
        columns: Columns to compare (None = all)
        method: "exact" or "fuzzy"
        threshold: Fuzzy similarity threshold

    Returns:
        Deduplicated Dataset with stats
    """
    from datasets import Dataset, load_dataset
    from .dedup import dedup_records

    if isinstance(dataset, str):
        dataset = load_dataset(dataset, split="train")

    records = [dict(r) for r in dataset]
    unique, removed = dedup_records(records, columns=columns, method=method, threshold=threshold)
    
    result = Dataset.from_list(unique)
    result.info.description = f"Deduplicated: {removed} duplicates removed from {len(records)} rows"
    return result
