# Model Merging Recipes

Complete cookbook with working recipes for all 26 merge strategies. Organized by category.

---

## Basic Strategies

### Recipe 1: Linear Interpolation (`linear`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "linear"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}

result = merger.merge([model_a, model_b])
print(result.tensor)
# {'layer1.weight': [2.0, 3.0], 'layer1.bias': [0.2, 0.3]}
```

---

### Recipe 2: Spherical Linear Interpolation (`slerp`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "slerp"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 0.0], "layer2.weight": [0.0, 1.0]}
model_b = {"layer1.weight": [0.0, 1.0], "layer2.weight": [1.0, 0.0]}

# SLERP interpolates along the great-circle arc
result = merger.merge([model_a, model_b], weights=[0.5, 0.5])
print(result.tensor)
```

---

### Recipe 3: Weighted Average (`weight_average`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "weight_average"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}
model_c = {"layer1.weight": [5.0, 6.0], "layer1.bias": [0.5, 0.6]}

result = merger.merge(
    [model_a, model_b, model_c],
    weights=[0.5, 0.3, 0.2],
)
print(result.tensor)
# {'layer1.weight': [2.4, 3.4], 'layer1.bias': [0.24, 0.34]}
```

---

### Recipe 4: Task Arithmetic (`task_arithmetic`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "task_arithmetic"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
task_a_model = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
task_b_model = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Combines task vectors: base + (task_a - base) + (task_b - base)
result = merger.merge(
    [task_a_model, task_b_model],
    base_model=base_model,
)
print(result.tensor)
# {'layer1.weight': [1.8, 2.8], 'layer1.bias': [0.17, 0.27]}
```

---

## Subspace / Sparsification Strategies

### Recipe 5: TIES Merge (`ties`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "ties"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Trim-Elect-Sign merge resolves sign conflicts in task vectors
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 6: DARE — Drop and Rescale (`dare`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "dare"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Randomly drops delta parameters and rescales survivors
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 7: DARE-TIES Hybrid (`dare_ties`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "dare_ties"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Combines DARE dropout with TIES sign election
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 8: DELLA — Drop Elect Low-Rank Approximate (`della`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "della"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Extends DARE-TIES with low-rank reconstruction
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 9: EMR — Elect Mask Rescale (`emr`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "emr"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Partitions into shared/task-specific params with distinct rescaling
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 10: Model Breadcrumbs (`model_breadcrumbs`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "model_breadcrumbs"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Retains only the most important "breadcrumb" parameters
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 11: AdaRank — Adaptive Rank Pruning (`adarank`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "adarank"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Adaptively selects rank per weight matrix during merge
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 12: STAR — Spectral Truncation Adaptive Rescaling (`star`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "star"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Truncates spectrum of task vectors and rescales
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

### Recipe 13: SVD Knot Tying (`svd_knot_tying`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "svd_knot_tying"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.8, 2.6], "layer1.bias": [0.18, 0.26]}
model_b = {"layer1.weight": [1.4, 2.4], "layer1.bias": [0.14, 0.24]}

# Aligns SVD subspaces of task vectors before merging
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
)
print(result.tensor)
```

---

## Weighted / Importance Strategies

### Recipe 14: Fisher Merge (`fisher_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "fisher_merge"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}

# Weights parameters by Fisher information (importance)
result = merger.merge(
    [model_a, model_b],
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

### Recipe 15: Adaptive Merging — AdaMerging (`ada_merging`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "ada_merging"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}
model_c = {"layer1.weight": [5.0, 6.0], "layer1.bias": [0.5, 0.6]}

# Learns per-layer coefficients via entropy minimization
result = merger.merge(
    [model_a, model_b, model_c],
    weights=[0.4, 0.35, 0.25],
)
print(result.tensor)
```

---

### Recipe 16: Differentiable Adaptive Merging — DAM (`dam`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "dam"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}

# End-to-end differentiable coefficient optimization
result = merger.merge(
    [model_a, model_b],
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

### Recipe 17: Regression Mean (`regression_mean`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "regression_mean"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}

# Regression-optimal mean that minimizes expected prediction error
result = merger.merge(
    [model_a, model_b],
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

## Evolutionary Strategies

### Recipe 18: Evolutionary Merge (`evolutionary_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "evolutionary_merge"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}
model_c = {"layer1.weight": [5.0, 6.0], "layer1.bias": [0.5, 0.6]}

# CMA-ES optimizes layer-wise merge coefficients against a fitness fn
result = merger.merge(
    [model_a, model_b, model_c],
    weights=[0.33, 0.33, 0.34],
)
print(result.tensor)
```

---

### Recipe 19: Genetic Merge (`genetic_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "genetic_merge"})
merger = ModelMerge(schema)

model_a = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_b = {"layer1.weight": [3.0, 4.0], "layer1.bias": [0.3, 0.4]}

# Genetic crossover + mutation to evolve merge recipes
result = merger.merge(
    [model_a, model_b],
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

## Safety-Aware Strategies

### Recipe 20: Safe Merge (`safe_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "safe_merge"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Detects and protects safety-critical layers during merge
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

### Recipe 21: LED — Layer-wise Evaluation-Driven Merge (`led_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "led_merge"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Evaluates each layer against safety benchmarks to adjust merge ratios
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

## Unlearning Strategies

### Recipe 22: Negative Merge (`negative_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "negative_merge"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
# Model fine-tuned on data we want to forget
forget_model = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.13, 0.23]}

# Subtracts the "forget" task vector to unlearn capabilities
result = merger.merge(
    [forget_model],
    base_model=base_model,
    weights=[-1.0],
)
print(result.tensor)
```

---

### Recipe 23: Split-Unlearn-Merge (`split_unlearn_merge`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "split_unlearn_merge"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
retain_model = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
forget_model = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.13, 0.23]}

# Splits into retain/forget, applies targeted unlearning, re-merges
result = merger.merge(
    [retain_model, forget_model],
    base_model=base_model,
)
print(result.tensor)
```

---

## Post-Calibration Strategies

### Recipe 24: Representation Surgery (`representation_surgery`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "representation_surgery"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Post-merge correction: realigns representations toward the base model
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

### Recipe 25: Weight Scope Alignment (`weight_scope_alignment`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "weight_scope_alignment"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Aligns weight distribution scope to correct magnitude drift
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

## Continual Learning Strategies

### Recipe 26: Dual Projection Merge (`dual_projection`)

```python
from crdt_merge.model import ModelMerge, ModelMergeSchema

schema = ModelMergeSchema.from_dict({"*": "dual_projection"})
merger = ModelMerge(schema)

base_model = {"layer1.weight": [1.0, 2.0], "layer1.bias": [0.1, 0.2]}
model_a = {"layer1.weight": [1.5, 2.5], "layer1.bias": [0.15, 0.25]}
model_b = {"layer1.weight": [1.3, 2.3], "layer1.bias": [0.12, 0.22]}

# Projects onto stable/plastic subspaces for knowledge preservation
# This is the only TRUE_CRDT strategy (commutative, associative, idempotent)
result = merger.merge(
    [model_a, model_b],
    base_model=base_model,
    weights=[0.5, 0.5],
)
print(result.tensor)
```

---

## Bonus: Safety-Checked Pipeline

```python
from crdt_merge.model import MergePipeline, SafetyAnalyzer

model_a = {"layer1.weight": [1.0, 2.0], "layer2.weight": [0.5, 0.5]}
model_b = {"layer1.weight": [3.0, 4.0], "layer2.weight": [0.6, 0.7]}
base = {"layer1.weight": [0.5, 1.0], "layer2.weight": [0.4, 0.4]}

# Run safety analysis before merging
analyzer = SafetyAnalyzer()
safety_layers = analyzer.detect_safety_layers(
    [model_a, model_b], base_model=base
)
report = analyzer.safety_report([model_a, model_b], base_model=base)
print(f"Risk score: {report.risk_score}")
print(f"Recommendation: {report.recommendation}")
print(f"Safety-critical layers: {safety_layers}")

# Build and execute a merge pipeline
pipeline = MergePipeline(stages=[
    {
        "name": "merge_step",
        "strategy": "linear",
        "models": [model_a, model_b],
    }
])

errors = pipeline.validate()
assert not errors, f"Pipeline validation failed: {errors}"

result = pipeline.execute()
print(result.final_model)
# {'layer1.weight': [2.0, 3.0], 'layer2.weight': [0.55, 0.6]}
```
