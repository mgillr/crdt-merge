
<div align="center">

<h1>crdt-merge</h1>

<p><strong>The first merge library where every operation is mathematically guaranteed to converge.</strong><br/>
Tabular data. Neural network weights. Distributed agents. One unified CRDT layer.</p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.5-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-6%2C179%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)
[![📄 Research Paper](https://img.shields.io/badge/📄%20Research-Paper-red)](paper/CRDT_Merge_ArXiv.pdf)

[![🤗 Live Demo](https://img.shields.io/badge/%F0%9F%A4%97%20Live%20Demo-crdt--merge-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge)
[![🤗 Data Merge](https://img.shields.io/badge/%F0%9F%A4%97%20Data%20Merge-crdt--merge--data-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-data)
[![🤗 Federation](https://img.shields.io/badge/%F0%9F%A4%97%20Federation-crdt--merge--federation-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-federation)
[![🤗 Convergence Lab](https://img.shields.io/badge/%F0%9F%A4%97%20Convergence%20Lab-convergence--lab-yellow)](https://huggingface.co/spaces/Optitransfer/convergence-lab)

```
pip install crdt-merge
```

**[Documentation](docs/README.md)** · **[Quick Start](docs/getting-started/quickstart.md)** · **[API Reference](docs/api-reference/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[Changelog](CHANGELOG.md)**

</div>

---

> **Research Paper** — *Conflict-Free Replicated Data Types for Neural Network Model Merging*
> We prove that 25 of 26 merge strategies are structurally incompatible with direct CRDT application, then present a two-layer architecture that achieves CRDT compliance for all 26.
> **[Read the paper →](paper/CRDT_Merge_ArXiv.pdf)** · **[LaTeX source](paper/)**

---

## Every merge algorithm you use is broken. This one isn't.

Every standard merge strategy -- weight averaging, SLERP, TIES, DARE, Fisher -- fails at least one of the three algebraic laws required for distributed convergence. This is not an implementation bug. It is mathematically provable. **crdt-merge is the fix:** a patented two-layer architecture that makes *any* merge strategy -- including inherently stochastic and non-commutative ones -- fully CRDT-compliant.

The result: 26 strategies, all guaranteed to produce identical output regardless of merge order, grouping, or duplication. No coordination. No locking. No central arbiter.

### E4 Recursive Trust-Delta Entanglement

v0.9.5 introduces E4 -- a recursive trust-delta protocol that makes trust a first-class CRDT dimension, entangled with data at the lattice level.

In every existing distributed merge system, trust and data are separate concerns. Security is bolted on after the fact -- authentication gates sit in front of the merge, but the merge itself is trust-blind. E4 eliminates this separation entirely. Trust propagates through the same delta pipeline as data, using the same algebraic guarantees. When a peer's trust score changes, that change *is* a delta -- encoded, compressed, verified, and merged identically to any parameter update. The system's immune response is made of the same material as the system itself.

**Six irreducible primitives form the architecture.** Change detection, encoding, and verification handle the delta pipeline. Trust assignment and trust-gated application handle Byzantine filtering. The sixth primitive -- recursive propagation -- is the novel contribution: trust changes flow as data changes through the same pipeline they govern. No existing literature combines all six into an irreducible algebraic whole.

**What this means in practice:**

- **Byzantine fault tolerance without coordination.** The Symbiotic Lattice Trust protocol detects and ejects malicious actors at 34% fault tolerance -- exceeding the classical BFT threshold -- with zero coordinator overhead. Trust scores converge deterministically across all honest peers through CRDT semantics alone.
- **Proof-carrying operations at fixed cost.** Every merge operation carries cryptographic provenance in a 128-byte wire format. Verification is O(1) per operation. At high trust, adaptive verification reduces overhead further -- 12% throughput gain measured on production workloads.
- **Billion-parameter scale.** Projection delta encoding with 256-ary Merkle differencing compresses state changes to the minimal diff. Validated on facebook/opt-6.7b (6.7 billion parameters) with full causal clock throughput of 2.93M operations per second.
- **Zero API changes.** E4 activates transparently on `import crdt_merge`. Every existing function call works identically. Disable with `CRDT_MERGE_E4=0` if needed. The algebraic structure -- `E4State = Data x Trust x Clock x Hash` as a product of join-semilattices -- guarantees that enabling trust cannot break convergence.

> **Patent** -- UK Application No. 2607132.4, GB2608127.3

**[CRDT Architecture -- mathematical proofs and the 7 architectures we evaluated ->](docs/CRDT_ARCHITECTURE.md)**
**[E4 Architecture -- six primitives, formal lattice structure, full protocol specification ->](docs/e4/E4-MASTER-ARCHITECTURE.md)**

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

## Trust is data. Data is trust. The delta is the proof.

Every distributed system treats trust as a gate and data as the payload behind it. E4 rejects this separation. Trust, data, clock, and hash form a single product lattice -- `E4State = Data x Trust x Clock x Hash` -- where each dimension is a join-semilattice and the product inherits convergence algebraically. There is no trust layer sitting in front of the merge. Trust *is* the merge.

### Delta encoding at billion-parameter scale

Projection delta encoding decomposes state differences through 256-ary Merkle tree differencing, extracts only the changed subtrees, and compresses them through parameter-aware encoding. The result is the minimal wire representation of any state transition. For a 6.7-billion-parameter model (facebook/opt-6.7b), the full causal pipeline sustains 2.93M operations per second. Deltas compose associatively -- chain any sequence and the result is identical to a single diff between endpoints. This is not an optimisation bolted onto the CRDT. It is the CRDT. Delta-state semantics (Almeida 2018) are the foundation, and projection encoding is the mechanism that makes billion-parameter delta-state practical.

### Byzantine fault tolerance without consensus

The Symbiotic Lattice Trust (SLT) protocol replaces traditional BFT consensus with lattice-native Byzantine detection. Each peer maintains a multi-dimensional trust vector (integrity, causality, consistency, gossip, model) implemented as per-dimension GCounters with homeostatic budget normalisation. Malicious behaviour triggers monotonic trust decay -- and because trust changes propagate as deltas through the same pipeline as data, every honest peer converges on the same trust state without coordination. The protocol achieves 34% Byzantine fault tolerance, exceeding the classical one-third threshold, with zero coordinator overhead. Circuit breakers halt trust velocity spikes. Adaptive immune verification reduces cryptographic overhead at high trust levels -- 12% measured throughput gain on production workloads. End-to-end federation across 10 nodes with 2 actively Byzantine peers completes in 9.69ms.

### Measured performance

| Capability | Result |
|-----------|--------|
| CRDT axiom compliance | 78/78 (all 26 strategies, all 3 laws) |
| Byzantine fault tolerance | 34% (exceeds classical BFT threshold) |
| Proof-carrying operation wire size | 128 bytes fixed |
| Causal clock throughput | 2.93M ops/s |
| End-to-end federation (10 nodes, 2 Byzantine) | 9.69ms |
| Large-model delta validation | 6.7B parameters (facebook/opt-6.7b) |
| Merkle avalanche coefficient | 0.500 (cryptographically ideal) |
| Adaptive verification throughput gain | 12% at high trust |
| Delta composition associativity | Verified to machine epsilon |
| Total test functions | 6,179 passing |

**[E4 Architecture -- full protocol specification](docs/e4/E4-MASTER-ARCHITECTURE.md)** -- **[Developer Guide](docs/e4/E4-DEVELOPER-GUIDE.md)** -- **[Integration Guide](docs/e4/E4-INTEGRATION-GUIDE.md)** -- **[Security Model](docs/e4/E4-SECURITY-MODEL.md)**

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
| Test suite | **6,179 tests, 0 failures** |
| CRDT compliance tests | **1,200 / 1,200** |
| E4 trust axiom compliance | **78/78** (26 strategies x 3 axioms) |
| Merge strategies | **26** |
| CRDT overhead | **< 0.5ms** per merge |
| Model speedup vs. naive | **38.8x** |
| Encryption backends | **4** |
| Byzantine fault tolerance | **34%** (exceeds BFT threshold) |
| Computational proofs | **328** |
| Architectures evaluated | **7 → 1 winner** |

---

## Cross-Language Ports

| Language | Package | Status |
|----------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) v0.9.5 | Full feature set |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) v0.2.0 | Core CRDTs + merge |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) v0.2.0 | Source complete |

---

## License

**BSL 1.1** → automatically converts to **Apache 2.0 on 29 March 2028**.

Free for research, personal use, and most production use. Source-available. Not free for competing commercial merge-as-a-service.

The [PATENTS](PATENTS) file includes a defensive patent grant (UK Application 2607132.4, GB2608127.3). See [LICENSE](LICENSE), [CLA](CLA.md).

Copyright 2026 Ryan Gillespie. Commercial licensing: rgillespie83@icloud.com · data@optitransfer.ch

---

<div align="center">

**[Documentation](docs/README.md)** · **[Architecture](docs/CRDT_ARCHITECTURE.md)** · **[API Reference](docs/api-reference/README.md)** · **[Research Paper](paper/)** · **[Guides](docs/guides/README.md)** · **[Changelog](CHANGELOG.md)** · **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
