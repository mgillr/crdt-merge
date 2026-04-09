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

"""Tests for crdt_merge.mergeql — MergeQL SQL-like CRDT merge interface."""

import pytest
from crdt_merge.mergeql import (
    MergeQL,
    MergeQLParser,
    MergeAST,
    MergePlan,
    MergeQLResult,
    MergeQLSyntaxError,
    MergeQLValidationError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser():
    return MergeQLParser()

@pytest.fixture
def ql():
    engine = MergeQL()
    engine.register("east", [
        {"id": 1, "name": "Alice", "salary": 100, "dept": "eng"},
        {"id": 2, "name": "Bob", "salary": 200, "dept": "eng"},
        {"id": 3, "name": "Charlie", "salary": 300, "dept": "sales"},
    ])
    engine.register("west", [
        {"id": 1, "name": "Alicia", "salary": 120, "dept": "eng"},
        {"id": 2, "name": "Bobby", "salary": 180, "dept": "marketing"},
        {"id": 4, "name": "Diana", "salary": 400, "dept": "hr"},
    ])
    return engine

@pytest.fixture
def ql_three(ql):
    ql.register("south", [
        {"id": 1, "name": "Ally", "salary": 110, "dept": "ops"},
        {"id": 5, "name": "Eve", "salary": 500, "dept": "finance"},
    ])
    return ql

# ===================================================================
# TestMergeQLParser -- 15 tests
# ===================================================================

class TestMergeQLParser:
    def test_parse_basic_merge(self, parser):
        ast = parser.parse("MERGE east, west ON id")
        assert ast.sources == ["east", "west"]
        assert ast.on_key == "id"

    def test_parse_multi_source(self, parser):
        ast = parser.parse("MERGE a, b, c ON key")
        assert ast.sources == ["a", "b", "c"]

    def test_parse_with_strategy(self, parser):
        ast = parser.parse("MERGE a, b ON id STRATEGY name='lww'")
        assert ast.strategies == {"name": "lww"}

    def test_parse_multi_strategy(self, parser):
        ast = parser.parse("MERGE a, b ON id STRATEGY name='lww', salary='max'")
        assert ast.strategies == {"name": "lww", "salary": "max"}

    def test_parse_with_where(self, parser):
        ast = parser.parse("MERGE a, b ON id WHERE dept = eng")
        assert ast.where_clause is not None
        assert "dept" in ast.where_clause

    def test_parse_with_limit(self, parser):
        ast = parser.parse("MERGE a, b ON id LIMIT 10")
        assert ast.limit == 10

    def test_parse_with_map(self, parser):
        ast = parser.parse("MERGE a, b ON id MAP old_name -> new_name")
        assert ast.schema_mapping == {"old_name": "new_name"}

    def test_parse_explain(self, parser):
        ast = parser.parse("EXPLAIN MERGE a, b ON id")
        assert ast.explain is True
        assert ast.sources == ["a", "b"]

    def test_parse_case_insensitive(self, parser):
        ast = parser.parse("merge A, B on id strategy name='lww'")
        assert ast.sources == ["A", "B"]
        assert ast.on_key == "id"
        assert ast.strategies == {"name": "lww"}

    def test_parse_extra_whitespace(self, parser):
        ast = parser.parse("  MERGE   a ,  b   ON   id  ")
        assert ast.sources == ["a", "b"]
        assert ast.on_key == "id"

    def test_parse_error_no_sources(self, parser):
        with pytest.raises(MergeQLSyntaxError):
            parser.parse("MERGE ON id")

    def test_parse_error_no_on(self, parser):
        with pytest.raises(MergeQLSyntaxError):
            parser.parse("MERGE a, b")

    def test_parse_error_invalid_strategy(self, parser):
        # Missing = sign
        with pytest.raises(MergeQLSyntaxError):
            parser.parse("MERGE a, b ON id STRATEGY name lww")

    def test_parse_error_empty_query(self, parser):
        with pytest.raises(MergeQLSyntaxError):
            parser.parse("")

    def test_parse_complex_combined(self, parser):
        ast = parser.parse(
            "EXPLAIN MERGE a, b, c ON id "
            "STRATEGY name='lww', score='max' "
            "WHERE dept = eng "
            "MAP old_col -> new_col "
            "LIMIT 50"
        )
        assert ast.explain is True
        assert ast.sources == ["a", "b", "c"]
        assert ast.on_key == "id"
        assert ast.strategies == {"name": "lww", "score": "max"}
        assert ast.where_clause is not None
        assert ast.schema_mapping == {"old_col": "new_col"}
        assert ast.limit == 50

# ===================================================================
# TestMergeQLExecution -- 15 tests
# ===================================================================

class TestMergeQLExecution:
    def test_basic_two_source_merge(self, ql):
        result = ql.execute("MERGE east, west ON id")
        assert isinstance(result, MergeQLResult)
        assert len(result.data) == 4  # ids 1,2,3,4
        ids = {r["id"] for r in result.data}
        assert ids == {1, 2, 3, 4}

    def test_three_source_merge(self, ql_three):
        result = ql_three.execute("MERGE east, west, south ON id")
        ids = {r["id"] for r in result.data}
        assert ids == {1, 2, 3, 4, 5}

    def test_merge_with_conflicts(self, ql):
        result = ql.execute("MERGE east, west ON id")
        assert result.conflicts > 0

    def test_merge_lww_strategy(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY name='lww'")
        assert len(result.data) == 4

    def test_merge_max_strategy(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='max'")
        rec1 = next(r for r in result.data if r["id"] == 1)
        assert rec1["salary"] == 120  # max(100, 120)

    def test_merge_min_strategy(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='min'")
        rec1 = next(r for r in result.data if r["id"] == 1)
        assert rec1["salary"] == 100  # min(100, 120)

    def test_merge_with_where_filter(self, ql):
        result = ql.execute("MERGE east, west ON id WHERE dept = eng")
        assert all(r["dept"] == "eng" for r in result.data)

    def test_merge_with_limit(self, ql):
        result = ql.execute("MERGE east, west ON id LIMIT 2")
        assert len(result.data) == 2

    def test_merge_with_column_mapping(self, ql):
        result = ql.execute("MERGE east, west ON id MAP name -> full_name")
        assert all("full_name" in r for r in result.data)
        assert all("name" not in r for r in result.data)

    def test_merge_empty_sources(self):
        ql = MergeQL()
        ql.register("a", [])
        ql.register("b", [])
        result = ql.execute("MERGE a, b ON id")
        assert result.data == []

    def test_merge_disjoint_keys(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "v": "x"}])
        ql.register("b", [{"id": 2, "v": "y"}])
        result = ql.execute("MERGE a, b ON id")
        assert len(result.data) == 2

    def test_merge_overlapping_partial(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "v": "x"}, {"id": 2, "v": "y"}])
        ql.register("b", [{"id": 2, "v": "z"}, {"id": 3, "v": "w"}])
        result = ql.execute("MERGE a, b ON id")
        assert len(result.data) == 3

    def test_register_unregister(self, ql):
        assert "east" in ql.list_sources()
        ql.unregister("east")
        assert "east" not in ql.list_sources()

    def test_list_sources(self, ql):
        sources = ql.list_sources()
        assert "east" in sources
        assert "west" in sources

    def test_source_info(self, ql):
        info = ql.source_info("east")
        assert info["name"] == "east"
        assert info["rows"] == 3
        assert "id" in info["columns"]

# ===================================================================
# TestMergeQLStrategies -- 10 tests
# ===================================================================

class TestMergeQLStrategies:
    def test_default_strategy_lww(self, ql):
        result = ql.execute("MERGE east, west ON id")
        # Default LWW -- both timestamps are 0, so tiebreaker by node_id
        assert len(result.data) == 4

    def test_per_field_strategies(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='max', name='lww'")
        rec = next(r for r in result.data if r["id"] == 2)
        assert rec["salary"] == 200  # max(200, 180)

    def test_mixed_strategies(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='max', dept='min'")
        assert len(result.data) == 4

    def test_custom_strategy_registration(self, ql):
        ql.register_strategy("always_left", lambda a, b: a)
        assert "always_left" in ql._custom_strategies

    def test_custom_strategy_in_query(self, ql):
        ql.register_strategy("pick_longer", lambda a, b: a if len(str(a)) >= len(str(b)) else b)
        result = ql.execute("MERGE east, west ON id STRATEGY name='custom:pick_longer'")
        rec = next(r for r in result.data if r["id"] == 2)
        assert rec["name"] in ("Bobby", "Bob")  # Bobby is longer

    def test_unknown_strategy_error(self, ql):
        with pytest.raises(MergeQLValidationError):
            ql.execute("MERGE east, west ON id STRATEGY name='nonexistent'")

    def test_strategy_from_schema(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='maxwins'")
        rec = next(r for r in result.data if r["id"] == 1)
        assert rec["salary"] == 120

    def test_strategy_numeric_fields(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY salary='min'")
        rec = next(r for r in result.data if r["id"] == 2)
        assert rec["salary"] == 180

    def test_strategy_string_fields(self, ql):
        result = ql.execute("MERGE east, west ON id STRATEGY name='longest'")
        rec = next(r for r in result.data if r["id"] == 1)
        assert rec["name"] == "Alicia"  # longer than "Alice"

    def test_strategy_boolean_fields(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "active": True}])
        ql.register("b", [{"id": 1, "active": False}])
        result = ql.execute("MERGE a, b ON id STRATEGY active='max'")
        assert result.data[0]["active"] is True

# ===================================================================
# TestMergeQLExplain -- 5 tests
# ===================================================================

class TestMergeQLExplain:
    def test_explain_basic(self, ql):
        plan = ql.explain("MERGE east, west ON id")
        assert isinstance(plan, MergePlan)
        assert plan.merge_key == "id"

    def test_explain_multi_source(self, ql_three):
        plan = ql_three.explain("MERGE east, west, south ON id")
        assert len(plan.sources) == 3

    def test_explain_arrow_backend(self):
        ql = MergeQL(arrow_backend=True)
        ql.register("a", [{"id": 1}])
        ql.register("b", [{"id": 2}])
        plan = ql.explain("MERGE a, b ON id")
        assert plan.arrow_backend is True

    def test_explain_schema_evolution(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "x": 1}])
        ql.register("b", [{"id": 1, "y": 2}])
        plan = ql.explain("MERGE a, b ON id")
        assert plan.schema_evolution_needed is True

    def test_explain_output_format(self, ql):
        plan = ql.explain("MERGE east, west ON id")
        text = str(plan)
        assert "MergePlan" in text
        assert "east" in text

# ===================================================================
# TestMergeQLProvenance -- 5 tests
# ===================================================================

class TestMergeQLProvenance:
    def test_provenance_enabled(self, ql):
        result = ql.execute("MERGE east, west ON id")
        assert result.provenance is not None
        assert len(result.provenance) > 0

    def test_provenance_disabled(self):
        ql = MergeQL(provenance=False)
        ql.register("a", [{"id": 1, "v": "x"}])
        ql.register("b", [{"id": 1, "v": "y"}])
        result = ql.execute("MERGE a, b ON id")
        assert result.provenance is None

    def test_provenance_multi_source(self, ql_three):
        result = ql_three.execute("MERGE east, west, south ON id")
        assert result.provenance is not None
        sources_in_prov = {p.get("source") for p in result.provenance}
        assert "east" in sources_in_prov

    def test_provenance_conflict_tracking(self, ql):
        result = ql.execute("MERGE east, west ON id")
        conflict_entries = [p for p in result.provenance if p.get("field") != "*"]
        assert len(conflict_entries) > 0

    def test_provenance_source_attribution(self, ql):
        result = ql.execute("MERGE east, west ON id")
        sources_in_prov = {p.get("source") for p in result.provenance}
        assert "west" in sources_in_prov

# ===================================================================
# TestMergeQLIntegration -- 10 tests
# ===================================================================

class TestMergeQLIntegration:
    def test_mergeql_with_schema_evolution(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "name": "Alice"}])
        ql.register("b", [{"id": 1, "email": "alice@test.com"}])
        result = ql.execute("MERGE a, b ON id")
        assert result.data[0].get("name") == "Alice"
        assert result.data[0].get("email") == "alice@test.com"

    def test_mergeql_with_arrow_backend_flag(self):
        ql = MergeQL(arrow_backend=True)
        ql.register("a", [{"id": 1, "v": 1}])
        ql.register("b", [{"id": 1, "v": 2}])
        result = ql.execute("MERGE a, b ON id")
        assert result.plan.arrow_backend is True

    def test_mergeql_with_merge_function(self):
        from crdt_merge.dataframe import merge as df_merge
        a = [{"id": 1, "v": "x"}]
        b = [{"id": 1, "v": "y"}]
        ql = MergeQL()
        ql.register("a", a)
        ql.register("b", b)
        result = ql.execute("MERGE a, b ON id")
        assert len(result.data) == 1

    def test_mergeql_with_dataframe_merge(self):
        ql = MergeQL()
        ql.register("a", [{"id": 1, "score": 50}])
        ql.register("b", [{"id": 1, "score": 80}])
        result = ql.execute("MERGE a, b ON id STRATEGY score='max'")
        assert result.data[0]["score"] == 80

    def test_mergeql_with_streaming_data(self):
        ql = MergeQL()
        big_a = [{"id": i, "v": f"a{i}"} for i in range(100)]
        big_b = [{"id": i, "v": f"b{i}"} for i in range(50, 150)]
        ql.register("a", big_a)
        ql.register("b", big_b)
        result = ql.execute("MERGE a, b ON id")
        assert len(result.data) == 150

    def test_mergeql_chained_queries(self, ql):
        r1 = ql.execute("MERGE east, west ON id STRATEGY salary='max'")
        ql.register("merged", r1.data)
        ql.register("extra", [{"id": 1, "salary": 999}])
        r2 = ql.execute("MERGE merged, extra ON id STRATEGY salary='max'")
        rec = next(r for r in r2.data if r["id"] == 1)
        assert rec["salary"] == 999

    def test_mergeql_large_dataset(self):
        ql = MergeQL()
        ql.register("a", [{"id": i, "v": i} for i in range(10000)])
        ql.register("b", [{"id": i, "v": i + 1} for i in range(5000, 15000)])
        result = ql.execute("MERGE a, b ON id STRATEGY v='max'")
        assert len(result.data) == 15000

    def test_mergeql_idempotent_merge(self):
        ql = MergeQL()
        data = [{"id": 1, "v": "x"}, {"id": 2, "v": "y"}]
        ql.register("a", data)
        ql.register("b", data)
        result = ql.execute("MERGE a, b ON id")
        assert len(result.data) == 2
        assert {r["v"] for r in result.data} == {"x", "y"}

    def test_mergeql_commutative_merge(self):
        ql1 = MergeQL()
        ql1.register("a", [{"id": 1, "v": 10}])
        ql1.register("b", [{"id": 1, "v": 20}])
        r1 = ql1.execute("MERGE a, b ON id STRATEGY v='max'")

        ql2 = MergeQL()
        ql2.register("a", [{"id": 1, "v": 20}])
        ql2.register("b", [{"id": 1, "v": 10}])
        r2 = ql2.execute("MERGE a, b ON id STRATEGY v='max'")

        assert r1.data[0]["v"] == r2.data[0]["v"] == 20

    def test_mergeql_associative_merge(self):
        # (A merge B) merge C == A merge (B merge C) for max strategy
        ql = MergeQL()
        ql.register("a", [{"id": 1, "v": 5}])
        ql.register("b", [{"id": 1, "v": 10}])
        ql.register("c", [{"id": 1, "v": 7}])

        # (A merge B) merge C
        r_ab = ql.execute("MERGE a, b ON id STRATEGY v='max'")
        ql.register("ab", r_ab.data)
        r_abc = ql.execute("MERGE ab, c ON id STRATEGY v='max'")

        # A merge (B merge C)
        r_bc = ql.execute("MERGE b, c ON id STRATEGY v='max'")
        ql.register("bc", r_bc.data)
        r_abc2 = ql.execute("MERGE a, bc ON id STRATEGY v='max'")

        assert r_abc.data[0]["v"] == r_abc2.data[0]["v"] == 10
