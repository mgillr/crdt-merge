# Why 6-Layer Architecture?

The rationale behind the six-layer design and how to use each layer independently.

---

## Design Goals

1. **Minimal dependencies per use case**: A data engineer merging DataFrames shouldn't need torch. An ML engineer shouldn't need cryptography.
2. **Progressive adoption**: Start with Layer 1 primitives. Add Layer 2 for DataFrames. Add Layer 5 when going to production. Each layer is independently useful.
3. **Clear separation of concerns**: Math (L1) → Data formats (L2) → Network (L3) → AI (L4) → Enterprise (L5) → Compliance (L6).
4. **Zero overhead when not used**: Enterprise wrappers are opt-in. The core merge path has no audit/encryption overhead if you don't use those features.

---

## The Six Layers

### Layer 1 — Core CRDTs (stdlib only)

The mathematical foundation. Pure Python, zero external dependencies.

```python
# Install: pip install crdt-merge (no extras needed)
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, Priority, UnionSet
from crdt_merge.clocks import VectorClock, DottedVersionVector
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom
from crdt_merge.verify import verify_crdt
```

**Use when**: Embedded systems, serverless functions, edge nodes, or any environment where installing pandas/torch is not possible or desirable.

**LOC**: 2,861 across 7 modules (415 symbols, 140 public endpoints, 0 circular deps).

---

### Layer 2 — Merge Engines (optional pandas/polars/pyarrow)

Bridges Layer 1 strategies to real-world data formats.

```python
# pip install crdt-merge                     (pandas — default)
# pip install crdt-merge[polars]             (Polars)
# pip install crdt-merge[arrow]              (Apache Arrow)
from crdt_merge import merge                  # DataFrame merge
from crdt_merge.streaming import merge_stream # streaming merge
from crdt_merge.parallel import parallel_merge # multi-core
from crdt_merge.arrow import arrow_merge      # Arrow tables
from crdt_merge.parquet import SelfMergingParquet
from crdt_merge.json_merge import merge_dicts
```

**Use when**: Merging DataFrames, CSVs, Parquet files, Arrow tables, or JSON records.

**LOC**: 2,573 across 8 modules (auto-detects pandas vs polars based on input type).

---

### Layer 3 — Sync & Transport (optional network libraries)

When data needs to move between nodes.

```python
from crdt_merge.wire import serialize, deserialize, peek_type  # binary protocol
from crdt_merge.gossip import GossipState                       # P2P sync
from crdt_merge.merkle import MerkleTree, merkle_diff          # content integrity
from crdt_merge.delta import DeltaStore, compute_delta         # bandwidth-efficient sync
```

**Use when**: Building distributed systems, peer-to-peer sync, or multi-region replication.

**LOC**: 2,626 across 4 modules. Wire format is cross-language (Python/TypeScript/Rust/Java compatible).

---

### Layer 4 — AI / Model / Agent (optional torch/transformers)

The largest layer — ML model merging, federated learning, agentic AI.

```python
# pip install crdt-merge[model]
from crdt_merge.model.crdt_state import CRDTMergeState   # CRDT-safe model merge
from crdt_merge.model.core import ModelMerge              # 26+ strategies
from crdt_merge.model.lora import LoRAMerge               # LoRA adapters
from crdt_merge.model.federated import FederatedMerge    # federated learning
from crdt_merge.model.gpu import GPUMerge                 # CUDA/MPS acceleration
from crdt_merge.agentic import AgentState                 # multi-agent state
from crdt_merge.mergeql import MergeQLEngine              # SQL-like interface
```

**Use when**: Federated model training, combining fine-tuned models, multi-agent convergence.

**LOC**: 18,410 across 20+ modules (26 strategies, 8 accelerators, LoRA, continual learning, GPU).

**Why so large**: Model merging is mathematically diverse. Each strategy (SLERP, TIES, DARE, Fisher, evolutionary, etc.) requires its own implementation. See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) §D-007.

---

### Layer 5 — Enterprise Wrappers (optional cryptography)

Production-grade security, auditing, and observability. Implemented as wrappers — zero overhead when not used.

```python
# pip install crdt-merge[enterprise]
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, Policy, MERGER, SecureMerge
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.observability import MetricsCollector, ObservedMerge, MergeTracer, DriftDetector
from crdt_merge.unmerge import GDPRForget, ModelUnmerge

# Compose wrappers — RBAC → Audit → core merge
rbac = RBACController()
rbac.add_policy(Policy(role=MERGER, denied_fields={"ssn", "dob"}))
audit = AuditLog(node_id="node1")
audited = AuditedMerge(audit_log=audit)
result, entry = audited.merge(df_a, df_b, key="id")
assert audit.verify_chain()
```

**Use when**: Production deployments, regulated industries, systems requiring audit trails.

**LOC**: 3,323 across 5 modules (4 encryption backends, RBAC, SHA-256 audit chain, OpenTelemetry, GDPR unmerge).

**Wrapper composition order**: RBAC check → Audit log → Encrypt/decrypt → Metrics → Core merge.

---

### Layer 6 — Verification & Compliance (builds on L5)

Automated regulatory compliance auditing. Reads Layer 5 audit chain, RBAC config, and encryption state to validate against regulatory frameworks.

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport, register_compliance_rule
from crdt_merge.audit import AuditLog

audit = AuditLog(node_id="prod")
auditor = ComplianceAuditor(framework="gdpr", audit_log=audit)
auditor.record_merge("merge-001", input_hash="...", output_hash="...")

report = auditor.validate()
print(f"Passed: {report.passed}")
print(report.to_text())

# Sign report for regulators
import secrets
sig = report.sign(secrets.token_bytes(32))
```

**Use when**: GDPR, HIPAA, SOX, or EU AI Act compliance requirements.

**LOC**: 932 in `compliance.py` (ComplianceAuditor, EUAIActReport, 4 built-in framework rule sets, custom rule registration).

---

## Layer Dependency Rules

```
Layer N may import from Layers 1..N-1 only.
No circular dependencies. (0 confirmed by AST analysis.)

Layer 6  →  Layer 5, Layer 4, Layer 1
Layer 5  →  Layer 4, Layer 2, Layer 1
Layer 4  →  Layer 3, Layer 2, Layer 1
Layer 3  →  Layer 2, Layer 1
Layer 2  →  Layer 1
Layer 1  →  Python stdlib only
```

**Exception**: `crdt_merge/__init__.py` imports from all layers as a facade (the package's flat public API). This is expected — not a violation.

---

## Choosing Your Starting Layer

| Your use case | Start here |
|---|---|
| Just need CRDT math (no pandas/torch) | Layer 1 |
| Merging DataFrames, CSVs, Parquet | Layer 2 |
| Building a distributed sync system | Layer 3 |
| Federated ML, model merging | Layer 4 |
| Production system with audit requirements | Layer 5 |
| GDPR/HIPAA/SOX/EU AI Act compliance | Layer 6 |

See [LAYER_MAP.md](LAYER_MAP.md) for the full per-module inventory.
See [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) for import-level dependencies.
