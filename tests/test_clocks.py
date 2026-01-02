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

"""Tests for crdt_merge.clocks — VectorClock and DottedVersionVector."""

import random

import pytest

from crdt_merge.clocks import (
    DottedVersionVector,
    Ordering,
    VectorClock,
)
from crdt_merge.verify import (
    verify_associative,
    verify_commutative,
    verify_convergence,
    verify_idempotent,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. VectorClock creation (3 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockCreation:
    def test_empty_clock(self):
        vc = VectorClock()
        assert vc.value == {}

    def test_single_node(self):
        vc = VectorClock({"a": 5})
        assert vc.value == {"a": 5}
        assert vc.get("a") == 5

    def test_multi_node_and_none_input(self):
        vc_multi = VectorClock({"a": 1, "b": 2, "c": 3})
        assert vc_multi.value == {"a": 1, "b": 2, "c": 3}
        vc_none = VectorClock(None)
        assert vc_none.value == {}


# ═════════════════════════════════════════════════════════════════════════════
# 2. VectorClock.increment (3 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockIncrement:
    def test_increment_new_node(self):
        vc = VectorClock()
        vc2 = vc.increment("a")
        assert vc2.get("a") == 1

    def test_increment_existing_node(self):
        vc = VectorClock({"a": 3})
        vc2 = vc.increment("a")
        assert vc2.get("a") == 4

    def test_increment_returns_new_instance(self):
        vc = VectorClock({"a": 1})
        vc2 = vc.increment("a")
        assert vc.get("a") == 1, "Original must be unchanged"
        assert vc2.get("a") == 2
        assert vc is not vc2


# ═════════════════════════════════════════════════════════════════════════════
# 3. VectorClock.get (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockGet:
    def test_get_existing_node(self):
        vc = VectorClock({"x": 42})
        assert vc.get("x") == 42

    def test_get_missing_node_returns_zero(self):
        vc = VectorClock({"x": 42})
        assert vc.get("y") == 0


# ═════════════════════════════════════════════════════════════════════════════
# 4. VectorClock.compare (5 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockCompare:
    def test_compare_before(self):
        a = VectorClock({"x": 1, "y": 1})
        b = VectorClock({"x": 2, "y": 2})
        assert a.compare(b) == Ordering.BEFORE

    def test_compare_after(self):
        a = VectorClock({"x": 3, "y": 3})
        b = VectorClock({"x": 1, "y": 2})
        assert a.compare(b) == Ordering.AFTER

    def test_compare_concurrent(self):
        a = VectorClock({"x": 2, "y": 1})
        b = VectorClock({"x": 1, "y": 2})
        assert a.compare(b) == Ordering.CONCURRENT

    def test_compare_equal(self):
        a = VectorClock({"x": 1, "y": 2})
        b = VectorClock({"x": 1, "y": 2})
        assert a.compare(b) == Ordering.EQUAL

    def test_compare_empty_vs_nonempty(self):
        empty = VectorClock()
        nonempty = VectorClock({"a": 1})
        assert empty.compare(nonempty) == Ordering.BEFORE
        assert nonempty.compare(empty) == Ordering.AFTER
        assert empty.compare(VectorClock()) == Ordering.EQUAL


# ═════════════════════════════════════════════════════════════════════════════
# 5. VectorClock.merge (4 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockMerge:
    def test_merge_disjoint_nodes(self):
        a = VectorClock({"x": 3})
        b = VectorClock({"y": 5})
        merged = a.merge(b)
        assert merged.value == {"x": 3, "y": 5}

    def test_merge_overlapping_nodes_element_wise_max(self):
        a = VectorClock({"x": 3, "y": 1})
        b = VectorClock({"x": 1, "y": 5})
        merged = a.merge(b)
        assert merged.value == {"x": 3, "y": 5}

    def test_merge_empty(self):
        a = VectorClock({"x": 2})
        empty = VectorClock()
        assert a.merge(empty).value == {"x": 2}
        assert empty.merge(a).value == {"x": 2}
        assert empty.merge(VectorClock()).value == {}

    def test_merge_returns_new_instance(self):
        a = VectorClock({"x": 1})
        b = VectorClock({"x": 2})
        merged = a.merge(b)
        assert merged is not a
        assert merged is not b
        assert a.get("x") == 1, "Original a must be unchanged"
        assert b.get("x") == 2, "Original b must be unchanged"


# ═════════════════════════════════════════════════════════════════════════════
# 6. VectorClock serialization (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestVectorClockSerialization:
    def test_roundtrip(self):
        vc = VectorClock({"a": 3, "b": 7, "c": 1})
        d = vc.to_dict()
        assert d["type"] == "vector_clock"
        restored = VectorClock.from_dict(d)
        assert restored == vc

    def test_empty_roundtrip(self):
        vc = VectorClock()
        restored = VectorClock.from_dict(vc.to_dict())
        assert restored == vc
        assert restored.value == {}


# ═════════════════════════════════════════════════════════════════════════════
# 7. DottedVersionVector creation (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestDVVCreation:
    def test_default(self):
        dvv = DottedVersionVector()
        assert dvv.value == {}
        assert dvv.dot is None

    def test_with_base_and_dot(self):
        base = VectorClock({"a": 3, "b": 2})
        dvv = DottedVersionVector(base=base, dot=("a", 4))
        assert dvv.value == {"a": 4, "b": 2}
        assert dvv.dot == ("a", 4)


# ═════════════════════════════════════════════════════════════════════════════
# 8. DottedVersionVector.advance (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestDVVAdvance:
    def test_advance_new_node(self):
        dvv = DottedVersionVector()
        advanced = dvv.advance("a")
        assert advanced.dot == ("a", 1)
        assert advanced.base == VectorClock()  # base unchanged

    def test_advance_existing_node(self):
        base = VectorClock({"a": 5})
        dvv = DottedVersionVector(base=base)
        advanced = dvv.advance("a")
        assert advanced.dot == ("a", 6)
        assert advanced.base == base  # base unchanged


# ═════════════════════════════════════════════════════════════════════════════
# 9. DottedVersionVector.merge (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestDVVMerge:
    def test_merge_two_dvvs(self):
        a = DottedVersionVector(
            base=VectorClock({"x": 2}), dot=("x", 3)
        )
        b = DottedVersionVector(
            base=VectorClock({"y": 1}), dot=("y", 2)
        )
        merged = a.merge(b)
        assert merged.dot is None, "Dots must be consumed into base"
        assert merged.value == {"x": 3, "y": 2}

    def test_merge_with_empty(self):
        dvv = DottedVersionVector(
            base=VectorClock({"a": 3}), dot=("a", 4)
        )
        empty = DottedVersionVector()
        merged = dvv.merge(empty)
        assert merged.value == {"a": 4}
        assert merged.dot is None


# ═════════════════════════════════════════════════════════════════════════════
# 10. DottedVersionVector.descends (2 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestDVVDescends:
    def test_descends_true(self):
        older = DottedVersionVector(base=VectorClock({"a": 1}))
        newer = DottedVersionVector(base=VectorClock({"a": 3}))
        assert newer.descends(older) is True

    def test_descends_false(self):
        a = DottedVersionVector(base=VectorClock({"x": 1}))
        b = DottedVersionVector(base=VectorClock({"x": 3}))
        assert a.descends(b) is False


# ═════════════════════════════════════════════════════════════════════════════
# 11. DottedVersionVector serialization (1 test)
# ═════════════════════════════════════════════════════════════════════════════


class TestDVVSerialization:
    def test_roundtrip(self):
        dvv = DottedVersionVector(
            base=VectorClock({"a": 3, "b": 7}), dot=("a", 4)
        )
        d = dvv.to_dict()
        assert d["type"] == "dotted_version_vector"
        restored = DottedVersionVector.from_dict(d)
        assert restored.value == dvv.value
        assert restored.dot == dvv.dot
        assert restored.base == dvv.base


# ═════════════════════════════════════════════════════════════════════════════
# 12. CRDT law verification (4 tests) — CRITICAL
# ═════════════════════════════════════════════════════════════════════════════


def _gen_vector_clock():
    """Generate a random VectorClock for property-based testing."""
    nodes = [f"node-{i}" for i in range(random.randint(1, 10))]
    vc = VectorClock()
    for node in nodes:
        for _ in range(random.randint(0, 20)):
            vc = vc.increment(node)
    return vc


class TestCRDTLaws:
    def test_vector_clock_commutative(self):
        result = verify_commutative(
            lambda a, b: a.merge(b), _gen_vector_clock, trials=1000
        )
        assert result.passed, f"Commutativity failed: {result.first_failure}"

    def test_vector_clock_associative(self):
        result = verify_associative(
            lambda a, b: a.merge(b), _gen_vector_clock, trials=1000
        )
        assert result.passed, f"Associativity failed: {result.first_failure}"

    def test_vector_clock_idempotent(self):
        result = verify_idempotent(
            lambda a, b: a.merge(b), _gen_vector_clock, trials=1000
        )
        assert result.passed, f"Idempotency failed: {result.first_failure}"

    def test_vector_clock_convergence(self):
        result = verify_convergence(
            lambda a, b: a.merge(b),
            _gen_vector_clock,
            trials=500,
            num_replicas=5,
        )
        assert result.passed, f"Convergence failed: {result.first_failure}"


# ═════════════════════════════════════════════════════════════════════════════
# 13. Edge cases (3 tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_negative_counter_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            VectorClock({"a": -1})

    def test_100_node_stress(self):
        """Merge two clocks with 100+ nodes each — must complete quickly."""
        nodes_a = {f"node-{i}": random.randint(1, 1000) for i in range(120)}
        nodes_b = {f"node-{i}": random.randint(1, 1000) for i in range(50, 170)}
        a = VectorClock(nodes_a)
        b = VectorClock(nodes_b)

        merged = a.merge(b)
        # All 170 distinct nodes present
        assert len(merged.value) == 170
        # Element-wise max holds
        for n in nodes_a:
            assert merged.get(n) >= nodes_a[n]
        for n in nodes_b:
            assert merged.get(n) >= nodes_b[n]

    def test_zero_counter_equivalence(self):
        """VectorClock({"a": 0}) and VectorClock({}) are equivalent."""
        a = VectorClock({"a": 0})
        b = VectorClock({})
        assert a == b
        assert a.value == b.value
        assert a.get("a") == 0
