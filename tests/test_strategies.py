"""Tests for crdt_merge.strategies — Composable Merge Strategies."""
import pytest
import time
from crdt_merge.strategies import (
    LWW, MaxWins, MinWins, UnionSet, Priority, Concat, Custom, MergeSchema,
)


# ===========================================================================
# Individual Strategy Tests
# ===========================================================================

class TestLWW:
    def test_later_timestamp_wins(self):
        s = LWW()
        assert s.resolve("old", "new", ts_a=1.0, ts_b=2.0) == "new"
        assert s.resolve("old", "new", ts_a=2.0, ts_b=1.0) == "old"

    def test_tie_breaks_by_node_id(self):
        s = LWW()
        assert s.resolve("a_val", "b_val", ts_a=1.0, ts_b=1.0, node_a="a", node_b="b") == "b_val"
        assert s.resolve("z_val", "a_val", ts_a=1.0, ts_b=1.0, node_a="z", node_b="a") == "z_val"

    def test_commutative(self):
        s = LWW()
        for _ in range(100):
            ab = s.resolve("x", "y", ts_a=1.0, ts_b=2.0)
            ba = s.resolve("y", "x", ts_a=2.0, ts_b=1.0)
            assert ab == ba

    def test_idempotent(self):
        s = LWW()
        v = s.resolve("same", "same", ts_a=1.0, ts_b=1.0)
        assert v == "same"


class TestMaxWins:
    def test_picks_higher(self):
        s = MaxWins()
        assert s.resolve(10, 20) == 20
        assert s.resolve(20, 10) == 20

    def test_commutative(self):
        s = MaxWins()
        assert s.resolve(5, 9) == s.resolve(9, 5)

    def test_associative(self):
        s = MaxWins()
        a, b, c = 3, 7, 5
        assert s.resolve(s.resolve(a, b), c) == s.resolve(a, s.resolve(b, c))

    def test_idempotent(self):
        s = MaxWins()
        assert s.resolve(42, 42) == 42

    def test_with_strings(self):
        s = MaxWins()
        assert s.resolve("apple", "banana") == "banana"

    def test_with_floats(self):
        s = MaxWins()
        assert s.resolve(3.14, 2.71) == 3.14


class TestMinWins:
    def test_picks_lower(self):
        s = MinWins()
        assert s.resolve(10, 20) == 10
        assert s.resolve(20, 10) == 10

    def test_commutative(self):
        s = MinWins()
        assert s.resolve(5, 9) == s.resolve(9, 5)

    def test_associative(self):
        s = MinWins()
        a, b, c = 3, 7, 5
        assert s.resolve(s.resolve(a, b), c) == s.resolve(a, s.resolve(b, c))

    def test_idempotent(self):
        s = MinWins()
        assert s.resolve(42, 42) == 42


class TestUnionSet:
    def test_union_comma_separated(self):
        s = UnionSet(separator=",")
        assert s.resolve("a,b", "b,c") == "a,b,c"

    def test_union_pipe_separated(self):
        s = UnionSet(separator="|")
        assert s.resolve("x|y", "y|z") == "x|y|z"

    def test_commutative(self):
        s = UnionSet(separator=",")
        ab = s.resolve("a,b", "c,d")
        ba = s.resolve("c,d", "a,b")
        assert set(ab.split(",")) == set(ba.split(","))

    def test_idempotent(self):
        s = UnionSet(separator=",")
        result = s.resolve("a,b,c", "a,b,c")
        assert set(result.split(",")) == {"a", "b", "c"}

    def test_empty_values(self):
        s = UnionSet(separator=",")
        assert s.resolve("", "a,b") == "a,b"
        assert s.resolve("a,b", "") == "a,b"

    def test_preserves_sorted_order(self):
        s = UnionSet(separator=",")
        result = s.resolve("z,a", "m,b")
        parts = result.split(",")
        assert parts == sorted(parts)


class TestPriority:
    def test_higher_priority_wins(self):
        s = Priority(["low", "medium", "high", "critical"])
        assert s.resolve("low", "high") == "high"
        assert s.resolve("critical", "low") == "critical"

    def test_commutative(self):
        s = Priority(["draft", "review", "approved", "published"])
        assert s.resolve("draft", "published") == s.resolve("published", "draft")

    def test_unknown_value_loses(self):
        s = Priority(["a", "b", "c"])
        assert s.resolve("unknown", "b") == "b"

    def test_idempotent(self):
        s = Priority(["a", "b", "c"])
        assert s.resolve("b", "b") == "b"


class TestConcat:
    def test_concat_with_separator(self):
        s = Concat(separator=" | ")
        result = s.resolve("note1", "note2")
        assert "note1" in result and "note2" in result

    def test_commutative_via_sorting(self):
        s = Concat(separator=",")
        ab = s.resolve("x", "y")
        ba = s.resolve("y", "x")
        assert ab == ba  # sorted, so commutative

    def test_idempotent(self):
        s = Concat(separator=",")
        assert s.resolve("same", "same") == "same"

    def test_no_duplicate_parts(self):
        s = Concat(separator=",")
        result = s.resolve("a,b", "b,c")
        parts = result.split(",")
        assert len(parts) == len(set(parts))


class TestCustom:
    def test_custom_function(self):
        s = Custom(fn=lambda a, b, **kw: a + b)
        assert s.resolve(3, 4) == 7

    def test_custom_with_timestamps(self):
        s = Custom(fn=lambda a, b, ts_a=0, ts_b=0, **kw: a if ts_a > ts_b else b)
        assert s.resolve("old", "new", ts_a=2.0, ts_b=1.0) == "old"
        assert s.resolve("old", "new", ts_a=1.0, ts_b=2.0) == "new"


# ===========================================================================
# MergeSchema Tests
# ===========================================================================

class TestMergeSchema:
    def test_basic_schema(self):
        schema = MergeSchema(
            default=LWW(),
            score=MaxWins(),
            tags=UnionSet(separator=","),
        )
        assert isinstance(schema.strategy_for("score"), MaxWins)
        assert isinstance(schema.strategy_for("tags"), UnionSet)
        assert isinstance(schema.strategy_for("unknown_col"), LWW)

    def test_default_is_lww(self):
        schema = MergeSchema(name=MaxWins())
        assert isinstance(schema.strategy_for("name"), MaxWins)
        # Default should be LWW
        strat = schema.strategy_for("other")
        assert isinstance(strat, LWW)

    def test_resolve_row(self):
        schema = MergeSchema(
            default=LWW(),
            score=MaxWins(),
            tags=UnionSet(separator=","),
        )
        row_a = {"id": "1", "score": 10, "tags": "a,b", "name": "old", "_ts": 1.0}
        row_b = {"id": "1", "score": 20, "tags": "b,c", "name": "new", "_ts": 2.0}
        resolved = schema.resolve_row(row_a, row_b, timestamp_col="_ts")
        assert resolved["score"] == 20  # MaxWins
        assert set(resolved["tags"].split(",")) == {"a", "b", "c"}  # UnionSet
        assert resolved["name"] == "new"  # LWW, ts_b > ts_a

    def test_to_dict_roundtrip(self):
        schema = MergeSchema(
            default=LWW(),
            score=MaxWins(),
            tags=UnionSet(separator=","),
            status=Priority(["draft", "review", "published"]),
        )
        d = schema.to_dict()
        assert d["score"]["strategy"] == "MaxWins"
        assert d["tags"]["strategy"] == "UnionSet"
        assert d["status"]["strategy"] == "Priority"

    def test_empty_schema_uses_defaults(self):
        schema = MergeSchema()
        strat = schema.strategy_for("anything")
        assert isinstance(strat, LWW)

    def test_schema_with_all_strategies(self):
        schema = MergeSchema(
            a=LWW(),
            b=MaxWins(),
            c=MinWins(),
            d=UnionSet(separator=","),
            e=Priority(["x", "y", "z"]),
            f=Concat(separator=" | "),
            g=Custom(fn=lambda a, b, **kw: max(a, b)),
        )
        for col in "abcdefg":
            assert schema.strategy_for(col) is not None


# ===========================================================================
# CRDT Property Proofs for All Strategies
# ===========================================================================

class TestCRDTProperties:
    """Verify all strategies satisfy CRDT laws."""

    strategies = [
        ("LWW", LWW(), lambda: (1.0, 2.0)),
        ("MaxWins", MaxWins(), lambda: (0.0, 0.0)),
        ("MinWins", MinWins(), lambda: (0.0, 0.0)),
    ]

    def test_all_commutative(self):
        """merge(A, B) == merge(B, A)"""
        import random
        for name, s, ts_fn in self.strategies:
            for _ in range(100):
                a, b = random.randint(0, 1000), random.randint(0, 1000)
                ts_a, ts_b = random.random(), random.random()
                ab = s.resolve(a, b, ts_a=ts_a, ts_b=ts_b)
                ba = s.resolve(b, a, ts_a=ts_b, ts_b=ts_a)
                assert ab == ba, f"{name}: commutativity failed"

    def test_all_associative(self):
        """merge(merge(A,B),C) == merge(A,merge(B,C))"""
        import random
        for name, s, _ in [("MaxWins", MaxWins(), None), ("MinWins", MinWins(), None)]:
            for _ in range(100):
                a, b, c = random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)
                ab_c = s.resolve(s.resolve(a, b), c)
                a_bc = s.resolve(a, s.resolve(b, c))
                assert ab_c == a_bc, f"{name}: associativity failed"

    def test_all_idempotent(self):
        """merge(A, A) == A"""
        import random
        for name, s, _ in self.strategies:
            for _ in range(100):
                v = random.randint(0, 1000)
                assert s.resolve(v, v) == v, f"{name}: idempotency failed"
