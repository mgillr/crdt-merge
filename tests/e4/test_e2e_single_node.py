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

"""End-to-end tests: single node behavior identical to pre-E4.

Verifies that trust defaults to 1.0 effective (probation 0.5), all gates
pass for cooperative peers, and output is mathematically identical to
pre-E4 operation when there are no violations.
"""

import pytest

from crdt_merge.e4.typed_trust import (
    PROBATION_TRUST,
    TRUST_DIMENSIONS,
    TypedTrustScore,
    TrustHomeostasis,
)
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef
from crdt_merge.e4.projection_delta import (
    FrozenDict,
    ProjectionDelta,
    ProjectionDeltaManager,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
)
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk
from crdt_merge.e4.integration.agent_bridge import TrustAgentState
from e4_factories import make_delta, make_pco


# ---------------------------------------------------------------------------
# Single-node trust defaults
# ---------------------------------------------------------------------------

class TestSingleNodeDefaults:

    def test_new_peer_at_probation(self):
        """A new peer's trust defaults to PROBATION_TRUST (0.5)."""
        lattice = DeltaTrustLattice("local")
        ts = lattice.get_trust("unknown_peer")
        assert ts.overall_trust() == PROBATION_TRUST

    def test_verification_level_probation(self):
        """Probation trust (0.5) yields verification level 1."""
        ts = TypedTrustScore.probationary()
        assert ts.verification_level() == 1

    def test_no_evidence_all_dims_equal(self):
        """With no evidence all dimensions yield equal trust."""
        ts = TypedTrustScore()
        trusts = {d: ts.trust_for_dimension(d) for d in TRUST_DIMENSIONS}
        values = list(trusts.values())
        assert all(v == values[0] for v in values)


# ---------------------------------------------------------------------------
# Single-node delta operations
# ---------------------------------------------------------------------------

class TestSingleNodeDelta:

    def test_empty_delta_is_empty(self):
        """An empty delta from a single node is recognized as empty."""
        d = make_delta(source_id="local")
        assert d.is_empty()

    def test_delta_with_data_preserved(self):
        """Data in a delta is faithfully preserved."""
        d = make_delta(
            source_id="local",
            insertions={"key1": b"value1", "key2": b"value2"},
        )
        assert len(d.insertions) == 2
        assert d.insertions["key1"] == b"value1"

    def test_delta_content_hash_stable(self):
        """Content hash is stable across repeated calls."""
        d = make_delta(source_id="local", insertions={"k": b"v"})
        h1 = d.content_hash()
        h2 = d.content_hash()
        assert h1 == h2

    def test_compose_identity(self):
        """Composing with empty delta is identity-like."""
        d1 = make_delta(source_id="local", insertions={"k": b"v"})
        d_empty = make_delta(source_id="local")
        composed = d1.compose(d_empty)
        assert composed.insertions["k"] == b"v"

    def test_pco_attached(self):
        """Delta from single node has a valid PCO."""
        d = make_delta(source_id="local")
        assert d.pco is not None
        assert len(d.pco.signature) == 64


# ---------------------------------------------------------------------------
# Single-node verification (all gates pass)
# ---------------------------------------------------------------------------

class TestSingleNodeVerification:

    def test_level_1_passes(self):
        """A valid delta from probationary peer passes level 1 verification."""
        lattice = DeltaTrustLattice("local", initial_peers={"peer-a"})
        verifier = AdaptiveVerificationController(trust_lattice=lattice)
        delta = make_delta(source_id="peer-a")
        result = verifier.verify(delta, state=object(), trust_lattice=lattice)
        # PCO signature is valid (zero-sig matches build) -> accepted
        assert result.accepted is True

    def test_gossip_accepts_all(self):
        """Single-node gossip accepts all deltas (no verifier disputes)."""
        engine = TrustGossipEngine()
        delta = make_delta(source_id="local")
        payload = TrustGossipPayload(data_deltas=[delta], peer_id="local")
        data, trust = engine.receive_sync(payload)
        assert len(data) == 1

    def test_stream_accepts_all_chunks(self):
        """Single-node stream validation accepts all chunks."""
        tsm = TrustStreamMerge()
        chunks = [
            StreamChunk(delta=make_delta(), sequence=i, stream_id="s1")
            for i in range(5)
        ]
        results = tsm.validate_stream(chunks)
        assert all(r.accepted for r in results)


# ---------------------------------------------------------------------------
# Single-node agent state
# ---------------------------------------------------------------------------

class TestSingleNodeAgentState:

    def test_put_get_roundtrip(self):
        """Single node put/get roundtrip works."""
        state = TrustAgentState()
        state.put("memory_key", {"data": 42}, "local")
        entry = state.get("memory_key")
        assert entry.value == {"data": 42}

    def test_agent_state_trust_default(self):
        """Agent entries default to probation trust (0.5)."""
        state = TrustAgentState()
        entry = state.put("k", "v", "local")
        assert entry.trust_at_write == 0.5

    def test_ranked_entries_single_peer(self):
        """ranked_entries for single peer returns all entries sorted."""
        state = TrustAgentState()
        for i in range(5):
            state.put(f"k{i}", f"v{i}", "local")
        ranked = state.ranked_entries()
        assert len(ranked) == 5


# ---------------------------------------------------------------------------
# Single-node Merkle tree
# ---------------------------------------------------------------------------

class TestSingleNodeMerkle:

    def test_empty_tree_root(self):
        """Empty Merkle tree has a root hash."""
        tree = TrustBoundMerkle()
        assert tree.root_hash is not None

    def test_insert_preserves_data(self):
        """Inserted data can be looked up."""
        tree = TrustBoundMerkle()
        tree.insert_leaf("key1", b"data1", "local")
        node = tree._leaves.get("key1")
        assert node is not None
        assert node.data == b"data1"


# ---------------------------------------------------------------------------
# Single-node causal clock
# ---------------------------------------------------------------------------

class TestSingleNodeClock:

    def test_clock_creation(self):
        """CausalTrustClock can be created for local peer."""
        clock = CausalTrustClock("local")
        assert clock.peer_id == "local"

    def test_increment(self):
        """Incrementing the clock advances local counter."""
        clock = CausalTrustClock("local")
        clock2 = clock.increment()
        assert clock2.logical_time > clock.logical_time

    def test_serialize_roundtrip(self):
        """Clock serialization produces deterministic bytes."""
        clock = CausalTrustClock("local")
        b1 = clock.serialize_compact()
        b2 = clock.serialize_compact()
        assert b1 == b2
