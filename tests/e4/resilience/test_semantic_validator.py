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

"""Tests for semantic validation (Okonkwo §7, Nair §13)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.semantic_validator import (
    MagnitudeValidator,
    StatisticalShiftDetector,
    ParameterRegionGuard,
    CompositeSemanticValidator,
    ValidationResult,
)


class TestMagnitudeValidator:
    def test_normal_values_pass(self):
        v = MagnitudeValidator(max_magnitude=10.0)
        result = v.validate({"a": 1.0, "b": 5.0}, "peer-1", 0.8)
        assert result.valid

    def test_extreme_values_fail(self):
        v = MagnitudeValidator(max_magnitude=10.0)
        result = v.validate({"a": 1000.0}, "peer-1", 0.8)
        assert not result.valid
        assert result.risk_score > 0

    def test_critical_region_stricter(self):
        v = MagnitudeValidator(max_magnitude=100.0, critical_regions={"attn."})
        result = v.validate({"attn.q": 20.0}, "peer-1", 0.8)
        assert not result.valid  # 20 > 100 * 0.1 = 10

    def test_non_numeric_ignored(self):
        v = MagnitudeValidator()
        result = v.validate({"a": "text", "b": None}, "peer-1", 0.8)
        assert result.valid


class TestStatisticalShiftDetector:
    def test_warmup_always_passes(self):
        d = StatisticalShiftDetector(warmup_samples=10)
        for _ in range(5):
            result = d.validate({"a": 1.0}, "peer-1", 0.8)
            assert result.valid

    def test_normal_distribution_passes(self):
        d = StatisticalShiftDetector(warmup_samples=5, shift_threshold=5.0)
        # Feed normal data
        for i in range(20):
            d.validate({f"k{j}": float(j) * 0.1 for j in range(10)}, "p", 0.8)
        result = d.validate({f"k{j}": float(j) * 0.1 for j in range(10)}, "p", 0.8)
        assert result.valid

    def test_extreme_shift_detected(self):
        d = StatisticalShiftDetector(warmup_samples=5, shift_threshold=2.0)
        # Establish baseline
        for _ in range(20):
            d.validate({f"k{j}": 1.0 for j in range(10)}, "p", 0.8)
        # Inject massive shift
        result = d.validate({f"k{j}": 1000.0 for j in range(10)}, "p", 0.8)
        assert not result.valid


class TestParameterRegionGuard:
    def test_unguarded_passes(self):
        g = ParameterRegionGuard()
        result = g.validate({"any.param": 100.0}, "peer-1", 0.8)
        assert result.valid

    def test_guarded_region_enforced(self):
        g = ParameterRegionGuard({"model.attention": 0.01})
        result = g.validate({"model.attention.q": 5.0}, "peer-1", 0.8)
        assert not result.valid

    def test_trust_scales_threshold(self):
        g = ParameterRegionGuard({"model.attn": 0.1})
        # High trust peer gets more lenient threshold
        result = g.validate({"model.attn.k": 0.15}, "peer-1", 0.9)
        assert result.valid  # 0.15 < 0.1 * (1 + 0.9) = 0.19

    def test_add_region(self):
        g = ParameterRegionGuard()
        g.add_region("embed", 0.001)
        assert g.region_count == 1


class TestCompositeSemanticValidator:
    def test_empty_passes(self):
        c = CompositeSemanticValidator()
        result = c.validate({"a": 1.0}, "peer", 0.8)
        assert result.valid

    def test_any_failure_fails_composite(self):
        c = CompositeSemanticValidator([
            MagnitudeValidator(max_magnitude=10.0),
            MagnitudeValidator(max_magnitude=0.5),  # This will fail
        ])
        result = c.validate({"a": 5.0}, "peer", 0.8)
        assert not result.valid

    def test_all_pass_passes(self):
        c = CompositeSemanticValidator([
            MagnitudeValidator(max_magnitude=100.0),
            ParameterRegionGuard(),
        ])
        result = c.validate({"a": 1.0}, "peer", 0.8)
        assert result.valid

    def test_escalation_propagates(self):
        c = CompositeSemanticValidator([
            MagnitudeValidator(max_magnitude=1.0),
        ])
        result = c.validate({"a": 100.0}, "peer", 0.8)
        assert result.escalate
