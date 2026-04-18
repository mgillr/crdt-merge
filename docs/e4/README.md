# E4 Recursive Trust-Delta Protocol

> **Trust is data. Data is trust.**

E4 makes trust a first-class CRDT dimension. Every merge operation carries cryptographic proof of provenance. Every delta propagates trust scores that converge with the same algebraic guarantees as the data itself. Byzantine actors are detected, isolated, and ejected -- no coordinator required.

Patent: UK Application No. 2607132.4, GB2608127.3

---

## Why E4 exists

Standard CRDTs guarantee convergence of *data*. They say nothing about whether the data should be trusted. A malicious node can inject arbitrary state and the CRDT will faithfully propagate it. E4 closes this gap by entangling trust with the lattice structure: merge and trust converge together, or not at all.

---

## Quick start

```python
import numpy as np
from crdt_merge.e4 import TypedTrustScore, TrustEvidence

# E4 activates transparently on import -- zero configuration
# Create typed trust scores for peers
score = TypedTrustScore()
print(score.overall_trust())  # 1.0 -- all peers start trusted

# Record evidence of misbehaviour
evidence = TrustEvidence(
    evidence_type="equivocation",
    peer_id="node-suspect",
    details={"description": "conflicting deltas from same causal slot"},
)
print(evidence.evidence_type)  # equivocation
```

Disable E4 if needed: `CRDT_MERGE_E4=0`

---

## Benchmark summary (H100 validation)

| Subsystem | Metric | Result |
|-----------|--------|--------|
| CRDT axiom compliance | 26 strategies x 3 axioms | 78/78 (0.0 residual) |
| Large-scale CRDT axiom trials on weight tensors | facebook/opt-1.3b + opt-6.7b | 156/156 PASS |
| Trust-bound Merkle | Bit diffusion (avalanche) | 0.500 (cryptographically ideal) |
| PCO wire format | Fixed size | 128 bytes |
| PCO throughput | Build / Verify | 167K / 101K ops/s |
| Causal trust clocks | Vector clock throughput | 2.93M ops/s |
| Adversarial-participant tolerance | SLT harness (not PBFT) | 34% |
| Byzantine pipeline | End-to-end (10 nodes, 2 Byzantine) | 9.69ms |
| Trust convergence | Max divergence | 0.0 |
| Trust convergence | Convergence time | 3.84ms |
| Adaptive verification | Zero trust / High trust | 97K / 109K ops/s |
| Trust-weighted influence | High-trust peer weight | 55.9% (vs 50% baseline) |
| Delta encoding | Throughput at 10K entries | 1.45M ops/s |
| Clock scaling | Throughput at 100K entries | 3.08M ops/s |
| Agent memory | Agents / Models | 3 / 4 (full convergence) |
| Tree scaling | Branching / Depth / Leaves | 256-ary, depth 4, 1B |
| Computational proofs | Total | 328 |
| Test functions | E4 + core | 1,681 + 4,498 = 6,179 |

---

## Architecture

E4 is structured as five interlocking subsystems:

**Trust Algebra** -- Typed multi-dimensional trust scores backed by GCounter evidence accumulation. Trust homeostasis prevents inflation through conserved-budget normalisation.

**Proof-Carrying Operations** -- Every merge operation is wrapped in a 128-byte proof envelope containing provenance hash, trust snapshot, and causal clock. Verification scales with trust: high-trust peers get fast-path validation.

**Projection Delta Encoding** -- Sparse delta representation maps billion-parameter model spaces into compact trust-annotated diffs. Achieves 1.45M ops/s at 10K entries.

**Symbiotic Lattice Trust (SLT)** -- Lattice-native Byzantine detection without consensus. Under our evaluated harness, honest peers converged on identical trust state with up to 34% actively Byzantine participants (honest distance 49.5 vs Byzantine 165.0). No coordinator, no voting rounds; 34% is an empirical measurement, not a PBFT-style theoretical bound.

**Resilience** -- 18 modules covering Sybil defence, longcon detection, epoch rotation, partition reconciliation, post-quantum signatures, and formal TLA+ specification (5/5 properties verified over 700 states).

---

## Documentation

- **[Master Architecture](E4-MASTER-ARCHITECTURE.md)** -- full technical specification
- **[Developer Guide](E4-DEVELOPER-GUIDE.md)** -- building with E4 trust scoring
- **[Integration Guide](E4-INTEGRATION-GUIDE.md)** -- wiring E4 into existing systems
- **[API Reference](E4-API-REFERENCE.md)** -- complete module and class reference
- **[Security Model](E4-SECURITY-MODEL.md)** -- threat model, Byzantine defence, resilience
- **[Peer Review](E4-PEER-REVIEW-ANALYSIS.md)** -- expert evaluation (9.0/10)
- **[Computational Evidence](E4-COMPUTATIONAL-EVIDENCE.md)** -- H100 validation results
- **[Changelog](E4-CHANGELOG.md)** -- E4-specific release history
