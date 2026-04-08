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

"""Tests for crdt-merge v0.9.2 observability extensions.

Covers MergeTracer, DriftDetector, DriftReport, PrometheusExporter, and
GrafanaDashboard.
"""

import json
import time

import pytest

from crdt_merge.observability import (
    DriftDetector,
    DriftReport,
    GrafanaDashboard,
    MergeTracer,
    MetricsCollector,
    PrometheusExporter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collector():
    return MetricsCollector(node_id="test-node")


@pytest.fixture
def baseline_records():
    return [
        {"id": 1, "score": 100.0, "name": "Alice"},
        {"id": 2, "score": 110.0, "name": "Bob"},
        {"id": 3, "score": 90.0, "name": "Charlie"},
    ]


# ---------------------------------------------------------------------------
# MergeTracer
# ---------------------------------------------------------------------------


class TestMergeTracer:
    def test_trace_merge_context_manager_noop(self):
        """trace_merge works as a context manager even without OTel."""
        tracer = MergeTracer(service_name="test-svc")
        with tracer.trace_merge("my_merge", {"key": "user_id"}) as span:
            result = 1 + 1
        assert result == 2
        # Span is a NoOp — should not raise
        span.set_attribute("extra", "ok")

    def test_trace_batch(self):
        """trace_batch yields a span-like object."""
        tracer = MergeTracer()
        with tracer.trace_batch("batch_op", batch_size=42) as span:
            total = sum(range(10))
        assert total == 45
        # No exception is the success criterion

    def test_is_enabled_without_otel(self):
        """is_enabled is False when OpenTelemetry is not installed."""
        tracer = MergeTracer()
        # In this test environment OTel is not installed
        assert tracer.is_enabled is False

    def test_trace_merge_with_collector(self, collector):
        """When a collector is provided, trace_merge records a metric."""
        tracer = MergeTracer(collector=collector)
        assert len(collector) == 0
        with tracer.trace_merge("tracked_merge"):
            time.sleep(0.01)
        assert len(collector) == 1
        metrics = collector.get_metrics()
        assert metrics[0].operation == "tracked_merge"
        assert metrics[0].duration_ms > 0

    def test_trace_batch_with_collector(self, collector):
        """trace_batch also records to collector when provided."""
        tracer = MergeTracer(collector=collector)
        with tracer.trace_batch("batch_op", batch_size=5):
            pass
        assert len(collector) == 1
        m = collector.get_metrics()[0]
        assert m.operation == "batch_op"
        assert m.input_record_count == 5

    def test_get_tracer_none_without_otel(self):
        """get_tracer returns None when OTel is unavailable."""
        tracer = MergeTracer()
        assert tracer.get_tracer() is None

    def test_trace_merge_propagates_exception(self):
        """Exceptions inside trace_merge are re-raised."""
        tracer = MergeTracer()
        with pytest.raises(ValueError, match="boom"):
            with tracer.trace_merge("failing"):
                raise ValueError("boom")


# ---------------------------------------------------------------------------
# DriftDetector & DriftReport
# ---------------------------------------------------------------------------


class TestDriftDetector:
    def test_no_drift_identical_data(self, baseline_records):
        """No drift when checking against identical data."""
        detector = DriftDetector()
        detector.record_baseline(baseline_records)
        report = detector.check(baseline_records)
        assert report.has_drift is False
        assert report.schema_changes["added"] == []
        assert report.schema_changes["removed"] == []
        assert report.schema_changes["type_changed"] == {}
        assert report.statistical_drift == {}

    def test_detects_new_columns(self, baseline_records):
        """Detects columns added since baseline."""
        detector = DriftDetector()
        detector.record_baseline(baseline_records)
        modified = [dict(r, new_col="x") for r in baseline_records]
        report = detector.check(modified)
        assert report.has_drift is True
        assert "new_col" in report.schema_changes["added"]

    def test_detects_removed_columns(self, baseline_records):
        """Detects columns removed since baseline."""
        detector = DriftDetector()
        detector.record_baseline(baseline_records)
        modified = [{"id": r["id"]} for r in baseline_records]  # only id
        report = detector.check(modified)
        assert report.has_drift is True
        assert "score" in report.schema_changes["removed"]
        assert "name" in report.schema_changes["removed"]

    def test_detects_statistical_drift(self):
        """Detects mean shift beyond sensitivity * stddev."""
        detector = DriftDetector(sensitivity=2.0)
        baseline = [{"val": 100.0}, {"val": 102.0}, {"val": 98.0}]
        detector.record_baseline(baseline)
        # mean=100, stddev≈1.63 → need shift > 3.27 for drift
        drifted = [{"val": 200.0}, {"val": 210.0}, {"val": 190.0}]
        report = detector.check(drifted)
        assert report.has_drift is True
        assert "val" in report.statistical_drift
        assert report.statistical_drift["val"]["drift_score"] > 2.0

    def test_sensitivity_parameter(self):
        """Higher sensitivity requires larger shifts to trigger drift."""
        baseline = [{"val": 100.0}, {"val": 102.0}, {"val": 98.0}]
        current = [{"val": 106.0}, {"val": 108.0}, {"val": 104.0}]

        sensitive = DriftDetector(sensitivity=1.0)
        sensitive.record_baseline(baseline)
        report_sensitive = sensitive.check(current)

        tolerant = DriftDetector(sensitivity=50.0)
        tolerant.record_baseline(baseline)
        report_tolerant = tolerant.check(current)

        # The sensitive detector should flag drift, the tolerant one should not
        assert report_sensitive.has_drift is True
        assert report_tolerant.has_drift is False

    def test_reset(self, baseline_records):
        """reset() clears baseline so check raises."""
        detector = DriftDetector()
        detector.record_baseline(baseline_records)
        detector.reset()
        with pytest.raises(RuntimeError, match="No baseline"):
            detector.check(baseline_records)

    def test_empty_baseline(self):
        """Empty baseline is valid — any new column is drift."""
        detector = DriftDetector()
        detector.record_baseline([])
        report = detector.check([{"a": 1}])
        assert report.has_drift is True
        assert "a" in report.schema_changes["added"]


class TestDriftReport:
    def test_to_dict_roundtrip(self):
        """to_dict produces a serialisable dictionary."""
        report = DriftReport(
            has_drift=True,
            schema_changes={"added": ["col_x"], "removed": [], "type_changed": {}},
            statistical_drift={"score": {"baseline_mean": 1.0, "current_mean": 5.0, "drift_score": 4.0}},
            checked_at=1000.0,
        )
        d = report.to_dict()
        assert d["has_drift"] is True
        assert d["schema_changes"]["added"] == ["col_x"]
        assert d["statistical_drift"]["score"]["drift_score"] == 4.0
        assert d["checked_at"] == 1000.0
        # Ensure JSON-serialisable
        json.dumps(d)


# ---------------------------------------------------------------------------
# PrometheusExporter
# ---------------------------------------------------------------------------


class TestPrometheusExporter:
    def test_expose_format(self, collector):
        """expose() returns valid Prometheus exposition text."""
        collector.record_merge(5, 5, 8, 12.5, conflicts=2)
        collector.record_merge(3, 3, 5, 3.0, conflicts=0)
        exporter = PrometheusExporter.from_collector(collector)
        text = exporter.expose()

        # Check required metric names present
        assert "crdt_merge_merges_total 2" in text
        assert "crdt_merge_conflicts_total 2" in text
        assert "crdt_merge_records_processed_total 16" in text

        # Check histogram format
        assert "# TYPE crdt_merge_merge_duration_ms histogram" in text
        assert 'crdt_merge_merge_duration_ms_bucket{le="1"}' in text
        assert 'crdt_merge_merge_duration_ms_bucket{le="+Inf"} 2' in text
        assert "crdt_merge_merge_duration_ms_sum" in text
        assert "crdt_merge_merge_duration_ms_count 2" in text

    def test_from_collector_integration(self, collector):
        """from_collector creates a working exporter."""
        for i in range(5):
            collector.record_merge(1, 1, 1, float(i + 1))
        exporter = PrometheusExporter.from_collector(collector)
        text = exporter.expose()
        assert "crdt_merge_merges_total 5" in text

    def test_to_dict(self, collector):
        """to_dict returns expected keys."""
        collector.record_merge(2, 3, 4, 10.0, conflicts=1)
        exporter = PrometheusExporter.from_collector(collector)
        d = exporter.to_dict()
        assert d["crdt_merge_merges_total"] == 1
        assert d["crdt_merge_conflicts_total"] == 1
        assert d["crdt_merge_records_processed_total"] == 5
        assert d["crdt_merge_errors_total"] == 0
        dur = d["crdt_merge_merge_duration_ms"]
        assert dur["count"] == 1
        assert dur["sum"] == 10.0
        assert dur["buckets"]["+Inf"] == 1
        assert dur["buckets"]["10"] == 1
        assert dur["buckets"]["5"] == 0

    def test_empty_collector(self):
        """Exporter works with no metrics recorded."""
        c = MetricsCollector()
        exporter = PrometheusExporter.from_collector(c)
        text = exporter.expose()
        assert "crdt_merge_merges_total 0" in text


# ---------------------------------------------------------------------------
# GrafanaDashboard
# ---------------------------------------------------------------------------


class TestGrafanaDashboard:
    def test_generate_has_required_panels(self):
        """generate() includes all six expected panels."""
        dashboard = GrafanaDashboard()
        model = dashboard.generate()
        panels = model["dashboard"]["panels"]
        titles = {p["title"] for p in panels}
        assert "Merge Throughput" in titles
        assert "Merge Latency" in titles
        assert "Conflict Rate" in titles
        assert "Error Rate" in titles
        assert "Health Status" in titles
        assert "Drift Alerts" in titles
        assert len(panels) == 6

    def test_to_json_is_valid(self):
        """to_json returns parseable JSON."""
        dashboard = GrafanaDashboard()
        raw = dashboard.to_json()
        parsed = json.loads(raw)
        assert "dashboard" in parsed
        assert parsed["dashboard"]["title"] == "CRDT Merge Monitoring"

    def test_custom_title_and_datasource(self):
        """Custom title and datasource are honoured."""
        dashboard = GrafanaDashboard(
            title="My Custom Dashboard",
            datasource="Mimir",
            refresh="10s",
        )
        model = dashboard.generate()
        assert model["dashboard"]["title"] == "My Custom Dashboard"
        assert model["dashboard"]["refresh"] == "10s"
        # All panels should reference the custom datasource
        for panel in model["dashboard"]["panels"]:
            assert panel["datasource"]["uid"] == "Mimir"

    def test_generate_structure(self):
        """Dashboard model has expected top-level keys."""
        dashboard = GrafanaDashboard()
        model = dashboard.generate()
        assert "dashboard" in model
        assert "overwrite" in model
        d = model["dashboard"]
        assert "title" in d
        assert "uid" in d
        assert "panels" in d
        assert "refresh" in d
        assert "schemaVersion" in d
