# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.accelerators.duckdb_udf — DuckDBMergeUDF.

Uses in-memory DuckDB connections when duckdb is installed; mocks the
connection layer otherwise.  Tests cover init, register/unregister,
merge_tables(), diff_tables(), merge_results(), get_strategy_info(),
register_strategy(), health_check(), and the internal helper functions.
"""

import json
import pytest
from unittest.mock import MagicMock

from crdt_merge.accelerators.duckdb_udf import (
    DuckDBMergeUDF,
    DuckDBMergeQLExtension,
    _merge_records,
    _diff_records,
    _resolve_strategy,
    _records_from_relation,
    _STRATEGY_MAP,
)
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins
from crdt_merge.accelerators import ACCELERATOR_REGISTRY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_rel(columns, rows):
    rel = MagicMock()
    rel.columns = columns
    rel.fetchall.return_value = rows
    return rel


def _mock_conn_with_tables(table_data):
    """table_data: {name: (columns, rows)}"""
    conn = MagicMock()

    def _sql(query):
        for name, (cols, rows) in table_data.items():
            if name in query:
                return _mock_rel(cols, rows)
        return _mock_rel([], [])

    conn.sql.side_effect = _sql
    return conn


# ---------------------------------------------------------------------------
# Check whether real duckdb is available
# ---------------------------------------------------------------------------

try:
    import duckdb as _real_duckdb
    _DUCKDB_AVAILABLE = True
except ImportError:
    _DUCKDB_AVAILABLE = False


# ===================================================================
# TestDuckDBMergeUDFInit
# ===================================================================

class TestDuckDBMergeUDFInit:
    def test_default_connection_is_none(self):
        udf = DuckDBMergeUDF()
        assert udf._conn is None

    def test_connection_stored(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        assert udf._conn is conn

    def test_default_schema_uses_lww(self):
        udf = DuckDBMergeUDF()
        assert udf._schema.default.name() == "LWW"

    def test_custom_schema_stored(self):
        schema = MergeSchema(default=MaxWins())
        udf = DuckDBMergeUDF(schema=schema)
        assert udf._schema.default.name() == "MaxWins"

    def test_registered_false_at_init(self):
        assert DuckDBMergeUDF()._registered is False

    def test_custom_strategies_empty_at_init(self):
        assert DuckDBMergeUDF()._custom_strategies == {}

    def test_registered_in_accelerator_registry(self):
        assert "duckdb_udf" in ACCELERATOR_REGISTRY


# ===================================================================
# TestAvailabilityAndHealth
# ===================================================================

class TestAvailabilityAndHealth:
    def test_is_available_returns_bool(self):
        udf = DuckDBMergeUDF()
        assert isinstance(udf.is_available(), bool)

    def test_health_check_name(self):
        hc = DuckDBMergeUDF().health_check()
        assert hc["name"] == "duckdb_udf"

    def test_health_check_version(self):
        hc = DuckDBMergeUDF().health_check()
        assert hc["version"] == "0.7.0"

    def test_health_check_duckdb_available_key(self):
        hc = DuckDBMergeUDF().health_check()
        assert "duckdb_available" in hc

    def test_health_check_registered_key(self):
        hc = DuckDBMergeUDF().health_check()
        assert "registered" in hc

    def test_health_check_custom_strategies_key(self):
        hc = DuckDBMergeUDF().health_check()
        assert "custom_strategies" in hc


# ===================================================================
# TestRegisterUnregister
# ===================================================================

class TestRegisterUnregister:
    def test_register_sets_flag(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        assert udf._registered is True

    def test_unregister_clears_flag(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        udf.unregister()
        assert udf._registered is False

    def test_register_calls_create_function(self):
        conn = MagicMock()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        assert conn.create_function.called


# ===================================================================
# TestMergeTables
# ===================================================================

class TestMergeTables:
    def test_basic_merge_returns_all_keys(self):
        conn = _mock_conn_with_tables({
            "t1": (["id", "v"], [(1, "a"), (2, "b")]),
            "t2": (["id", "v"], [(1, "c"), (3, "d")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("t1", "t2", key="id")
        ids = {r["id"] for r in result}
        assert ids == {1, 2, 3}

    def test_merge_with_max_strategy(self):
        conn = _mock_conn_with_tables({
            "scores_a": (["id", "score"], [(1, 50)]),
            "scores_b": (["id", "score"], [(1, 80)]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("scores_a", "scores_b", key="id",
                                  strategies={"score": "max"})
        assert result[0]["score"] == 80

    def test_merge_with_min_strategy(self):
        conn = _mock_conn_with_tables({
            "prices_a": (["id", "price"], [(1, 100)]),
            "prices_b": (["id", "price"], [(1, 60)]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("prices_a", "prices_b", key="id",
                                  strategies={"price": "min"})
        assert result[0]["price"] == 60

    def test_disjoint_tables_no_conflicts(self):
        conn = _mock_conn_with_tables({
            "left": (["id", "v"], [(1, "x")]),
            "right": (["id", "v"], [(2, "y")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("left", "right", key="id")
        assert len(result) == 2


# ===================================================================
# TestDiffTables
# ===================================================================

class TestDiffTables:
    def test_diff_returns_added(self):
        conn = _mock_conn_with_tables({
            "tl": (["id", "v"], [(1, "a")]),
            "tr": (["id", "v"], [(1, "a"), (2, "b")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        diff = udf.diff_tables("tl", "tr", key="id")
        assert len(diff["added"]) == 1
        assert diff["added"][0]["id"] == 2

    def test_diff_returns_removed(self):
        conn = _mock_conn_with_tables({
            "tl": (["id", "v"], [(1, "a"), (2, "b")]),
            "tr": (["id", "v"], [(2, "b")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        diff = udf.diff_tables("tl", "tr", key="id")
        assert len(diff["removed"]) == 1

    def test_diff_returns_unchanged_count(self):
        conn = _mock_conn_with_tables({
            "tl": (["id", "v"], [(1, "same")]),
            "tr": (["id", "v"], [(1, "same")]),
        })
        udf = DuckDBMergeUDF(connection=conn)
        diff = udf.diff_tables("tl", "tr", key="id")
        assert diff["unchanged_count"] == 1


# ===================================================================
# TestMergeResults
# ===================================================================

class TestMergeResults:
    def test_merge_results_combines_records(self):
        left = _mock_rel(["id", "v"], [(1, "x")])
        right = _mock_rel(["id", "v"], [(1, "y"), (2, "z")])
        udf = DuckDBMergeUDF()
        result = udf.merge_results(left, right, key="id")
        assert len(result) == 2

    def test_merge_results_with_strategies(self):
        left = _mock_rel(["id", "score"], [(1, 30)])
        right = _mock_rel(["id", "score"], [(1, 90)])
        udf = DuckDBMergeUDF()
        result = udf.merge_results(left, right, key="id",
                                   strategies={"score": "max"})
        assert result[0]["score"] == 90


# ===================================================================
# TestStrategyRegistration
# ===================================================================

class TestStrategyRegistration:
    def test_register_custom_strategy(self):
        udf = DuckDBMergeUDF()
        udf.register_strategy("double", lambda a, b: (a or 0) * 2)
        assert "double" in udf._custom_strategies

    def test_register_empty_name_raises(self):
        udf = DuckDBMergeUDF()
        with pytest.raises(ValueError):
            udf.register_strategy("", lambda a, b: a)

    def test_get_strategy_info_builtin(self):
        udf = DuckDBMergeUDF()
        info = udf.get_strategy_info("lww")
        assert info["type"] == "builtin"
        assert info["class"] == "LWW"

    def test_get_strategy_info_builtin_max(self):
        udf = DuckDBMergeUDF()
        info = udf.get_strategy_info("max")
        assert info["type"] == "builtin"

    def test_get_strategy_info_custom(self):
        udf = DuckDBMergeUDF()
        udf.register_strategy("myfn", lambda a, b: a)
        info = udf.get_strategy_info("myfn")
        assert info["type"] == "custom"

    def test_get_strategy_info_unknown_raises(self):
        udf = DuckDBMergeUDF()
        with pytest.raises(ValueError):
            udf.get_strategy_info("does_not_exist")


# ===================================================================
# TestInternalHelpers
# ===================================================================

class TestMergeRecords:
    def test_no_overlap(self):
        left = [{"id": 1, "v": "a"}]
        right = [{"id": 2, "v": "b"}]
        merged, conflicts = _merge_records(left, right, "id", MergeSchema())
        assert len(merged) == 2
        assert conflicts == 0

    def test_overlap_counts_conflict(self):
        left = [{"id": 1, "v": "a"}]
        right = [{"id": 1, "v": "b"}]
        _, conflicts = _merge_records(left, right, "id", MergeSchema(default=MaxWins()))
        assert conflicts == 1

    def test_max_wins_resolves_correctly(self):
        left = [{"id": 1, "score": 10}]
        right = [{"id": 1, "score": 20}]
        merged, _ = _merge_records(left, right, "id", MergeSchema(default=MaxWins()))
        assert merged[0]["score"] == 20

    def test_empty_both(self):
        merged, conflicts = _merge_records([], [], "id", MergeSchema())
        assert merged == []
        assert conflicts == 0

    def test_none_key_skipped(self):
        left = [{"id": None, "v": "a"}]
        right = [{"id": 1, "v": "b"}]
        merged, _ = _merge_records(left, right, "id", MergeSchema())
        assert len(merged) == 1


class TestDiffRecords:
    def test_identical_data_no_changes(self):
        data = [{"id": 1, "v": "x"}]
        diff = _diff_records(data, data, "id")
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["unchanged_count"] == 1

    def test_added_keys_detected(self):
        left = [{"id": 1}]
        right = [{"id": 1}, {"id": 2}]
        diff = _diff_records(left, right, "id")
        assert len(diff["added"]) == 1
        assert diff["added"][0]["id"] == 2

    def test_removed_keys_detected(self):
        left = [{"id": 1}, {"id": 2}]
        right = [{"id": 1}]
        diff = _diff_records(left, right, "id")
        assert len(diff["removed"]) == 1

    def test_modified_keys_detected(self):
        left = [{"id": 1, "v": "old"}]
        right = [{"id": 1, "v": "new"}]
        diff = _diff_records(left, right, "id")
        assert len(diff["modified"]) == 1


class TestResolveStrategy:
    def test_resolve_lww(self):
        strat = _resolve_strategy("lww")
        assert strat.name() == "LWW"

    def test_resolve_max(self):
        strat = _resolve_strategy("max")
        assert strat.name() == "MaxWins"

    def test_resolve_alias_maxwins(self):
        strat = _resolve_strategy("maxwins")
        assert strat.name() == "MaxWins"

    def test_resolve_min(self):
        strat = _resolve_strategy("min")
        assert strat.name() == "MinWins"

    def test_resolve_unknown_raises(self):
        with pytest.raises(ValueError):
            _resolve_strategy("unknown_strategy")


class TestRecordsFromRelation:
    def test_none_returns_empty_list(self):
        assert _records_from_relation(None) == []

    def test_relation_converted_to_dicts(self):
        rel = _mock_rel(["id", "name"], [(1, "Alice"), (2, "Bob")])
        result = _records_from_relation(rel)
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "Alice"}
        assert result[1] == {"id": 2, "name": "Bob"}

    def test_empty_relation_returns_empty(self):
        rel = _mock_rel([], [])
        result = _records_from_relation(rel)
        assert result == []


# ===================================================================
# TestLiveDuckDB (only run when duckdb is installed)
# ===================================================================

@pytest.mark.skipif(not _DUCKDB_AVAILABLE, reason="duckdb not installed")
class TestLiveDuckDB:
    """Integration tests using a real in-memory DuckDB connection."""

    def test_register_with_real_connection(self):
        conn = _real_duckdb.connect()
        udf = DuckDBMergeUDF(connection=conn)
        udf.register()
        assert udf._registered is True
        conn.close()

    def test_merge_tables_real_connection(self):
        conn = _real_duckdb.connect()
        conn.execute("CREATE TABLE ta AS SELECT 1 AS id, 'hello' AS v")
        conn.execute("CREATE TABLE tb AS SELECT 1 AS id, 'world' AS v UNION ALL SELECT 2, 'new'")
        udf = DuckDBMergeUDF(connection=conn)
        result = udf.merge_tables("ta", "tb", key="id")
        ids = {r["id"] for r in result}
        assert 1 in ids
        assert 2 in ids
        conn.close()

    def test_diff_tables_real_connection(self):
        conn = _real_duckdb.connect()
        conn.execute("CREATE TABLE da AS SELECT 1 AS id, 10 AS val")
        conn.execute("CREATE TABLE db AS SELECT 1 AS id, 10 AS val UNION ALL SELECT 2, 20")
        udf = DuckDBMergeUDF(connection=conn)
        diff = udf.diff_tables("da", "db", key="id")
        assert len(diff["added"]) == 1
        conn.close()
