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

"""Tests for epoch coordination protocol (Vasquez §1, Wei §20)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.epoch_protocol import (
    EpochManager, EpochState, EpochTransition,
)


class TestEpochState:
    def test_initial_state(self):
        state = EpochState(0)
        assert state.current_epoch == 0

    def test_advance(self):
        state = EpochState(0)
        t = state.advance()
        assert t.from_epoch == 0
        assert t.to_epoch == 1
        assert state.current_epoch == 1

    def test_merge_takes_max(self):
        s1 = EpochState(5)
        s2 = EpochState(10)
        merged = s1.merge(s2)
        assert merged.current_epoch == 10

    def test_merge_commutative(self):
        s1 = EpochState(5)
        s2 = EpochState(10)
        assert s1.merge(s2).current_epoch == s2.merge(s1).current_epoch

    def test_merge_idempotent(self):
        s1 = EpochState(5)
        assert s1.merge(s1).current_epoch == 5

    def test_evidence_gc(self):
        state = EpochState(0, retention_epochs=2)
        for i in range(5):
            state.record_evidence(i)
            state.advance()
        pruned = state.prune()
        assert pruned > 0

    def test_prunable_epochs(self):
        state = EpochState(10, retention_epochs=3)
        for e in range(11):
            state.record_evidence(e)
        prunable = state.prunable_epochs()
        assert all(e < 7 for e in prunable)

    def test_evidence_validity_check(self):
        state = EpochState(10, retention_epochs=3)
        assert state.is_evidence_valid(8)
        assert state.is_evidence_valid(10)
        assert not state.is_evidence_valid(6)


class TestEpochManager:
    def test_initialization(self):
        em = EpochManager("peer-1")
        assert em.current_epoch == 0

    def test_force_advance(self):
        em = EpochManager("peer-1")
        t = em.force_advance()
        assert t.to_epoch == 1
        assert em.current_epoch == 1

    def test_evidence_recording(self):
        em = EpochManager("peer-1", max_evidence_per_epoch=5)
        for _ in range(4):
            em.record_evidence()
        assert not em.should_advance()
        em.record_evidence()
        assert em.should_advance()

    def test_partition_strategy_fast_forward(self):
        em = EpochManager("peer-1")
        assert em.partition_resolution_strategy(5, 6) == "fast_forward"

    def test_partition_strategy_quarantine(self):
        em = EpochManager("peer-1")
        assert em.partition_resolution_strategy(5, 100) == "quarantine"

    def test_gc_evidence(self):
        em = EpochManager("peer-1")
        for _ in range(10):
            em.record_evidence()
            em.force_advance()
        pruned = em.gc_evidence()
        assert pruned >= 0

    def test_merge_remote_epoch(self):
        em = EpochManager("peer-1")
        remote = EpochState(10)
        t = em.merge_remote_epoch(remote)
        assert em.current_epoch == 10
