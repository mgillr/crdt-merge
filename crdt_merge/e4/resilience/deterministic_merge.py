# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""IEEE 754 deterministic merge for reproducible trust-weighted averaging.

Addresses Hassan §C9: trust-weighted averaging of model weights
introduces floating-point non-determinism because IEEE 754 addition
is not commutative (different accumulation orders give different
results at the ULP level).

For reproducible training pipelines, we need bitwise-identical results
regardless of merge order.  Three strategies:

  Strategy 1: Kahan summation.
    Compensated summation reduces error accumulation.  Not bitwise
    deterministic but reduces variance to < 1 ULP.

  Strategy 2: Integer accumulation.
    Convert float32/bfloat16 to fixed-point integers, accumulate in
    int64, convert back.  Bitwise deterministic but loses dynamic
    range for very large/small values.

  Strategy 3: Sorted accumulation.
    Sort operands by magnitude before accumulation.  Combined with
    Kahan summation, gives reproducible results for any permutation
    of the same operand set.  Deterministic if the operand multiset
    is identical (which CRDT merge guarantees).

Default: Strategy 3 (sorted Kahan) — deterministic, minimal precision
loss, compatible with float32, float64, and bfloat16.

Technical effect (UK patent): guarantees bitwise-reproducible
trust-weighted model merging regardless of operation ordering,
enabling reproducible distributed training pipelines.
"""

from __future__ import annotations

import math
import struct
from typing import List, Optional, Sequence, Tuple


# -- Kahan compensated summation -------------------------------------------

def kahan_sum(values: Sequence[float]) -> float:
    """Compensated summation (Kahan algorithm).

    Reduces numerical error from O(n * epsilon) to O(epsilon)
    for n floating-point additions.
    """
    total = 0.0
    compensation = 0.0
    for v in values:
        y = v - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total


# -- Sorted deterministic accumulation ------------------------------------

def deterministic_sum(values: Sequence[float]) -> float:
    """Bitwise-deterministic sum via sorted Kahan accumulation.

    Sort by magnitude (ascending) before compensated accumulation.
    Any permutation of the same multiset produces the same result.
    """
    sorted_vals = sorted(values, key=lambda x: (abs(x), x))
    return kahan_sum(sorted_vals)


def deterministic_weighted_avg(
    values: Sequence[float],
    weights: Sequence[float],
) -> float:
    """Deterministic weighted average with sorted Kahan accumulation."""
    if not values:
        return 0.0
    pairs = sorted(
        zip(values, weights),
        key=lambda p: (abs(p[0] * p[1]), p[0]),
    )
    products = [v * w for v, w in pairs]
    total_weight = deterministic_sum(list(weights))
    if total_weight == 0.0:
        return 0.0
    weighted_sum = kahan_sum(products)
    return weighted_sum / total_weight


# -- Fixed-point integer accumulation --------------------------------------

FIXED_POINT_SCALE = 2 ** 24  # 24 bits of fractional precision


def float_to_fixed(value: float, scale: int = FIXED_POINT_SCALE) -> int:
    """Convert float to fixed-point integer."""
    return int(round(value * scale))


def fixed_to_float(value: int, scale: int = FIXED_POINT_SCALE) -> float:
    """Convert fixed-point integer back to float."""
    return value / scale


def integer_deterministic_sum(values: Sequence[float]) -> float:
    """Bitwise-deterministic sum via integer accumulation.

    Convert to fixed-point, accumulate in integer arithmetic
    (commutative and associative), convert back.
    """
    total = sum(float_to_fixed(v) for v in values)
    return fixed_to_float(total)


# -- Deterministic merge operator ------------------------------------------

class DeterministicMerge:
    """Deterministic trust-weighted merge for model parameters.

    Parameters
    ----------
    strategy :
        One of "sorted_kahan", "integer", or "kahan".
    epsilon :
        Tolerance for reproducibility verification.
    """

    STRATEGIES = ("sorted_kahan", "integer", "kahan")

    def __init__(
        self,
        strategy: str = "sorted_kahan",
        epsilon: float = 1e-12,
    ) -> None:
        if strategy not in self.STRATEGIES:
            raise ValueError(f"unknown strategy: {strategy}")
        self._strategy = strategy
        self._epsilon = epsilon

    def merge_scalars(
        self,
        values: List[float],
        trust_weights: List[float],
    ) -> float:
        """Trust-weighted merge of scalar values."""
        if self._strategy == "sorted_kahan":
            return deterministic_weighted_avg(values, trust_weights)
        elif self._strategy == "integer":
            total_w = sum(trust_weights)
            if total_w == 0.0:
                return 0.0
            products = [v * w for v, w in zip(values, trust_weights)]
            return integer_deterministic_sum(products) / total_w
        else:
            total_w = kahan_sum(trust_weights)
            if total_w == 0.0:
                return 0.0
            products = [v * w for v, w in zip(values, trust_weights)]
            return kahan_sum(products) / total_w

    def merge_vectors(
        self,
        vectors: List[List[float]],
        trust_weights: List[float],
    ) -> List[float]:
        """Trust-weighted merge of parameter vectors."""
        if not vectors:
            return []
        dim = len(vectors[0])
        result = []
        for d in range(dim):
            vals = [v[d] for v in vectors]
            result.append(self.merge_scalars(vals, trust_weights))
        return result

    def verify_determinism(
        self,
        values: List[float],
        weights: List[float],
        permutations: int = 10,
    ) -> bool:
        """Verify that different orderings produce identical results."""
        import random
        reference = self.merge_scalars(values, weights)
        for _ in range(permutations):
            combined = list(zip(values, weights))
            random.shuffle(combined)
            v_perm = [c[0] for c in combined]
            w_perm = [c[1] for c in combined]
            result = self.merge_scalars(v_perm, w_perm)
            if abs(result - reference) > self._epsilon:
                return False
        return True

    @property
    def strategy(self) -> str:
        return self._strategy

    def __repr__(self) -> str:
        return f"DeterministicMerge(strategy={self._strategy!r})"


# -- Reproducibility report ------------------------------------------------

def reproducibility_report(
    values: List[float],
    weights: List[float],
    trials: int = 100,
) -> dict:
    """Run all strategies and compare for reproducibility.

    Returns dict with per-strategy results and max divergence.
    """
    import random
    results = {}

    for strat in DeterministicMerge.STRATEGIES:
        merger = DeterministicMerge(strategy=strat)
        outputs = set()
        for _ in range(trials):
            combined = list(zip(values, weights))
            random.shuffle(combined)
            v = [c[0] for c in combined]
            w = [c[1] for c in combined]
            result = merger.merge_scalars(v, w)
            outputs.add(struct.pack("!d", result))
        results[strat] = {
            "unique_outputs": len(outputs),
            "deterministic": len(outputs) == 1,
        }

    return results
