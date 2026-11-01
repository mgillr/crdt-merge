"""Named fault scenarios and history-checked outcomes (WP02-03).

Each scenario is a scripted history that is replayed against every subsystem (ORSet, LWWMap,
AgentState, TrustAgentState and gossip state), with every delivery crossing the serialised
form. The second half runs random histories and compares the converged result with an oracle
that is computed from the events alone, never from the merge code under test.
"""
import os
import sys

import pytest
from hypothesis import given

sys.path.insert(0, os.path.dirname(__file__))

from history import (  # noqa: E402
    ADAPTERS,
    History,
    assert_converged,
    conformance_settings,
    describe,
    heal,
    histories,
    lwwmap_oracle,
    orset_oracle,
    run_history,
    view,
)

NAMES = {
    "orset": "ORSet",
    "lwwmap": "LWWMap",
    "agentstate": "AgentState",
    "trustagentstate": "TrustAgentState",
    "gossip": "gossip",
}
SUBSYSTEMS = list(NAMES)
ALL = pytest.mark.parametrize("subsystem", SUBSYSTEMS, ids=[NAMES[s] for s in SUBSYSTEMS])

ADD = {"orset": "add", "lwwmap": "set", "agentstate": "add_tag", "trustagentstate": "put", "gossip": "update"}
REMOVE = {
    "orset": "remove",
    "lwwmap": "delete",
    "agentstate": "remove_tag",
    "trustagentstate": "delete",
    "gossip": "delete",
}


def present(subsystem, state, key):
    """Is ``key`` live in the observable view of ``state``?"""
    v = view(subsystem, state)
    if subsystem == "orset":
        return key in v
    if subsystem == "lwwmap":
        return any(k == key for k, _ in v)
    if subsystem == "agentstate":
        return key in v[1]
    if subsystem == "trustagentstate":
        return any(entry[0] == key for entry in v)
    return any(entry[0] == key and not entry[2] for entry in v)


def history(subsystem, events, replicas=3, skews=None):
    return History(0, replicas, subsystem, tuple(skews or (0,) * replicas), tuple(events))


def op(subsystem, replica, kind, key="a"):
    return ("op", replica, (ADD if kind == "add" else REMOVE)[subsystem], key)


def send(src, dst, mode="deliver", age=0):
    return ("send", src, dst, mode, age)


# --------------------------------------------------------------------------------------
# Scripted fault scenarios
# --------------------------------------------------------------------------------------

@ALL
def test_deletion_propagation(subsystem):
    """A removal made after seeing an element reaches every replica."""
    h = history(subsystem, [
        op(subsystem, 0, "add"), send(0, 1), send(0, 2),
        op(subsystem, 1, "remove"), send(1, 0), send(1, 2),
    ])
    run = run_history(h)
    for r, state in enumerate(run.states):
        assert not present(subsystem, state, "a"), f"replica {r} still holds a removed key; {describe(h)}"


@ALL
def test_stale_replica(subsystem):
    """A replica that never saw the removal must not resurrect the key when it syncs late."""
    h = history(subsystem, [
        op(subsystem, 0, "add"), send(0, 1), send(0, 2),
        op(subsystem, 1, "remove"), send(1, 0),
        send(2, 0), send(2, 1),  # replica 2 is stale and now syncs with everyone
    ])
    run = run_history(h)
    for r in (0, 1):
        assert not present(subsystem, run.states[r], "a"), (
            f"key resurrected on replica {r} by a stale replica; {describe(h)}"
        )
    healed = heal(subsystem, run.states)
    assert_converged(subsystem, healed, h)
    assert not present(subsystem, healed[0], "a"), f"key resurrected after heal; {describe(h)}"


@ALL
def test_duplicate_delivery(subsystem):
    """Delivering the same state twice, or ten times, gives the same result as once."""
    base = [
        op(subsystem, 0, "add", "a"), op(subsystem, 0, "add", "b"),
        op(subsystem, 0, "remove", "a"), op(subsystem, 1, "add", "c"),
    ]
    once = run_history(history(subsystem, base + [send(0, 1), send(1, 2)]))
    many = run_history(history(subsystem, base + [send(0, 1, "duplicate"), send(0, 1, "duplicate"),
                                                   send(1, 2, "duplicate"), send(1, 2, "duplicate")]))
    for r in range(3):
        assert view(subsystem, once.states[r]) == view(subsystem, many.states[r]), f"replica {r} differs"


@ALL
def test_out_of_order_delivery(subsystem):
    """An old snapshot arriving before or after the newest one does not change the outcome."""
    base = [op(subsystem, 0, "add", "a"), op(subsystem, 0, "add", "b"), op(subsystem, 0, "remove", "a")]
    old_then_new = run_history(history(subsystem, base + [send(0, 1, "stale", 2), send(0, 1)]))
    new_then_old = run_history(history(subsystem, base + [send(0, 1), send(0, 1, "stale", 2)]))
    assert view(subsystem, old_then_new.states[1]) == view(subsystem, new_then_old.states[1])
    assert not present(subsystem, new_then_old.states[1], "a"), "an older snapshot undid a removal"
    assert present(subsystem, new_then_old.states[1], "b")


@ALL
def test_process_restart(subsystem):
    """Saving and reloading a replica between any two events changes nothing a reader can see."""
    for seed in range(15):
        from history import generate_history

        plain = generate_history(seed, replicas=3, steps=30, subsystem=subsystem)
        events = []
        for ev in plain.events:
            events.append(ev)
            events.extend(("restart", r) for r in range(plain.replicas))
        restarted = History(plain.seed, plain.replicas, plain.subsystem, plain.skews, tuple(events))
        a, b = run_history(plain), run_history(restarted)
        for r in range(plain.replicas):
            assert view(subsystem, a.states[r]) == view(subsystem, b.states[r]), (
                f"replica {r} changed across restarts; {describe(plain)}"
            )


@ALL
def test_restarted_replica_does_not_resurrect_a_removed_key(subsystem):
    """After a restart the replica still remembers that the key was removed."""
    h = history(subsystem, [
        op(subsystem, 0, "add"), send(0, 1), send(0, 2),
        op(subsystem, 1, "remove"), ("restart", 1),
        send(2, 1),  # stale state arrives after the restart
        ("restart", 1), send(1, 0),
    ])
    run = run_history(h)
    assert not present(subsystem, run.states[1], "a"), f"key resurrected after restart; {describe(h)}"
    assert not present(subsystem, run.states[0], "a"), f"key resurrected on a peer; {describe(h)}"


@ALL
def test_clock_skew(subsystem):
    """Replicas with clocks 30 seconds apart still end up identical, whatever the sync order."""
    h = history(
        subsystem,
        [op(subsystem, 0, "add"), op(subsystem, 1, "add"), op(subsystem, 2, "add"),
         op(subsystem, 1, "remove"), op(subsystem, 0, "add", "b"), op(subsystem, 2, "add", "b")],
        skews=(0, 30, -30),
    )
    run = run_history(h)
    reference = None
    for order in ([0, 1, 2], [2, 1, 0], [1, 2, 0], [2, 0, 1]):
        healed = heal(subsystem, [run.states[i] for i in order])
        assert_converged(subsystem, healed, h)
        if reference is None:
            reference = view(subsystem, healed[0])
        assert view(subsystem, healed[0]) == reference, f"result depends on sync order {order}"


@ALL
def test_replica_id_collision(subsystem):
    """Two replicas that share one identity and write concurrently still converge.

    The writes carry different timestamps, so a last-writer-wins structure has a defined winner.
    """
    ad = ADAPTERS[subsystem]
    a, b = ad.new(0), ad.new(0)  # same replica number, therefore the same identity
    a = ad.apply(a, 0, ADD[subsystem], "k", 1, 10.0)
    b = ad.apply(b, 0, ADD[subsystem], "k", 2, 20.0)
    a = ad.apply(a, 0, ADD[subsystem], "only-a", 3, 30.0)
    ab = ad.merge(a, ad.load(ad.dump(b), 0))
    ba = ad.merge(b, ad.load(ad.dump(a), 0))
    assert view(subsystem, ab) == view(subsystem, ba)
    assert present(subsystem, ab, "k") and present(subsystem, ab, "only-a")


@pytest.mark.parametrize("subsystem", ["orset", "trustagentstate", "agentstate"],
                         ids=["ORSet", "TrustAgentState", "AgentState"])
def test_concurrent_add_survives_a_remove_that_never_saw_it(subsystem):
    """Add wins: a remove only removes what its replica had observed."""
    h = history(subsystem, [
        op(subsystem, 0, "add"), send(0, 1),
        op(subsystem, 1, "remove"),  # removes the add it observed
        op(subsystem, 2, "add"),  # concurrent add that replica 1 never saw
        send(1, 0), send(2, 0), send(2, 1), send(0, 2), send(1, 2),
    ])
    run = run_history(h)
    healed = heal(subsystem, run.states)
    assert_converged(subsystem, healed, h)
    assert present(subsystem, healed[0], "a"), f"a concurrent add was lost; {describe(h)}"


@ALL
def test_partition_and_heal(subsystem):
    """Replicas that diverge during a partition agree once it heals."""
    h = history(subsystem, [
        ("partition", ((0, 1), (2, 3))),
        op(subsystem, 0, "add", "a"), op(subsystem, 2, "add", "b"), op(subsystem, 3, "add", "a"),
        send(0, 1), send(2, 3), send(0, 2), send(3, 1),  # the last two cross the partition and are lost
        op(subsystem, 1, "remove", "a"), op(subsystem, 2, "add", "c"),
        send(1, 0), send(3, 2),
        ("heal",),
        send(0, 2), send(1, 3), send(2, 0), send(3, 1),
    ], replicas=4)
    run = run_history(h)
    assert run.dropped >= 2, "the partition did not drop cross-partition sends"
    healed = heal(subsystem, run.states)
    assert_converged(subsystem, healed, h)
    assert present(subsystem, healed[0], "b") and present(subsystem, healed[0], "c")


# --------------------------------------------------------------------------------------
# Random histories checked against an oracle
# --------------------------------------------------------------------------------------

@ALL
def test_random_histories_converge_after_heal(subsystem):
    @conformance_settings()
    @given(histories(subsystem, max_replicas=5, max_steps=60))
    def check(h):
        healed = heal(subsystem, run_history(h).states)
        assert_converged(subsystem, healed, h)

    check()


@pytest.mark.parametrize("subsystem", ["orset", "trustagentstate"], ids=["ORSet", "TrustAgentState"])
def test_random_histories_match_the_observed_remove_oracle(subsystem):
    """After a full sync, a key is live iff some add of it was never observed and removed."""

    @conformance_settings()
    @given(histories(subsystem, max_replicas=5, max_steps=60))
    def check(h):
        run = run_history(h)
        healed = heal(subsystem, run.states)
        live = tuple(sorted({k for k in "abcd" if present(subsystem, healed[0], k)}))
        assert live == orset_oracle(run), f"live keys {live} != oracle {orset_oracle(run)}; {describe(h)}"

    check()


def test_random_histories_match_the_agentstate_tag_oracle():
    @conformance_settings()
    @given(histories("agentstate", max_replicas=5, max_steps=60))
    def check(h):
        run = run_history(h)
        healed = heal("agentstate", run.states)
        assert tuple(sorted(view("agentstate", healed[0])[1])) == orset_oracle(run), describe(h)

    check()


def test_random_histories_match_the_lwwmap_oracle():
    """The converged map equals the map computed from the events alone."""

    @conformance_settings()
    @given(histories("lwwmap", max_replicas=5, max_steps=60))
    def check(h):
        healed = heal("lwwmap", run_history(h).states)
        assert view("lwwmap", healed[0]) == lwwmap_oracle(h), describe(h)

    check()
