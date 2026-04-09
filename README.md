
<div align="center">

<h1>crdt-merge</h1>

<p><strong>Deterministic, order-independent merge for distributed models, data, and agent state.</strong></p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.5-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-6%2C179%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-crdt--merge-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge)
[![Data Merge](https://img.shields.io/badge/Data%20Merge-crdt--merge--data-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-data)
[![Federation](https://img.shields.io/badge/Federation-crdt--merge--federation-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-federation)
[![Convergence Lab](https://img.shields.io/badge/Convergence%20Lab-convergence--lab-yellow)](https://huggingface.co/spaces/Optitransfer/convergence-lab)

```
pip install crdt-merge
```

</div>

```python
from crdt_merge import merge

# Two nodes recorded overlapping data independently
node_a = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
node_b = [{"id": 2, "name": "Bob"},   {"id": 3, "name": "Carol"}]

# Order does not matter. Result is identical either way.
merged = merge(node_a, node_b, key="id")
print(merged)
# [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, {"id": 3, "name": "Carol"}]

assert merge(node_a, node_b, key="id") == merge(node_b, node_a, key="id")  # commutativity
```

**[Documentation](docs/README.md)** -- **[Quick Start](docs/getting-started/quickstart.md)** -- **[API Reference](docs/api-reference/README.md)** -- **[Architecture](docs/CRDT_ARCHITECTURE.md)** -- **[Changelog](CHANGELOG.md)**

---

## The problem

Standard merge strategies -- weight averaging, SLERP, TIES, DARE, Fisher -- are non-convergent in distributed settings. At least one of the three algebraic laws required for distributed convergence (commutativity, associativity, idempotency) fails for 25 of the 26 strategies analysed. This is not an implementation bug. It is a structural property of the algorithms themselves (Shapiro et al., 2011).

When merge order matters, distributed systems require coordination -- a central server to dictate sequence, locks to prevent concurrent merges, or consensus protocols to agree on state. These are the constraints that crdt-merge eliminates.

## The architecture

crdt-merge uses a **two-layer separation** that makes any merge strategy CRDT-compliant without modifying the strategy itself:

**Layer 1 -- CRDT collection.** An OR-Set (Observed-Remove Set) manages the set of contributions. Set union is trivially commutative, associative, and idempotent. Every contribution carries a Merkle-provenance hash chain for tamper-evident audit. This layer satisfies all three CRDT laws by construction.

**Layer 2 -- Deterministic strategy resolution.** A deterministic function applies the chosen merge strategy over the complete collected set. Because the input set is identical at every node (Layer 1 guarantees this), and the strategy function is deterministic, the output is identical at every node.

The strategy itself does not need to be a CRDT. SLERP remains SLERP. TIES remains TIES. The CRDT operates over the *set of inputs*, not over raw tensors. This is the core insight, and it is what allows 26 strategies -- including inherently stochastic and non-commutative ones -- to produce identical output regardless of merge order, grouping, or duplication.

**[Full architecture -- mathematical proofs and the 7 architectures evaluated ->](docs/CRDT_ARCHITECTURE.md)**

> **Research Paper** -- *Conflict-Free Replicated Data Types for Neural Network Model Merging.*
> Proves that 25 of 26 strategies are structurally incompatible with direct CRDT application, then presents the two-layer architecture that achieves compliance for all 26.
> **[Read the paper ->](paper/CRDT_Merge_ArXiv.pdf)** -- **[LaTeX source](paper/)**

---

## E4: trust as a CRDT dimension

v0.9.5 introduces E4 Recursive Trust-Delta Entanglement -- a protocol that makes trust a first-class algebraic dimension of the CRDT, entangled with data at the lattice level.

In every existing distributed merge system, trust and data are separate concerns. Authentication sits in front of the merge pipeline, but the merge itself is trust-blind. A malicious peer that passes the gate poisons the shared state, and the system has no mechanism to detect, score, or recover from the damage within the merge semantics themselves.

E4 eliminates this separation. Trust, data, causal clock, and Merkle hash form a single product lattice:

```
E4State = Data x Trust x Clock x Hash
```

Each dimension is a join-semilattice. The product of join-semilattices is a join-semilattice. Convergence is algebraic -- not a property that needs to be tested, but one that is inherited from the structure.

### What makes this different

**Six foundational primitives form the architecture.** Change detection, change encoding, and change verification handle the delta pipeline. Trust assignment and trust-gated application handle Byzantine filtering. The sixth -- recursive propagation -- is the contribution that binds them into a unified whole: trust changes propagate as data changes through the same delta pipeline they govern.

No existing literature combines all six. Delta-state CRDTs handle P1-P2 (Almeida et al., 2018). Authenticated data structures handle P3 (Papamanthou et al., 2013). Byzantine filtering exists in consensus protocols but not as CRDT-native semantics. P6 -- recursive trust-delta propagation -- is novel. When a peer's trust score changes, that change *is* a delta, encoded and verified through the same pipeline as data. Trust validates data integrity via Merkle. Data integrity validates trust evidence via proof verification. Both converge through shared CRDT semantics.

### Byzantine fault tolerance without consensus

The Symbiotic Lattice Trust (SLT) protocol replaces BFT consensus with lattice-native Byzantine detection. Each peer maintains a five-dimensional trust vector (integrity, causality, consistency, gossip, model) as per-dimension GCounters with homeostatic budget normalisation. Malicious behaviour triggers monotonic trust decay that propagates as CRDT deltas -- every honest peer converges on the same trust state without coordination.

SLT's threat model differs from classical BFT (Castro and Liskov, 1999). Classical BFT guarantees safety below n/3 through voting rounds. SLT operates without voting -- Byzantine detection emerges from trust score convergence across the lattice. The 34% tolerance threshold was measured empirically with actively Byzantine peers performing data injection, trust inflation, and selective withholding. The guarantee is CRDT convergence of trust state among honest peers, which then gates data application. End-to-end federation across 10 nodes with 2 Byzantine peers: 9.69ms.

### Delta encoding at scale

Projection delta encoding decomposes state changes through 256-ary Merkle tree differencing, extracts only the changed subtrees, and compresses through parameter-aware encoding. Deltas compose associatively -- chain any sequence and the result is identical to a single diff between the endpoints.

Validated on facebook/opt-6.7b (6.7 billion parameters). Causal clock throughput: 2.93M operations per second. Proof-carrying operation wire size: 128 bytes fixed. These measurements are from the causal clock and PCO subsystems specifically -- full end-to-end merge throughput on billion-parameter models depends on strategy, hardware, and compression ratio.

### Zero API changes

E4 activates transparently on `import crdt_merge`. Every existing function call works identically. Disable with `CRDT_MERGE_E4=0` if needed. The algebraic structure guarantees that enabling trust cannot break convergence -- the product lattice join is defined dimension-by-dimension, and the Data dimension join is unchanged.

**[E4 Architecture -- six primitives, formal lattice structure, full protocol specification ->](docs/e4/E4-MASTER-ARCHITECTURE.md)**

> **Patent** -- UK Application No. 2607132.4, GB2608127.3

---

## Three ways to use it

### 1. Federated model merging

100 hospitals train locally, merge globally. No coordinator. No single point of failure. Any node can produce the final model. Late arrivals are absorbed automatically. With E4 enabled, each peer carries trust scores -- a compromised node's contributions are automatically down-weighted and eventually ejected.

```python
import torch
from crdt_merge.model import ModelMerge, ModelMergeSchema

# Simulate independently trained model weights
weights_a = {"layer.weight": torch.randn(128, 64)}
weights_b = {"layer.weight": torch.randn(128, 64)}
base = {"layer.weight": torch.zeros(128, 64)}

schema = ModelMergeSchema({"default": "ties"})
result = ModelMerge(schema).merge([weights_a, weights_b], base=base)

print(result.tensor["layer.weight"].shape)  # torch.Size([128, 64])
```

**[Federated merging guide ->](docs/guides/federated-model-merging.md)**

### 2. LoRA adapter merging

Mixed-rank adapters merged with per-module strategy selection and SVD rank harmonisation. CRDT semantics guarantee that merging adapter A into B produces the same result as merging B into A -- enabling asynchronous adapter development across teams.

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

base = {"lora_A": torch.zeros(16, 768), "lora_B": torch.zeros(768, 16)}
schema = ModelMergeSchema({"default": "dare_ties"})
result = ModelMerge(schema).merge([
    {"lora_A": torch.randn(16, 768), "lora_B": torch.randn(768, 16)},
    {"lora_A": torch.randn(16, 768), "lora_B": torch.randn(768, 16)},
], base=base)
```

**[LoRA merging guide ->](docs/guides/lora-adapter-merging.md)**

### 3. Distributed tabular data

DataFrames, JSON, CSV -- merged with CRDT guarantees. Conflict-free deduplication with O(1) per-record cost. Schema evolution handled automatically.

```python
from crdt_merge import merge

# Two nodes independently recorded overlapping data
node_a = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
node_b = [{"id": 2, "name": "Bob"},   {"id": 3, "name": "Carol"}]

merged = merge(node_a, node_b, key="id")
# [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, {"id": 3, "name": "Carol"}]
```

**[Data merge guide ->](docs/guides/data-merge.md)**

---

## What else you can do

| Capability | Description | Guide |
|-----------|-------------|-------|
| **Convergent multi-agent AI** | Agents merge beliefs via CRDT state -- no orchestrator | [Guide](docs/guides/convergent-multi-agent-ai.md) |
| **Privacy-preserving merge** | Merge encrypted data without decryption (4 AEAD backends) | [Guide](docs/guides/privacy-preserving-merge.md) |
| **Right to forget** | GDPR erasure in milliseconds -- remove a contributor without retraining | [Guide](docs/guides/right-to-forget-in-ai.md) |
| **MergeQL** | SQL-like syntax for CRDT-correct multi-source merges | [Guide](docs/guides/mergeql-distributed-knowledge.md) |
| **Provenance-complete AI** | Per-field SHA-256 hash-chained audit trail, EU AI Act ready | [Guide](docs/guides/provenance-complete-ai.md) |
| **Continual learning** | Absorb new tasks as post-training merges -- no data replay | [Guide](docs/guides/continual-learning-without-forgetting.md) |
| **Gossip protocol sync** | Serverless convergence via digest-based anti-entropy | [Guide](docs/guides/gossip-serverless-sync.md) |
| **Probabilistic CRDTs** | HyperLogLog, Bloom filters, Count-Min Sketch -- natively mergeable | [Guide](docs/guides/probabilistic-crdt-analytics.md) |
| **Delta sync + Merkle verification** | Ship only what changed. Prove convergence in O(log n) | [Guide](docs/guides/delta-sync-merkle-verification.md) |
| **Runtime CRDT verification** | Property-based proof that any merge function satisfies all three laws | [Guide](docs/guides/crdt-verification-toolkit.md) |
| **Agentic memory** | O(1) dedup across 1M+ agent memories with budget-aware merge | [Guide](docs/guides/agentic-memory-at-scale.md) |

---

## When not to use crdt-merge

If you are merging two models on a single machine with a known, fixed order, you do not need CRDT guarantees. Standard merge tools (mergekit, model-stock) are simpler and have no overhead. crdt-merge adds value when:

- Multiple nodes merge independently without coordination
- Merge order is unknown or non-deterministic
- You need provenance, auditability, or tamper evidence
- Byzantine actors may be present in the merge network
- You need GDPR-compliant erasure from merged state

---

## Installation

```bash
pip install crdt-merge            # Core -- zero dependencies
pip install crdt-merge[fast]      # DuckDB + Polars (38.8x speedup on A100)
pip install crdt-merge[model]     # PyTorch model weights
pip install crdt-merge[crypto]    # AEAD encryption backends
pip install crdt-merge[all]       # Everything
```

Zero required dependencies. Python 3.9-3.12. Linux, macOS, Windows.

**[All install options ->](docs/getting-started/quickstart.md)**

---

## Measured performance

| Metric | Result | Context |
|--------|--------|---------|
| CRDT axiom compliance | 78/78 | All 26 strategies, all 3 laws |
| Test suite | 6,179 passing, 0 failures | Core + E4 + resilience |
| Byzantine fault tolerance | 34% | SLT protocol, empirically measured |
| Proof-carrying operation wire size | 128 bytes | Fixed cost per operation |
| Causal clock throughput | 2.93M ops/s | E4 causal clock subsystem |
| End-to-end federation | 9.69ms | 10 nodes, 2 actively Byzantine |
| Large-model delta validation | 6.7B parameters | facebook/opt-6.7b |
| Merkle avalanche coefficient | 0.500 | Cryptographically ideal |
| Adaptive verification gain | 12% throughput | At high trust levels |
| Delta composition | Associative to machine epsilon | Verified computationally |
| CRDT overhead per merge | < 0.5ms | Layer 1 collection overhead |
| Model merge speedup | 38.8x vs naive | DuckDB + Polars backend on A100 |
| Computational proofs | 328 | Across all subsystems |

---

## Cross-language ports

| Language | Package | Status |
|----------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) v0.9.5 | Full feature set |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) v0.2.0 | Core CRDTs + merge |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) v0.2.0 | Source complete |

---

## References

- Shapiro, M., Preguica, N., Baquero, C., and Zawirski, M. (2011). *Conflict-free Replicated Data Types.* SSS 2011.
- Almeida, P. S., Shoker, A., and Baquero, C. (2018). *Delta State Replicated Data Types.* Journal of Parallel and Distributed Computing, 111, 162-173.
- Castro, M. and Liskov, B. (1999). *Practical Byzantine Fault Tolerance.* OSDI 1999.
- Yadav, P., Tam, D., Choshen, L., Raffel, C., and Bansal, M. (2023). *TIES-Merging: Resolving Interference When Merging Models.* NeurIPS 2023.
- Yu, L., Yu, B., Yu, H., Huang, F., and Li, Y. (2024). *Language Model is a DARE Merge.* ICML 2024.

---

## License

**BSL 1.1** -- automatically converts to **Apache 2.0 on 29 March 2028**.

Free for research, personal use, and most production use. Source-available. Not free for competing commercial merge-as-a-service.

The [PATENTS](PATENTS) file includes a defensive patent grant (UK Application 2607132.4, GB2608127.3). See [LICENSE](LICENSE), [CLA](CLA.md).

Copyright 2026 Ryan Gillespie. Commercial licensing: rgillespie83@icloud.com -- data@optitransfer.ch

---

<div align="center">

**[Documentation](docs/README.md)** -- **[Architecture](docs/CRDT_ARCHITECTURE.md)** -- **[E4 Architecture](docs/e4/E4-MASTER-ARCHITECTURE.md)** -- **[API Reference](docs/api-reference/README.md)** -- **[Research Paper](paper/)** -- **[Guides](docs/guides/README.md)** -- **[Changelog](CHANGELOG.md)** -- **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
