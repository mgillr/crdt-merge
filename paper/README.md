# Conflict-Free Replicated Data Types for Neural Network Model Merging

**A Two-Layer Architecture Enabling CRDT-Compliant Model Merging Across 26 Strategies**

📄 **[Read the Paper (PDF)](./CRDT_Merge_ArXiv.pdf)**  ·  💻 **[Library Code](../)**

## Abstract

Applying Conflict-free Replicated Data Types (CRDTs) directly to neural network
weight tensors is impossible: we prove that 25 of 26 widely-used merge strategies
violate commutativity, associativity, or both. We present a two-layer architecture
that decouples membership tracking (Layer 1, an OR-Set CRDT) from strategy
execution (Layer 2, a deterministic resolve function), achieving guaranteed
convergence for all 26 strategies without modifying the underlying merge logic.
Verified at production scale on GPT-2-XL (1.5B), Phi-2 (2.7B), and
LLaMA-3.2-3B (3B parameters) with <0.5ms CRDT overhead.

## Key Results

- **Impossibility proof**: Direct CRDT application to weight merging fails for 25/26 strategies
- **26/26 strategies** made CRDT-compliant via the two-layer architecture
- **Byte-identical convergence** across 100 nodes with random gossip orderings
- **<0.5ms overhead** on 7B-parameter models
- **Merkle-root-derived seeding** ensures stochastic strategies produce deterministic results

## Files

| File | Description |
|------|-------------|
| `CRDT_Merge_ArXiv.pdf` | Compiled paper (PDF) |
| `CRDT_Merge_ArXiv.tex` | LaTeX source |
| `references.bib` | Bibliography (37 entries) |

## Citation

```bibtex
@article{gillespie2026crdt,
  title   = {Conflict-Free Replicated Data Types for Neural Network Model Merging},
  author  = {Gillespie, Ryan},
  year    = {2026}
}
```

## License

This paper is copyright 2026 Ryan Gillespie. The paper content is shared for academic reference. 
The [crdt-merge library](../) is available under [BSL 1.1 → Apache 2.0](../LICENSE).
