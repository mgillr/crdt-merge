# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

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

__version__ = "0.9.2"

__all__ = [
    # Core CRDT types
    "GCounter", "PNCounter", "LWWRegister", "ORSet", "LWWMap",
    # DataFrame merge
    "merge", "diff",
    # Deduplication
    "dedup", "dedup_records", "DedupIndex", "MinHashDedup",
    # JSON merge
    "merge_dicts", "merge_json_lines",
    # Composable Merge Strategies
    "MergeStrategy", "LWW", "MaxWins", "MinWins", "UnionSet", "Priority",
    "Concat", "Custom", "LongestWins", "MergeSchema",
    # Streaming Merge Pipeline
    "merge_stream", "merge_sorted_stream", "StreamStats",
    # HuggingFace Datasets (lazy)
    "merge_datasets", "dedup_dataset",
    # Provenance & Lineage
    "merge_with_provenance", "MergeDecision", "MergeRecord",
    "ProvenanceLog", "export_provenance",
    # Verification
    "verified_merge", "CRDTVerificationError",
    # Wire format
    "serialize", "deserialize", "peek_type", "wire_size",
    "serialize_batch", "deserialize_batch", "WireError",
    # Probabilistic
    "MergeableHLL", "MergeableBloom", "MergeableCMS",
    # Vector Clocks & Causality
    "VectorClock", "DottedVersionVector", "Ordering",
    # Schema Evolution
    "evolve_schema", "check_compatibility", "widen_type",
    "SchemaPolicy", "SchemaChange", "SchemaEvolutionResult",
    # Merkle Trees
    "MerkleTree", "MerkleNode", "MerkleDiff", "merkle_diff",
    # Gossip Protocol
    "GossipState", "GossipEntry", "anti_entropy",
    # Arrow Merge Engine
    "ArrowMerge", "arrow_merge",
    # Async Merge
    "amerge", "amerge_stream", "amerge_sorted_stream",
    # Parallel Merge
    "parallel_merge", "parallel_merge_arrow",
    # MergeQL
    "MergeQL", "MergeAST", "MergePlan", "MergeQLResult",
    "MergeQLSyntaxError", "MergeQLValidationError",
    "MergeQLError", "MergeQLParser",
    # Context Memory System
    "MemorySidecar", "ContextManifest", "ContextBloom",
    "ContextConsolidator", "ConsolidatedBlock", "MemoryChunk",
    "ContextMerge", "MergeResult",
    # Agentic AI State Merge
    "AgentState", "SharedKnowledge", "Fact",
    # Enterprise: Unmerge, Audit, Encryption, RBAC
    "UnmergeEngine", "ModelUnmerge", "GDPRForget",
    "AuditLog", "AuditEntry", "AuditedMerge",
    "EncryptedMerge", "EncryptedValue", "StaticKeyProvider", "KeyProvider",
    "RBACController", "SecureMerge", "Permission", "Role", "Policy", "AccessContext",
    # Observability
    "MetricsCollector", "ObservedMerge", "MergeMetric", "HealthCheck",
    "MergeTracer", "DriftDetector", "DriftReport", "PrometheusExporter", "GrafanaDashboard",
    # Compliance (v0.9.2)
    "ComplianceAuditor", "ComplianceReport", "ComplianceFinding", "EUAIActReport",
    # Flower Plugin (v0.9.2)
    "CRDTStrategy", "FlowerCRDTClient", "FlowerAggregator",
    # Polars
    "HAS_POLARS",
]

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

# v0.8.2: Context Memory System
from .context import (
    MemorySidecar, ContextManifest, ContextBloom,
    ContextConsolidator, ConsolidatedBlock, MemoryChunk,
    ContextMerge, MergeResult,
)

# v0.8.2: Agentic AI State Merge
from .agentic import AgentState, SharedKnowledge, Fact

# v0.9.0: Enterprise Modules — Unmerge, Audit, Encryption, RBAC, Observability
from .unmerge import UnmergeEngine, ModelUnmerge, GDPRForget
from .audit import AuditLog, AuditEntry, AuditedMerge
from .encryption import EncryptedMerge, EncryptedValue, StaticKeyProvider, KeyProvider
from .rbac import RBACController, SecureMerge, Permission, Role, Policy, AccessContext
from .observability import MetricsCollector, ObservedMerge, MergeMetric, HealthCheck
from .observability import MergeTracer, DriftDetector, DriftReport, PrometheusExporter, GrafanaDashboard

# v0.9.2: Compliance Auditing
from .compliance import ComplianceAuditor, ComplianceReport, ComplianceFinding, EUAIActReport

# v0.9.2: Flower Federated Learning Plugin
try:
    from .flower_plugin import CRDTStrategy, FlowerCRDTClient, FlowerAggregator
except ImportError:  # pragma: no cover
    pass

# Optional fast engine
try:
    from crdt_merge._polars_engine import HAS_POLARS
except ImportError:
    HAS_POLARS = False

