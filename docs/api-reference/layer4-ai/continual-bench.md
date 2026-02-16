# `crdt_merge/model/continual_bench.py`

> Benchmarks for continual merge strategies.

Compares dual-projection merge against vanilla sequential merging in terms of
timing, stability retention, and CRDT convergence guarantees.

Example::

    from crdt_merge.model.continual_bench import ContinualBenchmark

    bench = ContinualBenchmark(laye

**Source:** `crdt_merge/model/continual_bench.py` | **Lines:** 268

---

**Exports (`__all__`):** `['ContinualBenchmark', 'BenchmarkResult', 'StrategyBenchmark']`

## Classes

### `class StrategyBenchmark`

Benchmark numbers for a single strategy.

    Attributes
    ----------
    strategy_name : str
        Name of the strategy.
    elapsed_seconds : float
        Wall-clock time to absorb all models and export.
    stability_scores : dict[str, float]
        Per-model retention scores (cosine similarity of task vectors).
    converged : bool
        Whether CRDT convergence was verified.
    memory_bytes : int
        Approximate memory footprint of the ContinualMerge object.

- `strategy_name`: `str`
- `elapsed_seconds`: `float`
- `stability_scores`: `Dict[str, float]`
- `converged`: `bool`
- `memory_bytes`: `int`

### `class BenchmarkResult`

Aggregate benchmark comparing multiple strategies.

    Attributes
    ----------
    n_models : int
        Number of models absorbed.
    layer_sizes : list[int]
        Size of each layer in the generated models.
    strategies : dict[str, StrategyBenchmark]
        Per-strategy benchmark data.

- `n_models`: `int`
- `layer_sizes`: `List[int]`
- `strategies`: `Dict[str, StrategyBenchmark]`

**Methods:**

#### `BenchmarkResult.summary(self) → str`

Human-readable summary table.


### `class ContinualBenchmark`

Benchmark continual merge against vanilla sequential merging.

    Parameters
    ----------
    layer_sizes : list[int] | None
        Size of each layer in generated models.  Default: ``[64, 32]``.


**Methods:**

#### `ContinualBenchmark.__init__(self, layer_sizes: Optional[List[int]] = None) → None`

*No docstring*

#### `ContinualBenchmark.generate_models(self, n_models: int, seed: int = 42) → List[dict]`

Generate synthetic model state dicts for benchmarking.

        Each model is a dict of ``layer_i`` → list of floats, where
        values are drawn from a seeded PRNG to be reproducible.

        Parameters
        ----------
        n_models : int
            Number of models to generate.
        seed : int
            Random seed for reproducibility.

        Returns
        -------
        list[dict]
            List of model state dicts.

#### `ContinualBenchmark.run(self, n_models: int = 5) → BenchmarkResult`

Run the full benchmark suite.

        Compares three configurations:

        1. ``dual_projection`` with ``convergence="crdt"``
        2. ``weight_average`` (classic mode, no CRDT)
        3. ``weight_average`` with ``convergence="crdt"``

        Parameters
        ----------
        n_models : int
            Number of models to absorb in each run.

        Returns
        -------
        BenchmarkResult

#### `ContinualBenchmark._bench_one(self, base_model: dict, models: List[dict], strategy: str, convergence: Optional[str]) → StrategyBenchmark`

Benchmark a single strategy/convergence configuration.


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 87.5%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
