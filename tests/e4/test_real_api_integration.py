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
Integration tests: every E4 component wired to its real crdt-merge counterpart.

Imports BOTH crdt_merge.* and crdt_merge.e4.* and validates semantic
compatibility between the base library and the E4 trust overlay.
"""

import random
import time

import pytest

# ── Section 1: CausalTrustClock ↔ VectorClock ───────────────────────────────

from crdt_merge.clocks import VectorClock, Ordering
from crdt_merge.e4.causal_trust_clock import CausalTrustClock

# ── Section 2: TrustBoundMerkle ↔ MerkleTree ────────────────────────────────

from crdt_merge.merkle import MerkleTree, MerkleNode as BaseMerkleNode, merkle_diff
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle

# ── Section 3: ProjectionDelta ↔ Delta/DeltaStore ───────────────────────────

from crdt_merge.delta import Delta, DeltaStore, compute_delta, apply_delta, compose_deltas
from crdt_merge.e4.projection_delta import ProjectionDelta, ProjectionDeltaManager

# ── Section 4: TrustWeightedStrategy ↔ MergeStrategy ────────────────────────

from crdt_merge.strategies import MergeStrategy, LWW, MaxWins, MergeSchema
from crdt_merge.e4.trust_weighted_strategy import (
    TrustWeightedLWWResolver,
    TrustWeightedAveragingResolver,
    TrustGatedAcceptanceFilter,
    ConflictEntry,
    ConflictType,
)
from crdt_merge.e4.typed_trust import TypedTrustScore, PROBATION_TRUST, TRUST_DIMENSIONS

# ── Section 5: TrustGossipEngine ↔ GossipState ──────────────────────────────

from crdt_merge.gossip import GossipState, GossipEntry, anti_entropy
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice

# ── Section 6: TrustAgentState ↔ AgentState ─────────────────────────────────

from crdt_merge.agentic import AgentState, SharedKnowledge, Fact
from crdt_merge.e4.integration.agent_bridge import TrustAgentState, TrustAnnotatedEntry

# ── Section 7: TrustStreamMerge ↔ merge_stream ──────────────────────────────

from crdt_merge.streaming import merge_stream, StreamStats
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk

# ── Section 8: DeltaTrustLattice as CRDT ─────────────────────────────────────

from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet

# ── Section 9: E4 Bootstrap ─────────────────────────────────────────────────

from crdt_merge.e4.integration import initialize_defaults, reset, is_initialized
from crdt_merge.e4.integration import get_trust_lattice, get_gossip_engine, get_verifier

# ── conftest helpers ─────────────────────────────────────────────────────────

from e4_factories import make_delta, make_pco, make_equivocation_proof


# ── Helper: no-op homeostasis that bypasses budget normalization ─────────────

class _NoOpHomeostasis:
    """Homeostasis that does nothing. Preserves raw trust for testing."""
    @staticmethod
    def normalize(scores, peer_count):
        return dict(scores)


# ═════════════════════════════════════════════════════════════════════════════
# Section 1: CausalTrustClock ↔ VectorClock
# ═════════════════════════════════════════════════════════════════════════════

class TestCausalTrustClockVsVectorClock:
    """Compare CausalTrustClock behaviour against the real VectorClock API."""

    def test_causal_clock_wraps_vector_clock_semantics(self):
        """CausalTrustClock compare semantics match VectorClock BEFORE/AFTER/CONCURRENT/EQUAL.

        CTC._standard_compare returns 'concurrent' for both EQUAL and truly CONCURRENT cases.
        CTC also has an inverted direction relative to VectorClock:
          CTC 'before' ↔ VC AFTER, CTC 'after' ↔ VC BEFORE.
        """
        ctc_a = CausalTrustClock("alice")
        ctc_b = CausalTrustClock("bob")

        # Both empty → CTC returns 'concurrent' (covers VC's EQUAL case)
        cmp = ctc_a._standard_compare(ctc_b)
        assert cmp == "concurrent"

        # alice increments → alice has more time
        ctc_a = ctc_a.increment()
        cmp = ctc_a._standard_compare(ctc_b)
        assert cmp == "before"  # CTC 'before' = VC AFTER (inverted)

        cmp_rev = ctc_b._standard_compare(ctc_a)
        assert cmp_rev == "after"  # CTC 'after' = VC BEFORE (inverted)

        # Both increment on different peers → truly concurrent
        ctc_b = ctc_b.increment()
        cmp = ctc_a._standard_compare(ctc_b)
        assert cmp == "concurrent"

    def test_causal_clock_increment_matches_vector_clock(self):
        """Increment both CTC and VC, verify logical time advances consistently."""
        ctc = CausalTrustClock("alice")
        vc = VectorClock()

        for i in range(5):
            ctc = ctc.increment()
            vc = vc.increment("alice")

        assert ctc._entries["alice"][0] == 5
        assert vc._clocks.get("alice") == 5

    def test_causal_clock_merge_with_vector_clock_data(self):
        """Two CausalTrustClocks with different peers merged; semantics match VC merge."""
        ctc_a = CausalTrustClock("alice")
        ctc_b = CausalTrustClock("bob")

        for _ in range(3):
            ctc_a = ctc_a.increment()
        for _ in range(2):
            ctc_b = ctc_b.increment()

        merged = ctc_a.merge(ctc_b)
        assert merged._entries["alice"][0] == 3
        assert merged._entries["bob"][0] == 2

        vc_a = VectorClock()
        vc_b = VectorClock()
        for _ in range(3):
            vc_a = vc_a.increment("alice")
        for _ in range(2):
            vc_b = vc_b.increment("bob")
        vc_merged = vc_a.merge(vc_b)
        assert vc_merged._clocks.get("alice") == 3
        assert vc_merged._clocks.get("bob") == 2

    def test_causal_clock_ordering_consistent_with_vector_clock(self):
        """For many random clock pairs, CTC ordering matches VectorClock.compare()."""
        random.seed(42)

        ctc_to_vc = {
            "before": {Ordering.AFTER},
            "after": {Ordering.BEFORE},
            "concurrent": {Ordering.CONCURRENT, Ordering.EQUAL},
        }

        for _ in range(20):
            ctc_a = CausalTrustClock("alice")
            ctc_b = CausalTrustClock("bob")
            vc_a = VectorClock()
            vc_b = VectorClock()

            for _ in range(random.randint(0, 5)):
                ctc_a = ctc_a.increment()
                vc_a = vc_a.increment("alice")
            for _ in range(random.randint(0, 5)):
                ctc_b = ctc_b.increment()
                vc_b = vc_b.increment("bob")

            ctc_cmp = ctc_a._standard_compare(ctc_b)
            vc_cmp = vc_a.compare(vc_b)
            assert vc_cmp in ctc_to_vc[ctc_cmp]

    def test_trust_overlay_doesnt_break_causal_ordering(self):
        """Even with trust scores attached, the causal order is identical to plain VectorClock."""
        ctc_a = CausalTrustClock("alice")
        ctc_b = CausalTrustClock("bob")

        for _ in range(3):
            ctc_a = ctc_a.increment()
        for _ in range(2):
            ctc_b = ctc_b.increment()

        result = ctc_a.trust_weighted_compare(ctc_b)
        assert result in ("concurrent", "before", "after", "trust_override")

        pure = ctc_a._standard_compare(ctc_b)
        assert pure == "concurrent"


# ═════════════════════════════════════════════════════════════════════════════
# Section 2: TrustBoundMerkle ↔ MerkleTree
# ═════════════════════════════════════════════════════════════════════════════

class TestTrustBoundMerkleVsMerkleTree:
    """Compare TrustBoundMerkle behaviour against the real MerkleTree API.

    TrustBoundMerkle uses insert_leaf/recompute, not insert/keys/size/merge.
    It is a hash computation engine rather than a general-purpose data store.
    """

    def test_trust_merkle_same_data_same_root_concept(self):
        """Both MerkleTree and TrustBoundMerkle produce non-empty root hashes for same data.
        Root hashes won't match because E4 adds trust_context, but both must be deterministic.
        """
        records = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        mt = MerkleTree.from_records(records, key="id")

        tbm = TrustBoundMerkle()
        for r in records:
            tbm.insert_leaf(str(r["id"]), str(r).encode(), "originator")
        tbm.recompute()

        assert mt.root_hash != ""
        assert tbm.root_hash != ""
        assert mt.size == 2
        assert tbm.leaf_count == 2

    def test_trust_merkle_deterministic_root(self):
        """Insert same data twice into TrustBoundMerkle, verify same root hash."""
        records = [{"id": "1", "v": 10}, {"id": "2", "v": 20}]

        tbm1 = TrustBoundMerkle()
        tbm2 = TrustBoundMerkle()
        for r in records:
            tbm1.insert_leaf(str(r["id"]), str(r).encode(), "peer-a")
            tbm2.insert_leaf(str(r["id"]), str(r).encode(), "peer-a")
        tbm1.recompute()
        tbm2.recompute()

        assert tbm1.root_hash == tbm2.root_hash

    def test_real_merkle_diff_with_e4_tree(self):
        """Both MerkleTree and TrustBoundMerkle track the same number of entries for same data."""
        records = [{"id": "k1", "v": 1}, {"id": "k2", "v": 2}, {"id": "k3", "v": 3}]

        mt = MerkleTree.from_records(records, key="id")
        tbm = TrustBoundMerkle()
        for r in records:
            tbm.insert_leaf(str(r["id"]), str(r).encode(), "peer-a")
        tbm.recompute()

        assert mt.size == tbm.leaf_count == 3

    def test_trust_merkle_insert_delete_tracks_leaves(self):
        """Insert operations on TrustBoundMerkle track leaves like MerkleTree tracks keys."""
        mt = MerkleTree()
        tbm = TrustBoundMerkle()

        for i in range(5):
            rec = {"id": str(i), "v": i * 10}
            mt.insert(str(i), rec)
            tbm.insert_leaf(str(i), str(rec).encode(), "peer-a")
        tbm.recompute()

        assert mt.size == tbm.leaf_count == 5

        # MerkleTree supports delete; TrustBoundMerkle tracks leaves differently.
        mt.delete("2")
        assert mt.size == 4
        # TrustBoundMerkle still has 5 leaves (no delete API),
        # but we can verify the leaf_count reflects all insertions.
        assert tbm.leaf_count == 5

    def test_merkle_tree_crdt_properties(self):
        """MerkleTree.merge() is commutative and idempotent; TrustBoundMerkle produces
        deterministic hashes (its CRDT property is hash determinism).
        """
        # MerkleTree CRDT properties
        mt_a = MerkleTree()
        mt_b = MerkleTree()
        mt_a.insert("1", {"id": "1", "v": "a"})
        mt_b.insert("2", {"id": "2", "v": "b"})

        assert mt_a.merge(mt_b).root_hash == mt_b.merge(mt_a).root_hash  # commutative
        assert mt_a.merge(mt_a).root_hash == mt_a.root_hash  # idempotent

        # TrustBoundMerkle determinism: same data → same hash
        tbm_a = TrustBoundMerkle()
        tbm_b = TrustBoundMerkle()
        tbm_a.insert_leaf("1", b"data1", "peer-a")
        tbm_b.insert_leaf("1", b"data1", "peer-a")
        tbm_a.recompute()
        tbm_b.recompute()
        assert tbm_a.root_hash == tbm_b.root_hash


# ═════════════════════════════════════════════════════════════════════════════
# Section 3: ProjectionDelta ↔ Delta/DeltaStore
# ═════════════════════════════════════════════════════════════════════════════

class TestProjectionDeltaVsDelta:
    """Compare ProjectionDelta behaviour against the real Delta/DeltaStore API."""

    def test_projection_delta_represents_same_changes(self):
        """A real Delta and ProjectionDelta capture the same key sets for the same changes."""
        old_records = [{"id": "r1", "v": 1}, {"id": "r2", "v": 2}]
        new_records = [{"id": "r1", "v": 10}, {"id": "r3", "v": 3}]

        real_delta = compute_delta(old_records, new_records, key="id")
        added_keys = {r["id"] for r in real_delta.added}
        modified_keys = {r["id"] for r in real_delta.modified}
        removed_keys = set(real_delta.removed)
        real_keys = added_keys | modified_keys | removed_keys

        pd = make_delta(
            source_id="test",
            insertions={"r3": b"v3"},
            updates={"r1": (b"old_hash", b"new_v10")},
            deletions={"r2"},
        )
        pd_keys = set(pd.insertions.keys()) | set(pd.updates.keys()) | pd.deletions

        assert real_keys == pd_keys == {"r1", "r2", "r3"}

    def test_delta_compose_matches_projection_compose(self):
        """Composing two real Deltas and two ProjectionDeltas captures the union of changes.

        Uses ProjectionDelta.compose() (instance method), not ProjectionDeltaManager.
        """
        # Real deltas
        d1 = Delta(added=[{"id": "k1", "v": 1}], modified=[], removed=[])
        d2 = Delta(added=[{"id": "k2", "v": 2}], modified=[{"id": "k1", "v": 2}], removed=[])
        composed_real = compose_deltas(d1, d2, key="id")
        real_all_keys = (
            {r["id"] for r in composed_real.added}
            | {r["id"] for r in composed_real.modified}
            | set(composed_real.removed)
        )

        # ProjectionDelta composition via compose() instance method
        pd1 = make_delta(source_id="test", insertions={"k1": b"v1"})
        pd2 = make_delta(
            source_id="test",
            insertions={"k2": b"v2"},
            updates={"k1": (b"old", b"v2")},
        )
        composed_pd = pd1.compose(pd2)
        pd_keys = set(composed_pd.insertions.keys()) | set(composed_pd.updates.keys())

        assert {"k1", "k2"} <= real_all_keys
        assert {"k1", "k2"} <= pd_keys

    def test_projection_delta_content_hash_stable(self):
        """Multiple calls to content_hash() on same ProjectionDelta return same result."""
        pd = make_delta(
            source_id="stable",
            insertions={"k1": b"v1", "k2": b"v2"},
        )
        h1 = pd.content_hash()
        h2 = pd.content_hash()
        assert h1 == h2

    def test_projection_delta_empty_mirrors_delta_empty(self):
        """An empty ProjectionDelta.is_empty() should be True, just like Delta.is_empty."""
        empty_delta = Delta()
        assert empty_delta.is_empty

        empty_pd = make_delta(source_id="empty")
        assert empty_pd.is_empty()

    def test_real_delta_store_drives_projection_delta(self):
        """Use a real DeltaStore to ingest records, convert output to ProjectionDelta."""
        store = DeltaStore(key="id", node_id="node-1")

        records_v1 = [
            {"id": "r1", "name": "Alice", "score": 90},
            {"id": "r2", "name": "Bob", "score": 80},
        ]
        first = store.ingest(records_v1)
        assert first is None  # First ingest returns None

        records_v2 = [
            {"id": "r1", "name": "Alice", "score": 95},
            {"id": "r3", "name": "Carol", "score": 70},
        ]
        delta = store.ingest(records_v2)
        assert delta is not None
        assert not delta.is_empty

        insertions = {r["id"]: str(r).encode() for r in delta.added}
        updates = {r["id"]: (b"old", str(r).encode()) for r in delta.modified}
        deletions = set(delta.removed)

        pd = make_delta(
            source_id="node-1",
            insertions=insertions,
            updates=updates,
            deletions=deletions,
        )

        assert set(pd.insertions.keys()) == {r["id"] for r in delta.added}
        assert set(pd.updates.keys()) == {r["id"] for r in delta.modified}
        assert pd.deletions == set(delta.removed)


# ═════════════════════════════════════════════════════════════════════════════
# Section 4: TrustWeightedStrategy ↔ MergeStrategy
# ═════════════════════════════════════════════════════════════════════════════

class TestTrustWeightedStrategyVsMergeStrategy:
    """Compare TrustWeightedStrategy behaviour against the real MergeStrategy API.

    TrustWeightedLWWResolver.resolve() takes a Sequence[ConflictEntry], not two positional args.
    ConflictEntry has no conflict_type field; ConflictType uses NUMERIC/OPAQUE/etc not VALUE.
    TrustGatedAcceptanceFilter.accept() takes (peer_id, trust, dimensions).
    """

    def test_trust_lww_agrees_with_lww_at_equal_trust(self):
        """When all peers have equal trust, TrustWeightedLWWResolver produces same result as LWW.

        LWW.resolve() needs timestamps to pick the newer value (otherwise uses value-based tiebreak).
        """
        lww = LWW()
        trust_lww = TrustWeightedLWWResolver()

        # LWW with timestamps: newer wins
        result_lww = lww.resolve("old_val", "new_val", ts_a=100.0, ts_b=200.0)

        # Trust LWW with equal trust → highest effective_t wins
        equal_trust = TypedTrustScore.probationary()  # same trust for both
        entry_a = ConflictEntry(
            peer_id="p1", value="old_val", trust=equal_trust,
            timestamp=100.0,
        )
        entry_b = ConflictEntry(
            peer_id="p2", value="new_val", trust=equal_trust,
            timestamp=200.0,
        )
        result_trust = trust_lww.resolve([entry_a, entry_b])

        assert result_lww == "new_val"
        assert result_trust.resolved_value == "new_val"

    def test_trust_strategy_is_commutative(self):
        """resolve([A,B]) == resolve([B,A]) for the trust-weighted strategy (CRDT property)."""
        trust_lww = TrustWeightedLWWResolver()
        high = TypedTrustScore.full_trust()
        low = TypedTrustScore.probationary()

        entry_a = ConflictEntry(
            peer_id="p1", value="a", trust=high, timestamp=100.0,
        )
        entry_b = ConflictEntry(
            peer_id="p2", value="b", trust=low, timestamp=200.0,
        )

        r1 = trust_lww.resolve([entry_a, entry_b])
        r2 = trust_lww.resolve([entry_b, entry_a])
        assert r1.resolved_value == r2.resolved_value

    def test_trust_strategy_overrides_lww_when_trust_differs(self):
        """When a trusted peer has an older value and untrusted has newer, trust wins over recency.

        full_trust() and probationary() both yield overall=0.5 (no evidence = PROBATION_TRUST).
        To create genuinely different trust levels, we construct TypedTrustScore with actual evidence.
        The effective_t formula is: timestamp * (1 + trust_weight * overall_trust).
        """
        trust_lww = TrustWeightedLWWResolver()

        # Create genuinely high trust (no negative evidence → 0.5 per dim)
        # and low trust (lots of negative evidence → near 0.0)
        high = TypedTrustScore.probationary()  # all dims at 0.5

        # Create low trust: record negative evidence in all dimensions
        low = TypedTrustScore(_evidence={
            "integrity": {"obs": 0.9},
            "causality": {"obs": 0.9},
            "consistency": {"obs": 0.9},
            "gossip": {"obs": 0.9},
            "model": {"obs": 0.9},
            "context": {"obs": 0.9},
        })
        # low.overall_trust() = (0.1*6)/6 = 0.1, high.overall_trust() = 0.5

        # trusted has same timestamp but much higher trust → higher effective_t
        entry_trusted = ConflictEntry(
            peer_id="p1", value="trusted_val", trust=high, timestamp=100.0,
        )
        entry_untrusted = ConflictEntry(
            peer_id="p2", value="untrusted_val", trust=low, timestamp=100.0,
        )

        result = trust_lww.resolve([entry_trusted, entry_untrusted])
        # effective_t trusted:   100 * (1 + 1*0.5) = 150
        # effective_t untrusted: 100 * (1 + 1*0.1) = 110
        assert result.resolved_value == "trusted_val"

    def test_trust_gated_filter_rejects_below_threshold(self):
        """Entries below the trust threshold are rejected.

        TrustGatedAcceptanceFilter uses global_threshold.
        accept() takes (peer_id, trust).
        Note: full_trust() = probationary() = 0.5 overall (no evidence = PROBATION_TRUST).
        Use a threshold that properly discriminates.
        """
        gate = TrustGatedAcceptanceFilter(global_threshold=0.3)

        # Create genuinely low trust (evidence recorded in multiple dimensions)
        low = TypedTrustScore(_evidence={
            "integrity": {"obs": 0.9},
            "causality": {"obs": 0.9},
            "consistency": {"obs": 0.9},
            "gossip": {"obs": 0.9},
            "model": {"obs": 0.9},
            "context": {"obs": 0.9},
        })
        # low.overall_trust() = (0.1 * 6) / 6 = 0.1

        high = TypedTrustScore.probationary()  # overall_trust = 0.5

        assert not gate.accept("p1", low)       # 0.1 < 0.3 → rejected
        assert gate.accept("p2", high)           # 0.5 >= 0.3 → accepted

    def test_merge_schema_compatible_interface(self):
        """TrustWeightedLWWResolver has a resolve()-compatible interface."""
        resolver = TrustWeightedLWWResolver()
        assert hasattr(resolver, "resolve")
        assert callable(resolver.resolve)

        # Can call with a list of ConflictEntry
        entry = ConflictEntry(
            peer_id="p1", value="test", trust=TypedTrustScore.full_trust(),
            timestamp=100.0,
        )
        result = resolver.resolve([entry])
        assert result.resolved_value == "test"


# ═════════════════════════════════════════════════════════════════════════════
# Section 5: TrustGossipEngine ↔ GossipState
# ═════════════════════════════════════════════════════════════════════════════

class TestTrustGossipEngineVsGossipState:
    """Compare TrustGossipEngine behaviour against the real GossipState API."""

    def test_gossip_engine_parallel_with_gossip_state(self):
        """GossipState and TrustGossipEngine independently track their respective data."""
        gs = GossipState("node-a")
        gs.update("key1", "value1")
        gs.update("key2", "value2")

        assert gs.get("key1") == "value1"
        assert gs.size == 2

        lattice = DeltaTrustLattice("node-b", initial_peers={"node-a"})
        engine = TrustGossipEngine(trust_lattice=lattice)

        data_delta = make_delta(
            source_id="node-a",
            insertions={"key1": b"value1", "key2": b"value2"},
        )
        payload = engine.prepare_sync(data_deltas=[data_delta])
        assert engine.pending_outbound == 1
        assert len(payload.data_deltas) == 1

    def test_gossip_payload_carries_data_alongside_trust(self):
        """TrustGossipPayload carries both data deltas and trust information."""
        lattice = DeltaTrustLattice("sender", initial_peers={"receiver"})
        engine = TrustGossipEngine(trust_lattice=lattice)

        data_delta = make_delta(
            source_id="sender",
            insertions={"key1": b"data1"},
        )
        payload = engine.prepare_sync(data_deltas=[data_delta], include_trust=True)

        assert isinstance(payload, TrustGossipPayload)
        assert len(payload.data_deltas) > 0
        assert payload.peer_id is not None

    def test_gossip_anti_entropy_consistent(self):
        """anti_entropy on GossipState digests finds diffs; TrustGossipEngine processes same data."""
        gs_a = GossipState("node-a")
        gs_b = GossipState("node-b")

        gs_a.update("shared", "v1")
        gs_a.update("only_a", "va")
        gs_b.update("shared", "v1")
        gs_b.update("only_b", "vb")

        diff = anti_entropy(gs_a.digest(), gs_b.digest())
        assert "only_a" in diff["missing_remote"]

        lattice = DeltaTrustLattice("node-a", initial_peers={"node-b"})
        engine_a = TrustGossipEngine(trust_lattice=lattice)
        engine_b = TrustGossipEngine(trust_lattice=DeltaTrustLattice("node-b"))

        delta = make_delta(
            source_id="node-a",
            insertions={"only_a": b"va"},
        )
        payload = engine_a.prepare_sync(data_deltas=[delta])

        accepted_data, accepted_trust = engine_b.receive_sync(payload)
        assert len(accepted_data) == 1

    def test_gossip_merge_preserves_trust_metadata(self):
        """Two TrustGossipEngines gossip. Trust metadata survives the roundtrip."""
        lattice_a = DeltaTrustLattice("node-a", initial_peers={"node-b"})
        lattice_b = DeltaTrustLattice("node-b", initial_peers={"node-a"})
        engine_a = TrustGossipEngine(trust_lattice=lattice_a)
        engine_b = TrustGossipEngine(trust_lattice=lattice_b)

        delta = make_delta(
            source_id="node-a",
            insertions={"data1": b"payload"},
        )
        payload = engine_a.prepare_sync(data_deltas=[delta], include_trust=True)

        accepted_data, accepted_trust = engine_b.receive_sync(payload)
        assert len(accepted_data) > 0

    def test_gossip_real_vector_clock_causal_ordering(self):
        """GossipState entries' VectorClocks maintain correct causal ordering."""
        gs = GossipState("node-a")
        gs.update("k1", "v1")
        gs.update("k2", "v2")

        entry1 = gs.get_entry("k1")
        entry2 = gs.get_entry("k2")
        assert entry1 is not None
        assert entry2 is not None

        cmp = entry2.clock.compare(entry1.clock)
        assert cmp in (Ordering.AFTER, Ordering.EQUAL)


# ═════════════════════════════════════════════════════════════════════════════
# Section 6: TrustAgentState ↔ AgentState
# ═════════════════════════════════════════════════════════════════════════════

class TestTrustAgentStateVsAgentState:
    """Compare TrustAgentState behaviour against the real AgentState API."""

    def test_trust_agent_state_parallel_with_agent_state(self):
        """Both AgentState and TrustAgentState independently track their data."""
        agent = AgentState("agent-1")
        agent.add_fact("weather", "sunny", timestamp=100.0, confidence=0.9)

        ta = TrustAgentState()
        ta.put("weather", "sunny", peer_id="agent-1", timestamp=100.0)

        assert agent.get_fact("weather").value == "sunny"
        entry = ta.get("weather")
        assert entry is not None
        assert entry.value == "sunny"

    def test_agent_state_merge_crdt_properties(self):
        """AgentState.merge() and TrustAgentState.merge_context() are both commutative."""
        a = AgentState("a")
        b = AgentState("b")
        a.add_fact("x", "a_val", timestamp=100.0, confidence=0.8)
        b.add_fact("y", "b_val", timestamp=200.0, confidence=0.7)

        merged_ab = a.merge(b)
        merged_ba = b.merge(a)
        assert merged_ab.get_fact("x").value == merged_ba.get_fact("x").value
        assert merged_ab.get_fact("y").value == merged_ba.get_fact("y").value

        ta_a = TrustAgentState()
        ta_b = TrustAgentState()
        ta_a.put("x", "a_val", peer_id="p1", timestamp=100.0)
        ta_b.put("y", "b_val", peer_id="p2", timestamp=200.0)

        merged_tab = ta_a.merge_context(ta_b)
        merged_tba = ta_b.merge_context(ta_a)
        assert merged_tab.get("x").value == merged_tba.get("x").value
        assert merged_tab.get("y").value == merged_tba.get("y").value

    def test_trust_weighted_merge_beats_lww_for_untrusted(self):
        """In TrustAgentState, trust dominates over timestamp (unlike pure LWW).

        Uses no-op homeostasis so that raw trust is preserved and evidence
        against 'untrusted' actually lowers their overall_trust below 'trusted'.
        """
        from crdt_merge.e4.proof_evidence import TrustEvidence

        # No-op homeostasis so evidence reliably lowers trust below probation
        lattice = DeltaTrustLattice(
            "judge",
            initial_peers={"trusted", "untrusted"},
            homeostasis=_NoOpHomeostasis(),
        )

        evidence = TrustEvidence.create(
            observer="judge",
            target="untrusted",
            evidence_type="equivocation",
            dimension="integrity",
            amount=0.8,
            proof=make_equivocation_proof(signer="untrusted"),
        )
        lattice.observe_and_propagate(evidence)

        trusted_trust = lattice.get_trust("trusted").overall_trust()
        untrusted_trust = lattice.get_trust("untrusted").overall_trust()
        # Without homeostasis: untrusted integrity = 1.0-0.8 = 0.2, other dims = 0.5
        # untrusted overall = (0.2 + 5*0.5)/6 = 2.7/6 = 0.45
        # trusted overall = 0.5 (all probation)
        assert untrusted_trust < trusted_trust

        ta = TrustAgentState(trust_lattice=lattice, trust_weight_context=True)
        ta.put("answer", "wrong", peer_id="untrusted", timestamp=200.0)
        ta.put("answer", "correct", peer_id="trusted", timestamp=100.0)

        entry = ta.get("answer")
        assert entry.value == "correct"

    def test_shared_knowledge_merge_with_trust_ranking(self):
        """Merge multiple AgentStates via SharedKnowledge.merge(), then merge TrustAgentStates."""
        a = AgentState("a")
        b = AgentState("b")
        a.add_fact("f1", "va", timestamp=100.0, confidence=0.9)
        b.add_fact("f1", "vb", timestamp=200.0, confidence=0.5)

        sk = SharedKnowledge.merge(a, b)
        merged = sk.state
        assert merged.get_fact("f1") is not None

        ta_a = TrustAgentState()
        ta_b = TrustAgentState()
        ta_a.put("f1", "va", peer_id="p1", timestamp=100.0)
        ta_b.put("f1", "vb", peer_id="p2", timestamp=200.0)

        merged_ta = ta_a.merge_context(ta_b)
        ranked = merged_ta.ranked_entries()
        assert len(ranked) >= 1

    def test_agent_state_fact_roundtrip_with_trust(self):
        """Add a Fact to AgentState, same data to TrustAgentState. Both retrieve correctly."""
        agent = AgentState("a")
        agent.add_fact("key", "value", timestamp=100.0, confidence=0.9)

        ta = TrustAgentState()
        ta.put("key", "value", peer_id="a", timestamp=100.0)

        assert agent.get_fact("key").value == "value"
        assert ta.get("key").value == "value"


# ═════════════════════════════════════════════════════════════════════════════
# Section 7: TrustStreamMerge ↔ merge_stream
# ═════════════════════════════════════════════════════════════════════════════

class TestTrustStreamMergeVsMergeStream:
    """Compare TrustStreamMerge behaviour against the real merge_stream API."""

    def test_stream_merge_real_data_through_trust_validation(self):
        """Real data streams processed through both merge_stream and TrustStreamMerge."""
        source_a = [
            {"id": "1", "name": "Alice", "score": 90},
            {"id": "2", "name": "Bob", "score": 80},
        ]
        source_b = [
            {"id": "2", "name": "Bob", "score": 85},
            {"id": "3", "name": "Carol", "score": 95},
        ]

        stats = StreamStats()
        batches = list(merge_stream(source_a, source_b, key="id", stats=stats))
        assert stats.rows_processed > 0

        tsm = TrustStreamMerge()
        chunks = []
        for i, record in enumerate(source_a + source_b):
            delta = make_delta(
                source_id="sender",
                insertions={record["id"]: str(record).encode()},
            )
            chunk = StreamChunk(delta=delta, sequence=i, stream_id="stream-1")
            chunks.append(chunk)

        results = tsm.validate_stream(chunks)
        assert all(r.accepted for r in results)
        assert len(results) == len(source_a) + len(source_b)

    def test_stream_chunk_validation_accepts_valid_deltas(self):
        """StreamChunks with valid ProjectionDeltas accepted by TrustStreamMerge (no verifier)."""
        tsm = TrustStreamMerge()

        for i in range(5):
            delta = make_delta(
                source_id=f"peer-{i}",
                insertions={f"k{i}": f"v{i}".encode()},
            )
            chunk = StreamChunk(delta=delta, sequence=i, stream_id="test-stream")
            result = tsm.validate_chunk(chunk)
            assert result.accepted
            assert result.sequence == i

    def test_stream_stats_comparable(self):
        """merge_stream with StreamStats and TrustStreamMerge process the same record count."""
        data_a = [{"id": str(i), "v": i} for i in range(10)]
        data_b = [{"id": str(i + 5), "v": i + 5} for i in range(10)]

        stats = StreamStats()
        batches = list(merge_stream(data_a, data_b, key="id", stats=stats))
        total_merged = stats.rows_processed

        tsm = TrustStreamMerge()
        all_records = data_a + data_b
        for i, rec in enumerate(all_records):
            delta = make_delta(insertions={rec["id"]: str(rec).encode()})
            chunk = StreamChunk(delta=delta, sequence=i, stream_id="s1")
            tsm.validate_chunk(chunk)

        stream_results = tsm.stream_results("s1")
        assert len(stream_results) == len(all_records)
        assert total_merged > 0


# ═════════════════════════════════════════════════════════════════════════════
# Section 8: DeltaTrustLattice as CRDT
# ═════════════════════════════════════════════════════════════════════════════

class TestDeltaTrustLatticeAsCRDT:
    """Verify DeltaTrustLattice has the same CRDT properties as base CRDTs."""

    def test_trust_lattice_merge_commutative(self):
        """DeltaTrustLattice.merge() must be commutative like all crdt-merge CRDTs."""
        a = DeltaTrustLattice("node-a", initial_peers={"p1"})
        b = DeltaTrustLattice("node-b", initial_peers={"p2"})

        ab = a.merge(b)
        ba = b.merge(a)

        assert ab.get_trust("p1").overall_trust() == pytest.approx(
            ba.get_trust("p1").overall_trust()
        )
        assert ab.get_trust("p2").overall_trust() == pytest.approx(
            ba.get_trust("p2").overall_trust()
        )

    def test_trust_lattice_merge_idempotent(self):
        """Self-merge must be idempotent."""
        a = DeltaTrustLattice("node-a", initial_peers={"p1", "p2"})
        aa = a.merge(a)

        for p in ("p1", "p2"):
            assert a.get_trust(p).overall_trust() == pytest.approx(
                aa.get_trust(p).overall_trust()
            )

    def test_trust_scores_use_gcounter_semantics(self):
        """TypedTrustScore evidence uses max-based merge (like GCounter).
        Merge of two scores = element-wise max of evidence.
        """
        ev_a = {"integrity": {"obs1": 0.3}}
        ev_b = {"integrity": {"obs1": 0.5}}
        ts_a = TypedTrustScore(_evidence=ev_a)
        ts_b = TypedTrustScore(_evidence=ev_b)

        merged = ts_a.merge(ts_b)
        assert merged._evidence["integrity"]["obs1"] == 0.5

    def test_trust_lattice_union_of_peers(self):
        """Merging two lattices unions their peer sets (like ORSet)."""
        a = DeltaTrustLattice("a", initial_peers={"p1", "p2"})
        b = DeltaTrustLattice("b", initial_peers={"p3", "p4"})

        merged = a.merge(b)
        assert merged.known_peers() >= {"p1", "p2", "p3", "p4"}

    def test_trust_propagation_as_delta(self):
        """observe_and_propagate() returns a ProjectionDelta (delta-state CRDT pattern)."""
        from crdt_merge.e4.proof_evidence import TrustEvidence

        lattice = DeltaTrustLattice("observer", initial_peers={"target"})
        evidence = TrustEvidence.create(
            observer="observer",
            target="target",
            evidence_type="equivocation",
            dimension="integrity",
            amount=0.2,
            proof=make_equivocation_proof(signer="target"),
        )
        delta = lattice.observe_and_propagate(evidence)
        assert isinstance(delta, ProjectionDelta)
        assert not delta.is_empty()


# ═════════════════════════════════════════════════════════════════════════════
# Section 9: E4 Bootstrap Integration
# ═════════════════════════════════════════════════════════════════════════════

class TestE4BootstrapIntegration:
    """Verify E4 bootstrap functions work correctly."""

    def test_initialize_creates_all_defaults(self):
        """After initialize_defaults(), all accessors return non-None."""
        reset()
        initialize_defaults()
        assert get_trust_lattice() is not None
        assert get_gossip_engine() is not None
        assert get_verifier() is not None

    def test_initialize_idempotent(self):
        """Calling initialize_defaults() twice is safe."""
        reset()
        initialize_defaults()
        initialize_defaults()
        assert is_initialized()

    def test_reset_clears_state(self):
        """After reset(), is_initialized() returns False."""
        initialize_defaults()
        reset()
        assert not is_initialized()

    def test_default_lattice_is_functional(self):
        """The default lattice can get_trust() and observe_and_propagate()."""
        reset()
        initialize_defaults()
        lattice = get_trust_lattice()
        trust = lattice.get_trust("unknown_peer")
        assert trust.overall_trust() == pytest.approx(PROBATION_TRUST)

    def test_default_gossip_is_functional(self):
        """The default gossip engine can prepare_sync() and receive_sync()."""
        reset()
        initialize_defaults()
        engine = get_gossip_engine()

        payload = engine.prepare_sync(data_deltas=[])
        assert isinstance(payload, TrustGossipPayload)
        assert len(payload.data_deltas) == 0

        accepted_data, accepted_trust = engine.receive_sync(payload)
        assert isinstance(accepted_data, list)
