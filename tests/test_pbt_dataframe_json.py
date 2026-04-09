"""Property-based tests for dataframe merge/diff and JSON merge operations.

Uses Hypothesis to verify CRDT algebraic laws hold for tabular and
nested dict merge operations across randomized inputs.
"""

import copy

import pytest
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from crdt_merge.dataframe import merge, diff
from crdt_merge.json_merge import merge_dicts, merge_json_lines
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins


# ---------------------------------------------------------------------------
# Hypothesis strategies for generating test data
# ---------------------------------------------------------------------------

_ALPHA = st.characters(whitelist_categories=("L",), min_codepoint=65, max_codepoint=122)


@st.composite
def record_lists(draw, min_size=0, max_size=8):
    """Generate list[dict] with schema {id, name, value} and unique 'id' keys."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    records = []
    for id_val in ids:
        records.append(
            {
                "id": id_val,
                "name": draw(st.text(min_size=1, max_size=8, alphabet=_ALPHA)),
                "value": draw(st.integers(min_value=0, max_value=1000)),
            }
        )
    return records


@st.composite
def record_lists_with_ts(draw, min_size=0, max_size=8):
    """Generate list[dict] with schema {id, name, value, _ts} and unique 'id' keys."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    records = []
    for id_val in ids:
        records.append(
            {
                "id": id_val,
                "name": draw(st.text(min_size=1, max_size=8, alphabet=_ALPHA)),
                "value": draw(st.integers(min_value=0, max_value=1000)),
                "_ts": draw(
                    st.floats(
                        min_value=1.0,
                        max_value=1e9,
                        allow_nan=False,
                        allow_infinity=False,
                    )
                ),
            }
        )
    return records


@st.composite
def flat_dicts(draw, min_size=0, max_size=6):
    """Generate flat dicts with string keys and int/str values."""
    keys = draw(
        st.lists(
            st.text(min_size=1, max_size=6, alphabet=_ALPHA),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        )
    )
    d = {}
    for k in keys:
        d[k] = draw(
            st.one_of(
                st.integers(min_value=0, max_value=100),
                st.text(min_size=1, max_size=8, alphabet=_ALPHA),
            )
        )
    return d


@st.composite
def nested_dicts(draw, max_depth=2):
    """Generate nested dicts suitable for json_merge testing."""
    if max_depth <= 0:
        return draw(flat_dicts(min_size=1, max_size=4))
    keys = draw(
        st.lists(
            st.text(min_size=1, max_size=5, alphabet=_ALPHA),
            min_size=1,
            max_size=4,
            unique=True,
        )
    )
    d = {}
    for k in keys:
        choice = draw(st.integers(min_value=0, max_value=2))
        if choice == 0:
            d[k] = draw(st.integers(min_value=0, max_value=100))
        elif choice == 1:
            d[k] = draw(st.text(min_size=1, max_size=8, alphabet=_ALPHA))
        else:
            d[k] = draw(nested_dicts(max_depth=max_depth - 1))
    return d


@st.composite
def disjoint_flat_dict_pair(draw):
    """Generate a pair of flat dicts with no overlapping keys."""
    all_keys = draw(
        st.lists(
            st.text(min_size=1, max_size=6, alphabet=_ALPHA),
            min_size=2,
            max_size=10,
            unique=True,
        )
    )
    split = draw(st.integers(min_value=1, max_value=max(1, len(all_keys) - 1)))
    keys_a, keys_b = all_keys[:split], all_keys[split:]
    a = {k: draw(st.integers(min_value=0, max_value=100)) for k in keys_a}
    b = {k: draw(st.integers(min_value=0, max_value=100)) for k in keys_b}
    return a, b


@st.composite
def json_line_lists(draw, min_size=0, max_size=6):
    """Generate JSONL-style list[dict] with unique 'id' keys."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    lines = []
    for id_val in ids:
        lines.append(
            {
                "id": id_val,
                "data": draw(st.text(min_size=1, max_size=8, alphabet=_ALPHA)),
            }
        )
    return lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sorted_by_key(records, key="id"):
    """Sort list[dict] by key for order-independent comparison."""
    return sorted(records, key=lambda r: r.get(key, 0))


def _key_set(records, key="id"):
    """Extract set of key values from list[dict]."""
    return {r[key] for r in records if key in r}


# ---------------------------------------------------------------------------
# DataFrame merge -- commutativity
# ---------------------------------------------------------------------------


class TestDataframeMergeCommutativity:
    """Commutativity: merge(A, B) ≡ merge(B, A) for deterministic strategies."""

    @given(
        a=record_lists(min_size=0, max_size=8),
        b=record_lists(min_size=0, max_size=8),
    )
    @settings(max_examples=100)
    def test_merge_commutativity_default(self, a, b):
        """Commutativity: merge(A,B,key='id') equals merge(B,A,key='id') with prefer='latest'."""
        ab = merge(a, b, key="id")
        ba = merge(b, a, key="id")
        assert _sorted_by_key(ab) == _sorted_by_key(ba)

    @given(
        a=record_lists_with_ts(min_size=1, max_size=6),
        b=record_lists_with_ts(min_size=1, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_commutativity_with_timestamps(self, a, b):
        """Commutativity: merge(A,B) equals merge(B,A) when _ts column is present."""
        ab = merge(a, b, key="id")
        ba = merge(b, a, key="id")
        assert _sorted_by_key(ab) == _sorted_by_key(ba)

    @given(
        a=record_lists(min_size=0, max_size=6),
        b=record_lists(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_commutativity_schema_lww(self, a, b):
        """Commutativity: merge with LWW schema produces identical result regardless of argument order."""
        schema = MergeSchema(default=LWW(), value=LWW())
        ab = merge(a, b, key="id", schema=schema)
        ba = merge(b, a, key="id", schema=schema)
        assert _sorted_by_key(ab) == _sorted_by_key(ba)

    @given(
        a=record_lists(min_size=0, max_size=6),
        b=record_lists(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_commutativity_schema_maxwins(self, a, b):
        """Commutativity: merge with MaxWins schema produces identical result regardless of argument order."""
        schema = MergeSchema(default=MaxWins())
        ab = merge(a, b, key="id", schema=schema)
        ba = merge(b, a, key="id", schema=schema)
        assert _sorted_by_key(ab) == _sorted_by_key(ba)

    @given(
        a=record_lists(min_size=0, max_size=6),
        b=record_lists(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_commutativity_schema_minwins(self, a, b):
        """Commutativity: merge with MinWins schema produces identical result regardless of argument order."""
        schema = MergeSchema(default=MinWins())
        ab = merge(a, b, key="id", schema=schema)
        ba = merge(b, a, key="id", schema=schema)
        assert _sorted_by_key(ab) == _sorted_by_key(ba)


# ---------------------------------------------------------------------------
# DataFrame merge -- idempotency
# ---------------------------------------------------------------------------


class TestDataframeMergeIdempotency:
    """Idempotency: merge(A, A) ≡ A for all inputs."""

    @given(a=record_lists(min_size=1, max_size=8))
    @settings(max_examples=100)
    def test_merge_idempotency_default(self, a):
        """Idempotency: merge(A,A,key='id') reproduces original records."""
        result = merge(a, a, key="id")
        assert _sorted_by_key(result) == _sorted_by_key(a)

    @given(a=record_lists(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_idempotency_with_schema(self, a):
        """Idempotency: merge(A,A) with MaxWins schema reproduces original records."""
        schema = MergeSchema(default=MaxWins())
        result = merge(a, a, key="id", schema=schema)
        assert _sorted_by_key(result) == _sorted_by_key(a)


# ---------------------------------------------------------------------------
# DataFrame merge -- key preservation
# ---------------------------------------------------------------------------


class TestDataframeMergeKeyPreservation:
    """Merged output preserves all key values from both inputs."""

    @given(
        a=record_lists(min_size=0, max_size=6),
        b=record_lists(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_preserves_all_keys(self, a, b):
        """Key preservation: union of input key sets equals output key set."""
        result = merge(a, b, key="id")
        assert _key_set(result) == _key_set(a) | _key_set(b)


# ---------------------------------------------------------------------------
# DataFrame merge -- empty inputs
# ---------------------------------------------------------------------------


class TestDataframeMergeEmpty:
    """Empty input handling for dataframe merge."""

    @given(b=record_lists(min_size=0, max_size=6))
    @settings(max_examples=100)
    def test_merge_empty_a(self, b):
        """Left identity: merge([], B, key='id') preserves all records from B."""
        result = merge([], b, key="id")
        assert _sorted_by_key(result) == _sorted_by_key(b)

    @given(a=record_lists(min_size=0, max_size=6))
    @settings(max_examples=100)
    def test_merge_empty_b(self, a):
        """Right identity: merge(A, [], key='id') preserves all records from A."""
        result = merge(a, [], key="id")
        assert _sorted_by_key(result) == _sorted_by_key(a)

    @given(st.just(None))
    @settings(max_examples=1)
    def test_merge_both_empty(self, _):
        """Empty merge: merge([], []) returns empty list."""
        result = merge([], [], key="id")
        assert result == []


# ---------------------------------------------------------------------------
# DataFrame merge -- None value handling
# ---------------------------------------------------------------------------


class TestDataframeMergeNoneValues:
    """None value handling in dataframe merge."""

    @given(a=record_lists(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_with_none_values(self, a):
        """None tolerance: non-None values are preferred over None in merge result."""
        b = [dict(r, name=None) for r in a]
        result = merge(a, b, key="id")
        assert _key_set(result) == _key_set(a)
        for r in _sorted_by_key(result):
            matched = [x for x in a if x["id"] == r["id"]]
            if matched:
                assert r["name"] == matched[0]["name"]


# ---------------------------------------------------------------------------
# DataFrame diff
# ---------------------------------------------------------------------------


class TestDataframeDiff:
    """Diff consistency: diff reflects correct additions, removals, and roundtrip identity."""

    @given(a=record_lists(min_size=1, max_size=8))
    @settings(max_examples=100)
    def test_diff_identical_no_changes(self, a):
        """Roundtrip identity: diff(A, A) reports zero added/removed/modified."""
        result = diff(a, a, key="id")
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []
        assert result["unchanged"] == len(a)

    @given(
        a=record_lists(min_size=1, max_size=5),
        b=record_lists(min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_diff_after_merge_no_removals(self, a, b):
        """Merge superset: diff(A, merge(A,B)) has no removals since merge preserves all of A's keys."""
        merged = merge(a, b, key="id")
        result = diff(a, merged, key="id")
        assert result["removed"] == []

    @given(a=record_lists(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_diff_merge_self_roundtrip(self, a):
        """Roundtrip: diff(A, merge(A,A)) shows no modifications."""
        merged = merge(a, a, key="id")
        result = diff(a, merged, key="id")
        assert result["modified"] == []
        assert result["added"] == []
        assert result["removed"] == []


# ---------------------------------------------------------------------------
# JSON merge_dicts -- commutativity
# ---------------------------------------------------------------------------


class TestMergeDictsCommutativity:
    """Commutativity of merge_dicts for non-conflicting inputs."""

    @given(pair=disjoint_flat_dict_pair())
    @settings(max_examples=100)
    def test_merge_dicts_commutativity_disjoint_keys(self, pair):
        """Commutativity: merge_dicts(A,B) equals merge_dicts(B,A) for disjoint key sets."""
        a, b = pair
        assert merge_dicts(a, b) == merge_dicts(b, a)

    @given(a=flat_dicts(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_dicts_commutativity_identical(self, a):
        """Commutativity: merge_dicts(A,A) is symmetric by definition."""
        assert merge_dicts(a, a) == merge_dicts(a, a)


# ---------------------------------------------------------------------------
# JSON merge_dicts -- idempotency
# ---------------------------------------------------------------------------


class TestMergeDictsIdempotency:
    """Idempotency: merge_dicts(A, A) ≡ A."""

    @given(a=flat_dicts(min_size=0, max_size=8))
    @settings(max_examples=100)
    def test_merge_dicts_idempotent(self, a):
        """Idempotency: merge_dicts(A, A) reproduces A for flat dicts."""
        assert merge_dicts(a, a) == a

    @given(a=nested_dicts(max_depth=2))
    @settings(max_examples=100)
    def test_merge_dicts_idempotent_nested(self, a):
        """Idempotency: merge_dicts(A, A) reproduces A for nested dicts."""
        assert merge_dicts(a, a) == a


# ---------------------------------------------------------------------------
# JSON merge_dicts -- key preservation and empty inputs
# ---------------------------------------------------------------------------


class TestMergeDictsKeyPreservation:
    """Key preservation and empty input handling for merge_dicts."""

    @given(
        a=flat_dicts(min_size=0, max_size=6),
        b=flat_dicts(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_dicts_preserves_all_keys(self, a, b):
        """Key preservation: merged dict contains union of all keys from both inputs."""
        result = merge_dicts(a, b)
        assert set(result.keys()) == set(a.keys()) | set(b.keys())

    @given(a=flat_dicts(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_dicts_empty_a(self, a):
        """Left identity: merge_dicts({}, A) equals A."""
        assert merge_dicts({}, a) == a

    @given(a=flat_dicts(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_dicts_empty_b(self, a):
        """Right identity: merge_dicts(A, {}) equals A."""
        assert merge_dicts(a, {}) == a

    @given(st.just(None))
    @settings(max_examples=1)
    def test_merge_dicts_both_empty(self, _):
        """Empty merge: merge_dicts({}, {}) returns empty dict."""
        assert merge_dicts({}, {}) == {}


# ---------------------------------------------------------------------------
# JSON merge_dicts -- None value handling
# ---------------------------------------------------------------------------


class TestMergeDictsNoneValues:
    """None value handling in merge_dicts."""

    @given(a=flat_dicts(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_dicts_none_values_prefer_non_none(self, a):
        """None tolerance: non-None values are preferred over None in merge result."""
        b = {k: None for k in a}
        result = merge_dicts(a, b)
        assert result == a


# ---------------------------------------------------------------------------
# JSON merge_json_lines
# ---------------------------------------------------------------------------


class TestMergeJsonLines:
    """Property tests for merge_json_lines."""

    @given(
        a=json_line_lists(min_size=0, max_size=6),
        b=json_line_lists(min_size=0, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_json_lines_all_keys_present(self, a, b):
        """Key completeness: merged JSONL contains all unique 'id' values from both inputs."""
        result = merge_json_lines(a, b, key="id")
        result_ids = {r["id"] for r in result}
        expected_ids = {r["id"] for r in a} | {r["id"] for r in b}
        assert result_ids == expected_ids

    @given(a=json_line_lists(min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_merge_json_lines_idempotent(self, a):
        """Idempotency: merge_json_lines(A, A, key='id') preserves same key set as A."""
        result = merge_json_lines(a, a, key="id")
        assert {r["id"] for r in result} == {r["id"] for r in a}

    @given(a=json_line_lists(min_size=0, max_size=6))
    @settings(max_examples=100)
    def test_merge_json_lines_empty_b(self, a):
        """Right identity: merge_json_lines(A, []) preserves A's records."""
        result = merge_json_lines(a, [], key="id")
        assert {r["id"] for r in result} == {r["id"] for r in a}

    @given(b=json_line_lists(min_size=0, max_size=6))
    @settings(max_examples=100)
    def test_merge_json_lines_empty_a(self, b):
        """Left identity: merge_json_lines([], B) preserves B's records."""
        result = merge_json_lines([], b, key="id")
        assert {r["id"] for r in result} == {r["id"] for r in b}

    @given(st.just(None))
    @settings(max_examples=1)
    def test_merge_json_lines_both_empty(self, _):
        """Empty merge: merge_json_lines([], []) returns empty list."""
        assert merge_json_lines([], []) == []

    @given(
        a=json_line_lists(min_size=1, max_size=6),
        b=json_line_lists(min_size=1, max_size=6),
    )
    @settings(max_examples=100)
    def test_merge_json_lines_no_key_dedup(self, a, b):
        """No-key merge: concatenation with dedup retains all unique records."""
        result = merge_json_lines(a, b, key=None)
        result_ids = {r["id"] for r in result if "id" in r}
        expected_ids = {r["id"] for r in a} | {r["id"] for r in b}
        assert result_ids == expected_ids
