"""Property-based tests for probabilistic data structures and wire protocol.

Uses Hypothesis to verify CRDT merge laws for HyperLogLog, Bloom filter,
and Count-Min Sketch, plus serialization roundtrip correctness.
"""

import math

import hypothesis.strategies as st
from hypothesis import given, settings, assume

from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.wire import (
    serialize,
    deserialize,
    peek_type,
    wire_size,
    serialize_batch,
    deserialize_batch,
    WireError,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Keep precision small for speed; 4–6 covers edge cases adequately.
hll_precision = st.integers(min_value=4, max_value=6)
item_lists = st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=60)
short_items = st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=30)
bloom_capacity = st.just(500)
bloom_fp = st.just(0.05)
cms_width = st.just(200)
cms_depth = st.just(5)

node_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=8,
)


def _make_hll(precision, items):
    """Build a MergeableHLL and add *items*."""
    h = MergeableHLL(precision=precision)
    h.add_all(items)
    return h


def _make_bloom(items, capacity=500, fp_rate=0.05):
    """Build a MergeableBloom and add *items*."""
    b = MergeableBloom(capacity=capacity, fp_rate=fp_rate)
    b.add_all(items)
    return b


def _make_cms(items, width=200, depth=5):
    """Build a MergeableCMS and add *items*."""
    c = MergeableCMS(width=width, depth=depth)
    c.add_all(items)
    return c


# ═══════════════════════════════════════════════════════════════════════════
# HLL merge laws
# ═══════════════════════════════════════════════════════════════════════════


@given(
    prec=hll_precision,
    items_a=item_lists,
    items_b=item_lists,
)
@settings(max_examples=30, deadline=None)
def test_hll_merge_commutativity(prec, items_a, items_b):
    """merge(a, b).cardinality() == merge(b, a).cardinality() for any two HLLs."""
    a = _make_hll(prec, items_a)
    b = _make_hll(prec, items_b)
    assert a.merge(b).cardinality() == b.merge(a).cardinality()


@given(
    prec=hll_precision,
    ia=item_lists,
    ib=item_lists,
    ic=item_lists,
)
@settings(max_examples=30, deadline=None)
def test_hll_merge_associativity(prec, ia, ib, ic):
    """(a ⊕ b) ⊕ c produces the same cardinality as a ⊕ (b ⊕ c)."""
    a, b, c = _make_hll(prec, ia), _make_hll(prec, ib), _make_hll(prec, ic)
    left = a.merge(b).merge(c)
    right = a.merge(b.merge(c))
    assert left.cardinality() == right.cardinality()


@given(prec=hll_precision, items=item_lists)
@settings(max_examples=30, deadline=None)
def test_hll_merge_idempotency(prec, items):
    """Self-merge does not change cardinality."""
    h = _make_hll(prec, items)
    assert h.merge(h).cardinality() == h.cardinality()


@given(prec=hll_precision, items=item_lists)
@settings(max_examples=30, deadline=None)
def test_hll_roundtrip(prec, items):
    """to_dict/from_dict preserves register state exactly."""
    h = _make_hll(prec, items)
    restored = MergeableHLL.from_dict(h.to_dict())
    assert restored == h
    assert restored.cardinality() == h.cardinality()


# ═══════════════════════════════════════════════════════════════════════════
# Bloom merge laws
# ═══════════════════════════════════════════════════════════════════════════


@given(items_a=short_items, items_b=short_items)
@settings(max_examples=30, deadline=None)
def test_bloom_merge_commutativity(items_a, items_b):
    """merge(a, b) and merge(b, a) produce identical bit arrays."""
    a, b = _make_bloom(items_a), _make_bloom(items_b)
    assert a.merge(b).bits == b.merge(a).bits


@given(ia=short_items, ib=short_items, ic=short_items)
@settings(max_examples=30, deadline=None)
def test_bloom_merge_associativity(ia, ib, ic):
    """Three-way merge is independent of grouping order."""
    a, b, c = _make_bloom(ia), _make_bloom(ib), _make_bloom(ic)
    assert a.merge(b).merge(c).bits == a.merge(b.merge(c)).bits


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_bloom_merge_idempotency(items):
    """Self-merge leaves the bit array unchanged."""
    bl = _make_bloom(items)
    assert bl.merge(bl).bits == bl.bits


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_bloom_roundtrip(items):
    """to_dict/from_dict preserves bit array state."""
    bl = _make_bloom(items)
    restored = MergeableBloom.from_dict(bl.to_dict())
    assert restored == bl


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_bloom_contains_after_add(items):
    """Every item that was added is reported as present (no false negatives)."""
    bl = _make_bloom(items)
    for item in items:
        assert bl.contains(item), f"{item!r} missing after add"


# ═══════════════════════════════════════════════════════════════════════════
# CMS merge laws
# ═══════════════════════════════════════════════════════════════════════════


@given(items_a=short_items, items_b=short_items)
@settings(max_examples=30, deadline=None)
def test_cms_merge_commutativity(items_a, items_b):
    """Estimates after merge(a, b) equal those after merge(b, a) for all probed items."""
    a, b = _make_cms(items_a), _make_cms(items_b)
    ab = a.merge(b)
    ba = b.merge(a)
    probes = set(items_a) | set(items_b)
    for p in probes:
        assert ab.estimate(p) == ba.estimate(p)


@given(ia=short_items, ib=short_items, ic=short_items)
@settings(max_examples=30, deadline=None)
def test_cms_merge_associativity(ia, ib, ic):
    """Three-way CMS merge is order-independent for all probed items."""
    a, b, c = _make_cms(ia), _make_cms(ib), _make_cms(ic)
    left = a.merge(b).merge(c)
    right = a.merge(b.merge(c))
    probes = set(ia) | set(ib) | set(ic)
    for p in probes:
        assert left.estimate(p) == right.estimate(p)


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_cms_merge_idempotency(items):
    """Self-merge (per-cell max) does not alter any estimate."""
    c = _make_cms(items)
    merged = c.merge(c)
    for item in set(items):
        assert merged.estimate(item) == c.estimate(item)


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_cms_roundtrip(items):
    """to_dict/from_dict preserves table and total."""
    c = _make_cms(items)
    restored = MergeableCMS.from_dict(c.to_dict())
    assert restored == c
    assert restored.total == c.total


# ═══════════════════════════════════════════════════════════════════════════
# Wire protocol — core CRDT roundtrips
# ═══════════════════════════════════════════════════════════════════════════


@given(
    nid=node_ids,
    amount=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=30, deadline=None)
def test_wire_gcounter_roundtrip(nid, amount):
    """GCounter survives serialize/deserialize unchanged."""
    gc = GCounter(nid, initial=amount)
    restored = deserialize(serialize(gc))
    assert isinstance(restored, GCounter)
    assert restored.value == gc.value


@given(
    nid=node_ids,
    inc=st.integers(min_value=0, max_value=500),
    dec=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=30, deadline=None)
def test_wire_pncounter_roundtrip(nid, inc, dec):
    """PNCounter survives serialize/deserialize unchanged."""
    pn = PNCounter()
    if inc > 0:
        pn.increment(nid, inc)
    if dec > 0:
        pn.decrement(nid, dec)
    restored = deserialize(serialize(pn))
    assert isinstance(restored, PNCounter)
    assert restored.value == pn.value


@given(
    val=st.one_of(st.integers(min_value=-(2**63), max_value=2**63 - 1), st.text(max_size=30), st.floats(allow_nan=False, allow_infinity=False)),
    ts=st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False),
    nid=node_ids,
)
@settings(max_examples=30, deadline=None)
def test_wire_lwwregister_roundtrip(val, ts, nid):
    """LWWRegister survives serialize/deserialize unchanged."""
    reg = LWWRegister(val, ts, nid)
    restored = deserialize(serialize(reg))
    assert isinstance(restored, LWWRegister)
    assert restored.value == reg.value
    assert restored.timestamp == reg.timestamp


@given(elems=st.lists(st.text(min_size=1, max_size=15), min_size=0, max_size=20))
@settings(max_examples=30, deadline=None)
def test_wire_orset_roundtrip(elems):
    """ORSet element set survives serialize/deserialize."""
    s = ORSet()
    for e in elems:
        s.add(e)
    restored = deserialize(serialize(s))
    assert isinstance(restored, ORSet)
    assert restored.value == s.value


@given(
    keys=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=10, unique=True),
    vals=st.lists(st.integers(min_value=-1000, max_value=1000), min_size=1, max_size=10),
)
@settings(max_examples=30, deadline=None)
def test_wire_lwwmap_roundtrip(keys, vals):
    """LWWMap value dict survives serialize/deserialize."""
    m = LWWMap()
    for i, k in enumerate(keys):
        v = vals[i % len(vals)]
        m.set(k, v, timestamp=float(i + 1))
    restored = deserialize(serialize(m))
    assert isinstance(restored, LWWMap)
    assert restored.value == m.value


# ═══════════════════════════════════════════════════════════════════════════
# Wire protocol — probabilistic type roundtrips
# ═══════════════════════════════════════════════════════════════════════════


@given(prec=hll_precision, items=item_lists)
@settings(max_examples=30, deadline=None)
def test_wire_hll_roundtrip(prec, items):
    """MergeableHLL survives serialize/deserialize with identical registers."""
    h = _make_hll(prec, items)
    restored = deserialize(serialize(h))
    assert isinstance(restored, MergeableHLL)
    assert restored == h


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_wire_bloom_roundtrip(items):
    """MergeableBloom survives serialize/deserialize with identical bits."""
    bl = _make_bloom(items)
    restored = deserialize(serialize(bl))
    assert isinstance(restored, MergeableBloom)
    assert restored == bl


@given(items=short_items)
@settings(max_examples=30, deadline=None)
def test_wire_cms_roundtrip(items):
    """MergeableCMS survives serialize/deserialize with identical table."""
    c = _make_cms(items)
    restored = deserialize(serialize(c))
    assert isinstance(restored, MergeableCMS)
    assert restored == c


# ═══════════════════════════════════════════════════════════════════════════
# Wire protocol — batch, compression, peek, size
# ═══════════════════════════════════════════════════════════════════════════


@given(
    nid=node_ids,
    amounts=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=8),
)
@settings(max_examples=30, deadline=None)
def test_wire_batch_roundtrip(nid, amounts):
    """serialize_batch/deserialize_batch preserves every object in the list."""
    objs = []
    for a in amounts:
        gc = GCounter(nid, initial=a)
        objs.append(gc)
    data = serialize_batch(objs)
    restored = deserialize_batch(data)
    assert len(restored) == len(objs)
    for orig, rest in zip(objs, restored):
        assert rest.value == orig.value


@given(
    nid=node_ids,
    amount=st.integers(min_value=0, max_value=1000),
)
@settings(max_examples=30, deadline=None)
def test_wire_compressed_roundtrip(nid, amount):
    """compress=True still roundtrips correctly."""
    gc = GCounter(nid, initial=amount)
    data = serialize(gc, compress=True)
    restored = deserialize(data)
    assert isinstance(restored, GCounter)
    assert restored.value == gc.value


@given(
    nid=node_ids,
    amount=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=30, deadline=None)
def test_wire_peek_type_correctness(nid, amount):
    """peek_type returns the correct type string for GCounter wire data."""
    gc = GCounter(nid, initial=amount)
    data = serialize(gc)
    assert peek_type(data) == "g_counter"


@given(
    nid=node_ids,
    amount=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=30, deadline=None)
def test_wire_size_consistency(nid, amount):
    """wire_size total_bytes matches len(serialized)."""
    gc = GCounter(nid, initial=amount)
    data = serialize(gc)
    info = wire_size(data)
    assert info["total_bytes"] == len(data)
    assert info["header_bytes"] + info["payload_bytes"] == info["total_bytes"]
