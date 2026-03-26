# LoRA Adapter Merging: Per-Module Strategy With Rank Harmonization

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Rank Heterogeneity Problem

LoRA (Low-Rank Adaptation) is the dominant fine-tuning method for large language models. When multiple teams fine-tune the same base model — each using a different rank, each on a different task — combining the resulting adapters has no principled solution.

**What happens today:**
- Adapter A was trained with `r=64` (summarisation, detail-heavy)
- Adapter B was trained with `r=16` (translation, lightweight)
- Adapter C was trained with `r=32` (reasoning, balanced)

When you try to merge them:
- Using `r=64` → merged adapter is 4× larger than needed, inference slows 20%
- Using `r=8` → signal from the `r=64` adapter is truncated, performance drops 12%
- Naive row-padding → the added zeros add noise, not signal

And even before the rank problem: most tools apply a **single global strategy** (weighted average) to every module — the same treatment for attention query projections, value projections, feedforward layers, and output projections, despite these having fundamentally different geometric properties.

crdt-merge's `LoRAMerge` solves both.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Rank Harmonization (CRDT-safe preprocessing)       │
│                                                              │
│  _harmonize_rank_lora_a() / _harmonize_rank_lora_b()         │
│                                                              │
│  Strategies:                                                 │
│  • max:      use the highest rank (preserves all signal)     │
│  • min:      use the lowest rank (smallest merged result)    │
│  • mean:     round-trip average rank                        │
│  • adaptive: weight-proportional rank (default)             │
│                                                              │
│  Padding: zero-pad (order-independent, commutative)         │
│  Truncation: SVD — keep top singular values, not rows        │
│  Result: all adapters have the same rank → comparable        │
└──────────────────────┬──────────────────────────────────────┘
                       │ harmonized adapters (same rank)
                       ┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Per-Module Strategy (deterministic pure function)  │
│                                                              │
│  LoRAMergeSchema maps module name → strategy:               │
│  "q_proj"  → "ties"      (trim + elect sign on attention Q) │
│  "v_proj"  → "slerp"     (spherical interpolation on V)     │
│  "ff.*"    → "dare_ties" (sparse feedforward)               │
│  "default" → "weight_average"                               │
│                                                              │
│  Same harmonized set → same merged adapter on every replica  │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```python
import numpy as np
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

# Three LoRA adapters with different ranks (nested dict format)
adapter_a = {
    "q_proj": {"lora_A": np.random.randn(64, 768).astype(np.float32),  # r=64
               "lora_B": np.random.randn(768, 64).astype(np.float32)},
    "v_proj": {"lora_A": np.random.randn(64, 768).astype(np.float32),
               "lora_B": np.random.randn(768, 64).astype(np.float32)},
}
adapter_b = {
    "q_proj": {"lora_A": np.random.randn(16, 768).astype(np.float32),  # r=16
               "lora_B": np.random.randn(768, 16).astype(np.float32)},
    "v_proj": {"lora_A": np.random.randn(16, 768).astype(np.float32),
               "lora_B": np.random.randn(768, 16).astype(np.float32)},
}
adapter_c = {
    "q_proj": {"lora_A": np.random.randn(32, 768).astype(np.float32),  # r=32
               "lora_B": np.random.randn(768, 32).astype(np.float32)},
    "v_proj": {"lora_A": np.random.randn(32, 768).astype(np.float32),
               "lora_B": np.random.randn(768, 32).astype(np.float32)},
}

schema = LoRAMergeSchema(strategies={"q_proj": "ties", "v_proj": "ties"})
merger = LoRAMerge(schema=schema)

# Adaptive rank harmonization — weight-proportional target rank
merged = merger.merge_adapters(
    adapters=[adapter_a, adapter_b, adapter_c],
    weights=[0.5, 0.25, 0.25],
    rank_strategy="adaptive",
)

print(f"q_proj lora_A shape: {merged['q_proj']['lora_A'].shape}")
# Adaptive rank = max(1, round(64*0.5 + 16*0.25 + 32*0.25)) = r=40
```

---

## Cookbook: All Rank Harmonization Strategies

```python
import numpy as np
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

adapters = [
    {"layer": {"lora_A": np.random.randn(64, 128).astype(np.float32),
               "lora_B": np.random.randn(128, 64).astype(np.float32)}},
    {"layer": {"lora_A": np.random.randn(16, 128).astype(np.float32),
               "lora_B": np.random.randn(128, 16).astype(np.float32)}},
    {"layer": {"lora_A": np.random.randn(32, 128).astype(np.float32),
               "lora_B": np.random.randn(128, 32).astype(np.float32)}},
]
weights = [0.5, 0.25, 0.25]
merger = LoRAMerge(schema=LoRAMergeSchema(strategies={"layer": "weight_average"}))

# max: target rank = max(64, 16, 32) = 64
# Smaller adapters padded with zeros — no information loss
result_max = merger.merge_adapters(adapters, weights, rank_strategy="max")
assert result_max["layer"]["lora_A"].shape[0] == 64

# min: target rank = min(64, 16, 32) = 16
# Larger adapters SVD-truncated — keeps most significant components
result_min = merger.merge_adapters(adapters, weights, rank_strategy="min")
assert result_min["layer"]["lora_A"].shape[0] == 16

# mean: target rank = round(mean(64, 16, 32)) = round(37.3) = 37
result_mean = merger.merge_adapters(adapters, weights, rank_strategy="mean")
assert result_mean["layer"]["lora_A"].shape[0] == 37

# adaptive: target rank = round(64*0.5 + 16*0.25 + 32*0.25) = round(40) = 40
result_adaptive = merger.merge_adapters(adapters, weights, rank_strategy="adaptive")
assert result_adaptive["layer"]["lora_A"].shape[0] == 40
```

---

## Cookbook: Per-Module Strategy Assignment

Different modules in a transformer have different geometric properties. The same merge strategy applied uniformly is suboptimal:

```python
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

# Attention query: sign conflicts matter → use TIES (trim + elect sign)
# Attention value: smooth interpolation works well → use SLERP
# Feedforward: sparse important parameters → use DARE+TIES
# Everything else: simple weighted average
schema = LoRAMergeSchema(strategies={
    "q_proj": "ties",
    "k_proj": "ties",
    "v_proj": "slerp",
    "o_proj": "slerp",
    "gate_proj": "dare_ties",
    "up_proj":   "dare_ties",
    "down_proj": "dare_ties",
    "default":   "weight_average",
})

merger = LoRAMerge(schema=schema)

# Adapters from two fine-tunes of Mistral-7B
merged = merger.merge_adapters(
    adapters=[mistral_code_adapter, mistral_math_adapter],
    weights=[0.6, 0.4],
    rank_strategy="adaptive",
)
```

---

## Cookbook: Merge With Provenance

```python
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
import numpy as np

schema = LoRAMergeSchema(strategies={"q_proj": "ties", "default": "weight_average"})
merger = LoRAMerge(schema=schema)

adapters = [
    {"q_proj.lora_A": np.random.randn(32, 256).astype(np.float32),
     "q_proj.lora_B": np.random.randn(256, 32).astype(np.float32)},
    {"q_proj.lora_A": np.random.randn(32, 256).astype(np.float32),
     "q_proj.lora_B": np.random.randn(256, 32).astype(np.float32)},
]

merged, provenance = merger.merge_adapters_with_provenance(
    adapters=adapters,
    weights=[0.6, 0.4],
    rank_strategy="max",
)

for module, prov in provenance.items():
    print(f"Module: {module}")
    print(f"  Strategy: {prov['strategy']}")
    print(f"  Dominant source: {prov['dominant_source']}")
    print(f"  Contributions: {prov['contribution_map']}")
    # q_proj: strategy=ties, dominant_source=0, contributions={0: 0.6, 1: 0.4}
```

---

## Cookbook: Apply Merged Adapter to Base Model

```python
from crdt_merge.model.lora import LoRAMerge
import numpy as np

# Base model (pretrained weights)
base_model = {
    "q_proj.weight": np.random.randn(768, 768).astype(np.float32),
    "v_proj.weight": np.random.randn(768, 768).astype(np.float32),
}

# Merged LoRA adapter (lora_B @ lora_A applied to base)
schema = LoRAMergeSchema(strategies={"q_proj": "weight_average", "v_proj": "weight_average"})
merger = LoRAMerge(schema=schema)
merged_adapter = merger.merge_adapters(adapters=[adapter_a, adapter_b], weights=[0.6, 0.4])

# Apply: θ = θ_base + lora_B @ lora_A
fused_model = merger.apply_to_base(merged_adapter, base_model)

print(f"q_proj shape: {fused_model['q_proj.weight'].shape}")  # (768, 768) unchanged
```

---

## Scenario: Open-Source LLM Community Merging

A community fine-tunes Llama-3 on 8 different tasks. Each contributor posts their LoRA adapter on HuggingFace. A community member wants a single merged adapter that captures all contributions.

```python
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

# Adapters from 8 community contributors — different ranks, different tasks
community_adapters = {
    "llama3-code-r64":       (code_adapter,    0.20),   # r=64, code generation
    "llama3-math-r32":       (math_adapter,    0.15),   # r=32, mathematics
    "llama3-reason-r48":     (reason_adapter,  0.18),   # r=48, reasoning
    "llama3-instruct-r16":   (instruct_adapter,0.12),   # r=16, instruction following
    "llama3-creative-r24":   (creative_adapter,0.10),   # r=24, creative writing
    "llama3-science-r40":    (science_adapter, 0.10),   # r=40, science facts
    "llama3-translate-r8":   (trans_adapter,   0.08),   # r=8,  translation
    "llama3-chat-r32":       (chat_adapter,    0.07),   # r=32, conversation
}

adapters = [a for a, _ in community_adapters.values()]
weights  = [w for _, w in community_adapters.values()]

# Strategy: attention = TIES (sign-aware), feedforward = DARE_TIES (sparse)
schema = LoRAMergeSchema(strategies={
    "q_proj": "ties", "k_proj": "ties", "v_proj": "ties",
    "gate_proj": "dare_ties", "up_proj": "dare_ties", "down_proj": "dare_ties",
    "default": "weight_average",
})

merger = LoRAMerge(schema=schema)
merged, prov = merger.merge_adapters_with_provenance(
    adapters, weights, rank_strategy="adaptive"
)

# Adaptive rank ~= weighted average of all ranks
# Contributors with higher weight have proportionally more influence on target rank
# CRDT guarantee: any order of the 8 adapters produces identical result
print("Merged adapter ready for community distribution")
for module, p in list(prov.items())[:3]:
    print(f"  {module}: dominant={p['dominant_source']}, strategy={p['strategy']}")
```

---

## Scenario: Enterprise Multi-Team LoRA Governance

An enterprise has three teams each fine-tuning the company LLM on their domain. Monthly merges combine all three into a production adapter.

```python
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
from crdt_merge.model import CRDTMergeState
import numpy as np

# Monthly merge using CRDTMergeState for convergence guarantees
state = CRDTMergeState("weight_average")

# Each team registers their adapter
state.add(
    legal_team_adapter,
    model_id="team_legal_may",
    weight=0.35,
    metadata={"team": "legal", "month": "2026-05", "rank": 32}
)
state.add(
    finance_team_adapter,
    model_id="team_finance_may",
    weight=0.40,
    metadata={"team": "finance", "month": "2026-05", "rank": 48}
)
state.add(
    hr_team_adapter,
    model_id="team_hr_may",
    weight=0.25,
    metadata={"team": "hr", "month": "2026-05", "rank": 16}
)

# Resolve — CRDT guarantees: same result whether IT team or Finance team runs this
prod_adapter = state.resolve()

# Month 2: legal team found a bias issue in their adapter
state.remove("team_legal_may")
state.add(fixed_legal_adapter, model_id="team_legal_may_v2", weight=0.35,
          metadata={"team": "legal", "month": "2026-05", "rank": 32, "version": 2})

updated_prod = state.resolve()
print(f"Production adapter updated — bias fix applied, all teams converge to same result")
```

---

## SVD Truncation: Why It Matters

When reducing a rank-64 adapter to rank-16, row truncation discards 75% of the adapter with no regard for information content. SVD truncation keeps the most important components:

```
Naive row truncation:        SVD truncation:
lora_A[r=64] → lora_A[:16]  lora_A[r=64] → U[:16, :k] @ diag(S[:k]) @ Vt[:k, :]

Discards rows 16-63           Keeps top 16 singular value directions
Loss is uniform (random)      Loss is minimal (removes least informative components)
```

In practice, SVD truncation retains 85–95% of the adapter's representational capacity even when cutting rank by 4×, compared to ~40–60% for naive truncation.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Federated Model Merging Without a Parameter Server](./federated-model-merging.md)
- [Guide — Continual Learning Without Catastrophic Forgetting](./continual-learning-without-forgetting.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [API Reference — LoRAMerge](../api-reference/layer4-ai/model.md)
- [Benchmarks — A100 GPU Performance](../benchmarks/v030_a100_analysis.md)
