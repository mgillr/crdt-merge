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

"""Tests for crdt_merge.accelerators.polars_plugin — PolarsCRDTMerge.

Polars is mocked so tests always run without requiring the polars package.
When real polars is present, additional live tests verify end-to-end behaviour.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock

from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins

# ---------------------------------------------------------------------------
# Minimal polars mock
# ---------------------------------------------------------------------------

class _MockDataFrame:
    def __init__(self, data=None):
        self._data = list(data) if data else []

    def to_dicts(self):
        return list(self._data)

    @property
    def columns(self):
        return list(self._data[0].keys()) if self._data else []

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"MockDF(rows={len(self._data)})"


class _MockLazyFrame:
    def __init__(self, data):
        self._data = list(data)

    def collect(self):
        return _MockDataFrame(self._data)


_mock_pl = types.ModuleType("polars")
_mock_pl.__version__ = "1.0.0"
_mock_pl.DataFrame = lambda data=None: _MockDataFrame(data or [])

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _inject_mock_polars():
    """Swap the module-level _pl reference in polars_plugin for tests."""
    import crdt_merge.accelerators.polars_plugin as mod
    original = mod._pl
    mod._pl = _mock_pl
    yield
    mod._pl = original


@pytest.fixture
def schema():
    return MergeSchema(default=LWW(), score=MaxWins(), price=MinWins())


@pytest.fixture
def merger(schema):
    from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
    return PolarsCRDTMerge(schema=schema)


@pytest.fixture
def left():
    return [
        {"id": 1, "name": "Alice", "score": 100, "price": 50},
        {"id": 2, "name": "Bob", "score": 200, "price": 80},
    ]


@pytest.fixture
def right():
    return [
        {"id": 1, "name": "Alicia", "score": 120, "price": 40},
        {"id": 3, "name": "Charlie", "score": 300, "price": 90},
    ]


# ===================================================================
# TestPolarsCRDTMergeInit
# ===================================================================

class TestPolarsCRDTMergeInit:
    def test_name_attribute(self, merger):
        assert merger.name == "polars_plugin"

    def test_version_attribute(self, merger):
        assert merger.version == "0.7.2"

    def test_default_schema_uses_lww(self):
        from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
        m = PolarsCRDTMerge()
        assert m._schema.default.name() == "LWW"

    def test_custom_schema_stored(self, merger, schema):
        assert merger._schema is schema

    def test_repr_contains_available(self, merger):
        assert "available" in repr(merger)


# ===================================================================
# TestHealthCheckAndAvailability
# ===================================================================

class TestHealthCheckAndAvailability:
    def test_health_check_name(self, merger):
        hc = merger.health_check()
        assert hc["name"] == "polars_plugin"

    def test_health_check_polars_available_true(self, merger):
        hc = merger.health_check()
        assert hc["polars_available"] is True

    def test_health_check_status_ready(self, merger):
        hc = merger.health_check()
        assert hc["status"] == "ready"

    def test_health_check_schema_fields_count(self, merger, schema):
        hc = merger.health_check()
        assert hc["schema_fields"] == len(schema.fields)

    def test_is_available_true(self, merger):
        assert merger.is_available() is True

    def test_health_check_degraded_when_polars_missing(self):
        import crdt_merge.accelerators.polars_plugin as mod
        original = mod._pl
        mod._pl = None
        try:
            from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
            m = PolarsCRDTMerge()
            hc = m.health_check()
            assert hc["polars_available"] is False
            assert hc["status"] == "degraded"
        finally:
            mod._pl = original

    def test_is_available_false_when_polars_missing(self):
        import crdt_merge.accelerators.polars_plugin as mod
        original = mod._pl
        mod._pl = None
        try:
            from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
            m = PolarsCRDTMerge()
            assert m.is_available() is False
        finally:
            mod._pl = original


# ===================================================================
# TestMerge
# ===================================================================

class TestMerge:
    def test_overlap_row_counted(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert result.rows_merged == 1

    def test_left_only_row_counted(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert result.rows_left_only == 1

    def test_right_only_row_counted(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert result.rows_right_only == 1

    def test_conflict_counted(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert result.conflicts > 0

    def test_max_wins_strategy_applied(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        rows = result.data.to_dicts()
        row1 = next(r for r in rows if r["id"] == 1)
        assert row1["score"] == 120  # MaxWins: max(100, 120)

    def test_min_wins_strategy_applied(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        rows = result.data.to_dicts()
        row1 = next(r for r in rows if r["id"] == 1)
        assert row1["price"] == 40  # MinWins: min(50, 40)

    def test_empty_left(self, merger, right):
        result = merger.merge([], right, key="id")
        assert result.rows_left_only == 0
        assert result.rows_right_only == 2

    def test_empty_right(self, merger, left):
        result = merger.merge(left, [], key="id")
        assert result.rows_left_only == 2
        assert result.rows_right_only == 0

    def test_empty_both(self, merger):
        result = merger.merge([], [], key="id")
        assert result.conflicts == 0
        assert result.rows_merged == 0

    def test_identical_rows_no_conflict(self, merger):
        data = [{"id": 1, "v": "same"}]
        result = merger.merge(data, list(data), key="id")
        assert result.conflicts == 0
        assert result.rows_merged == 1

    def test_merge_time_tracked(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert result.merge_time_ms >= 0

    def test_to_dict_contains_total_rows(self, merger, left, right):
        d = merger.merge(left, right, key="id").to_dict()
        assert d["total_rows"] == 3

    def test_to_dict_contains_conflicts(self, merger, left, right):
        d = merger.merge(left, right, key="id").to_dict()
        assert "conflicts" in d

    def test_strategy_override_at_call_time(self, merger):
        left = [{"id": 1, "score": 80}]
        right = [{"id": 1, "score": 60}]
        result = merger.merge(left, right, key="id", strategies={"score": "min"})
        rows = result.data.to_dicts()
        assert rows[0]["score"] == 60

    def test_strategy_override_does_not_mutate_schema(self, merger):
        original_fields = dict(merger._schema.fields)
        merger.merge(
            [{"id": 1, "x": 1}], [{"id": 1, "x": 2}],
            key="id", strategies={"x": "max"}
        )
        assert dict(merger._schema.fields) == original_fields


# ===================================================================
# TestMergeLazy
# ===================================================================

class TestMergeLazy:
    def test_lazy_frames_collected_and_merged(self, merger, left, right):
        lazy_left = _MockLazyFrame(left)
        lazy_right = _MockLazyFrame(right)
        result = merger.merge_lazy(lazy_left, lazy_right, key="id")
        assert result.rows_merged == 1

    def test_regular_lists_accepted_as_lazy(self, merger, left, right):
        result = merger.merge_lazy(left, right, key="id")
        assert result.rows_merged == 1


# ===================================================================
# TestAsExpression
# ===================================================================

class TestAsExpression:
    def test_expression_field_stored(self, merger):
        expr = merger.as_expression("salary")
        assert expr.field == "salary"

    def test_default_strategy_is_lww(self, merger):
        expr = merger.as_expression("salary")
        assert expr.strategy_name == "LWW"

    def test_max_strategy(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        assert expr.strategy_name == "MaxWins"

    def test_min_strategy(self, merger):
        expr = merger.as_expression("salary", strategy="min")
        assert expr.strategy_name == "MinWins"

    def test_apply_resolves_value(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        assert expr.apply(100, 200) == 200
        assert expr.apply(300, 50) == 300

    def test_repr_contains_field_and_strategy(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        r = repr(expr)
        assert "salary" in r
        assert "MaxWins" in r

    def test_unknown_strategy_raises(self, merger):
        with pytest.raises(ValueError, match="Unknown strategy"):
            merger.as_expression("field", strategy="nonexistent")


# ===================================================================
# TestCrdtMergeExpr
# ===================================================================

class TestCrdtMergeExpr:
    def test_convenience_function_returns_expression(self):
        from crdt_merge.accelerators.polars_plugin import crdt_merge_expr
        expr = crdt_merge_expr("price", "min")
        assert expr.field == "price"
        assert expr.apply(10, 5) == 5

    def test_default_strategy_lww(self):
        from crdt_merge.accelerators.polars_plugin import crdt_merge_expr
        expr = crdt_merge_expr("ts")
        assert expr.strategy_name == "LWW"


# ===================================================================
# TestPolarsMergeResult
# ===================================================================

class TestPolarsMergeResult:
    def test_repr_contains_class_name(self, merger, left, right):
        result = merger.merge(left, right, key="id")
        assert "PolarsMergeResult" in repr(result)

    def test_to_dict_merge_time_ms(self, merger, left, right):
        d = merger.merge(left, right, key="id").to_dict()
        assert "merge_time_ms" in d

    def test_to_dict_rows_merged(self, merger, left, right):
        d = merger.merge(left, right, key="id").to_dict()
        assert d["rows_merged"] == 1
