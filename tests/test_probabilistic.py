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

"""Tests for probabilistic CRDTs (v0.5.0)."""
import pytest
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS

# ══════════════════════════════════════════════════════════════════════════
# MergeableHLL Tests
# ══════════════════════════════════════════════════════════════════════════

class TestHLLBasic:
    def test_empty_cardinality(self):
        hll = MergeableHLL(precision=10)
        assert hll.cardinality() == 0.0

    def test_single_item(self):
        hll = MergeableHLL(precision=14)
        hll.add("hello")
        assert hll.cardinality() > 0

    def test_add_all(self):
        hll = MergeableHLL(precision=14)
        hll.add_all(range(1000))
        est = hll.cardinality()
        # Within 10% for 1000 items at precision 14
        assert 900 < est < 1100, f"Expected ~1000, got {est}"

    def test_duplicate_items_no_increase(self):
        hll = MergeableHLL(precision=14)
        hll.add_all(range(100))
        est1 = hll.cardinality()
        hll.add_all(range(100))  # duplicates
        est2 = hll.cardinality()
        # Should be roughly the same
        assert abs(est2 - est1) < est1 * 0.05

    def test_precision_bounds(self):
        with pytest.raises(ValueError):
            MergeableHLL(precision=3)
        with pytest.raises(ValueError):
            MergeableHLL(precision=19)

    def test_size_bytes(self):
        hll = MergeableHLL(precision=14)
        assert hll.size_bytes() == 2**14  # 16384 bytes

    def test_standard_error(self):
        hll = MergeableHLL(precision=14)
        assert abs(hll.standard_error() - 0.0081) < 0.001

class TestHLLMerge:
    def test_merge_disjoint(self):
        a = MergeableHLL(precision=14)
        a.add_all(range(1000))
        b = MergeableHLL(precision=14)
        b.add_all(range(1000, 2000))
        merged = a.merge(b)
        est = merged.cardinality()
        assert 1800 < est < 2200, f"Expected ~2000, got {est}"

    def test_merge_overlapping(self):
        a = MergeableHLL(precision=14)
        a.add_all(range(1000))
        b = MergeableHLL(precision=14)
        b.add_all(range(500, 1500))
        merged = a.merge(b)
        est = merged.cardinality()
        assert 1350 < est < 1650, f"Expected ~1500, got {est}"

    def test_merge_commutative(self):
        a = MergeableHLL(precision=12)
        a.add_all(range(500))
        b = MergeableHLL(precision=12)
        b.add_all(range(300, 800))
        assert a.merge(b) == b.merge(a)

    def test_merge_associative(self):
        a = MergeableHLL(precision=12)
        a.add_all(range(200))
        b = MergeableHLL(precision=12)
        b.add_all(range(100, 300))
        c = MergeableHLL(precision=12)
        c.add_all(range(200, 400))
        assert a.merge(b).merge(c) == a.merge(b.merge(c))

    def test_merge_idempotent(self):
        a = MergeableHLL(precision=12)
        a.add_all(range(500))
        assert a.merge(a) == a

    def test_merge_different_precision_fails(self):
        a = MergeableHLL(precision=10)
        b = MergeableHLL(precision=12)
        with pytest.raises(ValueError):
            a.merge(b)

class TestHLLSerialization:
    def test_roundtrip(self):
        hll = MergeableHLL(precision=10)
        hll.add_all(range(500))
        d = hll.to_dict()
        restored = MergeableHLL.from_dict(d)
        assert restored == hll
        assert abs(restored.cardinality() - hll.cardinality()) < 0.01

    def test_wire_format_roundtrip(self):
        """Test with the wire format."""
        from crdt_merge.wire import serialize, deserialize
        hll = MergeableHLL(precision=10)
        hll.add_all(range(200))
        d = hll.to_dict()
        data = serialize(d)
        restored = deserialize(data)
        hll2 = MergeableHLL.from_dict(restored)
        assert hll2 == hll

# ══════════════════════════════════════════════════════════════════════════
# MergeableBloom Tests
# ══════════════════════════════════════════════════════════════════════════

class TestBloomBasic:
    def test_add_and_contains(self):
        bloom = MergeableBloom(capacity=1000, fp_rate=0.01)
        bloom.add("alice")
        bloom.add("bob")
        assert bloom.contains("alice")
        assert bloom.contains("bob")

    def test_absent_item(self):
        bloom = MergeableBloom(capacity=1000, fp_rate=0.01)
        bloom.add("alice")
        # This COULD be a false positive, but very unlikely for a single absent item
        # Test with many items to be safe
        false_pos = sum(1 for i in range(1000) if bloom.contains(f"absent_{i}"))
        assert false_pos < 20  # < 2% with 0.01 fp_rate and only 1 item

    def test_add_all(self):
        bloom = MergeableBloom(capacity=10000, fp_rate=0.01)
        items = [f"item_{i}" for i in range(1000)]
        bloom.add_all(items)
        for item in items:
            assert bloom.contains(item)

    def test_false_positive_rate(self):
        bloom = MergeableBloom(capacity=1000, fp_rate=0.01)
        bloom.add_all(range(1000))
        # Check items NOT in the set
        fp = sum(1 for i in range(10000, 11000) if bloom.contains(i))
        # Should be around 1% = 10 out of 1000, allow 5x margin
        assert fp < 50, f"False positive rate too high: {fp}/1000"

class TestBloomMerge:
    def test_merge_contains_both(self):
        a = MergeableBloom(capacity=1000, fp_rate=0.01)
        a.add("alice")
        b = MergeableBloom(capacity=1000, fp_rate=0.01)
        b.add("bob")
        merged = a.merge(b)
        assert merged.contains("alice")
        assert merged.contains("bob")

    def test_merge_commutative(self):
        a = MergeableBloom(capacity=1000, fp_rate=0.01)
        a.add_all(["a", "b", "c"])
        b = MergeableBloom(capacity=1000, fp_rate=0.01)
        b.add_all(["d", "e", "f"])
        assert a.merge(b) == b.merge(a)

    def test_merge_associative(self):
        a = MergeableBloom(capacity=1000, fp_rate=0.01)
        a.add("x")
        b = MergeableBloom(capacity=1000, fp_rate=0.01)
        b.add("y")
        c = MergeableBloom(capacity=1000, fp_rate=0.01)
        c.add("z")
        assert a.merge(b).merge(c) == a.merge(b.merge(c))

    def test_merge_idempotent(self):
        a = MergeableBloom(capacity=1000, fp_rate=0.01)
        a.add_all(["a", "b", "c"])
        assert a.merge(a) == a

    def test_merge_different_params_fails(self):
        a = MergeableBloom(capacity=1000, fp_rate=0.01)
        b = MergeableBloom(capacity=2000, fp_rate=0.01)
        with pytest.raises(ValueError):
            a.merge(b)

class TestBloomSerialization:
    def test_roundtrip(self):
        bloom = MergeableBloom(capacity=1000, fp_rate=0.01)
        bloom.add_all(["alice", "bob", "charlie"])
        d = bloom.to_dict()
        restored = MergeableBloom.from_dict(d)
        assert restored == bloom
        assert restored.contains("alice")

    def test_wire_format_roundtrip(self):
        from crdt_merge.wire import serialize, deserialize
        bloom = MergeableBloom(capacity=100, fp_rate=0.05)
        bloom.add_all(["x", "y", "z"])
        d = bloom.to_dict()
        data = serialize(d)
        restored = deserialize(data)
        bloom2 = MergeableBloom.from_dict(restored)
        assert bloom2 == bloom

# ══════════════════════════════════════════════════════════════════════════
# MergeableCMS Tests
# ══════════════════════════════════════════════════════════════════════════

class TestCMSBasic:
    def test_single_item(self):
        cms = MergeableCMS(width=1000, depth=5)
        cms.add("hello", count=10)
        assert cms.estimate("hello") == 10

    def test_multiple_items(self):
        cms = MergeableCMS(width=2000, depth=7)
        cms.add("a", 100)
        cms.add("b", 50)
        cms.add("c", 1)
        assert cms.estimate("a") >= 100  # may overcount
        assert cms.estimate("b") >= 50
        assert cms.estimate("c") >= 1

    def test_absent_item(self):
        cms = MergeableCMS(width=2000, depth=7)
        cms.add("present", 100)
        est = cms.estimate("absent")
        # Should be 0 or very small for a sparse sketch
        assert est < 10

    def test_add_all(self):
        cms = MergeableCMS(width=2000, depth=7)
        cms.add_all(["a", "b", "a", "a"])
        assert cms.estimate("a") >= 3

    def test_total(self):
        cms = MergeableCMS(width=1000, depth=5)
        cms.add("a", 10)
        cms.add("b", 20)
        assert cms.total == 30

    def test_invalid_dimensions(self):
        with pytest.raises(ValueError):
            MergeableCMS(width=0, depth=5)

class TestCMSMerge:
    def test_merge_takes_max(self):
        a = MergeableCMS(width=1000, depth=5)
        a.add("x", 100)
        b = MergeableCMS(width=1000, depth=5)
        b.add("x", 50)
        merged = a.merge(b)
        assert merged.estimate("x") >= 100  # max(100, 50)

    def test_merge_commutative(self):
        a = MergeableCMS(width=500, depth=5)
        a.add("a", 10)
        b = MergeableCMS(width=500, depth=5)
        b.add("b", 20)
        assert a.merge(b) == b.merge(a)

    def test_merge_associative(self):
        a = MergeableCMS(width=500, depth=5)
        a.add("x", 10)
        b = MergeableCMS(width=500, depth=5)
        b.add("y", 20)
        c = MergeableCMS(width=500, depth=5)
        c.add("z", 30)
        assert a.merge(b).merge(c) == a.merge(b.merge(c))

    def test_merge_idempotent(self):
        a = MergeableCMS(width=500, depth=5)
        a.add("hello", 42)
        assert a.merge(a) == a

    def test_merge_different_dimensions_fails(self):
        a = MergeableCMS(width=500, depth=5)
        b = MergeableCMS(width=1000, depth=5)
        with pytest.raises(ValueError):
            a.merge(b)

class TestCMSSerialization:
    def test_roundtrip(self):
        cms = MergeableCMS(width=100, depth=3)
        cms.add("a", 50)
        cms.add("b", 25)
        d = cms.to_dict()
        restored = MergeableCMS.from_dict(d)
        assert restored == cms
        assert restored.estimate("a") == cms.estimate("a")

    def test_wire_format_roundtrip(self):
        from crdt_merge.wire import serialize, deserialize
        cms = MergeableCMS(width=50, depth=3)
        cms.add("x", 10)
        d = cms.to_dict()
        data = serialize(d)
        restored = deserialize(data)
        cms2 = MergeableCMS.from_dict(restored)
        assert cms2 == cms

# ══════════════════════════════════════════════════════════════════════════
# Cross-type CRDT verification (all 3 types)
# ══════════════════════════════════════════════════════════════════════════

class TestCRDTPropertiesAll:
    """Verify all three probabilistic types satisfy CRDT properties."""

    def test_hll_all_properties(self):
        """HLL: commutative + associative + idempotent."""
        a, b, c = MergeableHLL(8), MergeableHLL(8), MergeableHLL(8)
        a.add_all(range(50))
        b.add_all(range(25, 75))
        c.add_all(range(50, 100))
        # Commutative
        assert a.merge(b) == b.merge(a)
        # Associative
        assert a.merge(b).merge(c) == a.merge(b.merge(c))
        # Idempotent
        assert a.merge(a) == a

    def test_bloom_all_properties(self):
        """Bloom: commutative + associative + idempotent."""
        a = MergeableBloom(100, 0.05)
        b = MergeableBloom(100, 0.05)
        c = MergeableBloom(100, 0.05)
        a.add_all(["a", "b"])
        b.add_all(["c", "d"])
        c.add_all(["e", "f"])
        assert a.merge(b) == b.merge(a)
        assert a.merge(b).merge(c) == a.merge(b.merge(c))
        assert a.merge(a) == a

    def test_cms_all_properties(self):
        """CMS: commutative + associative + idempotent."""
        a = MergeableCMS(200, 3)
        b = MergeableCMS(200, 3)
        c = MergeableCMS(200, 3)
        a.add("x", 10)
        b.add("y", 20)
        c.add("z", 30)
        assert a.merge(b) == b.merge(a)
        assert a.merge(b).merge(c) == a.merge(b.merge(c))
        assert a.merge(a) == a
