---
title: crdt-merge
colorFrom: gray
colorTo: gray
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: true
license: other
license_name: BUSL-1.1
license_link: https://github.com/mgillr/crdt-merge/blob/main/LICENSE
tags:
  - crdt
  - merge
  - model-merging
  - distributed
  - convergence
  - neural-network
short_description: Mathematically guaranteed convergent model and data merge
---

<div align="center">

<h1>crdt-merge</h1>

<p><strong>The first merge library where every operation is mathematically guaranteed to converge.</strong><br/>
Tabular data. Neural network weights. Distributed agents. One unified CRDT layer.</p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.4-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-4%2C498%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)

```
pip install crdt-merge
```

**[Documentation](docs/README.md)** · **[Quick Start](docs/getting-started/quickstart.md)** · **[API Reference](docs/api-reference/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[Changelog](CHANGELOG.md)**

</div>

---

## Every merge algorithm you use is broken. This one isn't.

Every standard merge strategy — weight averaging, SLERP, TIES, DARE, Fisher — fails at least one of the three algebraic laws required for distributed convergence. This isn't an implementation bug. It's mathematically provable. **crdt-merge is the fix:** a patented two-layer architecture that makes *any* merge strategy — including inherently stochastic and non-commutative ones — fully CRDT-compliant.

The result: 26 strategies, all guaranteed to produce identical output regardless of merge order, grouping, or duplication. No coordination. No locking. No central arbiter.

> **Patent Pending** — UK Application No. 2607132.4

**[How it works — full architecture, mathematical proofs, and the 7 architectures we evaluated →](docs/CRDT_ARCHITECTURE.md)**

---

## What you can do with it

### Federated Model Merging Without a Parameter Server
100 hospitals train locally, merge globally — no coordinator, no single point of failure. Any node can produce the final model. Late arrivals are absorbed automatically. **[Guide →](docs/guides/federated-model-merging.md)**

### Convergent Multi-Agent AI
Agents share and merge beliefs via CRDT state — no orchestrator picks winners. Works offline, across partitions, at any scale. **[Guide →](docs/guides/convergent-multi-agent-ai.md)**

### Privacy-Preserving Merge
Merge encrypted data without decryption. Four AEAD backends. The merging party never sees plaintext. **[Guide →](docs/guides/privacy-preserving-merge.md)**

### The Right to Forget in Trained Models
GDPR erasure in milliseconds — surgically remove a contributor's influence without retraining. **[Guide →](docs/guides/right-to-forget-in-ai.md)**

### MergeQL — Query Language for Distributed Knowledge
SQL-like syntax for CRDT-correct multi-source merges with full provenance. **[Guide →](docs/guides/mergeql-distributed-knowledge.md)**

### Provenance-Complete AI
Per-field, per-decision audit trail — SHA-256 hash-chained, tamper-evident, EU AI Act ready. **[Guide →](docs/guides/provenance-complete-ai.md)**

### LoRA Adapter Merging
Mixed-rank adapters merged with per-module strategy selection and SVD rank harmonization. **[Guide →](docs/guides/lora-adapter-merging.md)**

### Continual Learning Without Catastrophic Forgetting
Absorb new tasks as post-training merges — no data replay, no model growth, full knowledge retention. **[Guide →](docs/guides/continual-learning-without-forgetting.md)**

### Gossip Protocol Sync
Serverless state convergence via digest-based anti-entropy. You provide the transport. **[Guide →](docs/guides/gossip-serverless-sync.md)**

### Probabilistic CRDTs at Planetary Scale
HyperLogLog, Bloom filters, Count-Min Sketch — all natively CRDT-mergeable across 500+ nodes. **[Guide →](docs/guides/probabilistic-crdt-analytics.md)**

### Delta Sync & Merkle Verification
Ship only what changed. Prove convergence in O(log n). **[Guide →](docs/guides/delta-sync-merkle-verification.md)**

### Runtime CRDT Verification
Property-based proof that any merge function satisfies all three laws. Catches violations at import time. **[Guide →](docs/guides/crdt-verification-toolkit.md)**

### Agentic Memory at Scale
O(1) dedup across 1M+ agent memories. Budget-aware context merge. Crash recovery from peers. **[Guide →](docs/guides/agentic-memory-at-scale.md)**

---

## Quick Start

```python
# Tabular
from crdt_merge import CRDTDataFrame
merged = CRDTDataFrame(df_a, node_id="a").merge(CRDTDataFrame(df_b, node_id="b"))

# Model weights
from crdt_merge.model import CRDTMergeState
state = CRDTMergeState()
state.add("model-a", weights_a)
state.add("model-b", weights_b)
merged = state.merge(strategy="slerp")  # order of add() never matters

# Verify any merge function
from crdt_merge import verified_merge

@verified_merge
def my_merge(a, b):
    return your_logic(a, b)  # raises CRDTViolationError if laws are broken
```

**[Full API reference →](docs/api-reference/README.md)**

---

## Installation

```bash
pip install crdt-merge            # Core — zero dependencies
pip install crdt-merge[fast]      # DuckDB + Polars (38.8× on A100)
pip install crdt-merge[model]     # PyTorch model weights
pip install crdt-merge[crypto]    # AEAD encryption backends
pip install crdt-merge[all]       # Everything
```

Zero required dependencies. Python 3.9–3.12. Linux, macOS, Windows.

**[All install options →](docs/getting-started/quickstart.md)**

---

## By the Numbers

| | |
|:---|:---:|
| Test suite | **3,041 tests, 0 failures** |
| CRDT compliance tests | **1,200 / 1,200** |
| Merge strategies | **26** |
| CRDT overhead | **< 0.5ms** per merge |
| Model speedup vs. naive | **38.8×** |
| Encryption backends | **4** |
| Architectures evaluated | **7 → 1 winner** |

---

## Cross-Language Ports

| Language | Package | Status |
|----------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) v0.9.4 | Full feature set |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) v0.2.0 | Core CRDTs + merge |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) v0.2.0 | Source complete |

---

## License

**BSL 1.1** → automatically converts to **Apache 2.0 on 29 March 2028**.

Free for research, personal use, and most production use. Source-available. Not free for competing commercial merge-as-a-service.

The [PATENTS](PATENTS) file includes a defensive patent grant (UK Application 2607132.4). See [LICENSE](LICENSE), [CLA](CLA.md).

Copyright 2026 Ryan Gillespie. Commercial licensing: rgillespie83@icloud.com · data@optitransfer.ch

---

<div align="center">

**[Documentation](docs/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[API Reference](docs/api-reference/README.md)** · **[Guides](docs/guides/README.md)** · **[Changelog](CHANGELOG.md)** · **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
