# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""Tests for crdt_merge.arrow — Arrow-native merge engine.

Requires pyarrow. Tests are skipped when pyarrow is not installed.
"""

from __future__ import annotations

import os
import tempfile
import time
from unittest import mock

import pytest

try:
    import pyarrow as pa
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

pytestmark = pytest.mark.skipif(not HAS_PYARROW, reason="pyarrow not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_left():
    """Simple left table: id, name, score."""
    return pa.table({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "score": [10, 20, 30],
    })


@pytest.fixture
def simple_right():
    """Simple right table: id, name, score — overlaps with left on id=2,3."""
    return pa.table({
        "id": [2, 3, 4],
        "name": ["Bobby", "Charlie", "Diana"],
        "score": [25, 35, 40],
    })


@pytest.fixture
def engine():
    """Default ArrowMerge engine (no schema, no timestamp)."""
    from crdt_merge.arrow import ArrowMerge
    return ArrowMerge()


@pytest.fixture
def tmpdir():
    """Temporary directory for IPC file tests."""
    with tempfile.TemporaryDirectory() as d:
        yield d


# ===========================================================================
# 1. ArrowMerge basic (5 tests)
# ===========================================================================


class TestArrowMergeBasic:
    """Basic ArrowMerge creation and merge tests."""

    def test_create_engine(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        assert eng.schema is None
        assert eng.timestamp_col is None

    def test_create_engine_with_schema(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, MaxWins
        schema = MergeSchema(default=MaxWins())
        eng = ArrowMerge(schema=schema, timestamp_col="_ts")
        assert eng.schema is schema
        assert eng.timestamp_col == "_ts"

    def test_merge_with_key(self, engine, simple_left, simple_right):
        result = engine.merge(simple_left, simple_right, key="id")
        assert isinstance(result, pa.Table)
        ids = sorted(result.column("id").to_pylist())
        assert ids == [1, 2, 3, 4]

    def test_merge_without_key(self, engine, simple_left, simple_right):
        result = engine.merge(simple_left, simple_right)
        assert isinstance(result, pa.Table)
        # Concat + dedup: unique rows
        assert len(result) >= 4  # at least 4 unique rows

    def test_merge_empty_tables(self, engine):
        left = pa.table({"id": pa.array([], type=pa.int64()),
                         "val": pa.array([], type=pa.string())})
        right = pa.table({"id": pa.array([], type=pa.int64()),
                          "val": pa.array([], type=pa.string())})
        result = engine.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        assert len(result) == 0


# ===========================================================================
# 2. Strategy application (8 tests)
# ===========================================================================


class TestStrategyApplication:
    """Verify all 8 strategy types work with Arrow tables."""

    def _make_tables(self, left_val, right_val):
        left = pa.table({"id": [1], "val": [left_val]})
        right = pa.table({"id": [1], "val": [right_val]})
        return left, right

    def test_lww_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, LWW
        schema = MergeSchema(default=LWW())
        eng = ArrowMerge(schema=schema, timestamp_col="_ts")
        left = pa.table({"id": [1], "val": ["old"], "_ts": [1.0]})
        right = pa.table({"id": [1], "val": ["new"], "_ts": [2.0]})
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == ["new"]

    def test_max_wins_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, MaxWins
        schema = MergeSchema(val=MaxWins())
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables(10, 20)
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == [20]

    def test_min_wins_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, MinWins
        schema = MergeSchema(val=MinWins())
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables(10, 20)
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == [10]

    def test_concat_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, Concat
        schema = MergeSchema(val=Concat(separator=" | "))
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables("hello", "world")
        result = eng.merge(left, right, key="id")
        val = result.column("val").to_pylist()[0]
        assert "hello" in val
        assert "world" in val

    def test_union_set_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, UnionSet
        schema = MergeSchema(val=UnionSet(separator=","))
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables("a,b", "b,c")
        result = eng.merge(left, right, key="id")
        val = result.column("val").to_pylist()[0]
        parts = sorted(val.split(","))
        assert parts == ["a", "b", "c"]

    def test_priority_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, Priority
        schema = MergeSchema(val=Priority(["draft", "review", "published"]))
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables("draft", "published")
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == ["published"]

    def test_custom_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, Custom
        schema = MergeSchema(val=Custom(lambda a, b: f"{a}+{b}" if a < b else f"{b}+{a}"))
        eng = ArrowMerge(schema=schema)
        left, right = self._make_tables("x", "y")
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == ["x+y"]

    def test_merge_schema_multi_strategy(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, MaxWins, MinWins, LWW
        schema = MergeSchema(default=LWW(), high=MaxWins(), low=MinWins())
        eng = ArrowMerge(schema=schema)
        left = pa.table({"id": [1], "high": [10], "low": [100]})
        right = pa.table({"id": [1], "high": [20], "low": [50]})
        result = eng.merge(left, right, key="id")
        assert result.column("high").to_pylist() == [20]
        assert result.column("low").to_pylist() == [50]


# ===========================================================================
# 3. Schema evolution (5 tests)
# ===========================================================================


class TestSchemaEvolution:
    """Merge tables with different column sets."""

    def test_union_adds_missing_columns(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "a": [10]})
        right = pa.table({"id": [1], "b": [20]})
        result = eng.merge(left, right, key="id")
        assert "a" in result.column_names
        assert "b" in result.column_names

    def test_missing_columns_filled_with_null(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1, 2], "a": [10, 20]})
        right = pa.table({"id": [3], "b": ["x"]})
        result = eng.merge(left, right, key="id")
        # Row 1 and 2 should have null for 'b'
        rows = result.to_pylist()
        row1 = [r for r in rows if r["id"] == 1][0]
        assert row1.get("b") is None

    def test_schema_evolution_different_columns(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "x": [100]})
        right = pa.table({"id": [2], "y": ["hello"]})
        result = eng.merge(left, right, key="id")
        assert set(result.column_names) >= {"id", "x", "y"}
        assert len(result) == 2

    def test_type_widening_int_float(self):
        """Tables with int64 and float64 for same column should merge."""
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "val": pa.array([10], type=pa.int64())})
        right = pa.table({"id": [2], "val": pa.array([20.5], type=pa.float64())})
        result = eng.merge(left, right, key="id")
        assert len(result) == 2
        assert "val" in result.column_names

    def test_completely_disjoint_schemas(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "a": [1], "b": [2]})
        right = pa.table({"id": [2], "c": [3], "d": [4]})
        result = eng.merge(left, right, key="id")
        assert set(result.column_names) >= {"id", "a", "b", "c", "d"}


# ===========================================================================
# 4. RecordBatch (3 tests)
# ===========================================================================


class TestRecordBatch:
    """Merge with RecordBatch inputs."""

    def test_merge_record_batches(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.record_batch({"id": [1, 2], "val": [10, 20]})
        right = pa.record_batch({"id": [2, 3], "val": [25, 30]})
        result = eng.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        assert len(result) == 3

    def test_merge_mixed_table_batch(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1, 2], "val": [10, 20]})
        right = pa.record_batch({"id": [2, 3], "val": [25, 30]})
        result = eng.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        assert len(result) == 3

    def test_merge_batch_and_table(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.record_batch({"id": [1], "val": [10]})
        right = pa.table({"id": [2], "val": [20]})
        result = eng.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        assert len(result) == 2


# ===========================================================================
# 5. Fallback (3 tests)
# ===========================================================================


class TestFallback:
    """arrow_merge fallback and conversion tests."""

    def test_arrow_merge_with_lists(self):
        from crdt_merge.arrow import arrow_merge
        left = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
        right = [{"id": 2, "val": "c"}, {"id": 3, "val": "d"}]
        result = arrow_merge(left, right, key="id")
        # With pyarrow available, should return pa.Table
        assert isinstance(result, pa.Table)
        assert len(result) == 3

    def test_arrow_merge_fallback_no_pyarrow(self):
        """When pyarrow is unavailable, arrow_merge falls back to dataframe.merge."""
        import crdt_merge.arrow as arrow_mod
        with mock.patch.object(arrow_mod, '_has_pyarrow', return_value=False):
            left = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
            right = [{"id": 2, "val": "c"}, {"id": 3, "val": "d"}]
            result = arrow_mod.arrow_merge(left, right, key="id")
            # Fallback returns list[dict]
            assert isinstance(result, list)
            assert len(result) == 3

    def test_has_pyarrow_check(self):
        from crdt_merge.arrow import _has_pyarrow
        assert _has_pyarrow() is True


# ===========================================================================
# 6. Streaming (4 tests)
# ===========================================================================


class TestStreaming:
    """Streaming batch merge tests."""

    def test_merge_batches_basic(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        batches = [
            pa.record_batch({"id": [1, 2], "val": [10, 20]}),
            pa.record_batch({"id": [3, 4], "val": [30, 40]}),
        ]
        results = list(eng.merge_batches(iter(batches), key="id", batch_size=10))
        assert len(results) >= 1
        total_rows = sum(len(b) for b in results)
        assert total_rows == 4

    def test_merge_batches_yields_correct_size(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        batches = [
            pa.record_batch({"id": list(range(i * 5, (i + 1) * 5)),
                             "val": list(range(i * 5, (i + 1) * 5))})
            for i in range(4)
        ]
        results = list(eng.merge_batches(iter(batches), key="id", batch_size=10))
        assert len(results) >= 1
        total_rows = sum(len(b) for b in results)
        assert total_rows == 20

    def test_merge_batches_empty_input(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        results = list(eng.merge_batches(iter([]), key="id"))
        assert results == []

    def test_merge_batches_single_batch(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        batches = [
            pa.record_batch({"id": [1, 2, 3], "val": [10, 20, 30]})
        ]
        results = list(eng.merge_batches(iter(batches), key="id", batch_size=100))
        assert len(results) == 1
        assert len(results[0]) == 3


# ===========================================================================
# 7. IPC (4 tests)
# ===========================================================================


class TestIPC:
    """IPC file merge tests."""

    def _write_ipc(self, table, path):
        writer = pa.ipc.new_file(path, table.schema)
        writer.write_table(table)
        writer.close()

    def test_merge_ipc_creates_output(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1, 2], "val": [10, 20]})
        right = pa.table({"id": [2, 3], "val": [25, 30]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")
        op = os.path.join(tmpdir, "out.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        stats = eng.merge_ipc(lp, rp, op, key="id")
        assert os.path.exists(op)

    def test_merge_ipc_correct_row_counts(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1, 2], "val": [10, 20]})
        right = pa.table({"id": [2, 3], "val": [25, 30]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")
        op = os.path.join(tmpdir, "out.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        stats = eng.merge_ipc(lp, rp, op, key="id")
        assert stats["rows_left"] == 2
        assert stats["rows_right"] == 2
        assert stats["rows_merged"] == 3

    def test_merge_ipc_stats_dict(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1], "val": [10]})
        right = pa.table({"id": [2], "val": [20]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")
        op = os.path.join(tmpdir, "out.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        stats = eng.merge_ipc(lp, rp, op, key="id")
        assert set(stats.keys()) == {"rows_left", "rows_right", "rows_merged", "output_path"}
        assert stats["output_path"] == op

    def test_merge_ipc_output_readable(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1, 2], "val": [10, 20]})
        right = pa.table({"id": [3], "val": [30]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")
        op = os.path.join(tmpdir, "out.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        eng.merge_ipc(lp, rp, op, key="id")

        # Read back
        reader = pa.ipc.open_file(op)
        merged = reader.read_all()
        assert len(merged) == 3


# ===========================================================================
# 8. Memory-mapped (2 tests)
# ===========================================================================


class TestMemoryMapped:
    """Memory-mapped file merge tests."""

    def _write_ipc(self, table, path):
        writer = pa.ipc.new_file(path, table.schema)
        writer.write_table(table)
        writer.close()

    def test_memory_mapped_basic(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1, 2], "val": [10, 20]})
        right = pa.table({"id": [2, 3], "val": [25, 30]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        result = eng.merge_memory_mapped(lp, rp, key="id")
        assert isinstance(result, pa.Table)
        assert len(result) == 3

    def test_memory_mapped_no_key(self, tmpdir):
        from crdt_merge.arrow import ArrowMerge
        left = pa.table({"id": [1], "val": [10]})
        right = pa.table({"id": [2], "val": [20]})

        lp = os.path.join(tmpdir, "left.arrow")
        rp = os.path.join(tmpdir, "right.arrow")

        self._write_ipc(left, lp)
        self._write_ipc(right, rp)

        eng = ArrowMerge()
        result = eng.merge_memory_mapped(lp, rp)
        assert isinstance(result, pa.Table)
        assert len(result) == 2


# ===========================================================================
# 9. Null handling (3 tests)
# ===========================================================================


class TestNullHandling:
    """Null/None value handling."""

    def test_null_in_key_column(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1, None], "val": [10, 20]})
        right = pa.table({"id": [1, 3], "val": [15, 30]})
        result = eng.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        # Should have: matched id=1, left-only None row, right-only id=3
        assert len(result) >= 3

    def test_null_in_value_columns(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1, 2], "val": [None, 20]})
        right = pa.table({"id": [1, 2], "val": [10, None]})
        result = eng.merge(left, right, key="id")
        rows = result.to_pylist()
        row1 = [r for r in rows if r["id"] == 1][0]
        row2 = [r for r in rows if r["id"] == 2][0]
        # None on one side → take the non-None value
        assert row1["val"] == 10
        assert row2["val"] == 20

    def test_all_null_column(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1, 2], "val": [None, None]})
        right = pa.table({"id": [1, 2], "val": [None, None]})
        result = eng.merge(left, right, key="id")
        vals = result.column("val").to_pylist()
        assert all(v is None for v in vals)


# ===========================================================================
# 10. Edge cases (5 tests)
# ===========================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_left_table(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": pa.array([], type=pa.int64()),
                         "val": pa.array([], type=pa.int64())})
        right = pa.table({"id": [1, 2], "val": [10, 20]})
        result = eng.merge(left, right, key="id")
        assert len(result) == 2

    def test_single_row_tables(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "val": [10]})
        right = pa.table({"id": [1], "val": [20]})
        result = eng.merge(left, right, key="id")
        assert len(result) == 1

    def test_mismatched_schemas_no_key(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"a": [1], "b": [2]})
        right = pa.table({"b": [3], "c": [4]})
        result = eng.merge(left, right)
        assert isinstance(result, pa.Table)
        assert "a" in result.column_names
        assert "c" in result.column_names

    def test_large_merge_10k_rows(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        n = 10000
        left = pa.table({"id": list(range(n)), "val": list(range(n))})
        right = pa.table({"id": list(range(n // 2, n + n // 2)),
                          "val": list(range(n, n + n))})
        result = eng.merge(left, right, key="id")
        assert isinstance(result, pa.Table)
        # n unique left + n//2 unique right = n + n//2
        assert len(result) == n + n // 2

    def test_timestamp_col_resolution(self):
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, LWW
        schema = MergeSchema(default=LWW())
        eng = ArrowMerge(schema=schema, timestamp_col="_ts")
        left = pa.table({"id": [1], "val": ["old"], "_ts": [1.0]})
        right = pa.table({"id": [1], "val": ["new"], "_ts": [2.0]})
        result = eng.merge(left, right, key="id")
        assert result.column("val").to_pylist() == ["new"]


# ===========================================================================
# 11. Performance (2 tests)
# ===========================================================================


class TestPerformance:
    """Timing-based tests."""

    def test_arrow_merge_performance_10k(self):
        """Arrow merge should complete 10K rows in under 10 seconds."""
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        n = 10000
        left = pa.table({"id": list(range(n)),
                          "val": [f"left_{i}" for i in range(n)]})
        right = pa.table({"id": list(range(n // 2, n + n // 2)),
                           "val": [f"right_{i}" for i in range(n)]})
        t0 = time.perf_counter()
        result = eng.merge(left, right, key="id")
        elapsed = time.perf_counter() - t0
        assert elapsed < 10.0, f"Arrow merge took {elapsed:.2f}s for 10K rows"
        assert len(result) == n + n // 2

    def test_benchmark_helper(self):
        """benchmark_arrow_merge should return valid results."""
        from crdt_merge.arrow import benchmark_arrow_merge
        stats = benchmark_arrow_merge(num_rows=500, num_cols=3)
        assert "arrow_time_ms" in stats
        assert "dict_time_ms" in stats
        assert "speedup" in stats
        assert stats["rows"] > 0


# ===========================================================================
# 12. Serialization (1 test)
# ===========================================================================


class TestSerialization:
    """Output type validation."""

    def test_output_is_valid_pa_table(self, engine, simple_left, simple_right):
        result = engine.merge(simple_left, simple_right, key="id")
        assert isinstance(result, pa.Table)
        # Verify schema and data are accessible
        assert result.num_rows == 4
        assert result.num_columns > 0
        # Should be convertible to pylist
        rows = result.to_pylist()
        assert len(rows) == 4


# ===========================================================================
# 13. Error handling (3 tests)
# ===========================================================================


class TestErrorHandling:
    """Error condition tests."""

    def test_invalid_key_column(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        left = pa.table({"id": [1], "val": [10]})
        right = pa.table({"id": [2], "val": [20]})
        with pytest.raises(ValueError, match="Key column"):
            eng.merge(left, right, key="nonexistent")

    def test_wrong_input_type(self):
        from crdt_merge.arrow import ArrowMerge
        eng = ArrowMerge()
        with pytest.raises(TypeError):
            eng.merge("not a table", pa.table({"id": [1]}), key="id")

    def test_import_error_message(self):
        """_import_pyarrow should give a clear message when missing."""
        from crdt_merge.arrow import _import_pyarrow
        # Just verify it works when pyarrow IS available
        pa_mod = _import_pyarrow()
        assert pa_mod is not None


# ===========================================================================
# 14. CRDT compliance (2 tests)
# ===========================================================================


class TestCRDTCompliance:
    """Verify Arrow merge satisfies CRDT properties."""

    def test_commutativity(self):
        """merge(A, B) should produce same result as merge(B, A) with commutative strategy.

        Note: The default LWW strategy uses node-id tiebreak which is order-
        dependent when timestamps are equal.  We use MaxWins here which is
        truly commutative: max(a, b) == max(b, a).
        """
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, MaxWins
        schema = MergeSchema(default=MaxWins())
        eng = ArrowMerge(schema=schema)
        left = pa.table({"id": [1, 2, 3], "val": [10, 20, 30]})
        right = pa.table({"id": [2, 3, 4], "val": [25, 35, 40]})
        r1 = eng.merge(left, right, key="id")
        r2 = eng.merge(right, left, key="id")

        # Sort by id for comparison
        r1_rows = sorted(r1.to_pylist(), key=lambda x: x["id"])
        r2_rows = sorted(r2.to_pylist(), key=lambda x: x["id"])
        assert r1_rows == r2_rows

    def test_arrow_matches_dict_merge(self):
        """Arrow merge should produce same results as dataframe merge."""
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.dataframe import merge as df_merge
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(score=MaxWins())

        left_data = [
            {"id": 1, "name": "Alice", "score": 10},
            {"id": 2, "name": "Bob", "score": 20},
        ]
        right_data = [
            {"id": 2, "name": "Bobby", "score": 25},
            {"id": 3, "name": "Charlie", "score": 30},
        ]

        # Arrow merge
        eng = ArrowMerge(schema=schema)
        left_table = pa.Table.from_pylist(left_data)
        right_table = pa.Table.from_pylist(right_data)
        arrow_result = sorted(
            eng.merge(left_table, right_table, key="id").to_pylist(),
            key=lambda x: x["id"]
        )

        # Dict merge
        dict_result = sorted(
            df_merge(left_data, right_data, key="id", schema=schema),
            key=lambda x: x["id"]
        )

        assert len(arrow_result) == len(dict_result)
        for ar, dr in zip(arrow_result, dict_result):
            assert ar["id"] == dr["id"]
            assert ar["score"] == dr["score"]


# ===========================================================================
# Additional utility tests
# ===========================================================================


class TestUtilities:
    """Tests for utility functions."""

    def test_arrow_schema_info(self):
        from crdt_merge.arrow import arrow_schema_info
        table = pa.table({"id": [1], "name": ["Alice"]})
        info = arrow_schema_info(table)
        assert "id" in info
        assert "name" in info

    def test_compare_arrow_schemas_compatible(self):
        from crdt_merge.arrow import compare_arrow_schemas
        left = pa.table({"id": [1], "name": ["a"]})
        right = pa.table({"id": [2], "name": ["b"]})
        diff = compare_arrow_schemas(left, right)
        assert diff["compatible"] is True
        assert diff["only_left"] == []
        assert diff["only_right"] == []

    def test_compare_arrow_schemas_incompatible(self):
        from crdt_merge.arrow import compare_arrow_schemas
        left = pa.table({"id": [1], "a": [1]})
        right = pa.table({"id": [2], "b": [2]})
        diff = compare_arrow_schemas(left, right)
        assert diff["compatible"] is False
        assert "a" in diff["only_left"]
        assert "b" in diff["only_right"]

    def test_write_read_ipc(self, tmpdir):
        from crdt_merge.arrow import write_ipc, read_ipc
        table = pa.table({"id": [1, 2, 3], "val": ["a", "b", "c"]})
        path = os.path.join(tmpdir, "test.arrow")
        write_ipc(table, path)
        loaded = read_ipc(path)
        assert loaded.equals(table)

    def test_table_to_batches(self):
        from crdt_merge.arrow import table_to_batches
        table = pa.table({"id": list(range(25)), "val": list(range(25))})
        batches = table_to_batches(table, batch_size=10)
        assert len(batches) == 3  # 10 + 10 + 5
        total = sum(len(b) for b in batches)
        assert total == 25

    def test_arrow_merge_tables(self):
        from crdt_merge.arrow import arrow_merge_tables
        t1 = pa.table({"id": [1, 2], "val": [10, 20]})
        t2 = pa.table({"id": [2, 3], "val": [25, 30]})
        t3 = pa.table({"id": [3, 4], "val": [35, 40]})
        result = arrow_merge_tables([t1, t2, t3], key="id")
        assert isinstance(result, pa.Table)
        ids = sorted(result.column("id").to_pylist())
        assert ids == [1, 2, 3, 4]
