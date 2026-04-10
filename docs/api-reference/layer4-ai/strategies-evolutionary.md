# Evolutionary

> Evolutionary model-merge strategies.

**Source:** `crdt_merge/model/strategies/evolutionary.py`  
**Lines of Code:** 363

## Overview

Implements 2 strategies:

18. EvolutionaryMerge  — CMA-ES style population-based optimization
19. GeneticMerge       — Genetic algorithm with crossover/mutation

## Classes

### `EvolutionaryMerge(ModelMergeStrategy)`

Population-based optimization over merge weights (CMA-ES style).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

### `GeneticMerge(ModelMergeStrategy)`

Genetic algorithm merge with crossover and mutation (Mergenetic, 2025).

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `name` | `name() -> str` | — |
| `category` | `category() -> str` | — |
| `paper_reference` | `paper_reference() -> str` | — |
| `crdt_properties` | `crdt_properties() -> Dict[str, Any]` | — |
| `merge` | `merge(tensors: list, weights: Optional[List[float]] = None, base: Any = None, **kwargs: Any) -> Any` | — |

**Internal Methods:**

- `_tournament_select(population, fitnesses, rng, tournament_size)` — Tournament selection: pick best from random subset.

## Functions

### `_py_add()`

```python
_py_add(a: list, b: list) -> list
```

Defined in `crdt_merge/model/strategies/evolutionary.py`.

### `_py_scale()`

```python
_py_scale(a: list, s: float) -> list
```

Defined in `crdt_merge/model/strategies/evolutionary.py`.

### `_py_zeros()`

```python
_py_zeros(n: int) -> list
```

Defined in `crdt_merge/model/strategies/evolutionary.py`.

### `_flatten()`

```python
_flatten(arr: Any)
```

Flatten array-like to 1-D. Returns (flat, shape).

### `_unflatten()`

```python
_unflatten(flat: Any, shape)
```

Defined in `crdt_merge/model/strategies/evolutionary.py`.

### `_default_fitness()`

```python
_default_fitness(merged_flat, input_flats)
```

Default fitness: negative variance (higher = better, minimize variance).

### `_weighted_merge_py()`

```python
_weighted_merge_py(flats, coeffs)
```

Merge flat arrays with given coefficients (pure Python).


## Performance

### Expected Latency

Evolutionary and genetic strategies are **population-based optimization algorithms** — they evaluate many candidate merge-weight vectors across multiple generations. This makes them inherently slower than direct algebraic merges (e.g., `weight_average`, `slerp`, `ties`).

| Tensor Size | Population | Generations | Approx. Time | Notes |
|-------------|-----------|-------------|---------------|-------|
| 500 × 64 | 20 | 50 | ~5–8 s | Default parameters |
| 500 × 64 | 50 | 50 | ~15–20 s | Moderate population |
| 500 × 64 | 50+ | 100 | ~25 s+ | Typical for thorough search |
| 1000 × 128 | 20 | 50 | ~15–25 s | Larger tensors scale linearly with element count |

**~25 seconds on 500×64 tensors is expected** when `population_size > 50` and `generations ≥ 50`. The per-generation cost is O(population_size × tensor_elements) for fitness evaluation plus O(population_size × n_models) for the weighted merge of each candidate.

### Mitigation Strategies

1. **Reduce `population_size`**: Smaller populations converge faster. A population of 10–20 is often sufficient for ≤ 5 input models.

2. **Reduce `generations`**: Convergence typically occurs within the first 20–30 generations. Diminishing returns are common beyond 50 generations.

3. **Use smaller tensors**: If merging full model weights, consider merging per-layer or per-block rather than the full parameter tensor at once.

4. **Pre-compute merge weights**: For production inference pipelines, run the evolutionary search offline to find optimal coefficients, then apply those coefficients at runtime using the `weight_average` or `linear` strategy (sub-millisecond). This decouples the expensive search from the serving path.

5. **GPU acceleration**: When NumPy is available, evolutionary strategies operate on `ndarray` which can be swapped for CuPy or JAX arrays for GPU-accelerated fitness evaluation. See `crdt_merge.model.gpu` for the `GPUMerge` wrapper.

### Comparison with Other Strategy Families

| Family | Strategies | Approx. Time (500×64) | Deterministic? |
|--------|-----------|----------------------|---------------|
| Basic (algebraic) | weight_average, slerp, linear | < 1 ms | Yes |
| Subspace (sparsification) | ties, dare, della | 1–10 ms | Seed-dependent |
| Weighted (Fisher, regression) | fisher_merge, regression_mean | 5–50 ms | Yes |
| **Evolutionary** | **evolutionary_merge, genetic_merge** | **5–25 s** | **Seed-dependent** |

---

## Analysis Notes
