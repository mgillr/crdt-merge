# All 26 Model Merge Strategies

> **crdt-merge v0.9.2** — Complete reference for every strategy in the registry.
>
> Use `get_strategy("registry_name")` to instantiate any strategy.

## Quick Reference

| # | Registry Name | Class | Category | Commutative | Associative | Idempotent |
|---|--------------|-------|----------|:-----------:|:-----------:|:----------:|
| 1 | `linear` | LinearInterpolation | Basic | conditional | ✗ | ✓ |
| 2 | `slerp` | SphericalLinearInterpolation | Basic | conditional | ✗ | ✓ |
| 3 | `weight_average` | WeightAverage | Basic | ✓ | ✗ | ✓ |
| 4 | `task_arithmetic` | TaskArithmetic | Basic | ✓ | ✓ | ✗ |
| 5 | `ties` | TIESMerge | Subspace | ✓ | ✗ | ✗ |
| 6 | `dare` | DareDropAndRescale | Subspace | ✗ | ✗ | ✗ |
| 7 | `dare_ties` | DareTiesHybrid | Subspace | ✗ | ✗ | ✗ |
| 8 | `della` | DellaDropElectLowRank | Subspace | ✗ | ✗ | ✗ |
| 9 | `emr` | EMRMerge | Subspace | ✓ | ✗ | ✗ |
| 10 | `model_breadcrumbs` | ModelBreadcrumbs | Subspace | ✓ | ✗ | ✗ |
| 11 | `adarank` | AdaptiveRankPruning | Subspace | ✓ | ✗ | ✗ |
| 12 | `star` | SpectralTruncationAdaptiveRescaling | Subspace | ✓ | ✗ | ✗ |
| 13 | `svd_knot_tying` | SVDKnotTying | Subspace | ✓ | ✗ | ✓ |
| 14 | `fisher_merge` | FisherMerge | Weighted | ✓ | ✗ | ✓ |
| 15 | `ada_merging` | AdaptiveMerging | Weighted | conditional | conditional | ✓ |
| 16 | `dam` | DifferentiableAdaptiveMerging | Weighted | conditional | conditional | ✓ |
| 17 | `regression_mean` | RegressionMean | Weighted | ✓ | ✗ | ✓ |
| 18 | `evolutionary_merge` | EvolutionaryMerge | Evolutionary | ✗ | ✗ | ✗ |
| 19 | `genetic_merge` | GeneticMerge | Evolutionary | ✗ | ✗ | ✓ |
| 20 | `safe_merge` | SafeMerge | Safety | ✓ | ✗ | ✓ |
| 21 | `led_merge` | LEDMerge | Safety | ✓ | ✗ | ✓ |
| 22 | `negative_merge` | NegativeMerge | Unlearning | ✓ | ✗ | ✗ |
| 23 | `split_unlearn_merge` | SplitUnlearnMerge | Unlearning | ✓ | ✗ | ✗ |
| 24 | `representation_surgery` | RepresentationSurgery | Calibration | ✓ | ✗ | ✓ |
| 25 | `weight_scope_alignment` | WeightScopeAlignment | Calibration | ✓ | ✗ | ✓ |
| 26 | `dual_projection` | DualProjectionMerge | Continual | ✓ | ✓ | ✓ |

---

## Basic Strategies

### `linear` — LinearInterpolation

Element-wise linear interpolation between two or more model weight tensors.

- **Module**: `crdt_merge.model.strategies.basic`
- **Paper**: Wortsman et al., 2022 — *Model soups: averaging weights of multiple fine-tuned models improves accuracy without increasing inference time*
- **CRDT**: commutative (conditional) · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("linear")
result = strategy.merge(tensors, weights=[0.6, 0.4])
```

---

### `slerp` — SphericalLinearInterpolation

Spherical linear interpolation (SLERP) — interpolates along the great circle on the hypersphere, preserving angular relationships between weight vectors.

- **Module**: `crdt_merge.model.strategies.basic`
- **Paper**: Shoemake, 1985 — *Animating Rotation with Quaternion Curves*
- **CRDT**: commutative (conditional) · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("slerp")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

### `weight_average` — WeightAverage

Weighted element-wise average of model parameters. The foundational strategy behind Federated Averaging.

- **Module**: `crdt_merge.model.strategies.basic`
- **Paper**: McMahan et al., 2017 — *Communication-Efficient Learning of Deep Networks from Decentralized Data*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("weight_average")
result = strategy.merge(tensors, weights=[0.5, 0.3, 0.2])
```

---

### `task_arithmetic` — TaskArithmetic

Computes task vectors (difference from a shared base model) and additively combines them, enabling compositional multi-task merging.

- **Module**: `crdt_merge.model.strategies.basic`
- **Paper**: Ilharco et al., 2023 — *Editing Models with Task Arithmetic*
- **CRDT**: commutative ✓ · associative ✓ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("task_arithmetic")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

## Subspace / Sparsification Strategies

### `ties` — TIESMerge

Trim low-magnitude values, Elect a consensus sign, and merge only agreeing components — resolves interference between task vectors.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Yadav et al., NeurIPS 2023 — *Resolving Interference When Merging Models (TIES-Merging)*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("ties")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `dare` — DareDropAndRescale

Randomly drops delta parameters with a given probability and rescales the survivors, reducing interference while preserving expected magnitude.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Yu et al., 2024 — *Language Models are Super Mario*
- **CRDT**: commutative ✗ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("dare")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `dare_ties` — DareTiesHybrid

Combines DARE's stochastic dropout with TIES' sign-election consensus for a best-of-both-worlds sparsification approach.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Community hybrid, 2024 — *DARE-TIES*
- **CRDT**: commutative ✗ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("dare_ties")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `della` — DellaDropElectLowRank

Drop, Elect, and Low-Rank Approximate — extends DARE-TIES with a low-rank reconstruction step to recover information lost during sparsification.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Bansal, 2024 — *DELLA-Merging*
- **CRDT**: commutative ✗ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("della")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `emr` — EMRMerge

Elect, Mask, and Rescale — partitions parameters into shared and task-specific sets, applying distinct rescaling to each to minimize cross-task noise.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Huang et al., 2024 — *EMR-Merging*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("emr")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `model_breadcrumbs` — ModelBreadcrumbs

Identifies and retains only the most important "breadcrumb" parameters that moved significantly during fine-tuning, discarding noisy updates.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: Davari & Belilovsky, 2023 — *Model Breadcrumbs*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("model_breadcrumbs")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `adarank` — AdaptiveRankPruning

Adaptively selects the rank for each weight matrix during merging, pruning low-importance singular components to reduce redundancy.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: ICLR 2026 — *AdaRank: Adaptive Rank Pruning for Model Merging*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("adarank")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `star` — SpectralTruncationAdaptiveRescaling

Truncates the spectrum (singular values) of task vectors and adaptively rescales the retained components to balance task contributions.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: 2025 — *Spectral Truncation Adaptive Rescaling (STAR)*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("star")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

### `svd_knot_tying` — SVDKnotTying

Aligns the SVD subspaces of task vectors before merging by tying singular-vector "knots", reducing destructive interference between tasks.

- **Module**: `crdt_merge.model.strategies.subspace`
- **Paper**: 2024 — *SVD Knot Tying: Aligning Merge Subspaces*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("svd_knot_tying")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

## Weighted / Importance Strategies

### `fisher_merge` — FisherMerge

Weights each parameter by its Fisher information (diagonal approximation), giving higher influence to parameters that matter more for each task.

- **Module**: `crdt_merge.model.strategies.weighted`
- **Paper**: Matena & Raffel, 2022 — *Merging Models with Fisher-Weighted Averaging*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("fisher_merge")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

### `ada_merging` — AdaptiveMerging

Learns per-layer or per-task merging coefficients automatically using entropy minimization on unlabeled test data.

- **Module**: `crdt_merge.model.strategies.weighted`
- **Paper**: Yang et al., 2024 — *AdaMerging: Adaptive Model Merging*
- **CRDT**: commutative (conditional) · associative (conditional) · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("ada_merging")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

### `dam` — DifferentiableAdaptiveMerging

End-to-end differentiable merging that jointly optimizes merge coefficients via gradient descent on a validation objective.

- **Module**: `crdt_merge.model.strategies.weighted`
- **Paper**: 2024 — *Differentiable Adaptive Merging (DAM)*
- **CRDT**: commutative (conditional) · associative (conditional) · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("dam")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

### `regression_mean` — RegressionMean

Computes the merge as a regression-optimal mean that minimizes expected prediction error across constituent models.

- **Module**: `crdt_merge.model.strategies.weighted`
- **Paper**: Jin et al., 2023 — *Dataless Knowledge Fusion by Merging Weights*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("regression_mean")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

## Evolutionary Strategies

### `evolutionary_merge` — EvolutionaryMerge

Uses CMA-ES or similar evolutionary optimization to search for layer-wise merge coefficients that maximize a fitness function.

- **Module**: `crdt_merge.model.strategies.evolutionary`
- **Paper**: Sakana AI, 2024; M2N2 (GECCO 2025)
- **CRDT**: commutative ✗ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("evolutionary_merge")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

### `genetic_merge` — GeneticMerge

Applies genetic-algorithm-based crossover and mutation to evolve merge recipes, selecting the best-performing merged model across generations.

- **Module**: `crdt_merge.model.strategies.evolutionary`
- **Paper**: Mergenetic library, 2025
- **CRDT**: commutative ✗ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("genetic_merge")
result = strategy.merge(tensors, weights=[0.5, 0.5])
```

---

## Safety-Aware Strategies

### `safe_merge` — SafeMerge

Preserves safety-critical layers (e.g., RLHF alignment heads) by detecting and protecting them during the merge process.

- **Module**: `crdt_merge.model.strategies.safety`
- **Paper**: 2025 — *Safety-Preserving Model Merging*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("safe_merge")
result = strategy.merge(tensors, base=base_tensor, weights=[0.5, 0.5])
```

---

### `led_merge` — LEDMerge

Layer-wise Evaluation-Driven merging — evaluates each layer independently against a safety benchmark and adjusts merge ratios to preserve safe behavior.

- **Module**: `crdt_merge.model.strategies.safety`
- **Paper**: 2025 — *Layer-wise Evaluation-Driven Merging (LED)*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("led_merge")
result = strategy.merge(tensors, base=base_tensor, weights=[0.5, 0.5])
```

---

## Unlearning Strategies

### `negative_merge` — NegativeMerge

Negates (subtracts) the task vector of an undesirable capability from the base model, effectively removing learned behaviors.

- **Module**: `crdt_merge.model.strategies.unlearning`
- **Paper**: ICML 2025 — *NegMerge: Weight Negation for Unlearning*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("negative_merge")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, -1.0])
```

---

### `split_unlearn_merge` — SplitUnlearnMerge

Splits the model into retain/forget partitions, applies targeted unlearning to the forget set, and re-merges the cleaned components.

- **Module**: `crdt_merge.model.strategies.unlearning`
- **Paper**: 2025 — *Sequential Split-Unlearn-Merge*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✗

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("split_unlearn_merge")
result = strategy.merge(tensors, base=base_tensor, weights=[1.0, 1.0])
```

---

## Post-Calibration Strategies

### `representation_surgery` — RepresentationSurgery

Post-merge calibration that corrects representation drift by aligning the merged model's internal representations back toward the base or reference model.

- **Module**: `crdt_merge.model.strategies.calibration`
- **Paper**: 2024 — *Post-Merge Representation Surgery*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("representation_surgery")
result = strategy.merge(tensors, base=base_tensor, weights=[0.5, 0.5])
```

---

### `weight_scope_alignment` — WeightScopeAlignment

Aligns the scope (distribution range) of merged weights to match the expected weight distribution, correcting magnitude drift after merging.

- **Module**: `crdt_merge.model.strategies.calibration`
- **Paper**: 2024 — *Weight Distribution Scope Alignment*
- **CRDT**: commutative ✓ · associative ✗ · idempotent ✓

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("weight_scope_alignment")
result = strategy.merge(tensors, base=base_tensor, weights=[0.5, 0.5])
```

---

## Continual Learning Strategies

### `dual_projection` — DualProjectionMerge

Projects task vectors onto dual subspaces (stable vs. plastic) to merge new knowledge while preserving previously learned information. The only strategy that achieves TRUE_CRDT tier.

- **Module**: `crdt_merge.model.strategies.continual`
- **Paper**: Yuan et al., NeurIPS 2025
- **CRDT**: commutative ✓ · associative ✓ · idempotent ✓ · **TRUE_CRDT**

```python
from crdt_merge.model.strategies import get_strategy

strategy = get_strategy("dual_projection")
# Constructor accepts optional tuning parameters
# strategy = DualProjectionMerge(stability_weight=0.5, rank_fraction=0.5)
result = strategy.merge(tensors, base=base_tensor, weights=[0.5, 0.5])
```
