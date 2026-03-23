# crdt-merge Documentation

> **Production-grade CRDT merging for data, ML models, and distributed systems.**

| | |
|---|---|
| **Version** | 0.9.4 |
| **Architecture** | 6-layer + Accelerators + CLI |
| **Codebase** | 44,304 LOC · 104 modules · 212 classes · 1,586 functions |
| **Guide tests** | 309 tests across 7 guide test suites — all passing |
| **License** | BUSL-1.1 → Apache 2.0 (2028-03-29) |

---

## Guides

25 in-depth guides covering every major use case. Every code example is verified by an automated test suite.

### Data & Records

| Guide | What it covers |
|---|---|
| [CRDT Fundamentals](guides/crdt-fundamentals.md) | CRDT theory, OR-Set, LWW, G-Counter |
| [CRDT Primitives Reference](guides/crdt-primitives-reference.md) | Working examples for every primitive type |
| [CRDT Verification Toolkit](guides/crdt-verification-toolkit.md) | `verify_crdt`, `verify_commutative`, property testing |
| [Merge Strategies](guides/merge-strategies.md) | LWW, MaxWins, MinWins, UnionSet, Priority, Custom, and more |
| [Schema Evolution](guides/schema-evolution.md) | Backwards-compatible schema changes |
| [MergeQL — Distributed Knowledge](guides/mergeql-distributed-knowledge.md) | SQL-like merge interface |
| [Probabilistic CRDT Analytics](guides/probabilistic-crdt-analytics.md) | HyperLogLog, MinHash, CMS |
| [Performance Tuning](guides/performance-tuning.md) | `parallel_merge`, chunking, DuckDB, profiling |
| [Troubleshooting](guides/troubleshooting.md) | Common errors and fixes |

### Transport & Sync

| Guide | What it covers |
|---|---|
| [Wire Protocol](guides/wire-protocol.md) | Binary format, `serialize`/`deserialize`, `peek_type` |
| [Gossip & Serverless Sync](guides/gossip-serverless-sync.md) | `GossipState`, peer-to-peer propagation |
| [Delta Sync & Merkle Verification](guides/delta-sync-merkle-verification.md) | Bandwidth-efficient sync, content integrity |

### AI & ML Models

| Guide | What it covers |
|---|---|
| [Federated Model Merging](guides/federated-model-merging.md) | `CRDTMergeState`, 26 strategies, no parameter server |
| [Model Merge Strategies](guides/model-merge-strategies.md) | SLERP, TIES, DARE, DARE-TIES, Fisher, and more |
| [Model CRDT Matrix](guides/model-crdt-matrix.md) | Strategy × CRDT-compliance comparison table |
| [LoRA Adapter Merging](guides/lora-adapter-merging.md) | `LoRAMerge`, `LoRAMergeSchema`, per-layer strategies |
| [Continual Learning Without Forgetting](guides/continual-learning-without-forgetting.md) | `ContinualMerge`, replay, EWC integration |

### Agentic & Context

| Guide | What it covers |
|---|---|
| [Convergent Multi-Agent AI](guides/convergent-multi-agent-ai.md) | `AgentState`, `ContextMerge`, `ContextManifest` |
| [Agentic Memory at Scale](guides/agentic-memory-at-scale.md) | `ContextBloom`, `MemorySidecar`, budget-bounded merge |

### Privacy, Provenance & Compliance

| Guide | What it covers |
|---|---|
| [Provenance — Complete AI](guides/provenance-complete-ai.md) | `AuditLog`, `AuditedMerge`, tamper-evident chain |
| [Right to Forget in AI](guides/right-to-forget-in-ai.md) | CRDT `remove()`, GDPR erasure, model unmerge |
| [Privacy-Preserving Merge](guides/privacy-preserving-merge.md) | `EncryptedMerge`, field-level encryption, RBAC |
| [Security Hardening](guides/security-hardening.md) | Threat model, key rotation, audit integration |
| [Security Guide](guides/security-guide.md) | Encryption backends, `StaticKeyProvider`, RBAC policies |
| [Compliance Guide](guides/compliance-guide.md) | GDPR Art.5, HIPAA PHI, SOX, EU AI Act |

---

## 30-Second Demo

```python
import pandas as pd
from crdt_merge import merge, MergeSchema, LWW, MaxWins

df_a = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Charlie"], "score": [80, 70], "_ts": [1000.0, 1000.0]})
df_b = pd.DataFrame({"id": [1, 3], "name": ["Bob",   "Diana"  ], "score": [90, 85], "_ts": [2000.0, 1000.0]})

schema = MergeSchema(name=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="_ts")
#    id     name  score      _ts
# 0   1      Bob     90   2000.0  ← Bob (newer), 90 (higher)
# 1   2  Charlie     70   1000.0  ← Only in df_a
# 2   3    Diana     85   1000.0  ← Only in df_b
```

**Model merging:**

```python
import numpy as np
from crdt_merge.model import CRDTMergeState

# Three teams fine-tuning the same base — merge in any order, get identical result
team_a = CRDTMergeState("weight_average")
team_b = CRDTMergeState("weight_average")
team_c = CRDTMergeState("weight_average")

team_a.add(math_tensors,      model_id="llama-math-v2",   weight=0.4)
team_b.add(code_tensors,      model_id="llama-code-v4",   weight=0.35)
team_c.add(reasoning_tensors, model_id="llama-reason-v1", weight=0.25)

team_a.merge(team_b).merge(team_c)  # in-place, returns self

assert team_a.state_hash == team_b.merge(team_c).state_hash  # identical regardless of order
merged = team_a.resolve()
```

---

## Learning Path

**New to crdt-merge?**

1. [CRDT Fundamentals](guides/crdt-fundamentals.md) — understand OR-Sets and convergence (15 min)
2. [CRDT Primitives Reference](guides/crdt-primitives-reference.md) — hands-on with every type (20 min)
3. [Merge Strategies](guides/merge-strategies.md) — pick the right strategy for your data (10 min)
4. Choose your domain:
   - **Data/DataFrames** → [MergeQL](guides/mergeql-distributed-knowledge.md), [Performance Tuning](guides/performance-tuning.md)
   - **ML Models** → [Federated Model Merging](guides/federated-model-merging.md), [LoRA](guides/lora-adapter-merging.md)
   - **Distributed agents** → [Convergent Multi-Agent AI](guides/convergent-multi-agent-ai.md)
   - **Compliance** → [Provenance](guides/provenance-complete-ai.md), [Compliance Guide](guides/compliance-guide.md)

---

## Repository Layout

```
docs/
├── guides/                  ← 25 in-depth guides (all code verified by tests)
├── api-reference/           ← Complete API reference (layers 1–6, accelerators, CLI)
├── architecture/            ← System overview, layer map, data flow, design decisions
├── getting-started/         ← Installation, quickstart, core concepts
├── cookbook/                ← Practical recipes and patterns
├── CRDT_ARCHITECTURE.md     ← Full mathematical proof of CRDT compliance
├── ARCHITECTURE_MAP.md      ← Annotated codebase map
└── benchmarks/              ← A100 GPU performance, stress test reports
```

---

## Architecture

crdt-merge uses a strict **6-layer architecture** — each layer is independently testable and composable:

| Layer | Module | Responsibility |
|---|---|---|
| 1 | `crdt_merge.core` | OR-Set, G-Counter, LWW-Register, VectorClock |
| 2 | `crdt_merge` | DataFrame/JSON merge, strategies, MergeQL |
| 3 | `crdt_merge.wire` / `.gossip` / `.merkle` | Transport, serialisation, content integrity |
| 4 | `crdt_merge.model` | ML model merging, CRDTMergeState, 26 strategies |
| 5 | `crdt_merge.encryption` / `.rbac` / `.metrics` | Security, access control, observability |
| 6 | `crdt_merge.compliance` | GDPR, HIPAA, SOX, EU AI Act |
| + | `crdt_merge.context` / `.agentic` | Agent memory, ContextBloom, ContextManifest |
| + | Accelerators | DuckDB, dbt, Polars, Airbyte, Spark |

Full proof: [CRDT_ARCHITECTURE.md](CRDT_ARCHITECTURE.md)

---

## By Role

| Role | Start here |
|---|---|
| **Developer** | [Quickstart](getting-started/QUICKSTART.md) → [Primitives Reference](guides/crdt-primitives-reference.md) |
| **ML Engineer** | [Federated Model Merging](guides/federated-model-merging.md) → [LoRA](guides/lora-adapter-merging.md) |
| **Data Engineer** | [Merge Strategies](guides/merge-strategies.md) → [MergeQL](guides/mergeql-distributed-knowledge.md) |
| **Architect** | [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md) → [api-reference/](api-reference/) |
| **Compliance** | [Compliance Guide](guides/compliance-guide.md) → [Right to Forget](guides/right-to-forget-in-ai.md) |
| **Security** | [Security Guide](guides/security-guide.md) → [Privacy-Preserving Merge](guides/privacy-preserving-merge.md) |

---

*crdt-merge v0.9.4 · April 2026*
