
<div align="center">

<h1>crdt-merge</h1>

<p><strong>Deterministic, order-independent merge for distributed models, data, and agent state.</strong></p>

[![PyPI version](https://img.shields.io/badge/pypi-v0.9.6-orange)](https://pypi.org/project/crdt-merge/)
[![Downloads](https://img.shields.io/pypi/dm/crdt-merge?label=downloads&color=brightgreen)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-7%2C945%20passing-brightgreen)](TEST_RESULTS.md)
[![CRDT Compliance](https://img.shields.io/badge/CRDT%20compliance-26%2F26%20strategies-blue)](docs/CRDT_ARCHITECTURE.md)
[![Crypto](https://img.shields.io/badge/crypto-Ed25519%20%2B%20ML--DSA--65-blue)](docs/security/CRYPTOGRAPHY.md)
[![License: BSL 1.1](https://img.shields.io/badge/license-BSL%201.1%20%E2%86%92%20Apache%202.0-orange)](LICENSE)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-crdt--merge-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge)
[![Data Merge](https://img.shields.io/badge/Data%20Merge-crdt--merge--data-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-data)
[![Federation](https://img.shields.io/badge/Federation-crdt--merge--federation-yellow)](https://huggingface.co/spaces/optitransfer/crdt-merge-federation)
[![Convergence Lab](https://img.shields.io/badge/Convergence%20Lab-convergence--lab-yellow)](https://huggingface.co/spaces/Optitransfer/convergence-lab)
[![Merged Model](https://img.shields.io/badge/Merged%20Model-Qwen2.5--7B--borg--merge--v1-blue)](https://huggingface.co/Optitransfer/Qwen2.5-7B-Instruct-borg-merge-v1)

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
> **[Read the paper ->](paper/CRDT_Merge_ArXiv.pdf)** -- **[LaTeX source](paper/)** -- **[SSRN](https://ssrn.com/abstract=6545518)**

### Why this enables cross-family merging

Standard weight merging requires models to share the same architecture -- identical key names, identical tensor shapes. A Qwen attention block and a Mistral attention block use different parameter names, different head dimensions, and different FFN layouts. Naive interpolation between them does not even type-check.

crdt-merge's canonical key namespace solves the first problem. The Layer 1 collection treats each model's tensors as contributions to a shared namespace, mapping architecture-specific parameter names (e.g. `model.layers.0.self_attn.q_proj.weight` in Qwen vs `model.layers.0.attention.wq.weight` in other families) to canonical roles. Ten architecture families are covered: BERT, RoBERTa, Llama/Qwen, Mistral, Pythia, OPT, Phi, T5, w2v-bert, and more.

With tensors in a shared namespace, Layer 2's deterministic resolution can apply per-tensor Procrustes alignment (orthogonal rotation via SVD) to map each donor's basis onto the anchor's, then absorb filtered deltas. The result is a single merged checkpoint in the anchor's native format -- standard `safetensors`, loadable by any HuggingFace-compatible stack.

[**Qwen2.5-7B-Instruct-borg-merge-v1**](https://huggingface.co/Optitransfer/Qwen2.5-7B-Instruct-borg-merge-v1) is the first published model built on this pipeline. Nine models from four architecture families (Llama, Phi, NeoX, OPT) merged into a single checkpoint -- no fine-tuning, no distillation, no router:

| Benchmark | Anchor (Qwen2.5-7B-Instruct) | Merged | Δ |
|---|---:|---:|---:|
| GSM8K | 0.8120 | **0.8446** | **+3.3 pp** |
| ARC-Challenge | 0.5256 | **0.5572** | **+3.2 pp** |
| IFEval | 0.6547 | **0.6811** | **+2.6 pp** |

Evaluated with `lm-eval-harness` 0.4.4 on a single A100 80 GB. Full 8-task surface and methodology on the [model card](https://huggingface.co/Optitransfer/Qwen2.5-7B-Instruct-borg-merge-v1). Deep-dive write-up: [**We Merged 9 Models from 4 Architecture Families into One -- and It Beats the Anchor on Real Benchmarks**](https://medium.com/@rgillespie83/we-merged-9-models-from-4-architecture-families-into-one-and-it-beats-the-anchor-on-real-e6537dfa9252).

---

## E4: trust as a CRDT dimension

v0.9.5 introduced E4 Recursive Trust-Delta Entanglement -- a protocol that makes trust a first-class algebraic dimension of the CRDT, entangled with data at the lattice level. **v0.9.6 hardens the cryptographic foundation with real Ed25519 signatures and NIST ML-DSA-65 post-quantum support.**

In every existing distributed merge system, trust and data are separate concerns. Authentication sits in front of the merge pipeline, but the merge itself is trust-blind. A malicious peer that passes the gate poisons the shared state, and the system has no mechanism to detect, score, or recover from the damage within the merge semantics themselves.

E4 eliminates this separation. Trust, data, causal clock, and Merkle hash form a single product lattice:

```
E4State = Data x Trust x Clock x Hash
```

Each dimension is a join-semilattice. The product of join-semilattices is a join-semilattice -- a standard result (Birkhoff 1940). The E4 contribution is **including Trust as a lattice dimension** alongside Data and letting it propagate through the same delta pipeline, not reinventing the product construction. Convergence of the unified system is then inherited from that standard result, so it does not need a separate proof.

### Cryptographic hardening (v0.9.6)

Every signature is now real cryptography when the optional `[crypto]` or `[security]` extras are installed:

- **Real Ed25519** on all PCO operations via the `cryptography` library. The previous v0.9.5 stub (which accepted any 64-byte blob) is preserved for backward compatibility when no key registry is configured.
- **Observer authentication** on `TrustEvidence` -- evidence is signed by its observer, preventing spoofed accusations. Timestamp is part of the signed payload, blocking replay.
- **NIST ML-DSA-65** post-quantum signatures via liboqs (`Dilithium3Scheme`). Real lattice-based cryptography, not the `DilithiumLite` hash-based placeholder.
- **Structured revocation proofs** -- `RevocationEntry.verify(registry=...)` validates real signatures over key_id + peer_id + reason + successor, rejecting the previous "any non-empty bytes passes" behaviour.

Opt in by configuring a key registry:

```python
from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification

configure_ed25519_verification(my_registry)       # real Ed25519 on PCOs
configure_evidence_verification(my_registry)      # observer auth on evidence
```

Without a registry, behaviour is identical to v0.9.5. Upgrade at your own pace.

### What makes this different

**Six foundational primitives form the architecture.** Change detection, change encoding, and change verification handle the delta pipeline. Trust assignment and trust-gated application handle Byzantine filtering. The sixth -- recursive propagation -- is the contribution that binds them into a unified whole: trust changes propagate as data changes through the same delta pipeline they govern.

No existing literature combines all six. Delta-state CRDTs handle P1-P2 (Almeida et al., 2018). Authenticated data structures handle P3 (Papamanthou et al., 2013). Byzantine filtering exists in consensus protocols but not as CRDT-native semantics. P6 -- recursive trust-delta propagation -- is novel. When a peer's trust score changes, that change *is* a delta, encoded and verified through the same pipeline as data. Trust validates data integrity via Merkle. Data integrity validates trust evidence via proof verification. Both converge through shared CRDT semantics.

### Byzantine fault tolerance without consensus

The Symbiotic Lattice Trust (SLT) protocol replaces BFT consensus with lattice-native Byzantine detection. Each peer maintains a five-dimensional trust vector (integrity, causality, consistency, gossip, model) as per-dimension GCounters with homeostatic budget normalisation. Malicious behaviour triggers monotonic trust decay that propagates as CRDT deltas -- every honest peer converges on the same trust state without coordination.

SLT is not a consensus protocol and does not claim PBFT equivalence. Classical BFT (Castro and Liskov, 1999) guarantees consensus safety below n/3 through voting rounds; SLT has no voting. Instead, Byzantine detection emerges from trust score convergence across the lattice, and the trust state gates data application. Under our evaluated harness -- 10 nodes, actively Byzantine peers performing data injection, trust inflation, and selective withholding -- honest peers continued to converge on identical trust state with up to 34% adversarial participation. This is an empirical measurement of the specific harness, not a theoretical bound. End-to-end federation across 10 nodes with 2 Byzantine peers: 9.69ms.

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

## When you do not need the CRDT layer

The CRDT convergence layer is unnecessary when merge order is fixed and known in advance -- a single researcher merging two models on one machine, for example. In that case, the CRDT overhead (sub-millisecond) is harmless but adds no value.

The rest of the library -- 26 merge strategies, E4 trust scoring, Merkle provenance, GDPR-compliant erasure, schema evolution, and the data/model/agent merge APIs -- works identically with or without the distributed convergence guarantee. You can use crdt-merge as a local merge toolkit and gain the CRDT properties for free if you later move to a distributed setting.

---

## Installation

```bash
pip install crdt-merge            # Core -- zero dependencies
pip install crdt-merge[fast]      # DuckDB + Polars (38.8x speedup on A100)
pip install crdt-merge[model]     # PyTorch model weights
pip install crdt-merge[crypto]    # AEAD encryption + real Ed25519 signatures
pip install crdt-merge[security]  # Ed25519 + NIST ML-DSA-65 post-quantum (new in 0.9.6)
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
| Adversarial-participant tolerance | 34% | SLT harness; honest peers still converge (not PBFT consensus) |
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

**BSL 1.1** -- automatically converts to **Apache 2.0 on 8 April 2028**.

Free for research, personal use, and most production use. Source-available. Not free for competing commercial merge-as-a-service.

The [PATENTS](PATENTS) file includes a defensive patent grant (UK Application 2607132.4, GB2608127.3). See [LICENSE](LICENSE), [CLA](CLA.md).

Copyright 2026 Ryan Gillespie. Commercial licensing: rgillespie83@icloud.com -- data@optitransfer.ch

---

<div align="center">

**[Documentation](docs/README.md)** -- **[Architecture](docs/CRDT_ARCHITECTURE.md)** -- **[E4 Architecture](docs/e4/E4-MASTER-ARCHITECTURE.md)** -- **[API Reference](docs/api-reference/README.md)** -- **[Research Paper](paper/)** -- **[Guides](docs/guides/README.md)** -- **[Changelog](CHANGELOG.md)** -- **[License](LICENSE)**

*Built by [Ryan Gillespie / Optitransfer](https://optitransfer.ch)*

</div>
