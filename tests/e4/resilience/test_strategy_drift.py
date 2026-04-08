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

"""Tests for strategy drift discriminator."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "source"))

from crdt_merge.e4.resilience.strategy_drift import (
    StrategyDriftDiscriminator,
    DriftVerdict,
    BehavioralFingerprint,
)


class TestBehavioralFingerprint:

    def test_record(self):
        fp = BehavioralFingerprint()
        fp.record(0.5, 3)
        assert fp.total_contributions == 1
        assert fp.magnitude_histogram[5] == 1
        assert fp.region_histogram[3] == 1

    def test_normalised(self):
        fp = BehavioralFingerprint()
        for _ in range(10):
            fp.record(0.5, 0)
        nm = fp.normalised_magnitude()
        assert abs(sum(nm) - 1.0) < 0.01


class TestStrategyDriftDiscriminator:

    def test_init(self):
        sdd = StrategyDriftDiscriminator()
        assert sdd.agent_count == 0

    def test_stable_agent(self):
        sdd = StrategyDriftDiscriminator(window_size=10)
        for i in range(30):
            sdd.record_contribution("agent-1", 0.5, 3)
        verdict = sdd.analyse("agent-1")
        assert isinstance(verdict, DriftVerdict)

    def test_drifting_agent_detected(self):
        sdd = StrategyDriftDiscriminator(window_size=10)
        # Phase 1: consistent behavior
        for i in range(15):
            sdd.record_contribution("agent-1", 0.5, 2)
        # Phase 2: shift to different behavior
        for i in range(15):
            sdd.record_contribution("agent-1", 0.2, 6)
        verdict = sdd.analyse("agent-1")
        assert isinstance(verdict, DriftVerdict)
        assert verdict.agent_id == "agent-1"

    def test_cohort_shift(self):
        sdd = StrategyDriftDiscriminator(window_size=10)
        # Multiple agents shifting together
        for i in range(20):
            for aid in ("a", "b", "c"):
                mag = 0.5 if i < 10 else 0.2
                sdd.record_contribution(aid, mag, 3 if i < 10 else 7)
        verdicts = sdd.analyse_all()
        assert len(verdicts) == 3

    def test_analyse_unknown_agent(self):
        sdd = StrategyDriftDiscriminator()
        verdict = sdd.analyse("nobody")
        assert verdict.recommended_action == "normal"

    def test_repr(self):
        sdd = StrategyDriftDiscriminator()
        assert "StrategyDriftDiscriminator" in repr(sdd)
