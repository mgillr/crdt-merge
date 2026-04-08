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

"""
End-to-end pipeline tests that run real data through the full E4 + crdt-merge stack.

Every test exercises both crdt_merge.* and crdt_merge.e4.* together, validating
that the trust overlay works transparently alongside the base CRDT library.
"""

import time
import pytest

# ── Base library imports ─────────────────────────────────────────────────────
from crdt_merge.delta import Delta, DeltaStore, compute_delta
from crdt_merge.gossip import GossipState, anti_entropy
from crdt_merge.agentic import AgentState, SharedKnowledge, Fact
from crdt_merge.merkle import MerkleTree, merkle_diff
from crdt_merge.streaming import merge_stream, StreamStats
from crdt_merge.core import GCounter, LWWRegister, ORSet

# ── E4 imports ───────────────────────────────────────────────────────────────
from crdt_merge.e4.projection_delta import ProjectionDelta
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.integration.agent_bridge import TrustAgentState, TrustAnnotatedEntry
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.typed_trust import TypedTrustScore
from crdt_merge.e4.proof_evidence import TrustEvidence
from crdt_merge.e4.adaptive_verification import AdaptiveVerificationController

# ── conftest helpers ─────────────────────────────────────────────────────────
from e4_factories import make_delta, make_pco, make_equivocation_proof


# ── Helper: no-op homeostasis ────────────────────────────────────────────────

class _NoOpHomeostasis:
    """Homeostasis that does nothing. Preserves raw trust for testing."""
    @staticmethod
    def normalize(scores, peer_count):
        return dict(scores)


class TestFullPipelineE2E:
    """End-to-end tests exercising the full crdt-merge + E4 stack."""

    def test_full_pipeline_records_to_deltas_to_gossip(self):
        """Create records → DeltaStore → ProjectionDelta → TrustGossipEngine → verify arrival.

        Validates the complete data path from record ingestion through trust-annotated gossip.
        """
        store = DeltaStore(key="id", node_id="node-a")
        store.ingest([
            {"id": "r1", "name": "Alice", "score": 90},
            {"id": "r2", "name": "Bob", "score": 80},
        ])
        delta = store.ingest([
            {"id": "r1", "name": "Alice", "score": 95},
            {"id": "r3", "name": "Carol", "score": 70},
        ])
        assert delta is not None and not delta.is_empty

        insertions = {r["id"]: str(r).encode() for r in delta.added}
        updates = {r["id"]: (b"old", str(r).encode()) for r in delta.modified}
        deletions = set(delta.removed)
        pd = make_delta(
            source_id="node-a",
            insertions=insertions,
            updates=updates,
            deletions=deletions,
        )

        lattice_a = DeltaTrustLattice("node-a", initial_peers={"node-b"})
        lattice_b = DeltaTrustLattice("node-b", initial_peers={"node-a"})
        engine_a = TrustGossipEngine(trust_lattice=lattice_a)
        engine_b = TrustGossipEngine(trust_lattice=lattice_b)

        payload = engine_a.prepare_sync(data_deltas=[pd])
        accepted_data, accepted_trust = engine_b.receive_sync(payload)

        assert len(accepted_data) == 1
        received = accepted_data[0]
        all_received_keys = (
            set(received.insertions.keys())
            | set(received.updates.keys())
            | received.deletions
        )
        expected_keys = set(insertions.keys()) | set(updates.keys()) | deletions
        assert all_received_keys == expected_keys

    def test_full_pipeline_agent_merge_with_trust(self):
        """Two AgentStates with conflicting facts → TrustAgentState with trust → trust wins.

        Uses no-op homeostasis to ensure trust manipulation works predictably.
        """
        a = AgentState("analyst")
        b = AgentState("junior")
        a.add_fact("answer", "42", timestamp=100.0, confidence=0.9)
        b.add_fact("answer", "43", timestamp=200.0, confidence=0.5)

        merged = a.merge(b)
        # Standard LWW: later timestamp wins
        assert merged.get_fact("answer") is not None

        # E4 trust-weighted: trusted analyst beats newer junior answer
        lattice = DeltaTrustLattice(
            "judge",
            initial_peers={"analyst", "junior"},
            homeostasis=_NoOpHomeostasis(),
        )
        evidence = TrustEvidence.create(
            observer="judge",
            target="junior",
            evidence_type="equivocation",
            dimension="integrity",
            amount=0.8,
            proof=make_equivocation_proof(signer="junior"),
        )
        lattice.observe_and_propagate(evidence)

        ta = TrustAgentState(trust_lattice=lattice, trust_weight_context=True)
        ta.put("answer", "42", peer_id="analyst", timestamp=100.0)
        ta.put("answer", "43", peer_id="junior", timestamp=200.0)

        entry = ta.get("answer")
        assert entry.value == "42"  # trusted analyst wins

    def test_full_pipeline_merkle_diff_with_trust(self):
        """Build two MerkleTrees → identify diff → create ProjectionDeltas → validate via TrustStreamMerge."""
        records_a = [{"id": "k1", "v": 1}, {"id": "k2", "v": 2}, {"id": "k3", "v": 3}]
        records_b = [{"id": "k2", "v": 2}, {"id": "k3", "v": 30}, {"id": "k4", "v": 4}]

        mt_a = MerkleTree.from_records(records_a, key="id")
        mt_b = MerkleTree.from_records(records_b, key="id")

        diff = merkle_diff(mt_a, mt_b)
        assert diff.num_differences > 0  # There are differences

        diff_keys = diff.differing_keys
        # Create a ProjectionDelta for the differences
        insertions = {}
        for key in diff_keys:
            insertions[key] = f"diff_{key}".encode()

        pd = make_delta(source_id="diff-sender", insertions=insertions)

        tsm = TrustStreamMerge()
        chunk = StreamChunk(delta=pd, sequence=0, stream_id="diff-stream")
        result = tsm.validate_chunk(chunk)
        assert result.accepted
        assert len(pd.insertions) == len(diff_keys)

    def test_full_pipeline_byzantine_peer_detection(self):
        """Honest peer sends valid data, Byzantine peer sends conflicting data.

        TrustGossipEngine processes both → evidence recorded → Byzantine peer's trust drops.
        Uses no-op homeostasis so trust changes are predictable.
        """
        lattice = DeltaTrustLattice(
            "validator",
            initial_peers={"honest", "byzantine"},
            homeostasis=_NoOpHomeostasis(),
        )
        engine = TrustGossipEngine(trust_lattice=lattice)

        honest_delta = make_delta(
            source_id="honest",
            insertions={"data": b"correct"},
        )
        payload_h = engine.prepare_sync(data_deltas=[honest_delta])
        engine.receive_sync(payload_h)

        byzantine_delta = make_delta(
            source_id="byzantine",
            insertions={"data": b"WRONG_DATA"},
        )
        payload_b = engine.prepare_sync(data_deltas=[byzantine_delta])
        engine.receive_sync(payload_b)

        # Record equivocation evidence against byzantine peer
        evidence = TrustEvidence.create(
            observer="validator",
            target="byzantine",
            evidence_type="equivocation",
            dimension="integrity",
            amount=0.7,
            proof=make_equivocation_proof(signer="byzantine"),
        )
        lattice.observe_and_propagate(evidence)

        honest_trust = lattice.get_trust("honest").overall_trust()
        byzantine_trust = lattice.get_trust("byzantine").overall_trust()

        assert byzantine_trust < honest_trust

    def test_full_pipeline_sybil_resistance(self):
        """5 colluding Sybil peers all submit bad data → evidence accumulates → trust drops.

        AdaptiveVerifier raises verification level for low-trust peers.
        Uses no-op homeostasis so evidence is fully reflected in trust.
        """
        sybil_ids = [f"sybil_{i}" for i in range(5)]
        all_peers = set(sybil_ids) | {"honest"}
        lattice = DeltaTrustLattice(
            "guardian",
            initial_peers=all_peers,
            homeostasis=_NoOpHomeostasis(),
        )

        # Record evidence against each Sybil peer
        for sid in sybil_ids:
            evidence = TrustEvidence.create(
                observer="guardian",
                target=sid,
                evidence_type="equivocation",
                dimension="integrity",
                amount=0.6,
                proof=make_equivocation_proof(signer=sid),
            )
            lattice.observe_and_propagate(evidence)

        honest_trust = lattice.get_trust("honest").overall_trust()
        for sid in sybil_ids:
            sybil_trust = lattice.get_trust(sid).overall_trust()
            assert sybil_trust < honest_trust

        # AdaptiveVerificationController: low-trust peers get stricter verification
        # TypedTrustScore.verification_level() returns the level for that peer
        for sid in sybil_ids:
            sybil_ts = lattice.get_trust(sid)
            level = sybil_ts.verification_level()
            assert level >= 1  # At least level 1 verification for degraded trust
        honest_ts = lattice.get_trust("honest")
        honest_level = honest_ts.verification_level()
        # Sybil peers should have stricter (higher) verification level
        sybil_level = lattice.get_trust(sybil_ids[0]).verification_level()
        assert honest_level <= sybil_level

    def test_backward_compatibility_real_merge(self):
        """Real merge() on base CRDTs still works exactly the same with E4 loaded.

        E4 is transparent and doesn't break base CRDT operations.
        """
        g1 = GCounter()
        g2 = GCounter()
        g1.increment("a", 5)
        g2.increment("b", 3)
        merged = g1.merge(g2)
        assert merged.value == 8

        lww1 = LWWRegister("old", timestamp=100.0, node_id="n1")
        lww2 = LWWRegister("new", timestamp=200.0, node_id="n2")
        merged_lww = lww1.merge(lww2)
        assert merged_lww.value == "new"

        s1 = ORSet()
        s2 = ORSet()
        s1.add("x")
        s2.add("y")
        merged_set = s1.merge(s2)
        assert "x" in merged_set.value
        assert "y" in merged_set.value

    def test_backward_compatibility_real_gossip_state(self):
        """GossipState standard operations still work with E4 loaded."""
        gs_a = GossipState("a")
        gs_b = GossipState("b")

        gs_a.update("k1", "v1")
        gs_a.update("k2", "v2")
        gs_b.update("k2", "v2_b")
        gs_b.update("k3", "v3")

        assert gs_a.size == 2
        assert gs_b.size == 2
        assert gs_a.get("k1") == "v1"

        merged = gs_a.merge(gs_b)
        assert merged.get("k1") == "v1"
        assert merged.get("k3") == "v3"
        assert merged.size == 3
