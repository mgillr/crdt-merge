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

"""Property-based tests for GossipState and MerkleTree.

Verifies CRDT laws (commutativity, associativity, idempotency),
deterministic hashing, and convergence after sync.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from crdt_merge.gossip import GossipState, GossipEntry, anti_entropy
from crdt_merge.merkle import MerkleTree, merkle_diff

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_node_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=1,
    max_size=6,
)

_key = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
)

_json_value = st.one_of(
    st.integers(min_value=-100, max_value=100),
    st.text(max_size=16),
    st.booleans(),
    st.none(),
)


@st.composite
def gen_gossip_state(draw, node_prefix=""):
    """Build a GossipState with random updates."""
    nid = node_prefix + draw(_node_id)
    state = GossipState(nid)
    ops = draw(st.lists(st.tuples(_key, _json_value), min_size=0, max_size=6))
    for k, v in ops:
        state.update(k, v)
    return state


@st.composite
def gen_records(draw, min_size=0, max_size=5):
    """Generate a list of record dicts with an 'id' key."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    records = []
    for i in range(n):
        rec = {
            "id": str(i),
            "value": draw(st.integers(min_value=0, max_value=1000)),
            "label": draw(st.text(max_size=8)),
        }
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# GossipState — CRDT laws
# ---------------------------------------------------------------------------


@given(a=gen_gossip_state("a_"), b=gen_gossip_state("b_"))
@settings(max_examples=50)
def test_gossip_merge_commutativity(a, b):
    """GossipState.merge is commutative: merge(a,b) == merge(b,a)."""
    ab = a.merge(b)
    ba = b.merge(a)
    assert ab.to_dict()["entries"] == ba.to_dict()["entries"]


@given(
    a=gen_gossip_state("a_"),
    b=gen_gossip_state("b_"),
    c=gen_gossip_state("c_"),
)
@settings(max_examples=50)
def test_gossip_merge_associativity(a, b, c):
    """GossipState.merge is associative: (a.merge(b)).merge(c) == a.merge(b.merge(c))."""
    left = a.merge(b).merge(c)
    right = a.merge(b.merge(c))
    assert left.to_dict()["entries"] == right.to_dict()["entries"]


@given(a=gen_gossip_state("a_"))
@settings(max_examples=50)
def test_gossip_merge_idempotency(a):
    """GossipState.merge is idempotent: merge(a,a) == a."""
    merged = a.merge(a)
    assert merged.to_dict()["entries"] == a.to_dict()["entries"]


@given(a=gen_gossip_state("a_"))
@settings(max_examples=50)
def test_gossip_to_from_dict_roundtrip(a):
    """GossipState.to_dict / from_dict reproduces identical state."""
    restored = GossipState.from_dict(a.to_dict())
    assert restored.to_dict() == a.to_dict()


# ---------------------------------------------------------------------------
# GossipState — digest determinism and anti-entropy
# ---------------------------------------------------------------------------


@given(a=gen_gossip_state("a_"))
@settings(max_examples=50)
def test_gossip_digest_deterministic(a):
    """digest() returns the same result when called twice (no mutations)."""
    assert a.digest() == a.digest()


@given(a=gen_gossip_state("a_"), b=gen_gossip_state("b_"))
@settings(max_examples=50)
def test_gossip_apply_entries_convergence(a, b):
    """After apply_entries(b -> a) and apply_entries(a -> b), states converge."""
    # We simulate a full sync: push all of b's entries into a, and vice versa
    entries_b = list(b._entries.values())  # type: ignore[attr-defined]
    entries_a = list(a._entries.values())  # type: ignore[attr-defined]

    a_copy = GossipState.from_dict(a.to_dict())
    b_copy = GossipState.from_dict(b.to_dict())

    a_copy.apply_entries(entries_b)
    b_copy.apply_entries(entries_a)

    # After full exchange both should have the same entry keys
    assert set(a_copy.to_dict()["entries"].keys()) == set(
        b_copy.to_dict()["entries"].keys()
    )


@given(a=gen_gossip_state("a_"), b=gen_gossip_state("b_"))
@settings(max_examples=50)
def test_gossip_anti_entropy_keys_classify_correctly(a, b):
    """anti_entropy() classifies keys consistently with the digest contents."""
    da, db = a.digest(), b.digest()
    result = anti_entropy(da, db)
    # Keys only in b should be missing from a's digest
    for k in result["missing_local"]:
        assert k not in da
        assert k in db
    # Keys only in a should be missing from b's digest
    for k in result["missing_remote"]:
        assert k in da
        assert k not in db


# ---------------------------------------------------------------------------
# MerkleTree — CRDT laws
# ---------------------------------------------------------------------------


@given(records=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_root_hash_deterministic(records):
    """Building a MerkleTree twice from the same records yields the same root hash."""
    t1 = MerkleTree.from_records(records, key="id")
    t2 = MerkleTree.from_records(records, key="id")
    assert t1.root_hash == t2.root_hash


@given(a=gen_records(max_size=5), b=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_merge_commutativity(a, b):
    """MerkleTree.merge is commutative: merge(a,b).root_hash == merge(b,a).root_hash."""
    ta = MerkleTree.from_records(a, key="id")
    tb = MerkleTree.from_records(b, key="id")
    assert ta.merge(tb).root_hash == tb.merge(ta).root_hash


@given(records=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_merge_idempotency(records):
    """MerkleTree.merge is idempotent: merge(t,t).root_hash == t.root_hash."""
    t = MerkleTree.from_records(records, key="id")
    assert t.merge(t).root_hash == t.root_hash


@given(
    ra=gen_records(max_size=4),
    rb=gen_records(max_size=4),
    rc=gen_records(max_size=4),
)
@settings(max_examples=50)
def test_merkle_merge_associativity(ra, rb, rc):
    """MerkleTree.merge is associative."""
    ta = MerkleTree.from_records(ra, key="id")
    tb = MerkleTree.from_records(rb, key="id")
    tc = MerkleTree.from_records(rc, key="id")
    left = ta.merge(tb).merge(tc)
    right = ta.merge(tb.merge(tc))
    assert left.root_hash == right.root_hash


@given(records=gen_records(max_size=6))
@settings(max_examples=50)
def test_merkle_to_from_dict_roundtrip(records):
    """MerkleTree.to_dict / from_dict preserves root hash."""
    t = MerkleTree.from_records(records, key="id")
    restored = MerkleTree.from_dict(t.to_dict())
    assert restored.root_hash == t.root_hash


# ---------------------------------------------------------------------------
# MerkleTree — diff and convergence
# ---------------------------------------------------------------------------


@given(a=gen_records(max_size=5), b=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_diff_symmetric_keys(a, b):
    """merkle_diff only_in_left and only_in_right are disjoint."""
    ta = MerkleTree.from_records(a, key="id")
    tb = MerkleTree.from_records(b, key="id")
    diff = merkle_diff(ta, tb)
    assert diff.only_in_left.isdisjoint(diff.only_in_right)


@given(records=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_diff_identical_trees_is_empty(records):
    """merkle_diff of identical trees reports no differences."""
    t = MerkleTree.from_records(records, key="id")
    diff = merkle_diff(t, t)
    assert diff.is_identical


@given(a=gen_records(max_size=5), b=gen_records(max_size=5))
@settings(max_examples=50)
def test_merkle_merge_superset_of_inputs(a, b):
    """After merge, every key from both inputs is present in the result."""
    ta = MerkleTree.from_records(a, key="id")
    tb = MerkleTree.from_records(b, key="id")
    merged = ta.merge(tb)
    for k in ta.keys():
        assert merged.contains(k)
    for k in tb.keys():
        assert merged.contains(k)
