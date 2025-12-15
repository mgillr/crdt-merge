# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for v0.7.0 wire protocol tags (0x50–0x55).

Verifies that the new MergeQL, Parquet metadata, and conflict/provenance
types serialize and deserialize correctly, including compression.
"""

import pytest

from crdt_merge.wire import (
    serialize,
    deserialize,
    peek_type,
    wire_size,
    serialize_batch,
    deserialize_batch,
    WireError,
    TAG_MERGEQL_QUERY,
    TAG_MERGE_PLAN,
    TAG_MERGEQL_RESULT,
    TAG_PARQUET_MERGE_META,
    TAG_CONFLICT_RECORD,
    TAG_CONFLICT_TOPOLOGY,
    _TAG_TO_TYPE,
)
from crdt_merge.mergeql import MergeAST, MergePlan, MergeQLResult
from crdt_merge.parquet import ParquetMergeMetadata
from crdt_merge.provenance import MergeRecord, MergeDecision, ProvenanceLog


# ---------------------------------------------------------------------------
# Tag constants
# ---------------------------------------------------------------------------

class TestV070TagConstants:
    """Verify tag values don't clash with existing tags."""

    def test_mergeql_query_tag(self):
        assert TAG_MERGEQL_QUERY == 0x50

    def test_merge_plan_tag(self):
        assert TAG_MERGE_PLAN == 0x51

    def test_mergeql_result_tag(self):
        assert TAG_MERGEQL_RESULT == 0x52

    def test_parquet_merge_meta_tag(self):
        assert TAG_PARQUET_MERGE_META == 0x53

    def test_conflict_record_tag(self):
        assert TAG_CONFLICT_RECORD == 0x54

    def test_conflict_topology_tag(self):
        assert TAG_CONFLICT_TOPOLOGY == 0x55

    def test_tags_in_tag_to_type(self):
        assert _TAG_TO_TYPE[TAG_MERGEQL_QUERY] == "mergeql_query"
        assert _TAG_TO_TYPE[TAG_MERGE_PLAN] == "merge_plan"
        assert _TAG_TO_TYPE[TAG_MERGEQL_RESULT] == "mergeql_result"
        assert _TAG_TO_TYPE[TAG_PARQUET_MERGE_META] == "parquet_merge_metadata"
        assert _TAG_TO_TYPE[TAG_CONFLICT_RECORD] == "conflict_record"
        assert _TAG_TO_TYPE[TAG_CONFLICT_TOPOLOGY] == "conflict_topology"


# ---------------------------------------------------------------------------
# MergeAST wire round-trip
# ---------------------------------------------------------------------------

class TestMergeASTWire:
    def test_basic_roundtrip(self):
        ast = MergeAST(sources=["a", "b"], on_key="id", strategies={"name": "lww"})
        data = serialize(ast)
        restored = deserialize(data)
        assert isinstance(restored, MergeAST)
        assert restored.sources == ["a", "b"]
        assert restored.on_key == "id"
        assert restored.strategies == {"name": "lww"}

    def test_compressed_roundtrip(self):
        ast = MergeAST(sources=["src_" + str(i) for i in range(20)], on_key="pk")
        data = serialize(ast, compress=True)
        restored = deserialize(data)
        assert len(restored.sources) == 20

    def test_peek_type(self):
        ast = MergeAST(sources=["a", "b"], on_key="id")
        data = serialize(ast)
        assert peek_type(data) == "mergeql_query"

    def test_with_where_and_limit(self):
        ast = MergeAST(
            sources=["x", "y"], on_key="k",
            where_clause="val > 0", limit=100, explain=True,
        )
        data = serialize(ast)
        restored = deserialize(data)
        assert restored.where_clause == "val > 0"
        assert restored.limit == 100
        assert restored.explain is True


# ---------------------------------------------------------------------------
# MergePlan wire round-trip
# ---------------------------------------------------------------------------

class TestMergePlanWire:
    def _make_plan(self) -> MergePlan:
        return MergePlan(
            sources=["a", "b"],
            source_sizes={"a": 100, "b": 200},
            merge_key="id",
            strategies={"name": "lww", "score": "max"},
            estimated_output_rows=250,
            schema_evolution_needed=False,
            arrow_backend=True,
            steps=["Load sources", "Apply strategies", "Emit results"],
        )

    def test_basic_roundtrip(self):
        plan = self._make_plan()
        data = serialize(plan)
        restored = deserialize(data)
        assert isinstance(restored, MergePlan)
        assert restored.merge_key == "id"
        assert restored.estimated_output_rows == 250
        assert restored.arrow_backend is True
        assert len(restored.steps) == 3

    def test_compressed(self):
        plan = self._make_plan()
        raw = serialize(plan)
        comp = serialize(plan, compress=True)
        restored = deserialize(comp)
        assert restored.merge_key == "id"

    def test_peek_type(self):
        data = serialize(self._make_plan())
        assert peek_type(data) == "merge_plan"

    def test_wire_size(self):
        data = serialize(self._make_plan())
        info = wire_size(data)
        assert info["type_name"] == "merge_plan"


# ---------------------------------------------------------------------------
# MergeQLResult wire round-trip
# ---------------------------------------------------------------------------

class TestMergeQLResultWire:
    def _make_result(self) -> MergeQLResult:
        plan = MergePlan(
            sources=["a", "b"],
            source_sizes={"a": 5, "b": 5},
            merge_key="id",
            strategies={},
            estimated_output_rows=8,
            schema_evolution_needed=False,
            arrow_backend=False,
            steps=["merge"],
        )
        return MergeQLResult(
            data=[{"id": 1, "val": "x"}, {"id": 2, "val": "y"}],
            plan=plan,
            conflicts=1,
            merge_time_ms=2.5,
            sources_merged=2,
        )

    def test_basic_roundtrip(self):
        result = self._make_result()
        data = serialize(result)
        restored = deserialize(data)
        assert isinstance(restored, MergeQLResult)
        assert restored.conflicts == 1
        assert len(restored.data) == 2
        assert isinstance(restored.plan, MergePlan)
        assert restored.merge_time_ms == 2.5

    def test_peek_type(self):
        data = serialize(self._make_result())
        assert peek_type(data) == "mergeql_result"


# ---------------------------------------------------------------------------
# ParquetMergeMetadata wire round-trip
# ---------------------------------------------------------------------------

class TestParquetMergeMetadataWire:
    def test_basic_roundtrip(self):
        meta = ParquetMergeMetadata(
            key_column="id",
            strategies={"name": "lww", "score": "max"},
            provenance_enabled=True,
            source_count=3,
            merge_count=7,
        )
        data = serialize(meta)
        restored = deserialize(data)
        assert isinstance(restored, ParquetMergeMetadata)
        assert restored.key_column == "id"
        assert restored.strategies == {"name": "lww", "score": "max"}
        assert restored.source_count == 3
        assert restored.merge_count == 7

    def test_compressed(self):
        meta = ParquetMergeMetadata(key_column="pk", strategies={"c": "lww"})
        data = serialize(meta, compress=True)
        restored = deserialize(data)
        assert restored.key_column == "pk"

    def test_peek_type(self):
        meta = ParquetMergeMetadata(key_column="id", strategies={})
        data = serialize(meta)
        assert peek_type(data) == "parquet_merge_metadata"


# ---------------------------------------------------------------------------
# MergeRecord (conflict_record) wire round-trip
# ---------------------------------------------------------------------------

class TestConflictRecordWire:
    def _make_record(self) -> MergeRecord:
        return MergeRecord(
            key=42,
            origin="merged",
            decisions=[
                MergeDecision(
                    field="name",
                    source="conflict_resolved",
                    strategy="LWW",
                    value="Alice",
                    alternative="Bob",
                ),
                MergeDecision(
                    field="score",
                    source="b",
                    strategy="MaxWins",
                    value=200,
                    alternative=100,
                ),
            ],
        )

    def test_basic_roundtrip(self):
        rec = self._make_record()
        data = serialize(rec)
        restored = deserialize(data)
        assert isinstance(restored, MergeRecord)
        assert restored.key == 42
        assert restored.origin == "merged"
        assert len(restored.decisions) == 2
        assert restored.decisions[0].field == "name"
        assert restored.decisions[0].value == "Alice"

    def test_compressed(self):
        rec = self._make_record()
        data = serialize(rec, compress=True)
        restored = deserialize(data)
        assert restored.key == 42

    def test_peek_type(self):
        data = serialize(self._make_record())
        assert peek_type(data) == "conflict_record"


# ---------------------------------------------------------------------------
# ProvenanceLog (conflict_topology) wire round-trip
# ---------------------------------------------------------------------------

class TestConflictTopologyWire:
    def _make_log(self) -> ProvenanceLog:
        dec = MergeDecision(
            field="name", source="conflict_resolved",
            strategy="LWW", value="Alice", alternative="Bob",
        )
        rec = MergeRecord(key=1, origin="merged", decisions=[dec])
        return ProvenanceLog(
            records=[rec],
            total_rows=10,
            merged_rows=5,
            unique_a_rows=3,
            unique_b_rows=2,
            total_conflicts=1,
            duration_ms=3.7,
        )

    def test_basic_roundtrip(self):
        log = self._make_log()
        data = serialize(log)
        restored = deserialize(data)
        assert isinstance(restored, ProvenanceLog)
        assert restored.total_rows == 10
        assert restored.total_conflicts == 1
        assert len(restored.records) == 1
        assert restored.records[0].decisions[0].field == "name"

    def test_compressed(self):
        log = self._make_log()
        data = serialize(log, compress=True)
        restored = deserialize(data)
        assert restored.total_conflicts == 1

    def test_peek_type(self):
        data = serialize(self._make_log())
        assert peek_type(data) == "conflict_topology"

    def test_empty_log(self):
        log = ProvenanceLog()
        data = serialize(log)
        restored = deserialize(data)
        assert len(restored.records) == 0
        assert restored.total_rows == 0


# ---------------------------------------------------------------------------
# Batch with v0.7.0 types
# ---------------------------------------------------------------------------

class TestV070Batch:
    def test_batch_mixed(self):
        ast = MergeAST(sources=["a", "b"], on_key="id")
        meta = ParquetMergeMetadata(key_column="pk", strategies={})
        batch_data = serialize_batch([ast, meta])
        restored = deserialize_batch(batch_data)
        assert isinstance(restored[0], MergeAST)
        assert isinstance(restored[1], ParquetMergeMetadata)
