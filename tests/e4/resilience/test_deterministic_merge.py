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

"""Tests for deterministic merge operator."""

import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "source"))

from crdt_merge.e4.resilience.deterministic_merge import (
    DeterministicMerge,
    deterministic_sum,
    kahan_sum,
    integer_deterministic_sum,
    reproducibility_report,
)


class TestKahanSum:

    def test_basic_sum(self):
        assert abs(kahan_sum([1.0, 2.0, 3.0]) - 6.0) < 1e-15

    def test_catastrophic_cancellation(self):
        """Kahan should handle values where naive sum loses precision."""
        vals = [1.0] + [1e-16] * 10_000
        result = kahan_sum(vals)
        assert abs(result - (1.0 + 10_000 * 1e-16)) < 1e-14

    def test_empty(self):
        assert kahan_sum([]) == 0.0


class TestDeterministicSum:

    def test_order_independent(self):
        vals = [random.random() for _ in range(100)]
        result1 = deterministic_sum(vals)
        random.shuffle(vals)
        result2 = deterministic_sum(vals)
        assert result1 == result2

    def test_negative_values(self):
        vals = [-0.5, 0.3, -0.1, 0.8, -0.2]
        result = deterministic_sum(vals)
        assert abs(result - 0.3) < 1e-14


class TestIntegerDeterministicSum:

    def test_basic(self):
        result = integer_deterministic_sum([0.1, 0.2, 0.3])
        assert abs(result - 0.6) < 0.01

    def test_order_independent(self):
        vals = [random.random() for _ in range(50)]
        r1 = integer_deterministic_sum(vals)
        random.shuffle(vals)
        r2 = integer_deterministic_sum(vals)
        assert abs(r1 - r2) < 1e-6


class TestDeterministicMerge:

    def test_sorted_kahan_deterministic(self):
        merger = DeterministicMerge(strategy="sorted_kahan")
        vals = [0.3, 0.7, 0.1, 0.9, 0.5]
        weights = [0.2, 0.3, 0.1, 0.25, 0.15]
        assert merger.verify_determinism(vals, weights, permutations=20)

    def test_integer_deterministic(self):
        merger = DeterministicMerge(strategy="integer")
        vals = [0.3, 0.7, 0.1, 0.9, 0.5]
        weights = [0.2, 0.3, 0.1, 0.25, 0.15]
        assert merger.verify_determinism(vals, weights, permutations=20)

    def test_merge_vectors(self):
        merger = DeterministicMerge()
        vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        weights = [0.3, 0.3, 0.4]
        result = merger.merge_vectors(vectors, weights)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_empty_merge(self):
        merger = DeterministicMerge()
        assert merger.merge_scalars([], []) == 0.0
        assert merger.merge_vectors([], []) == []

    def test_all_strategies_valid(self):
        for strat in DeterministicMerge.STRATEGIES:
            merger = DeterministicMerge(strategy=strat)
            result = merger.merge_scalars([0.5, 0.7], [0.6, 0.4])
            assert 0.0 < result < 1.0

    def test_invalid_strategy_raises(self):
        try:
            DeterministicMerge(strategy="invalid")
            assert False, "should have raised"
        except ValueError:
            pass

    def test_reproducibility_report(self):
        report = reproducibility_report(
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.2, 0.2, 0.2, 0.2, 0.2],
            trials=50,
        )
        assert "sorted_kahan" in report
        assert report["sorted_kahan"]["deterministic"]
