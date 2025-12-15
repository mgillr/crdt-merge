# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.accelerators.duckdb_udf — DuckDB UDF wrapper.

All DuckDB interactions are mocked; duckdb is NOT required to run these tests.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from crdt_merge.accelerators.duckdb_udf import (
    DuckDBMergeUDF,
    DuckDBMergeQLExtension,
    _merge_records,
    _diff_records,
    _resolve_strategy,
    _records_from_relation,
)
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins
from crdt_merge.accelerators import ACCELERATOR_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_relation(columns, rows):
    """Build a mock DuckDB relation."""
    rel = MagicMock()
    rel.columns = columns
    rel.fetchall.return_value = rows
    return rel


def _mock_conn(tables=None):
    """Build a mock DuckDB connection with optional tables."""
    conn = MagicMock()
    table_data = tables or {}

    def sql_side_effect(query):
        for tbl, (cols, rows) in table_data.items():
            if tbl in query:
                return _mock_relation(cols, rows)
        return _mock_relation([], [])

    conn.sql.side_effect = sql_side_effect
    return conn


# ===================================================================
# TestDuckDBMergeUDF — 25 tests
# ===================================================================

class TestDuckDBMergeUDF:
    def test_init_no_connection(self):
        udf = DuckDBMergeUDF()
        assert udf._conn is None

    def test_init_with_connection(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        assert udf._conn is conn

    def test_init_with_schema(self):
        schema = MergeSchema(default=MaxWins())
        udf = DuckDBMergeUDF(schema=schema)
        assert udf._schema.default.name() == "MaxWins"

    def test_is_available(self):
        udf = DuckDBMergeUDF()
        # Without duckdb installed, returns False (or True if installed)
        result = udf.is_available()
        assert isinstance(result, bool)

    def test_register(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        assert udf._registered is True

    def test_unregister(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        udf.unregister()
        assert udf._registered is False

    def test_health_check(self):
        udf = DuckDBMergeUDF()
        hc = udf.health_check()
        assert hc["name"] == "duckdb_udf"
        assert hc["version"] == "0.7.0"
        assert "duckdb_available" in hc

    def test_registered_in_accelerator_registry(self):
        assert "duckdb_udf" in ACCELERATOR_REGISTRY

    def test_merge_tables_basic(self):
        conn = _mock_conn({
            "t1": (["id", "v"], [(1, "a"), (2, "b")]),
            "t2": (["id", "v"], [(1, "c"), (3, "d")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("t1", "t2", key="id")
        ids = {r["id"] for r in result}
        assert ids == {1, 2, 3}

    def test_merge_tables_with_max_strategy(self):
        conn = _mock_conn({
            "t1": (["id", "score"], [(1, 50)]),
            "t2": (["id", "score"], [(1, 80)]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("t1", "t2", key="id", strategies={"score": "max"})
        assert result[0]["score"] == 80

    def test_merge_tables_with_min_strategy(self):
        conn = _mock_conn({
            "t1": (["id", "score"], [(1, 50)]),
            "t2": (["id", "score"], [(1, 80)]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("t1", "t2", key="id", strategies={"score": "min"})
        assert result[0]["score"] == 50

    def test_diff_tables(self):
        conn = _mock_conn({
            "t1": (["id", "v"], [(1, "a"), (2, "b")]),
            "t2": (["id", "v"], [(2, "b"), (3, "c")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        diff = udf.diff_tables("t1", "t2", key="id")
        assert len(diff["added"]) == 1
        assert len(diff["removed"]) == 1
        assert diff["unchanged_count"] == 1

    def test_merge_results(self):
        left = _mock_relation(["id", "v"], [(1, "x")])
        right = _mock_relation(["id", "v"], [(1, "y"), (2, "z")])
        udf = DuckDBMergeUDF()
        result = udf.merge_results(left, right, key="id")
        assert len(result) == 2

    def test_register_custom_strategy(self):
        udf = DuckDBMergeUDF()
        udf.register_strategy("double", lambda a, b: a * 2)
        assert "double" in udf._custom_strategies

    def test_register_strategy_empty_name(self):
        udf = DuckDBMergeUDF()
        with pytest.raises(ValueError):
            udf.register_strategy("", lambda a, b: a)

    def test_get_strategy_info_builtin(self):
        udf = DuckDBMergeUDF()
        info = udf.get_strategy_info("lww")
        assert info["type"] == "builtin"

    def test_get_strategy_info_custom(self):
        udf = DuckDBMergeUDF()
        udf.register_strategy("custom1", lambda a, b: a)
        info = udf.get_strategy_info("custom1")
        assert info["type"] == "custom"

    def test_get_strategy_info_unknown(self):
        udf = DuckDBMergeUDF()
        with pytest.raises(ValueError):
            udf.get_strategy_info("nonexistent")


class TestMergeRecords:
    def test_merge_no_overlap(self):
        left = [{"id": 1, "v": "a"}]
        right = [{"id": 2, "v": "b"}]
        schema = MergeSchema(default=LWW())
        result, conflicts = _merge_records(left, right, "id", schema)
        assert len(result) == 2
        assert conflicts == 0

    def test_merge_with_overlap(self):
        left = [{"id": 1, "v": "a"}]
        right = [{"id": 1, "v": "b"}]
        schema = MergeSchema(default=MaxWins())
        result, conflicts = _merge_records(left, right, "id", schema)
        assert len(result) == 1
        assert conflicts == 1
        assert result[0]["v"] == "b"

    def test_merge_empty_left(self):
        result, conflicts = _merge_records([], [{"id": 1}], "id", MergeSchema())
        assert len(result) == 1

    def test_merge_empty_both(self):
        result, conflicts = _merge_records([], [], "id", MergeSchema())
        assert result == []
        assert conflicts == 0


class TestDiffRecords:
    def test_diff_identical(self):
        data = [{"id": 1, "v": "a"}]
        diff = _diff_records(data, data, "id")
        assert diff["unchanged_count"] == 1
        assert diff["added"] == []
        assert diff["removed"] == []

    def test_diff_additions(self):
        left = [{"id": 1, "v": "a"}]
        right = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        diff = _diff_records(left, right, "id")
        assert len(diff["added"]) == 1


class TestResolveStrategy:
    def test_resolve_lww(self):
        s = _resolve_strategy("lww")
        assert s.name() == "LWW"

    def test_resolve_unknown(self):
        with pytest.raises(ValueError):
            _resolve_strategy("nonexistent")


class TestRecordsFromRelation:
    def test_from_none(self):
        assert _records_from_relation(None) == []

    def test_from_relation(self):
        rel = _mock_relation(["id", "v"], [(1, "a"), (2, "b")])
        result = _records_from_relation(rel)
        assert len(result) == 2
        assert result[0] == {"id": 1, "v": "a"}
