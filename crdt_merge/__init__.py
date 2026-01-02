# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

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

__version__ = "0.7.1"

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
    Concat, Custom, LongestWins, MergeSchema,
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

# v0.4.0: Merge Provenance & Lineage
from .provenance import (
    merge_with_provenance, MergeDecision, MergeRecord,
    ProvenanceLog, export_provenance,
)

# v0.4.0: CRDT Verification Decorator
from .verify import verified_merge, CRDTVerificationError
from .wire import serialize, deserialize, peek_type, wire_size, serialize_batch, deserialize_batch, WireError
from .probabilistic import MergeableHLL, MergeableBloom, MergeableCMS

# v0.6.0: Vector Clocks & Causality
from .clocks import VectorClock, DottedVersionVector, Ordering

# v0.6.0: Schema Evolution
from .schema_evolution import (
    evolve_schema, check_compatibility, widen_type,
    SchemaPolicy, SchemaChange, SchemaEvolutionResult,
)

# v0.6.0: Merkle Trees
from .merkle import MerkleTree, MerkleNode, MerkleDiff, merkle_diff

# v0.6.0: Gossip Protocol
from .gossip import GossipState, GossipEntry, anti_entropy

# v0.6.0: Arrow Merge Engine
from .arrow import ArrowMerge, arrow_merge

# v0.6.0: Async Merge
from .async_merge import amerge, amerge_stream, amerge_sorted_stream

# v0.6.0: Parallel Merge
from .parallel import parallel_merge, parallel_merge_arrow

# v0.7.0: MergeQL — SQL-like CRDT merge interface
from .mergeql import (
    MergeQL, MergeAST, MergePlan, MergeQLResult,
    MergeQLSyntaxError, MergeQLValidationError,
    MergeQLError, MergeQLParser,
)

# v0.7.0: Accelerators (lazy)
def _load_accelerators():
    """Lazy loader for the accelerators sub-package."""
    from crdt_merge import accelerators as _acc
    return _acc

# v0.8.0: Model Merge (lazy — avoids importing numpy at top level)
def _load_model():
    """Lazy loader for the model-merge sub-package."""
    from crdt_merge import model as _model
    return _model

# Optional fast engine
try:
    from crdt_merge._polars_engine import HAS_POLARS
except ImportError:
    HAS_POLARS = False

