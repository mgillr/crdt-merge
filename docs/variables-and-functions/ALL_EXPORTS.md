# All Public Exports — crdt_merge.__init__.py

## Top-Level Exports

```python
from crdt_merge import (
    # Version
    __version__,           # "0.9.2"

    # Core CRDTs (Layer 1)
    GCounter,
    PNCounter,
    LWWRegister,
    ORSet,
    LWWMap,

    # Strategies (Layer 1)
    MergeStrategy,
    LWW,
    MaxWins,
    MinWins,
    UnionSet,
    Priority,
    Concat,
    LongestWins,
    Custom,
    MergeSchema,

    # Clocks (Layer 1)
    VectorClock,
    DottedVersionVector,
    Ordering,

    # Probabilistic (Layer 1)
    MergeableHLL,
    MergeableBloom,
    MergeableCMS,

    # Dedup (Layer 1)
    dedup,
    DedupIndex,
    MinHashDedup,

    # Provenance (Layer 1)
    merge_with_provenance,
    export_provenance,
    ProvenanceTracker,

    # Verify (Layer 1)
    verify_crdt,
    verified_merge,
    CRDTVerifier,

    # DataFrame Engine (Layer 2)
    merge,
    diff,

    # Streaming (Layer 2)
    merge_stream,
    merge_sorted_stream,

    # Arrow (Layer 2)
    arrow_merge,

    # JSON (Layer 2)
    merge_dicts,
    merge_json_lines,

    # Parallel (Layer 2)
    parallel_merge,

    # Async (Layer 2)
    amerge,
    amerge_stream,

    # Wire (Layer 3)
    serialize,
    deserialize,

    # Schema Evolution (Layer 3)
    evolve_schema,
    check_compatibility,
)
```

## Subpackage Exports

```python
# Layer 3
from crdt_merge.gossip import GossipState, anti_entropy
from crdt_merge.merkle import MerkleTree, merkle_diff
from crdt_merge.delta import DeltaStore, compute_delta, apply_delta

# Layer 4
from crdt_merge.model import ModelMerge, ModelMergeSchema, CRDTMergeState
from crdt_merge.model.lora import LoRAMerge
from crdt_merge.model.continual import ContinualMerge
from crdt_merge.model.federated import FederatedMerge
from crdt_merge.model.gpu import GPUMerge
from crdt_merge.model.pipeline import MergePipeline
from crdt_merge.model.safety import SafetyAnalyzer
from crdt_merge.model.heatmap import ConflictHeatmap
from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.context import ContextMerge, MemorySidecar
from crdt_merge.hub import HFMergeHub, AutoModelCard
from crdt_merge.mergeql import MergeQL
from crdt_merge.viz import ConflictTopology
from crdt_merge.datasets_ext import merge_datasets

# Layer 5
from crdt_merge.audit import AuditLog, AuditEntry, AuditedMerge
from crdt_merge.encryption import EncryptedMerge
from crdt_merge.rbac import RBACController, SecureMerge
from crdt_merge.observability import MetricsCollector, ObservedMerge, PrometheusExporter
from crdt_merge.unmerge import UnmergeEngine, ModelUnmerge, GDPRForget

# Layer 6
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport
```
