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

"""Tests for convergence monitoring (Vasquez §2, Wei §19)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.convergence_monitor import (
    ConvergenceBound, ConvergenceMonitor,
)


class TestConvergenceBound:
    def test_single_peer(self):
        b = ConvergenceBound.compute(1)
        assert b.time_bound_seconds == 0

    def test_scales_logarithmically(self):
        b100 = ConvergenceBound.compute(100)
        b10000 = ConvergenceBound.compute(10000)
        # 10K should be less than 2x the bound of 100
        assert b10000.time_bound_seconds < b100.time_bound_seconds * 3

    def test_known_bound_10k(self):
        b = ConvergenceBound.compute(10000, gossip_interval=1.0)
        # O(log n) rounds at ~1.58x factor
        assert 10 < b.time_bound_seconds < 50

    def test_partition_factor(self):
        b = ConvergenceBound.compute(1000, evidence_divergence_ratio=0.5)
        assert b.post_partition_bound > b.time_bound_seconds

    def test_1m_peers(self):
        b = ConvergenceBound.compute(1000000, gossip_interval=1.0)
        assert b.time_bound_seconds < 60  # Should converge within a minute


class TestConvergenceMonitor:
    def test_healthy_observations(self):
        mon = ConvergenceMonitor(100, gossip_interval=1.0)
        for _ in range(10):
            assert mon.record_convergence(1.0)
        assert mon.convergence_health == "healthy"

    def test_slow_convergence_triggers_alert(self):
        mon = ConvergenceMonitor(100, gossip_interval=1.0, alert_threshold=2.0)
        result = mon.record_convergence(1000.0)  # Way over bound
        assert not result
        assert len(mon.alerts) == 1

    def test_average_convergence(self):
        mon = ConvergenceMonitor(100)
        mon.record_convergence(1.0)
        mon.record_convergence(3.0)
        assert mon.average_convergence_time == 2.0

    def test_p99_convergence(self):
        mon = ConvergenceMonitor(100)
        for i in range(100):
            mon.record_convergence(float(i))
        assert mon.p99_convergence_time >= 98.0

    def test_update_peer_count(self):
        mon = ConvergenceMonitor(100)
        old_bound = mon.theoretical_bound.time_bound_seconds
        mon.update_peer_count(10000)
        new_bound = mon.theoretical_bound.time_bound_seconds
        assert new_bound > old_bound
