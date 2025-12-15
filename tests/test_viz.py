# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.viz — Conflict Topology Visualization."""

import csv
import io
import json
import os
import tempfile

import pytest

from crdt_merge.viz import ConflictTopology, ConflictRecord, ConflictCluster


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_conflict(key=1, field="name", sources=None, values=None,
                   resolved_value="Alice", strategy="lww", timestamp=None):
    return ConflictRecord(
        key=key,
        field=field,
        sources=sources or ["a", "b"],
        values=values or ["Alice", "Bob"],
        resolved_value=resolved_value,
        strategy=strategy,
        timestamp=timestamp,
    )


def _sample_conflicts():
    return [
        _make_conflict(key=1, field="name", values=["Alice", "Alicia"], resolved_value="Alice"),
        _make_conflict(key=1, field="salary", values=[100, 120], resolved_value=120, strategy="max"),
        _make_conflict(key=2, field="name", values=["Bob", "Bobby"], resolved_value="Bob"),
        _make_conflict(key=2, field="email", values=["b@x.com", "b@y.com"],
                       resolved_value="b@y.com", sources=["east", "west"]),
        _make_conflict(key=3, field="name", values=["Charlie", "Chuck"], resolved_value="Charlie"),
    ]


# ---------------------------------------------------------------------------
# TestConflictTopology (15 tests)
# ---------------------------------------------------------------------------

class TestConflictTopology:
    def test_create_empty(self):
        topo = ConflictTopology()
        assert len(topo) == 0
        assert topo.summary() == "No conflicts detected."

    def test_create_from_records(self):
        recs = [
            {"key": 1, "field": "name", "sources": ["a", "b"],
             "values": ["X", "Y"], "resolved_value": "X"},
        ]
        topo = ConflictTopology.from_records(recs)
        assert len(topo) == 1

    def test_from_merge_result_mergeql(self):
        """Test from_merge with a MergeQLResult-like object."""
        class FakeResult:
            data = [{"id": 1}]
            plan = "plan"
            provenance = [
                {"key": 1, "decisions": [
                    {"field": "name", "source": "conflict_resolved",
                     "value": "A", "alternative": "B", "strategy": "lww"},
                ]}
            ]
        topo = ConflictTopology.from_merge(FakeResult())
        assert len(topo) == 1

    def test_from_merge_result_provenance_log(self):
        """Test from_merge with a ProvenanceLog object."""
        from crdt_merge.provenance import ProvenanceLog, MergeRecord, MergeDecision
        dec = MergeDecision(field="name", source="conflict_resolved",
                            strategy="lww", value="A", alternative="B")
        rec = MergeRecord(key=1, origin="merged", decisions=[dec])
        log = ProvenanceLog(records=[rec], total_conflicts=1)
        topo = ConflictTopology.from_merge([], provenance=log)
        assert len(topo) == 1

    def test_add_conflict(self):
        topo = ConflictTopology()
        topo.add_conflict(_make_conflict())
        assert len(topo) == 1

    def test_heatmap_basic(self):
        topo = ConflictTopology([_make_conflict(field="name")])
        hm = topo.heatmap()
        assert "name" in hm
        assert sum(hm["name"].values()) == 1

    def test_heatmap_multi_field(self):
        topo = ConflictTopology(_sample_conflicts())
        hm = topo.heatmap()
        assert "name" in hm
        assert "salary" in hm
        assert "email" in hm

    def test_heatmap_multi_source(self):
        topo = ConflictTopology(_sample_conflicts())
        hm = topo.heatmap()
        # email has sources east/west
        assert "east↔west" in hm["email"]

    def test_field_frequency(self):
        topo = ConflictTopology(_sample_conflicts())
        freq = topo.field_frequency()
        assert freq["name"] == 3
        assert freq["salary"] == 1
        assert freq["email"] == 1

    def test_source_frequency(self):
        topo = ConflictTopology(_sample_conflicts())
        freq = topo.source_frequency()
        # 4 conflicts with ["a","b"] + 1 with ["east","west"]
        assert freq["a"] == 4
        assert freq["b"] == 4
        assert freq["east"] == 1
        assert freq["west"] == 1

    def test_strategy_stats(self):
        topo = ConflictTopology(_sample_conflicts())
        stats = topo.strategy_stats()
        assert stats["lww"] == 4
        assert stats["max"] == 1

    def test_summary_format(self):
        topo = ConflictTopology(_sample_conflicts())
        s = topo.summary()
        assert "5 conflicts" in s
        assert "3 fields" in s
        assert "clusters" in s

    def test_summary_no_conflicts(self):
        topo = ConflictTopology()
        assert topo.summary() == "No conflicts detected."

    def test_len(self):
        topo = ConflictTopology(_sample_conflicts())
        assert len(topo) == 5

    def test_repr(self):
        topo = ConflictTopology(_sample_conflicts())
        r = repr(topo)
        assert "ConflictTopology" in r
        assert "5" in r

    def test_to_dict(self):
        topo = ConflictTopology(_sample_conflicts())
        d = topo.to_dict()
        assert "heatmap" in d
        assert "clusters" in d
        assert "summary" in d
        assert "total_conflicts" in d
        assert d["total_conflicts"] == 5


# ---------------------------------------------------------------------------
# TestTemporalPatterns (5 tests)
# ---------------------------------------------------------------------------

class TestTemporalPatterns:
    def test_temporal_empty(self):
        topo = ConflictTopology()
        assert topo.temporal_pattern() == []

    def test_temporal_single_time(self):
        c = _make_conflict(timestamp="2026-01-01T00:00:00")
        topo = ConflictTopology([c])
        tp = topo.temporal_pattern()
        assert len(tp) == 1
        assert tp[0]["timestamp"] == "2026-01-01T00:00:00"
        assert tp[0]["count"] == 1

    def test_temporal_multiple_times(self):
        cs = [
            _make_conflict(key=1, timestamp="2026-01-01"),
            _make_conflict(key=2, timestamp="2026-01-02"),
            _make_conflict(key=3, timestamp="2026-01-01"),
        ]
        topo = ConflictTopology(cs)
        tp = topo.temporal_pattern()
        assert len(tp) == 2
        # First bucket has 2 conflicts
        assert tp[0]["count"] == 2

    def test_temporal_no_timestamps(self):
        topo = ConflictTopology([_make_conflict()])
        tp = topo.temporal_pattern()
        assert len(tp) == 1
        assert tp[0]["timestamp"] is None

    def test_temporal_ordering(self):
        cs = [
            _make_conflict(key=1, timestamp="2026-03-01"),
            _make_conflict(key=2, timestamp="2026-01-01"),
            _make_conflict(key=3, timestamp="2026-02-01"),
        ]
        topo = ConflictTopology(cs)
        tp = topo.temporal_pattern()
        timestamps = [t["timestamp"] for t in tp]
        assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# TestClusterAnalysis (5 tests)
# ---------------------------------------------------------------------------

class TestClusterAnalysis:
    def test_clusters_empty(self):
        topo = ConflictTopology()
        assert topo.clusters() == []

    def test_clusters_single_field(self):
        topo = ConflictTopology([_make_conflict()])
        clusters = topo.clusters()
        assert len(clusters) == 1
        assert clusters[0].count == 1

    def test_clusters_multi_field(self):
        cs = [
            _make_conflict(field="name"),
            _make_conflict(field="salary"),
        ]
        topo = ConflictTopology(cs)
        clusters = topo.clusters()
        # Both have same source pair a↔b, so one cluster
        assert len(clusters) == 1
        assert set(clusters[0].fields) == {"name", "salary"}

    def test_clusters_source_pairs(self):
        cs = [
            _make_conflict(field="name", sources=["a", "b"]),
            _make_conflict(field="email", sources=["east", "west"]),
        ]
        topo = ConflictTopology(cs)
        clusters = topo.clusters()
        assert len(clusters) == 2

    def test_clusters_pattern_description(self):
        topo = ConflictTopology([_make_conflict()])
        clusters = topo.clusters()
        assert "conflict" in clusters[0].pattern.lower()


# ---------------------------------------------------------------------------
# TestExport (10 tests)
# ---------------------------------------------------------------------------

class TestExport:
    def test_to_json_format(self):
        topo = ConflictTopology(_sample_conflicts())
        j = topo.to_json()
        data = json.loads(j)
        assert isinstance(data, dict)

    def test_to_json_d3_compatible(self):
        topo = ConflictTopology(_sample_conflicts())
        data = json.loads(topo.to_json())
        assert "nodes" in data
        assert "links" in data

    def test_to_json_nodes_and_links(self):
        topo = ConflictTopology(_sample_conflicts())
        data = json.loads(topo.to_json())
        # Should have field nodes + source nodes
        node_types = set(n["type"] for n in data["nodes"])
        assert "field" in node_types
        assert "source" in node_types
        assert len(data["links"]) > 0

    def test_to_json_empty(self):
        topo = ConflictTopology()
        data = json.loads(topo.to_json())
        assert data["nodes"] == []
        assert data["links"] == []

    def test_to_csv_basic(self):
        topo = ConflictTopology(_sample_conflicts())
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            topo.to_csv(path)
            with open(path) as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 6  # header + 5 conflicts
        finally:
            os.unlink(path)

    def test_to_csv_headers(self):
        topo = ConflictTopology([_make_conflict()])
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            topo.to_csv(path)
            with open(path) as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames
            assert "key" in fields
            assert "field" in fields
            assert "strategy" in fields
        finally:
            os.unlink(path)

    def test_to_csv_empty(self):
        topo = ConflictTopology()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            topo.to_csv(path)
            with open(path) as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 1  # header only
        finally:
            os.unlink(path)

    def test_to_csv_special_chars(self):
        c = _make_conflict(field="na,me", values=["He said \"hi\"", "normal"])
        topo = ConflictTopology([c])
        csv_str = topo.to_csv_string()
        assert "na,me" in csv_str  # properly quoted

    def test_roundtrip_json(self):
        topo = ConflictTopology(_sample_conflicts())
        j = topo.to_json()
        data = json.loads(j)
        assert data["stats"]["total_conflicts"] == 5

    def test_roundtrip_csv(self):
        topo = ConflictTopology(_sample_conflicts())
        csv_str = topo.to_csv_string()
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 5
