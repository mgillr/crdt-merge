# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CRDTMergeState's opt-in extension protocol (EXTENSION_PROTOCOL = 1): a registered strategy whose class sets
``crdt_extension = True`` resolves through the CRDT state with what it declares (base, seed, the contributions'
ids and metadata) and its ``strategy_kwargs``; every built-in name and every state built without strategy_kwargs
behaves exactly as before."""

import itertools
import json

import pytest

np = pytest.importorskip("numpy")

from crdt_merge.model import strategies as S  # noqa: E402
from crdt_merge.model.crdt_state import CRDTMergeState  # noqa: E402
from crdt_merge.model.strategies.base import ModelMergeStrategy  # noqa: E402

_N = itertools.count()


def _make(marker=True, requires_base=False, stochastic=False, reads=False):
    """A registered probe strategy (a unique name, removed after the test by the fixture)."""
    name = f"probe_extension_{next(_N)}"
    calls = []

    class Probe(ModelMergeStrategy):
        crdt_extension = marker
        requires_base_ = requires_base

        @property
        def name(self):
            return name

        @property
        def category(self):
            return "test"

        @property
        def paper_reference(self):
            return "test"

        @property
        def crdt_properties(self):
            return {"commutative": True, "associative": False, "idempotent": False}

        def merge(self, tensors, weights=None, base=None, **kwargs):
            calls.append({"n": len(tensors), "weights": list(weights or []), "base": base, "kwargs": kwargs})
            out = sum(np.asarray(t, dtype=np.float64) * w for t, w in zip(tensors, weights or [1.0] * len(tensors)))
            return out if base is None else out + base

    Probe.requires_base = requires_base
    Probe.stochastic = stochastic
    Probe.reads_contributions = reads
    S.register_strategy(name)(Probe)
    return name, calls


@pytest.fixture(autouse=True)
def _clean_registry():
    before = set(S._REGISTRY)
    yield
    for k in set(S._REGISTRY) - before:
        del S._REGISTRY[k]


def test_the_protocol_is_declared():
    assert CRDTMergeState.EXTENSION_PROTOCOL == 1
    assert CRDTMergeState.EXTENSION_RESERVED_KWARGS == {"tensors", "weights", "base", "seed", "model_ids", "metadata"}


def test_a_registered_extension_is_accepted_and_one_without_the_marker_is_refused_as_before():
    name, _ = _make()
    assert CRDTMergeState(name).strategy_name == name
    plain, _ = _make(marker=False)
    for bad in (plain, "never_registered"):
        with pytest.raises(ValueError, match=f"Unknown strategy '{bad}'. Known strategies: "):
            CRDTMergeState(bad)


def test_resolve_passes_what_the_extension_declares_in_canonical_order():
    name, calls = _make(requires_base=True, stochastic=True, reads=True)
    st = CRDTMergeState(name, base=np.zeros(3), seed=7, strategy_kwargs={"part": "mlp", "orient": "with_base"})
    st.add(np.full(3, 2.0), model_id="donor:b", weight=0.5, metadata={"role": "donor"})
    st.add(np.ones(3), model_id="donor:a", weight=1.0, metadata={"role": "donor"})
    st.add(np.full(3, 4.0), model_id="root", metadata={"role": "root"})
    out = st.resolve()
    c = calls[-1]
    assert c["kwargs"]["model_ids"] == ["donor:a", "donor:b", "root"] and c["weights"] == [1.0, 0.5, 1.0]
    assert c["kwargs"]["metadata"] == [{"role": "donor"}, {"role": "donor"}, {"role": "root"}]
    assert c["kwargs"]["seed"] == 7 and c["kwargs"]["part"] == "mlp" and c["kwargs"]["orient"] == "with_base"
    assert np.array_equal(c["base"], np.zeros(3)) and np.allclose(out, 1.0 + 1.0 + 4.0)
    assert st.needs_base and st.is_stochastic


def test_an_extension_without_declarations_gets_neither_base_nor_seed_nor_contributions():
    name, calls = _make()
    st = CRDTMergeState(name, base=np.zeros(2))
    st.add(np.ones(2), model_id="a")
    st.resolve()
    assert calls[-1]["base"] is None and calls[-1]["kwargs"] == {}
    assert not st.needs_base and not st.is_stochastic


def test_a_required_base_that_is_missing_is_refused_at_resolve():
    name, _ = _make(requires_base=True)
    st = CRDTMergeState(name)
    st.add(np.ones(2), model_id="a")
    with pytest.raises(ValueError, match="requires base="):
        st.resolve()


def test_strategy_kwargs_are_checked_and_frozen():
    name, calls = _make()
    with pytest.raises(ValueError, match="only for extension strategies"):
        CRDTMergeState("ties", strategy_kwargs={"density": 0.2})
    with pytest.raises(ValueError, match="reserved"):
        CRDTMergeState(name, strategy_kwargs={"seed": 1})
    with pytest.raises(ValueError, match="JSON-serialisable"):
        CRDTMergeState(name, strategy_kwargs={"x": object()})
    for bad in (float("nan"), float("inf")):                  # NaN != NaN would break replica equality
        with pytest.raises(ValueError, match="JSON-serialisable"):
            CRDTMergeState(name, strategy_kwargs={"x": bad})
    with pytest.raises(ValueError, match="string keys"):
        CRDTMergeState(name, strategy_kwargs={1: 2})
    kw = {"lam": 0.5, "nested": {"a": [1, 2]}}
    st = CRDTMergeState(name, strategy_kwargs=kw)
    kw["lam"] = 9.0
    kw["nested"]["a"].append(3)
    st.add(np.ones(2), model_id="a")
    st.resolve()
    assert calls[-1]["kwargs"] == {"lam": 0.5, "nested": {"a": [1, 2]}}


def test_the_crdt_laws_hold_for_an_extension_state():
    name, _ = _make(requires_base=True, reads=True)
    kw = {"part": "attn"}

    def replica(*items):
        st = CRDTMergeState(name, base=np.zeros(2), strategy_kwargs=kw)
        for mid, v in items:
            st.add(np.full(2, v), model_id=mid)
        return st
    a, b, c = replica(("x", 1.0)), replica(("y", 2.0)), replica(("z", 3.0))
    ab_c = replica(("x", 1.0)).merge(b).merge(c)
    c_ba = replica(("z", 3.0)).merge(replica(("y", 2.0)).merge(a))
    assert ab_c == c_ba and np.array_equal(ab_c.resolve(), c_ba.resolve())                  # commutative, associative
    assert replica(("x", 1.0)).merge(a) == a                                                  # idempotent
    many = CRDTMergeState.merge_many([a, b, c])
    assert many.strategy_kwargs == kw and np.array_equal(many.resolve(), ab_c.resolve())
    with pytest.raises(ValueError, match="different strategy_kwargs"):
        CRDTMergeState(name, base=np.zeros(2), strategy_kwargs={"part": "mlp"}).merge(a)
    with pytest.raises(ValueError, match="different strategy_kwargs"):
        CRDTMergeState.merge_many([a, CRDTMergeState(name, base=np.zeros(2))])
    assert CRDTMergeState(name, strategy_kwargs={"part": "mlp"}) != CRDTMergeState(name, strategy_kwargs=kw)


def test_serialisation_round_trips_the_kwargs_and_leaves_every_other_state_unchanged():
    name, _ = _make()
    st = CRDTMergeState(name, strategy_kwargs={"orient": "toward_seed"})
    st.add(np.ones(2), model_id="a")
    back = CRDTMergeState.from_dict(json.loads(json.dumps(st.to_dict())))
    assert back.strategy_kwargs == {"orient": "toward_seed"} and back == st
    plain = CRDTMergeState("weight_average")
    plain.add(np.ones(2), model_id="a")
    d = plain.to_dict()
    assert "strategy_kwargs" not in d and set(d) == {"type", "version", "strategy_name", "base",
                                                      "conflict_resolution", "seed", "contributions", "tombstones"}
    assert CRDTMergeState.from_dict(d).strategy_kwargs is None


def test_built_in_strategies_resolve_exactly_as_their_direct_call():
    rng = np.random.default_rng(0)
    base, x, y = rng.normal(size=8), rng.normal(size=8), rng.normal(size=8)
    st = CRDTMergeState("ties", base=base)
    st.add(y, model_id="y")
    st.add(x, model_id="x")
    direct = S.get_strategy("ties").merge([np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)],
                                          weights=[1.0, 1.0], base=np.asarray(base, dtype=np.float64))
    assert np.array_equal(st.resolve(), direct)
    wa = CRDTMergeState("weight_average")
    wa.add(x, model_id="x")
    wa.add(y, model_id="y")
    assert np.array_equal(wa.resolve(), S.get_strategy("weight_average").merge(
        [np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)], weights=[1.0, 1.0]))
    assert CRDTMergeState("ties").needs_base and CRDTMergeState("dare").is_stochastic
    assert not CRDTMergeState("weight_average").needs_base
