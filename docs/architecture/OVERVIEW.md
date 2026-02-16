# System Overview — crdt-merge v0.9.2

## What is crdt-merge?

crdt-merge is a Python library that applies **Conflict-Free Replicated Data Type (CRDT)** mathematics to real-world data merging problems. It provides:

1. **CRDT Primitives**: Mathematically proven data structures (GCounter, PNCounter, LWWRegister, ORSet, LWWMap) that guarantee eventual consistency without coordination.

2. **Merge Engines**: Apply CRDT strategies to DataFrames, Arrow tables, Parquet files, JSON, and streaming data.

3. **Sync Protocols**: Wire format, gossip protocol, Merkle tree sync, and delta compression for distributed systems.

4. **Model Merging**: 26+ strategies for merging ML model weights, supporting LoRA, continual learning, federated learning, and GPU acceleration.

5. **Enterprise Features**: Audit trails, encryption, RBAC, observability, and GDPR-compliant unmerge.

6. **Compliance**: Automated regulatory auditing for GDPR, HIPAA, SOX, and EU AI Act.

---

## Design Philosophy

- **Mathematical Correctness First**: Every merge operation is commutative, associative, and idempotent
- **Zero-Dependency Core**: Layer 1 uses only Python stdlib
- **Progressive Enhancement**: Each layer adds capabilities without breaking lower layers
- **Strategy Pattern**: Per-field conflict resolution via composable MergeSchema
- **Transport Agnostic**: Core merge logic is independent of serialization format

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Production LOC | 32,787 (AST-verified) |
| Modules | 78 |
| Classes | 201 |
| Functions | 289 |
| Methods | 996 |
| Test Files | 90+ |
| Accelerators | 8 |

---

## Layer 1 Re-Verified Metrics (GDEPA + RREA Engines — 2026-03-31)

| Metric | Value |
|--------|-------|
| Layer 1 LOC | 2,861 |
| Layer 1 Modules | 8 (all imported successfully) |
| Layer 1 Total Symbols | 415 |
| Layer 1 Public Endpoints | 140 |
| Layer 1 Total Graph Edges | 1,355 |
| Inherited Methods (runtime) | 10 |
| Runtime-Only Symbols | 40 |
| Circular Dependencies | 0 |
| Truly Dead Code | 2 (`_load_accelerators`, `_load_model`) |
| Cross-Layer Symbols | 16 (used by L2–L6, not dead) |
| Undocumented Inherited | 2 (CRDTVerificationError: `add_note`, `with_traceback`) |

### Entropy Analysis (RREA Ping Entropy)

| Chokepoint | Combined H | Shannon | Ping | Endpoints |
|-----------|-----------|---------|------|-----------|
| **MergeStrategy** | **0.722** | 0.4446 | 0.9994 | 9 |
| MergeRecord | 0.159 | 0.1403 | 0.1775 | 2 |
| MergeDecision | 0.159 | 0.1403 | 0.1775 | 2 |
| ProvenanceLog | 0.159 | 0.1403 | 0.1775 | 2 |

> **Key finding:** MergeStrategy (not VerificationResult) is the true #1 chokepoint when using Ping Entropy. Previous analysis using only Shannon entropy ranked VerificationResult first; the combined metric with Ping Entropy (which models information flow attenuation) correctly identifies MergeStrategy as the critical convergence point where 9 public endpoints funnel through a single abstract base class.

---

*System Overview v1.2 — updated with GDEPA runtime inspect + RREA Ping Entropy engine results*
