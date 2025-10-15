"""
crdt-merge: Conflict-free merge, dedup and sync for DataFrames, JSON and datasets.

Usage:
    from crdt_merge import merge, dedup, diff

    # Merge two DataFrames (pandas, polars, or dicts)
    merged = merge(df_a, df_b, key="id")

    # Composable per-column strategies (NEW in v0.3.0)
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet
    schema = MergeSchema(
        default=LWW(),
        score=MaxWins(),
        tags=UnionSet(),
    )
    merged = merge(df_a, df_b, key="id", schema=schema)

    # Streaming merge — O(batch_size) memory (NEW in v0.3.0)
    from crdt_merge.streaming import merge_stream
    for batch in merge_stream(source_a, source_b, key="id", batch_size=5000):
        write_batch(batch)

    # Deduplicate a list
    unique, dups = dedup(items)

    # See what changed
    changes = diff(df_a, df_b, key="id")

    # Merge JSON/dicts
    from crdt_merge import merge_dicts
    result = merge_dicts(config_a, config_b)

    # HuggingFace Datasets (requires `pip install crdt-merge[datasets]`)
    from crdt_merge import merge_datasets, dedup_dataset
    merged = merge_datasets("user/dataset-a", "user/dataset-b", key="id")
"""

__version__ = "0.3.0"

# Core CRDT types
from .core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

# DataFrame merge
from .dataframe import merge, diff

# Deduplication
from .dedup import dedup_list as dedup
from .dedup import dedup_records, DedupIndex, MinHashDedup

# JSON merge
from .json_merge import merge_dicts, merge_json_lines

# v0.3.0: Composable Merge Strategies
from .strategies import (
    MergeStrategy, LWW, MaxWins, MinWins, UnionSet, Priority,
    Concat, Custom, MergeSchema,
)

# v0.3.0: Streaming Merge Pipeline
from .streaming import merge_stream, merge_sorted_stream, StreamStats

# Lazy imports for optional deps
def merge_datasets(*args, **kwargs):
    """Merge two HuggingFace Datasets. Requires: pip install crdt-merge[datasets]"""
    from .datasets_ext import merge_datasets as _merge
    return _merge(*args, **kwargs)

def dedup_dataset(*args, **kwargs):
    """Deduplicate a HuggingFace Dataset. Requires: pip install crdt-merge[datasets]"""
    from .datasets_ext import dedup_dataset as _dedup
    return _dedup(*args, **kwargs)
