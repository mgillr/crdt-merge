# crdt-merge v0.9.2 — Architecture Map

## System Overview

crdt-merge is a **6-layer architecture** with orthogonal Accelerator and CLI subsystems. Each layer builds on the one below, providing increasing levels of abstraction from raw CRDT primitives up to regulatory compliance.

---

## Layer Architecture (Bottom-Up)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 6: VERIFICATION & COMPLIANCE (932 LOC)                          │
│  compliance.py → ComplianceAuditor, EUAIActReport, GDPR/HIPAA/SOX     │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 5: ENTERPRISE WRAPPERS (3,323 LOC)                              │
│  audit.py │ encryption.py │ rbac.py │ observability.py │ unmerge.py    │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 4: AI / MODEL / AGENT (18,410 LOC)                              │
│  model/ (15,464) │ context/ (1,535) │ hub/ (726) │ agentic.py (402)   │
│  mergeql.py (743) │ viz.py (509) │ datasets_ext.py │ flower_plugin.py │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: SYNC & TRANSPORT (2,626 LOC)                                 │
│  wire.py (740) │ merkle.py (554) │ gossip.py (546) │ delta.py (367)   │
│  schema_evolution.py (419)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: MERGE ENGINES (3,984 LOC)                                    │
│  dataframe.py (444) │ arrow.py (969) │ streaming.py (362)              │
│  parquet.py (625) │ parallel.py (251) │ async_merge.py (188)           │
│  json_merge.py (145) │ _polars_engine.py (433)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 1: CORE CRDT PRIMITIVES (2,614 LOC)                             │
│  core.py (320) │ strategies.py (377) │ clocks.py (324)                 │
│  probabilistic.py (502) │ dedup.py (260) │ provenance.py (383)        │
│  verify.py (448)                                                        │
└─────────────────────────────────────────────────────────────────────────┘
         ↑                                              ↑
    ┌────┴──────────────┐                ┌──────────────┴────────┐
    │ ACCELERATORS      │                │ CLI                    │
    │ (4,465 LOC)       │                │ (548 LOC)              │
    │ DuckDB, dbt,      │                │ migrate.py             │
    │ Polars, Flight,   │                │ (MergeKit→Python)      │
    │ Airbyte, DuckLake,│                └────────────────────────┘
    │ SQLite, Streamlit  │
    └────────────────────┘
```

---

## Layer Details

### Layer 1: Core CRDT Primitives (2,614 LOC)
**Purpose**: Mathematical foundations — every other layer depends on this.

| Module | LOC | Key Exports |
|--------|-----|-------------|
| `core.py` | 320 | `GCounter`, `PNCounter`, `LWWRegister`, `ORSet`, `LWWMap` |
| `strategies.py` | 377 | `LWW`, `MaxWins`, `MinWins`, `UnionSet`, `Priority`, `Concat`, `LongestWins`, `Custom`, `MergeSchema` |
| `clocks.py` | 324 | `VectorClock`, `DottedVersionVector`, `Ordering` |
| `probabilistic.py` | 502 | `MergeableHLL`, `MergeableBloom`, `MergeableCMS` |
| `dedup.py` | 260 | `dedup()`, `DedupIndex`, `MinHashDedup` |
| `provenance.py` | 383 | `merge_with_provenance()`, `ProvenanceTracker`, `export_provenance()` |
| `verify.py` | 448 | `verify_crdt()`, `@verified_merge`, `CRDTVerifier` |

**Dependencies**: Python stdlib only (zero external dependencies)

**CRDT Properties Guaranteed**:
- Commutative: `merge(A, B) == merge(B, A)`
- Associative: `merge(merge(A, B), C) == merge(A, merge(B, C))`
- Idempotent: `merge(A, A) == A`

---

### Layer 2: Merge Engines (3,984 LOC)
**Purpose**: Apply CRDT strategies to real-world data formats (DataFrames, Arrow, Parquet, streams).

| Module | LOC | Key Exports |
|--------|-----|-------------|
| `dataframe.py` | 444 | `merge()`, `diff()` |
| `streaming.py` | 362 | `merge_stream()`, `merge_sorted_stream()`, `StreamStats` |
| `arrow.py` | 969 | `Arrow`, `ArrowBatch`, `arrow_merge()` |
| `parquet.py` | 625 | `SelfMergingParquet`, `ParquetMerge` |
| `parallel.py` | 251 | `parallel_merge()`, `ParallelMerge` |
| `async_merge.py` | 188 | `amerge()`, `amerge_stream()`, `AsyncMerge` |
| `json_merge.py` | 145 | `merge_dicts()`, `merge_json_lines()` |
| `_polars_engine.py` | 433 | Polars engine internals |

**Dependencies**: Layer 1 (core, strategies), pandas, pyarrow (optional), polars (optional)

---

### Layer 3: Sync & Transport (2,626 LOC)
**Purpose**: Move merge state across networks — serialization, synchronization protocols, schema versioning.

| Module | LOC | Key Exports |
|--------|-----|-------------|
| `wire.py` | 740 | `serialize()`, `deserialize()`, `peek()`, binary protocol |
| `merkle.py` | 554 | `MerkleTree`, `merkle_diff()` |
| `gossip.py` | 546 | `GossipState`, `anti_entropy()` |
| `delta.py` | 367 | `DeltaStore`, `compute_delta()`, `apply_delta()` |
| `schema_evolution.py` | 419 | `evolve_schema()`, `check_compatibility()` |

**Dependencies**: Layer 1, Layer 2 (for merge operations)

---

### Layer 4: AI / Model / Agent (18,410 LOC)
**Purpose**: ML model merging (26+ strategies), agentic AI state management, HuggingFace Hub integration.

| Module/Package | LOC | Key Exports |
|--------|-----|-------------|
| `model/` | 15,464 | `ModelMerge`, `CRDTMergeState`, 26+ strategy classes, `LoRAMerge`, `ContinualMerge`, `FederatedMerge`, `GPUMerge`, `MergePipeline`, `SafetyAnalyzer`, `ConflictHeatmap` |
| `context/` | 1,535 | `ContextMerge`, `MemorySidecar`, `ContextConsolidator`, `ContextBloom`, `ContextManifest` |
| `hub/` | 726 | `HFMergeHub`, `AutoModelCard` |
| `agentic.py` | 402 | `AgentState`, `SharedKnowledge` |
| `mergeql.py` | 743 | `MergeQL` DSL |
| `viz.py` | 509 | `ConflictTopology`, D3 export |
| `datasets_ext.py` | 106 | `merge_datasets()` |
| `flower_plugin.py` | 500 | Flower FL integration |

**Dependencies**: Layer 1, Layer 2, Layer 3, torch (optional), transformers (optional)

---

### Layer 5: Enterprise Wrappers (3,323 LOC)
**Purpose**: Production-grade wrappers adding audit trails, encryption, RBAC, observability, and GDPR compliance.

| Module | LOC | Key Exports |
|--------|-----|-------------|
| `audit.py` | 430 | `AuditLog`, `AuditEntry`, `AuditedMerge` (SHA-256 chain) |
| `encryption.py` | 669 | `EncryptedMerge`, 4 crypto backends, key rotation |
| `rbac.py` | 357 | `RBACController`, `SecureMerge` |
| `observability.py` | 1,034 | `MetricsCollector`, `ObservedMerge`, `PrometheusExporter`, `GrafanaDashboard`, `MergeTracer`, `DriftDetector`, `HealthCheck` |
| `unmerge.py` | 833 | `UnmergeEngine`, `ModelUnmerge`, `GDPRForget` |

**Dependencies**: All lower layers

**Documentation Status**: **ZERO existing docs** — fully documented in this repo for the first time.

---

### Layer 6: Verification & Compliance (932 LOC)
**Purpose**: Regulatory compliance auditing and reporting.

| Module | LOC | Key Exports |
|--------|-----|-------------|
| `compliance.py` | 932 | `ComplianceAuditor`, `EUAIActReport`, GDPR/HIPAA/SOX auditing |

**Dependencies**: Layer 5 (audit, encryption), Layer 4 (model)

**Documentation Status**: **ZERO existing docs** — fully documented in this repo for the first time.

---

### Accelerators (4,465 LOC)
**Purpose**: Performance-optimized integrations with external databases and tools.

| Module | ~LOC | Purpose |
|--------|------|---------|
| `duckdb_udf.py` | ~500 | DuckDB UDF integration |
| `dbt_package.py` | ~450 | dbt macro package |
| `polars_plugin.py` | ~600 | Polars engine plugin |
| `flight_server.py` | ~400 | Arrow Flight distributed server |
| `airbyte.py` | ~350 | Airbyte ETL connector |
| `ducklake.py` | ~400 | DuckLake (DuckDB + Data Lake) |
| `sqlite_ext.py` | ~450 | SQLite extension |
| `streamlit_ui.py` | ~315 | Streamlit dashboard components |

---

### CLI (548 LOC)
| Module | LOC | Purpose |
|--------|-----|---------|
| `cli/migrate.py` | 548 | MergeKit YAML → Python migration tool |

---

## Data Flow

```
                    ┌─────────────────────────────┐
                    │  External Data Sources       │
                    │  (DataFrames, Parquet, JSON,  │
                    │   ML Models, Agent State)     │
                    └──────────────┬────────────────┘
                                   │
                    ┌──────────────────────────────┐
                    │  Layer 2: Merge Engines        │
                    │  merge(), merge_stream(),      │
                    │  arrow_merge(), etc.           │
                    │                                │
                    │  ┌──────────────────────────┐  │
                    │  │ Layer 1: CRDT Core       │  │
                    │  │ MergeSchema → per-field   │  │
                    │  │ strategy resolution       │  │
                    │  └──────────────────────────┘  │
                    └──────────────┬────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
    ┌───────────────────┐  ┌───────────────┐  ┌────────────────┐
    │ Layer 3: Transport │  │ Layer 4: AI    │  │ Layer 5:        │
    │ serialize()        │  │ ModelMerge()   │  │ Enterprise      │
    │ gossip sync        │  │ AgentState()   │  │ AuditedMerge()  │
    │ delta compress     │  │ MergeQL        │  │ EncryptedMerge()│
    └────────────────────┘  └────────────────┘  │ SecureMerge()   │
                                                 └────────┬────────┘
                                                          │
                                                 ┌────────────────┐
                                                 │ Layer 6:        │
                                                 │ Compliance      │
                                                 │ ComplianceAudit │
                                                 │ EUAIActReport   │
                                                 └─────────────────┘
```

---

## LOC Summary

| Component | LOC | % of Total |
|-----------|-----|-----------|
| Layer 1: Core CRDT | 2,614 | 8.0% |
| Layer 2: Engines | 3,984 | 12.1% |
| Layer 3: Transport | 2,626 | 8.0% |
| Layer 4: AI/Model | 18,410 | 56.2% |
| Layer 5: Enterprise | 3,323 | 10.1% |
| Layer 6: Compliance | 932 | 2.8% |
| Accelerators | 4,465 | — |
| CLI + __init__ | 795 | — |
| **Total (AST actual)** | **29,768** | — |

> **Note**: The codebase inventory previously reported 38,157 LOC. AST-verified total is 29,768 LOC. Full discrepancy analysis in gap-analysis/INVENTORY_VS_ACTUAL.md.

---

*Architecture Map v1.0 — crdt-merge v0.9.2*
