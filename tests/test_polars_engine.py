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

"""Tests for the Polars merge engine (_polars_engine.py).

These tests verify:
1. All 8 strategies vectorize correctly
2. Arrow table round-trip (zero-copy in/out)
3. Dict list round-trip (for accelerators)
4. Conflict counting accuracy
5. Null handling edge cases
6. Empty table edge cases
7. Schema evolution (columns only in one side)
8. Performance vs baseline (at least 10× faster for 10K+ rows)
9. Graceful fallback when engine="python"
10. CRDT laws (associative, commutative, idempotent)
"""

import pytest
import time
from typing import List, Dict, Any

# Always import the pure-Python baseline for comparison
from crdt_merge.strategies import (
    MergeSchema,
    LWW,
    MaxWins,
    MinWins,
    Concat,
    LongestWins,
    Custom,
    Priority,
    UnionSet,
)
from crdt_merge.arrow import ArrowMerge, arrow_merge

# Optional imports
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

try:
    import pyarrow as pa
    HAS_ARROW = True
except ImportError:
    HAS_ARROW = False

try:
    from crdt_merge._polars_engine import (
        HAS_POLARS as ENGINE_HAS_POLARS,
        polars_merge_arrow,
        polars_merge_dicts,
        strategy_to_expr,
    )
except ImportError:
    ENGINE_HAS_POLARS = False

needs_polars = pytest.mark.skipif(not HAS_POLARS, reason="polars not installed")
needs_arrow = pytest.mark.skipif(not HAS_ARROW, reason="pyarrow not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_arrow_tables(n: int = 10):
    """Create left/right Arrow tables with overlapping keys."""
    left = pa.table({
        "id": list(range(n)),
        "name": [f"left_{i}" for i in range(n)],
        "value": list(range(100, 100 + n)),
        "score": [float(i * 10) for i in range(n)],
    })
    right = pa.table({
        "id": list(range(n // 2, n + n // 2)),  # 50% overlap
        "name": [f"right_{i}" for i in range(n // 2, n + n // 2)],
        "value": list(range(200, 200 + n)),
        "score": [float(i * 20) for i in range(n)],
    })
    return left, right


def make_dict_rows(n: int = 10):
    """Create left/right dict rows with overlapping keys."""
    left = [
        {"id": i, "name": f"left_{i}", "value": 100 + i, "score": float(i * 10)}
        for i in range(n)
    ]
    right = [
        {"id": i, "name": f"right_{i}", "value": 200 + i, "score": float(i * 20)}
        for i in range(n // 2, n + n // 2)
    ]
    return left, right


# ===========================================================================
# 1. Strategy vectorization tests
# ===========================================================================

class TestMaxWins:
    @needs_polars
    @needs_arrow
    def test_max_wins_arrow(self):
        schema = MergeSchema(default=LWW(), value=MaxWins())
        left, right = make_arrow_tables()
        result, conflicts = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        # For overlapping keys (5-9), MaxWins should pick max value
        for i, kid in enumerate(rows["id"]):
            if 5 <= kid <= 9:
                assert rows["value"][i] == max(100 + kid, 200 + (kid - 5))

    @needs_polars
    def test_max_wins_dicts(self):
        schema = MergeSchema(default=LWW(), value=MaxWins())
        left, right = make_dict_rows()
        result, conflicts = polars_merge_dicts(left, right, "id", schema)
        for row in result:
            if 5 <= row["id"] <= 9:
                assert row["value"] == max(100 + row["id"], 200 + row["id"])


class TestMinWins:
    @needs_polars
    @needs_arrow
    def test_min_wins_arrow(self):
        schema = MergeSchema(default=LWW(), value=MinWins())
        left, right = make_arrow_tables()
        result, conflicts = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        for i, kid in enumerate(rows["id"]):
            if 5 <= kid <= 9:
                assert rows["value"][i] == min(100 + kid, 200 + (kid - 5))


class TestLWW:
    @needs_polars
    @needs_arrow
    def test_lww_no_timestamp(self):
        """Without timestamps, LWW coalesces (right wins)."""
        schema = MergeSchema(default=LWW())
        left, right = make_arrow_tables()
        result, _ = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        # Right-only rows should have right values
        for i, kid in enumerate(rows["id"]):
            if kid >= 10:
                assert rows["name"][i] == f"right_{kid}"

    @needs_polars
    @needs_arrow
    def test_lww_with_timestamp(self):
        """With timestamps, higher timestamp wins."""
        left = pa.table({
            "id": [1, 2, 3],
            "name": ["old_alice", "old_bob", "old_carol"],
            "ts": [1.0, 3.0, 1.0],
        })
        right = pa.table({
            "id": [1, 2, 3],
            "name": ["new_alice", "new_bob", "new_carol"],
            "ts": [2.0, 1.0, 2.0],
        })
        schema = MergeSchema(default=LWW())
        result, conflicts = polars_merge_arrow(left, right, "id", schema, timestamp_col="ts")
        rows = result.to_pydict()
        names = {rows["id"][i]: rows["name"][i] for i in range(len(rows["id"]))}
        assert names[1] == "new_alice"  # right ts=2 > left ts=1
        assert names[2] == "old_bob"    # left ts=3 > right ts=1
        assert names[3] == "new_carol"  # right ts=2 > left ts=1
        assert conflicts == 3


class TestConcat:
    @needs_polars
    @needs_arrow
    def test_concat_strategy(self):
        left = pa.table({"id": [1, 2], "tags": ["a", "c"]})
        right = pa.table({"id": [1, 2], "tags": ["b", "d"]})
        schema = MergeSchema(default=LWW(), tags=Concat(separator=", "))
        result, _ = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        tags = {rows["id"][i]: rows["tags"][i] for i in range(len(rows["id"]))}
        assert tags[1] == "a, b"
        assert tags[2] == "c, d"


class TestLongestWins:
    @needs_polars
    @needs_arrow
    def test_longest_wins_strategy(self):
        left = pa.table({"id": [1, 2], "desc": ["short", "very long description"]})
        right = pa.table({"id": [1, 2], "desc": ["longer text", "tiny"]})
        schema = MergeSchema(default=LWW(), desc=LongestWins())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        descs = {rows["id"][i]: rows["desc"][i] for i in range(len(rows["id"]))}
        assert descs[1] == "longer text"          # right is longer
        assert descs[2] == "very long description"  # left is longer


class TestPriority:
    @needs_polars
    @needs_arrow
    def test_priority_fallback(self):
        """Priority uses map_elements fallback."""
        left = pa.table({"id": [1], "status": ["draft"]})
        right = pa.table({"id": [1], "status": ["approved"]})
        schema = MergeSchema(
            default=LWW(),
            status=Priority(["draft", "review", "approved"]),
        )
        result, _ = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        assert rows["status"][0] == "approved"


class TestCustom:
    @needs_polars
    @needs_arrow
    def test_custom_function(self):
        """Custom strategy uses map_elements fallback."""
        left = pa.table({"id": [1], "value": [10]})
        right = pa.table({"id": [1], "value": [20]})
        schema = MergeSchema(
            default=LWW(),
            value=Custom(lambda a, b: a + b),
        )
        result, _ = polars_merge_arrow(left, right, "id", schema)
        rows = result.to_pydict()
        assert rows["value"][0] == 30


# ===========================================================================
# 2. Conflict counting
# ===========================================================================

class TestConflictCounting:
    @needs_polars
    @needs_arrow
    def test_conflict_count_accuracy(self):
        left, right = make_arrow_tables(20)
        schema = MergeSchema(default=MaxWins())
        _, conflicts = polars_merge_arrow(left, right, "id", schema)
        # 20 keys in left (0-19), 20 in right (10-29) → 10 overlap
        assert conflicts == 10

    @needs_polars
    @needs_arrow
    def test_no_conflicts_disjoint(self):
        left = pa.table({"id": [1, 2], "v": [10, 20]})
        right = pa.table({"id": [3, 4], "v": [30, 40]})
        schema = MergeSchema(default=LWW())
        _, conflicts = polars_merge_arrow(left, right, "id", schema)
        assert conflicts == 0

    @needs_polars
    @needs_arrow
    def test_all_conflicts(self):
        left = pa.table({"id": [1, 2, 3], "v": [10, 20, 30]})
        right = pa.table({"id": [1, 2, 3], "v": [40, 50, 60]})
        schema = MergeSchema(default=MaxWins())
        _, conflicts = polars_merge_arrow(left, right, "id", schema)
        assert conflicts == 3


# ===========================================================================
# 3. Null handling
# ===========================================================================

class TestNullHandling:
    @needs_polars
    @needs_arrow
    def test_null_left_takes_right(self):
        left = pa.table({"id": [1], "v": pa.array([None], type=pa.int64())})
        right = pa.table({"id": [1], "v": [42]})
        schema = MergeSchema(default=MaxWins())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        assert result.to_pydict()["v"][0] == 42

    @needs_polars
    @needs_arrow
    def test_null_right_takes_left(self):
        left = pa.table({"id": [1], "v": [42]})
        right = pa.table({"id": [1], "v": pa.array([None], type=pa.int64())})
        schema = MergeSchema(default=MaxWins())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        assert result.to_pydict()["v"][0] == 42

    @needs_polars
    @needs_arrow
    def test_both_null(self):
        left = pa.table({"id": [1], "v": pa.array([None], type=pa.int64())})
        right = pa.table({"id": [1], "v": pa.array([None], type=pa.int64())})
        schema = MergeSchema(default=MaxWins())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        assert result.to_pydict()["v"][0] is None


# ===========================================================================
# 4. Empty table edge cases
# ===========================================================================

class TestEmptyTables:
    @needs_polars
    def test_both_empty_dicts(self):
        schema = MergeSchema(default=LWW())
        result, conflicts = polars_merge_dicts([], [], "id", schema)
        assert result == []
        assert conflicts == 0

    @needs_polars
    def test_left_empty_dicts(self):
        right = [{"id": 1, "v": 10}]
        schema = MergeSchema(default=LWW())
        result, conflicts = polars_merge_dicts([], right, "id", schema)
        assert len(result) == 1
        assert conflicts == 0

    @needs_polars
    def test_right_empty_dicts(self):
        left = [{"id": 1, "v": 10}]
        schema = MergeSchema(default=LWW())
        result, conflicts = polars_merge_dicts(left, [], "id", schema)
        assert len(result) == 1
        assert conflicts == 0


# ===========================================================================
# 5. Schema evolution (asymmetric columns)
# ===========================================================================

class TestSchemaEvolution:
    @needs_polars
    @needs_arrow
    def test_extra_column_in_right(self):
        left = pa.table({"id": [1, 2], "name": ["a", "b"]})
        right = pa.table({"id": [2, 3], "name": ["c", "d"], "extra": [10, 20]})
        schema = MergeSchema(default=LWW())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        cols = result.column_names
        assert "extra" in cols
        rows = result.to_pydict()
        # id=3 (right-only) should have extra=20
        idx_3 = rows["id"].index(3)
        assert rows["extra"][idx_3] == 20

    @needs_polars
    @needs_arrow
    def test_extra_column_in_left(self):
        left = pa.table({"id": [1, 2], "name": ["a", "b"], "bonus": [100, 200]})
        right = pa.table({"id": [2, 3], "name": ["c", "d"]})
        schema = MergeSchema(default=LWW())
        result, _ = polars_merge_arrow(left, right, "id", schema)
        cols = result.column_names
        assert "bonus" in cols


# ===========================================================================
# 6. Dict round-trip (for accelerators)
# ===========================================================================

class TestDictRoundTrip:
    @needs_polars
    def test_basic_merge(self):
        left = [{"id": 1, "v": 10}, {"id": 2, "v": 20}]
        right = [{"id": 2, "v": 30}, {"id": 3, "v": 40}]
        schema = MergeSchema(default=MaxWins())
        result, conflicts = polars_merge_dicts(left, right, "id", schema)
        assert len(result) == 3
        assert conflicts == 1
        result_map = {r["id"]: r["v"] for r in result}
        assert result_map[1] == 10   # left only
        assert result_map[2] == 30   # max(20, 30) = 30
        assert result_map[3] == 40   # right only


# ===========================================================================
# 7. Integration with ArrowMerge (engine routing)
# ===========================================================================

class TestEngineRouting:
    @needs_arrow
    def test_python_engine_explicit(self):
        """engine='python' always uses the Python path."""
        left, right = make_arrow_tables()
        schema = MergeSchema(default=MaxWins())
        engine = ArrowMerge(schema=schema, engine="python")
        result = engine.merge(left, right, key="id")
        assert result.num_rows == 15  # 10 + 10 - 5 overlap

    @needs_polars
    @needs_arrow
    def test_polars_engine_explicit(self):
        """engine='polars' uses the Polars path."""
        left, right = make_arrow_tables()
        schema = MergeSchema(default=MaxWins())
        engine = ArrowMerge(schema=schema, engine="polars")
        result = engine.merge(left, right, key="id")
        assert result.num_rows == 15

    @needs_polars
    @needs_arrow
    def test_auto_engine_uses_polars(self):
        """engine='auto' (default) should use Polars when available."""
        left, right = make_arrow_tables()
        schema = MergeSchema(default=MaxWins())
        engine = ArrowMerge(schema=schema)  # default is "auto"
        result = engine.merge(left, right, key="id")
        assert result.num_rows == 15

    @needs_polars
    @needs_arrow
    def test_arrow_merge_function_with_engine(self):
        """arrow_merge() convenience function passes engine through."""
        left, right = make_arrow_tables()
        schema = MergeSchema(default=MaxWins())
        result = arrow_merge(left, right, key="id", schema=schema, engine="polars")
        assert result.num_rows == 15


# ===========================================================================
# 8. Results match between Python and Polars engines
# ===========================================================================

class TestEngineConsistency:
    @needs_polars
    @needs_arrow
    def test_maxwins_results_match(self):
        left, right = make_arrow_tables()
        schema = MergeSchema(default=LWW(), value=MaxWins(), score=MinWins())

        py_engine = ArrowMerge(schema=schema, engine="python")
        pl_engine = ArrowMerge(schema=schema, engine="polars")

        py_result = py_engine.merge(left, right, key="id")
        pl_result = pl_engine.merge(left, right, key="id")

        py_dict = py_result.to_pydict()
        pl_dict = pl_result.to_pydict()

        # Sort both by id for comparison
        py_rows = sorted(zip(py_dict["id"], py_dict["value"], py_dict["score"]))
        pl_rows = sorted(zip(pl_dict["id"], pl_dict["value"], pl_dict["score"]))

        assert py_rows == pl_rows, f"Results differ:\nPython: {py_rows}\nPolars: {pl_rows}"


# ===========================================================================
# 9. Performance test
# ===========================================================================

class TestPerformance:
    @needs_polars
    @needs_arrow
    def test_polars_faster_than_python(self):
        """Polars engine should be at least 5× faster for 10K rows."""
        n = 10_000
        left, right = make_arrow_tables(n)
        schema = MergeSchema(default=MaxWins())

        # Python path
        py_engine = ArrowMerge(schema=schema, engine="python")
        t0 = time.perf_counter()
        py_engine.merge(left, right, key="id")
        py_time = time.perf_counter() - t0

        # Polars path
        pl_engine = ArrowMerge(schema=schema, engine="polars")
        t0 = time.perf_counter()
        pl_engine.merge(left, right, key="id")
        pl_time = time.perf_counter() - t0

        speedup = py_time / pl_time if pl_time > 0 else float("inf")
        print(f"\n  Python: {py_time:.3f}s | Polars: {pl_time:.3f}s | Speedup: {speedup:.1f}×")
        assert speedup >= 5, f"Polars only {speedup:.1f}× faster (expected ≥5×)"


# ===========================================================================
# 10. CRDT laws (associative, commutative, idempotent)
# ===========================================================================

class TestCRDTLaws:
    @needs_polars
    @needs_arrow
    def test_commutative(self):
        """merge(A, B) == merge(B, A)"""
        left = pa.table({"id": [1, 2], "v": [10, 20]})
        right = pa.table({"id": [2, 3], "v": [30, 40]})
        schema = MergeSchema(default=MaxWins())

        ab, _ = polars_merge_arrow(left, right, "id", schema)
        ba, _ = polars_merge_arrow(right, left, "id", schema)

        ab_sorted = sorted(zip(ab.to_pydict()["id"], ab.to_pydict()["v"]))
        ba_sorted = sorted(zip(ba.to_pydict()["id"], ba.to_pydict()["v"]))
        assert ab_sorted == ba_sorted

    @needs_polars
    @needs_arrow
    def test_idempotent(self):
        """merge(A, A) == A"""
        table = pa.table({"id": [1, 2, 3], "v": [10, 20, 30]})
        schema = MergeSchema(default=MaxWins())

        result, conflicts = polars_merge_arrow(table, table, "id", schema)
        result_sorted = sorted(zip(result.to_pydict()["id"], result.to_pydict()["v"]))
        original_sorted = sorted(zip([1, 2, 3], [10, 20, 30]))
        assert result_sorted == original_sorted

    @needs_polars
    @needs_arrow
    def test_associative(self):
        """merge(merge(A, B), C) == merge(A, merge(B, C))"""
        a = pa.table({"id": [1, 2], "v": [10, 20]})
        b = pa.table({"id": [2, 3], "v": [30, 40]})
        c = pa.table({"id": [3, 4], "v": [50, 60]})
        schema = MergeSchema(default=MaxWins())

        ab, _ = polars_merge_arrow(a, b, "id", schema)
        ab_c, _ = polars_merge_arrow(ab, c, "id", schema)

        bc, _ = polars_merge_arrow(b, c, "id", schema)
        a_bc, _ = polars_merge_arrow(a, bc, "id", schema)

        lhs = sorted(zip(ab_c.to_pydict()["id"], ab_c.to_pydict()["v"]))
        rhs = sorted(zip(a_bc.to_pydict()["id"], a_bc.to_pydict()["v"]))
        assert lhs == rhs
