"""
CRDT Compliance Test Suite
===========================
Verifies commutativity, associativity, idempotency, and convergence
for all merge strategies across both tabular and model layers.

Part of the v0.8.3 release quality assurance process.
"""

import pytest
import pandas as pd
import numpy as np

from crdt_merge import merge, MergeSchema
from crdt_merge.strategies import (
    LWW, MaxWins, MinWins, Priority, Concat, LongestWins, UnionSet,
)
from crdt_merge.model import CRDTMergeState, list_strategies


# ---------------------------------------------------------------------------
# Fixtures -- tabular
# ---------------------------------------------------------------------------

@pytest.fixture
def df_a():
    return pd.DataFrame({"key": ["x", "y"], "val": [10, 20], "_ts": [1, 2]})


@pytest.fixture
def df_b():
    return pd.DataFrame({"key": ["x", "z"], "val": [30, 40], "_ts": [3, 4]})


@pytest.fixture
def df_c():
    return pd.DataFrame({"key": ["x", "w"], "val": [50, 60], "_ts": [5, 6]})


@pytest.fixture
def df_tied_a():
    """DataFrame with timestamps that tie with df_tied_b on key 'x'."""
    return pd.DataFrame({"key": ["x", "y"], "val": [1, 2], "_ts": [10, 20]})


@pytest.fixture
def df_tied_b():
    """Same timestamp as df_tied_a on key 'x', different value."""
    return pd.DataFrame({"key": ["x", "z"], "val": [9, 8], "_ts": [10, 30]})


# String-valued DataFrames for Concat / UnionSet / LongestWins / Priority
@pytest.fixture
def df_str_a():
    return pd.DataFrame({"key": ["x", "y"], "val": ["a,b", "short"], "_ts": [1, 2]})


@pytest.fixture
def df_str_b():
    return pd.DataFrame({"key": ["x", "z"], "val": ["b,c", "longword"], "_ts": [3, 4]})


@pytest.fixture
def df_str_c():
    return pd.DataFrame({"key": ["x", "w"], "val": ["c,d", "mid"], "_ts": [5, 6]})


@pytest.fixture
def df_prio_a():
    return pd.DataFrame({"key": ["x", "y"], "val": ["high", "low"], "_ts": [1, 2]})


@pytest.fixture
def df_prio_b():
    return pd.DataFrame({"key": ["x", "z"], "val": ["low", "med"], "_ts": [3, 4]})


@pytest.fixture
def df_prio_c():
    return pd.DataFrame({"key": ["x", "w"], "val": ["med", "high"], "_ts": [5, 6]})


# ---------------------------------------------------------------------------
# Fixtures -- model
# ---------------------------------------------------------------------------

@pytest.fixture
def tensors():
    rng = np.random.RandomState(42)
    return {
        "t1": rng.randn(4, 4),
        "t2": rng.randn(4, 4),
        "t3": rng.randn(4, 4),
        "base": rng.randn(4, 4),
    }


ALL_STRATEGIES = list_strategies()
BASE_REQUIRED = CRDTMergeState.BASE_REQUIRED
STOCHASTIC = CRDTMergeState.STOCHASTIC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sorted(df):
    """Return a reset-index, key-sorted copy for deterministic comparison."""
    return df.sort_values("key").reset_index(drop=True)


def _frames_equal(a, b):
    """Compare two DataFrames after sorting by key."""
    sa, sb = _sorted(a), _sorted(b)
    # align columns
    sb = sb[sa.columns]
    return sa.equals(sb)


def _make_state(strategy_name, base, seed=42):
    """Build a CRDTMergeState with the right kwargs for a strategy."""
    kw = {"strategy_name": strategy_name}
    if strategy_name in BASE_REQUIRED:
        kw["base"] = base
    if strategy_name in STOCHASTIC:
        kw["seed"] = seed
    return CRDTMergeState(**kw)


# ===================================================================
# TABULAR LAYER -- timestamp-based strategies (default merge behaviour)
# ===================================================================

class TestTabularCommutativity:
    """merge(A, B) produces the same result as merge(B, A)."""

    def test_lww_default(self, df_a, df_b):
        r_ab = merge(df_a, df_b, key="key", timestamp_col="_ts")
        r_ba = merge(df_b, df_a, key="key", timestamp_col="_ts")
        assert _frames_equal(r_ab, r_ba)

    def test_lww_schema(self, df_a, df_b):
        schema = MergeSchema(default=LWW())
        r_ab = merge(df_a, df_b, key="key", schema=schema)
        r_ba = merge(df_b, df_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_maxwins(self, df_a, df_b):
        schema = MergeSchema(val=MaxWins())
        r_ab = merge(df_a, df_b, key="key", schema=schema)
        r_ba = merge(df_b, df_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_minwins(self, df_a, df_b):
        schema = MergeSchema(val=MinWins())
        r_ab = merge(df_a, df_b, key="key", schema=schema)
        r_ba = merge(df_b, df_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_concat(self, df_str_a, df_str_b):
        schema = MergeSchema(val=Concat())
        r_ab = merge(df_str_a, df_str_b, key="key", schema=schema)
        r_ba = merge(df_str_b, df_str_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_longestwins(self, df_str_a, df_str_b):
        schema = MergeSchema(val=LongestWins())
        r_ab = merge(df_str_a, df_str_b, key="key", schema=schema)
        r_ba = merge(df_str_b, df_str_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_unionset(self, df_str_a, df_str_b):
        schema = MergeSchema(val=UnionSet())
        r_ab = merge(df_str_a, df_str_b, key="key", schema=schema)
        r_ba = merge(df_str_b, df_str_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)

    def test_priority(self, df_prio_a, df_prio_b):
        schema = MergeSchema(val=Priority(levels=["low", "med", "high"]))
        r_ab = merge(df_prio_a, df_prio_b, key="key", schema=schema)
        r_ba = merge(df_prio_b, df_prio_a, key="key", schema=schema)
        assert _frames_equal(r_ab, r_ba)


class TestTabularIdempotency:
    """merge(A, A) == A (structurally)."""

    def test_lww_default(self, df_a):
        result = merge(df_a, df_a, key="key", timestamp_col="_ts")
        assert _frames_equal(result, df_a)

    def test_lww_schema(self, df_a):
        schema = MergeSchema(default=LWW())
        result = merge(df_a, df_a, key="key", schema=schema)
        assert _frames_equal(result, df_a)

    def test_maxwins(self, df_a):
        schema = MergeSchema(val=MaxWins())
        result = merge(df_a, df_a, key="key", schema=schema)
        assert _frames_equal(result, df_a)

    def test_minwins(self, df_a):
        schema = MergeSchema(val=MinWins())
        result = merge(df_a, df_a, key="key", schema=schema)
        assert _frames_equal(result, df_a)

    def test_concat(self, df_str_a):
        schema = MergeSchema(val=Concat())
        result = merge(df_str_a, df_str_a, key="key", schema=schema)
        assert _frames_equal(result, df_str_a)

    def test_longestwins(self, df_str_a):
        schema = MergeSchema(val=LongestWins())
        result = merge(df_str_a, df_str_a, key="key", schema=schema)
        assert _frames_equal(result, df_str_a)

    def test_unionset(self, df_str_a):
        schema = MergeSchema(val=UnionSet())
        result = merge(df_str_a, df_str_a, key="key", schema=schema)
        assert _frames_equal(result, df_str_a)

    def test_priority(self, df_prio_a):
        schema = MergeSchema(val=Priority(levels=["low", "med", "high"]))
        result = merge(df_prio_a, df_prio_a, key="key", schema=schema)
        assert _frames_equal(result, df_prio_a)


class TestTabularAssociativity:
    """merge(merge(A,B), C) == merge(A, merge(B,C))."""

    def test_lww_default(self, df_a, df_b, df_c):
        left = merge(merge(df_a, df_b, key="key", timestamp_col="_ts"),
                      df_c, key="key", timestamp_col="_ts")
        right = merge(df_a,
                       merge(df_b, df_c, key="key", timestamp_col="_ts"),
                       key="key", timestamp_col="_ts")
        assert _frames_equal(left, right)

    def test_maxwins(self, df_a, df_b, df_c):
        s = MergeSchema(val=MaxWins())
        left = merge(merge(df_a, df_b, key="key", schema=s),
                      df_c, key="key", schema=s)
        right = merge(df_a, merge(df_b, df_c, key="key", schema=s),
                       key="key", schema=s)
        assert _frames_equal(left, right)

    def test_minwins(self, df_a, df_b, df_c):
        s = MergeSchema(val=MinWins())
        left = merge(merge(df_a, df_b, key="key", schema=s),
                      df_c, key="key", schema=s)
        right = merge(df_a, merge(df_b, df_c, key="key", schema=s),
                       key="key", schema=s)
        assert _frames_equal(left, right)

    def test_longestwins(self, df_str_a, df_str_b, df_str_c):
        s = MergeSchema(val=LongestWins())
        left = merge(merge(df_str_a, df_str_b, key="key", schema=s),
                      df_str_c, key="key", schema=s)
        right = merge(df_str_a, merge(df_str_b, df_str_c, key="key", schema=s),
                       key="key", schema=s)
        assert _frames_equal(left, right)

    def test_unionset(self, df_str_a, df_str_b, df_str_c):
        s = MergeSchema(val=UnionSet())
        left = merge(merge(df_str_a, df_str_b, key="key", schema=s),
                      df_str_c, key="key", schema=s)
        right = merge(df_str_a, merge(df_str_b, df_str_c, key="key", schema=s),
                       key="key", schema=s)
        assert _frames_equal(left, right)

    def test_priority(self, df_prio_a, df_prio_b, df_prio_c):
        s = MergeSchema(val=Priority(levels=["low", "med", "high"]))
        left = merge(merge(df_prio_a, df_prio_b, key="key", schema=s),
                      df_prio_c, key="key", schema=s)
        right = merge(df_prio_a, merge(df_prio_b, df_prio_c, key="key", schema=s),
                       key="key", schema=s)
        assert _frames_equal(left, right)


class TestTabularDeterministicTieBreaking:
    """Tied timestamps always resolve to the same value regardless of input order."""

    def test_tied_timestamps_lww(self, df_tied_a, df_tied_b):
        r_ab = merge(df_tied_a, df_tied_b, key="key", timestamp_col="_ts")
        r_ba = merge(df_tied_b, df_tied_a, key="key", timestamp_col="_ts")
        assert _frames_equal(r_ab, r_ba)

    def test_tied_timestamps_repeated(self, df_tied_a, df_tied_b):
        """Run the same merge 10 times — output must be identical every time."""
        results = []
        for _ in range(10):
            r = merge(df_tied_a, df_tied_b, key="key", timestamp_col="_ts")
            results.append(_sorted(r))
        for r in results[1:]:
            assert r.equals(results[0])


class TestTabularConvergence:
    """Multiple replicas merging in different orders converge to the same state."""

    def test_three_replica_convergence(self, df_a, df_b, df_c):
        # Order 1: A + B + C
        r1 = merge(merge(df_a, df_b, key="key", timestamp_col="_ts"),
                    df_c, key="key", timestamp_col="_ts")
        # Order 2: C + A + B
        r2 = merge(merge(df_c, df_a, key="key", timestamp_col="_ts"),
                    df_b, key="key", timestamp_col="_ts")
        # Order 3: B + C + A
        r3 = merge(merge(df_b, df_c, key="key", timestamp_col="_ts"),
                    df_a, key="key", timestamp_col="_ts")
        assert _frames_equal(r1, r2)
        assert _frames_equal(r2, r3)

    def test_schema_convergence_maxwins(self, df_a, df_b, df_c):
        s = MergeSchema(val=MaxWins())
        r1 = merge(merge(df_a, df_b, key="key", schema=s), df_c, key="key", schema=s)
        r2 = merge(merge(df_c, df_a, key="key", schema=s), df_b, key="key", schema=s)
        r3 = merge(merge(df_b, df_c, key="key", schema=s), df_a, key="key", schema=s)
        assert _frames_equal(r1, r2)
        assert _frames_equal(r2, r3)


# ===================================================================
# MODEL LAYER -- all 26 strategies via CRDTMergeState
# ===================================================================

class TestModelCommutativity:
    """add(t1) then add(t2) produces the same resolved tensor as add(t2) then add(t1)."""

    @pytest.mark.parametrize("strategy_name", ALL_STRATEGIES)
    def test_commutativity(self, strategy_name, tensors):
        t1, t2, base = tensors["t1"], tensors["t2"], tensors["base"]

        state_ab = _make_state(strategy_name, base)
        state_ab = state_ab.add(t1, model_id="model_a", version=1)
        state_ab = state_ab.add(t2, model_id="model_b", version=2)
        result_ab = state_ab.resolve()

        state_ba = _make_state(strategy_name, base)
        state_ba = state_ba.add(t2, model_id="model_b", version=2)
        state_ba = state_ba.add(t1, model_id="model_a", version=1)
        result_ba = state_ba.resolve()

        np.testing.assert_allclose(result_ab, result_ba, rtol=1e-5,
                                   err_msg=f"{strategy_name} violated commutativity")


class TestModelIdempotency:
    """Adding the same tensor twice (same model_id) doesn't change the result."""

    @pytest.mark.parametrize("strategy_name", ALL_STRATEGIES)
    def test_idempotency(self, strategy_name, tensors):
        t1, base = tensors["t1"], tensors["base"]

        state_once = _make_state(strategy_name, base)
        state_once = state_once.add(t1, model_id="model_a", version=1)
        result_once = state_once.resolve()

        state_twice = _make_state(strategy_name, base)
        state_twice = state_twice.add(t1, model_id="model_a", version=1)
        state_twice = state_twice.add(t1, model_id="model_a", version=1)
        result_twice = state_twice.resolve()

        np.testing.assert_allclose(result_once, result_twice, rtol=1e-5,
                                   err_msg=f"{strategy_name} violated idempotency")


class TestModelConvergence:
    """Three replicas merging tensors in different orders converge."""

    @pytest.mark.parametrize("strategy_name", ALL_STRATEGIES)
    def test_convergence(self, strategy_name, tensors):
        t1, t2, t3, base = tensors["t1"], tensors["t2"], tensors["t3"], tensors["base"]

        # Order 1: t1 → t2 → t3
        s1 = _make_state(strategy_name, base)
        s1 = s1.add(t1, model_id="a", version=1)
        s1 = s1.add(t2, model_id="b", version=2)
        s1 = s1.add(t3, model_id="c", version=3)
        r1 = s1.resolve()

        # Order 2: t3 → t1 → t2
        s2 = _make_state(strategy_name, base)
        s2 = s2.add(t3, model_id="c", version=3)
        s2 = s2.add(t1, model_id="a", version=1)
        s2 = s2.add(t2, model_id="b", version=2)
        r2 = s2.resolve()

        # Order 3: t2 → t3 → t1
        s3 = _make_state(strategy_name, base)
        s3 = s3.add(t2, model_id="b", version=2)
        s3 = s3.add(t3, model_id="c", version=3)
        s3 = s3.add(t1, model_id="a", version=1)
        r3 = s3.resolve()

        np.testing.assert_allclose(r1, r2, rtol=1e-5,
                                   err_msg=f"{strategy_name} order 1 vs 2")
        np.testing.assert_allclose(r2, r3, rtol=1e-5,
                                   err_msg=f"{strategy_name} order 2 vs 3")


class TestModelStochasticSeeded:
    """Stochastic strategies produce identical results when given the same seed."""

    @pytest.mark.parametrize("strategy_name", sorted(STOCHASTIC))
    def test_seeded_reproducibility(self, strategy_name, tensors):
        t1, t2, base = tensors["t1"], tensors["t2"], tensors["base"]

        results = []
        for _ in range(3):
            s = _make_state(strategy_name, base, seed=42)
            s = s.add(t1, model_id="a", version=1)
            s = s.add(t2, model_id="b", version=2)
            results.append(s.resolve())

        for i in range(1, len(results)):
            np.testing.assert_allclose(results[0], results[i], rtol=1e-5,
                                       err_msg=f"{strategy_name} seed=42 run 0 vs {i}")


class TestModelDeterministicNoSeed:
    """Deterministic strategies produce identical results without explicit seed."""

    DETERMINISTIC = sorted(set(ALL_STRATEGIES) - STOCHASTIC)

    @pytest.mark.parametrize("strategy_name", DETERMINISTIC)
    def test_no_seed_reproducibility(self, strategy_name, tensors):
        t1, t2, base = tensors["t1"], tensors["t2"], tensors["base"]

        results = []
        for _ in range(3):
            kw = {"strategy_name": strategy_name}
            if strategy_name in BASE_REQUIRED:
                kw["base"] = base
            s = CRDTMergeState(**kw)
            s = s.add(t1, model_id="a", version=1)
            s = s.add(t2, model_id="b", version=2)
            results.append(s.resolve())

        for i in range(1, len(results)):
            np.testing.assert_allclose(results[0], results[i], rtol=1e-5,
                                       err_msg=f"{strategy_name} run 0 vs {i}")


class TestModelStateMerge:
    """CRDTMergeState.merge() and merge_many() honour CRDT properties."""

    def test_state_merge_commutativity(self, tensors):
        t1, t2, base = tensors["t1"], tensors["t2"], tensors["base"]

        s1 = CRDTMergeState("linear")
        s1 = s1.add(t1, model_id="a", version=1)

        s2 = CRDTMergeState("linear")
        s2 = s2.add(t2, model_id="b", version=2)

        r_12 = s1.merge(s2).resolve()
        r_21 = s2.merge(s1).resolve()
        np.testing.assert_allclose(r_12, r_21, rtol=1e-5)

    def test_merge_many_convergence(self, tensors):
        t1, t2, t3, base = tensors["t1"], tensors["t2"], tensors["t3"], tensors["base"]

        s1 = CRDTMergeState("weight_average").add(t1, model_id="a", version=1)
        s2 = CRDTMergeState("weight_average").add(t2, model_id="b", version=2)
        s3 = CRDTMergeState("weight_average").add(t3, model_id="c", version=3)

        r1 = CRDTMergeState.merge_many([s1, s2, s3]).resolve()
        r2 = CRDTMergeState.merge_many([s3, s1, s2]).resolve()
        r3 = CRDTMergeState.merge_many([s2, s3, s1]).resolve()

        np.testing.assert_allclose(r1, r2, rtol=1e-5)
        np.testing.assert_allclose(r2, r3, rtol=1e-5)
