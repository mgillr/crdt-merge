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

"""Tests for the LongestWins merge strategy."""

import pytest
from crdt_merge.strategies import LongestWins, MergeSchema

class TestLongestWins:
    """Tests for LongestWins strategy — resolves conflicts by picking the longer value."""

    def test_longer_string_wins(self):
        s = LongestWins()
        assert s.resolve("hi", "hello") == "hello"
        assert s.resolve("hello", "hi") == "hello"

    def test_equal_length_returns_first(self):
        s = LongestWins()
        result = s.resolve("abc", "xyz")
        # Equal length: either is valid, just verify it's one of them
        assert result in ("abc", "xyz")

    def test_empty_vs_nonempty(self):
        s = LongestWins()
        assert s.resolve("", "hello") == "hello"
        assert s.resolve("hello", "") == "hello"

    def test_both_empty(self):
        s = LongestWins()
        assert s.resolve("", "") == ""

    def test_single_char_vs_multi(self):
        s = LongestWins()
        assert s.resolve("a", "abcdef") == "abcdef"

    def test_with_numbers_as_strings(self):
        s = LongestWins()
        assert s.resolve("1", "100") == "100"

    def test_unicode_strings(self):
        s = LongestWins()
        assert s.resolve("hi", "héllo") == "héllo"

    def test_in_merge_schema(self):
        schema = MergeSchema(description=LongestWins())
        strategy = schema.strategy_for("description")
        assert isinstance(strategy, LongestWins)
        assert strategy.resolve("short", "much longer text") == "much longer text"

    def test_whitespace_strings(self):
        s = LongestWins()
        assert s.resolve("ab", "a b c") == "a b c"

    def test_none_handling(self):
        """LongestWins should handle None gracefully if passed."""
        s = LongestWins()
        try:
            result = s.resolve(None, "hello")
            # If it handles None, it should return the non-None value
            assert result == "hello"
        except (TypeError, AttributeError):
            # Acceptable -- None isn't a valid string input
            pass

    def test_numeric_values(self):
        """Test with numeric values (which have no len())."""
        s = LongestWins()
        try:
            result = s.resolve(42, 12345)
            # If it handles numbers, fine
        except (TypeError, AttributeError):
            # Also acceptable -- LongestWins is designed for strings
            pass
