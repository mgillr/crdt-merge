"""Property-based tests for CRDT primitives and merge strategies.

Uses Hypothesis to verify algebraic laws (commutativity, associativity,
idempotency) and serialization roundtrips across randomized inputs.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.strategies import (
    LWW,
    MaxWins,
    MinWins,
    LongestWins,
    Concat,
    UnionSet,
    Priority,
    Custom,
    MergeSchema,
)

# ---------------------------------------------------------------------------
# Equality helpers -- compare CRDT state since instances lack __eq__
# ---------------------------------------------------------------------------


def eq_gcounter(a: GCounter, b: GCounter) -> bool:
    """State equality for GCounters via internal counts dict."""
    return a.to_dict() == b.to_dict()


def eq_pncounter(a: PNCounter, b: PNCounter) -> bool:
    """State equality for PNCounters via serialized positive/negative counters."""
    return a.to_dict() == b.to_dict()


def eq_lww_register(a: LWWRegister, b: LWWRegister) -> bool:
    """State equality for LWWRegisters via value, timestamp, and node_id."""
    return a.to_dict() == b.to_dict()


def eq_orset(a: ORSet, b: ORSet) -> bool:
    """State equality for ORSets — compare element-to-tag-set mappings."""
    da, db = a.to_dict(), b.to_dict()
    ea, eb = da.get("elements", {}), db.get("elements", {})
    if set(ea.keys()) != set(eb.keys()):
        return False
    return all(set(ea[k]) == set(eb[k]) for k in ea)


def eq_lww_map(a: LWWMap, b: LWWMap) -> bool:
    """State equality for LWWMaps via registers and tombstones."""
    return a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------
# Reusable Hypothesis strategies for atomic values
# ---------------------------------------------------------------------------

_NODE_ALPHA = st.characters(
    whitelist_categories=("L",), min_codepoint=97, max_codepoint=122
)
_node_id = st.text(min_size=1, max_size=4, alphabet=_NODE_ALPHA)
_small_pos_int = st.integers(min_value=0, max_value=100)
_timestamp = st.floats(
    min_value=0.001, max_value=1e9, allow_nan=False, allow_infinity=False
)
_small_text = st.text(
    min_size=0, max_size=8,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# ---------------------------------------------------------------------------
# Composite strategies to build random CRDT instances
# ---------------------------------------------------------------------------


@st.composite
def gen_gcounter(draw):
    """Build a GCounter with 1-4 random node increments."""
    gc = GCounter()
    ops = draw(st.lists(st.tuples(_node_id, _small_pos_int), min_size=1, max_size=4))
    for nid, amt in ops:
        gc.increment(nid, amt)
    return gc


@st.composite
def gen_pncounter(draw):
    """Build a PNCounter with random increments and decrements."""
    pn = PNCounter()
    ops = draw(
        st.lists(
            st.tuples(st.booleans(), _node_id, _small_pos_int),
            min_size=1,
            max_size=4,
        )
    )
    for is_inc, nid, amt in ops:
        if is_inc:
            pn.increment(nid, amt)
        else:
            pn.decrement(nid, amt)
    return pn


@st.composite
def gen_lww_register(draw, node_prefix=""):
    """Build an LWWRegister with random value, timestamp, and prefixed node_id."""
    value = draw(_small_text)
    ts = draw(_timestamp)
    nid = node_prefix + draw(_node_id)
    return LWWRegister(value=value, timestamp=ts, node_id=nid)


@st.composite
def gen_orset(draw):
    """Build an ORSet with random string adds and optional removes."""
    s = ORSet()
    elements = draw(st.lists(_small_text, min_size=0, max_size=6))
    for e in elements:
        s.add(e)
    if elements:
        to_remove = draw(st.lists(st.sampled_from(elements), max_size=2))
        for e in to_remove:
            s.remove(e)
    return s


@st.composite
def gen_lww_map(draw, node_prefix=""):
    """Build an LWWMap with random set/delete operations and prefixed node_id."""
    m = LWWMap()
    keys = draw(
        st.lists(
            st.text(min_size=1, max_size=4, alphabet=_NODE_ALPHA),
            min_size=1,
            max_size=4,
        )
    )
    for k in keys:
        v = draw(_small_text)
        ts = draw(_timestamp)
        nid = node_prefix + draw(_node_id)
        m.set(k, v, ts, nid)
    if keys:
        to_del = draw(st.lists(st.sampled_from(keys), max_size=1))
        for k in to_del:
            del_ts = draw(_timestamp)
            m.delete(k, del_ts)
    return m


# ===================================================================
# GCounter -- algebraic laws and roundtrip
# ===================================================================


@given(a=gen_gcounter(), b=gen_gcounter())
@settings(max_examples=200)
def test_gcounter_commutativity(a, b):
    """Commutativity: a.merge(b) produces identical state to b.merge(a)."""
    assert eq_gcounter(a.merge(b), b.merge(a))


@given(a=gen_gcounter(), b=gen_gcounter(), c=gen_gcounter())
@settings(max_examples=200)
def test_gcounter_associativity(a, b, c):
    """Associativity: (a.merge(b)).merge(c) equals a.merge(b.merge(c))."""
    assert eq_gcounter(a.merge(b).merge(c), a.merge(b.merge(c)))


@given(a=gen_gcounter())
@settings(max_examples=200)
def test_gcounter_idempotency(a):
    """Idempotency: a.merge(a) yields the same state as a."""
    assert eq_gcounter(a.merge(a), a)


@given(a=gen_gcounter())
@settings(max_examples=200)
def test_gcounter_roundtrip(a):
    """Roundtrip: from_dict(to_dict(a)) reproduces identical state."""
    assert eq_gcounter(GCounter.from_dict(a.to_dict()), a)


@given(a=gen_gcounter(), b=gen_gcounter())
@settings(max_examples=200)
def test_gcounter_merge_monotonic(a, b):
    """Monotonicity: merged value >= each input value."""
    merged = a.merge(b)
    assert merged.value >= a.value
    assert merged.value >= b.value


# ===================================================================
# PNCounter -- algebraic laws and roundtrip
# ===================================================================


@given(a=gen_pncounter(), b=gen_pncounter())
@settings(max_examples=200)
def test_pncounter_commutativity(a, b):
    """Commutativity: a.merge(b) produces identical state to b.merge(a)."""
    assert eq_pncounter(a.merge(b), b.merge(a))


@given(a=gen_pncounter(), b=gen_pncounter(), c=gen_pncounter())
@settings(max_examples=200)
def test_pncounter_associativity(a, b, c):
    """Associativity: (a.merge(b)).merge(c) equals a.merge(b.merge(c))."""
    assert eq_pncounter(a.merge(b).merge(c), a.merge(b.merge(c)))


@given(a=gen_pncounter())
@settings(max_examples=200)
def test_pncounter_idempotency(a):
    """Idempotency: a.merge(a) yields the same state as a."""
    assert eq_pncounter(a.merge(a), a)


@given(a=gen_pncounter())
@settings(max_examples=200)
def test_pncounter_roundtrip(a):
    """Roundtrip: from_dict(to_dict(a)) reproduces identical state."""
    assert eq_pncounter(PNCounter.from_dict(a.to_dict()), a)


# ===================================================================
# LWWRegister -- algebraic laws and roundtrip
# Uses fixed distinct node_ids to avoid the pathological case where
# timestamp and node_id are both equal but values differ.
# ===================================================================


@given(
    val_a=_small_text,
    ts_a=_timestamp,
    val_b=_small_text,
    ts_b=_timestamp,
)
@settings(max_examples=200)
def test_lww_register_commutativity(val_a, ts_a, val_b, ts_b):
    """Commutativity: a.merge(b) produces identical state to b.merge(a)."""
    a = LWWRegister(val_a, ts_a, "node_a")
    b = LWWRegister(val_b, ts_b, "node_b")
    assert eq_lww_register(a.merge(b), b.merge(a))


@given(
    val_a=_small_text,
    ts_a=_timestamp,
    val_b=_small_text,
    ts_b=_timestamp,
    val_c=_small_text,
    ts_c=_timestamp,
)
@settings(max_examples=200)
def test_lww_register_associativity(val_a, ts_a, val_b, ts_b, val_c, ts_c):
    """Associativity: (a.merge(b)).merge(c) equals a.merge(b.merge(c))."""
    a = LWWRegister(val_a, ts_a, "node_a")
    b = LWWRegister(val_b, ts_b, "node_b")
    c = LWWRegister(val_c, ts_c, "node_c")
    assert eq_lww_register(a.merge(b).merge(c), a.merge(b.merge(c)))


@given(a=gen_lww_register())
@settings(max_examples=200)
def test_lww_register_idempotency(a):
    """Idempotency: a.merge(a) yields the same state as a."""
    assert eq_lww_register(a.merge(a), a)


@given(a=gen_lww_register())
@settings(max_examples=200)
def test_lww_register_roundtrip(a):
    """Roundtrip: from_dict(to_dict(a)) reproduces identical state."""
    assert eq_lww_register(LWWRegister.from_dict(a.to_dict()), a)


# ===================================================================
# ORSet -- algebraic laws and roundtrip
# ===================================================================


@given(a=gen_orset(), b=gen_orset())
@settings(max_examples=200)
def test_orset_commutativity(a, b):
    """Commutativity: a.merge(b) produces identical state to b.merge(a)."""
    assert eq_orset(a.merge(b), b.merge(a))


@given(a=gen_orset(), b=gen_orset(), c=gen_orset())
@settings(max_examples=200)
def test_orset_associativity(a, b, c):
    """Associativity: (a.merge(b)).merge(c) equals a.merge(b.merge(c))."""
    assert eq_orset(a.merge(b).merge(c), a.merge(b.merge(c)))


@given(a=gen_orset())
@settings(max_examples=200)
def test_orset_idempotency(a):
    """Idempotency: a.merge(a) yields the same state as a."""
    assert eq_orset(a.merge(a), a)


@given(a=gen_orset())
@settings(max_examples=200)
def test_orset_roundtrip(a):
    """Roundtrip: from_dict(to_dict(a)) reproduces equivalent tag structure."""
    restored = ORSet.from_dict(a.to_dict())
    assert eq_orset(restored, a)


# ===================================================================
# LWWMap -- algebraic laws and roundtrip
# Uses node_prefix to guarantee distinct node_ids across replicas.
# ===================================================================


@given(a=gen_lww_map(node_prefix="a_"), b=gen_lww_map(node_prefix="b_"))
@settings(max_examples=200)
def test_lww_map_commutativity(a, b):
    """Commutativity: a.merge(b) produces identical state to b.merge(a)."""
    assert eq_lww_map(a.merge(b), b.merge(a))


@given(
    a=gen_lww_map(node_prefix="a_"),
    b=gen_lww_map(node_prefix="b_"),
    c=gen_lww_map(node_prefix="c_"),
)
@settings(max_examples=200)
def test_lww_map_associativity(a, b, c):
    """Associativity: (a.merge(b)).merge(c) equals a.merge(b.merge(c))."""
    assert eq_lww_map(a.merge(b).merge(c), a.merge(b.merge(c)))


@given(a=gen_lww_map())
@settings(max_examples=200)
def test_lww_map_idempotency(a):
    """Idempotency: a.merge(a) yields the same state as a."""
    assert eq_lww_map(a.merge(a), a)


@given(a=gen_lww_map())
@settings(max_examples=200)
def test_lww_map_roundtrip(a):
    """Roundtrip: from_dict(to_dict(a)) reproduces identical state."""
    assert eq_lww_map(LWWMap.from_dict(a.to_dict()), a)


# ===================================================================
# Strategy commutativity -- resolve(a,b,...) == resolve(b,a,...) swapped
# ===================================================================


@given(
    val_a=_small_text,
    val_b=_small_text,
    ts_a=_timestamp,
    ts_b=_timestamp,
)
@settings(max_examples=200)
def test_strategy_lww_commutativity(val_a, val_b, ts_a, ts_b):
    """Commutativity: LWW.resolve(a,b,ts_a,ts_b) == LWW.resolve(b,a,ts_b,ts_a)."""
    s = LWW()
    assert s.resolve(val_a, val_b, ts_a, ts_b, "na", "nb") == s.resolve(
        val_b, val_a, ts_b, ts_a, "nb", "na"
    )


@given(val_a=st.integers(), val_b=st.integers())
@settings(max_examples=200)
def test_strategy_max_wins_commutativity(val_a, val_b):
    """Commutativity: MaxWins.resolve(a,b) == MaxWins.resolve(b,a)."""
    s = MaxWins()
    assert s.resolve(val_a, val_b) == s.resolve(val_b, val_a)


@given(val_a=st.integers(), val_b=st.integers())
@settings(max_examples=200)
def test_strategy_min_wins_commutativity(val_a, val_b):
    """Commutativity: MinWins.resolve(a,b) == MinWins.resolve(b,a)."""
    s = MinWins()
    assert s.resolve(val_a, val_b) == s.resolve(val_b, val_a)


@given(
    val_a=_small_text,
    val_b=_small_text,
    ts_a=_timestamp,
    ts_b=_timestamp,
)
@settings(max_examples=200)
def test_strategy_longest_wins_commutativity(val_a, val_b, ts_a, ts_b):
    """Commutativity: LongestWins.resolve(a,b) == LongestWins.resolve(b,a)."""
    s = LongestWins()
    assert s.resolve(val_a, val_b, ts_a, ts_b, "na", "nb") == s.resolve(
        val_b, val_a, ts_b, ts_a, "nb", "na"
    )


@given(val_a=_small_text, val_b=_small_text)
@settings(max_examples=200)
def test_strategy_union_set_commutativity(val_a, val_b):
    """Commutativity: UnionSet.resolve(a,b) == UnionSet.resolve(b,a)."""
    s = UnionSet(separator=",")
    assert s.resolve(val_a, val_b) == s.resolve(val_b, val_a)


@given(val_a=_small_text, val_b=_small_text)
@settings(max_examples=200)
def test_strategy_concat_commutativity(val_a, val_b):
    """Commutativity: Concat.resolve(a,b) == Concat.resolve(b,a) with dedup."""
    s = Concat(separator=" | ", dedup=True)
    assert s.resolve(val_a, val_b) == s.resolve(val_b, val_a)


@given(
    val_a=st.sampled_from(["draft", "review", "approved", "published"]),
    val_b=st.sampled_from(["draft", "review", "approved", "published"]),
)
@settings(max_examples=200)
def test_strategy_priority_commutativity(val_a, val_b):
    """Commutativity: Priority.resolve(a,b) == Priority.resolve(b,a)."""
    s = Priority(["draft", "review", "approved", "published"])
    assert s.resolve(val_a, val_b) == s.resolve(val_b, val_a)


# ===================================================================
# Strategy idempotency -- resolve(a, a) == a
# ===================================================================


@given(val=st.integers())
@settings(max_examples=200)
def test_strategy_max_wins_idempotent(val):
    """Idempotency: MaxWins.resolve(a, a) == a."""
    assert MaxWins().resolve(val, val) == val


@given(val=st.integers())
@settings(max_examples=200)
def test_strategy_min_wins_idempotent(val):
    """Idempotency: MinWins.resolve(a, a) == a."""
    assert MinWins().resolve(val, val) == val


# ===================================================================
# MergeSchema -- roundtrip and resolve_row commutativity
# ===================================================================


@settings(max_examples=200)
@given(st.data())
def test_merge_schema_roundtrip(data):
    """Roundtrip: MergeSchema.from_dict(schema.to_dict()) preserves all strategies."""
    schema = MergeSchema(
        default=LWW(),
        score=MaxWins(),
        rating=MinWins(),
        tags=UnionSet(separator=","),
        notes=Concat(separator=" | ", dedup=True),
        status=Priority(["draft", "review", "approved", "published"]),
        length=LongestWins(),
    )
    d = schema.to_dict()
    restored = MergeSchema.from_dict(d)
    assert restored.to_dict() == d


@given(
    row_a_name=_small_text,
    row_b_name=_small_text,
    row_a_score=st.integers(min_value=0, max_value=1000),
    row_b_score=st.integers(min_value=0, max_value=1000),
    ts_a=_timestamp,
    ts_b=_timestamp,
)
@settings(max_examples=200)
def test_merge_schema_resolve_row_commutativity(
    row_a_name, row_b_name, row_a_score, row_b_score, ts_a, ts_b
):
    """Commutativity: resolve_row(a,b) matches resolve_row(b,a) with swapped nodes."""
    schema = MergeSchema(default=LWW(), score=MaxWins())
    row_a = {"name": row_a_name, "score": row_a_score, "_ts": ts_a}
    row_b = {"name": row_b_name, "score": row_b_score, "_ts": ts_b}
    ab = schema.resolve_row(row_a, row_b, timestamp_col="_ts", node_a="na", node_b="nb")
    ba = schema.resolve_row(row_b, row_a, timestamp_col="_ts", node_a="nb", node_b="na")
    assert ab == ba
