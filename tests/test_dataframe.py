"""Tests for DataFrame merge operations."""
import pytest
from crdt_merge.dataframe import merge, diff


class TestMergeListOfDicts:
    """Test with plain list-of-dicts (no pandas required)."""

    def test_merge_by_key(self):
        a = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        b = [{"id": 2, "name": "Robert"}, {"id": 3, "name": "Charlie"}]
        result = merge(a, b, key="id")
        assert len(result) == 3
        names = {r["id"]: r["name"] for r in result}
        assert names[1] == "Alice"
        assert names[2] == "Robert"  # B wins by default
        assert names[3] == "Charlie"

    def test_merge_prefer_a(self):
        a = [{"id": 1, "name": "Alice"}]
        b = [{"id": 1, "name": "Bob"}]
        result = merge(a, b, key="id", prefer="a")
        assert result[0]["name"] == "Alice"

    def test_merge_no_key_appends(self):
        a = [{"x": 1}, {"x": 2}]
        b = [{"x": 3}, {"x": 4}]
        result = merge(a, b)
        assert len(result) == 4

    def test_merge_no_key_dedup(self):
        a = [{"x": 1}, {"x": 2}]
        b = [{"x": 2}, {"x": 3}]
        result = merge(a, b, dedup=True)
        assert len(result) == 3

    def test_schema_union(self):
        a = [{"id": 1, "name": "Alice"}]
        b = [{"id": 2, "email": "bob@test.com"}]
        result = merge(a, b, key="id")
        assert len(result) == 2
        assert result[0].get("email") is None
        assert result[1].get("name") is None

    def test_merge_fills_none_from_other(self):
        a = [{"id": 1, "name": "Alice", "age": None}]
        b = [{"id": 1, "age": 30}]
        result = merge(a, b, key="id")
        assert result[0]["age"] == 30
        assert result[0]["name"] == "Alice"

    def test_timestamp_lww(self):
        a = [{"id": 1, "name": "old", "ts": 1.0}]
        b = [{"id": 1, "name": "new", "ts": 2.0}]
        result = merge(a, b, key="id", timestamp_col="ts")
        assert result[0]["name"] == "new"

    def test_timestamp_lww_a_wins(self):
        a = [{"id": 1, "name": "newer", "ts": 5.0}]
        b = [{"id": 1, "name": "older", "ts": 1.0}]
        result = merge(a, b, key="id", timestamp_col="ts")
        assert result[0]["name"] == "newer"

    def test_empty_a(self):
        result = merge([], [{"id": 1, "x": 1}], key="id")
        assert len(result) == 1

    def test_empty_b(self):
        result = merge([{"id": 1, "x": 1}], [], key="id")
        assert len(result) == 1

    def test_both_empty(self):
        result = merge([], [])
        assert len(result) == 0

    def test_large_merge(self):
        a = [{"id": i, "val": f"a_{i}"} for i in range(1000)]
        b = [{"id": i, "val": f"b_{i}"} for i in range(500, 1500)]
        result = merge(a, b, key="id")
        assert len(result) == 1500

    def test_commutativity(self):
        a = [{"id": 1, "x": "a"}, {"id": 2, "x": "b"}]
        b = [{"id": 2, "x": "c"}, {"id": 3, "x": "d"}]
        # Without timestamp, B wins, so order matters for conflict cells
        # but structure (which keys exist) should be symmetric
        r1 = merge(a, b, key="id")
        r2 = merge(b, a, key="id")
        assert len(r1) == len(r2) == 3


class TestDiff:
    def test_basic_diff(self):
        a = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        b = [{"id": 2, "name": "Robert"}, {"id": 3, "name": "Charlie"}]
        d = diff(a, b, key="id")
        assert d["unchanged"] == 0
        assert len(d["modified"]) == 1
        assert d["summary"].startswith("+1")
