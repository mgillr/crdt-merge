# Layer Map — Detailed Architecture (v0.9.4)

Six layers, each independently usable, each depending only on lower layers.

---

## Layer 1: Core CRDT Primitives (2,861 LOC)

**Responsibility**: Mathematically proven conflict-free data types and composable merge strategies.

**Dependencies**: Python stdlib only — zero external packages required.

### Modules

| Module | LOC | Exports |
|---|---|---|
| `core.py` | 321 | `GCounter`, `PNCounter`, `LWWRegister`, `ORSet`, `LWWMap` |
| `strategies.py` | 378 | `MergeStrategy`, `LWW`, `MaxWins`, `MinWins`, `UnionSet`, `Concat`, `Priority`, `LongestWins`, `Custom`, `MergeSchema` |
| `clocks.py` | 325 | `VectorClock`, `DottedVersionVector`, `Ordering` |
| `probabilistic.py` | 503 | `MergeableHLL`, `MergeableBloom`, `MergeableCMS` |
| `dedup.py` | 261 | `dedup_records`, `DedupIndex`, `MinHashDedup` |
| `provenance.py` | 384 | `merge_with_provenance`, `ProvenanceTracker`, `ProvenanceLog` |
| `verify.py` | 449 | `verify_crdt`, `verify_commutative`, `@verified_merge`, `CRDTVerifier` |

### Key Properties
- 0 circular dependencies (AST-verified)
- All 8 strategies satisfy: commutative, associative, idempotent
- Deterministic tie-breaking on every strategy
- `MergeStrategy` is the top entropy chokepoint (H=0.722, 9 public endpoints)

### Quick Reference

```python
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins, Custom
from crdt_merge.clocks import VectorClock, DottedVersionVector
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS
from crdt_merge.dedup import dedup_records, DedupIndex
from crdt_merge.verify import verify_crdt
```

---

## Layer 2: Merge Engines (2,573 LOC)

**Responsibility**: Apply Layer 1 strategies to real-world data formats.

**Dependencies**: Layer 1 (`strategies.py`, `schema_evolution.py`) + optional pandas/polars/pyarrow.

### Modules

| Module | LOC | Exports | Optional Deps |
|---|---|---|---|
| `dataframe.py` | 355 | `merge`, `diff` | pandas, polars |
| `streaming.py` | 288 | `merge_stream`, `merge_sorted_stream` | — |
| `arrow.py` | 728 | `ArrowMerge`, `arrow_merge` | pyarrow |
| `parquet.py` | 476 | `SelfMergingParquet` | pyarrow |
| `parallel.py` | 175 | `parallel_merge`, `parallel_merge_arrow` | — |
| `async_merge.py` | 140 | `amerge`, `amerge_stream` | — |
| `json_merge.py` | 105 | `merge_dicts`, `merge_json_lines` | — |
| `_polars_engine.py` | 306 | (internal — not public API) | polars |
| `schema_evolution.py` | 419 | `evolve_schema`, `check_compatibility` | — |

### Quick Reference

```python
from crdt_merge import merge                        # pandas/polars DataFrame merge
from crdt_merge.streaming import merge_stream        # streaming merge
from crdt_merge.arrow import arrow_merge             # Arrow table merge
from crdt_merge.parquet import SelfMergingParquet    # self-merging Parquet store
from crdt_merge.parallel import parallel_merge       # multi-core parallel merge
from crdt_merge.async_merge import amerge            # async merge
from crdt_merge.json_merge import merge_dicts        # JSON/dict merge
from crdt_merge.schema_evolution import evolve_schema
```

---

## Layer 3: Sync & Transport (2,626 LOC)

**Responsibility**: Serialize, transmit, and synchronize merge state across networks.

**Dependencies**: Layer 1 + Layer 2 for some modules. No mandatory external packages.

### Modules

| Module | LOC | Exports |
|---|---|---|
| `wire.py` | 740 | `serialize`, `deserialize`, `peek_type`, `wire_size`, `serialize_batch`, `deserialize_batch`, `WireError`, `supported_versions` |
| `merkle.py` | 554 | `MerkleTree`, `merkle_diff`, `MerkleNode` |
| `gossip.py` | 546 | `GossipState`, `anti_entropy` |
| `delta.py` | 367 | `DeltaStore`, `compute_delta`, `apply_delta` |

### Wire Protocol Format

```
[automatic:4][VERSION:2][TYPE:1][FLAGS:1][LENGTH:4][PAYLOAD:N]

automatic:   b'CRDT'
VERSION: uint16 big-endian (currently 1)
TYPE:    0x01=GCounter, 0x02=PNCounter, 0x03=LWWRegister,
         0x04=ORSet, 0x05=LWWMap, 0x10=Delta, 0x20=Generic
FLAGS:   bit 0 = zlib compressed
LENGTH:  uint32 big-endian
```

### Quick Reference

```python
from crdt_merge.wire import serialize, deserialize, peek_type, wire_size
from crdt_merge.merkle import MerkleTree, merkle_diff
from crdt_merge.gossip import GossipState
from crdt_merge.delta import DeltaStore, compute_delta
```

---

## Layer 4: AI / Model / Agent (18,410 LOC)

**Responsibility**: ML model merging, federated learning, agentic AI state management.

**Dependencies**: Layers 1-3 + optional torch/transformers.

### Sub-packages

| Package / Module | LOC | Exports |
|---|---|---|
| `model/crdt_state.py` | ~800 | `CRDTMergeState` |
| `model/core.py` | ~1,200 | `ModelMerge`, `MergeConfig` |
| `model/strategies/basic.py` | ~400 | `WeightAverage`, `LinearInterpolation`, `SLERP` |
| `model/strategies/weighted.py` | ~400 | `TIES`, `DARE`, `DARETies`, `TaskArithmetic` |
| `model/strategies/evolutionary.py` | ~500 | `EvolutionaryMerge`, `GeneticMerge` |
| `model/strategies/calibration.py` | ~450 | `FisherWeighted`, `RegMean` |
| `model/strategies/subspace.py` | ~400 | `SubspaceMerge` |
| `model/strategies/unlearning.py` | ~350 | `UnlearningMerge` |
| `model/lora.py` | ~600 | `LoRAMerge`, `LoRAMergeSchema` |
| `model/continual.py` | ~700 | `ContinualMerge` |
| `model/federated.py` | ~800 | `FederatedMerge` |
| `model/gpu.py` | ~500 | `GPUMerge` |
| `model/formats.py` | ~400 | `load_model`, `save_model` |
| `model/provenance.py` | ~500 | `ModelProvenanceTracker` |
| `model/safety.py` | ~450 | `SafetyAnalyzer` |
| `context/merge.py` | ~400 | `ContextMerge`, `ContextManifest` |
| `context/consolidator.py` | ~350 | `ContextConsolidator` |
| `context/bloom.py` | ~300 | `ContextBloom` |
| `context/sidecar.py` | ~350 | `MemorySidecar` |
| `agentic.py` | 402 | `AgentState`, `SharedKnowledge` |
| `mergeql.py` | 743 | `MergeQLEngine`, `execute_mergeql` |
| `hub/hf.py` | ~400 | `HFModelTarget`, `push_to_hub` |
| `accelerators/duckdb_udf.py` | ~300 | `register_duckdb_udfs` |
| `accelerators/polars_plugin.py` | ~250 | `CRDTPolarsPlugin` |
| `flower_plugin.py` | 500 | `CRDTFlowerStrategy` |

### Model Strategies (26+)

| Strategy name | Description | BASE required |
|---|---|---|
| `weight_average` | Simple linear interpolation | No |
| `slerp` | Spherical linear interpolation | No |
| `ties` | Trim + Elect + Sign | Yes |
| `dare` | Delta pruning via DARE | Yes |
| `dare_ties` | DARE + TIES combined | Yes |
| `task_arithmetic` | Task vector addition | Yes |
| `fisher_weighted` | Fisher information weighting | No |
| `lora_merge` | LoRA adapter merge | No |
| `evolutionary` | Evolutionary/genetic | No |
| `continual` | Anti-forgetting merge | No |

### Quick Reference

```python
from crdt_merge.model.crdt_state import CRDTMergeState
from crdt_merge.model.core import ModelMerge, MergeConfig
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
from crdt_merge.model.federated import FederatedMerge
from crdt_merge.model.gpu import GPUMerge
from crdt_merge.agentic import AgentState
from crdt_merge.mergeql import MergeQLEngine
from crdt_merge.context.merge import ContextMerge, ContextManifest
from crdt_merge.context.bloom import ContextBloom
```

---

## Layer 5: Enterprise Wrappers (3,323 LOC)

**Responsibility**: Production-grade encryption, audit, RBAC, observability, unmerge.

**Dependencies**: Layers 1-4. Encryption requires `cryptography` package.

### Modules

| Module | LOC | Exports |
|---|---|---|
| `encryption.py` | 669 | `EncryptedMerge`, `StaticKeyProvider`, `RotatingKeyProvider`, `CryptoBackend`, `register_backend` |
| `rbac.py` | 357 | `RBACController`, `Policy`, `Permission`, `Role`, `READER`, `WRITER`, `MERGER`, `ADMIN`, `SecureMerge` |
| `audit.py` | 430 | `AuditLog`, `AuditEntry`, `AuditedMerge` |
| `observability.py` | 1,034 | `MetricsCollector`, `ObservedMerge`, `MergeTracer`, `DriftDetector`, `DriftReport` |
| `unmerge.py` | 833 | `UnmergeEngine`, `GDPRForget`, `ModelUnmerge` |

### Encryption Backends

| Backend | Algorithm | Requires |
|---|---|---|
| `"aes-256-gcm"` | AES-256-GCM | `cryptography` |
| `"chacha20-poly1305"` | ChaCha20-Poly1305 | `cryptography` |
| `"xor-legacy"` | XOR + HMAC-SHA256 | nothing (not production-safe) |
| `"auto"` | Best available | selects aes-256-gcm if available |

### RBAC Roles

| Role constant | Permissions |
|---|---|
| `READER` | READ, AUDIT_READ |
| `WRITER` | READ, WRITE |
| `MERGER` | READ, WRITE, MERGE |
| `ADMIN` | All permissions |

### Quick Reference

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, Policy, MERGER, SecureMerge
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.observability import MetricsCollector, ObservedMerge, MergeTracer, DriftDetector
from crdt_merge.unmerge import GDPRForget, ModelUnmerge
```

---

## Layer 6: Verification & Compliance (932 LOC)

**Responsibility**: Automated regulatory compliance auditing and signed reporting.

**Dependencies**: Layers 1-5 (reads audit chain, encryption config, RBAC config).

### Modules

| Module | LOC | Exports |
|---|---|---|
| `compliance.py` | 932 | `ComplianceAuditor`, `ComplianceReport`, `ComplianceFinding`, `EUAIActReport`, `register_compliance_rule`, `GDPRForget` |

### Supported Frameworks

| Framework string | Regulation | Key class |
|---|---|---|
| `"gdpr"` | EU General Data Protection Regulation | `ComplianceAuditor` |
| `"hipaa"` | US Health Insurance Portability | `ComplianceAuditor` |
| `"sox"` | US Sarbanes-Oxley Act | `ComplianceAuditor` |
| `"eu_ai_act"` | EU AI Act (Annex III high-risk) | `EUAIActReport` |

### Quick Reference

```python
from crdt_merge.compliance import (
    ComplianceAuditor,
    ComplianceReport,
    ComplianceFinding,
    EUAIActReport,
    register_compliance_rule,
)
```

---

## Accelerators (cross-layer)

Accelerators are standalone adapters that expose crdt-merge capabilities to external systems. They depend on Layers 1-2 and optionally Layer 4.

| Accelerator | Module | External System |
|---|---|---|
| DuckDB UDFs | `accelerators/duckdb_udf.py` | DuckDB SQL |
| Polars plugin | `accelerators/polars_plugin.py` | Polars expr API |
| Arrow Flight | `accelerators/flight_server.py` | gRPC Arrow Flight |
| dbt package | `accelerators/dbt_package.py` | dbt macros |
| Airbyte connector | `accelerators/airbyte.py` | Airbyte platform |
| DuckLake | `accelerators/ducklake.py` | DuckLake format |
| SQLite ext | `accelerators/sqlite_ext.py` | SQLite C extension |
| Streamlit UI | `accelerators/streamlit_ui.py` | Streamlit dashboard |

---

*Layer Map v1.1 — updated for v0.9.4*
