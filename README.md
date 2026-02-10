<div align="center">

<h1>crdt-merge</h1>

<p><strong>The first merge library where every operation is mathematically guaranteed to converge.</strong><br/>
Tabular data. Neural network weights. Distributed agents. One unified CRDT layer.</p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.2-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-3%2C254%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)

```
pip install crdt-merge
```

</div>

---

## The Problem Every Data Engineer and ML Researcher Has

You're merging data or models from multiple sources — pipelines, replicas, collaborators, distributed nodes. You apply your merge. It looks right. But:

- Run it in a different **order**? Different result.
- Apply the same patch **twice**? Different result.
- Merge A into B then B into C vs. A into (B into C)? **Different result.**

This is not a bug in your code. It is a fundamental property of nearly every merge algorithm ever written — including the ones everyone uses. **crdt-merge is the fix.**

---

## What Is crdt-merge?

`crdt-merge` is a Python library that enforces **CRDT (Conflict-free Replicated Data Type)** correctness across every merge operation — for tabular data, neural network model weights, and AI agent memory.

A CRDT-compliant merge satisfies three algebraic laws:

| Law | Meaning | Why It Matters |
|---|---|---|
| **Commutativity** | `merge(A, B) == merge(B, A)` | Order of inputs never changes the outcome |
| **Associativity** | `merge(merge(A,B),C) == merge(A,merge(B,C))` | Grouping never changes the outcome |
| **Idempotency** | `merge(A, A) == A` | Applying the same data twice is safe |

When all three hold, your distributed system **always converges** — no coordination, no locking, no central arbiter required.

> [Deep dive: How we proved all 26 strategies are CRDT-compliant — 7 architectures tested, full mathematical proofs](docs/CRDT_ARCHITECTURE.md)

---

## What crdt-merge IS — and IS NOT

### What It IS

| Category | crdt-merge does this |
|---|---|
| **Tabular merge** | CRDT-correct merging of DataFrames, Parquet, Arrow, DuckDB, Polars, Delta Lake |
| **Model merge** | CRDT-correct SLERP, TIES, DARE, Fisher, LoRA, evolutionary, and 21 more strategies |
| **Agent memory** | CRDT-merged context for multi-agent systems (CrewAI, AutoGen, LangGraph) |
| **Distributed sync** | Gossip protocol, vector clocks, Merkle verification, Apache Arrow Flight |
| **Audit and provenance** | Per-field conflict history, full merge lineage, `@verified_merge` decorator, immutable hash-chain audit log |
| **Schema evolution** | Non-breaking column additions, type widening, backwards-compatible deltas |
| **Streaming** | Incremental merge, real-time CRDT state updates |
| **Federated learning** | CRDT-safe weight aggregation without a parameter server |

### What It IS NOT

| What you might assume | Reality |
|---|---|
| A DataFrame merge wrapper around `pandas.merge()` | No. It's a full CRDT state machine with provenance |
| A model training framework | No. It operates on already-trained weights — post-training only |
| A model hub or registry | No. It handles the *merge logic*, not storage or serving |
| A real-time collaboration tool | No. For collaborative text editing, see [Yjs](https://github.com/yjs/yjs) or [Loro](https://github.com/loro-dev/loro) |
| A database | No. No persistence, no queries, no networking. It's a library |
| A workflow orchestrator (Airflow, Prefect) | No. Use those to *call* crdt-merge, not replace it |
| Slow because of "CRDT overhead" | No. Overhead is **< 0.5ms** per merge regardless of model size |
| Only for AI/ML workloads | No. The tabular core works on any structured data |
| Another mergekit wrapper | No. crdt-merge uses a two-layer architecture that mergekit cannot provide |

---

## By the Numbers

<div align="center">

| Stat | Value |
|:---|:---:|
| Test suite | **3,041 tests, 0 failures** |
| Property-based (Hypothesis) tests | **137** |
| CRDT compliance tests | **1,200 / 1,200 passing** |
| Merge strategies | **26 strategies** across tabular + model domains |
| Encryption backends | **4** (AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305, XOR legacy) |
| CRDT overhead | **< 0.5ms** per merge operation |
| Architectures evaluated during R&D | **7 candidates, 1 production winner** |
| Core modules | **51 across 3 namespaces** |
| Ecosystem accelerators | **8** |
| Benchmark verified on | **A100 GPU (Colab), v0.6.0 -- v0.8.3** |
| Model speedup vs. naive baseline | **38.8x** |
| Lines of source | **~37,800** |
| Python versions | **3.9 -- 3.12** |

</div>

---

## Why Standard Merge Algorithms Fail (And How We Fixed It)

Most model merge algorithms **fail the basic laws of distributed systems** on raw tensors. We proved this formally:

| Strategy | Commutative | Associative | Idempotent | CRDT? |
|:---------|:-----------:|:-----------:|:----------:|:-----:|
| WeightAverage | ✓ | ✗ | ✓ | ✗ |
| SLERP | ✗ | ✗ | ✓ | ✗ |
| TIES | ~ | ✗ | ✗ | ✗ |
| DARE | ✗ | ✗ | ✗ | ✗ |
| Fisher Merge | ✓ | ✗ | ✗ | ✗ |
| **crdt-merge (two-layer)** | **✓** | **✓** | **✓** | **✅** |

**The insight:** Don't try to make the strategy itself CRDT-compliant on raw tensors (mathematically near-impossible). Instead, use a **two-layer architecture**:

- **Layer 1 — `CRDTMergeState`**: Manages a *set* of model contributions. Set union is trivially commutative, associative, and idempotent.
- **Layer 2 — Strategy**: A pure deterministic function over the set. Same inputs, same output, every time.

We tested 7 architectures before landing on this. [Read the full proof.](docs/CRDT_ARCHITECTURE.md)

---

## Architecture

crdt-merge uses a **two-layer OR-Set architecture** — the result of evaluating 7 candidate designs during R&D. It is the only approach that achieves full CRDT compliance across all 26 merge strategies without sacrificing performance or API simplicity.

```
┌─────────────────────────────────────────────┐
│  Layer 1: CRDTMergeState (OR-Set)            │
│  • Manages a set of contributions            │
│  • Set union: commutative ✓ assoc ✓ idem ✓  │
│  • Merkle hash + vector clock per entry      │
└────────────────────┬────────────────────────┘
                     │ deterministic set
                     ▼
┌─────────────────────────────────────────────┐
│  Layer 2: Strategy (pure function)           │
│  • SLERP / TIES / DARE / Fisher / ...        │
│  • Same input set → same output, always      │
│  • Swappable without breaking CRDT laws      │
└─────────────────────────────────────────────┘
```

> **[Read the full architecture document](docs/CRDT_ARCHITECTURE.md)** — mathematical proofs, 7 alternative architectures, benchmark results, compliance matrix.

---

## Quick Start

### Tabular Data

```python
from crdt_merge import CRDTDataFrame

# Two replicas, modified independently
replica_a = CRDTDataFrame(df_a, node_id="node-a")
replica_b = CRDTDataFrame(df_b, node_id="node-b")

# Merge — commutative, associative, idempotent
merged = replica_a.merge(replica_b)

# Full provenance
print(merged.conflict_log())
```

### Model Weights

```python
from crdt_merge.model import CRDTMergeState

# Add model contributions — order doesn't matter
state = CRDTMergeState()
state.add("llama-ft-v1", weights_a, metadata={"task": "summarisation"})
state.add("llama-ft-v2", weights_b, metadata={"task": "summarisation"})
state.add("llama-ft-v3", weights_c, metadata={"task": "summarisation"})

# Merge with any strategy — CRDT laws guaranteed
merged_model = state.merge(strategy="slerp")     # or ties, dare, fisher...
merged_model = state.merge(strategy="ties")      # same result regardless of add() order
```

### Verify CRDT Compliance Yourself

```python
from crdt_merge import verified_merge

@verified_merge
def my_merge(a, b):
    return your_merge_logic(a, b)

# Raises CRDTViolationError if commutativity, associativity,
# or idempotency is broken — automatically tested on every call
```

---

## Enterprise Features

> New in v0.9.0 — zero external dependencies, composable with each other and existing merge pipelines.

### Merge Undo & GDPR Compliance
```python
from crdt_merge.unmerge import UnmergeEngine, GDPRForget

# Selective rollback of a contributor's records
engine = UnmergeEngine()
rolled_back = engine.unmerge(merged_records, provenance_log, remove_source="node-2", key_field="id")

# GDPR right-to-be-forgotten
gdpr = GDPRForget()
result = gdpr.forget_data(merged_records, provenance_log, contributor="user-123", key_field="id")
print(result)  # ForgetResult with scrubbed records and compliance metadata
```

### Audit Trail
```python
from crdt_merge.audit import AuditedMerge

audited = AuditedMerge(node_id="server-1")
result, entry = audited.merge(left, right, key="id")
assert audited.audit_log.verify_chain()  # SHA-256 hash chain tamper detection
```

### Field-Level Encryption
```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import os

provider = StaticKeyProvider(key=os.urandom(32))

# Auto-selects best available backend (AES-256-GCM > AES-GCM-SIV > ChaCha20 > XOR)
em = EncryptedMerge(provider, backend="auto")

# Or choose explicitly: "aes-256-gcm", "aes-256-gcm-siv", "chacha20-poly1305", "xor"
em = EncryptedMerge(provider, backend="aes-256-gcm-siv")  # nonce-misuse resistant

encrypted = em.encrypt_records(records, fields=["salary", "ssn"])
merged = em.merge_encrypted(enc_left, enc_right, key="id")
decrypted = em.decrypt_records(merged, fields=["salary", "ssn"])

# Cross-backend decryption works automatically — migrate backends without re-encrypting
```

### Role-Based Access Control
```python
from crdt_merge.rbac import RBACController, SecureMerge, Policy, AccessContext, READER

rbac = RBACController()
rbac.add_policy("analyst", Policy(role=READER, denied_fields={"salary", "ssn"}))
secure = SecureMerge(rbac)
result = secure.merge(left, right, key="id",
    context=AccessContext(node_id="analyst", role=READER))
```

### Observability & Health Monitoring
```python
from crdt_merge.observability import ObservedMerge, HealthCheck

observed = ObservedMerge(node_id="prod-1")
result, metric = observed.merge(left, right, key="id")
print(f"Merge took {metric.duration_ms:.1f}ms, {metric.conflicts_resolved} conflicts resolved")

health = HealthCheck(observed.collector)
status = health.check_health()  # {"status": "healthy", ...}
```

---

## What's New in v0.9.1 — "The Iron Dome Release"
## What's New in v0.9.2 — "The Completion Release"

Delivers the compliance, observability extensions, and federated learning modules that complete the enterprise layer.

### Compliance Suite

Full regulatory compliance engine with pluggable rule sets and automated report generation:

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor()
report = auditor.audit(merge_result, policy="strict")
print(report.summary())  # {"passed": 12, "warnings": 2, "failures": 0}

# EU AI Act report with full provenance chain
eu_report = EUAIActReport.generate(merge_result, model_card=card)
eu_report.export("compliance_report.json")
```

| Class | Purpose |
|-------|---------|
| **ComplianceAuditor** | Pluggable rule engine — SOC 2, HIPAA, EU AI Act checks |
| **ComplianceFinding** | Structured finding with severity, category, remediation |
| **ComplianceReport** | Aggregate report with pass/warn/fail summary |
| **EUAIActReport** | EU AI Act Article 11 transparency report generator |

### Extended Observability

OpenTelemetry-compatible distributed tracing, Prometheus metrics export, Grafana dashboard generation, and merge drift detection:

```python
from crdt_merge.observability import MergeTracer, PrometheusExporter, DriftDetector

tracer = MergeTracer(service_name="ml-pipeline")
with tracer.trace_merge("model-combine") as span:
    result = merger.merge(a, b)
    span.set_attribute("conflicts", result.conflicts)

# Export Prometheus metrics
exporter = PrometheusExporter(prefix="crdt_merge")
print(exporter.render())  # Prometheus text format

# Detect merge drift over time
detector = DriftDetector(window_size=100)
detector.record(result)
drift_report = detector.analyze()
```

| Class | Purpose |
|-------|---------|
| **MergeTracer** | OTel-compatible span generation for merge operations |
| **DriftDetector** | Statistical drift detection across merge windows |
| **DriftReport** | Structured drift analysis with severity scoring |
| **PrometheusExporter** | `/metrics` endpoint in Prometheus text format |
| **GrafanaDashboard** | Auto-generated Grafana JSON dashboard |

### Flower Federated Learning Plugin

Native integration with the Flower federated learning framework — CRDT-guaranteed aggregation across distributed clients:

```python
from crdt_merge.flower_plugin import CRDTStrategy, FlowerCRDTClient

# Server-side: CRDT-backed aggregation strategy
strategy = CRDTStrategy(merge_strategy="dare_ties", min_clients=3)

# Client-side: automatic CRDT wrapping
client = FlowerCRDTClient(model=my_model, strategy="ties")
```

| Class | Purpose |
|-------|---------|
| **CRDTStrategy** | Flower Strategy with CRDT merge aggregation |
| **FlowerCRDTClient** | Flower NumPyClient with CRDT parameter wrapping |
| **FlowerAggregator** | Standalone CRDT aggregator for custom FL pipelines |

### v0.9.2 Numbers

- **3 new modules**: `compliance.py` (932 LOC), `observability.py` extensions (+571 LOC), `flower_plugin.py` (485 LOC)
- **12 new public classes** added to `__all__`
- **213 new tests**, bringing the total to **3,254 passing**
- **Zero new required dependencies** — `flower` and `cryptography` are optional extras

---


Production-grade encryption and comprehensive property-based testing — closing every developer-addressable finding from the independent due-diligence audit.

### Pluggable Crypto Backend System

The encryption module now supports four interchangeable backends behind a single `CryptoBackend` protocol:

| Backend | Standard | Key Feature | Best For |
|---------|----------|-------------|----------|
| **AES-256-GCM** | NIST SP 800-38D | Hardware-accelerated (AES-NI) | General production (default) |
| **AES-256-GCM-SIV** | RFC 8452 | Nonce-misuse resistant | CRDT multi-replica encryption |
| **ChaCha20-Poly1305** | IETF RFC 8439 | Constant-time on all architectures | ARM/embedded, side-channel sensitive |
| **XOR** | — | Zero dependencies | Stdlib-only environments (legacy) |

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, register_backend, get_backend
import os

provider = StaticKeyProvider(key=os.urandom(32))

# Auto-selects strongest available backend
em = EncryptedMerge(provider, backend="auto")

# Or choose explicitly
em = EncryptedMerge(provider, backend="aes-256-gcm-siv")

# Register custom or post-quantum backends
from crdt_merge.encryption import CryptoBackend
register_backend("my-pqc-backend", MyPQCBackend())
```

**Key design properties:**
- **Backward-compatible wire format** — v1 (XOR) payloads are auto-detected and decrypted by any backend
- **Cross-backend decryption** — Migrate from XOR → AES-GCM or AES-GCM → ChaCha20 without re-encrypting existing data
- **Post-quantum ready** — `register_backend()` accepts any future backend (ML-KEM, CRYSTALS-Kyber) without core changes
- **Zero new required dependencies** — AEAD backends activate only when `cryptography` is installed

### 135 Property-Based Tests via Hypothesis

Full CRDT law verification across all module families:

| Module Group | Tests | Laws Verified |
|---|---|---|
| Core primitives & strategies | 32 | Commutativity, associativity, idempotency, monotonicity |
| DataFrame & JSON merge | 30 | Merge correctness, conflict resolution, schema evolution |
| Streaming & delta | 27 | Chunk reassembly, ordering invariants, delta composition |
| Probabilistic & wire format | 25 | HLL/Bloom merge, encode/decode round-trips |
| Verify, dedup & provenance | 21 | Verified merge, dedup stability, provenance integrity |

Total test suite: **3,041 tests** (up from 2,855), **0 failures**.

---

## What's New in v0.9.0 — "The Enterprise Release"

Five new enterprise modules — all stdlib-only, all composable with each other and the existing merge pipeline:

| Module | Key Classes | Purpose |
|--------|------------|---------|
| `unmerge` | `UnmergeEngine`, `ModelUnmerge`, `GDPRForget` | Selective rollback, GDPR right-to-be-forgotten |
| `audit` | `AuditLog`, `AuditedMerge` | Immutable hash-chained audit trail |
| `encryption` | `EncryptedMerge`, `StaticKeyProvider`, `CryptoBackend`, `register_backend` | Field-level encryption with 4 pluggable backends and key rotation |
| `rbac` | `RBACController`, `SecureMerge` | Policy-based access control |
| `observability` | `ObservedMerge`, `HealthCheck`, `MetricsCollector` | Timing, conflict metrics, health monitoring |

Enterprise modules compose cleanly — wrap a single merge pipeline with audit + encryption + RBAC + observability simultaneously.

---

## What's New in v0.8.3 — "The Research Release"

### Continual Merge Engine (NeurIPS 2025-Inspired)

SVD-based dual-projection merging that separates shared knowledge from task-specific knowledge, with CRDT convergence guarantees.

```python
from crdt_merge.model.continual import ContinualMerge

# Continual merge with CRDT convergence verification
engine = ContinualMerge(convergence="crdt")
engine.absorb(base_model)
engine.absorb(finetuned_model_1)
engine.absorb(finetuned_model_2)

merged = engine.result()

# Verify CRDT properties hold
proof = engine.verify_convergence()
print(proof)  # Commutativity: ✓, Associativity: ✓, Idempotency: ✓

# Measure knowledge retention
stability = engine.measure_stability(base_model)
print(f"Retention: {stability.overall:.1%}")
```

Or use the strategy directly in ModelMerge pipelines:

```python
from crdt_merge.model.core import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema(strategies={"default": "dual_projection"})
merge = ModelMerge(schema)
result = merge.run({"layer.weight": weights_a}, {"layer.weight": weights_b})
```

### HuggingFace Hub Native Integration

Push, pull, and merge models directly on HuggingFace Hub with provenance-enriched model cards.

```python
from crdt_merge.hub import HFMergeHub, AutoModelCard, ModelCardConfig

# Merge and push in one call
hub = HFMergeHub(token="hf_...")
result = hub.merge(
    sources=["user/model-a", "user/model-b"],
    strategy="slerp",
    destination="user/merged-model",
    auto_model_card=True,  # Generates provenance card automatically
)

# Generate model cards with EU AI Act metadata
card_gen = AutoModelCard(ModelCardConfig(include_eu_ai_act=True))
card_md = card_gen.generate(
    sources=["user/model-a", "user/model-b"],
    strategy="slerp",
    verified=True,
)
```

---

## What's New in v0.8.2 — "The Adoption Release"

**Context Memory System, Agentic AI State Merge, and MergeKit Migration CLI.** crdt-merge now spans **tabular data + model weights + agent memory** under one algebraic framework.

### Context Memory System (Category-Defining)

CRDT-merged memory for AI agents. Dedup, merge, and audit agent memories with the same strategies used for tabular data.

```python
from crdt_merge.context import ContextMerge, ContextBloom

bloom = ContextBloom(expected_items=100_000, fp_rate=0.001)
merger = ContextMerge(bloom=bloom, strategy="lww")
result = merger.merge(agent_a_memories, agent_b_memories)
print(result.manifest.summary())  # "3 unique memories from 2 agents"
```

- `MemorySidecar` — pre-computed metadata for O(1) memory filtering
- `ContextManifest` — self-describing merge attestation with EU AI Act traceability
- `ContextBloom` — 64-shard bloom filter for memory dedup (~10M checks/sec)
- `ContextConsolidator` — bundles thousands of memories into indexed blocks
- `ContextMerge` — quality-weighted, budget-aware context merge

### Agentic AI State Merge

CRDT containers purpose-built for multi-agent orchestration (CrewAI, AutoGen, LangGraph).

```python
from crdt_merge.agentic import AgentState, SharedKnowledge

researcher = AgentState(agent_id="researcher")
researcher.add_fact("revenue_q1", 4_200_000, confidence=0.9)

analyst = AgentState(agent_id="analyst")
analyst.add_fact("revenue_q1", 4_250_000, confidence=0.95)

shared = SharedKnowledge.merge(researcher, analyst)
print(shared.facts["revenue_q1"].confidence)  # 0.95 — higher confidence wins
```

### MergeKit Migration CLI

```bash
crdt-merge migrate mergekit-config.yaml --output merge_pipeline.py
```

Zero-cost switching for MergeKit users. Supports linear, slerp, ties, dare, task_arithmetic methods.

---

## What's New in v0.8.1 — "The CRDT Architecture Release"

**All 26 model merge strategies are now provably true CRDTs.**

v0.8.0 introduced 25 model merge strategies, but a fundamental mathematical limitation meant strategies like SLERP, TIES, DARE, and Fisher could not satisfy CRDT laws when applied directly to raw tensors.

v0.8.1 solves this with the **two-layer architecture**:

| Layer | Responsibility | CRDT? |
|-------|---------------|-------|
| **CRDTMergeState** | Collects models via set union | ✅ Provably C+A+I |
| **Strategy** (unchanged) | Computes merged model atomically | Deterministic pure function |

```python
from crdt_merge.model import CRDTMergeState

# Create CRDT states on different replicas
state_a = CRDTMergeState("slerp")
state_a.add(model_weights_1, model_id="llama-7b")

state_b = CRDTMergeState("slerp")
state_b.add(model_weights_2, model_id="mistral-7b")

# Merge in any order — always converges
merged = state_a.merge(state_b)  # Same result as state_b.merge(state_a)
result = merged.resolve()         # Deterministic merged weights
```

**Key features of `CRDTMergeState`:**
- OR-Set add/remove semantics with tombstones (add-wins)
- SHA-256 Merkle hashing for content-addressable provenance
- Version vectors with configurable conflict resolution
- Canonical hash-sorted ordering for deterministic cross-replica convergence
- Wire serialization via `to_dict()` / `from_dict()`
- Batch operations: `add_batch()`, `merge_many()`
- 195 new tests — all 25 strategies x 3 CRDT laws verified

Or use the high-level API:

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema(strategies={"default": "slerp"})
merger = ModelMerge(schema)
result = merger.crdt_merge(
    models=[model_a, model_b, model_c],
    model_ids=["llama", "mistral", "phi"],
)
assert result.metadata["crdt_guaranteed"] is True
```

### v0.8.0 — "The Intelligence Release"

**26 model merge strategies** across 8 categories, powered by CRDT-native architecture:

| Category | Strategies |
|----------|-----------|
| Basic | WeightAverage, SLERP, TaskArithmetic, LinearInterp |
| Subspace | TIES, DARE, DELLA, DARE-TIES, ModelBreadcrumbs, EMR, STAR, SVDKnotTying, AdaRank |
| Weighted | FisherMerge, RegMean, AdaMerging, DAM |
| Evolutionary | EvolutionaryMerge, GeneticMerge |
| Unlearning | NegMerge, SplitUnlearnMerge |
| Calibration | WeightScopeAlignment, RepresentationSurgery |
| Safety | SafeMerge, LEDMerge |

```python
from crdt_merge.model import ModelCRDT, ModelMergeSchema

# Define per-layer merge strategies
schema = ModelMergeSchema({
    "embed_tokens": "slerp",
    "layers.*.self_attn": "ties",
    "layers.*.mlp": "dare",
    "lm_head": "weight_average",
})

# Merge two models with CRDT guarantees
model = ModelCRDT(weights_a, weights_b, schema=schema)
merged = model.merge()

# Full provenance — which model contributed which parameters
provenance = model.provenance()
```

---

## Full Feature Matrix

### Tabular / Data Layer

| Feature | Status |
|---|---|
| LWW (Last-Write-Wins) merge | ✅ |
| Multi-value register (MVR) | ✅ |
| Observed-Remove Set (OR-Set) | ✅ |
| Vector clocks | ✅ |
| Hybrid Logical Clocks (HLC) | ✅ |
| Merkle tree verification | ✅ |
| Schema evolution (non-breaking) | ✅ |
| Field-level provenance and audit log | ✅ |
| Probabilistic dedup (MinHash/HLL) | ✅ |
| Parquet / Delta Lake support | ✅ |
| Apache Arrow / Arrow Flight | ✅ |
| Gossip protocol sync | ✅ |
| Async merge | ✅ |
| Streaming / incremental merge | ✅ |
| Wire serialisation (protobuf-compatible) | ✅ |
| MergeQL query language | ✅ |
| JSON CRDT merge | ✅ |
| `@verified_merge` compliance decorator | ✅ |

### Model Weights Layer

| Feature | Status |
|---|---|
| SLERP | ✅ |
| TIES | ✅ |
| DARE | ✅ |
| Fisher-weighted merge | ✅ |
| LoRA-aware merge | ✅ |
| Evolutionary / search-based merge | ✅ |
| Continual learning merge | ✅ |
| Dual-projection merge (DualProjectionMerge) | ✅ v0.8.3 |
| CRDT convergence verification (ConvergenceProof) | ✅ v0.8.3 |
| Federated learning aggregation | ✅ |
| Safety filtering on merged weights | ✅ |
| mergekit compatibility layer | ✅ |
| GPU acceleration | ✅ |
| Model merge pipeline | ✅ |
| CRDTMergeState (two-layer architecture) | ✅ v0.8.1 |
| Context Memory System | ✅ v0.8.2 |
| Agentic AI State Merge | ✅ v0.8.2 |
| MergeKit Migration CLI | ✅ v0.8.2 |
| HuggingFace Hub integration (HFMergeHub) | ✅ v0.8.3 |
| Auto model cards with provenance (AutoModelCard) | ✅ v0.8.3 |
| EU AI Act traceability metadata (JSON-LD) | ✅ v0.8.3 |

### Enterprise Layer

| Feature | Status |
|---|---|
| UnmergeEngine — selective merge rollback | ✅ v0.9.0 |
| ModelUnmerge — neural weight contribution removal | ✅ v0.9.0 |
| GDPRForget — privacy-compliant data removal | ✅ v0.9.0 |
| AuditLog — SHA-256 hash-chained audit trail | ✅ v0.9.0 |
| AuditedMerge — auto-logging merge wrapper | ✅ v0.9.0 |
| EncryptedMerge — field-level encryption | ✅ v0.9.0 |
| Pluggable crypto backends (AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305) | ✅ v0.9.1 |
| Auto-detection of best available backend | ✅ v0.9.1 |
| Cross-backend decryption (migrate without re-encrypting) | ✅ v0.9.1 |
| Post-quantum ready backend registry (`register_backend()`) | ✅ v0.9.1 |
| Key rotation — re-encrypt on credential cycling | ✅ v0.9.0 |
| RBACController — policy-based access control | ✅ v0.9.0 |
| SecureMerge — RBAC-enforced merge operations | ✅ v0.9.0 |
| MetricsCollector — operation timing and conflict tracking | ✅ v0.9.0 |
| ObservedMerge — auto-instrumented merge wrapper | ✅ v0.9.0 |
| HealthCheck — configurable degradation thresholds | ✅ v0.9.0 |
| ComplianceAuditor — pluggable regulatory rule engine | ✅ v0.9.2 |
| ComplianceReport — aggregate pass/warn/fail reporting | ✅ v0.9.2 |
| EUAIActReport — Article 11 transparency report generator | ✅ v0.9.2 |
| MergeTracer — OTel-compatible distributed tracing | ✅ v0.9.2 |
| DriftDetector — statistical merge drift analysis | ✅ v0.9.2 |
| PrometheusExporter — /metrics endpoint generation | ✅ v0.9.2 |
| GrafanaDashboard — auto-generated dashboard JSON | ✅ v0.9.2 |
| CRDTStrategy — Flower federated learning aggregation | ✅ v0.9.2 |
| FlowerCRDTClient — Flower client with CRDT wrapping | ✅ v0.9.2 |
| FlowerAggregator — standalone FL aggregator | ✅ v0.9.2 |

### Ecosystem Accelerators

| Integration | Status |
|---|---|
| DuckDB UDF extension | ✅ |
| Polars plugin | ✅ |
| dbt package | ✅ |
| DuckLake | ✅ |
| Airbyte connector | ✅ |
| SQLite extension | ✅ |
| Apache Arrow Flight server | ✅ |
| Streamlit UI | ✅ |

---

## Installation

```bash
# Core — zero required dependencies
pip install crdt-merge

# With fast tabular backends
pip install crdt-merge[fast]          # DuckDB + Polars (38.8x on A100)

# With specific ecosystem support
pip install crdt-merge[polars]        # Polars plugin
pip install crdt-merge[pandas]        # pandas support
pip install crdt-merge[datasets]      # HuggingFace datasets

# AEAD encryption backends (AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305)
pip install crdt-merge[crypto]        # Installs cryptography library

# Model merging
pip install crdt-merge[model]         # PyTorch model weights

# GPU-accelerated model merging
pip install crdt-merge[gpu]           # CUDA-accelerated ops

# Ecosystem accelerators
pip install crdt-merge[duckdb]        # DuckDB UDF + MergeQL
pip install crdt-merge[dbt]           # dbt CRDT models
pip install crdt-merge[flight]        # Arrow Flight merge server
pip install crdt-merge[airbyte]       # Airbyte destination connector
pip install crdt-merge[streamlit]     # Visual merge UI
pip install crdt-merge[sqlite]        # SQLite extension

# Everything
pip install crdt-merge[all]

# Development
pip install crdt-merge[dev]           # pytest + hypothesis
```

**Zero required dependencies.** All extras are optional. The core runs on pure Python. Works on Linux, macOS, Windows.

---

## API Reference

### `merge()` — The Main Entry Point

```python
from crdt_merge import merge

result = merge(
    df_a,                    # First dataset (list of dicts, pandas DataFrame, or Polars DataFrame)
    df_b,                    # Second dataset
    key="id",                # Column to match rows on (raises KeyError if not found)
    prefer="latest",         # "a", "b", or "latest" — conflict resolution (raises ValueError if invalid)
    schema=None,             # Optional MergeSchema for per-field strategies (overrides prefer)
    timestamp_col=None,      # Column with timestamps for LWW resolution
    dedup=True,              # Remove exact duplicates in output
    fuzzy_dedup=False,       # Also remove near-duplicates
    fuzzy_threshold=0.85,    # Similarity threshold for fuzzy dedup
)
```

- When `key` is provided: rows with matching keys are merged, unique rows from both sides are preserved.
- When `key` is `None`: datasets are appended and deduplication is applied.
- When `schema` is provided: per-field strategies override the `prefer` parameter for matched rows.
- Input/output format matches: pass pandas in, get pandas out. Pass list of dicts, get list of dicts.

### `merge_with_provenance()` — Merge + Full Audit Trail

```python
from crdt_merge import merge_with_provenance

merged, log = merge_with_provenance(
    df_a, df_b,
    key="id",
    schema=my_schema,          # Optional MergeSchema
    timestamp_col=None,        # Optional timestamp column
    as_dataframe=False,        # Set True to get pandas DataFrame output
)

# Inspect the audit trail
print(log.summary())           # Human-readable summary
print(log.total_conflicts)     # Number of field-level conflicts resolved
for entry in log.entries:
    print(entry.field, entry.winner, entry.strategy)

# Export
from crdt_merge import export_provenance
json_str = export_provenance(log, format="json")  # Returns string
csv_str = export_provenance(log, format="csv")     # Returns string
log_dict = log.to_dict()                           # Returns dict
```

### `merge_stream()` — Streaming Merge

```python
from crdt_merge import merge_stream, StreamStats

stats = StreamStats()
for batch in merge_stream(
    source_a,                # Iterable of dicts (streamed)
    source_b,                # Iterable of dicts (loaded into memory)
    key="id",
    batch_size=5000,
    schema=my_schema,        # Optional MergeSchema
    prefer="b",              # Optional prefer shorthand
    timestamp_col=None,
    stats=stats,
):
    process(batch)

print(f"{stats.rows_per_second:.0f} rows/s, {stats.batch_count} batches")
```

**Memory:** O(|source_b| + batch_size). Loads source_b fully for key lookup, streams source_a in batches.

### `merge_sorted_stream()` — True O(1) Memory Merge

```python
from crdt_merge import merge_sorted_stream

for batch in merge_sorted_stream(
    sorted_source_a,          # MUST be sorted by key ascending
    sorted_source_b,          # MUST be sorted by key ascending
    key="id",
    batch_size=5000,
    schema=my_schema,
    verify_order=True,        # Raises ValueError if sources aren't sorted
):
    process(batch)
```

**Memory:** O(batch_size). Never loads more than 1 row from each source at a time. Tested to 100M rows at 10.8 MB.

### Composable Strategies

```python
from crdt_merge.strategies import (
    MergeSchema, LWW, MaxWins, MinWins, UnionSet,
    Priority, Concat, LongestWins, Custom
)

# Declare per-field strategies
schema = MergeSchema(
    default=LWW(),                                    # Fallback for unspecified fields
    score=MaxWins(),                                   # Highest value wins
    rating=MinWins(),                                  # Lowest value wins
    tags=UnionSet(delimiter=";"),                       # Set union of delimited values
    status=Priority(order=["draft", "review", "live"]), # Priority ranking
    notes=Concat(delimiter="\n"),                       # Concatenate with dedup
    title=LongestWins(),                               # Longer string wins
    custom_field=Custom(fn=my_merge_fn),               # Your own function
)

# Apply to any merge function
result = merge(df_a, df_b, key="id", schema=schema)
merged, log = merge_with_provenance(df_a, df_b, key="id", schema=schema)
for batch in merge_stream(src_a, src_b, key="id", schema=schema):
    ...

# Serialize for storage/transmission
d = schema.to_dict()
restored = MergeSchema.from_dict(d)
```

**Note:** `Custom(fn)` strategies cannot be serialized — `to_dict()` stores `{"strategy": "Custom"}` and `from_dict()` raises `ValueError` to prevent silent behavior change.

### Delta Sync

```python
from crdt_merge.delta import compute_delta, apply_delta, compose_deltas, DeltaStore

# Compute what changed between two versions
delta = compute_delta(old_records, new_records, key="id")
print(delta.size)  # Number of changes

# Apply delta to bring a remote node up to date
updated = apply_delta(remote_records, delta, key="id")

# Compose multiple deltas: delta(v1->v2) + delta(v2->v3) = delta(v1->v3)
combined = compose_deltas(delta_1, delta_2, key="id")

# DeltaStore tracks versions automatically
store = DeltaStore(key="id", node_id="node_a")
delta = store.ingest(new_records)  # Returns delta from previous state
print(store.version, store.size)
```

**Note:** DeltaStore is in-memory. Use `Delta.to_dict()` / `Delta.from_dict()` to persist deltas externally.

### Binary Wire Format

```python
from crdt_merge import serialize, deserialize, peek_type, wire_size, serialize_batch, deserialize_batch

# Serialize any CRDT type to compact binary
gc = GCounter("node1")
gc.increment("node1", 100)
wire_bytes = serialize(gc, compress=True)   # zlib compression
restored = deserialize(wire_bytes)          # GCounter with value 100

# Inspect without deserializing
type_name = peek_type(wire_bytes)           # "g_counter"
info = wire_size(wire_bytes)                # {total_bytes, header_bytes, payload_bytes, ...}

# Batch serialize/deserialize
batch_bytes = serialize_batch([gc, pn, lww])
objects = deserialize_batch(batch_bytes)    # [GCounter, PNCounter, LWWRegister]
```

**Supported types:** GCounter, PNCounter, LWWRegister, ORSet, LWWMap, MergeableHLL, MergeableBloom, MergeableCMS, Delta.

**Wire format specification:** Deterministic byte layout with 12-byte header (magic, version, type, flags, length). Any language implementation that speaks this format can interoperate.

### Probabilistic CRDTs

```python
from crdt_merge import MergeableHLL, MergeableBloom, MergeableCMS

# HyperLogLog — estimate unique counts across distributed nodes
hll_a = MergeableHLL(precision=14)
hll_a.add_all(user_ids_node_a)
hll_b = MergeableHLL(precision=14)
hll_b.add_all(user_ids_node_b)
merged = hll_a.merge(hll_b)       # register-max merge
print(f"~{merged.cardinality():.0f} unique users (+-0.81%)")

# Bloom filter — distributed membership testing
bloom = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom.add("blocked_ip")
merged = bloom_a.merge(bloom_b)    # bitwise-OR merge

# Count-Min Sketch — distributed frequency estimation
cms = MergeableCMS(width=1000, depth=5)
cms.add("event_type", count=3)
merged = cms_a.merge(cms_b)       # element-wise max merge
```

All three structures satisfy CRDT merge properties and can be serialized via the wire format.

### Verified Merge

```python
from crdt_merge import verified_merge

@verified_merge(samples=100, key="id")
def my_merge(a, b, key="id"):
    return merge(a, b, key=key)

# Calling my_merge() automatically verifies:
# - Commutativity: my_merge(a, b) == my_merge(b, a)
# - Associativity: my_merge(my_merge(a, b), c) == my_merge(a, my_merge(b, c))
# - Idempotency: my_merge(a, a) == a
# Raises CRDTVerificationError if any property fails.
```

### CRDT Primitives

```python
from crdt_merge import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

# Grow-only counter — nodes increment independently, merge via max-per-node
a = GCounter("node_a")
a.increment("node_a", 10)
b = GCounter("node_b")
b.increment("node_b", 5)
merged = a.merge(b)
print(merged.value)  # 15 — guaranteed correct regardless of merge order
```

All primitives satisfy CRDT properties: **commutative** (a ⊔ b = b ⊔ a), **associative** ((a ⊔ b) ⊔ c = a ⊔ (b ⊔ c)), **idempotent** (a ⊔ a = a).

### MergeQL — SQL-Like Merges

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("nyc", [{"id": 1, "name": "Alice", "salary": 100000}])
ql.register("london", [{"id": 1, "name": "Alice", "salary": 120000}])

result = ql.execute("""
    MERGE nyc, london
    ON id
    STRATEGY salary='max', name='lww'
""")
# salary: 120000 (max wins), name: "Alice" (LWW)
```

### Self-Merging Parquet

```python
from crdt_merge.parquet import SelfMergingParquet
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), salary=MaxWins())
smf = SelfMergingParquet("customers", key="id", schema=schema)
smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
smf.ingest([{"id": 1, "name": "Alicia", "salary": 120}])
assert smf.read()[0]["salary"] == 120  # MaxWins applied automatically
```

### JSON Deep Merge

```python
from crdt_merge import merge_dicts, merge_json_lines

# Deep merge two dicts with LWW semantics
merged = merge_dicts(
    {"user": {"name": "Alice", "score": 80}},
    {"user": {"name": "Alice", "score": 95, "level": 5}},
)
# {"user": {"name": "Alice", "score": 95, "level": 5}}

# None values in B are treated as missing (A's value preserved)
merged = merge_dicts({"x": 10}, {"x": None})
# {"x": 10}

# Merge JSONL files line by line
merged_lines = merge_json_lines(jsonl_a, jsonl_b, key="id")
```

### Deduplication

```python
from crdt_merge import dedup, dedup_records, DedupIndex, MinHashDedup

# Exact dedup on strings
unique = dedup(["hello", "world", "hello"])

# Fuzzy dedup on records
unique_records = dedup_records(records, key="title", threshold=0.85)

# MinHash for large-scale approximate dedup
mh = MinHashDedup(num_hashes=128, threshold=0.5)
unique = mh.dedup(items, text_fn=lambda x: x["description"])

# DedupIndex — CRDT-mergeable dedup state
idx_a = DedupIndex("node_a")
idx_a.add_exact("item1")
idx_b = DedupIndex("node_b")
idx_b.add_exact("item2")
merged_idx = idx_a.merge(idx_b)
```

---

## Performance Benchmarks

All benchmarks verified on A100 GPU (Google Colab). Notebooks available in [`/notebooks`](notebooks/).

| Benchmark | Result |
|---|---|
| Tabular merge throughput (10M rows, Polars) | ~2.1s |
| Model merge speedup vs. naive baseline | **38.8x** |
| CRDT state overhead per merge | **< 0.5ms** |
| Memory overhead for CRDT metadata | < 3% of payload size |
| Merkle verification (1M row delta) | < 120ms |

### Polars Engine vs Python Merge (v0.7.1 -- A100 Measured)

| Rows | Polars Engine | Python Engine | Speedup |
|------|:-------------|:-------------|:-------:|
| 10,000 | 0.238s | 0.046s | 0.2x |
| 50,000 | 0.007s | 0.242s | **32.8x** |
| 100,000 | 0.012s | 0.445s | **37.0x** |
| 500,000 | 0.060s | 2.3s | **38.8x** |
| 1,000,000 | 0.127s | 4.5s | **35.2x** |
| 5,000,000 | 1.0s | 22.4s | **22.5x** |
| 10,000,000 | 2.1s | 44.5s | **21.4x** |

**Sweet spot: 50K--1M rows** (33--39x speedup). Above 5M rows, speedup tapers to ~21x as memory bandwidth saturates. Below 15K rows, Python engine is faster due to Polars compilation overhead. `engine="auto"` handles this automatically.

### v0.6.0 -- Throughput Ceilings (A100)

| Operation | Peak Throughput | Scale Tested | Scaling |
|-----------|----------------|-------------|---------|
| GCounter increment | **4.14M ops/s** | 10K -- 500K | Flat |
| VectorClock ops | **1.06M ops/s** | 100K -- 2M | Flat |
| Streaming merge | **594K rows/s** | 50K -- 1M | 17% degradation |
| JSON merge (dicts) | **530K ops/s** | 10K -- 500K | Graceful |
| Gossip updates | **474K ops/s** | 10K -- 200K | State growth |
| HyperLogLog add | **433K ops/s** | 100K -- 2M | Flat |
| Schema evolution | **443K ops/s** | 1K -- 20K cols | Stable |
| Dedup strings | **333K ops/s** | 100K -- 2M | 18% degradation |
| Bloom filter add | **178K ops/s** | 100K -- 2M | Flat |
| Wire serialize batch | **170K ops/s** | 1K -- 50K | Flat |
| MergeSchema merge | **149K rows/s** | 10K -- 200K | Improves at scale |
| Merkle tree build | **138K records/s** | 50K -- 1M | 22% degradation |
| Provenance merge | **81K rows/s** | 50K -- 500K | Improves at scale |
| **DataFrame merge** | **77K rows/s** | **100K -- 10M** | **2% degradation** |

**Notebooks:** All available in [`notebooks/`](notebooks/) for independent reproduction on Google Colab.

---

## Who Uses crdt-merge

crdt-merge is designed for:

- **ML researchers** merging fine-tuned model variants without coordination
- **Data engineers** building multi-source pipelines that must be replayable and auditable
- **Platform teams** running federated or distributed training
- **AI teams** building multi-agent systems where agents share and update state
- **Anyone** who has been burned by merge order mattering when it shouldn't

### Ecosystem Compatibility

| Tool | Status |
|---|---|
| DuckDB | ✅ Native UDF |
| Polars | ✅ Native plugin |
| pandas | ✅ Full support |
| dbt | ✅ Package |
| Delta Lake | ✅ Read/write |
| Apache Arrow | ✅ Full |
| HuggingFace Transformers | ✅ Weight-compatible |
| mergekit | ✅ Compatibility layer |
| PyTorch | ✅ Tensor-native |
| CrewAI / AutoGen / LangGraph | ✅ Agent state merge |

---

## Cross-Language Ports

crdt-merge follows a **reference + protocol** architecture:

| Language | Package | Version | Status |
|----------|---------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) | v0.9.2 | ✅ Full feature set + 26 model merge strategies + CRDT architecture + 8 accelerators + Context Memory + Agentic AI + Continual Merge + HF Hub + Enterprise (Unmerge, Audit, Encryption w/ 4 AEAD backends, RBAC, Observability, Compliance, Flower FL) |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) | v0.2.0 | Source complete |

**Architecture:** Python is the reference implementation where all innovation starts. The Rust crate will become a thin protocol engine implementing wire format + merge semantics. FFI wrappers (Go, C#, Swift) will wrap the protocol engine. The golden rule: `Python serialize -> Rust deserialize -> merge -> serialize -> Python deserialize` must roundtrip perfectly.

---

## Known Limitations

| Limitation | Details | Planned Fix |
|-----------|---------|------------|
| **No persistence** | DeltaStore is in-memory. State lost on process exit. Use `to_dict()`/`from_dict()` to serialize externally. | By design — persistence belongs in the application layer |
| **No networking** | Gossip protocol provides state tracking but no built-in transport. Wire format enables interop. | By design — transport belongs in the application layer |
| **O(n^2) fuzzy dedup** | `_fuzzy_dedup_records` compares every record against all existing records. Unusable above ~10K records. | Algorithmic improvement planned |
| **Wire format doesn't include MergeSchema** | You can serialize CRDTs and Deltas, but not MergeSchema over the wire. | Planned for future release |

---

## License

crdt-merge is released under the **Business Source License 1.1 (BSL 1.1)**.

**What this means in plain English:**

- ✅ **Free for research, personal use, and most production use** — the Additional Use Grant is unusually broad and explicitly covers DuckDB, Polars, dbt, and similar open-data tooling
- ✅ **Source-available** — you can read, audit, fork, and contribute
- ✅ **Converts to Apache 2.0 on 29 March 2028** — fully open source, permanently, on a fixed public date
- ❌ **Not free** if you are building a *competing commercial merge service* (SaaS) without a commercial license

The [PATENTS](PATENTS) file includes a defensive patent grant. Patent pending (UK Application 2607132.4). The [CLA](CLA.md) covers contributions.

**tl;dr: If you're using this in data pipelines, ML research, or distributed systems — you're fine. If you're building a hosted merge-as-a-service product — contact us.**

Copyright 2026 Ryan Gillespie. See [LICENSE](LICENSE) for the full text.

---

## Contributing

We welcome contributions. Before opening a PR:

1. Sign the [CLA](CLA.md) (one comment on your first PR — takes 30 seconds)
2. Run the full test suite: `pytest tests/ -v`
3. CRDT compliance must be maintained: `pytest tests/test_crdt_compliance.py`

See [CHANGELOG.md](CHANGELOG.md) for the full project history.

**Commercial licensing and inquiries:**
- rgillespie83@icloud.com
- data@optitransfer.ch

---

## Roadmap

| Version | Focus | Status |
|---|---|---|
| v0.8.3 | Continual Merge Engine, HuggingFace Hub Native | ✅ Released |
| v0.8.2 | Context Memory, Agentic AI, MergeKit CLI | ✅ Released |
| v0.8.1 | Two-layer CRDT architecture, 25/25 compliance | ✅ Released |
| v0.9.0 | Enterprise: UnmergeEngine, Audit, Encryption, RBAC, Observability | ✅ Released |
| v0.9.1 | Iron Dome: Pluggable crypto backends, 186 new tests, audit remediation | ✅ Released |
| v0.9.1.1 | Backfill: [crypto] optional dependency group | ✅ Released |
| v0.9.2 | Completion: Compliance, Observability Extensions, Flower FL Plugin | ✅ Released |
| v1.0 | Stable API, formal spec, security audit, cross-language parity | Planned |

**Full roadmap:** [`docs/roadmap/roadmap_v2_0.md`](docs/roadmap/roadmap_v2_0.md)

---

<div align="center">

**[Documentation](docs/)** · **[API Reference](docs/api/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[Benchmarks](notebooks/)** · **[Changelog](CHANGELOG.md)** · **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
