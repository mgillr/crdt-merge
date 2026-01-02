# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for multi-key (composite key) support in crdt_merge.dataframe."""

import pytest
from crdt_merge.dataframe import merge, diff, _normalize_key, _make_composite_key


# ─── Composite key merge tests (3) ──────────────────────────────────────────

class TestCompositeKeyMerge:
    def test_two_column_key(self):
        """Two-column composite key merges correctly."""
        left = [
            {"first": "Alice", "last": "Smith", "score": 10},
            {"first": "Bob", "last": "Jones", "score": 20},
        ]
        right = [
            {"first": "Alice", "last": "Smith", "score": 15},
            {"first": "Alice", "last": "Jones", "score": 30},
        ]
        result = merge(left, right, key=["first", "last"])
        assert len(result) == 3
        # Alice Smith: merged (both sides)
        alice_smith = [r for r in result if r["first"] == "Alice" and r["last"] == "Smith"]
        assert len(alice_smith) == 1
        # Bob Jones: only in left
        bob = [r for r in result if r["first"] == "Bob"]
        assert len(bob) == 1
        assert bob[0]["score"] == 20
        # Alice Jones: only in right
        alice_jones = [r for r in result if r["first"] == "Alice" and r["last"] == "Jones"]
        assert len(alice_jones) == 1
        assert alice_jones[0]["score"] == 30

    def test_three_column_key(self):
        """Three-column composite key merges correctly."""
        left = [
            {"dept": "eng", "team": "alpha", "role": "lead", "salary": 100},
            {"dept": "eng", "team": "beta", "role": "lead", "salary": 110},
        ]
        right = [
            {"dept": "eng", "team": "alpha", "role": "lead", "salary": 120},
            {"dept": "eng", "team": "alpha", "role": "dev", "salary": 80},
        ]
        result = merge(left, right, key=["dept", "team", "role"])
        assert len(result) == 3
        # eng/alpha/lead merged from both
        lead = [r for r in result if r["team"] == "alpha" and r["role"] == "lead"]
        assert len(lead) == 1
        # eng/beta/lead only in left
        beta = [r for r in result if r["team"] == "beta"]
        assert len(beta) == 1
        assert beta[0]["salary"] == 110
        # eng/alpha/dev only in right
        dev = [r for r in result if r["role"] == "dev"]
        assert len(dev) == 1
        assert dev[0]["salary"] == 80

    def test_composite_key_conflict_resolution(self):
        """Composite key merge resolves conflicts with prefer parameter."""
        left = [{"x": 1, "y": "a", "val": "LEFT"}]
        right = [{"x": 1, "y": "a", "val": "RIGHT"}]
        result_b = merge(left, right, key=["x", "y"], prefer="b")
        assert result_b[0]["val"] == "RIGHT"
        result_a = merge(left, right, key=["x", "y"], prefer="a")
        assert result_a[0]["val"] == "LEFT"


# ─── Backward compatibility tests (3) ───────────────────────────────────────

class TestBackwardCompatibility:
    def test_single_string_key_still_works(self):
        """Single string key (original API) still works identically."""
        left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        right = [{"id": 1, "name": "Alicia"}, {"id": 3, "name": "Carol"}]
        result = merge(left, right, key="id")
        assert len(result) == 3
        ids = {r["id"] for r in result}
        assert ids == {1, 2, 3}

    def test_key_none_still_works(self):
        """key=None still appends and deduplicates."""
        left = [{"a": 1}, {"a": 2}]
        right = [{"a": 2}, {"a": 3}]
        result = merge(left, right, key=None)
        assert len(result) == 3

    def test_diff_with_string_key(self):
        """diff() still works with a plain string key."""
        a = [{"id": 1, "v": "x"}, {"id": 2, "v": "y"}]
        b = [{"id": 1, "v": "x"}, {"id": 2, "v": "z"}]
        d = diff(a, b, key="id")
        assert d["unchanged"] == 1
        assert len(d["modified"]) == 1


# ─── Hierarchical resolution tests (2) ──────────────────────────────────────

class TestHierarchicalResolution:
    def test_primary_secondary_key(self):
        """Primary+secondary key distinguishes rows that share a primary key."""
        left = [
            {"region": "US", "product": "A", "sales": 100},
            {"region": "US", "product": "B", "sales": 200},
        ]
        right = [
            {"region": "US", "product": "A", "sales": 150},
            {"region": "EU", "product": "A", "sales": 50},
        ]
        result = merge(left, right, key=["region", "product"])
        assert len(result) == 3
        us_a = [r for r in result if r["region"] == "US" and r["product"] == "A"]
        assert len(us_a) == 1

    def test_hierarchical_preserves_unique_rows(self):
        """Rows unique to either side are preserved with composite keys."""
        left = [{"a": 1, "b": 1, "v": "L"}]
        right = [{"a": 1, "b": 2, "v": "R"}]
        result = merge(left, right, key=["a", "b"])
        assert len(result) == 2
        vals = {r["v"] for r in result}
        assert vals == {"L", "R"}


# ─── diff with composite key tests (2) ──────────────────────────────────────

class TestDiffCompositeKey:
    def test_diff_composite_key_added_removed(self):
        """diff() correctly detects added/removed rows with composite key."""
        a = [
            {"x": 1, "y": "a", "v": 10},
            {"x": 2, "y": "b", "v": 20},
        ]
        b = [
            {"x": 1, "y": "a", "v": 10},
            {"x": 3, "y": "c", "v": 30},
        ]
        d = diff(a, b, key=["x", "y"])
        assert d["unchanged"] == 1
        assert len(d["added"]) == 1
        assert len(d["removed"]) == 1
        assert d["added"][0]["x"] == 3
        assert d["removed"][0]["x"] == 2

    def test_diff_composite_key_modified(self):
        """diff() detects modifications with composite key."""
        a = [{"x": 1, "y": "a", "v": 10}]
        b = [{"x": 1, "y": "a", "v": 99}]
        d = diff(a, b, key=["x", "y"])
        assert d["unchanged"] == 0
        assert len(d["modified"]) == 1
        assert d["modified"][0]["changes"]["v"] == {"old": 10, "new": 99}


# ─── Edge case tests (5) ────────────────────────────────────────────────────

class TestEdgeCases:
    def test_none_in_composite_key_column(self):
        """Rows with None in any composite key column go to none_key_rows."""
        left = [
            {"a": 1, "b": "x", "v": 10},
            {"a": None, "b": "y", "v": 20},
        ]
        right = [
            {"a": 1, "b": "x", "v": 15},
        ]
        result = merge(left, right, key=["a", "b"])
        # Row with None key preserved, plus the merged row
        assert len(result) == 2
        none_row = [r for r in result if r.get("a") is None]
        assert len(none_row) == 1

    def test_duplicate_composite_keys(self):
        """Duplicate composite keys warn and keep last."""
        left = [
            {"a": 1, "b": 2, "v": "first"},
            {"a": 1, "b": 2, "v": "second"},
        ]
        right = [{"a": 3, "b": 4, "v": "other"}]
        with pytest.warns(UserWarning, match="Duplicate keys"):
            result = merge(left, right, key=["a", "b"])
        # One from left (last dup kept) + one from right
        assert len(result) == 2

    def test_empty_key_list_raises(self):
        """Empty key list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            merge([{"a": 1}], [{"a": 2}], key=[])

    def test_single_element_list_like_string(self):
        """Single-element list key behaves identically to string key."""
        left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        right = [{"id": 1, "name": "Alicia"}, {"id": 3, "name": "Carol"}]
        result_str = merge(left, right, key="id")
        result_list = merge(left, right, key=["id"])
        # Same number of results
        assert len(result_str) == len(result_list)
        # Same ids
        ids_str = {r["id"] for r in result_str}
        ids_list = {r["id"] for r in result_list}
        assert ids_str == ids_list

    def test_key_column_missing_raises(self):
        """Missing key column raises KeyError."""
        left = [{"a": 1, "b": 2}]
        right = [{"a": 3, "b": 4}]
        with pytest.raises(KeyError, match="Key columns not found"):
            merge(left, right, key=["a", "nonexistent"])
