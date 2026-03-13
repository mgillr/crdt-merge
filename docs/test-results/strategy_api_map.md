# Strategy → Codebase API Map

**Date**: 2026-03-31  
**crdt-merge version**: 0.9.2  
**Total strategies**: 26  
**Total categories**: 10

## Category Overview

| Category | Strategies | Module |
|----------|-----------|--------|
| Evolutionary | `evolutionary_merge`, `genetic_merge` | evolutionary |
| Post-Calibration | `representation_surgery`, `weight_scope_alignment` | calibration |
| Safety-Aware | `led_merge`, `safe_merge` | safety |
| Subspace / Sparsification | `adarank`, `dare`, `dare_ties`, `della`, `emr`, `model_breadcrumbs`, `star`, `svd_knot_tying`, `ties` | subspace |
| Unlearning | `negative_merge`, `split_unlearn_merge` | unlearning |
| Weighted / Importance | `ada_merging`, `dam`, `fisher_merge`, `regression_mean` | weighted |
| averaging | `weight_average` | basic |
| continual | `dual_projection` | continual |
| interpolation | `linear`, `slerp` | basic |
| task_vector | `task_arithmetic` | basic |

## Full API Map

### `ada_merging` → `AdaptiveMerging`

| Property | Value |
|----------|-------|
| **Registry name** | `ada_merging` |
| **Class** | `AdaptiveMerging` |
| **Module** | `crdt_merge.model.strategies.weighted` |
| **Source** | `crdt_merge/model/strategies/weighted.py` |
| **Category** | Weighted / Importance |
| **Paper** | Yang et al., 2024 — AdaMerging: Adaptive Model Merging |
| **CRDT props** | `{"commutative": "conditional", "associative": "conditional", "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 131 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `adarank` → `AdaptiveRankPruning`

| Property | Value |
|----------|-------|
| **Registry name** | `adarank` |
| **Class** | `AdaptiveRankPruning` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | ICLR 2026 — AdaRank: Adaptive Rank Pruning for Model Merging |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 126 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `dam` → `DifferentiableAdaptiveMerging`

| Property | Value |
|----------|-------|
| **Registry name** | `dam` |
| **Class** | `DifferentiableAdaptiveMerging` |
| **Module** | `crdt_merge.model.strategies.weighted` |
| **Source** | `crdt_merge/model/strategies/weighted.py` |
| **Category** | Weighted / Importance |
| **Paper** | 2024 — Differentiable Adaptive Merging (DAM) |
| **CRDT props** | `{"commutative": "conditional", "associative": "conditional", "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 118 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `dare` → `DareDropAndRescale`

| Property | Value |
|----------|-------|
| **Registry name** | `dare` |
| **Class** | `DareDropAndRescale` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Yu et al., 2024 — Language Models are Super Mario |
| **CRDT props** | `{"commutative": false, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 68 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `dare_ties` → `DareTiesHybrid`

| Property | Value |
|----------|-------|
| **Registry name** | `dare_ties` |
| **Class** | `DareTiesHybrid` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Community hybrid, 2024 — DARE-TIES |
| **CRDT props** | `{"commutative": false, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 133 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `della` → `DellaDropElectLowRank`

| Property | Value |
|----------|-------|
| **Registry name** | `della` |
| **Class** | `DellaDropElectLowRank` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Bansal, 2024 — DELLA-Merging |
| **CRDT props** | `{"commutative": false, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 86 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `dual_projection` → `DualProjectionMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `dual_projection` |
| **Class** | `DualProjectionMerge` |
| **Module** | `crdt_merge.model.strategies.continual` |
| **Source** | `crdt_merge/model/strategies/continual.py` |
| **Category** | continual |
| **Paper** | Yuan et al., NeurIPS 2025 |
| **CRDT props** | `{"commutative": true, "associative": true, "idempotent": true, "crdt_tier": "TRUE_CRDT"}` |
| **Constructor** | `(self, stability_weight: 'float' = 0.5, rank_fraction: 'float' = 0.5) -> 'None'` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 262 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `emr` → `EMRMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `emr` |
| **Class** | `EMRMerge` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Huang et al., 2024 — EMR-Merging |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 104 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `evolutionary_merge` → `EvolutionaryMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `evolutionary_merge` |
| **Class** | `EvolutionaryMerge` |
| **Module** | `crdt_merge.model.strategies.evolutionary` |
| **Source** | `crdt_merge/model/strategies/evolutionary.py` |
| **Category** | Evolutionary |
| **Paper** | Sakana AI, 2024; M2N2 (GECCO 2025) |
| **CRDT props** | `{"commutative": false, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 122 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `fisher_merge` → `FisherMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `fisher_merge` |
| **Class** | `FisherMerge` |
| **Module** | `crdt_merge.model.strategies.weighted` |
| **Source** | `crdt_merge/model/strategies/weighted.py` |
| **Category** | Weighted / Importance |
| **Paper** | Matena & Raffel, 2022 — Merging Models with Fisher-Weighted Averaging |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 103 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `genetic_merge` → `GeneticMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `genetic_merge` |
| **Class** | `GeneticMerge` |
| **Module** | `crdt_merge.model.strategies.evolutionary` |
| **Source** | `crdt_merge/model/strategies/evolutionary.py` |
| **Category** | Evolutionary |
| **Paper** | Mergenetic library, 2025 |
| **CRDT props** | `{"commutative": false, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 138 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `led_merge` → `LEDMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `led_merge` |
| **Class** | `LEDMerge` |
| **Module** | `crdt_merge.model.strategies.safety` |
| **Source** | `crdt_merge/model/strategies/safety.py` |
| **Category** | Safety-Aware |
| **Paper** | 2025 — Layer-wise Evaluation-Driven Merging (LED) |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 121 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `linear` → `LinearInterpolation`

| Property | Value |
|----------|-------|
| **Registry name** | `linear` |
| **Class** | `LinearInterpolation` |
| **Module** | `crdt_merge.model.strategies.basic` |
| **Source** | `crdt_merge/model/strategies/basic.py` |
| **Category** | interpolation |
| **Paper** | Wortsman et al., 2022 — Model soups: averaging weights of multiple fine-tuned models improves accuracy without increasing inference time |
| **CRDT props** | `{"commutative": "conditional", "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 62 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `model_breadcrumbs` → `ModelBreadcrumbs`

| Property | Value |
|----------|-------|
| **Registry name** | `model_breadcrumbs` |
| **Class** | `ModelBreadcrumbs` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Davari & Belilovsky, 2023 — Model Breadcrumbs |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 93 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `negative_merge` → `NegativeMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `negative_merge` |
| **Class** | `NegativeMerge` |
| **Module** | `crdt_merge.model.strategies.unlearning` |
| **Source** | `crdt_merge/model/strategies/unlearning.py` |
| **Category** | Unlearning |
| **Paper** | ICML 2025 — NegMerge: Weight Negation for Unlearning |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 108 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `regression_mean` → `RegressionMean`

| Property | Value |
|----------|-------|
| **Registry name** | `regression_mean` |
| **Class** | `RegressionMean` |
| **Module** | `crdt_merge.model.strategies.weighted` |
| **Source** | `crdt_merge/model/strategies/weighted.py` |
| **Category** | Weighted / Importance |
| **Paper** | Jin et al., 2023 — Dataless Knowledge Fusion by Merging Weights |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 86 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `representation_surgery` → `RepresentationSurgery`

| Property | Value |
|----------|-------|
| **Registry name** | `representation_surgery` |
| **Class** | `RepresentationSurgery` |
| **Module** | `crdt_merge.model.strategies.calibration` |
| **Source** | `crdt_merge/model/strategies/calibration.py` |
| **Category** | Post-Calibration |
| **Paper** | 2024 — Post-Merge Representation Surgery |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 150 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `safe_merge` → `SafeMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `safe_merge` |
| **Class** | `SafeMerge` |
| **Module** | `crdt_merge.model.strategies.safety` |
| **Source** | `crdt_merge/model/strategies/safety.py` |
| **Category** | Safety-Aware |
| **Paper** | 2025 — Safety-Preserving Model Merging |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 117 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `slerp` → `SphericalLinearInterpolation`

| Property | Value |
|----------|-------|
| **Registry name** | `slerp` |
| **Class** | `SphericalLinearInterpolation` |
| **Module** | `crdt_merge.model.strategies.basic` |
| **Source** | `crdt_merge/model/strategies/basic.py` |
| **Category** | interpolation |
| **Paper** | Shoemake, 1985 — Animating Rotation with Quaternion Curves |
| **CRDT props** | `{"commutative": "conditional", "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 135 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `split_unlearn_merge` → `SplitUnlearnMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `split_unlearn_merge` |
| **Class** | `SplitUnlearnMerge` |
| **Module** | `crdt_merge.model.strategies.unlearning` |
| **Source** | `crdt_merge/model/strategies/unlearning.py` |
| **Category** | Unlearning |
| **Paper** | 2025 — Sequential Split-Unlearn-Merge |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 110 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `star` → `SpectralTruncationAdaptiveRescaling`

| Property | Value |
|----------|-------|
| **Registry name** | `star` |
| **Class** | `SpectralTruncationAdaptiveRescaling` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | 2025 — Spectral Truncation Adaptive Rescaling (STAR) |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 121 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `svd_knot_tying` → `SVDKnotTying`

| Property | Value |
|----------|-------|
| **Registry name** | `svd_knot_tying` |
| **Class** | `SVDKnotTying` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | 2024 — SVD Knot Tying: Aligning Merge Subspaces |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 122 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `task_arithmetic` → `TaskArithmetic`

| Property | Value |
|----------|-------|
| **Registry name** | `task_arithmetic` |
| **Class** | `TaskArithmetic` |
| **Module** | `crdt_merge.model.strategies.basic` |
| **Source** | `crdt_merge/model/strategies/basic.py` |
| **Category** | task_vector |
| **Paper** | Ilharco et al., 2023 — Editing Models with Task Arithmetic |
| **CRDT props** | `{"commutative": true, "associative": true, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 76 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `ties` → `TIESMerge`

| Property | Value |
|----------|-------|
| **Registry name** | `ties` |
| **Class** | `TIESMerge` |
| **Module** | `crdt_merge.model.strategies.subspace` |
| **Source** | `crdt_merge/model/strategies/subspace.py` |
| **Category** | Subspace / Sparsification |
| **Paper** | Yadav et al., NeurIPS 2023 — Resolving Interference When Merging Models (TIES-Merging) |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": false}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 132 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `weight_average` → `WeightAverage`

| Property | Value |
|----------|-------|
| **Registry name** | `weight_average` |
| **Class** | `WeightAverage` |
| **Module** | `crdt_merge.model.strategies.basic` |
| **Source** | `crdt_merge/model/strategies/basic.py` |
| **Category** | averaging |
| **Paper** | McMahan et al., 2017 — Communication-Efficient Learning of Deep Networks from Decentralized Data |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 63 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

### `weight_scope_alignment` → `WeightScopeAlignment`

| Property | Value |
|----------|-------|
| **Registry name** | `weight_scope_alignment` |
| **Class** | `WeightScopeAlignment` |
| **Module** | `crdt_merge.model.strategies.calibration` |
| **Source** | `crdt_merge/model/strategies/calibration.py` |
| **Category** | Post-Calibration |
| **Paper** | 2024 — Weight Distribution Scope Alignment |
| **CRDT props** | `{"commutative": true, "associative": false, "idempotent": true}` |
| **Constructor** | `(self, /, *args, **kwargs)` |
| **merge()** | `(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` |
| **Source lines** | 166 |

**Methods**: `category`, `crdt_properties`, `crdt_tier`, `merge`, `name`, `paper_reference`, `verify_crdt`

---

