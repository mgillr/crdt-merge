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

"""CRDTMergeState contribution tags must be globally unique and restart-safe."""

import json
import random
import subprocess
import sys

import pytest

np = pytest.importorskip("numpy")

from crdt_merge.model.crdt_state import CRDTMergeState, MergeContribution

_PROBE = (
    "from crdt_merge.model.crdt_state import MergeContribution as M;"
    "print(M('m', [1.0, 2.0], 1.0, 1)._tag)"
)


def _tag_in_fresh_process():
    return subprocess.check_output([sys.executable, "-c", _PROBE], text=True).strip()


def _vis(s):
    return {mid: c.merkle_hash for mid, c in s._contributions.items() if c._tag not in s._tombstones}


class TestTagUniqueness:

    def test_tags_differ_across_processes(self):
        assert _tag_in_fresh_process() != _tag_in_fresh_process()

    def test_tags_unique_within_process(self):
        tags = {MergeContribution("m", [1.0], 1.0, 1)._tag for _ in range(2000)}
        assert len(tags) == 2000

    def test_restarted_replica_add_not_swallowed_by_old_tombstone(self, monkeypatch):
        """Replica A removes m@v1; replica B restarts and adds m@v1 afresh.

        With a process-local counter both replicas produced the same tag
        (``m:v1:t0``) for unrelated adds, so B's contribution looked removed.
        The counter reset below is exactly what a process restart does.
        """
        import itertools
        monkeypatch.setattr(CRDTMergeState, "_tag_seq", itertools.count(), raising=False)
        a = CRDTMergeState("weight_average")
        a.add([1.0, 2.0], model_id="m", version=1)
        a.remove("m")
        monkeypatch.setattr(CRDTMergeState, "_tag_seq", itertools.count(), raising=False)
        b = CRDTMergeState("weight_average")
        b.add([1.0, 2.0], model_id="m", version=1)
        a_copy = CRDTMergeState.from_dict(a.to_dict())
        a_copy._tombstones = set(a._tombstones)
        for merged in (a.merge(b), b.merge(a_copy)):
            assert "m" in merged._active_ids(), "independent add swallowed by tag collision"

    def test_tag_survives_serialisation_so_remove_replicates(self):
        a = CRDTMergeState("weight_average")
        a.add([1.0, 2.0], model_id="m", version=1)
        b = CRDTMergeState.from_dict(json.loads(json.dumps(a.to_dict())))
        b.remove("m")
        assert "m" not in a.merge(b)._active_ids()

    def test_legacy_dict_without_tags_loads(self):
        a = CRDTMergeState("weight_average")
        a.add([1.0, 2.0], model_id="m", version=1)
        d = json.loads(json.dumps(a.to_dict()))
        for c in d["contributions"].values():
            c.pop("tag", None)
        b = CRDTMergeState.from_dict(d)
        assert b._active_ids() == a._active_ids()


def _replicas(ops):
    reps = [CRDTMergeState("weight_average") for _ in range(3)]
    for kind, r, mid, ver, other in ops:
        if kind == "add":
            reps[r].add([float(ver), 1.0], model_id=mid, version=ver)
        elif kind == "remove":
            reps[r].remove(mid)
        else:
            reps[r] = CRDTMergeState.from_dict(reps[r].to_dict()).merge(reps[other])
    return reps


from hypothesis import given, settings, strategies as st

_ops = st.lists(
    st.tuples(st.sampled_from(["add", "remove", "sync"]), st.integers(0, 2),
              st.sampled_from(["m1", "m2"]), st.integers(1, 3), st.integers(0, 2)),
    max_size=20,
)


class TestLaws:

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_commutative(self, ops):
        x, y, _ = _replicas(ops)
        a = CRDTMergeState.from_dict(x.to_dict()).merge(CRDTMergeState.from_dict(y.to_dict()))
        b = CRDTMergeState.from_dict(y.to_dict()).merge(CRDTMergeState.from_dict(x.to_dict()))
        assert _vis(a) == _vis(b)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_idempotent(self, ops):
        x, _, _ = _replicas(ops)
        c = CRDTMergeState.from_dict(x.to_dict())
        assert _vis(c.merge(x)) == _vis(x)

    @given(_ops)
    @settings(max_examples=100, deadline=None)
    def test_stale_replica_recovery_and_redelivery(self, ops):
        x, y, z = _replicas(ops)
        snap = CRDTMergeState.from_dict(x.to_dict())
        x.remove("m1")
        merged = CRDTMergeState.from_dict(x.to_dict()).merge(snap).merge(snap)
        assert "m1" not in merged._active_ids() or "m1" in x._active_ids()
