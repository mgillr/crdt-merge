# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Benchmarks for continual merge strategies.

Compares dual-projection merge against vanilla sequential merging in terms of
timing, stability retention, and CRDT convergence guarantees.

Example::

    from crdt_merge.model.continual_bench import ContinualBenchmark

    bench = ContinualBenchmark(layer_sizes=[128, 64])
    result = bench.run(n_models=5)
    print(result)

"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crdt_merge.model.continual import ContinualMerge
from crdt_merge.model.strategies.base import _get_np

__all__ = [
    "ContinualBenchmark",
    "BenchmarkResult",
    "StrategyBenchmark",
]


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class StrategyBenchmark:
    """Benchmark numbers for a single strategy.

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
    """

    strategy_name: str
    elapsed_seconds: float
    stability_scores: Dict[str, float] = field(default_factory=dict)
    converged: bool = False
    memory_bytes: int = 0


@dataclass
class BenchmarkResult:
    """Aggregate benchmark comparing multiple strategies.

    Attributes
    ----------
    n_models : int
        Number of models absorbed.
    layer_sizes : list[int]
        Size of each layer in the generated models.
    strategies : dict[str, StrategyBenchmark]
        Per-strategy benchmark data.
    """

    n_models: int
    layer_sizes: List[int]
    strategies: Dict[str, StrategyBenchmark] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary table."""
        lines = [
            f"ContinualBenchmark: {self.n_models} models, layers={self.layer_sizes}",
            f"{'Strategy':<25} {'Time (s)':<12} {'Converged':<12} {'Avg Stability':<15}",
            "-" * 64,
        ]
        for name, sb in sorted(self.strategies.items()):
            avg_stab = (
                sum(sb.stability_scores.values()) / len(sb.stability_scores)
                if sb.stability_scores
                else 0.0
            )
            lines.append(
                f"{name:<25} {sb.elapsed_seconds:<12.4f} "
                f"{str(sb.converged):<12} {avg_stab:<15.4f}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ContinualBenchmark
# ---------------------------------------------------------------------------

class ContinualBenchmark:
    """Benchmark continual merge against vanilla sequential merging.

    Parameters
    ----------
    layer_sizes : list[int] | None
        Size of each layer in generated models.  Default: ``[64, 32]``.
    """

    def __init__(self, layer_sizes: Optional[List[int]] = None) -> None:
        self._layer_sizes = layer_sizes or [64, 32]

    # ------------------------------------------------------------------
    # Model generation
    # ------------------------------------------------------------------

    def generate_models(
        self,
        n_models: int,
        seed: int = 42,
    ) -> List[dict]:
        """Generate synthetic model state dicts for benchmarking.

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
        """
        np = _get_np()
        models: List[dict] = []

        if np is not None:
            rng = np.random.RandomState(seed)  # nosec B311 -- seeded RNG for benchmarks
            for m in range(n_models):
                sd: dict = {}
                for i, size in enumerate(self._layer_sizes):
                    sd[f"layer_{i}"] = rng.randn(size).tolist()
                models.append(sd)
        else:
            # Pure-Python fallback using deterministic LCG
            import random
            rng = random.Random(seed)  # nosec B311 -- seeded RNG for benchmarks
            for m in range(n_models):
                sd = {}
                for i, size in enumerate(self._layer_sizes):
                    sd[f"layer_{i}"] = [rng.gauss(0, 1) for _ in range(size)]
                models.append(sd)

        return models

    # ------------------------------------------------------------------
    # Run benchmark
    # ------------------------------------------------------------------

    def run(self, n_models: int = 5) -> BenchmarkResult:
        """Run the full benchmark suite.

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
        """
        models = self.generate_models(n_models)
        base_model = self.generate_models(1, seed=0)[0]

        result = BenchmarkResult(
            n_models=n_models,
            layer_sizes=list(self._layer_sizes),
        )

        configs = [
            ("dual_projection+crdt", "dual_projection", "crdt"),
            ("weight_average", "weight_average", None),
            ("weight_average+crdt", "weight_average", "crdt"),
        ]

        for label, strategy, convergence in configs:
            sb = self._bench_one(base_model, models, strategy, convergence)
            sb.strategy_name = label
            result.strategies[label] = sb

        return result

    def _bench_one(
        self,
        base_model: dict,
        models: List[dict],
        strategy: str,
        convergence: Optional[str],
    ) -> StrategyBenchmark:
        """Benchmark a single strategy/convergence configuration."""
        cm = ContinualMerge(
            base_model=base_model,
            strategy=strategy,
            convergence=convergence,
        )

        t0 = time.perf_counter()
        for i, m in enumerate(models):
            cm.absorb(m, name=f"model_{i}")
        _ = cm.export()
        elapsed = time.perf_counter() - t0

        # Measure stability per model
        stability: Dict[str, float] = {}
        for i in range(len(models)):
            name = f"model_{i}"
            try:
                sr = cm.measure_stability(name)
                stability[name] = sr.retention
            except Exception:
                stability[name] = 0.0

        # Check convergence
        converged = cm.verify_convergence()

        # Memory estimate
        mem = sys.getsizeof(cm)

        return StrategyBenchmark(
            strategy_name=strategy,
            elapsed_seconds=elapsed,
            stability_scores=stability,
            converged=converged,
            memory_bytes=mem,
        )
