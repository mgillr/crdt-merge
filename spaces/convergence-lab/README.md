---
title: CRDT-Merge Convergence Lab
emoji: 🔬
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 5.29.0
python_version: "3.12"
app_file: app.py
pinned: true
license: other
license_name: BUSL-1.1
license_link: https://github.com/mgillr/crdt-merge/blob/main/LICENSE
tags:
  - crdt
  - model-merging
  - distributed-systems
  - convergence
  - neural-network
  - federated-learning
short_description: "CRDT convergence proof: 100 nodes, 26 strategies"
---

# CRDT-Merge Multi-Node Convergence Laboratory

**Empirical proof that the two-layer CRDTMergeState architecture guarantees identical merged models across distributed nodes — regardless of merge ordering, network partitions, or strategy choice.**

> **Patent** — UK Application No. 2607132.4, GB2608127.3 | **E4 Trust-Delta Architecture**  
> **Paper**: *Conflict-Free Replicated Data Types for Neural Network Model Merging*  
> **Library**: [crdt-merge](https://pypi.org/project/crdt-merge/) v0.9.5

## Experiments

### 1. Multi-Node Convergence
Simulates N distributed nodes (up to 100), each contributing a unique model tensor. Nodes merge in multiple random orderings. Verifies that **all orderings produce bitwise-identical Merkle roots and resolved tensors**.

### 2. Network Partition & Healing
Splits nodes into isolated partitions. Each partition gossips internally and converges to its own state. Partitions are then healed (full gossip resumes). Verifies that **all nodes converge to the same state post-healing** — the core CRDT guarantee.

### 3. Cross-Strategy Sweep
Tests **every merge strategy** (weight averaging, SLERP, TIES, DARE, Fisher, evolutionary, and 7+ more) for convergence on the same node set. Verifies that the two-layer architecture provides **universal CRDT compliance regardless of strategy**.

### 4. Scalability Benchmark
Measures gossip and resolve overhead from 2 to 100 nodes. Confirms that the CRDT merge operation (set union on metadata) remains **sub-millisecond regardless of model size**, while resolve time scales linearly with contributions.

## Key Results

| Metric | Result |
|--------|--------|
| Max nodes tested | 100 |
| Strategies verified | 13/13 (no-base) |
| Convergence rate | 100% across all orderings |
| Partition healing | Always converges |
| CRDT merge overhead | < 0.5ms |
| Bitwise reproducibility | Guaranteed |
| E4 trust convergence | 0.000 max divergence, 3.84ms |
| E4 proof-carrying ops | 167K build/s, 101K verify/s |

## How It Works

The two-layer architecture separates concerns:

- **Layer 1 (CRDTMergeState)**: Manages a *set* of model contributions using OR-Set CRDT semantics. Merge = set union — trivially commutative, associative, idempotent.
- **Layer 2 (Strategy)**: Applies any merge strategy as a deterministic pure function over the canonically-ordered contribution set. Same inputs → same outputs.

Since Layer 1 guarantees all replicas converge to the same set of inputs, and Layer 2 is deterministic, **all replicas compute identical merged models**.

## Links

- **GitHub**: [mgillr/crdt-merge](https://github.com/mgillr/crdt-merge)
- **PyPI**: [crdt-merge](https://pypi.org/project/crdt-merge/)
- **Architecture**: [CRDT_ARCHITECTURE.md](https://github.com/mgillr/crdt-merge/blob/main/docs/CRDT_ARCHITECTURE.md)

---

Copyright 2026 Ryan Gillespie / Optitransfer
