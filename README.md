<div align="center">

<h1>crdt-merge</h1>

<p><strong>The first merge library where every operation is mathematically guaranteed to converge.</strong><br/>
Tabular data. Neural network weights. Distributed agents. One unified CRDT layer.</p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.3-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-3%2C291%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)

```
pip install crdt-merge
```

**[Documentation](docs/README.md)** · **[Quick Start](docs/getting-started/quickstart.md)** · **[API Reference](docs/api-reference/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[Changelog](CHANGELOG.md)**

</div>

---

## The Problem

You're merging data or models from multiple sources — pipelines, replicas, collaborators, distributed nodes. It looks right. But:

- Run it in a different **order**? Different result.
- Apply the same patch **twice**? Different result.
- Merge A→B→C vs. A→(B→C)? **Different result.**

This is a fundamental property of nearly every merge algorithm ever written. **crdt-merge is the fix.**

---

## What Is crdt-merge?

A Python library that enforces **CRDT (Conflict-free Replicated Data Type)** correctness across every merge operation — for tabular data, neural network weights, and AI agent memory.

A CRDT-compliant merge satisfies three algebraic laws:

| Law | Meaning | Why It Matters |
|---|---|---|
| **Commutativity** | `merge(A, B) == merge(B, A)` | Order of inputs never changes the outcome |
| **Associativity** | `merge(merge(A,B),C) == merge(A,merge(B,C))` | Grouping never changes the outcome |
| **Idempotency** | `merge(A, A) == A` | Applying the same data twice is safe |

When all three hold, your distributed system **always converges** — no coordination, no locking, no central arbiter required.

---

## The Novel Innovation

> ⚠️ **Patent Pending — UK Application No. 2607132.4 (filed 30 March 2026)**

The starting point for crdt-merge was a mathematically uncomfortable finding: **virtually every standard merge algorithm fails CRDT laws when applied directly to data or model tensors.**

This isn't an implementation problem. It's provable:

| Strategy | Commutative | Associative | Idempotent | CRDT on raw tensors? |
|---|:---:|:---:|:---:|:---:|
| Weight Average | ✓ | ✗ | ✓ | **✗** |
| SLERP | ✗ | ✗ | ✓ | **✗** |
| TIES | ~ | ✗ | ✗ | **✗** |
| DARE | ✗ | ✗ | ✗ | **✗** |
| Fisher Merge | ✓ | ✗ | ✓ | **✗** |
| Task Arithmetic | ✓ | ✗ | ✗ | **✗** |

Even simple weight averaging fails associativity: `((A+B)/2 + C)/2 ≠ (A + (B+C)/2)/2`. Every strategy in the table — and every strategy anyone is likely to build — fails at least one law.

**Seven architectures** were designed and evaluated to solve this. The winning insight was a fundamental reframing:

> *Don't try to make the strategy satisfy CRDT laws. Lift CRDT compliance to the layer above it.*

The solution is a **two-layer OR-Set architecture**:

```
┌──────────────────────────────────────────────────────┐
│  Layer 1 — CRDTMergeState (OR-Set wrapper)            │
│                                                       │
│  • Contributions stored as a set, not a sequence      │
│  • Set union is commutative ✓  associative ✓          │
│    idempotent ✓  — CRDT laws hold here, always        │
│  • Merkle hash + vector clock enforce canonical order │
│  • Seeded randomness: stochastic strategies become    │
│    fully deterministic given the same input set       │
└──────────────────────┬───────────────────────────────┘
                       │ ordered, deterministic set
                       ▼
┌──────────────────────────────────────────────────────┐
│  Layer 2 — Strategy (pure function)                   │
│                                                       │
│  • SLERP / TIES / DARE / Fisher / LoRA / ...          │
│  • Raw algorithm — does not need to be CRDT-safe      │
│  • Same ordered input set → same output, always       │
│  • Fully swappable without re-adding contributions    │
└──────────────────────────────────────────────────────┘
```

**The key insight:** CRDT guarantees live in Layer 1, not in individual strategies. A strategy can be inherently stochastic, non-commutative, or non-associative — the OR-Set wrapper above it absorbs all of that and guarantees convergence at the system level. This is why all 26 strategies in crdt-merge are fully CRDT-compliant, even DARE (which randomly drops tensor entries) and EvolutionaryMerge (which runs a stochastic search).

> **[Full architecture document](docs/CRDT_ARCHITECTURE.md)** — mathematical proofs for each strategy, all 7 candidate architectures evaluated, benchmark results, full compliance matrix.

---

## What crdt-merge IS — and IS NOT

| Category | crdt-merge does this |
|---|---|
| **Tabular merge** | CRDT-correct merging of DataFrames, Parquet, Arrow, DuckDB, Polars, Delta Lake |
| **Model merge** | CRDT-correct SLERP, TIES, DARE, Fisher, LoRA, evolutionary, and 21 more strategies |
| **Agent memory** | CRDT-merged context for multi-agent systems (CrewAI, AutoGen, LangGraph) |
| **Audit & provenance** | Per-field conflict history, immutable hash-chain audit log, `@verified_merge` decorator |
| **Schema evolution** | Non-breaking column additions, type widening, backwards-compatible deltas |
| **Enterprise** | Merge undo, GDPR forget, field-level encryption, RBAC, observability, compliance |

| What you might assume | Reality |
|---|---|
| A DataFrame wrapper around `pandas.merge()` | No. A full CRDT state machine with provenance |
| A model training framework | No. Operates on already-trained weights only |
| A database | No. No persistence, no queries, no networking |
| Slow because of "CRDT overhead" | No. Overhead is **< 0.5ms** per merge |

---

## Quick Start

### Tabular Data

```python
from crdt_merge import CRDTDataFrame

replica_a = CRDTDataFrame(df_a, node_id="node-a")
replica_b = CRDTDataFrame(df_b, node_id="node-b")

merged = replica_a.merge(replica_b)        # commutative, associative, idempotent
print(merged.conflict_log())               # full provenance
```

### Model Weights

```python
from crdt_merge.model import CRDTMergeState

state = CRDTMergeState()
state.add("llama-ft-v1", weights_a, metadata={"task": "summarisation"})
state.add("llama-ft-v2", weights_b, metadata={"task": "summarisation"})

merged_model = state.merge(strategy="slerp")   # order of add() never matters
merged_model = state.merge(strategy="ties")    # swap strategies without re-adding
```

### Verify CRDT Compliance

```python
from crdt_merge import verified_merge

@verified_merge
def my_merge(a, b):
    return your_merge_logic(a, b)

# Raises CRDTViolationError if commutativity, associativity,
# or idempotency is broken — tested automatically on every call
```

---

## Feature Matrix

### Tabular / Data Layer

| Feature | Status |
|---|---|
| LWW, MVR, OR-Set, Vector Clocks, HLC | ✅ |
| Merkle tree verification | ✅ |
| Schema evolution (non-breaking) | ✅ |
| Field-level provenance and audit log | ✅ |
| Probabilistic dedup (MinHash / HLL) | ✅ |
| Parquet / Delta Lake | ✅ |
| Apache Arrow / Arrow Flight | ✅ |
| Gossip protocol sync | ✅ |
| Streaming / incremental merge | ✅ |
| Wire serialisation (protobuf-compatible) | ✅ |
| MergeQL query language | ✅ |
| JSON CRDT merge | ✅ |
| `@verified_merge` compliance decorator | ✅ |

### Model Weights Layer

| Feature | Status |
|---|---|
| 26 strategies: SLERP, TIES, DARE, Fisher, LoRA, Evolutionary and more | ✅ |
| Continual learning merge (dual-projection) | ✅ |
| CRDT convergence verification | ✅ |
| Federated learning aggregation | ✅ |
| Safety filtering on merged weights | ✅ |
| mergekit compatibility layer + migration CLI | ✅ |
| GPU acceleration | ✅ |
| Context Memory System | ✅ |
| Agentic AI State Merge (CrewAI / AutoGen / LangGraph) | ✅ |
| HuggingFace Hub integration | ✅ |
| EU AI Act traceability metadata (JSON-LD) | ✅ |

### Enterprise Layer

| Feature | Status |
|---|---|
| UnmergeEngine — selective merge rollback | ✅ |
| GDPRForget — privacy-compliant data removal | ✅ |
| AuditLog — SHA-256 hash-chained audit trail | ✅ |
| EncryptedMerge — AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305, XOR | ✅ |
| Post-quantum ready backend registry | ✅ |
| Key rotation + cross-backend migration | ✅ |
| RBACController — policy-based access control | ✅ |
| MetricsCollector + ObservedMerge + HealthCheck | ✅ |
| ComplianceAuditor — SOC 2, HIPAA, EU AI Act rule engine | ✅ |
| MergeTracer — OTel-compatible distributed tracing | ✅ |
| DriftDetector — statistical merge drift analysis | ✅ |
| PrometheusExporter + GrafanaDashboard | ✅ |
| Flower federated learning aggregation strategy | ✅ |

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

# Fast tabular backends (38.8× at 500K rows on A100)
pip install crdt-merge[fast]        # DuckDB + Polars

# Common extras
pip install crdt-merge[model]       # PyTorch model weights
pip install crdt-merge[crypto]      # AEAD encryption backends
pip install crdt-merge[gpu]         # CUDA-accelerated ops
pip install crdt-merge[duckdb]      # DuckDB UDF + MergeQL
pip install crdt-merge[flight]      # Arrow Flight merge server
pip install crdt-merge[datasets]    # HuggingFace datasets

# Everything
pip install crdt-merge[all]
```

Zero required dependencies. Works on Linux, macOS, Windows. Python 3.9–3.12.

---

## Enterprise Features

```python
# Merge undo + GDPR
from crdt_merge.unmerge import UnmergeEngine, GDPRForget

engine = UnmergeEngine()
rolled_back = engine.unmerge(merged_records, provenance_log, remove_source="node-2", key_field="id")

gdpr = GDPRForget()
result = gdpr.forget_data(merged_records, provenance_log, contributor="user-123", key_field="id")

# Immutable audit trail
from crdt_merge.audit import AuditedMerge

audited = AuditedMerge(node_id="server-1")
result, entry = audited.merge(left, right, key="id")
assert audited.audit_log.verify_chain()   # SHA-256 tamper detection

# Field-level encryption
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import os

em = EncryptedMerge(StaticKeyProvider(key=os.urandom(32)), backend="auto")
encrypted = em.encrypt_records(records, fields=["salary", "ssn"])
merged    = em.merge_encrypted(enc_left, enc_right, key="id")
decrypted = em.decrypt_records(merged, fields=["salary", "ssn"])

# RBAC
from crdt_merge.rbac import RBACController, SecureMerge, Policy, AccessContext, READER

rbac = RBACController()
rbac.add_policy("analyst", Policy(role=READER, denied_fields={"salary", "ssn"}))
secure = SecureMerge(rbac)
result = secure.merge(left, right, key="id", context=AccessContext(node_id="analyst", role=READER))

# Observability
from crdt_merge.observability import ObservedMerge, HealthCheck

observed = ObservedMerge(node_id="prod-1")
result, metric = observed.merge(left, right, key="id")
print(f"{metric.duration_ms:.1f}ms — {metric.conflicts_resolved} conflicts resolved")
```

All enterprise modules are stdlib-only and compose cleanly with each other and the core merge pipeline.

---

## Performance

All benchmarks measured on A100 GPU (Google Colab). Full reproduction notebooks in [`/notebooks`](notebooks/).

| Benchmark | Result |
|---|---|
| Tabular merge (10M rows, Polars) | ~2.1s |
| Model merge speedup vs. naive baseline | **38.8×** at 500K rows |
| CRDT state overhead per merge | **< 0.5ms** |
| Memory overhead for CRDT metadata | < 3% of payload |
| Merkle verification (1M row delta) | < 120ms |
| Streaming throughput | ~594K rows/s |

**Polars sweet spot: 50K–1M rows (33–39× speedup).** `engine="auto"` switches automatically — Python engine is faster below 15K rows.

---

## Who Uses crdt-merge

- **ML researchers** merging fine-tuned model variants without coordination
- **Data engineers** building multi-source pipelines that must be replayable and auditable
- **Platform teams** running federated or distributed training
- **AI teams** building multi-agent systems where agents share and update state
- **Anyone** who has been burned by merge order mattering when it shouldn't

---

## Cross-Language Ports

| Language | Package | Version | Status |
|----------|---------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) | v0.9.3 | ✅ Full feature set |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) | v0.2.0 | Source complete |

Python is the reference implementation. All innovations land here first. The Rust crate is evolving into a thin protocol engine (wire format + merge semantics). Golden rule: `Python → Rust → merge → Python` roundtrips must be byte-perfect.

---

## Known Limitations

| Limitation | Details |
|---|---|
| **No persistence** | All state is in-memory. Use `to_dict()`/`from_dict()` to serialize externally. By design — persistence belongs in the application layer. |
| **No networking** | Gossip protocol tracks state; no built-in transport. Wire format enables interop. By design. |
| **O(n²) fuzzy dedup** | `_fuzzy_dedup_records` is unusable above ~10K records. Algorithmic fix planned. |
| **MergeSchema not wire-serialisable** | CRDTs and Deltas serialize; MergeSchema does not yet. Planned. |

---

## License

Released under **BSL 1.1 (Business Source License)**. Converts automatically to **Apache 2.0 on 29 March 2028**.

- ✅ Free for research, personal use, and most production use
- ✅ Source-available — read, audit, fork, contribute
- ✅ Permanently Apache 2.0 from 29 March 2028
- ❌ Not free if building a competing commercial merge-as-a-service product

The [PATENTS](PATENTS) file includes a defensive patent grant (UK Application 2607132.4). The [CLA](CLA.md) covers contributions.

Copyright 2026 Ryan Gillespie. See [LICENSE](LICENSE) for full text.  
Commercial licensing: rgillespie83@icloud.com · data@optitransfer.ch

---

## Contributing

1. Sign the [CLA](CLA.md) (one comment on your first PR)
2. Run the full test suite: `pytest tests/ -v`
3. CRDT compliance must be maintained: `pytest tests/test_crdt_compliance.py`

See [CHANGELOG.md](CHANGELOG.md) for full project history and release notes.

---

<div align="center">

**[Documentation](docs/README.md)** · **[API Reference](docs/api-reference/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[Benchmarks](notebooks/)** · **[Changelog](CHANGELOG.md)** · **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
