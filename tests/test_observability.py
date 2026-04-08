# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.observability — metrics, health checks, and telemetry."""

import json
import os
import tempfile
import threading
import time

import pytest

from crdt_merge.observability import (
    HealthCheck,
    MergeMetric,
    MetricsCollector,
    ObservedMerge,
)
from crdt_merge.strategies import LWW, MaxWins, MergeSchema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collector():
    return MetricsCollector(node_id="test-node")


@pytest.fixture
def sample_left():
    return [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
    ]


@pytest.fixture
def sample_right():
    return [
        {"id": 1, "name": "Alicia", "age": 31},
        {"id": 3, "name": "Charlie", "age": 40},
    ]


# ---------------------------------------------------------------------------
# MergeMetric
# ---------------------------------------------------------------------------


class TestMergeMetric:
    def test_to_dict(self):
        m = MergeMetric(
            operation="merge",
            timestamp=1000.0,
            duration_ms=5.0,
            input_record_count=4,
            output_record_count=3,
            conflicts_detected=1,
            conflicts_resolved=1,
            strategy_used="LWW",
            node_id="n1",
        )
        d = m.to_dict()
        assert d["operation"] == "merge"
        assert d["duration_ms"] == 5.0
        assert d["conflicts_detected"] == 1

    def test_default_metadata(self):
        m = MergeMetric(operation="merge", timestamp=0, duration_ms=0)
        assert m.metadata == {}


# ---------------------------------------------------------------------------
# MetricsCollector — recording
# ---------------------------------------------------------------------------


class TestMetricsRecording:
    def test_record_merge(self, collector):
        m = collector.record_merge(
            left_count=10,
            right_count=5,
            result_count=12,
            duration_ms=3.5,
            strategy="LWW",
            conflicts=2,
        )
        assert m.operation == "merge"
        assert m.input_record_count == 15
        assert m.output_record_count == 12
        assert m.duration_ms == 3.5
        assert m.conflicts_detected == 2
        assert len(collector) == 1

    def test_record_operation(self, collector):
        m = collector.record_operation("encrypt", 1.2, input_record_count=5)
        assert m.operation == "encrypt"
        assert m.input_record_count == 5

    def test_record_error(self, collector):
        collector.record_error("merge", 10.0)
        summary = collector.get_summary()
        assert summary["total_errors"] == 1

    def test_len_and_iter(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        collector.record_merge(2, 2, 2, 2.0)
        assert len(collector) == 2
        items = list(collector)
        assert len(items) == 2


# ---------------------------------------------------------------------------
# MetricsCollector — querying
# ---------------------------------------------------------------------------


class TestMetricsQuerying:
    def test_filter_by_operation(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        collector.record_operation("encrypt", 2.0)
        assert len(collector.get_metrics(operation="merge")) == 1
        assert len(collector.get_metrics(operation="encrypt")) == 1

    def test_filter_by_since(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        cutoff = time.time() + 0.1
        time.sleep(0.15)
        collector.record_merge(1, 1, 1, 2.0)
        recent = collector.get_metrics(since=cutoff)
        assert len(recent) == 1

    def test_filter_by_limit(self, collector):
        for i in range(10):
            collector.record_merge(1, 1, 1, float(i))
        assert len(collector.get_metrics(limit=3)) == 3

    def test_empty_collector(self, collector):
        assert collector.get_metrics() == []
        assert len(collector) == 0


# ---------------------------------------------------------------------------
# MetricsCollector — summary
# ---------------------------------------------------------------------------


class TestMetricsSummary:
    def test_summary_values(self, collector):
        collector.record_merge(2, 3, 4, 10.0, conflicts=2)
        collector.record_merge(1, 1, 1, 20.0, conflicts=0)
        s = collector.get_summary()
        assert s["total_operations"] == 2
        assert s["avg_duration_ms"] == 15.0
        assert s["max_duration_ms"] == 20.0
        assert s["min_duration_ms"] == 10.0
        assert s["total_conflicts"] == 2
        assert s["total_input_records"] == 7
        assert s["total_output_records"] == 5

    def test_summary_empty(self, collector):
        s = collector.get_summary()
        assert s["total_operations"] == 0
        assert s["avg_duration_ms"] == 0.0

    def test_operations_by_type(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        collector.record_operation("encrypt", 1.0)
        s = collector.get_summary()
        assert s["operations_by_type"]["merge"] == 1
        assert s["operations_by_type"]["encrypt"] == 1


# ---------------------------------------------------------------------------
# MetricsCollector — reset and export
# ---------------------------------------------------------------------------


class TestResetAndExport:
    def test_reset(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        collector.reset()
        assert len(collector) == 0
        assert collector.get_summary()["total_operations"] == 0
        assert collector.get_summary()["total_errors"] == 0

    def test_export_json(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        payload = collector.export_metrics()
        data = json.loads(payload)
        assert len(data) == 1
        assert data[0]["operation"] == "merge"

    def test_export_to_file(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            collector.export_metrics(filepath=path)
            with open(path) as fh:
                data = json.load(fh)
            assert len(data) == 1
        finally:
            os.unlink(path)

    def test_json_roundtrip(self, collector):
        collector.record_merge(2, 3, 4, 5.5, strategy="LWW", conflicts=1)
        payload = collector.export_metrics()
        data = json.loads(payload)
        m = data[0]
        assert m["strategy_used"] == "LWW"
        assert m["conflicts_detected"] == 1


# ---------------------------------------------------------------------------
# Max history
# ---------------------------------------------------------------------------


class TestMaxHistory:
    def test_eviction(self):
        c = MetricsCollector(max_history=5)
        for i in range(10):
            c.record_merge(1, 1, 1, float(i))
        assert len(c) == 5
        metrics = c.get_metrics()
        # Oldest metrics evicted — remaining durations are 5..9
        durations = [m.duration_ms for m in metrics]
        assert durations == [5.0, 6.0, 7.0, 8.0, 9.0]


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_writes(self):
        c = MetricsCollector(max_history=50_000)
        errors = []

        def writer(n):
            try:
                for _ in range(500):
                    c.record_merge(1, 1, 1, 0.1)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(c) == 4000


# ---------------------------------------------------------------------------
# HealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_healthy(self, collector):
        collector.record_merge(1, 1, 1, 1.0)
        hc = HealthCheck(collector)
        report = hc.check_health()
        assert report["status"] == "healthy"

    def test_unhealthy_merge_time(self, collector):
        collector.record_merge(1, 1, 1, 10_000.0)
        hc = HealthCheck(collector)
        report = hc.check_health()
        assert report["status"] == "unhealthy"
        assert report["checks"]["avg_merge_time"]["status"] == "unhealthy"

    def test_degraded_merge_time(self, collector):
        # 80-100% of threshold → degraded
        collector.record_merge(1, 1, 1, 4500.0)
        hc = HealthCheck(collector)
        report = hc.check_health()
        assert report["status"] == "degraded"

    def test_unhealthy_error_rate(self):
        c = MetricsCollector()
        # 2 errors out of 10 = 20% > 5%
        for _ in range(8):
            c.record_merge(1, 1, 1, 1.0)
        for _ in range(2):
            c.record_error("merge", 1.0)
        hc = HealthCheck(c)
        report = hc.check_health()
        assert report["checks"]["error_rate"]["status"] == "unhealthy"

    def test_unhealthy_conflict_rate(self, collector):
        # Every merge has 5 conflicts → 5.0 conflict_rate > 0.5
        for _ in range(10):
            collector.record_merge(1, 1, 1, 1.0, conflicts=5)
        hc = HealthCheck(collector)
        report = hc.check_health()
        assert report["checks"]["conflict_rate"]["status"] == "unhealthy"

    def test_custom_thresholds(self, collector):
        collector.record_merge(1, 1, 1, 100.0)
        hc = HealthCheck(collector, thresholds={"merge_time_ms": 50.0})
        report = hc.check_health()
        assert report["checks"]["avg_merge_time"]["status"] == "unhealthy"

    def test_empty_collector_healthy(self, collector):
        hc = HealthCheck(collector)
        report = hc.check_health()
        assert report["status"] == "healthy"


# ---------------------------------------------------------------------------
# ObservedMerge — integration with real merge API
# ---------------------------------------------------------------------------


class TestObservedMerge:
    def test_basic_merge(self, sample_left, sample_right):
        om = ObservedMerge(node_id="test")
        result, metric = om.merge(sample_left, sample_right, key="id")
        assert isinstance(result, list)
        assert len(result) >= 2
        assert metric.operation == "merge"
        assert metric.duration_ms >= 0
        assert metric.input_record_count == 4
        assert metric.output_record_count == len(result)

    def test_merge_with_schema(self, sample_left, sample_right):
        om = ObservedMerge()
        schema = MergeSchema(default=LWW())
        result, metric = om.merge(sample_left, sample_right, key="id", schema=schema)
        assert metric.strategy_used == "LWW"
        assert isinstance(result, list)

    def test_conflict_detection(self, sample_left, sample_right):
        om = ObservedMerge()
        _, metric = om.merge(sample_left, sample_right, key="id")
        # id=1 appears on both sides
        assert metric.conflicts_detected >= 1

    def test_collector_property(self):
        om = ObservedMerge()
        assert isinstance(om.collector, MetricsCollector)

    def test_custom_collector(self):
        c = MetricsCollector(node_id="custom")
        om = ObservedMerge(collector=c)
        assert om.collector is c

    def test_metrics_accumulate(self, sample_left, sample_right):
        om = ObservedMerge()
        om.merge(sample_left, sample_right, key="id")
        om.merge(sample_left, sample_right, key="id")
        assert len(om.collector) == 2

    def test_empty_inputs(self):
        om = ObservedMerge()
        result, metric = om.merge([], [], key="id")
        assert result == []
        assert metric.input_record_count == 0

    def test_zero_duration_acceptable(self):
        om = ObservedMerge()
        result, metric = om.merge([], [], key="id")
        assert metric.duration_ms >= 0
