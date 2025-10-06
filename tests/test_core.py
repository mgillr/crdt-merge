"""Tests for CRDT core primitives — correctness proofs."""
import time
import pytest
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap


class TestGCounter:
    def test_basic_increment(self):
        c = GCounter()
        c.increment("node1", 5)
        c.increment("node2", 3)
        assert c.value == 8

    def test_merge_commutativity(self):
        a = GCounter()
        a.increment("n1", 10)
        b = GCounter()
        b.increment("n2", 20)
        assert a.merge(b).value == b.merge(a).value == 30

    def test_merge_associativity(self):
        a, b, c = GCounter(), GCounter(), GCounter()
        a.increment("n1", 5)
        b.increment("n2", 10)
        c.increment("n3", 15)
        ab_c = a.merge(b).merge(c)
        a_bc = a.merge(b.merge(c))
        assert ab_c.value == a_bc.value == 30

    def test_merge_idempotency(self):
        a = GCounter()
        a.increment("n1", 42)
        assert a.merge(a).value == 42

    def test_concurrent_increments(self):
        """Two nodes increment concurrently — both preserved."""
        a = GCounter()
        a.increment("n1", 5)
        b = GCounter()
        b.increment("n1", 3)
        b.increment("n2", 7)
        merged = a.merge(b)
        assert merged.value == 12  # max(5,3) + 7

    def test_serialization(self):
        a = GCounter()
        a.increment("n1", 42)
        d = a.to_dict()
        b = GCounter.from_dict(d)
        assert b.value == 42

    def test_negative_increment_raises(self):
        c = GCounter()
        with pytest.raises(ValueError):
            c.increment("n1", -1)


class TestPNCounter:
    def test_increment_decrement(self):
        c = PNCounter()
        c.increment("n1", 10)
        c.decrement("n1", 3)
        assert c.value == 7

    def test_merge_commutativity(self):
        a = PNCounter()
        a.increment("n1", 10)
        a.decrement("n1", 2)
        b = PNCounter()
        b.increment("n2", 5)
        assert a.merge(b).value == b.merge(a).value == 13

    def test_negative_value(self):
        c = PNCounter()
        c.decrement("n1", 5)
        assert c.value == -5

    def test_serialization(self):
        c = PNCounter()
        c.increment("n1", 10)
        c.decrement("n2", 3)
        d = c.to_dict()
        r = PNCounter.from_dict(d)
        assert r.value == 7


class TestLWWRegister:
    def test_latest_wins(self):
        a = LWWRegister("old", 1.0)
        b = LWWRegister("new", 2.0)
        assert a.merge(b).value == "new"
        assert b.merge(a).value == "new"

    def test_tie_breaks_on_node_id(self):
        a = LWWRegister("from_a", 1.0, "alpha")
        b = LWWRegister("from_b", 1.0, "beta")
        # beta > alpha, so b wins
        assert a.merge(b).value == "from_b"
        assert b.merge(a).value == "from_b"

    def test_commutativity(self):
        a = LWWRegister("x", 1.0, "a")
        b = LWWRegister("y", 2.0, "b")
        assert a.merge(b).value == b.merge(a).value

    def test_idempotency(self):
        a = LWWRegister("x", 1.0)
        assert a.merge(a).value == "x"

    def test_serialization(self):
        a = LWWRegister("hello", 42.0, "n1")
        d = a.to_dict()
        b = LWWRegister.from_dict(d)
        assert b.value == "hello"
        assert b.timestamp == 42.0


class TestORSet:
    def test_add_contains(self):
        s = ORSet()
        s.add("apple")
        s.add("banana")
        assert s.contains("apple")
        assert s.contains("banana")
        assert not s.contains("cherry")

    def test_remove(self):
        s = ORSet()
        s.add("apple")
        s.remove("apple")
        assert not s.contains("apple")

    def test_add_wins_over_concurrent_remove(self):
        """Add-wins semantics: concurrent add on one node, remove on another."""
        s1 = ORSet()
        s1.add("apple")
        
        # Fork: s2 is a snapshot before s1 adds a new tag
        s2 = ORSet()
        s2._elements = {k: set(v) for k, v in s1._elements.items()}
        
        # s1 adds apple again (new tag)
        s1.add("apple")
        
        # s2 removes apple (kills its tags)
        s2.remove("apple")
        
        # Merge: s1's new tag survives
        merged = s1.merge(s2)
        assert merged.contains("apple")

    def test_merge_commutativity(self):
        a = ORSet()
        a.add("x")
        a.add("y")
        b = ORSet()
        b.add("y")
        b.add("z")
        assert a.merge(b).value == b.merge(a).value == {"x", "y", "z"}

    def test_merge_idempotency(self):
        a = ORSet()
        a.add("x")
        assert a.merge(a).value == {"x"}

    def test_serialization(self):
        a = ORSet()
        a.add("hello")
        a.add("world")
        d = a.to_dict()
        b = ORSet.from_dict(d)
        assert b.value == {"hello", "world"}


class TestLWWMap:
    def test_basic_set_get(self):
        m = LWWMap()
        m.set("name", "Alice", 1.0)
        assert m.get("name") == "Alice"

    def test_latest_wins(self):
        m = LWWMap()
        m.set("name", "Alice", 1.0)
        m.set("name", "Bob", 2.0)
        assert m.get("name") == "Bob"

    def test_merge_different_keys(self):
        a = LWWMap()
        a.set("x", 1, 1.0)
        b = LWWMap()
        b.set("y", 2, 1.0)
        merged = a.merge(b)
        assert merged.value == {"x": 1, "y": 2}

    def test_merge_same_key_lww(self):
        a = LWWMap()
        a.set("x", "old", 1.0)
        b = LWWMap()
        b.set("x", "new", 2.0)
        merged = a.merge(b)
        assert merged.get("x") == "new"

    def test_merge_commutativity(self):
        a = LWWMap()
        a.set("x", "from_a", 1.0)
        b = LWWMap()
        b.set("x", "from_b", 2.0)
        assert a.merge(b).value == b.merge(a).value

    def test_delete(self):
        m = LWWMap()
        m.set("x", 1, 1.0)
        m.delete("x", 2.0)
        assert m.get("x") is None

    def test_set_after_delete(self):
        m = LWWMap()
        m.set("x", 1, 1.0)
        m.delete("x", 2.0)
        m.set("x", 2, 3.0)
        assert m.get("x") == 2

    def test_serialization(self):
        m = LWWMap()
        m.set("a", 1, 1.0, "n1")
        m.set("b", 2, 2.0, "n2")
        d = m.to_dict()
        r = LWWMap.from_dict(d)
        assert r.value == {"a": 1, "b": 2}
