"""Tests for the conformance history generator (WP02-01).

A history is a random interleaving of local operations, deliveries and faults on N replicas.
The generator is seeded, so every failing history can be replayed from its seed.
"""
import json
import os
import sys

import pytest
from hypothesis import find, given, settings

sys.path.insert(0, os.path.dirname(__file__))

from history import (  # noqa: E402
    FAULT_MODES,
    SUBSYSTEMS,
    History,
    describe,
    generate_history,
    histories,
    run_history,
    view,
)


def test_same_seed_gives_the_same_history():
    a = generate_history(1234, replicas=3, steps=40, subsystem="orset")
    b = generate_history(1234, replicas=3, steps=40, subsystem="orset")
    assert a == b
    assert generate_history(1235, replicas=3, steps=40, subsystem="orset") != a


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_history_has_the_requested_shape(subsystem):
    h = generate_history(7, replicas=4, steps=50, subsystem=subsystem)
    assert h.replicas == 4
    assert len(h.events) == 50
    assert len(h.skews) == 4
    for ev in h.events:
        kind = ev[0]
        assert kind in ("op", "send", "restart", "partition", "heal")
        if kind == "op":
            assert 0 <= ev[1] < 4
        if kind == "send":
            assert ev[1] != ev[2]
            assert ev[3] in FAULT_MODES


def test_every_fault_is_generated():
    seen_modes, seen_kinds = set(), set()
    for seed in range(300):
        for ev in generate_history(seed, replicas=3, steps=40, subsystem="orset").events:
            seen_kinds.add(ev[0])
            if ev[0] == "send":
                seen_modes.add(ev[3])
    assert seen_modes == set(FAULT_MODES)  # drop, duplicate, reorder (stale) and plain delivery
    assert {"restart", "partition", "heal", "op", "send"} <= seen_kinds


def test_history_round_trips_through_json_so_a_failure_replays():
    h = generate_history(99, replicas=3, steps=30, subsystem="lwwmap")
    again = History.from_json(json.dumps(h.to_json()))
    assert again == h


def test_describe_names_the_seed_and_the_call_that_replays_it():
    h = generate_history(4242, replicas=3, steps=25, subsystem="gossip")
    text = describe(h)
    assert "seed=4242" in text
    assert "generate_history(" in text and "subsystem='gossip'" in text


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_replaying_a_history_gives_the_same_observable_states(subsystem):
    h = generate_history(31, replicas=3, steps=40, subsystem=subsystem)
    first = [view(subsystem, s) for s in run_history(h).states]
    second = [view(subsystem, s) for s in run_history(h).states]
    assert first == second


@settings(max_examples=40, deadline=None)
@given(histories("orset", max_replicas=5, max_steps=60))
def test_the_strategy_draws_valid_histories(h):
    assert 2 <= h.replicas <= 5
    assert 1 <= len(h.events) <= 60
    assert "seed=" in describe(h)
    run_history(h)  # must execute without error


def test_a_recorded_seed_replays_through_the_environment(monkeypatch):
    monkeypatch.setenv("CONFORMANCE_SEED", "5150")
    drawn = find(histories("orset"), lambda h: True)
    assert drawn.seed == 5150
