"""Tests for crdt_merge.streaming — Streaming Merge Pipeline."""
import pytest
import time
import sys
from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet


def gen_rows(n, prefix="a", start=0):
    """Generate n rows with predictable keys."""
    for i in range(start, start + n):
        yield {
            "id": f"row-{i}",
            "value": f"{prefix}-{i}",
            "score": i,
            "tags": f"{prefix}",
            "_ts": float(i),
        }


# ===========================================================================
# Basic Functionality
# ===========================================================================

class TestMergeStream:
    def test_disjoint_sources(self):
        """Two sources with no overlap — should union all."""
        a = list(gen_rows(10, "a", start=0))
        b = list(gen_rows(10, "b", start=10))
        result = []
        for batch in merge_stream(a, b, key="id", batch_size=5):
            result.extend(batch)
        assert len(result) == 20

    def test_full_overlap(self):
        """Both sources have same keys — merge every row."""
        a = list(gen_rows(10, "a", start=0))
        b = list(gen_rows(10, "b", start=0))
        result = []
        for batch in merge_stream(a, b, key="id", batch_size=5):
            result.extend(batch)
        assert len(result) == 10

    def test_partial_overlap(self):
        """50% overlap."""
        a = list(gen_rows(10, "a", start=0))
        b = list(gen_rows(10, "b", start=5))
        result = []
        for batch in merge_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 15

    def test_empty_sources(self):
        """Both empty."""
        result = list(merge_stream([], [], key="id"))
        assert result == []

    def test_one_empty(self):
        """One source empty, other has data."""
        a = list(gen_rows(5, "a"))
        result = []
        for batch in merge_stream(a, [], key="id"):
            result.extend(batch)
        assert len(result) == 5

    def test_batch_size_1(self):
        """Extreme: process one row at a time."""
        a = list(gen_rows(5, "a", start=0))
        b = list(gen_rows(5, "b", start=0))
        batches = list(merge_stream(a, b, key="id", batch_size=1))
        total = sum(len(b) for b in batches)
        assert total == 5

    def test_batch_size_larger_than_data(self):
        """Batch size exceeds data — should still work."""
        a = list(gen_rows(3, "a", start=0))
        b = list(gen_rows(3, "b", start=3))  # disjoint keys
        result = []
        for batch in merge_stream(a, b, key="id", batch_size=10000):
            result.extend(batch)
        assert len(result) == 6


class TestMergeStreamWithSchema:
    def test_schema_applied(self):
        """Schema strategies should be applied during merge."""
        schema = MergeSchema(
            default=LWW(),
            score=MaxWins(),
            tags=UnionSet(separator=","),
        )
        a = [{"id": "1", "score": 10, "tags": "x", "name": "old", "_ts": 1.0}]
        b = [{"id": "1", "score": 5, "tags": "y", "name": "new", "_ts": 2.0}]
        result = []
        for batch in merge_stream(a, b, key="id", schema=schema, timestamp_col="_ts"):
            result.extend(batch)
        assert len(result) == 1
        row = result[0]
        assert row["score"] == 10  # MaxWins
        assert row["name"] == "new"  # LWW: ts_b > ts_a
        # tags should be union
        tag_set = set(row["tags"].split(","))
        assert "x" in tag_set and "y" in tag_set


class TestMergeSortedStream:
    def test_sorted_merge(self):
        """Pre-sorted sources should merge correctly."""
        a = [{"id": f"row-{i:04d}", "val": "a"} for i in range(10)]
        b = [{"id": f"row-{i:04d}", "val": "b"} for i in range(5, 15)]
        result = []
        for batch in merge_sorted_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 15  # 0-14 unique keys

    def test_sorted_preserves_order(self):
        """Output should be in key order."""
        a = [{"id": f"row-{i:04d}", "val": "a"} for i in range(0, 20, 2)]
        b = [{"id": f"row-{i:04d}", "val": "b"} for i in range(1, 20, 2)]
        result = []
        for batch in merge_sorted_stream(a, b, key="id"):
            result.extend(batch)
        ids = [r["id"] for r in result]
        assert ids == sorted(ids)


# ===========================================================================
# Generators (True Streaming)
# ===========================================================================

class TestGeneratorSources:
    def test_generator_input(self):
        """Sources can be generators, not just lists."""
        result = []
        for batch in merge_stream(gen_rows(100, "a", start=0), gen_rows(100, "b", start=100), key="id"):
            result.extend(batch)
        assert len(result) == 200

    def test_large_generator(self):
        """10K rows from generators — must not OOM."""
        result_count = 0
        for batch in merge_stream(gen_rows(5000, "a", start=0), gen_rows(5000, "b", start=5000), key="id", batch_size=500):
            result_count += len(batch)
        assert result_count == 10000

    def test_generator_overlap(self):
        """Generators with same keys."""
        result = []
        for batch in merge_stream(gen_rows(100, "a", 0), gen_rows(100, "b", 0), key="id"):
            result.extend(batch)
        assert len(result) == 100


# ===========================================================================
# StreamStats
# ===========================================================================

class TestStreamStats:
    def test_stats_returned(self):
        """merge_stream should optionally return stats."""
        a = list(gen_rows(10, "a", 0))
        b = list(gen_rows(10, "b", 0))
        stats = StreamStats()
        result = []
        for batch in merge_stream(a, b, key="id", stats=stats):
            result.extend(batch)
        assert stats.rows_processed > 0
        assert stats.batches_processed > 0
        assert stats.duration_ms > 0


# ===========================================================================
# Memory Efficiency (Sanity Check)
# ===========================================================================

class TestMemoryEfficiency:
    def test_does_not_hold_all_in_memory(self):
        """Verify streaming doesn't accumulate everything."""
        import tracemalloc
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]

        count = 0
        for batch in merge_stream(gen_rows(5000, "a", start=0), gen_rows(5000, "b", start=5000), key="id", batch_size=100):
            count += len(batch)
            # Don't accumulate — just count

        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        assert count == 10000
        # Peak should be well under what holding 10K rows would take
        # Each row is ~200 bytes, 10K = ~2MB. Peak should be << 2MB
        # (batch of 100 rows ≈ 20KB)
        # Give generous margin for Python overhead
        assert peak < 10_000_000, f"Peak memory {peak/1e6:.1f}MB — too high for streaming"


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    def test_single_row_each(self):
        a = [{"id": "1", "v": "a"}]
        b = [{"id": "1", "v": "b"}]
        result = []
        for batch in merge_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 1

    def test_unicode_keys(self):
        a = [{"id": "日本語", "v": "a"}]
        b = [{"id": "日本語", "v": "b"}]
        result = []
        for batch in merge_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 1

    def test_numeric_keys(self):
        a = [{"id": i, "v": "a"} for i in range(5)]
        b = [{"id": i, "v": "b"} for i in range(5)]
        result = []
        for batch in merge_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 5

    def test_missing_columns(self):
        """Rows with different column sets."""
        a = [{"id": "1", "name": "alice"}]
        b = [{"id": "1", "score": 100}]
        result = []
        for batch in merge_stream(a, b, key="id"):
            result.extend(batch)
        assert len(result) == 1
        row = result[0]
        assert row["name"] == "alice"
        assert row["score"] == 100
