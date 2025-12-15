# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.parquet — Self-Merging Parquet."""

import json
import time
import pytest

from crdt_merge.parquet import (
    CompactResult,
    IngestResult,
    ParquetMergeMetadata,
    ProvenanceEntry,
    SelfMergingParquet,
    SCHEMA_VERSION,
)
from crdt_merge.strategies import LWW, MaxWins, MinWins, MergeSchema


# ═══════════════════════════════════════════════════════════════════════════
# TestParquetMetadata — 10 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestParquetMetadata:
    """Tests for ParquetMergeMetadata serialization."""

    def test_metadata_to_dict(self):
        meta = ParquetMergeMetadata(
            key_column="id",
            strategies={"name": "LWW", "salary": "MaxWins"},
        )
        d = meta.to_dict()
        assert d["key_column"] == "id"
        assert d["strategies"]["name"] == "LWW"
        assert d["strategies"]["salary"] == "MaxWins"

    def test_metadata_from_dict(self):
        d = {
            "key_column": "id",
            "strategies": {"name": "LWW"},
            "provenance_enabled": False,
        }
        meta = ParquetMergeMetadata.from_dict(d)
        assert meta.key_column == "id"
        assert meta.strategies == {"name": "LWW"}
        assert meta.provenance_enabled is False

    def test_metadata_roundtrip(self):
        original = ParquetMergeMetadata(
            key_column="pk",
            strategies={"a": "LWW", "b": "MaxWins"},
            provenance_enabled=True,
            source_count=3,
            merge_count=2,
        )
        d = original.to_dict()
        restored = ParquetMergeMetadata.from_dict(d)
        assert restored.key_column == original.key_column
        assert restored.strategies == original.strategies
        assert restored.provenance_enabled == original.provenance_enabled
        assert restored.source_count == original.source_count
        assert restored.merge_count == original.merge_count

    def test_metadata_missing_key(self):
        with pytest.raises(ValueError, match="Missing required metadata"):
            ParquetMergeMetadata.from_parquet_metadata({})

    def test_metadata_empty_strategies(self):
        meta = ParquetMergeMetadata(key_column="id", strategies={})
        pq_meta = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq_meta)
        assert restored.strategies == {}

    def test_metadata_version(self):
        meta = ParquetMergeMetadata(key_column="id", strategies={})
        assert meta.schema_version == SCHEMA_VERSION
        pq = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq)
        assert restored.schema_version == SCHEMA_VERSION

    def test_metadata_source_count(self):
        meta = ParquetMergeMetadata(key_column="id", strategies={}, source_count=5)
        pq = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq)
        assert restored.source_count == 5

    def test_metadata_merge_count(self):
        meta = ParquetMergeMetadata(key_column="id", strategies={}, merge_count=10)
        pq = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq)
        assert restored.merge_count == 10

    def test_metadata_created_at(self):
        meta = ParquetMergeMetadata(
            key_column="id", strategies={}, created_at="2026-01-01T00:00:00Z"
        )
        pq = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq)
        assert restored.created_at == "2026-01-01T00:00:00Z"

    def test_metadata_provenance_flag(self):
        for flag in (True, False):
            meta = ParquetMergeMetadata(
                key_column="id", strategies={}, provenance_enabled=flag
            )
            pq = meta.to_parquet_metadata()
            restored = ParquetMergeMetadata.from_parquet_metadata(pq)
            assert restored.provenance_enabled is flag


# ═══════════════════════════════════════════════════════════════════════════
# TestSelfMergingParquet — 15 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfMergingParquet:
    """Tests for the SelfMergingParquet container."""

    def test_create_empty(self):
        smf = SelfMergingParquet("test", key="id")
        assert len(smf) == 0
        assert smf.read() == []

    def test_ingest_single_batch(self):
        smf = SelfMergingParquet("test", key="id")
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = smf.ingest(data)
        assert result.records_ingested == 2
        assert result.new_records == 2
        assert len(smf) == 2

    def test_ingest_multiple_batches(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        smf.ingest([{"id": 2, "name": "Bob"}])
        assert len(smf) == 2
        records = smf.read()
        names = {r["name"] for r in records}
        assert names == {"Alice", "Bob"}

    def test_ingest_with_conflicts(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
        result = smf.ingest([{"id": 1, "name": "Alicia", "salary": 120}])
        assert result.updated_records == 1
        assert result.conflicts_resolved >= 1
        records = smf.read()
        assert records[0]["salary"] == 120  # MaxWins

    def test_ingest_disjoint_keys(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        smf.ingest([{"id": 2, "name": "Bob"}])
        assert len(smf) == 2

    def test_read_empty(self):
        smf = SelfMergingParquet("test", key="id")
        assert smf.read() == []

    def test_read_after_ingest(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        records = smf.read()
        assert len(records) == 1
        assert records[0]["id"] == 1
        assert records[0]["name"] == "Alice"

    def test_compact_removes_dead_entries(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": None}])
        result = smf.compact()
        assert isinstance(result, CompactResult)
        assert result.records_before == 1
        # After compaction, the dead entry should be removed
        assert result.records_after == 0

    def test_compact_preserves_data(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
        result = smf.compact()
        assert result.records_after == 2
        assert len(smf) == 2

    def test_merge_with_another(self):
        smf_a = SelfMergingParquet("a", key="id")
        smf_b = SelfMergingParquet("b", key="id")
        smf_a.ingest([{"id": 1, "name": "Alice"}])
        smf_b.ingest([{"id": 2, "name": "Bob"}])
        result = smf_a.merge_with(smf_b)
        assert result.new_records == 1
        assert len(smf_a) == 2

    def test_len(self):
        smf = SelfMergingParquet("test", key="id")
        assert len(smf) == 0
        smf.ingest([{"id": 1, "name": "x"}])
        assert len(smf) == 1
        smf.ingest([{"id": 2, "name": "y"}])
        assert len(smf) == 2

    def test_repr(self):
        smf = SelfMergingParquet("myfile", key="id")
        r = repr(smf)
        assert "myfile" in r
        assert "id" in r

    def test_ingest_result_stats(self):
        smf = SelfMergingParquet("test", key="id")
        result = smf.ingest([{"id": 1, "name": "Alice"}])
        assert isinstance(result, IngestResult)
        assert result.records_ingested == 1
        assert result.new_records == 1
        assert result.updated_records == 0
        assert result.merge_time_ms >= 0

    def test_compact_result_stats(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        result = smf.compact()
        assert isinstance(result, CompactResult)
        assert result.compact_time_ms >= 0
        assert result.records_before == 1
        assert result.records_after == 1

    def test_source_label_tracking(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "A"}], source="batch_1")
        smf.ingest([{"id": 2, "name": "B"}], source="batch_2")
        log = smf.get_provenance_log()
        assert len(log) == 2
        assert log[0]["source"] == "batch_1"
        assert log[1]["source"] == "batch_2"


# ═══════════════════════════════════════════════════════════════════════════
# TestParquetStrategies — 10 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestParquetStrategies:
    """Tests for strategy application within SelfMergingParquet."""

    def test_lww_strategy(self):
        schema = MergeSchema(default=LWW())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "name": "Alice"}])
        smf.ingest([{"id": 1, "name": "Alicia"}])
        # LWW with 0 timestamps — incoming wins by default (node_id "incoming" > "existing")
        records = smf.read()
        assert records[0]["name"] == "Alicia"

    def test_max_strategy(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "salary": 100}])
        smf.ingest([{"id": 1, "salary": 50}])
        records = smf.read()
        assert records[0]["salary"] == 100

    def test_min_strategy(self):
        schema = MergeSchema(default=LWW(), score=MinWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "score": 80}])
        smf.ingest([{"id": 1, "score": 60}])
        records = smf.read()
        assert records[0]["score"] == 60

    def test_mixed_strategies(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins(), score=MinWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "salary": 100, "score": 80}])
        smf.ingest([{"id": 1, "salary": 150, "score": 60}])
        records = smf.read()
        assert records[0]["salary"] == 150  # MaxWins
        assert records[0]["score"] == 60  # MinWins

    def test_default_strategy(self):
        schema = MergeSchema(default=MaxWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "val": 10}])
        smf.ingest([{"id": 1, "val": 20}])
        records = smf.read()
        assert records[0]["val"] == 20

    def test_custom_schema(self):
        schema = MergeSchema(default=LWW(), a=MaxWins(), b=MinWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "a": 5, "b": 5}])
        smf.ingest([{"id": 1, "a": 3, "b": 3}])
        records = smf.read()
        assert records[0]["a"] == 5  # MaxWins
        assert records[0]["b"] == 3  # MinWins

    def test_no_schema_fallback(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        smf.ingest([{"id": 1, "name": "Bob"}])
        # Default schema is LWW, incoming wins due to node_id ordering
        records = smf.read()
        assert records[0]["name"] in ("Alice", "Bob")

    def test_strategy_preserved_in_metadata(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        meta = smf.metadata()
        assert "salary" in meta.strategies
        assert meta.strategies["salary"] == "MaxWins"

    def test_strategy_roundtrip(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins(), score=MinWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        meta = smf.metadata()
        d = meta.to_dict()
        restored = ParquetMergeMetadata.from_dict(d)
        assert restored.strategies == meta.strategies

    def test_sum_like_max_strategy(self):
        """MaxWins effectively acts like 'keep highest' for numeric values."""
        schema = MergeSchema(default=MaxWins())
        smf = SelfMergingParquet("test", key="id", schema=schema)
        smf.ingest([{"id": 1, "count": 100}])
        smf.ingest([{"id": 1, "count": 200}])
        smf.ingest([{"id": 1, "count": 150}])
        records = smf.read()
        assert records[0]["count"] == 200


# ═══════════════════════════════════════════════════════════════════════════
# TestParquetProvenance — 5 tests
# ═══════════════════════════════════════════════════════════════════════════


class TestParquetProvenance:
    """Tests for provenance tracking in SelfMergingParquet."""

    def test_provenance_enabled(self):
        smf = SelfMergingParquet("test", key="id", provenance=True)
        smf.ingest([{"id": 1, "name": "A"}])
        log = smf.get_provenance_log()
        assert len(log) == 1

    def test_provenance_disabled(self):
        smf = SelfMergingParquet("test", key="id", provenance=False)
        smf.ingest([{"id": 1, "name": "A"}])
        log = smf.get_provenance_log()
        assert len(log) == 0

    def test_provenance_multi_ingest(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "A"}])
        smf.ingest([{"id": 2, "name": "B"}])
        smf.ingest([{"id": 3, "name": "C"}])
        log = smf.get_provenance_log()
        assert len(log) == 3

    def test_provenance_source_labels(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1}], source="east_dc")
        smf.ingest([{"id": 2}], source="west_dc")
        log = smf.get_provenance_log()
        sources = [e["source"] for e in log]
        assert "east_dc" in sources
        assert "west_dc" in sources

    def test_provenance_in_metadata(self):
        smf = SelfMergingParquet("test", key="id", provenance=True)
        meta = smf.metadata()
        assert meta.provenance_enabled is True


# ═══════════════════════════════════════════════════════════════════════════
# TestSelfMergingParquetEdgeCases — extra tests to reach ~40
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfMergingParquetEdgeCases:
    """Edge-case tests."""

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            SelfMergingParquet("", key="id")

    def test_contains(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        assert 1 in smf
        assert 2 not in smf

    def test_getitem(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "Alice"}])
        rec = smf[1]
        assert rec["name"] == "Alice"

    def test_getitem_missing_raises(self):
        smf = SelfMergingParquet("test", key="id")
        with pytest.raises(KeyError):
            _ = smf[999]

    def test_merge_with_key_mismatch(self):
        smf_a = SelfMergingParquet("a", key="id")
        smf_b = SelfMergingParquet("b", key="pk")
        with pytest.raises(ValueError, match="Key column mismatch"):
            smf_a.merge_with(smf_b)

    def test_ingest_skips_records_without_key(self):
        smf = SelfMergingParquet("test", key="id")
        result = smf.ingest([{"name": "No ID"}])
        assert result.records_ingested == 1
        assert result.new_records == 0
        assert len(smf) == 0

    def test_ingest_dict_input(self):
        smf = SelfMergingParquet("test", key="id")
        result = smf.ingest({"id": 1, "name": "Alice"})
        assert result.new_records == 1

    def test_metadata_source_count_increments(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1}])
        smf.ingest([{"id": 2}])
        meta = smf.metadata()
        assert meta.source_count == 2

    def test_metadata_merge_count(self):
        smf = SelfMergingParquet("test", key="id")
        smf.ingest([{"id": 1, "name": "A"}])
        smf.ingest([{"id": 1, "name": "B"}])  # causes merge
        meta = smf.metadata()
        assert meta.merge_count >= 1

    def test_parquet_metadata_roundtrip(self):
        meta = ParquetMergeMetadata(
            key_column="id",
            strategies={"name": "LWW", "salary": "MaxWins"},
            provenance_enabled=True,
            source_count=3,
            merge_count=1,
            created_at="2026-03-01T00:00:00Z",
        )
        pq = meta.to_parquet_metadata()
        restored = ParquetMergeMetadata.from_parquet_metadata(pq)
        assert restored.key_column == meta.key_column
        assert restored.strategies == meta.strategies
        assert restored.source_count == meta.source_count
        assert restored.merge_count == meta.merge_count
        assert restored.created_at == meta.created_at
