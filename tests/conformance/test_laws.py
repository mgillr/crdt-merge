"""CRDT law tests (WP02-02): commutativity, associativity and idempotency of merge.

Each law is checked on states reached by random operation histories (see history.py), not on a
few hand-built states. The five subsystems under test are ORSet, LWWMap, AgentState,
TrustAgentState and gossip state. A failure prints the seed that regenerates the history.
"""
import os
import sys

import pytest
from hypothesis import given

sys.path.insert(0, os.path.dirname(__file__))

from history import (  # noqa: E402
    ADAPTERS,
    conformance_settings,
    describe,
    histories,
    run_history,
    view,
)

# subsystem key -> the name this suite uses for it
SUBSYSTEM_NAMES = {
    "orset": "ORSet",
    "lwwmap": "LWWMap",
    "agentstate": "AgentState",
    "trustagentstate": "TrustAgentState",
    "gossip": "gossip",
}
SUBSYSTEMS = list(SUBSYSTEM_NAMES)


def _three(h):
    states = run_history(h).states
    return states[0], states[1], states[2]


@pytest.mark.parametrize("subsystem", SUBSYSTEMS, ids=[SUBSYSTEM_NAMES[s] for s in SUBSYSTEMS])
class TestMergeLaws:
    def test_commutativity(self, subsystem):
        merge = ADAPTERS[subsystem].merge

        @conformance_settings()
        @given(histories(subsystem, min_replicas=3))
        def check(h):
            a, b, _ = _three(h)
            assert view(subsystem, merge(a, b)) == view(subsystem, merge(b, a)), describe(h)

        check()

    def test_associativity(self, subsystem):
        merge = ADAPTERS[subsystem].merge

        @conformance_settings()
        @given(histories(subsystem, min_replicas=3))
        def check(h):
            a, b, c = _three(h)
            left = view(subsystem, merge(merge(a, b), c))
            right = view(subsystem, merge(a, merge(b, c)))
            assert left == right, describe(h)

        check()

    def test_idempotency(self, subsystem):
        merge = ADAPTERS[subsystem].merge

        @conformance_settings()
        @given(histories(subsystem, min_replicas=3))
        def check(h):
            a, b, _ = _three(h)
            assert view(subsystem, merge(a, a)) == view(subsystem, a), describe(h)
            ab = merge(a, b)
            assert view(subsystem, merge(ab, b)) == view(subsystem, ab), describe(h)
            assert view(subsystem, merge(ab, a)) == view(subsystem, ab), describe(h)

        check()

    def test_merge_leaves_its_inputs_unchanged(self, subsystem):
        merge = ADAPTERS[subsystem].merge

        @conformance_settings()
        @given(histories(subsystem, min_replicas=3))
        def check(h):
            a, b, _ = _three(h)
            before = (view(subsystem, a), view(subsystem, b))
            merge(a, b)
            assert (view(subsystem, a), view(subsystem, b)) == before, describe(h)

        check()
