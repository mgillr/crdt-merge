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

"""Tests for crdt_merge.accelerators.polars_plugin — Polars CRDT merge.

All tests mock polars so they run without the polars dependency.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, patch

from crdt_merge.strategies import LWW, MaxWins, MinWins, MergeSchema

# ---------------------------------------------------------------------------
# Mock polars module
# ---------------------------------------------------------------------------

class _MockDataFrame:
    """Minimal mock for polars.DataFrame."""

    def __init__(self, data=None):
        self._data = data or []

    def to_dicts(self):
        return list(self._data)

    @property
    def columns(self):
        if not self._data:
            return []
        return list(self._data[0].keys())

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"MockPolarsDF(rows={len(self._data)})"

class _MockLazyFrame:
    """Minimal mock for polars.LazyFrame."""

    def __init__(self, data):
        self._data = data

    def collect(self):
        return _MockDataFrame(self._data)

def _mock_polars_dataframe(records=None):
    """Create mock that behaves like pl.DataFrame(records)."""
    return _MockDataFrame(records)

# Create a mock polars module
_mock_pl = types.ModuleType("polars")
_mock_pl.__version__ = "1.0.0"
_mock_pl.DataFrame = _mock_polars_dataframe

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_polars():
    """Inject mock polars into the plugin module."""
    import crdt_merge.accelerators.polars_plugin as mod
    original = mod._pl
    mod._pl = _mock_pl
    yield
    mod._pl = original

@pytest.fixture
def merger():
    from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
    return PolarsCRDTMerge(schema=MergeSchema(default=LWW(), salary=MaxWins()))

@pytest.fixture
def left_data():
    return [
        {"id": 1, "name": "Alice", "salary": 100},
        {"id": 2, "name": "Bob", "salary": 200},
    ]

@pytest.fixture
def right_data():
    return [
        {"id": 1, "name": "Alicia", "salary": 150},
        {"id": 3, "name": "Charlie", "salary": 300},
    ]

# ═══════════════════════════════════════════════════════════════════════════
# TestPolarsMerge -- core merge
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarsMerge:
    """Core merge functionality."""

    def test_basic_merge(self, merger, left_data, right_data):
        result = merger.merge(left_data, right_data, key="id")
        assert result.conflicts > 0
        assert result.rows_merged == 1
        assert result.rows_left_only == 1
        assert result.rows_right_only == 1

    def test_merge_disjoint(self, merger):
        left = [{"id": 1, "name": "A"}]
        right = [{"id": 2, "name": "B"}]
        result = merger.merge(left, right, key="id")
        assert result.conflicts == 0
        assert result.rows_left_only == 1
        assert result.rows_right_only == 1

    def test_merge_identical(self, merger):
        data = [{"id": 1, "name": "Alice", "salary": 100}]
        result = merger.merge(data, list(data), key="id")
        assert result.conflicts == 0
        assert result.rows_merged == 1

    def test_merge_max_wins_strategy(self, merger, left_data, right_data):
        result = merger.merge(left_data, right_data, key="id")
        merged_dicts = result.data.to_dicts() if hasattr(result.data, 'to_dicts') else result.data
        row_1 = [r for r in merged_dicts if r["id"] == 1][0]
        assert row_1["salary"] == 150  # MaxWins: 150 > 100

    def test_merge_empty_left(self, merger, right_data):
        result = merger.merge([], right_data, key="id")
        assert result.rows_right_only == 2
        assert result.rows_left_only == 0

    def test_merge_empty_right(self, merger, left_data):
        result = merger.merge(left_data, [], key="id")
        assert result.rows_left_only == 2
        assert result.rows_right_only == 0

    def test_merge_both_empty(self, merger):
        result = merger.merge([], [], key="id")
        assert result.conflicts == 0
        merged_dicts = result.data.to_dicts() if hasattr(result.data, 'to_dicts') else result.data
        assert len(merged_dicts) == 0

    def test_merge_result_to_dict(self, merger, left_data, right_data):
        result = merger.merge(left_data, right_data, key="id")
        d = result.to_dict()
        assert "conflicts" in d
        assert "merge_time_ms" in d
        assert "total_rows" in d
        assert d["total_rows"] == 3

    def test_merge_time_tracked(self, merger, left_data, right_data):
        result = merger.merge(left_data, right_data, key="id")
        assert result.merge_time_ms >= 0

# ═══════════════════════════════════════════════════════════════════════════
# TestPolarsLazy -- lazy merge
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarsLazy:
    """Lazy merge functionality."""

    def test_lazy_merge_collects(self, merger, left_data, right_data):
        lazy_left = _MockLazyFrame(left_data)
        lazy_right = _MockLazyFrame(right_data)
        result = merger.merge_lazy(lazy_left, lazy_right, key="id")
        assert result.rows_merged == 1

    def test_lazy_merge_with_dataframe(self, merger, left_data, right_data):
        # Should also accept regular DataFrames
        result = merger.merge_lazy(left_data, right_data, key="id")
        assert result.rows_merged == 1

# ═══════════════════════════════════════════════════════════════════════════
# TestPolarsExpression -- expression API
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarsExpression:
    """Expression API."""

    def test_as_expression_default(self, merger):
        expr = merger.as_expression("salary")
        assert expr.field == "salary"
        assert expr.strategy_name == "LWW"

    def test_as_expression_max(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        assert expr.strategy_name == "MaxWins"

    def test_as_expression_min(self, merger):
        expr = merger.as_expression("score", strategy="min")
        assert expr.strategy_name == "MinWins"

    def test_expression_apply(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        assert expr.apply(100, 200) == 200
        assert expr.apply(300, 100) == 300

    def test_expression_repr(self, merger):
        expr = merger.as_expression("salary", strategy="max")
        r = repr(expr)
        assert "salary" in r
        assert "MaxWins" in r

    def test_crdt_merge_expr_convenience(self):
        from crdt_merge.accelerators.polars_plugin import crdt_merge_expr
        expr = crdt_merge_expr("score", "min")
        assert expr.field == "score"
        assert expr.apply(10, 5) == 5

# ═══════════════════════════════════════════════════════════════════════════
# TestPolarsStrategyOverrides
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarsStrategyOverrides:
    """Strategy override via merge() call."""

    def test_override_at_merge_time(self, merger):
        left = [{"id": 1, "score": 80}]
        right = [{"id": 1, "score": 60}]
        result = merger.merge(left, right, key="id", strategies={"score": "min"})
        merged_dicts = result.data.to_dicts() if hasattr(result.data, 'to_dicts') else result.data
        row = merged_dicts[0]
        assert row["score"] == 60  # MinWins

    def test_override_does_not_mutate_schema(self, merger):
        original_fields = dict(merger._schema.fields)
        merger.merge(
            [{"id": 1, "x": 1}], [{"id": 1, "x": 2}],
            key="id", strategies={"x": "max"}
        )
        assert dict(merger._schema.fields) == original_fields

# ═══════════════════════════════════════════════════════════════════════════
# TestPolarsHealthCheck
# ═══════════════════════════════════════════════════════════════════════════

class TestPolarsHealthCheck:
    """Health check and availability."""

    def test_health_check_available(self, merger):
        hc = merger.health_check()
        assert hc["name"] == "polars_plugin"
        assert hc["polars_available"] is True
        assert hc["status"] == "ready"

    def test_health_check_not_available(self):
        import crdt_merge.accelerators.polars_plugin as mod
        original = mod._pl
        mod._pl = None
        try:
            from crdt_merge.accelerators.polars_plugin import PolarsCRDTMerge
            merger = PolarsCRDTMerge()
            hc = merger.health_check()
            assert hc["polars_available"] is False
            assert hc["status"] == "degraded"
        finally:
            mod._pl = original

    def test_is_available(self, merger):
        assert merger.is_available() is True

    def test_repr(self, merger):
        r = repr(merger)
        assert "available" in r

    def test_merge_result_repr(self, merger, left_data, right_data):
        result = merger.merge(left_data, right_data, key="id")
        r = repr(result)
        assert "PolarsMergeResult" in r
