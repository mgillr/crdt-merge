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

"""Tests for non-IID convergence analyser."""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.noniid_convergence import (
    TrustConvergenceAnalyser,
    HeterogeneityProfile,
    ConvergenceBound,
    WarmupSchedule,
    dirichlet_skew,
)


class TestHeterogeneityProfile:

    def test_iid(self):
        p = HeterogeneityProfile(peer_count=10, label_skew=1.0, volume_skew=1.0)
        assert "iid" in p.regime.lower() or p.regime in ("iid", "mild", "moderate")

    def test_severe_skew(self):
        p = HeterogeneityProfile(peer_count=10, label_skew=0.1, volume_skew=5.0)
        assert "severe" in p.regime.lower() or "extreme" in p.regime.lower()


class TestTrustConvergenceAnalyser:

    def test_init(self):
        a = TrustConvergenceAnalyser()
        assert a is not None

    def test_convergence_bound_iid(self):
        a = TrustConvergenceAnalyser()
        profile = HeterogeneityProfile(peer_count=10, label_skew=1.0, volume_skew=1.0)
        bound = a.convergence_bound(profile, target_trust=0.8)
        assert isinstance(bound, ConvergenceBound)
        assert bound.rounds_to_converge > 0

    def test_convergence_bound_noniid(self):
        a = TrustConvergenceAnalyser()
        profile = HeterogeneityProfile(peer_count=10, label_skew=0.2, volume_skew=3.0)
        bound = a.convergence_bound(profile)
        assert isinstance(bound, ConvergenceBound)

    def test_severe_takes_longer(self):
        a = TrustConvergenceAnalyser()
        mild = HeterogeneityProfile(peer_count=10, label_skew=0.8, volume_skew=1.2)
        severe = HeterogeneityProfile(peer_count=10, label_skew=0.1, volume_skew=5.0)
        b1 = a.convergence_bound(mild)
        b2 = a.convergence_bound(severe)
        assert b2.rounds_to_converge >= b1.rounds_to_converge

    def test_convergence_trajectory(self):
        a = TrustConvergenceAnalyser()
        profile = HeterogeneityProfile(peer_count=5, label_skew=0.5, volume_skew=2.0)
        traj = a.convergence_trajectory(profile, rounds=20)
        # Returns rounds+1 entries (0 through rounds inclusive)
        assert len(traj) == 21
        # Each entry is (round, trust, loss)
        assert len(traj[0]) == 3

    def test_recommend_warmup(self):
        a = TrustConvergenceAnalyser()
        profile = HeterogeneityProfile(peer_count=10, label_skew=0.3, volume_skew=3.0)
        warmup = a.recommend_warmup(profile)
        assert isinstance(warmup, WarmupSchedule)


class TestWarmupSchedule:

    def test_apply(self):
        ws = WarmupSchedule(boost_rounds=10, evidence_multiplier=2.0, threshold_reduction=0.1)
        w = ws.apply(current_round=5, evidence_weight=1.0)
        assert w > 1.0  # boosted during warmup

    def test_no_boost_after_warmup(self):
        ws = WarmupSchedule(boost_rounds=10, evidence_multiplier=2.0, threshold_reduction=0.1)
        w = ws.apply(current_round=15, evidence_weight=1.0)
        assert w == 1.0

    def test_active(self):
        ws = WarmupSchedule(boost_rounds=10, evidence_multiplier=2.0, threshold_reduction=0.1)
        assert ws.active is True
        ws0 = WarmupSchedule(boost_rounds=0, evidence_multiplier=1.0, threshold_reduction=0.0)
        assert ws0.active is False


class TestDirichletSkew:

    def test_uniform_high_alpha(self):
        # High alpha → near-IID → label_skew close to 1.0
        skew = dirichlet_skew(alpha=100.0, num_peers=10, num_classes=10)
        assert skew > 0.5

    def test_concentrated_low_alpha(self):
        skew = dirichlet_skew(alpha=0.01, num_peers=10, num_classes=10)
        assert skew < 0.5
