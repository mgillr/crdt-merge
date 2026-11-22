# Conflict-Free Replicated Data Types for Neural Network Model Merging

**A Two-Layer Architecture Enabling CRDT-Compliant Model Merging Across 26 Strategies**

**[arXiv:2605.19373](https://arxiv.org/abs/2605.19373)**  ·  **[Read the Paper (PDF)](./CRDT_Merge_ArXiv.pdf)**  ·  **[Library Code](../)**

This folder holds version 1 as published on arXiv on 16 May 2026.

## Abstract

Neural network merge strategies cannot be used directly as the merge operation of
a Conflict-free Replicated Data Type (CRDT): all 26 strategies we tested fail at
least one of commutativity, associativity and idempotency, and 25 of 26 fail
associativity. We present a two-layer architecture
that decouples membership tracking (Layer 1, an OR-Set CRDT) from strategy
execution (Layer 2, a deterministic resolve function), achieving guaranteed
convergence for all 26 strategies without modifying the underlying merge logic.
Verified at production scale on GPT-2-XL (1.5B parameters) and Mistral-7B
(7.24B parameters), with CRDT overhead below 0.5 ms.

## Key Results

- **Algebraic audit**: on controlled 4x4 tensors none of the 26 strategies satisfies all three CRDT properties, and 25/26 fail associativity
- **26/26 strategies** made CRDT-compliant via the two-layer architecture
- **Byte-identical convergence** across 100 nodes with random gossip orderings
- **CRDT overhead below 0.5 ms**
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
  title   = {Conflict-Free Replicated Data Types for Neural Network Model Merging:
             A Two-Layer Architecture Enabling {CRDT}-Compliant Model Merging Across 26 Strategies},
  author  = {Gillespie, Ryan},
  year    = {2026},
  journal = {arXiv preprint arXiv:2605.19373},
  eprint  = {2605.19373},
  archivePrefix = {arXiv}
}
```

## License

This paper is copyright 2026 Ryan Gillespie. The paper content is shared for academic reference. 
The [crdt-merge library](../) is available under [BSL 1.1 → Apache 2.0](../LICENSE).
