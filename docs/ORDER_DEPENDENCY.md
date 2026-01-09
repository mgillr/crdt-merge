# Strategy Order-Dependency Reference

> **Generated from:** crdt-merge v0.8.1 CRDT law analysis

This document classifies every model-merge strategy by its CRDT compliance
tier and documents the implications for distributed/federated merge
topologies. Release update implements architecture adjustment to ensure TRUE CRDT compliance.

## CRDT Tier Definitions

| Tier | Requirements | Safe Topology |
|:-----|:-------------|:--------------|
| **TRUE_CRDT** | Commutative + Associative + Idempotent | Fully decentralised — any merge order converges |
| **PARTIAL_CRDT** | At least one CRDT law holds | Restricted — star/hub-and-spoke topologies only |
| **NOT_CRDT** | No CRDT laws hold (or stochastic) | Centralised coordinator required |

## Strategy Classification

### PARTIAL_CRDT — Commutative + Associative (1 strategy)

`task_arithmetic` is the **only** strategy that satisfies both commutativity
and associativity.  Its additive formulation ``base + Σ(θᵢ − base)`` is
linear in the task vectors, so grouping does not change the result.
It is **not** idempotent: ``merge(A, A) = 2A − base ≠ A``.

| Strategy | Commutative | Associative | Idempotent | Notes |
|:---------|:-----------:|:-----------:|:----------:|:------|
| `task_arithmetic` | ✅ | ✅ | ❌ | Additive — `base + Σ(θᵢ - base)` is grouping-invariant |

### PARTIAL_CRDT — Commutative + Idempotent (17 strategies)

These strategies produce the same result regardless of input ordering and
return the input unchanged when merging a model with itself. However,
grouping matters: `merge(merge(A,B), C) ≠ merge(A, merge(B,C))`.

| Strategy | Commutative | Associative | Idempotent | Notes |
|:---------|:-----------:|:-----------:|:----------:|:------|
| `weight_average` | ✅ | ❌ | ✅ | Pairwise averaging weights later inputs more |
| `fisher_merge` | ✅ | ❌ | ✅ | Fisher proxy `|θ|²` changes on intermediates |
| `regression_mean` | ✅ | ❌ | ✅ | Self-weights `θᵢ² + λ` change on intermediates |
| `ties` | ✅ | ❌ | ❌ | Threshold/sign election differs on intermediates |
| `model_breadcrumbs` | ✅ | ❌ | ❌ | Binary mask differs on intermediate results |
| `emr` | ✅ | ❌ | ❌ | Elect-mask-rescale changes on intermediates |
| `star` | ✅ | ❌ | ❌ | Spectral truncation path-dependent |
| `svd_knot_tying` | ✅ | ❌ | ❌ | SVD bases change on intermediate merges |
| `adarank` | ✅ | ❌ | ❌ | Rank pruning decisions are path-dependent |
| `negative_merge` | ✅ | ❌ | ❌ | Task vector negation is path-dependent |
| `split_unlearn_merge` | ✅ | ❌ | ❌ | Unlearn mask differs on intermediates |
| `weight_scope_alignment` | ✅ | ❌ | ✅ | Normalization stats change on intermediates |
| `representation_surgery` | ✅ | ❌ | ✅ | Correction statistics path-dependent |
| `safe_merge` | ✅ | ❌ | ✅ | Safety mask computed per pair |
| `led_merge` | ✅ | ❌ | ✅ | Best-source selection is path-dependent |
| `ada_merging` | ~✅ | ~❌ | ✅ | Conditional — entropy coefficients are input-dependent |
| `dam` | ~✅ | ~❌ | ✅ | Conditional — iterative optimization is input-dependent |

### PARTIAL_CRDT — Commutative Only (2 strategies)

| Strategy | Commutative | Associative | Idempotent | Notes |
|:---------|:-----------:|:-----------:|:----------:|:------|
| `slerp` | ~✅ | ❌ | ✅ | Conditional commutativity (t=0.5 only) |
| `linear` | ~✅ | ❌ | ✅ | Conditional commutativity (t=0.5 only) |

### NOT_CRDT — Stochastic (5 strategies)

These strategies use random number generators, making them inherently
non-deterministic across different merge orderings.

| Strategy | Commutative | Associative | Idempotent | Notes |
|:---------|:-----------:|:-----------:|:----------:|:------|
| `dare` | ❌ | ❌ | ❌ | Random drop masks |
| `della` | ❌ | ❌ | ❌ | Random low-rank masks |
| `dare_ties` | ❌ | ❌ | ❌ | Hybrid DARE + TIES random masks |
| `evolutionary_merge` | ❌ | ❌ | ❌ | CMA-ES population is seed-dependent |
| `genetic_merge` | ❌ | ❌ | ❌ | Genetic crossover/mutation is seed-dependent |

## Guidance for Distributed Systems

### If you need eventual consistency (CRDT guarantees):
1. **Use single-call N-way merge** — pass all models to `merge([...])` at once
2. **Use a hub-and-spoke topology** — one coordinator collects all models, merges once
3. **Avoid cascaded pairwise merges** — they produce different results depending on grouping

### If you use pairwise cascaded merges:
1. Accept that order matters — document your merge tree
2. Use deterministic strategies (avoid `dare`, `della`, `evolutionary_merge`, `genetic_merge`)
3. Prefer `weight_average` or `fisher_merge` — they have the smallest associativity deviation

### If you need true CRDT semantics:
1. Wrap your merge in a coordinator that collects all updates before merging
2. Or use the primitive CRDTs (GCounter, PNCounter, LWWRegister, ORSet) which are true CRDTs
