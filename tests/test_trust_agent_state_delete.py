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

"""TrustAgentState.delete must replicate (observed-remove tombstones)."""

import random

from hypothesis import given, settings, strategies as st

from crdt_merge.e4.integration.agent_bridge import TrustAgentState


def _view(s):
    return {k: (e.value, e.peer_id, e.timestamp) for k, e in s._entries.items()}


def _full(s):
    return (_view(s), frozenset(getattr(s, "_tombstones", ())))


class TestDeleteReplicates:

    def test_delete_propagates_through_merge(self):
        a = TrustAgentState()
        a.put("k", "v", "alice", timestamp=1.0)
        b = TrustAgentState().merge_context(a)   # B syncs from A
        b.delete("k")
        assert b.get("k") is None
        merged = a.merge_context(b)
        assert merged.get("k") is None, "delete did not replicate"
        assert b.merge_context(a).get("k") is None

    def test_stale_replica_cannot_resurrect_deleted_key(self):
        a = TrustAgentState()
        a.put("k", "v", "alice", timestamp=1.0)
        stale = TrustAgentState().merge_context(a)
        a.delete("k")
        assert a.merge_context(stale).get("k") is None
        assert stale.merge_context(a).get("k") is None

    def test_concurrent_put_survives_delete(self):
        a = TrustAgentState()
        a.put("k", "v1", "alice", timestamp=1.0)
        b = TrustAgentState().merge_context(a)
        a.delete("k")
        b.put("k", "v2", "bob", timestamp=2.0)   # concurrent with the delete
        assert a.merge_context(b).get("k").value == "v2"
        assert b.merge_context(a).get("k").value == "v2"

    def test_put_after_delete_is_live(self):
        a = TrustAgentState()
        a.put("k", "v1", "alice", timestamp=1.0)
        stale = TrustAgentState().merge_context(a)
        a.delete("k")
        a.put("k", "v2", "alice", timestamp=2.0)
        assert a.merge_context(stale).get("k").value == "v2"

    def test_delete_returns_removed_entry_or_none(self):
        s = TrustAgentState()
        s.put("k", "v", "alice")
        assert s.delete("k").value == "v"
        assert s.delete("k") is None
        assert s.delete("never") is None

    def test_serialisation_round_trip_keeps_deletes(self):
        a = TrustAgentState()
        a.put("k", "v", "alice", timestamp=1.0)
        stale = TrustAgentState.from_dict(a.to_dict())
        a.delete("k")
        a2 = TrustAgentState.from_dict(a.to_dict())
        assert a2.merge_context(stale).get("k") is None


_ops = st.lists(
    st.tuples(
        st.sampled_from(["put", "delete", "sync"]),
        st.integers(0, 2),
        st.sampled_from(["k1", "k2"]),
        st.integers(1, 9),
        st.integers(0, 2),
    ),
    max_size=25,
)


def _build(ops):
    reps = [TrustAgentState(), TrustAgentState(), TrustAgentState()]
    for kind, r, key, ts, other in ops:
        if kind == "put":
            reps[r].put(key, f"v{r}-{ts}", f"peer{r}", timestamp=float(ts))
        elif kind == "delete":
            reps[r].delete(key)
        else:
            reps[r] = reps[r].merge_context(reps[other])
    return reps


class TestLaws:

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_commutative(self, ops):
        x, y, _ = _build(ops)
        assert _full(x.merge_context(y)) == _full(y.merge_context(x))

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_associative(self, ops):
        x, y, z = _build(ops)
        assert _full(x.merge_context(y).merge_context(z)) == _full(
            x.merge_context(y.merge_context(z)))

    @given(_ops)
    @settings(max_examples=150, deadline=None)
    def test_idempotent(self, ops):
        x, _, _ = _build(ops)
        assert _full(x.merge_context(x)) == _full(x)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_duplicate_and_out_of_order_delivery(self, ops):
        states = _build(ops)
        reference = states[0].merge_context(states[1]).merge_context(states[2])
        rng = random.Random(3)
        for _ in range(5):
            order = states * 2
            rng.shuffle(order)
            acc = TrustAgentState()
            for s in order:
                acc = acc.merge_context(s)
            assert _view(acc) == _view(reference)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_stale_replica_recovery(self, ops):
        x, _, _ = _build(ops)
        snap = TrustAgentState.from_dict(x.to_dict())
        x.delete("k1")
        x.put("k2", "later", "peer0", timestamp=100.0)
        assert _view(x.merge_context(snap)) == _view(x)
