# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Regression and property tests for ORSet and LWWMap.

* ORSet: a remove must record the tags it observed, so that a stale replica
  that still carries those tags cannot resurrect the element on merge.
* LWWMap: ``get`` and ``value`` must agree on which keys are live.
"""

import itertools
import random

import pytest
from hypothesis import given, settings, strategies as st

from crdt_merge.core import LWWMap, ORSet


def _orset_state(s):
    """Comparable full state (live tags and observed-removed tags)."""
    return (
        {e: frozenset(t) for e, t in s._elements.items() if t},
        frozenset(getattr(s, "_tombstones", ())),
    )


# ---------------------------------------------------------------------------
# Bug 1: ORSet resurrection by a stale replica
# ---------------------------------------------------------------------------

class TestORSetResurrection:

    def test_stale_replica_cannot_resurrect_removed_element(self):
        a, b = ORSet(), ORSet()
        a.add("x")
        b = b.merge(a)            # B syncs and now holds A's tag for x
        a.remove("x")
        assert not a.contains("x")
        a = a.merge(b)            # A merges B's stale state
        assert not a.contains("x"), "removed element resurrected by stale merge"
        assert "x" not in a.value

    def test_stale_merge_in_either_order(self):
        a = ORSet()
        a.add("x")
        b = ORSet().merge(a)
        a.remove("x")
        assert "x" not in a.merge(b).value
        assert "x" not in b.merge(a).value

    def test_concurrent_add_still_wins_over_remove(self):
        a = ORSet()
        a.add("x")
        b = ORSet().merge(a)
        a.remove("x")
        b.add("x")                # concurrent, unobserved by A's remove
        assert "x" in a.merge(b).value
        assert "x" in b.merge(a).value

    def test_readd_after_remove_is_live_and_survives_stale_state(self):
        a = ORSet()
        a.add("x")
        stale = ORSet().merge(a)
        a.remove("x")
        a.add("x")
        assert "x" in a.merge(stale).value

    def test_remove_tag_is_also_observed_remove(self):
        a = ORSet()
        tag = a.add("x")
        stale = ORSet().merge(a)
        a.remove_tag("x", tag)
        assert "x" not in a.merge(stale).value

    def test_serialisation_round_trip_keeps_removes(self):
        a = ORSet()
        a.add("x")
        stale = ORSet().merge(a)
        a.remove("x")
        a2 = ORSet.from_dict(a.to_dict())
        assert "x" not in a2.merge(stale).value

    def test_legacy_dict_without_tombstones_loads(self):
        legacy = {"type": "or_set", "elements": {"x": ["t1", "t2"], "y": []}}
        s = ORSet.from_dict(legacy)
        assert s.value == {"x"}
        assert s.merge(ORSet()).value == {"x"}

    def test_no_tombstones_key_when_nothing_removed(self):
        s = ORSet()
        s.add("x")
        assert "tombstones" not in s.to_dict()


# ---------------------------------------------------------------------------
# ORSet CRDT laws: random op histories on three replicas
# ---------------------------------------------------------------------------

def _build_replicas(ops):
    reps = [ORSet(), ORSet(), ORSet()]
    for kind, r, elem, other in ops:
        if kind == "add":
            reps[r].add(elem)
        elif kind == "remove":
            reps[r].remove(elem)
        else:  # sync r <- other
            reps[r] = reps[r].merge(reps[other])
    return reps


_ops = st.lists(
    st.tuples(
        st.sampled_from(["add", "remove", "sync"]),
        st.integers(0, 2),
        st.sampled_from(["a", "b", "c"]),
        st.integers(0, 2),
    ),
    max_size=25,
)


class TestORSetLaws:

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_commutative(self, ops):
        x, y, _ = _build_replicas(ops)
        assert _orset_state(x.merge(y)) == _orset_state(y.merge(x))

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_associative(self, ops):
        x, y, z = _build_replicas(ops)
        assert _orset_state(x.merge(y).merge(z)) == _orset_state(x.merge(y.merge(z)))

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_idempotent(self, ops):
        x, _, _ = _build_replicas(ops)
        assert _orset_state(x.merge(x)) == _orset_state(x)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_duplicate_and_out_of_order_delivery(self, ops):
        x, y, z = _build_replicas(ops)
        states = [x, y, z]
        reference = x.merge(y).merge(z)
        rng = random.Random(7)
        for _ in range(5):
            order = states * 2          # duplicates
            rng.shuffle(order)          # out of order
            acc = ORSet()
            for s in order:
                acc = acc.merge(s)
            assert _orset_state(acc) == _orset_state(reference)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_stale_replica_recovery(self, ops):
        """Merging an older snapshot of a replica into its successor is a no-op."""
        x, y, _ = _build_replicas(ops)
        snapshot = ORSet.from_dict(x.to_dict())
        x.remove("a")
        x.add("b")
        merged = x.merge(snapshot)
        assert _orset_state(merged) == _orset_state(x.merge(x))
        assert "a" not in merged.value or "a" in x.value

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_serialisation_round_trip(self, ops):
        x, _, _ = _build_replicas(ops)
        assert _orset_state(ORSet.from_dict(x.to_dict())) == _orset_state(x)


# ---------------------------------------------------------------------------
# Bug 2: LWWMap get() / value disagree after merging an older delete
# ---------------------------------------------------------------------------

class TestLWWMapGetValueAgree:

    def test_older_delete_merged_with_newer_write(self):
        w, d = LWWMap(), LWWMap()
        d.set("k", "old", timestamp=1.0)
        d.delete("k", timestamp=2.0)
        w.set("k", "new", timestamp=3.0)
        for m in (w.merge(d), d.merge(w)):
            assert m.value == {"k": "new"}
            assert m.get("k") == "new"

    def test_newer_delete_hides_key_in_both_views(self):
        w, d = LWWMap(), LWWMap()
        w.set("k", "v", timestamp=1.0)
        d.delete("k", timestamp=2.0)
        for m in (w.merge(d), d.merge(w)):
            assert m.value == {}
            assert m.get("k") is None
            assert m.get("k", "dflt") == "dflt"

    def test_equal_timestamp_delete_wins_in_both_views(self):
        w, d = LWWMap(), LWWMap()
        w.set("k", "v", timestamp=5.0)
        d.delete("k", timestamp=5.0)
        m = w.merge(d)
        assert "k" not in m.value
        assert m.get("k") is None

    def test_get_matches_value_after_direct_ops(self):
        m = LWWMap()
        m.set("k", "v", timestamp=10.0)
        m.delete("k", timestamp=5.0)   # delete older than the write
        assert m.get("k") == m.value.get("k") == "v"


_map_ops = st.lists(
    st.tuples(
        st.sampled_from(["set", "delete", "sync"]),
        st.integers(0, 2),
        st.sampled_from(["k1", "k2"]),
        st.integers(1, 20),
        st.integers(0, 2),
    ),
    max_size=25,
)


def _build_maps(ops):
    reps = [LWWMap(), LWWMap(), LWWMap()]
    for kind, r, key, ts, other in ops:
        if kind == "set":
            reps[r].set(key, f"v{r}-{ts}", timestamp=float(ts), node_id=f"n{r}")
        elif kind == "delete":
            reps[r].delete(key, timestamp=float(ts))
        else:
            reps[r] = reps[r].merge(reps[other])
    return reps


def _map_state(m):
    return (m.value, dict(m._tombstones))


class TestLWWMapLaws:

    @given(_map_ops)
    @settings(max_examples=150, deadline=None)
    def test_get_agrees_with_value(self, ops):
        for m in _build_maps(ops):
            for k in ("k1", "k2"):
                sentinel = object()
                assert m.get(k, sentinel) is m.value.get(k, sentinel) or \
                    m.get(k, sentinel) == m.value.get(k, sentinel)
        x, y, z = _build_maps(ops)
        for m in (x.merge(y), y.merge(z), x.merge(y).merge(z)):
            for k in ("k1", "k2"):
                assert (k in m.value) == (m.get(k, "<absent>") != "<absent>")
                if k in m.value:
                    assert m.get(k) == m.value[k]

    @given(_map_ops)
    @settings(max_examples=150, deadline=None)
    def test_commutative(self, ops):
        x, y, _ = _build_maps(ops)
        assert _map_state(x.merge(y)) == _map_state(y.merge(x))

    @given(_map_ops)
    @settings(max_examples=150, deadline=None)
    def test_associative(self, ops):
        x, y, z = _build_maps(ops)
        assert _map_state(x.merge(y).merge(z)) == _map_state(x.merge(y.merge(z)))

    @given(_map_ops)
    @settings(max_examples=150, deadline=None)
    def test_idempotent(self, ops):
        x, _, _ = _build_maps(ops)
        assert _map_state(x.merge(x)) == _map_state(x)

    @given(_map_ops)
    @settings(max_examples=100, deadline=None)
    def test_duplicate_and_out_of_order_delivery(self, ops):
        states = _build_maps(ops)
        reference = states[0].merge(states[1]).merge(states[2])
        rng = random.Random(11)
        for _ in range(5):
            order = states * 2
            rng.shuffle(order)
            acc = LWWMap()
            for s in order:
                acc = acc.merge(s)
            assert _map_state(acc) == _map_state(reference)

    @given(_map_ops)
    @settings(max_examples=100, deadline=None)
    def test_stale_replica_recovery(self, ops):
        x, _, _ = _build_maps(ops)
        snap = LWWMap.from_dict(x.to_dict())
        x.set("k1", "later", timestamp=1000.0, node_id="n0")
        x.delete("k2", timestamp=1001.0)
        merged = x.merge(snap)
        # Visible state must be unchanged (a dominated old tombstone may be
        # re-learned from the stale snapshot; it never shows).
        assert merged.value == x.value
        for k in ("k1", "k2"):
            assert merged.get(k, "<absent>") == x.get(k, "<absent>")
