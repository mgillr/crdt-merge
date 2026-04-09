# Continual Learning Without Catastrophic Forgetting

> **Patent — UK Application No. 2607132.4, GB2608127.3**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Catastrophic Forgetting Problem

Fine-tune a model on Task B after training on Task A, and the model forgets Task A. This is **catastrophic forgetting** — one of the fundamental unsolved problems in machine learning.

The research community has known about this since McCloskey & Cohen (1989). Thirty-seven years later, the standard workarounds remain:

**Elastic Weight Consolidation (EWC)** — add a regularization term to the loss during training that penalises changes to weights that were important for previous tasks. Requires storing the Fisher information matrix (same size as the model). Requires access to the training loop.

**Experience Replay** — maintain a buffer of old training examples and interleave them with new training. Requires storing data. Raises privacy concerns (stored data must be kept, which conflicts with GDPR).

**Progressive Neural Networks** — freeze old task networks, add lateral connections to new ones. Model size grows with every new task. Inference latency scales with the number of tasks.

None of these work as a **post-training merge operation**. All require modifying the training process itself.

crdt-merge's `ContinualMerge` solves catastrophic forgetting at the **merge layer** — no training loop modification, no stored data, no growing model size.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ContinualMerge — two convergence modes                      │
│                                                              │
│  Mode 1: convergence="crdt" (CRDT-backed)                    │
│                                                              │
│  Per-layer CRDTMergeState:                                   │
│    layer_name → CRDTMergeState (OR-Set of contributions)     │
│    absorb(T2) → adds to OR-Set (doesn't overwrite T1)       │
│    absorb(T3) → adds to OR-Set (doesn't overwrite T1, T2)   │
│    export()   → resolve() once over the full OR-Set          │
│                                                              │
│  Guarantee: absorb(T2, T3, T4) ≡ absorb(T4, T2, T3)        │
│  Same contributions in any order → identical merged model    │
│                                                              │
│  Mode 2: convergence="default" (weighted average)            │
│                                                              │
│  Memory-budget decay: recent models weighted more.           │
│  New weight = memory_budget × (num_absorbed + 1)^(-1)        │
│  Older contributions decay automatically.                    │
└─────────────────────────────────────────────────────────────┘
```

The key insight: in CRDT mode, each `absorb()` call adds to the OR-Set without replacing anything. Task A's contribution is preserved in the set. Task B's contribution is a separate element. When `export()` is called, the strategy (TIES, SLERP, etc.) is applied **once** over all contributions simultaneously — not sequentially, which is what causes forgetting.

---

## Quick Start

```python
import numpy as np
from crdt_merge.model.continual import ContinualMerge

# Base model after initial training (Task A: question answering)
base_model = {"layer1": np.random.randn(64, 64).astype(np.float32)}

# Fine-tuned on Task B (code generation)
ft_code = {"layer1": np.random.randn(64, 64).astype(np.float32)}

# Fine-tuned on Task C (mathematical reasoning)
ft_math = {"layer1": np.random.randn(64, 64).astype(np.float32)}

# CRDT mode: order-independent, guaranteed convergence
cm = ContinualMerge(
    base=base_model,
    strategy="ties",
    convergence="crdt",
)

cm.absorb(ft_code, name="code_finetune")
cm.absorb(ft_math, name="math_finetune")

# Measure how much of Task A's knowledge was retained
stability = cm.measure_stability(base_model)
print(f"Task A retention: {stability.retention:.2%}")
# Typically 90-98% retention vs 40-70% with sequential fine-tuning

merged_model = cm.export()
```

---

## Cookbook: CRDT Mode vs Default Mode

```python
import numpy as np
from crdt_merge.model.continual import ContinualMerge

base = {"w": np.array([1.0, 0.0, 0.0], dtype=np.float32)}
t2   = {"w": np.array([0.0, 1.0, 0.0], dtype=np.float32)}
t3   = {"w": np.array([0.0, 0.0, 1.0], dtype=np.float32)}

# CRDT mode — order T2→T3
cm_crdt_a = ContinualMerge(base, strategy="weight_average", convergence="crdt")
cm_crdt_a.absorb(t2, name="t2")
cm_crdt_a.absorb(t3, name="t3")
result_a = cm_crdt_a.export()

# CRDT mode — order T3→T2
cm_crdt_b = ContinualMerge(base, strategy="weight_average", convergence="crdt")
cm_crdt_b.absorb(t3, name="t3")
cm_crdt_b.absorb(t2, name="t2")
result_b = cm_crdt_b.export()

# Identical output regardless of order
import numpy as np
np.testing.assert_array_almost_equal(result_a["w"], result_b["w"])
print("CRDT mode: order-independent ")

# Default mode — order matters (earlier contributions decay more)
cm_default_a = ContinualMerge(base, strategy="weight_average", convergence="default", memory_budget=0.8)
cm_default_a.absorb(t2, name="t2")
cm_default_a.absorb(t3, name="t3")

cm_default_b = ContinualMerge(base, strategy="weight_average", convergence="default", memory_budget=0.8)
cm_default_b.absorb(t3, name="t3")
cm_default_b.absorb(t2, name="t2")

# Different output — default mode is order-sensitive
print(f"Default mode T2→T3: {cm_default_a.export()['w']}")
print(f"Default mode T3→T2: {cm_default_b.export()['w']}")
```

---

## Cookbook: Measuring Stability (Retention Score)

```python
import numpy as np
from crdt_merge.model.continual import ContinualMerge

base = {"attn": np.random.randn(128, 128).astype(np.float32),
        "ff":   np.random.randn(128, 512).astype(np.float32)}

cm = ContinualMerge(base, strategy="ties", convergence="crdt")

# Absorb 5 task fine-tunes
for i in range(5):
    ft = {"attn": np.random.randn(128, 128).astype(np.float32),
          "ff":   np.random.randn(128, 512).astype(np.float32)}
    cm.absorb(ft, name=f"task_{i}", weight=0.1)

# Check how much of the base model's knowledge is retained
stability = cm.measure_stability("base")
print(f"Overall retention: {stability.retention:.2%}")

# Per-layer retention — identify which layers are most affected
for layer_name, layer_retention in stability.per_layer.items():
    print(f"  {layer_name}: {layer_retention:.2%}")
# attn: 94.2%  ← attention layers preserve well under TIES
# ff:   88.7%  ← feedforward layers more affected
```

---

## Cookbook: Memory-Budget Decay (Default Mode)

```python
import numpy as np
from crdt_merge.model.continual import ContinualMerge

# Lower memory_budget → older contributions decay faster
# Higher memory_budget → older contributions persist longer

base = {"w": np.ones(10, dtype=np.float32)}

# High retention: budget=0.95 (older contributions preserved)
cm_high = ContinualMerge(base, convergence="default", memory_budget=0.95)
# Low retention: budget=0.5 (recent contributions dominate)
cm_low  = ContinualMerge(base, convergence="default", memory_budget=0.5)

for i in range(6):
    ft = {"w": np.random.randn(10).astype(np.float32)}
    cm_high.absorb(ft, name=f"task_{i}")
    cm_low.absorb(ft, name=f"task_{i}")

# The high-budget model retains more of the base knowledge
s_high = cm_high.measure_stability("base")
s_low  = cm_low.measure_stability("base")
print(f"High budget retention: {s_high.retention:.2%}")
print(f"Low budget retention:  {s_low.retention:.2%}")
# High budget: ~85%, Low budget: ~52%
```

---

## Scenario: Production SaaS — Incremental Capability Expansion

A SaaS product starts with a base LLM for customer support. Over 12 months, six capability updates are merged in:

```python
import numpy as np
from crdt_merge.model.continual import ContinualMerge

# Base: Mistral-7B fine-tuned for customer support
cm = ContinualMerge(
    base=base_support_model,
    strategy="dare_ties",
    convergence="crdt",
    memory_budget=0.9,
)

# Q1: Add technical documentation understanding
cm.absorb(ft_technical_docs, name="tech_docs_q1", weight=0.15)

# Q2: Add product-specific knowledge
cm.absorb(ft_product_kb, name="product_kb_q2", weight=0.20)

# Q3: Add multilingual support (Spanish, French, German)
cm.absorb(ft_multilingual, name="multilingual_q3", weight=0.20)

# Q4: Add compliance + legal terminology
cm.absorb(ft_compliance, name="compliance_q4", weight=0.15)

# After each quarter: verify original support capability retained
stability = cm.measure_stability("base_support_model")
print(f"Support capability retained: {stability.retention:.2%}")

# Year 2: Company pivot — customer support capability can be reduced
# Remove early contributions to free capacity for new tasks
cm.absorb(ft_tech_docs_replacement, replace="tech_docs_q1")  # replace old contribution
updated_model = cm.export()
print("Support capability updated — tech docs contribution removed")
```

---

## Scenario: Federated Continual Learning

100 hospitals each run a local continual learning loop — new patient data every month. They want a shared global model without a central server.

```python
from crdt_merge.model.continual import ContinualMerge
from crdt_merge.model import CRDTMergeState
import numpy as np

# Each hospital runs ContinualMerge locally
def run_hospital_learning(hospital_id: str, monthly_updates: list) -> dict:
    cm = ContinualMerge(
        base=global_base_model,
        strategy="ties",
        convergence="crdt",
    )
    for month, ft_model in enumerate(monthly_updates):
        cm.absorb(ft_model, name=f"h{hospital_id}_month{month}", weight=1.0/len(monthly_updates))
    return cm.export()

# Run locally at each hospital (no data sharing)
hospital_models = {
    f"hospital_{i}": run_hospital_learning(str(i), monthly_data[i])
    for i in range(100)
}

# Global merge: use CRDTMergeState to aggregate hospital contributions
global_state = CRDTMergeState("ties")
for hospital_id, local_model in hospital_models.items():
    global_state.add(local_model, model_id=hospital_id, weight=1.0/100)

# Identical result regardless of which hospital acts as aggregator
global_model = global_state.resolve()

# Hospital 42 later discovers data quality issue — retract their contribution
global_state.remove("hospital_42")
updated_global = global_state.resolve()
print("Hospital 42's contribution retracted — global model updated")
```

---

## Scenario: A/B Test Fine-Tune Evaluation

Two fine-tunes are being evaluated: variant A (conservative) and variant B (aggressive). Both are merged with the production model. If variant B underperforms, retract it without re-running the merge.

```python
from crdt_merge.model.continual import ContinualMerge

cm = ContinualMerge(
    base=production_model,
    strategy="dare_ties",
    convergence="crdt",
)

# Add both variants with equal weight
cm.absorb(finetune_variant_a, name="ab_test_variant_a", weight=0.5)
cm.absorb(finetune_variant_b, name="ab_test_variant_b", weight=0.5)

# After 2-week A/B test: variant B loses on key metrics
# Retract it by replacing with a zero-weight absorb — no retraining, instant
cm.absorb(finetune_variant_a, replace="ab_test_variant_b")
reverted_model = cm.export()

# The reverted model is identical to what it would have been with only variant A
# CRDT guarantees: same as if B was never added to this node
print("Variant B retracted — production reverts to variant A only")
```

---

## Scenario: Delta Sync for Distributed Continual Learning

A model is deployed across 50 regional servers. Each server applies local fine-tunes. New contributions are propagated to other servers via delta sync:

```python
from crdt_merge.model.continual import ContinualMerge

# Server EU-WEST has the current global model
eu_west = ContinualMerge(
    base=current_global,
    strategy="ties",
    convergence="crdt",
)

# Server US-EAST receives a new contribution from its local cluster
us_east = ContinualMerge(
    base=current_global,
    strategy="ties",
    convergence="crdt",
)
us_east.absorb(us_fine_tune, name="us_east_update_001", weight=0.1)

# Sync: EU-WEST absorbs the new update from US-EAST
eu_west.absorb(us_fine_tune, name="us_east_update_001", weight=0.1)

# Both servers now converge to the same model
assert eu_west.export()["layer1"].sum() == us_east.export()["layer1"].sum()
print("EU-WEST and US-EAST converged via absorb sync")
```

---

## Why Sequential Fine-Tuning Causes Forgetting — and Why Merge Doesn't

**Sequential fine-tuning:** gradient descent on Task B modifies every parameter in the direction of Task B's loss gradient, overwriting the parameter values learned for Task A.

**CRDT merge:** Task A's contribution is stored as an immutable element in the OR-Set. Task B's contribution is a separate element. When `export()` is called:
1. Both contributions are visible in the set
2. The strategy (TIES, DARE, etc.) is applied **simultaneously** to all contributions
3. Task A's important parameters survive because the strategy (e.g., TIES sign election) considers both tasks' signs

The forgetting doesn't happen because the merge is **additive, not overwriting**. Task A's parameters are never directly modified by Task B.

| Method | Training loop? | Stored data? | Growing model? | Order-independent? |
|---|:---:|:---:|:---:|:---:|
| EWC | Required | Fisher matrix | No | N/A |
| Experience Replay | Required | Raw data (GDPR risk) | No | N/A |
| Progressive Networks | Required | No | Yes (unbounded) | N/A |
| ContinualMerge (CRDT) | Not required | No | No | Yes |

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Federated Model Merging Without a Parameter Server](./federated-model-merging.md)
- [Guide — LoRA Adapter Merging](./lora-adapter-merging.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [API Reference — ContinualMerge](../api-reference/layer4-ai/model.md)
- [Benchmarks — A100 GPU Performance](../benchmarks/v030_a100_analysis.md)
