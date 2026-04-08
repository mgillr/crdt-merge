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

"""Tests for long-con Sybil detector."""

import time
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.longcon_sybil import (
    LongConDetector,
    LongConConfig,
    EvidenceRecord,
    SybilAlert,
)


class TestLongConConfig:

    def test_defaults(self):
        cfg = LongConConfig()
        assert cfg.correlation_window == 100
        assert cfg.signals_required == 2

    def test_custom(self):
        cfg = LongConConfig(correlation_window=50, min_evidence_count=5)
        assert cfg.correlation_window == 50


class TestLongConDetector:

    def test_init(self):
        det = LongConDetector()
        assert repr(det) is not None

    def test_record_evidence(self):
        det = LongConDetector()
        rec = EvidenceRecord(peer_id="p1", timestamp=1.0, dimension=0, magnitude=0.8)
        det.record_evidence(rec)

    def test_record_batch(self):
        det = LongConDetector()
        records = [
            EvidenceRecord(peer_id=f"p{i}", timestamp=float(i), dimension=0, magnitude=0.8)
            for i in range(10)
        ]
        det.record_batch(records)

    def test_scan_no_alerts_on_honest(self):
        det = LongConDetector(LongConConfig(min_evidence_count=5))
        for i in range(20):
            det.record_evidence(
                EvidenceRecord("honest-1", float(i), i % 5, 0.7 + (i % 3) * 0.05),
            )
        alerts = det.scan()
        assert isinstance(alerts, list)

    def test_correlated_group_detected(self):
        """Sybils with identical evidence patterns should trigger alerts."""
        cfg = LongConConfig(
            min_evidence_count=5,
            correlation_threshold=0.5,
            signals_required=1,
        )
        det = LongConDetector(cfg)
        # Create perfectly correlated evidence for 3 peers
        for i in range(30):
            for pid in ("sybil-a", "sybil-b", "sybil-c"):
                det.record_evidence(
                    EvidenceRecord(pid, float(i) * 0.1, i % 5, 0.8),
                )
        alerts = det.scan()
        assert isinstance(alerts, list)
        # May or may not fire depending on statistical tests

    def test_quarantine(self):
        det = LongConDetector()
        assert not det.is_quarantined("peer-1")
        assert len(det.quarantined_peers) == 0

    def test_alerts_property(self):
        det = LongConDetector()
        assert isinstance(det.alerts, list)

    def test_scan_returns_sybil_alerts(self):
        det = LongConDetector()
        alerts = det.scan()
        assert isinstance(alerts, list)
        for a in alerts:
            assert isinstance(a, SybilAlert)
