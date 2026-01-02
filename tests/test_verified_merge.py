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

"""Tests for @verified_merge decorator (v0.4.0)."""

import random
import pytest
from crdt_merge.verify import verified_merge, CRDTVerificationError


class TestVerifiedMergeDecorator:
    """Test the @verified_merge decorator."""

    def test_valid_crdt_passes(self):
        """max(a, b) is a valid CRDT merge — should pass."""
        @verified_merge(gen_fn=lambda: random.randint(0, 1000), trials=200)
        def my_max(a, b):
            return max(a, b)

        assert my_max._crdt_verified.passed
        assert my_max(3, 7) == 7
        assert my_max(10, 2) == 10

    def test_valid_min_merge(self):
        """min(a, b) is also a valid CRDT merge."""
        @verified_merge(gen_fn=lambda: random.randint(0, 1000), trials=200)
        def my_min(a, b):
            return min(a, b)

        assert my_min._crdt_verified.passed
        assert my_min(3, 7) == 3

    def test_invalid_crdt_raises(self):
        """Second-argument-wins is NOT commutative — should fail."""
        with pytest.raises(CRDTVerificationError):
            @verified_merge(gen_fn=lambda: random.randint(0, 1000), trials=100)
            def bad_merge(a, b):
                return b  # Not commutative!

    def test_invalid_crdt_warn_mode(self):
        """on_fail='warn' should attach result but not raise."""
        @verified_merge(
            gen_fn=lambda: random.randint(0, 1000),
            trials=100,
            on_fail="warn"
        )
        def bad_merge(a, b):
            return b

        assert not bad_merge._crdt_verified.passed
        assert bad_merge(3, 7) == 7  # Still callable

    def test_no_gen_fn_raises(self):
        """Missing gen_fn should raise ValueError."""
        with pytest.raises(ValueError, match="gen_fn"):
            @verified_merge
            def no_gen(a, b):
                return a

    def test_custom_eq_fn(self):
        """Custom equality function should be used."""
        @verified_merge(
            gen_fn=lambda: random.uniform(0, 100),
            trials=100,
            eq_fn=lambda a, b: abs(a - b) < 0.01
        )
        def avg_merge(a, b):
            return max(a, b)

        assert avg_merge._crdt_verified.passed

    def test_verification_summary_attached(self):
        """The summary string should be attached to the function."""
        @verified_merge(gen_fn=lambda: random.randint(0, 10), trials=50)
        def my_max(a, b):
            return max(a, b)

        assert "CRDT Verification Report" in my_max._crdt_verification_summary

    def test_set_union_merge(self):
        """Set union is a valid CRDT merge."""
        @verified_merge(
            gen_fn=lambda: frozenset(random.sample(range(20), random.randint(0, 5))),
            trials=200,
            eq_fn=lambda a, b: a == b
        )
        def set_merge(a, b):
            return a | b

        assert set_merge._crdt_verified.passed

    def test_decorated_function_preserves_name(self):
        """functools.wraps should preserve the original function name."""
        @verified_merge(gen_fn=lambda: random.randint(0, 10), trials=50)
        def my_special_merge(a, b):
            """My special merge docstring."""
            return max(a, b)

        assert my_special_merge.__name__ == "my_special_merge"
        assert my_special_merge.__doc__ == "My special merge docstring."

    def test_crdt_verification_error_type(self):
        """CRDTVerificationError should be an Exception subclass."""
        assert issubclass(CRDTVerificationError, Exception)
