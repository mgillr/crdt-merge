"""Operation histories for the CRDT conformance gate.

A history is a random interleaving of local operations, deliveries and faults on N replicas.
It is seeded: the same seed, replica count, step count and subsystem always give the same
history, so a failure replays from the line that ``describe`` prints.

Faults modelled:
    drop       the delivery never arrives
    duplicate  the same delivery arrives twice
    stale      an older snapshot of the sender arrives after newer ones (reordering)
    restart    a replica reloads from its own serialised form
    partition  deliveries across the groups are dropped until the matching heal

Every delivery crosses the wire form: the sender is serialised with ``to_dict`` and the
receiver rebuilds it with ``from_dict`` before merging.

Environment:
    CONFORMANCE_SEED       replay one seed
    CONFORMANCE_REPLICAS   replica count for that replay
    CONFORMANCE_STEPS      step count for that replay
    CONFORMANCE_EXAMPLES   number of histories each property test draws (default 100)
"""
from __future__ import annotations

import copy
import json
import os
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from hypothesis import settings, strategies as st

from crdt_merge.agentic import AgentState
from crdt_merge.core import LWWMap, ORSet
from crdt_merge.e4.integration.agent_bridge import TrustAgentState
from crdt_merge.gossip import GossipState

SUBSYSTEMS = ("orset", "lwwmap", "agentstate", "trustagentstate", "gossip")
FAULT_MODES = ("deliver", "duplicate", "stale", "drop")
KEYS = ("a", "b", "c", "d")

_OPS = {
    "orset": ("add", "remove"),
    "lwwmap": ("set", "delete"),
    "agentstate": ("add_fact", "add_tag", "remove_tag", "increment"),
    "trustagentstate": ("put", "delete"),
    "gossip": ("update", "delete"),
}
_SKEWS = (-30, -3, 0, 0, 3, 30)


@dataclass(frozen=True)
class History:
    seed: int
    replicas: int
    subsystem: str
    skews: Tuple[int, ...]
    events: Tuple[tuple, ...]

    def to_json(self) -> dict:
        return {
            "seed": self.seed,
            "replicas": self.replicas,
            "subsystem": self.subsystem,
            "skews": list(self.skews),
            "events": [_listify(e) for e in self.events],
        }

    @classmethod
    def from_json(cls, data) -> "History":
        d = json.loads(data) if isinstance(data, str) else data
        return cls(
            seed=d["seed"],
            replicas=d["replicas"],
            subsystem=d["subsystem"],
            skews=tuple(d["skews"]),
            events=tuple(_tuplify(e) for e in d["events"]),
        )


def _listify(x):
    return [_listify(i) for i in x] if isinstance(x, (tuple, list)) else x


def _tuplify(x):
    return tuple(_tuplify(i) for i in x) if isinstance(x, (tuple, list)) else x


def describe(history: History) -> str:
    """One line that names the seed and the call that regenerates the history."""
    return (
        f"history seed={history.seed} subsystem={history.subsystem} "
        f"replicas={history.replicas} steps={len(history.events)}; replay with "
        f"generate_history({history.seed}, replicas={history.replicas}, "
        f"steps={len(history.events)}, subsystem={history.subsystem!r})"
    )


def generate_history(seed: int, *, replicas: int = 3, steps: int = 40, subsystem: str = "orset") -> History:
    """A seeded random history of ``steps`` events on ``replicas`` replicas."""
    if subsystem not in _OPS:
        raise ValueError(f"unknown subsystem {subsystem!r}; expected one of {SUBSYSTEMS}")
    rng = random.Random(seed)
    skews = tuple(rng.choice(_SKEWS) for _ in range(replicas))
    events: List[tuple] = []
    partitioned = False
    for _ in range(steps):
        roll = rng.random()
        if roll < 0.50:
            events.append(("op", rng.randrange(replicas), rng.choice(_OPS[subsystem]), rng.choice(KEYS)))
        elif roll < 0.85:
            src, dst = rng.sample(range(replicas), 2)
            mode = rng.choices(FAULT_MODES, weights=(55, 15, 15, 15))[0]
            events.append(("send", src, dst, mode, rng.randrange(1, 6)))
        elif roll < 0.92:
            events.append(("restart", rng.randrange(replicas)))
        elif partitioned:
            events.append(("heal",))
            partitioned = False
        elif replicas >= 2:
            cut = rng.randrange(1, replicas)
            order = list(range(replicas))
            rng.shuffle(order)
            events.append(("partition", (tuple(sorted(order[:cut])), tuple(sorted(order[cut:])))))
            partitioned = True
        else:
            events.append(("restart", 0))
    return History(seed, replicas, subsystem, skews, tuple(events))


def conformance_settings(**overrides):
    """Hypothesis settings for the gate: no deadline, a failing example prints its blob."""
    examples = int(os.environ.get("CONFORMANCE_EXAMPLES", "100"))
    return settings(max_examples=examples, deadline=None, print_blob=True, **overrides)


def histories(subsystem: str = "orset", max_replicas: int = 4, max_steps: int = 40, min_replicas: int = 2):
    """A Hypothesis strategy of histories. ``CONFORMANCE_SEED`` pins the seed for a replay."""
    pinned = os.environ.get("CONFORMANCE_SEED")
    seed = st.just(int(pinned)) if pinned is not None else st.integers(min_value=0, max_value=2**31 - 1)
    if os.environ.get("CONFORMANCE_REPLICAS"):
        n = st.just(int(os.environ["CONFORMANCE_REPLICAS"]))
    else:
        n = st.integers(min_value=min_replicas, max_value=max_replicas)
    if os.environ.get("CONFORMANCE_STEPS"):
        steps = st.just(int(os.environ["CONFORMANCE_STEPS"]))
    else:
        steps = st.integers(min_value=1, max_value=max_steps)
    return st.builds(
        lambda s, r, k: generate_history(s, replicas=r, steps=k, subsystem=subsystem), seed, n, steps
    )


# ---------------------------------------------------------------------------------------
# Subsystem adapters: one small shim per type so a history runs the same way on all five.
# ---------------------------------------------------------------------------------------

@dataclass
class Adapter:
    new: Callable[[int], Any]
    apply: Callable[[Any, int, str, str, int, float], Any]  # state, replica, op, key, step, ts
    merge: Callable[[Any, Any], Any]
    dump: Callable[[Any], dict]
    load: Callable[[dict, int], Any]
    view: Callable[[Any], Any]


def _orset() -> Adapter:
    def apply(s, r, op, key, step, ts):
        if op == "add":
            s.add(key)
        else:
            s.remove(key)
        return s

    return Adapter(
        new=lambda r: ORSet(),
        apply=apply,
        merge=lambda a, b: a.merge(b),
        dump=lambda s: copy.deepcopy(s.to_dict()),
        load=lambda d, r: ORSet.from_dict(copy.deepcopy(d)),
        view=lambda s: tuple(sorted(s.value)),
    )


def _lwwmap() -> Adapter:
    def apply(s, r, op, key, step, ts):
        if op == "set":
            s.set(key, step, timestamp=ts, node_id=f"r{r}")
        else:
            s.delete(key, timestamp=ts)
        return s

    return Adapter(
        new=lambda r: LWWMap(),
        apply=apply,
        merge=lambda a, b: a.merge(b),
        dump=lambda s: copy.deepcopy(s.to_dict()),
        load=lambda d, r: LWWMap.from_dict(copy.deepcopy(d)),
        view=lambda s: tuple(sorted(s.value.items())),
    )


def _agentstate() -> Adapter:
    def apply(s, r, op, key, step, ts):
        if op == "add_fact":
            s.add_fact(key, step, timestamp=ts)
        elif op == "add_tag":
            s.add_tag(key)
        elif op == "remove_tag":
            s.remove_tag(key)
        else:
            s.increment(key)
        return s

    def view(s):
        facts = tuple(sorted((k, f.value, f.confidence, f.source_agent, f.timestamp) for k, f in s.list_facts().items()))
        counters = tuple(sorted((k, s.counter_value(k)) for k in s._counters))
        return (facts, tuple(sorted(s.tags)), counters)

    return Adapter(
        new=lambda r: AgentState(agent_id=f"agent{r}"),
        apply=apply,
        merge=lambda a, b: a.merge(b),
        dump=lambda s: copy.deepcopy(s.to_dict()),
        load=lambda d, r: AgentState.from_dict(copy.deepcopy(d)),
        view=view,
    )


def _trustagentstate() -> Adapter:
    def apply(s, r, op, key, step, ts):
        if op == "put":
            s.put(key, step, f"peer{r}", timestamp=ts)
        else:
            s.delete(key)
        return s

    return Adapter(
        new=lambda r: TrustAgentState(),
        apply=apply,
        merge=lambda a, b: a.merge_context(b),
        dump=lambda s: copy.deepcopy(s.to_dict()),
        load=lambda d, r: TrustAgentState.from_dict(copy.deepcopy(d)),
        view=lambda s: tuple(sorted((k, e.value, e.peer_id, e.timestamp) for k, e in s.snapshot().items())),
    )


def _gossip() -> Adapter:
    def apply(s, r, op, key, step, ts):
        if op == "update":
            s.update(key, step)
        else:
            s.delete(key)
        return s

    def view(s):
        return tuple(
            sorted((k, repr(e.value), e.tombstone, tuple(sorted(e.clock.to_dict().items()))) for k, e in s._entries.items())
        )

    return Adapter(
        new=lambda r: GossipState(f"n{r}"),
        apply=apply,
        merge=lambda a, b: a.merge(b),
        dump=lambda s: copy.deepcopy(s.to_dict()),
        load=lambda d, r: GossipState.from_dict(copy.deepcopy(d)),
        view=view,
    )


ADAPTERS: Dict[str, Adapter] = {
    "orset": _orset(),
    "lwwmap": _lwwmap(),
    "agentstate": _agentstate(),
    "trustagentstate": _trustagentstate(),
    "gossip": _gossip(),
}


def view(subsystem: str, state) -> Any:
    """The observable, comparable form of a state (what a reader of the replica can see)."""
    return ADAPTERS[subsystem].view(state)


# ---------------------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------------------

@dataclass
class Run:
    history: History
    states: List[Any]
    snapshots: List[List[dict]]
    #: tags created by adds, and tags observed and removed (ORSet and TrustAgentState oracle)
    added: Dict[str, Any] = field(default_factory=dict)
    removed: set = field(default_factory=set)
    delivered: int = 0
    dropped: int = 0


def _timestamp(history: History, step: int, replica: int) -> float:
    return float(step) + float(history.skews[replica])


def _tags_of(subsystem: str, state, key: str) -> set:
    if subsystem == "orset":
        return set(state._elements.get(key, ()))
    if subsystem == "trustagentstate":
        return set(state._versions(key))
    return set()


def run_history(history: History) -> Run:
    """Execute a history. Returns the final per-replica states and the oracle bookkeeping."""
    ad = ADAPTERS[history.subsystem]
    states = [ad.new(r) for r in range(history.replicas)]
    snapshots: List[List[dict]] = [[ad.dump(s)] for s in states]
    run = Run(history, states, snapshots)
    groups: Tuple[tuple, ...] = ()

    def same_side(a: int, b: int) -> bool:
        return not groups or any(a in g and b in g for g in groups)

    def deliver(src: int, dst: int, snap: dict) -> None:
        states[dst] = ad.merge(states[dst], ad.load(snap, dst))
        snapshots[dst].append(ad.dump(states[dst]))
        run.delivered += 1

    for step, ev in enumerate(history.events):
        kind = ev[0]
        if kind == "op":
            _, r, op, key = ev
            before = _tags_of(history.subsystem, states[r], key)
            ts = _timestamp(history, step, r)
            states[r] = ad.apply(states[r], r, op, key, step, ts)
            after = _tags_of(history.subsystem, states[r], key)
            if history.subsystem in ("orset", "trustagentstate"):
                for tag in after - before:
                    run.added[tag] = key
                run.removed |= before - after  # tags this replica observed and then dropped
            snapshots[r].append(ad.dump(states[r]))
        elif kind == "send":
            _, src, dst, mode, age = ev
            if mode == "drop" or not same_side(src, dst):
                run.dropped += 1
                continue
            log = snapshots[src]
            snap = log[max(0, len(log) - 1 - age)] if mode == "stale" else log[-1]
            deliver(src, dst, snap)
            if mode == "duplicate":
                deliver(src, dst, snap)
        elif kind == "restart":
            r = ev[1]
            states[r] = ad.load(ad.dump(states[r]), r)
        elif kind == "partition":
            groups = ev[1]
        elif kind == "heal":
            groups = ()
    return run


def heal(subsystem: str, states: List[Any], rounds: int = 2) -> List[Any]:
    """Every replica receives every other replica's current state, ``rounds`` times."""
    ad = ADAPTERS[subsystem]
    states = list(states)
    for _ in range(rounds):
        for i in range(len(states)):
            for j in range(len(states)):
                if i != j:
                    states[i] = ad.merge(states[i], ad.load(ad.dump(states[j]), i))
    return states


def assert_converged(subsystem: str, states: List[Any], history: History) -> None:
    views = [view(subsystem, s) for s in states]
    assert all(v == views[0] for v in views), f"replicas disagree after heal: {views}; {describe(history)}"


def orset_oracle(run: Run) -> tuple:
    """Elements an observed-remove set must hold once every replica has seen everything:
    an element is live iff some add of it was never observed and removed."""
    live = {key for tag, key in run.added.items() if tag not in run.removed}
    return tuple(sorted(live))
