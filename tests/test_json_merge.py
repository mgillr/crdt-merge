"""Tests for JSON/dict merge."""
from crdt_merge.json_merge import merge_dicts, merge_json_lines


class TestMergeDicts:
    def test_disjoint_keys(self):
        a = {"x": 1}
        b = {"y": 2}
        assert merge_dicts(a, b) == {"x": 1, "y": 2}

    def test_overlapping_same_value(self):
        a = {"x": 1}
        b = {"x": 1}
        assert merge_dicts(a, b) == {"x": 1}

    def test_conflict_b_wins(self):
        a = {"x": "old"}
        b = {"x": "new"}
        assert merge_dicts(a, b) == {"x": "new"}

    def test_conflict_timestamp(self):
        a = {"x": "newer"}
        b = {"x": "older"}
        ts_a = {"x": 10.0}
        ts_b = {"x": 1.0}
        assert merge_dicts(a, b, ts_a, ts_b)["x"] == "newer"

    def test_nested_dicts(self):
        a = {"config": {"host": "a.com", "port": 80}}
        b = {"config": {"host": "b.com", "debug": True}}
        result = merge_dicts(a, b)
        assert result["config"]["host"] == "b.com"
        assert result["config"]["port"] == 80
        assert result["config"]["debug"] == True

    def test_list_merge(self):
        a = {"tags": ["python", "ml"]}
        b = {"tags": ["ml", "data"]}
        result = merge_dicts(a, b)
        assert set(result["tags"]) == {"python", "ml", "data"}

    def test_deeply_nested(self):
        a = {"a": {"b": {"c": {"d": 1}}}}
        b = {"a": {"b": {"c": {"e": 2}}}}
        result = merge_dicts(a, b)
        assert result["a"]["b"]["c"] == {"d": 1, "e": 2}

    def test_empty_dicts(self):
        assert merge_dicts({}, {}) == {}
        assert merge_dicts({"x": 1}, {}) == {"x": 1}
        assert merge_dicts({}, {"x": 1}) == {"x": 1}


class TestMergeJsonLines:
    def test_with_key(self):
        a = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        b = [{"id": 2, "name": "Robert"}, {"id": 3, "name": "Charlie"}]
        result = merge_json_lines(a, b, key="id")
        assert len(result) == 3

    def test_without_key(self):
        a = [{"x": 1}, {"x": 2}]
        b = [{"x": 2}, {"x": 3}]
        result = merge_json_lines(a, b)
        assert len(result) == 3
