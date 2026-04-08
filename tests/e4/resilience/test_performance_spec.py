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

"""Tests for performance specifications (Vasquez §3, Tanaka §22-24)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.performance_spec import (
    SketchConfig, FanoutOptimizer, ProductionDeratingSpec, HardwareRequirements,
)


class TestSketchConfig:
    def test_default_target(self):
        sc = SketchConfig.for_target()
        assert sc.epsilon == 0.01
        assert sc.delta == 0.001
        assert sc.width > 0
        assert sc.depth > 0

    def test_memory_computed(self):
        sc = SketchConfig.for_target(0.01, 0.001)
        assert sc.memory_bytes == sc.width * sc.depth * 4

    def test_tighter_bounds_larger_sketch(self):
        loose = SketchConfig.for_target(0.1, 0.1)
        tight = SketchConfig.for_target(0.001, 0.0001)
        assert tight.width > loose.width
        assert tight.depth > loose.depth

    def test_for_scale_returns_config(self):
        for n in [100, 1000, 10000, 100000, 1000000]:
            sc = SketchConfig.for_scale(n)
            assert sc.width > 0
            assert sc.depth > 0

    def test_larger_scale_tighter_bounds(self):
        small = SketchConfig.for_scale(100)
        large = SketchConfig.for_scale(1000000)
        assert large.epsilon <= small.epsilon


class TestFanoutOptimizer:
    def test_single_peer(self):
        fo = FanoutOptimizer()
        cfg = fo.optimize(1)
        assert cfg.fan_out == 0

    def test_fan_out_scales_log(self):
        fo = FanoutOptimizer()
        c100 = fo.optimize(100)
        c10000 = fo.optimize(10000)
        assert c10000.fan_out > c100.fan_out

    def test_bandwidth_cap(self):
        # Min per-message = 128 + 4096 = 4224 bytes, so cap must be above that
        fo = FanoutOptimizer(max_bw_per_node=10000)
        cfg = fo.optimize(1000000)
        assert cfg.total_bw <= 10000
        # With very low cap, fan_out clamped to 1 (minimum)
        fo_low = FanoutOptimizer(max_bw_per_node=1000)
        cfg_low = fo_low.optimize(1000000)
        assert cfg_low.fan_out == 1  # Can't go lower

    def test_scale_report(self):
        fo = FanoutOptimizer()
        report = fo.scale_report()
        assert len(report) == 6  # Default 6 scale points


class TestProductionDeratingSpec:
    def test_default_derating(self):
        d = ProductionDeratingSpec()
        assert d.derate(100.0) == pytest.approx(40.0)

    def test_optimistic_higher_than_conservative(self):
        opt = ProductionDeratingSpec.optimistic()
        con = ProductionDeratingSpec.conservative()
        assert opt.overall > con.overall

    def test_category_derating(self):
        d = ProductionDeratingSpec()
        pco = d.derate(165000, "pco_build")
        assert pco == pytest.approx(165000 * 0.45)


class TestHardwareRequirements:
    def test_small_scale(self):
        hw = HardwareRequirements.for_scale(10)
        assert hw.cpu_cores >= 2
        assert hw.ram_gb >= 2

    def test_large_scale_more_resources(self):
        small = HardwareRequirements.for_scale(100)
        large = HardwareRequirements.for_scale(100000)
        assert large.cpu_cores >= small.cpu_cores
        assert large.ram_gb >= small.ram_gb

    def test_gpu_required_at_scale(self):
        hw = HardwareRequirements.for_scale(1000000)
        assert hw.gpu_required

    def test_scale_matrix(self):
        matrix = HardwareRequirements.scale_matrix()
        assert len(matrix) == 6
        # Should be monotonically increasing in cores
        cores = [h.cpu_cores for h in matrix]
        assert cores == sorted(cores)
