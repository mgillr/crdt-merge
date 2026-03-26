# SPDX-License-Identifier: BUSL-1.1

# Model Strategy CRDT Property Matrix

This guide documents the algebraic properties of every model-merge strategy
shipped with crdt-merge. Understanding these properties is essential for
choosing strategies in distributed, multi-node, or multi-round merge pipelines
where the order and grouping of operations must not affect the final result.

---

## CRDT Properties for Model Merging

### Commutativity

A strategy is **commutative** when `merge(A, B) == merge(B, A)`. In a
distributed system where nodes may receive models in arbitrary order, a
commutative strategy produces the same result regardless of message arrival
sequence. Non-commutative strategies require a globally agreed ordering.

### Associativity

A strategy is **associative** when `merge(merge(A, B), C) == merge(A, merge(B, C))`.
Associativity enables safe pairwise chaining: you can merge models two at a
time in any grouping and obtain the same result as a single N-way merge.
Non-associative strategies must receive all models in a single call to avoid
order-dependent bias.

### Idempotency

A strategy is **idempotent** when `merge(A, A) == A`. Idempotency means that
re-applying a merge (e.g., after a network retry or duplicate delivery) does
not change the state. Strategies that are not idempotent will drift if the
same model is applied multiple times.

### N-Way Safety

A strategy is **safe for direct N-way** merge when all inputs can be passed
in a single `merge([t1, t2, ..., tN])` call and the result does not depend on
internal processing order. Strategies that are only **pairwise-safe** require
sequential or tree-structured application but may give different results
depending on the pairing order.

### Notation

| Symbol | Meaning |
|--------|---------|
| | Property holds unconditionally |
| | Property does not hold |
| | Conditional — holds under specific assumptions (see Notes column) |
| N/A | Not applicable |

---

## Strategy CRDT Property Matrix

| Strategy | Registry Name | Commutative | Associative | Idempotent | N-Way Safe | Notes |
|----------|--------------|:-----------:|:-----------:|:----------:|:----------:|-------|
| **WeightAverage** | `weight_average` | | | | | Pass all tensors in one call. Pairwise averaging assigns progressively less weight to earlier inputs. Single-call N-way result is order-independent. |
| **LinearInterpolation** | `linear` | | | | | Commutative only when `t=0.5`. Pairwise sequential for N>2; result depends on pairing order. Prefer `weight_average` for true N-way. |
| **SLERP** | `slerp` | | | | | Commutative at `t=0.5`; not in general. Pairwise sequential for N>2 introduces order dependence. Use for two-model merges only. |
| **TaskArithmetic** | `task_arithmetic` | | | | | Fully commutative and associative — task vectors add independently. Not idempotent: applying the same model twice doubles its task vector. Requires a base model. |
| **TIES** | `ties` | | | | | Sign election is commutative (majority vote). Not associative under pairwise composition because sign masks change when computed on intermediate results. Pass all models together. |
| **DARE** | `dare` | | | | | Random dropout is seeded per-call; results vary between runs without a fixed seed. Not idempotent. Best applied once with all models. |
| **DELLA** | `della` | | | | | Magnitude-aware DARE variant. Same caveats as DARE regarding idempotency and ordering. |
| **DARETies** | `dare_ties` | | | | | Hybrid combining DARE dropout and TIES sign election. TIES component is commutative; DARE component is not idempotent. Pass all models in one call. |
| **ModelBreadcrumbs** | `breadcrumbs` | | | | | Binary sparse masks are commutative (OR-union). Not associative: mask density depends on which models are included in a given call. |
| **EMRMerge** | `emr` | | | | | Elect-Mask-Rescale. Commutative and idempotent but not associative under pairwise application due to rescaling on intermediate results. |
| **STAR** | `star` | | | | | Spectral truncation changes with the set of models provided. Non-associative. Idempotent. |
| **SVDKnotTying** | `svd_knot_tying` | | | | | SVD alignment is not commutative in general; order affects which basis is treated as reference. Pairwise only. |
| **AdaptiveRankPruning** | `ada_rank` | | | | | Rank pruning thresholds are computed globally; commutative. Not associative. |
| **FisherMerge** | `fisher_merge` | | | | | Fisher information proxy `|θ|²` changes on intermediate merges. Pass all models in one call for correct N-way result. |
| **RegressionMean** | `regression_mean` | | | | | Self-weighted by `θ²+λ`. Non-associative under pairwise composition; single N-way call is correct. |
| **AdaptiveMerging** | `ada_merging` | | | | | Entropy-based iterative refinement converges to the same fixed point only when inputs have identical entropy distributions. Treat as conditionally commutative and associative. |
| **DifferentiableAdaptiveMerging** | `dam` | | | | | Gradient-free optimisation; convergence point depends on initialization order for asymmetric inputs. Idempotent. |
| **EvolutionaryMerge** | `evolutionary` | | | | | CMA-ES population search uses random seeds. Results are non-deterministic without a fixed seed. Not suitable for CRDT-safe distributed merging. |
| **GeneticMerge** | `genetic` | | | | | Genetic algorithm with crossover/mutation. Same caveats as EvolutionaryMerge. Use only in offline/experimental pipelines. |
| **Passthrough** | `passthrough` | | | | | Returns the first tensor unchanged. Trivially satisfies all CRDT properties. Used as a no-op placeholder. |
| **DualProjection** | `dual_projection` | | | | | Shared subspace (GCounter semantics) is commutative and idempotent. Task-specific subspace (OR-Set semantics) is commutative but not associative under pairwise composition. |
| **UniformAverage** | `uniform_average` | | | | | Special case of `weight_average` with equal weights. Same pairwise non-associativity; use single N-way call. |
| **MagnitudePrune** | `magnitude_prune` | | | | | Pruning threshold is computed from the merged tensor; different when applied pairwise vs. jointly. |
| **RandPrune** | `rand_prune` | | | | | Random pruning is not idempotent (each call may drop different parameters). Use for one-shot model compression only. |
| **LoRAMerge** | `lora_merge` | | | | | Low-rank adapter averaging. Non-associative because rank selection changes with the set of adapters provided. |
| **KnowledgeDistillation** | `knowledge_distillation` | | | | | Requires forward-pass evaluation data; result depends on dataset ordering. Primarily a training-time operation. |
| **SER** | `ser` | | | | | Spectral Entropy Regularization. Commutative and idempotent. Non-associative due to spectral decomposition on intermediate results. |
| **HessianWeighted** | `hessian_weighted` | | | | | Fisher approximation via Hessian diagonal. Commutative and idempotent. Non-associative under pairwise composition; pass all models together. |
| **GradientWeighted** | `gradient_weighted` | | | | | Weight by gradient magnitude. Commutative and idempotent. Non-associative. |
| **ConsensusVoting** | `consensus_voting` | | | | | Majority-vote sign selection. Commutative and idempotent. Non-associative because vote counts depend on which models are included. |
| **MoEExpert** | `moe_expert` | | | | | Mixture-of-Experts router merging. Commutative. Not idempotent if expert routing changes. |
| **KnowledgeGraph** | `knowledge_graph` | | | | | Graph-topology-aware merging; commutativity depends on edge symmetry. Not suitable for fully automated distributed merging. |
| **EnsembleDistillation** | `ensemble_distillation` | | | | | Logit ensembling with distillation; requires consistent token vocabularies across models. |
| **ActivationAware** | `activation_aware` | | | | | Weighted by activation statistics. Commutative given identical calibration data. |
| **LayerWiseLearningRate** | `layer_wise_lr` | | | | | Layer-specific coefficients; commutative but non-associative under pairwise composition. |
| **SparseAttention** | `sparse_attention` | | | | | Attention-head sparsification. Commutative and idempotent. Non-associative. |

---

## N-Way vs. Pairwise Summary

### Safe for Direct N-Way (pass all models in one call)

These strategies produce order-independent results when all tensors are
provided to a single `merge([t1, ..., tN])` call:

- `weight_average`, `uniform_average`
- `task_arithmetic`
- `fisher_merge`, `regression_mean`
- `hessian_weighted`, `gradient_weighted`
- `consensus_voting`
- `ties`, `breadcrumbs`, `emr`
- `dual_projection`
- `passthrough`

### Pairwise-Only (sequential or tree-structured application)

These strategies may give different results depending on pairing order. Use
them for two-model merges, or apply them as a final step after pre-aggregating
with an N-way strategy:

- `slerp`, `linear` — designed for two-model interpolation
- `svd_knot_tying` — SVD alignment selects a reference basis
- `evolutionary`, `genetic` — stochastic; not suitable for CRDT workflows
- `knowledge_distillation`, `knowledge_graph`, `ensemble_distillation` — require data evaluation
- `lora_merge` — rank selection changes with adapter count

---

## Usage Guidance

### General-Purpose Merging

**`weight_average`** is the workhorse for most merging tasks. It satisfies
commutativity and idempotency, produces stable results when all models are
passed together, and has a clear mathematical interpretation (McMahan et al.,
FedAvg). Use it as the default unless you have a specific reason not to.

**`task_arithmetic`** is the right choice when you have a pretrained base
model and want to add or remove capabilities surgically. Its full
commutativity and associativity make it the most CRDT-safe strategy in the
library. Scaling coefficients (`scaling_coefficients=[0.5, 0.3]`) control
how strongly each fine-tuned model's task vector is applied.

### Geometry-Preserving Merges

**`slerp`** is best for two-model merges where maintaining directional
geometry in weight space matters (e.g., instruction-tuned chat models).
Restrict to two models; for more models, consider sequential application
with decreasing `t` values or switch to `weight_average`.

**`linear`** is the simplest interpolation and is equivalent to `weight_average`
at uniform weights. Use it for rapid prototyping.

### Sparse / Conflict-Aware Merges

**`ties`** and **`dare_ties`** are recommended when merging models fine-tuned
on competing tasks. TIES resolves sign conflicts via majority vote, reducing
interference. DARE adds stochastic pruning to further reduce redundancy.

**`breadcrumbs`** and **`emr`** are lighter-weight sparsification approaches
that do not require a base model, making them applicable when the base
checkpoint is unavailable.

### Importance-Weighted Merges

**`fisher_merge`** is the principled choice when Fisher information matrices
are available from training. It weights each parameter by its importance to
the model's task. Without precomputed Fisher matrices, it falls back to
magnitude-based importance (`|θ|²`), which is a reasonable proxy.

**`regression_mean`** (RegMean) is a fast closed-form alternative that
self-weights by parameter magnitude with ridge regularization. Good for
merging many fine-tuned variants of the same base model.

### Experimental / Research Strategies

**`evolutionary`** and **`genetic`** strategies are non-deterministic and
not suitable for production distributed workflows. Use them only in
controlled offline experiments where result reproducibility can be enforced
via fixed random seeds.

**`knowledge_distillation`** and **`ensemble_distillation`** require forward
passes over calibration data and a teacher-student training step. They are
training-time operations rather than weight-space merge operations.

### LoRA Adapters

**`lora_merge`** is the correct strategy for merging PEFT/LoRA adapters. It
handles rank alignment automatically. Use the `linear` or `cat` sub-strategy
via `--rank-method` to control how adapter ranks are combined.

---

## Selecting a Strategy: Decision Guide

```
Does your merge involve LoRA adapters?
  → lora_merge

Do you have a pretrained base model?
  Yes: Do tasks compete (different domains)?
    Yes  → dare_ties, ties, breadcrumbs
    No   → task_arithmetic, slerp (2 models), weight_average (N models)
  No: → weight_average, fisher_merge, regression_mean

Do you need full CRDT guarantees (commutative + associative + idempotent)?
  → task_arithmetic (with base) or weight_average / fisher_merge / regression_mean (without base)

Merging exactly two models?
  → slerp, linear, or any N-way strategy

Need maximum simplicity?
  → weight_average or linear
```

---

## Code Examples

### Two-Layer Architecture: CRDTMergeState

All strategies are made CRDT-safe through the `CRDTMergeState` wrapper. The CRDT guarantee comes from **set union** (OR-Set semantics) at the contribution level — not from the strategy itself.

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# Node A adds its contribution
state_a = CRDTMergeState("weight_average")
state_a.add_contribution(tensor_a, model_id="node_a", weight=1.0)

# Node B adds its contribution
state_b = CRDTMergeState("weight_average")
state_b.add_contribution(tensor_b, model_id="node_b", weight=1.0)

# CRDT guarantee: any merge order converges to the same state
merged_1 = state_a.merge(state_b)   # merge is in-place on state_a, returns self
merged_2 = state_b.merge(state_a)   # different order
assert merged_1.state_hash == merged_2.state_hash  # same content 

# resolve() applies the strategy to all contributions
result = merged_1.resolve()
```

### N-Way Strategies (pass all models together)

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# weight_average: N-way safe, commutative, idempotent
state = CRDTMergeState("weight_average")
state.add_contribution(model_a, model_id="hospital_a", weight=0.4)
state.add_contribution(model_b, model_id="hospital_b", weight=0.3)
state.add_contribution(model_c, model_id="hospital_c", weight=0.3)

merged = state.resolve()   # Weighted average of all three — order-independent 
```

### Strategies Requiring a Base Model (TIES, DARE, TaskArithmetic)

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# ties: requires base= at construction time
state = CRDTMergeState("ties", base=pretrained_llama)
state.add_contribution(finetuned_chat, model_id="chat-ft")
state.add_contribution(finetuned_code, model_id="code-ft")

merged = state.resolve()   # TIES sign election across both fine-tuned models
```

```python
# task_arithmetic: fully commutative + associative + NOT idempotent
state_ta = CRDTMergeState("task_arithmetic", base=base_model)
state_ta.add_contribution(expert_model, model_id="expert", weight=0.7)
merged = state_ta.resolve()
```

```python
# dare_ties: DARE pruning + TIES sign election
state_dt = CRDTMergeState("dare_ties", base=pretrained_base)
state_dt.add_contribution(domain_a, model_id="domain_a")
state_dt.add_contribution(domain_b, model_id="domain_b")
merged = state_dt.resolve()
```

### Two-Model Interpolation (SLERP, Linear)

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# slerp: commutative at t=0.5 only — best for two-model merges
state = CRDTMergeState("slerp")
state.add_contribution(base_model, model_id="base", weight=0.5)
state.add_contribution(instruct_model, model_id="instruct", weight=0.5)
merged = state.resolve()
```

### Checking CRDT Properties at Runtime

```python
from crdt_merge.model.crdt_state import CRDTMergeState

state_x = CRDTMergeState("weight_average")
state_x.add_contribution(model_a, model_id="a")
state_y = CRDTMergeState("weight_average")
state_y.add_contribution(model_b, model_id="b")

# Commutativity: merge order doesn't matter
m1 = CRDTMergeState("weight_average").merge(state_x).merge(state_y)
m2 = CRDTMergeState("weight_average").merge(state_y).merge(state_x)
assert m1.state_hash == m2.state_hash   # 

# Idempotency: merging same state twice
m3 = CRDTMergeState("weight_average").merge(state_x).merge(state_x)
m4 = CRDTMergeState("weight_average").merge(state_x)
assert m3.state_hash == m4.state_hash   # (OR-Set deduplicates by model_id)
```

### LoRA Adapter Merging

```python
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

schema = LoRAMergeSchema(
    default_strategy="weight_average",
    layer_strategies={
        "q_proj": "weight_average",
        "v_proj": "weight_average",
    }
)
merger = LoRAMerge(schema=schema)
merged_adapter = merger.merge([adapter_a, adapter_b])
```

### Distributed Federation Example

```python
from crdt_merge.model.crdt_state import CRDTMergeState

# Each hospital creates its own state and trains locally
hospital_a = CRDTMergeState("weight_average")
hospital_a.add_contribution(local_model_a, model_id="hospital_a")

hospital_b = CRDTMergeState("weight_average")
hospital_b.add_contribution(local_model_b, model_id="hospital_b")

# Coordinator merges — no parameter server needed
# Any merge order converges to the same global model
global_state = CRDTMergeState("weight_average")
global_state.merge(hospital_a)
global_state.merge(hospital_b)

print(global_state.state_hash)   # SHA-256 Merkle root of all contributions
federated_model = global_state.resolve()
```
