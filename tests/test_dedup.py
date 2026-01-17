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

"""Tests for deduplication engine."""
from crdt_merge.dedup import dedup_list, dedup_records, DedupIndex, MinHashDedup

class TestExactDedup:
    def test_basic(self):
        items = ["hello", "world", "hello", "foo", "world"]
        unique, dups = dedup_list(items, method="exact")
        assert unique == ["hello", "world", "foo"]
        assert dups == [2, 4]

    def test_no_duplicates(self):
        items = ["a", "b", "c"]
        unique, dups = dedup_list(items)
        assert unique == items
        assert dups == []

    def test_all_duplicates(self):
        items = ["x", "x", "x"]
        unique, dups = dedup_list(items)
        assert unique == ["x"]
        assert dups == [1, 2]

    def test_case_insensitive(self):
        items = ["Hello World", "hello world", "HELLO WORLD"]
        unique, dups = dedup_list(items)
        assert len(unique) == 1

    def test_whitespace_preservation(self):
        """BUG-6 fix: exact dedup preserves whitespace differences."""
        # Different whitespace = different records in exact mode
        items = ["hello  world", "hello world", "hello   world"]
        unique, dups = dedup_list(items)
        assert len(unique) == 3  # All distinct (exact = truly exact)
    
    def test_whitespace_tabs_vs_newlines(self):
        """BUG-6 fix: tabs and newlines are not collapsed to spaces."""
        items = ["hello\tworld", "hello\nworld", "hello world"]
        unique, dups = dedup_list(items)
        assert len(unique) == 3  # All distinct
    
    def test_case_insensitive_exact(self):
        """Exact dedup is case-insensitive but whitespace-preserving."""
        items = ["Hello World", "hello world", "HELLO WORLD"]
        unique, dups = dedup_list(items)
        assert len(unique) == 1  # Same after lowering

    def test_empty_list(self):
        unique, dups = dedup_list([])
        assert unique == []
        assert dups == []

class TestFuzzyDedup:
    def test_similar_strings(self):
        items = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumped over the lazy dog",
            "Something completely different",
        ]
        unique, dups = dedup_list(items, method="fuzzy", threshold=0.8)
        assert len(unique) == 2
    
    def test_different_strings(self):
        items = ["apple pie recipe", "quantum physics paper", "dog walking tips"]
        unique, dups = dedup_list(items, method="fuzzy", threshold=0.8)
        assert len(unique) == 3

    def test_high_threshold(self):
        items = ["hello world", "hello worlds"]
        unique, dups = dedup_list(items, method="fuzzy", threshold=0.99)
        assert len(unique) == 2  # Not similar enough

    def test_low_threshold(self):
        items = ["hello world", "hello worlds"]
        unique, dups = dedup_list(items, method="fuzzy", threshold=0.5)
        assert len(unique) == 1

class TestDedupRecords:
    def test_basic(self):
        records = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Alice", "age": 30},
        ]
        unique, removed = dedup_records(records)
        assert len(unique) == 2
        assert removed == 1

    def test_column_subset(self):
        records = [
            {"name": "Alice", "age": 30, "id": 1},
            {"name": "Alice", "age": 30, "id": 2},
        ]
        unique, removed = dedup_records(records, columns=["name", "age"])
        assert len(unique) == 1
        assert removed == 1

class TestDedupIndex:
    def test_merge_indices(self):
        idx_a = DedupIndex("worker_a")
        idx_a.add_exact("hello")
        idx_a.add_exact("world")
        
        idx_b = DedupIndex("worker_b")
        idx_b.add_exact("world")
        idx_b.add_exact("foo")
        
        merged = idx_a.merge(idx_b)
        assert merged.size == 3

class TestMinHashDedup:
    def test_basic(self):
        mh = MinHashDedup(num_hashes=64, threshold=0.5)
        items = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumped over the lazy dogs",
            "Something completely different about quantum mechanics",
        ]
        unique = mh.dedup(items, text_fn=lambda x: x)
        assert len(unique) == 2

    def test_all_unique(self):
        mh = MinHashDedup(num_hashes=64, threshold=0.9)
        items = ["apple", "banana", "cherry"]
        unique = mh.dedup(items, text_fn=lambda x: x)
        assert len(unique) == 3
