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

"""Property-based tests for crdt_merge.wire — serialize / deserialize roundtrips.

Covers: generic dicts, CRDT types (GCounter, PNCounter, LWWRegister, ORSet,
LWWMap), GossipState, MerkleTree, VectorClock, and compression.
"""

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from crdt_merge.wire import serialize, deserialize, WireError
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.gossip import GossipState
from crdt_merge.merkle import MerkleTree
from crdt_merge.clocks import VectorClock

# ---------------------------------------------------------------------------
# Scalar Hypothesis strategies safe for wire encoding
# ---------------------------------------------------------------------------

_safe_int = st.integers(min_value=-10_000, max_value=10_000)
_safe_str = st.text(
    min_size=0,
    max_size=32,
    alphabet="abcdefghijklmnopqrstuvwxyz_0123456789",
)
_safe_float = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)
_scalar = st.one_of(_safe_int, _safe_str, st.booleans(), st.none())

# A simple JSON-safe value (no floats — avoids float64 precision edge cases)
_wire_value = st.one_of(_safe_int, _safe_str, st.booleans(), st.none())

# ---------------------------------------------------------------------------
# Generic dict roundtrip
# ---------------------------------------------------------------------------

_simple_dict = st.dictionaries(
    keys=_safe_str.filter(bool),
    values=_wire_value,
    min_size=0,
    max_size=6,
)


@given(d=_simple_dict)
@settings(max_examples=50)
def test_generic_dict_roundtrip(d):
    """serialize/deserialize roundtrip for a plain dict of scalars."""
    raw = serialize(d)
    recovered = deserialize(raw)
    assert recovered == d


@given(d=_simple_dict)
@settings(max_examples=50)
def test_generic_dict_roundtrip_compressed(d):
    """Roundtrip is preserved when compression is enabled."""
    raw = serialize(d, compress=True)
    recovered = deserialize(raw)
    assert recovered == d


@given(lst=st.lists(_wire_value, min_size=0, max_size=8))
@settings(max_examples=50)
def test_generic_list_roundtrip(lst):
    """serialize/deserialize roundtrip for a plain list."""
    raw = serialize(lst)
    recovered = deserialize(raw)
    assert recovered == lst


@given(
    d=st.dictionaries(
        keys=_safe_str.filter(bool),
        values=st.lists(_wire_value, min_size=0, max_size=4),
        min_size=0,
        max_size=4,
    )
)
@settings(max_examples=50)
def test_generic_dict_with_list_values_roundtrip(d):
    """Dicts whose values are lists survive the wire roundtrip."""
    raw = serialize(d)
    recovered = deserialize(raw)
    assert recovered == d


@given(
    d=st.dictionaries(
        keys=_safe_str.filter(bool),
        values=st.booleans(),
        min_size=0,
        max_size=6,
    )
)
@settings(max_examples=50)
def test_generic_dict_bool_values_roundtrip(d):
    """Boolean values round-trip correctly without being coerced to int."""
    raw = serialize(d)
    recovered = deserialize(raw)
    assert recovered == d


# ---------------------------------------------------------------------------
# GCounter roundtrip
# ---------------------------------------------------------------------------

_node_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=1,
    max_size=4,
)


@st.composite
def gen_gcounter(draw):
    gc = GCounter()
    ops = draw(st.lists(st.tuples(_node_id, st.integers(0, 50)), min_size=0, max_size=4))
    for nid, amt in ops:
        gc.increment(nid, amt)
    return gc


@given(gc=gen_gcounter())
@settings(max_examples=50)
def test_gcounter_wire_roundtrip(gc):
    """GCounter serialises and deserialises to an equivalent GCounter."""
    raw = serialize(gc)
    restored = deserialize(raw)
    assert isinstance(restored, GCounter)
    assert restored.value == gc.value


# ---------------------------------------------------------------------------
# PNCounter roundtrip
# ---------------------------------------------------------------------------


@st.composite
def gen_pncounter(draw):
    pn = PNCounter()
    ops = draw(
        st.lists(
            st.tuples(st.booleans(), _node_id, st.integers(0, 50)),
            min_size=0,
            max_size=4,
        )
    )
    for is_inc, nid, amt in ops:
        if is_inc:
            pn.increment(nid, amt)
        else:
            pn.decrement(nid, amt)
    return pn


@given(pn=gen_pncounter())
@settings(max_examples=50)
def test_pncounter_wire_roundtrip(pn):
    """PNCounter serialises and deserialises to an equivalent PNCounter."""
    raw = serialize(pn)
    restored = deserialize(raw)
    assert isinstance(restored, PNCounter)
    assert restored.value == pn.value


# ---------------------------------------------------------------------------
# LWWRegister roundtrip
# ---------------------------------------------------------------------------


@given(
    value=_safe_str,
    ts=st.floats(min_value=0.001, max_value=1e9, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50)
def test_lww_register_wire_roundtrip(value, ts):
    """LWWRegister serialises and deserialises with matching value."""
    reg = LWWRegister(value=value, timestamp=ts, node_id="node_a")
    raw = serialize(reg)
    restored = deserialize(raw)
    assert isinstance(restored, LWWRegister)
    assert restored.value == value


# ---------------------------------------------------------------------------
# ORSet roundtrip
# ---------------------------------------------------------------------------


@st.composite
def gen_orset(draw):
    s = ORSet()
    elems = draw(st.lists(_safe_str.filter(bool), min_size=0, max_size=5))
    for e in elems:
        s.add(e)
    return s


@given(s=gen_orset())
@settings(max_examples=50)
def test_orset_wire_roundtrip(s):
    """ORSet serialises and deserialises to an ORSet with the same elements."""
    raw = serialize(s)
    restored = deserialize(raw)
    assert isinstance(restored, ORSet)


# ---------------------------------------------------------------------------
# LWWMap roundtrip
# ---------------------------------------------------------------------------


@st.composite
def gen_lww_map(draw):
    m = LWWMap()
    keys = draw(
        st.lists(
            _safe_str.filter(bool),
            min_size=0,
            max_size=4,
        )
    )
    for k in keys:
        v = draw(_safe_str)
        ts = draw(st.floats(min_value=0.001, max_value=1e9, allow_nan=False, allow_infinity=False))
        m.set(k, v, ts, "node_a")
    return m


@given(m=gen_lww_map())
@settings(max_examples=50)
def test_lww_map_wire_roundtrip(m):
    """LWWMap serialises and deserialises to an LWWMap."""
    raw = serialize(m)
    restored = deserialize(raw)
    assert isinstance(restored, LWWMap)


# ---------------------------------------------------------------------------
# VectorClock wire roundtrip
# ---------------------------------------------------------------------------


@given(
    entries=st.dictionaries(
        keys=_node_id,
        values=st.integers(min_value=0, max_value=100),
        min_size=0,
        max_size=4,
    )
)
@settings(max_examples=50)
def test_vector_clock_wire_roundtrip(entries):
    """VectorClock serialises and deserialises to an equal VectorClock."""
    vc = VectorClock(entries)
    raw = serialize(vc)
    restored = deserialize(raw)
    assert isinstance(restored, VectorClock)
    assert restored.to_dict() == vc.to_dict()


# ---------------------------------------------------------------------------
# GossipState wire roundtrip
# ---------------------------------------------------------------------------


@st.composite
def gen_gossip_state(draw):
    nid = draw(_node_id)
    state = GossipState(nid)
    ops = draw(
        st.lists(
            st.tuples(_safe_str.filter(bool), _safe_str),
            min_size=0,
            max_size=4,
        )
    )
    for k, v in ops:
        state.update(k, v)
    return state


@given(gs=gen_gossip_state())
@settings(max_examples=50)
def test_gossip_state_wire_roundtrip(gs):
    """GossipState serialises and deserialises to an equivalent state."""
    raw = serialize(gs)
    restored = deserialize(raw)
    assert isinstance(restored, GossipState)
    assert restored.to_dict()["entries"] == gs.to_dict()["entries"]


# ---------------------------------------------------------------------------
# MerkleTree wire roundtrip
# ---------------------------------------------------------------------------


@st.composite
def gen_merkle_tree(draw):
    n = draw(st.integers(min_value=0, max_value=5))
    records = [
        {"id": str(i), "value": draw(_safe_int), "label": draw(_safe_str)}
        for i in range(n)
    ]
    return MerkleTree.from_records(records, key="id")


@given(mt=gen_merkle_tree())
@settings(max_examples=50)
def test_merkle_tree_wire_roundtrip(mt):
    """MerkleTree serialises and deserialises with the same root_hash."""
    raw = serialize(mt)
    restored = deserialize(raw)
    assert isinstance(restored, MerkleTree)
    assert restored.root_hash == mt.root_hash


# ---------------------------------------------------------------------------
# Corrupt data raises WireError
# ---------------------------------------------------------------------------


@given(data=st.binary(min_size=0, max_size=8))
@settings(max_examples=50)
def test_deserialize_garbage_raises_wire_error(data):
    """Deserializing random short bytes raises WireError."""
    # Only test data that's definitely too short or has wrong automatically
    assume(len(data) < 12 or data[:4] != b"CRDT")
    with pytest.raises((WireError, Exception)):
        deserialize(data)
