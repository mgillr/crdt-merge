# ModelCRDT Gap Analysis: Model Merging Explosion vs. Current Roadmap

**Date:** 2026-03-28
**Author:** Nexus Engine Strategic Analysis
**Classification:** CRITICAL — The model merging space has grown 10× since our roadmap was written

---

## Executive Summary

The model merging field has **exploded** in 2025-2026:
- **200+ papers** cataloged in Awesome-Model-Merging (700 ⭐, updated 2 days ago)
- **ACM Computing Surveys** published comprehensive 41-page survey (2026)
- **ICLR 2026** has 8+ model merging papers accepted
- **NeurIPS 2025** ran a dedicated **LLM Merging Competition**
- **MergeKit** (Arcee AI): **6,919 ⭐**, 681 forks, LGPL-3.0, actively maintained
- **FusionBench** (JMLR 2025): Standardized benchmark for model fusion
- **Mergenetic**: New evolutionary merging library

Our current ModelCRDT roadmap (v0.8.0) plans **~700 lines** with **5 strategies** (TIES, DARE, SLERP, Task Arithmetic, Fisher). This is **dangerously undersized** for the opportunity. We need to expand significantly while maintaining our unique CRDT advantage.

---

## The Competitive Landscape (March 2026)

### MergeKit — The 800-Pound Gorilla

| Metric | Value |
|--------|-------|
| Stars | **6,919** |
| Forks | 681 |
| License | LGPL-3.0 |
| Language | Python |
| Last push | 2026-03-15 |
| Open issues | **260** (overwhelmed) |
| Backed by | Arcee AI (funded startup) |

**What MergeKit does:**
- ✅ TIES, DARE, SLERP, Task Arithmetic, Fisher-weighted averaging
- ✅ Multi-stage merge workflows (YAML config)
- ✅ Evolutionary merge (CMA-ES optimization)
- ✅ Tokenizer merge
- ✅ MoE upcycling (sparse MoE from dense models)
- ✅ PyTorch raw model merging
- ✅ Safetensors I/O
- ✅ GPU-accelerated for large models

**What MergeKit DOESN'T do (our advantage):**
- ❌ **No CRDT guarantees** — No formal commutativity/associativity proofs
- ❌ **No per-layer strategy DSL** — Their YAML allows per-slice config but it's verbose, not algebraic
- ❌ **No provenance tracking** — Can't trace which source model contributed what
- ❌ **No conflict visualization** — No way to see where models disagree
- ❌ **No verified merge** — No `@verified_merge` equivalent
- ❌ **No reversible merging** — Can't unmerge/unlearn
- ❌ **No structured data merge** — Only neural network weights
- ❌ **260 open issues** — Struggling with maintenance

### Other Competitors

| Tool | Focus | Stars | Status |
|------|-------|-------|--------|
| **Mergenetic** | Evolutionary LLM merging | ~200 | New (2025) |
| **FusionBench** | Model fusion benchmark | ~500 | Active (JMLR 2025) |
| **MoCo** | Model collaboration platform | New | Research (2026) |

### Key Academic Papers (2025-2026)

| Paper | Venue | Relevance |
|-------|-------|-----------|
| Yang et al. "Model Merging in LLMs, MLLMs, and Beyond" | ACM Computing Surveys 2026 | **THE** comprehensive survey (41 pages) |
| M2N2 (Sakana AI) | ACM GECCO 2025 | Evolutionary model merging |
| "Towards Reversible Model Merging" | ArXiv 2025 | **Validates our UnmergeEngine concept** |
| NegMerge | ICML 2025 | Weight negation for machine unlearning |
| FusionBench | JMLR 2025 | Standardized benchmark |
| SSAM | ArXiv 2026 | Multimodal model merging |
| MergOPT | ICLR 2026 | Merge-aware optimizer |
| DC-Merge | CVPR 2026 | Directional consistency merging |
| AdaRank | ICLR 2026 | Adaptive rank pruning for merging |

---

## Current Roadmap: What We Have

### ModelCRDT (v0.8.0) — Current Plan

```
Module: crdt_merge.model_crdt (~700 lines)
Strategies: 5 (TIES, DARE, SLERP, Task Arithmetic, Fisher)
Tests: ~50
Dependencies: safetensors, torch (lazy)
```

**Planned capabilities:**
1. ✅ `ModelCRDT.from_safetensors()` — Load models
2. ✅ `ModelCRDT.merge()` — Merge with strategy
3. ✅ `MergeSchema` for per-layer strategies
4. ✅ CRDT commutativity/associativity guarantees
5. ✅ Integration with `verify_crdt()`

---

## CRITICAL GAPS: What's Missing

### Gap Category 1: Missing Core Strategies

The field has grown far beyond TIES/DARE/SLERP. Our 5 strategies cover the **2023 baseline**. The 2025-2026 frontier has 20+ methods:

| Strategy | Year | Category | Status in Roadmap | Priority |
|----------|------|----------|-------------------|----------|
| TIES-Merging | 2023 | Subspace | ✅ Planned | — |
| DARE | 2024 | Subspace | ✅ Planned | — |
| SLERP | 1985/2024 | Basic | ✅ Planned | — |
| Task Arithmetic | 2023 | Basic | ✅ Planned | — |
| Fisher-weighted | 2022 | Weighted | ✅ Planned | — |
| **DELLA** | 2024 | Subspace | ❌ **MISSING** | 🔴 HIGH |
| **RegMean** | 2023 | Weighted | ❌ **MISSING** | 🟡 MEDIUM |
| **AdaMerging** | 2024 | Weighted | ❌ **MISSING** | 🟡 MEDIUM |
| **DARE-TIES** | 2024 | Hybrid | ❌ **MISSING** | 🔴 HIGH |
| **Model Breadcrumbs** | 2023 | Subspace | ❌ **MISSING** | 🟡 MEDIUM |
| **EMR-Merging** | 2024 | Subspace | ❌ **MISSING** | 🟡 MEDIUM |
| **DAM** (Differentiable Adaptive) | 2024 | Weighted | ❌ **MISSING** | 🟡 MEDIUM |
| **SVD Knot-Tying** | 2024 | Subspace | ❌ **MISSING** | 🟡 MEDIUM |
| **Weight Scope Alignment** | 2024 | Post-calibration | ❌ **MISSING** | 🟡 MEDIUM |
| **Representation Surgery** | 2024 | Post-calibration | ❌ **MISSING** | 🟡 MEDIUM |
| **STAR** (Spectral Truncation) | 2025 | Subspace | ❌ **MISSING** | 🟡 MEDIUM |
| **NegMerge** | 2024 | Unlearning | ❌ **MISSING** | 🔴 HIGH (connects to UnmergeEngine) |
| **AdaRank** | 2026 | Subspace | ❌ **MISSING** | 🟢 LOW (cutting-edge) |

**Recommendation:** Expand from 5 → **12-15 strategies** at launch, with plugin architecture for community additions.

### Gap Category 2: Missing Modalities

| Modality | Papers (2025-2026) | Status | Priority |
|----------|-------------------|--------|----------|
| LLM full-model merging | 100+ | ✅ Planned (safetensors) | — |
| **LoRA/Adapter merging** | 40+ | ❌ **CRITICAL MISSING** | 🔴🔴 CRITICAL |
| **Multimodal (VL) merging** | 15+ | ❌ **MISSING** | 🔴 HIGH |
| **MoE expert merging** | 12+ | ❌ **MISSING** | 🟡 MEDIUM |
| **Diffusion model merging** | 10+ | ❌ **MISSING** | 🟡 MEDIUM |
| GNN merging | 3+ | ❌ Missing | 🟢 LOW |

**🔴🔴 CRITICAL: LoRA merging is the #1 use case.** Most practitioners are merging LoRA adapters, not full 7B models. Missing this is like shipping a car without wheels. Need:

```python
# This MUST be in v0.8.0
from crdt_merge.model_crdt import ModelCRDT

base = ModelCRDT.from_safetensors("base-llama-8b/")
lora_a = ModelCRDT.from_lora("medical-lora/")     # ← NEW
lora_b = ModelCRDT.from_lora("legal-lora/")        # ← NEW

# LoRA-specific strategies
merged = ModelCRDT.merge_loras(
    base, lora_a, lora_b,
    strategy=LoRAMerge(method="cat", rank_reduction="svd")  # ← NEW
)
```

### Gap Category 3: Missing Capabilities

| Capability | MergeKit Has? | Roadmap Has? | Priority |
|------------|---------------|--------------|----------|
| Evolutionary merge (CMA-ES) | ✅ Yes | ❌ **MISSING** | 🔴 HIGH |
| Multi-stage merge pipeline | ✅ Yes (YAML) | ❌ **MISSING** | 🔴 HIGH |
| Tokenizer merging | ✅ Yes | ❌ **MISSING** | 🟡 MEDIUM |
| MoE upcycling | ✅ Yes | ❌ **MISSING** | 🟡 MEDIUM |
| GPU acceleration | ✅ Yes | ❌ **MISSING** | 🔴 HIGH |
| Model weight provenance | ❌ No | ❌ **MISSING** | 🔴🔴 CRITICAL (unique) |
| Conflict heatmap/viz | ❌ No | ❌ **MISSING** | 🔴 HIGH (unique) |
| Reversible merge | ❌ No | Partial (UnmergeEngine v0.9) | 🔴 HIGH (unique) |
| CRDT verification | ❌ No | ✅ Planned | — |
| Per-layer DSL | Partial (YAML) | ✅ Planned (MergeSchema) | — |
| MergeKit config import | ❌ N/A | ❌ **MISSING** | 🟡 MEDIUM |
| FusionBench compat | ❌ N/A | ❌ **MISSING** | 🟡 MEDIUM |

### Gap Category 4: Missing Research Integrations

| Research Direction | Papers | Status | Notes |
|-------------------|--------|--------|-------|
| Safety-preserving merging | SafeMERGE, LED-Merging | ❌ MISSING | Enterprise-critical |
| Continual/sequential merging | 10+ papers 2025 | ❌ MISSING | Real-world use case |
| Cross-architecture merging | Transport and Merge (2026) | ❌ MISSING | Novel capability |
| Knowledge unlearning via merge | NegMerge, Split-Unlearn-Merge | ❌ MISSING | Connects to UnmergeEngine |
| Merge-aware training | MergOPT (ICLR 2026) | ❌ MISSING | Pre-merging optimization |
| Scaling laws for merging | ArXiv 2025 | ❌ MISSING | Theoretical foundation |

---

## THE CRDT-MERGE UNIQUE ADVANTAGE: What Nobody Else Has

This is the critical insight: **MergeKit is a tool. crdt-merge ModelCRDT would be a formal framework.**

### 1. CRDT Guarantees for Model Merging (Unique)

Nobody in the model merging world has formal convergence guarantees:

```python
# crdt-merge provides what MergeKit can't:
from crdt_merge.model_crdt import verify_merge_crdt

# Prove your merge is order-independent
proof = verify_merge_crdt(
    strategy=TIESMerge(density=0.5),
    models=[model_a, model_b, model_c]
)
assert proof.commutative  # ✅ Merge order doesn't matter
assert proof.associative   # ✅ Grouping doesn't matter
assert proof.idempotent    # ✅ Double-merge is safe
```

**Why this matters:** In federated learning, devices merge asynchronously. CRDT guarantees mean you don't need a coordinator.

### 2. Per-Layer Strategy DSL with MergeSchema (Unique)

MergeKit uses verbose YAML. We use elegant Python:

```python
# MergeKit way (YAML, per-model weights):
# slices:
#   - sources:
#       - model: base
#         layer_range: [0, 16]
#       - model: finetune-a
#         layer_range: [0, 16]
#     merge_method: ties
#     parameters:
#       density: 0.5

# crdt-merge way (Python, per-layer strategy):
schema = MergeSchema(
    default=TIESMerge(density=0.5),
    embedding=TaskArithmetic(scaling=0.3),     # Light touch on embeddings
    attention=SLERPMerge(t=0.6),               # Smooth blend for attention
    ffn=DAREMerge(density=0.7, rescale=True),  # Aggressive for FFN
    lm_head=FisherMerge()                      # Fisher-weighted for output
)
```

### 3. Model Weight Provenance (Novel — Nobody Has This)

```python
merged, provenance = ModelCRDT.merge_with_provenance(
    base, finetune_medical, finetune_legal,
    strategy=TIESMerge(density=0.5)
)

# Per-parameter provenance tracking
provenance.contribution_map("layer.0.attention.q_proj.weight")
# → {"medical": 0.62, "legal": 0.38, "base": 0.0}

# Which model dominated each layer?
provenance.layer_dominance()
# → {0: "medical", 1: "legal", 2: "medical", ...}
```

**Why this matters:** For auditing, compliance, and understanding what your merged model actually learned.

### 4. Conflict Visualization for Weight Merging (Novel)

```python
from crdt_merge.model_crdt import ConflictMap

conflicts = ConflictMap.analyze(
    base, finetune_a, finetune_b,
    strategy=TIESMerge(density=0.5)
)

# Where do models disagree most?
conflicts.heatmap()  # Per-layer conflict intensity
conflicts.top_conflicts(k=10)  # Most conflicted parameters
conflicts.sign_disagreements()  # Where TIES had to vote
```

### 5. UnmergeEngine for Models (Novel — v0.9.0 synergy)

```python
# Reversible model merging — connects to UnmergeEngine
from crdt_merge.model_crdt import ReversibleMerge

merged, receipt = ReversibleMerge.merge(
    base, finetune_a, finetune_b,
    strategy=TIESMerge(density=0.5)
)

# Later: unmerge a model (GDPR "right to be forgotten" for training data)
unmerged = ReversibleMerge.unmerge(merged, receipt, remove=finetune_a)
```

**Why this matters:** "Towards Reversible Model Merging For Low-rank Weights" (2025) proves this is possible. crdt-merge can be the first library to ship it.

---

## RECOMMENDED ROADMAP CHANGES

### Option A: Expand ModelCRDT (Recommended)

Increase v0.8.0 ModelCRDT from ~700 lines to ~2,000 lines:

| Component | Lines | Strategies/Features |
|-----------|-------|-------------------|
| **Core framework** | ~400 | ModelCRDT class, loading, saving, lazy torch |
| **Basic strategies** | ~200 | Weight Average, SLERP, Task Arithmetic |
| **Subspace strategies** | ~400 | TIES, DARE, DELLA, DARE-TIES, NegMerge |
| **Weighted strategies** | ~200 | Fisher, RegMean, AdaMerging |
| **LoRA merging** | ~300 | LoRA loading, composition, rank reduction |
| **Provenance** | ~200 | Per-parameter tracking, contribution maps |
| **Conflict analysis** | ~150 | Conflict maps, sign disagreements, heatmap data |
| **CRDT verification** | ~100 | Commutativity, associativity, idempotency proofs |
| **Plugin architecture** | ~100 | Register custom strategies |
| **Total** | **~2,050** | **15+ strategies** |

### Option B: Split ModelCRDT into Two Releases

**v0.8.0 (Core ModelCRDT):**
- 12 strategies (TIES, DARE, SLERP, TA, Fisher, DELLA, DARE-TIES, NegMerge, RegMean, AdaMerge, Weight Average, SVD)
- LoRA merging support
- Per-layer MergeSchema
- CRDT verification
- ~1,200 lines, ~80 tests

**v0.8.5 (Advanced ModelCRDT):**
- Evolutionary merging (CMA-ES)
- Multi-stage merge pipelines
- Provenance tracking
- Conflict visualization
- Cross-architecture merging
- MergeKit config import/export
- FusionBench compatibility
- ~800 lines, ~60 tests

### Option C: Accelerate to v0.7.0

Given the explosion, consider moving ModelCRDT from v0.8.0 to v0.7.0 (swapping with or parallelizing MergeQL).

---

## Strategy: WHAT MAKES US WIN vs. MergeKit

| Their Advantage | Our Counter |
|----------------|-------------|
| 6,919 stars | We don't compete on stars — we compete on **guarantees** |
| Established ecosystem | We offer what they fundamentally can't: CRDT algebra |
| GPU acceleration | We start CPU-first (most LoRA merges are small), add GPU later |
| 260 open issues | Our code quality is higher (425 tests, zero failures) |
| YAML config | Our Python DSL is more expressive AND more composable |
| LGPL-3.0 license | Our Apache-2.0 is more enterprise-friendly |

| Our Unique Advantage | Why It Wins |
|---------------------|-------------|
| **CRDT guarantees** | Federated learning needs order-independent merging |
| **Provenance tracking** | Auditing and compliance — enterprises need this |
| **Conflict visualization** | Researchers need to understand their merges |
| **Reversible merging** | GDPR compliance, safety alignment preservation |
| **Verified merge** | "Prove your merge is safe" — regulatory requirement |
| **Per-layer MergeSchema** | More elegant than YAML, composable, testable |
| **Structured data + model merging** | Only library that bridges both worlds |

### The Positioning Statement

> **MergeKit is a tool for merging LLMs. crdt-merge is a formal framework for conflict-free merging of anything — datasets, models, and beyond. When you need guarantees, not just results, you need crdt-merge.**

---

## Specific Integration Opportunities

### 1. Federated Learning Bridge

Model merging in federated learning (FedAvg, FedProx, FedRAM) is mathematically equivalent to CRDT merge operations. crdt-merge can be the bridge:

```python
# Federated learning aggregation as CRDT merge
from crdt_merge.model_crdt import FederatedMerge

global_model = FederatedMerge.aggregate(
    local_models=[client_1, client_2, client_3],
    strategy=FedAvg(),  # or FedProx, FedRAM
    weights=[0.3, 0.3, 0.4]  # proportional to data size
)

# CRDT guarantee: any order of aggregation gives same result
```

### 2. Continual Merging

Real-world model updates happen continuously:

```python
from crdt_merge.model_crdt import ContinualMerge

merger = ContinualMerge(base_model)
merger.absorb(weekly_finetune_1, strategy=TIESMerge())
merger.absorb(weekly_finetune_2, strategy=TIESMerge())
# Anti-forgetting built in via CRDT semantics
```

### 3. Safety-Preserving Merge

```python
from crdt_merge.model_crdt import SafeMerge

merged = SafeMerge.merge(
    base_safe_model,
    finetune_a,
    safety_layers="freeze",  # Don't merge safety-critical layers
    verify_alignment=True     # Run safety checks post-merge
)
```

---

## Impact on Other Language Repos

### Rust Protocol Engine (crdt-merge-rs)

The Rust protocol engine needs to understand ModelCRDT wire format:
- Model weight deltas as protocol messages
- Efficient tensor diff encoding
- CRDT verification in Rust (fast)

### TypeScript (crdt-merge-ts)

Web-based model merging visualization:
- Conflict heatmaps in the browser
- Provenance explorer
- MergeSchema builder UI

### Java (crdt-merge-java)

Enterprise integrations:
- Spring Boot model merge service
- Kafka-based federated merge pipeline

---

## Revised Timeline Estimate

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Core ModelCRDT** | 3 weeks | 12 strategies, LoRA, MergeSchema, verification |
| **Provenance + Conflicts** | 2 weeks | Per-parameter tracking, conflict maps |
| **Evolutionary + Pipeline** | 2 weeks | CMA-ES, multi-stage merges |
| **Reversible Merge** | 1 week | UnmergeEngine bridge (basic) |
| **Testing + Docs** | 2 weeks | 120+ tests, API docs, tutorials |
| **Total** | **10 weeks** | vs. original 4 weeks |

---

## Conclusion

**The model merging explosion validates our vision but demands we expand scope significantly.**

Our current plan (5 strategies, ~700 lines) would land as a "nice toy" in a space dominated by MergeKit (6,919 ⭐). To be a **leader and innovator**, we need:

1. ✅ **15+ strategies** (not 5) — Cover the 2023-2026 frontier
2. ✅ **LoRA merging** — The #1 use case, cannot be missing
3. ✅ **Provenance tracking** — Our unique advantage, nobody else has it
4. ✅ **Conflict visualization** — Show what your merge actually did
5. ✅ **CRDT verification** — "Prove your merge is safe"
6. ✅ **Reversible merging** — Connects to UnmergeEngine, enables GDPR compliance
7. ✅ **Plugin architecture** — Community can add strategies without forking

**We don't need to beat MergeKit at being a merge tool. We need to make model merging a CRDT operation with formal guarantees. That's the category nobody occupies.**
