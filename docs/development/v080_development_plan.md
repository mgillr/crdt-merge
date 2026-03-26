# v0.8.0 Development Plan — "The Intelligence Release"

> **ModelCRDT + Protocol Engine**
>
> **Target:** ~14,500 LOC (+5,000) · ~1,800 Tests (+700) · **Zero Breaking Changes**
>
> **License:** BSL-1.1 (Business Source License) — ultra-open Additional Use Grant
>
> **Copyright:** 2026 Ryan Gillespie / Optitransfer

---

## Executive Summary

v0.8.0 transforms crdt-merge from a tabular-data merge engine into the **only comprehensive CRDT merge framework** covering both structured data AND model weights under one algebraic framework. This release introduces ModelCRDT — a CRDT-native model merge engine with 26 strategies, per-parameter provenance, conflict heatmaps, and formal verification.

**What makes this unique:** Every existing model merging tool (MergeKit, FusionBench, Mergenetic) treats merging as a one-shot operation with zero provenance, zero verification, and zero reversibility. ModelCRDT brings the same algebraic rigor crdt-merge applies to tabular data into the model weight space.

---

## Architecture Overview

```
crdt_merge/
├── model/                           # NEW — The Intelligence Module
│   ├── __init__.py                  # Public API surface
│   ├── core.py                      # ModelCRDT class, ModelMergeSchema
│   ├── strategies/
│   │   ├── __init__.py              # Strategy registry + plugin discovery
│   │   ├── base.py                  # ModelMergeStrategy ABC
│   │   ├── basic.py                 # WeightAverage, SLERP, TaskArithmetic, LinearInterp
│   │   ├── subspace.py             # TIES, DARE, DELLA, DARE-TIES, Breadcrumbs, EMR, STAR, SVDKnot, AdaRank
│   │   ├── weighted.py             # Fisher, RegMean, AdaMerging, DAM
│   │   ├── evolutionary.py         # CMA-ES, Genetic
│   │   ├── unlearning.py           # NegMerge, SplitUnlearnMerge
│   │   ├── calibration.py          # WeightScopeAlignment, RepresentationSurgery
│   │   └── safety.py               # SafeMERGE, LED-Merging
│   ├── lora.py                      # LoRA/adapter first-class support
│   ├── pipeline.py                  # Multi-stage merge pipelines (DAG-based)
│   ├── evolutionary.py              # CMA-ES/genetic optimizer orchestration
│   ├── provenance.py                # Per-parameter provenance tracking 
│   ├── heatmap.py                   # Conflict heatmaps + layer disagreement 
│   ├── safety.py                    # Safety-critical layer detection
│   ├── continual.py                 # Continual/sequential merge
│   ├── federated.py                 # FedAvg/FedProx as CRDT operations
│   ├── formats.py                   # MergeKit config import/export, FusionBench compat
│   └── gpu.py                       # GPU acceleration, lazy torch loading
```

### Design Principles

1. **Lazy torch import** — `torch` is NEVER loaded unless model features are explicitly used. The core crdt-merge package remains zero-dependency.
2. **Backend-agnostic tensors** — Strategies operate on numpy arrays by default, with optional torch/GPU acceleration. Pure-Python fallback for everything.
3. **CRDT verification** — Every strategy declares its CRDT properties and can be verified at runtime.
4. **Per-parameter provenance** — Every merge operation tracks which source contributed which parameters.
5. **Zero breaking changes** — All existing v0.7.x APIs remain unchanged. ModelCRDT is purely additive.

---

## Dev Team Assignment

### Phase 1 — Foundation Layer (~600 lines, ~120 tests)
**Owner:** `model/core.py`, `model/strategies/base.py`, `model/strategies/__init__.py`, `model/__init__.py`

**Deliverables:**
- `ModelCRDT` class with `merge()`, `merge_with_provenance()`, `verify()` methods
- `ModelMergeSchema` with per-layer strategy assignment (glob patterns, ranges, regex)
- `ModelMergeStrategy` ABC with common interface:
  - `merge(tensors, weights=None, **kwargs) → tensor`
  - `crdt_properties → dict` (commutative, associative, idempotent)
  - `name → str`, `category → str`, `paper_reference → str`
- Strategy registry with `@register_strategy` decorator
- Entry point discovery for community plugins
- Model weight I/O abstraction (safetensors, PyTorch state_dict, numpy arrays)

**Dependencies:** None (foundation — no internal deps)
**Tests:** CRDT law verification for ModelCRDT, schema pattern matching, registry, roundtrip

---

### Phase 2 — Basic Strategies (~400 lines, ~100 tests)
**Owner:** `model/strategies/basic.py`

**Deliverables — 4 strategies:**

| # | Strategy | Class | Operation | CRDT |
|---|----------|-------|-----------|------|
| 1 | Weight Averaging | `WeightAverage` | θ = Σ(αᵢ·θᵢ) | |
| 2 | SLERP | `SphericalLinearInterpolation` | Spherical interp | |
| 3 | Task Arithmetic | `TaskArithmetic` | θ = θ_base + Σ(αᵢ·τᵢ) | |
| 4 | Linear Interpolation | `LinearInterpolation` | θ = (1-t)·θ₁ + t·θ₂ | |

**Academic citations required for each strategy.**
**Dependencies:** Phase 1 (base.py ABC)
**Tests:** Commutativity/associativity verification, edge cases (zero weights, single model, empty tensors)

---

### Phase 3 — Subspace / Sparsification Strategies (~800 lines, ~120 tests)
**Owner:** `model/strategies/subspace.py`

**Deliverables — 9 strategies:**

| # | Strategy | Class | Paper | CRDT |
|---|----------|-------|-------|------|
| 5 | TIES-Merging | `TIESMerge` | Yadav, NeurIPS 2023 | |
| 6 | DARE | `DareDropAndRescale` | Yu, 2024 | stochastic |
| 7 | DELLA | `DellaDropElectLowRank` | Bansal, 2024 | stochastic |
| 8 | DARE-TIES | `DareTiesHybrid` | Community, 2024 | +|
| 9 | Model Breadcrumbs | `ModelBreadcrumbs` | Davari, 2023 | |
| 10 | EMR-Merging | `EMRMerge` | Huang, 2024 | |
| 11 | STAR | `SpectralTruncationAdaptiveRescaling` | 2025 | |
| 12 | SVD Knot-Tying | `SVDKnotTying` | 2024 | |
| 13 | AdaRank | `AdaptiveRankPruning` | ICLR 2026 | |

**Dependencies:** Phase 1 (base.py ABC), numpy
**Tests:** Each strategy with varying tensor sizes, sparsity levels, reproducibility (seed-deterministic)

---

### Phase 4 — Weighted, Evolutionary, Unlearning, Calibration, Safety Strategies (~700 lines, ~100 tests)
**Owner:** `model/strategies/weighted.py`, `model/strategies/evolutionary.py`, `model/strategies/unlearning.py`, `model/strategies/calibration.py`, `model/strategies/safety.py`

**Deliverables — 12 strategies:**

| # | Strategy | File | Paper | CRDT |
|---|----------|------|-------|------|
| 14 | Fisher-Weighted | weighted.py | Matena, 2022 | |
| 15 | RegMean | weighted.py | Jin, 2023 | |
| 16 | AdaMerging | weighted.py | Yang, 2024 | adaptive |
| 17 | DAM | weighted.py | 2024 | adaptive |
| 18 | CMA-ES Evolutionary | evolutionary.py | Sakana AI, 2024 | (meta) |
| 19 | Genetic Merge | evolutionary.py | Mergenetic, 2025 | (meta) |
| 20 | NegMerge | unlearning.py | ICML 2025 | |
| 21 | Split-Unlearn-Merge | unlearning.py | 2025 | |
| 22 | Weight Scope Alignment | calibration.py | 2024 | |
| 23 | Representation Surgery | calibration.py | 2024 | post-proc |
| 24 | SafeMERGE | safety.py | 2025 | |
| 25 | LED-Merging | safety.py | 2025 | |

**Dependencies:** Phase 1 (base.py ABC), numpy
**Tests:** Strategy-specific verification, fitness function interface, unlearning correctness

---

### Phase 5 — LoRA, Pipeline, Provenance, Heatmap (~800 lines, ~140 tests)
**Owner:** `model/lora.py`, `model/pipeline.py`, `model/provenance.py`, `model/heatmap.py`

**Deliverables:**

**LoRA Module:**
- `LoRAMerge` class with `merge_adapters()`, `apply_to_base()`
- `LoRAMergeSchema` for per-module strategy assignment
- Rank harmonization across mismatched adapters
- QLoRA support, multi-adapter fusion
- Adapter provenance tracking

**Pipeline Module:**
- `MergePipeline` with DAG-based stage execution
- Stage references via `$stage_name` syntax
- Checkpoint/resume, pipeline-level provenance
- Pipeline templates for common patterns

**Provenance Module (Unicorn Feature #3):**
- Per-parameter provenance tracking
- `dominant_source`, `contribution_map`, `conflict_score`
- Aggregate provenance summaries
- Export to JSON/CSV

**Heatmap Module (Unicorn Feature #4):**
- `ConflictHeatmap.from_merge(result)`
- Layer-level and parameter-level conflict maps
- Sign agreement maps, magnitude distribution
- Export to JSON/CSV for D3/Plotly visualization

**Dependencies:** Phase 1 (core.py), Phase 2-4 (strategies)
**Tests:** LoRA rank harmonization, pipeline DAG execution, provenance accuracy, heatmap generation

---

### Dev 6 — Continual, Federated, Formats, GPU (~600 lines, ~120 tests)
**Owner:** `model/continual.py`, `model/federated.py`, `model/formats.py`, `model/gpu.py`

**Deliverables:**

**Continual Merge:**
- `ContinualMerge` with `absorb()`, `export()`, memory budget
- Incremental model updates without catastrophic forgetting
- Replace/update semantics, full history tracking

**Federated Learning Bridge:**
- `FederatedMerge` with `submit()`, `aggregate()`
- FedAvg (sample-weighted), FedProx (proximal regularization)
- Client contribution provenance, straggler handling

**Format Compatibility:**
- `import_mergekit_config()` — YAML → ModelCRDT schema
- `export_mergekit_config()` — ModelCRDT → MergeKit YAML
- FusionBench evaluation bridge

**GPU Acceleration:**
- `GPUMerge` with lazy torch, CUDA-aware ops
- Automatic chunking for 7B+ models
- CPU offloading, multi-GPU support
- float16/bfloat16 precision

**Dependencies:** Phase 1 (core.py), Phase 2-4 (strategies)
**Tests:** Continual absorb/replace, federated aggregation, MergeKit YAML roundtrip, GPU fallback

---

## Phased Implementation Schedule

### Phase 1: Foundation (Phase 1)
```
Commit: "feat(model): foundation — ModelCRDT, ModelMergeSchema, strategy ABC"
Push: After tests pass
```

### Phase 2: Basic + Subspace Strategies (Phase 2 + Phase 3)
```
Commit: "feat(model): 13 merge strategies — basic (4) + subspace (9)"
Push: After tests pass
```

### Phase 3: Remaining Strategies (Phase 4)
```
Commit: "feat(model): 12 merge strategies — weighted, evolutionary, unlearning, calibration, safety"
Push: After tests pass
```

### Phase 4: LoRA + Pipeline + Provenance + Heatmap (Phase 5)
```
Commit: "feat(model): LoRA merging, pipelines, per-parameter provenance, conflict heatmaps"
Push: After tests pass
```

### Phase 5: Continual + Federated + Formats + GPU (Dev 6)
```
Commit: "feat(model): continual merge, federated bridge, MergeKit compat, GPU acceleration"
Push: After tests pass
```

### Phase 6: Integration + Release
```
Commit: "feat: v0.8.0 — The Intelligence Release"
Push: Final integration tests, version bump, PyPI publish
```

---

## Strategy Catalog Summary — 25 Strategies in 8 Categories

| Cat | Category | Count | Strategies |
|-----|----------|------:|------------|
| 1 | Basic | 4 | WeightAverage, SLERP, TaskArithmetic, LinearInterpolation |
| 2 | Subspace / Sparsification | 9 | TIES, DARE, DELLA, DARE-TIES, Breadcrumbs, EMR, STAR, SVDKnot, AdaRank |
| 3 | Weighted / Importance | 4 | Fisher, RegMean, AdaMerging, DAM |
| 4 | Evolutionary | 2 | CMA-ES, Genetic |
| 5 | Unlearning | 2 | NegMerge, SplitUnlearnMerge |
| 6 | Post-Calibration | 2 | WeightScopeAlignment, RepresentationSurgery |
| 7 | Safety-Aware | 2 | SafeMERGE, LED-Merging |
| 8 | **Total** | **25** | — |

CRDT Properties:
- Full CRDT (commutative + associative): 15 strategies
- Stochastic (seed-deterministic): 3 strategies (DARE, DELLA, DARE-TIES)
- Adaptive (learned coefficients, final merge commutative): 2 strategies
- Pairwise only (commutative at t=0.5): 2 strategies
- Post-processing: 1 strategy (RepresentationSurgery)

---

## Unicorn Features Delivered at v0.8.0

| # | Feature | Status |
|---|---------|--------|
| 0 | Per-field merge strategies | v0.5.1 |
| 1 | Formal CRDT verification | v0.5.1 |
| 2 | SQL-based merge (MergeQL) | v0.7.0 |
| 3 | Per-parameter provenance for model merges | 🆕 v0.8.0 |
| 4 | Conflict heatmaps / layer disagreement | 🆕 v0.8.0 |
| 5 | CRDT-verified model merging (26 strategies) | 🆕 v0.8.0 |
| 6 | LoRA-native merge with rank harmonization | 🆕 v0.8.0 |
| 7 | Evolutionary merge optimization | 🆕 v0.8.0 |

---

## Competitive Position at v0.8.0

| Capability | crdt-merge v0.8 | MergeKit (6.9K ⭐) | FusionBench | Mergenetic |
|-----------|-----------------|-------------------|-------------|------------|
| Merge strategies | 25 | ~10 | Eval only | Evolutionary only |
| CRDT verification | | | | |
| Per-param provenance | | | | |
| Conflict heatmaps | | | | |
| LoRA first-class | | | | |
| Evolutionary merge | | | | |
| Safety-aware merge | | | | |
| Continual merge | | | | |
| Federated bridge | | | | |
| Plugin architecture | | | | |
| MergeKit compat | (import/export) | Native | | |
| License | BSL-1.1 → Apache-2.0 | LGPL-3.0 | Apache-2.0 | MIT |
| Tabular + Model | | (model only) | (eval only) | (model only) |

---

## Testing Requirements

### Per-Strategy Tests (minimum):
- Commutativity: `merge(A,B) == merge(B,A)` for 100+ random tensor pairs
- Associativity: `merge(merge(A,B),C) == merge(A,merge(B,C))` where applicable
- Idempotency: `merge(A,A) == A` where applicable
- Edge cases: zero tensors, single model, mismatched shapes, NaN handling
- Reproducibility: seed-deterministic for stochastic strategies

### Integration Tests:
- Full pipeline: load → schema → merge → provenance → verify → export
- LoRA: rank harmonization → merge → apply to base → verify
- Pipeline: multi-stage DAG → checkpoint → resume → verify
- Federated: multi-client submit → aggregate → provenance
- Formats: MergeKit YAML → import → merge → export → validate

### Scale Tests:
- Small models: 1M parameters (CPU, < 1 second)
- Medium models: 100M parameters (CPU, < 30 seconds)
- Large models: 1B+ parameters (GPU optional, chunked)

---

## File Manifest

| File | Lines | Dev | Purpose |
|------|------:|-----|---------|
| `model/__init__.py` | ~80 | 1 | Public API |
| `model/core.py` | ~300 | 1 | ModelCRDT, ModelMergeSchema |
| `model/strategies/__init__.py` | ~100 | 1 | Registry, plugin discovery |
| `model/strategies/base.py` | ~120 | 1 | ModelMergeStrategy ABC |
| `model/strategies/basic.py` | ~400 | 2 | 4 basic strategies |
| `model/strategies/subspace.py` | ~800 | 3 | 9 subspace strategies |
| `model/strategies/weighted.py` | ~300 | 4 | 4 weighted strategies |
| `model/strategies/evolutionary.py` | ~150 | 4 | 2 evolutionary strategies |
| `model/strategies/unlearning.py` | ~120 | 4 | 2 unlearning strategies |
| `model/strategies/calibration.py` | ~100 | 4 | 2 calibration strategies |
| `model/strategies/safety.py` | ~100 | 4 | 2 safety strategies |
| `model/lora.py` | ~250 | 5 | LoRA adapter merging |
| `model/pipeline.py` | ~200 | 5 | Multi-stage pipelines |
| `model/provenance.py` | ~200 | 5 | Per-parameter provenance |
| `model/heatmap.py` | ~150 | 5 | Conflict heatmaps |
| `model/safety.py` | ~100 | 6 | Safety layer detection |
| `model/continual.py` | ~150 | 6 | Continual merge |
| `model/federated.py` | ~150 | 6 | Federated bridge |
| `model/formats.py` | ~150 | 6 | MergeKit/FusionBench compat |
| `model/gpu.py` | ~150 | 6 | GPU acceleration |
| **Total** | **~3,870** | — | — |

Plus ~700 new tests across corresponding test files.

---

## Non-Functional Requirements

- **Zero-dependency core preserved** — `pip install crdt-merge` must continue to work without numpy/torch
- **Lazy imports everywhere** — numpy/torch imported only when model features are used
- **BSL-1.1 headers** on all new files (SPDX: `BUSL-1.1`)
- **Type hints** on all public APIs
- **Docstrings** with academic citations for every strategy
- **Error messages** that guide users to install missing deps (`pip install crdt-merge[model]`)

---

*Generated from roadmap v2.0 — "The Intelligence Release"*
*Copyright 2026 Ryan Gillespie — BSL-1.1*
