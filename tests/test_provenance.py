# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.provenance — Merge Provenance & Lineage (v0.4.0)."""

import json
import pytest


class TestMergeDecision:
    """Test MergeDecision dataclass."""

    def test_conflict_decision(self):
        from crdt_merge.provenance import MergeDecision
        d = MergeDecision(field="score", source="conflict_resolved",
                          strategy="MaxWins", value=100, alternative=50)
        assert d.was_conflict()
        assert d.value == 100
        assert d.alternative == 50

    def test_non_conflict_decision(self):
        from crdt_merge.provenance import MergeDecision
        d = MergeDecision(field="name", source="both_equal",
                          strategy="", value="alice")
        assert not d.was_conflict()
        assert d.alternative is None

    def test_to_dict(self):
        from crdt_merge.provenance import MergeDecision
        d = MergeDecision(field="x", source="a_only", strategy="", value=42)
        result = d.to_dict()
        assert result["field"] == "x"
        assert result["source"] == "a_only"
        assert result["value"] == 42


class TestMergeRecord:
    """Test MergeRecord dataclass."""

    def test_conflict_count(self):
        from crdt_merge.provenance import MergeRecord, MergeDecision
        rec = MergeRecord(key=1, origin="merged", decisions=[
            MergeDecision(field="a", source="both_equal", strategy="", value=1),
            MergeDecision(field="b", source="conflict_resolved", strategy="LWW", value=2, alternative=3),
            MergeDecision(field="c", source="conflict_resolved", strategy="MaxWins", value=10, alternative=5),
        ])
        assert rec.conflict_count == 2
        assert len(rec.conflicts) == 2

    def test_fields_from_sources(self):
        from crdt_merge.provenance import MergeRecord, MergeDecision
        rec = MergeRecord(key="k", origin="merged", decisions=[
            MergeDecision(field="x", source="a_only", strategy="", value=1),
            MergeDecision(field="y", source="b_only", strategy="", value=2),
            MergeDecision(field="z", source="both_equal", strategy="", value=3),
        ])
        assert rec.fields_from_a == ["x"]
        assert rec.fields_from_b == ["y"]

    def test_unique_a_record(self):
        from crdt_merge.provenance import MergeRecord
        rec = MergeRecord(key=99, origin="unique_a")
        assert rec.conflict_count == 0
        assert rec.origin == "unique_a"


class TestMergeWithProvenance:
    """Test the main merge_with_provenance function."""

    def test_basic_merge_dicts(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "name": "alice", "score": 80}]
        b = [{"id": 1, "name": "alice", "score": 100}]
        merged, log = merge_with_provenance(a, b, key="id")
        assert len(merged) == 1
        assert log.total_rows == 1
        assert log.merged_rows == 1
        assert log.total_conflicts >= 1  # score conflict

    def test_no_conflicts(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "name": "alice"}]
        b = [{"id": 1, "name": "alice"}]
        merged, log = merge_with_provenance(a, b, key="id")
        assert log.total_conflicts == 0
        assert log.merged_rows == 1

    def test_unique_rows(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "val": "a1"}, {"id": 2, "val": "a2"}]
        b = [{"id": 3, "val": "b3"}]
        merged, log = merge_with_provenance(a, b, key="id")
        assert len(merged) == 3
        assert log.unique_a_rows == 2
        assert log.unique_b_rows == 1
        assert log.merged_rows == 0

    def test_mixed_merge(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [
            {"id": 1, "name": "alice", "score": 80},
            {"id": 2, "name": "bob"},
        ]
        b = [
            {"id": 1, "name": "alice", "score": 100},
            {"id": 3, "name": "charlie"},
        ]
        merged, log = merge_with_provenance(a, b, key="id")
        assert len(merged) == 3
        assert log.merged_rows == 1
        assert log.unique_a_rows == 1
        assert log.unique_b_rows == 1
        assert log.total_rows == 3

    def test_with_schema(self):
        from crdt_merge.provenance import merge_with_provenance
        from crdt_merge.strategies import MergeSchema, MaxWins
        schema = MergeSchema(score=MaxWins())
        a = [{"id": 1, "score": 80}]
        b = [{"id": 1, "score": 100}]
        merged, log = merge_with_provenance(a, b, key="id", schema=schema)
        assert merged[0]["score"] == 100
        conflict = log.records[0].conflicts[0]
        assert conflict.strategy == "MaxWins"
        assert conflict.value == 100
        assert conflict.alternative == 80

    def test_with_pandas_dataframes(self):
        pd = __import__("pytest").importorskip("pandas")
        from crdt_merge.provenance import merge_with_provenance
        df_a = pd.DataFrame([{"id": 1, "val": "old"}])
        df_b = pd.DataFrame([{"id": 1, "val": "new"}])
        merged, log = merge_with_provenance(df_a, df_b, key="id")
        assert len(merged) == 1
        assert log.total_rows == 1

    def test_provenance_log_summary(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "score": 80}]
        b = [{"id": 1, "score": 100}]
        _, log = merge_with_provenance(a, b, key="id")
        summary = log.summary()
        assert "Merge Provenance Report" in summary
        assert "Total conflicts:" in summary

    def test_provenance_log_repr(self):
        from crdt_merge.provenance import ProvenanceLog
        log = ProvenanceLog(total_rows=10, total_conflicts=2, duration_ms=5.5)
        r = repr(log)
        assert "rows=10" in r
        assert "conflicts=2" in r

    def test_empty_inputs(self):
        from crdt_merge.provenance import merge_with_provenance
        merged, log = merge_with_provenance([], [], key="id")
        assert len(merged) == 0
        assert log.total_rows == 0

    def test_a_only_field(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "name": "alice", "extra": "yes"}]
        b = [{"id": 1, "name": "alice"}]
        merged, log = merge_with_provenance(a, b, key="id")
        decisions = {d.field: d for d in log.records[0].decisions}
        assert decisions["extra"].source == "a_only"

    def test_b_only_field(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "name": "alice"}]
        b = [{"id": 1, "name": "alice", "extra": "yes"}]
        merged, log = merge_with_provenance(a, b, key="id")
        decisions = {d.field: d for d in log.records[0].decisions}
        assert decisions["extra"].source == "b_only"

    def test_with_timestamp_col(self):
        from crdt_merge.provenance import merge_with_provenance
        a = [{"id": 1, "val": "old", "ts": 1}]
        b = [{"id": 1, "val": "new", "ts": 2}]
        merged, log = merge_with_provenance(a, b, key="id", timestamp_col="ts")
        assert log.total_conflicts >= 1

    def test_large_merge(self):
        """Verify provenance works at scale without errors."""
        from crdt_merge.provenance import merge_with_provenance
        n = 1000
        a = [{"id": i, "val": f"a_{i}", "score": i} for i in range(n)]
        b = [{"id": i, "val": f"b_{i}", "score": i + 1} for i in range(n)]
        merged, log = merge_with_provenance(a, b, key="id")
        assert len(merged) == n
        assert log.merged_rows == n
        assert log.total_conflicts > 0  # val and score differ


class TestExportProvenance:
    """Test export_provenance function."""

    def test_export_json(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance
        a = [{"id": 1, "val": "a"}]
        b = [{"id": 1, "val": "b"}]
        _, log = merge_with_provenance(a, b, key="id")
        j = export_provenance(log, format="json")
        data = json.loads(j)
        assert data["total_rows"] == 1
        assert "records" in data

    def test_export_csv(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance
        a = [{"id": 1, "val": "a"}]
        b = [{"id": 1, "val": "b"}]
        _, log = merge_with_provenance(a, b, key="id")
        csv = export_provenance(log, format="csv")
        lines = csv.strip().split("\n")
        assert lines[0] == "key,origin,field,source,strategy,value,alternative"
        assert len(lines) > 1

    def test_export_invalid_format(self):
        from crdt_merge.provenance import ProvenanceLog, export_provenance
        log = ProvenanceLog()
        with pytest.raises(ValueError, match="Unknown format"):
            export_provenance(log, format="xml")


class TestProvenanceIntegration:
    """Integration tests — provenance with strategies and streaming-style data."""

    def test_all_strategies_tracked(self):
        from crdt_merge.provenance import merge_with_provenance
        from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet
        schema = MergeSchema(
            default=LWW(),
            score=MaxWins(),
            priority=MinWins(),
            tags=UnionSet(separator=","),
        )
        a = [{"id": 1, "name": "a", "score": 80, "priority": 3, "tags": "x,y"}]
        b = [{"id": 1, "name": "b", "score": 100, "priority": 1, "tags": "y,z"}]
        merged, log = merge_with_provenance(a, b, key="id", schema=schema)
        strategies_used = {d.strategy for d in log.records[0].conflicts}
        assert "MaxWins" in strategies_used
        assert "MinWins" in strategies_used

    def test_provenance_preserves_data_integrity(self):
        """Provenance merge must produce the SAME data as regular merge."""
        pd = __import__("pytest").importorskip("pandas")
        from crdt_merge import merge
        from crdt_merge.provenance import merge_with_provenance
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(score=MaxWins())
        a = [{"id": 1, "name": "alice", "score": 80},
             {"id": 2, "name": "bob", "score": 90}]
        b = [{"id": 1, "name": "alice", "score": 100},
             {"id": 3, "name": "charlie", "score": 70}]

        df_a = pd.DataFrame(a)
        df_b = pd.DataFrame(b)

        # Regular merge
        regular = merge(df_a, df_b, key="id", schema=schema)
        # Provenance merge
        prov_data, log = merge_with_provenance(a, b, key="id", schema=schema)

        # Compare: same keys, same values
        reg_by_key = {r["id"]: r for r in regular.to_dict("records")}
        prov_by_key = {r["id"]: r for r in prov_data}
        assert set(reg_by_key.keys()) == set(prov_by_key.keys())
        for k in reg_by_key:
            for col in reg_by_key[k]:
                assert reg_by_key[k][col] == prov_by_key[k][col], \
                    f"Mismatch at key={k}, col={col}"
