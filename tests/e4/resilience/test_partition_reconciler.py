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

"""Tests for post-partition trust reconciliation."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "source"))

from crdt_merge.e4.resilience.partition_reconciler import (
    PartitionReconciler,
    PartitionEvent,
)


class TestPartitionReconciler:

    def test_init(self):
        pr = PartitionReconciler()
        assert pr.active_reconciliations == 0

    def test_detect_partition_heal(self):
        pr = PartitionReconciler(detection_threshold=0.2)
        before = {"a", "b", "c"}
        after = {"a", "b", "c", "d", "e", "f"}
        trust = {"d": 0.5, "e": 0.5, "f": 0.5}
        event = pr.detect_partition_heal(
            before, after, trust, budget_before=3.0, budget_after=6.0,
        )
        assert event is not None
        assert isinstance(event, PartitionEvent)
        assert pr.active_reconciliations == 3

    def test_no_partition_if_below_threshold(self):
        pr = PartitionReconciler(detection_threshold=0.5)
        before = {"a", "b", "c", "d", "e"}
        after = {"a", "b", "c", "d", "e", "f"}
        event = pr.detect_partition_heal(
            before, after, {"f": 0.5}, 5.0, 6.0,
        )
        assert event is None

    def test_grace_period(self):
        pr = PartitionReconciler(grace_rounds=5, evidence_boost=2.0)
        before = {"a"}
        after = {"a", "b", "c", "d"}
        pr.detect_partition_heal(before, after, {"b": 0.5, "c": 0.5, "d": 0.5}, 1.0, 4.0)

        # During grace period, multiplier > 1
        assert pr.get_evidence_multiplier("b") > 1.0

        # Advance through grace
        for _ in range(5):
            pr.advance_round()

        # After grace, multiplier = 1.0
        assert abs(pr.get_evidence_multiplier("b") - 1.0) < 0.01

    def test_normalisation_budget_gradual(self):
        pr = PartitionReconciler(grace_rounds=10)
        before = {"a"}
        after = {"a", "b", "c", "d", "e"}
        pr.detect_partition_heal(
            before, after,
            {p: 0.5 for p in "bcde"},
            budget_before=1.0,
            budget_after=5.0,
        )
        # At start of grace, budget should be close to pre-merge
        budget = pr.get_normalisation_budget("b", 5.0)
        assert budget < 5.0
        assert budget >= 1.0

    def test_cleanup(self):
        pr = PartitionReconciler(grace_rounds=2)
        before = {"a"}
        after = {"a", "b"}
        pr.detect_partition_heal(before, after, {"b": 0.5}, 1.0, 2.0)
        pr.advance_round()
        pr.advance_round()
        removed = pr.cleanup_completed()
        assert removed == 1
        assert pr.active_reconciliations == 0

    def test_is_reconciling(self):
        pr = PartitionReconciler(grace_rounds=3)
        before = {"a"}
        after = {"a", "b"}
        pr.detect_partition_heal(before, after, {"b": 0.5}, 1.0, 2.0)
        assert pr.is_reconciling("b")
        assert not pr.is_reconciling("a")
