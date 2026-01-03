# SPDX-License-Identifier: BUSL-1.1
#
# Copyright 2026 Ryan Gillespie
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Evolutionary model-merge strategies.

Implements 2 strategies:

18. EvolutionaryMerge  — CMA-ES style population-based optimization
19. GeneticMerge       — Genetic algorithm with crossover/mutation
"""

from __future__ import annotations

import math
import random as _random_module
from typing import Any, Callable, Dict, List, Optional

from crdt_merge.model.strategies import register_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _from_array,
    _get_np,
    _normalize_weights,
    _to_array,
)


# ---------------------------------------------------------------------------
# Pure-Python vector helpers
# ---------------------------------------------------------------------------

def _py_add(a: list, b: list) -> list:
    return [x + y for x, y in zip(a, b)]


def _py_scale(a: list, s: float) -> list:
    return [x * s for x in a]


def _py_zeros(n: int) -> list:
    return [0.0] * n


def _flatten(arr: Any):
    """Flatten array-like to 1-D. Returns (flat, shape)."""
    np = _get_np()
    if np is not None and isinstance(arr, np.ndarray):
        return arr.ravel().astype(float), arr.shape
    if isinstance(arr, list) and arr and isinstance(arr[0], list):
        flat: list = []
        rows = len(arr)
        cols = len(arr[0]) if arr else 0
        for row in arr:
            flat.extend(row)
        return flat, (rows, cols)
    if isinstance(arr, list):
        return [float(x) for x in arr], None
    return arr, None


def _unflatten(flat: Any, shape):
    if shape is None:
        return flat
    np = _get_np()
    if np is not None and isinstance(flat, np.ndarray):
        return flat.reshape(shape)
    if isinstance(shape, tuple) and len(shape) == 2:
        rows, cols = shape
        return [flat[i * cols:(i + 1) * cols] for i in range(rows)]
    return flat


def _default_fitness(merged_flat, input_flats):
    """Default fitness: negative variance (higher = better, minimize variance)."""
    d = len(merged_flat)
    if d == 0:
        return 0.0
    mean_val = sum(merged_flat) / d
    variance = sum((x - mean_val) ** 2 for x in merged_flat) / d
    return -variance


def _weighted_merge_py(flats, coeffs):
    """Merge flat arrays with given coefficients (pure Python)."""
    d = len(flats[0])
    result = _py_zeros(d)
    for c, flat in zip(coeffs, flats):
        result = _py_add(result, _py_scale(flat, c))
    return result


# ===================================================================
# 18. EvolutionaryMerge (CMA-ES style)
# ===================================================================

@register_strategy("evolutionary_merge")
class EvolutionaryMerge(ModelMergeStrategy):
    """Population-based optimization over merge weights (CMA-ES style).

    Sakana AI, 2024; M2N2 (GECCO 2025).

    Evolves a population of coefficient vectors, selecting the
    best-fitness merge. Default fitness optimizes for minimum variance.
    """

    @property
    def name(self) -> str:
        return "evolutionary_merge"

    @property
    def category(self) -> str:
        return "Evolutionary"

    @property
    def paper_reference(self) -> str:
        return "Sakana AI, 2024; M2N2 (GECCO 2025)"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        population_size: int = kwargs.get("population_size", 20)
        generations: int = kwargs.get("generations", 50)
        fitness_fn: Optional[Callable] = kwargs.get("fitness_fn", None)
        seed: int = kwargs.get("seed", 42)
        original = tensors[0]
        np = _get_np()

        rng = _random_module.Random(seed)
        arrays = [_to_array(t) for t in tensors]
        n = len(arrays)

        # Flatten for computation
        flats = []
        shape = None
        for a in arrays:
            flat, s = _flatten(a)
            flats.append(flat)
            if shape is None:
                shape = s

        d = len(flats[0])

        # Initialize population: random coefficient vectors
        population = []
        for _ in range(population_size):
            coeffs = [rng.gauss(1.0 / n, 0.3) for _ in range(n)]
            # Normalize to sum to 1
            total = sum(abs(c) for c in coeffs)
            if total > 0:
                coeffs = [max(0.0, c) / total for c in coeffs]
            else:
                coeffs = [1.0 / n] * n
            population.append(coeffs)

        # Always include uniform
        population[0] = [1.0 / n] * n

        best_coeffs = population[0]
        best_fitness = float("-inf")

        for gen in range(generations):
            fitnesses = []
            for coeffs in population:
                merged = _weighted_merge_py(flats, coeffs)
                if fitness_fn is not None:
                    fit = fitness_fn(merged)
                else:
                    fit = _default_fitness(merged, flats)
                fitnesses.append(fit)

            # Find best
            for i, fit in enumerate(fitnesses):
                if fit > best_fitness:
                    best_fitness = fit
                    best_coeffs = population[i][:]

            # Select top half
            ranked = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)
            elite = [population[ranked[i]][:] for i in range(max(1, population_size // 2))]

            # Generate new population via mutation
            new_population = [best_coeffs[:]]  # Keep best
            while len(new_population) < population_size:
                parent = elite[rng.randint(0, len(elite) - 1)]
                child = [max(0.0, c + rng.gauss(0, 0.1)) for c in parent]
                total = sum(child)
                if total > 0:
                    child = [c / total for c in child]
                else:
                    child = [1.0 / n] * n
                new_population.append(child)

            population = new_population

        # Final merge with best coefficients
        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]
            result = sum(c * a for c, a in zip(best_coeffs, arrs))
            return _from_array(result, original)
        else:
            result = _weighted_merge_py(flats, best_coeffs)
            result = _unflatten(result, shape)
            return _from_array(result, original)


# ===================================================================
# 19. GeneticMerge
# ===================================================================

@register_strategy("genetic_merge")
class GeneticMerge(ModelMergeStrategy):
    """Genetic algorithm merge with crossover and mutation (Mergenetic, 2025).

    Chromosome = weight vector. Uses uniform crossover, Gaussian
    mutation, and tournament selection.
    """

    @property
    def name(self) -> str:
        return "genetic_merge"

    @property
    def category(self) -> str:
        return "Evolutionary"

    @property
    def paper_reference(self) -> str:
        return "Mergenetic library, 2025"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": True}

    def merge(
        self,
        tensors: list,
        weights: Optional[List[float]] = None,
        base: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not tensors:
            return []
        if len(tensors) == 1:
            return tensors[0]

        population_size: int = kwargs.get("population_size", 20)
        generations: int = kwargs.get("generations", 50)
        mutation_rate: float = kwargs.get("mutation_rate", 0.1)
        fitness_fn: Optional[Callable] = kwargs.get("fitness_fn", None)
        seed: int = kwargs.get("seed", 42)
        original = tensors[0]
        np = _get_np()

        rng = _random_module.Random(seed)
        arrays = [_to_array(t) for t in tensors]
        n = len(arrays)

        # Flatten
        flats = []
        shape = None
        for a in arrays:
            flat, s = _flatten(a)
            flats.append(flat)
            if shape is None:
                shape = s

        d = len(flats[0])

        # Initialize population
        population = []
        for _ in range(population_size):
            coeffs = [rng.random() for _ in range(n)]
            total = sum(coeffs)
            if total > 0:
                coeffs = [c / total for c in coeffs]
            else:
                coeffs = [1.0 / n] * n
            population.append(coeffs)

        # Include uniform
        population[0] = [1.0 / n] * n

        best_coeffs = population[0]
        best_fitness = float("-inf")

        for gen in range(generations):
            # Evaluate fitness
            fitnesses = []
            for coeffs in population:
                merged = _weighted_merge_py(flats, coeffs)
                if fitness_fn is not None:
                    fit = fitness_fn(merged)
                else:
                    fit = _default_fitness(merged, flats)
                fitnesses.append(fit)

            # Update best
            for i, fit in enumerate(fitnesses):
                if fit > best_fitness:
                    best_fitness = fit
                    best_coeffs = population[i][:]

            # Tournament selection + crossover + mutation
            new_population = [best_coeffs[:]]  # Elitism

            while len(new_population) < population_size:
                # Tournament selection (size 3)
                parent1 = self._tournament_select(population, fitnesses, rng, 3)
                parent2 = self._tournament_select(population, fitnesses, rng, 3)

                # Uniform crossover
                child = []
                for g1, g2 in zip(parent1, parent2):
                    child.append(g1 if rng.random() < 0.5 else g2)

                # Gaussian mutation
                child = [max(0.0, c + rng.gauss(0, mutation_rate)) if rng.random() < mutation_rate else c
                         for c in child]

                # Normalize
                total = sum(child)
                if total > 0:
                    child = [c / total for c in child]
                else:
                    child = [1.0 / n] * n

                new_population.append(child)

            population = new_population

        # Final merge with best coefficients
        if np is not None and isinstance(arrays[0], np.ndarray):
            arrs = [a.astype(float) for a in arrays]
            result = sum(c * a for c, a in zip(best_coeffs, arrs))
            return _from_array(result, original)
        else:
            result = _weighted_merge_py(flats, best_coeffs)
            result = _unflatten(result, shape)
            return _from_array(result, original)

    @staticmethod
    def _tournament_select(population, fitnesses, rng, tournament_size):
        """Tournament selection: pick best from random subset."""
        indices = [rng.randint(0, len(population) - 1) for _ in range(tournament_size)]
        best_idx = max(indices, key=lambda i: fitnesses[i])
        return population[best_idx][:]
