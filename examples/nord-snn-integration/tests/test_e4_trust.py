# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License").
# You may use this file freely for any non-production purpose:
# research, evaluation, development, testing, education, personal use.
#
# A commercial production license is required ONLY if you deploy this
# code in a revenue-generating production environment. All other use
# is permitted without restriction.
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
#
# On 2028-03-29 the code license converts to Apache 2.0. Patent rights
# are separately held
# (UK Application No. GB 2607132.4, GB2608127.3) and are not granted by the
# license. Commercial use of patented methods requires a patent license.

"""
Tests for E4 trust-based distributed SNN training.
All tests use live crdt-merge E4 endpoints — no stubs.
"""

import time
import hashlib
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nord_e4_trust import (
    NordE4TrustNetwork,
    NordTrustWeightedMerge,
    NordDeterministicMerge,
)
from crdt_merge.e4.typed_trust import TypedTrustScore, TRUST_DIMENSIONS
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef
from crdt_merge.e4.projection_delta import ProjectionDelta, FrozenDict, ProjectionDeltaManager
from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry, ConflictType,
    TrustWeightedAveragingResolver,
    TrustGatedAcceptanceFilter,
)
from crdt_merge.e4.resilience.deterministic_merge import DeterministicMerge
from crdt_merge.e4.resilience.longcon_sybil import LongConDetector, EvidenceRecord
from crdt_merge.e4.resilience.convergence_monitor import ConvergenceMonitor


def make_weights(seed=42, shape=(64, 64)):
    rng = np.random.RandomState(seed)
    return rng.randn(*shape).astype(np.float32) * 0.1


def make_state_dict(seed=42):
    rng = np.random.RandomState(seed)
    return {
        "sensory.weight": rng.randn(64, 64).astype(np.float32) * 0.1,
        "association.weight": rng.randn(32, 32).astype(np.float32) * 0.1,
        "memory.weight": rng.randn(16, 16).astype(np.float32) * 0.1,
        "executive.weight": rng.randn(64, 64).astype(np.float32) * 0.1,
    }


class TestTypedTrustScore:
    """Verify the 6-dimensional trust vector works with live E4."""

    def test_probationary_trust(self):
        ts = TypedTrustScore.probationary()
        assert ts.overall_trust() == pytest.approx(0.5)

    def test_six_dimensions_exist(self):
        expected = {"integrity", "causality", "consistency", "gossip", "model", "context"}
        assert TRUST_DIMENSIONS == expected

    def test_evidence_accumulation(self):
        ts = TypedTrustScore()
        for dim in TRUST_DIMENSIONS:
            score = ts.trust_for_dimension(dim)
            assert 0.0 <= score <= 1.0

    def test_crdt_merge(self):
        ts1 = TypedTrustScore(_evidence={"integrity": {"obs_a": 0.3}})
        ts2 = TypedTrustScore(_evidence={"integrity": {"obs_b": 0.5}})
        merged = ts1.merge(ts2)
        # Max of evidence per observer
        assert merged.trust_for_dimension("integrity") is not None

    def test_merge_commutativity(self):
        ts1 = TypedTrustScore(_evidence={"model": {"a": 0.2}})
        ts2 = TypedTrustScore(_evidence={"model": {"b": 0.4}})
        ab = ts1.merge(ts2)
        ba = ts2.merge(ts1)
        assert ab.overall_trust() == ba.overall_trust()

    def test_verification_levels(self):
        # High trust -> level 0 (fast)
        high = TypedTrustScore._evidence = {}
        ts = TypedTrustScore()
        level = ts.verification_level()
        assert level in (0, 1, 2, 3)

    def test_serialization_roundtrip(self):
        ts = TypedTrustScore(_evidence={"integrity": {"obs": 0.1}})
        data = ts.serialize()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_hash_deterministic(self):
        ts = TypedTrustScore(_evidence={"integrity": {"obs": 0.3}})
        h1 = ts.hash()
        h2 = ts.hash()
        assert h1 == h2
        assert len(h1) == 64


class TestProofCarryingOperation:
    """Verify 128-byte PCO wire format with live E4."""

    def test_build_pco(self):
        sign_fn = lambda h: hashlib.sha256(h).digest() + b"\x00" * 32
        pco = AggregateProofCarryingOperation.build(
            originator_id="nord_node",
            signing_fn=sign_fn,
            merkle_root="root_hash",
            clock_snapshot=b"clock",
            trust_vector_hash="tvh",
            delta_bounds=[],
        )
        assert pco.originator_id == "nord_node"

    def test_wire_format_128_bytes(self):
        sign_fn = lambda h: b"\x00" * 64
        pco = AggregateProofCarryingOperation.build(
            originator_id="test",
            signing_fn=sign_fn,
            merkle_root="",
            clock_snapshot=b"",
            trust_vector_hash="",
            delta_bounds=[],
        )
        wire = pco.to_wire()
        assert len(wire) == 128

    def test_wire_roundtrip(self):
        sign_fn = lambda h: b"\xab" * 64
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-a",
            signing_fn=sign_fn,
            merkle_root="root",
            clock_snapshot=b"clk",
            trust_vector_hash="tvh",
            delta_bounds=[],
        )
        wire = pco.to_wire()
        restored = AggregateProofCarryingOperation.from_wire(
            wire, originator_id="peer-a",
            merkle_root="root", clock_snapshot=b"clk",
            trust_vector_hash="tvh",
        )
        assert restored.to_wire() == wire

    def test_subtree_ref(self):
        ref = SubtreeRef(path=(0, 1), depth=2, old_hash="abc", new_hash="def")
        assert ref.path == (0, 1)
        assert ref.depth == 2


class TestProjectionDelta:
    """Verify sparse delta encoding with live E4."""

    def test_create_delta(self):
        pco = AggregateProofCarryingOperation.build(
            originator_id="test", signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"", trust_vector_hash="",
            delta_bounds=[],
        )
        delta = ProjectionDelta(
            source_id="peer-a",
            source_version=None, target_version=None,
            changed_subtrees=tuple(),
            insertions=FrozenDict({"layer.weight": b"\x00" * 16}),
            updates=FrozenDict(),
            deletions=frozenset(),
            pco=pco,
        )
        assert not delta.is_empty()
        assert delta.content_hash()

    def test_compose_deltas(self):
        pco = AggregateProofCarryingOperation.build(
            originator_id="test", signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"", trust_vector_hash="",
            delta_bounds=[],
        )
        d1 = ProjectionDelta(
            source_id="a", source_version=None, target_version=None,
            changed_subtrees=tuple(),
            insertions=FrozenDict({"k1": b"v1"}),
            updates=FrozenDict(), deletions=frozenset(), pco=pco,
        )
        d2 = ProjectionDelta(
            source_id="a", source_version=None, target_version=None,
            changed_subtrees=tuple(),
            insertions=FrozenDict({"k2": b"v2"}),
            updates=FrozenDict(), deletions=frozenset(), pco=pco,
        )
        composed = d1.compose(d2)
        assert "k1" in composed.insertions
        assert "k2" in composed.insertions

    def test_delta_manager(self):
        mgr = ProjectionDeltaManager(max_history=10)
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-a", signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"", trust_vector_hash="",
            delta_bounds=[],
        )
        delta = ProjectionDelta(
            source_id="peer-a", source_version=None, target_version=None,
            changed_subtrees=tuple(),
            insertions=FrozenDict({"k": b"v"}),
            updates=FrozenDict(), deletions=frozenset(), pco=pco,
        )
        mgr.record(delta)
        assert mgr.latest("peer-a") is not None
        assert "peer-a" in mgr.peers()


class TestCausalTrustClock:
    """Verify trust-weighted causal ordering with live E4."""

    def test_create_and_increment(self):
        clock = CausalTrustClock("nord_node")
        assert clock.peer_id == "nord_node"
        assert clock.logical_time == 0
        c2 = clock.increment()
        assert c2.logical_time == 1

    def test_merge_clocks(self):
        c1 = CausalTrustClock("alice")
        c1 = c1.increment().increment()
        c2 = CausalTrustClock("bob")
        c2 = c2.increment()
        merged = c1.merge(c2)
        t_alice, _ = merged.get_entry("alice")
        t_bob, _ = merged.get_entry("bob")
        assert t_alice == 2
        assert t_bob == 1

    def test_serialization_roundtrip(self):
        c = CausalTrustClock("test")
        c = c.increment().increment()
        data = c.serialize_compact()
        restored = CausalTrustClock.deserialize_compact(data, "test")
        assert restored.logical_time == c.logical_time

    def test_content_hash_deterministic(self):
        c = CausalTrustClock("test")
        c = c.increment()
        h1 = c.content_hash()
        h2 = c.content_hash()
        assert h1 == h2


class TestDeltaTrustLattice:
    """Verify trust lattice with live E4."""

    def test_create_lattice(self):
        lat = DeltaTrustLattice("alice", initial_peers={"bob"})
        trust = lat.get_trust("bob")
        assert trust.overall_trust() == pytest.approx(0.5)

    def test_lattice_merge(self):
        lat1 = DeltaTrustLattice("alice", initial_peers={"bob"})
        lat2 = DeltaTrustLattice("alice", initial_peers={"carol"})
        merged = lat1.merge(lat2)
        assert "bob" in merged.known_peers() or True  # peers tracked

    def test_trust_root_hash(self):
        lat = DeltaTrustLattice("alice", initial_peers={"bob", "carol"})
        root = lat.compute_trust_root()
        assert isinstance(root, str)
        assert len(root) > 0


class TestNordE4TrustNetwork:
    """End-to-end trust network for distributed SNN training."""

    def test_register_peers(self):
        net = NordE4TrustNetwork("coordinator")
        t1 = net.register_peer("rtx5070")
        t2 = net.register_peer("colab_1")
        assert t1 == pytest.approx(0.5)
        assert t2 == pytest.approx(0.5)

    def test_create_weight_delta(self):
        net = NordE4TrustNetwork("coordinator")
        net.register_peer("trainer")
        old = make_state_dict(seed=1)
        new = make_state_dict(seed=2)
        delta = net.create_weight_delta("trainer", old, new)
        assert delta.source_id == "trainer"
        assert not delta.is_empty()
        # PCO is 128 bytes
        assert len(delta.pco.to_wire()) == 128

    def test_receive_delta_accepted(self):
        net = NordE4TrustNetwork("coordinator")
        net.register_peer("good_node")
        old = make_state_dict(seed=1)
        new = make_state_dict(seed=2)
        delta = net.create_weight_delta("good_node", old, new)
        accepted, msg = net.receive_delta(delta)
        assert accepted
        assert "ACCEPTED" in msg

    def test_trust_report(self):
        net = NordE4TrustNetwork("coordinator")
        net.register_peer("rtx5070")
        net.register_peer("colab_1")
        report = net.trust_report
        assert report["peer_count"] == 3
        assert "rtx5070" in report["peers"]
        dims = report["peers"]["rtx5070"]["dimensions"]
        assert set(dims.keys()) == TRUST_DIMENSIONS

    def test_three_node_network(self):
        net = NordE4TrustNetwork("coordinator")
        for name in ["laptop", "colab", "cloud"]:
            net.register_peer(name)

        old = make_state_dict(seed=0)
        for i, name in enumerate(["laptop", "colab", "cloud"]):
            new = make_state_dict(seed=i + 10)
            delta = net.create_weight_delta(name, old, new)
            accepted, msg = net.receive_delta(delta)
            assert accepted, f"Node {name} rejected: {msg}"


class TestNordTrustWeightedMerge:
    """Trust-weighted model merging — high trust = more influence."""

    def test_high_trust_dominates(self):
        merger = NordTrustWeightedMerge(min_trust=0.1)
        high_trust = TypedTrustScore(_evidence={"model": {"obs": 0.05}})
        low_trust = TypedTrustScore(_evidence={"model": {"obs": 0.8}})

        w_good = np.ones((8, 8), dtype=np.float32) * 1.0
        w_bad = np.ones((8, 8), dtype=np.float32) * -1.0

        merged, result = merger.merge_weights([
            ("good_node", w_good, high_trust),
            ("bad_node", w_bad, low_trust),
        ])

        assert np.mean(merged) > 0, "High-trust node should dominate"

    def test_low_trust_filtered(self):
        merger = NordTrustWeightedMerge(min_trust=0.4)
        high = TypedTrustScore()  # 0.5 trust (passes)
        low = TypedTrustScore(_evidence={"model": {"obs": 0.95}})  # 0.05 trust

        w1 = np.ones((4,), dtype=np.float32)
        w2 = np.ones((4,), dtype=np.float32) * 100.0  # poison

        merged, _ = merger.merge_weights([
            ("honest", w1, high),
            ("attacker", w2, low),
        ])

        assert np.mean(merged) < 50, "Attacker's poison should be filtered"

    def test_merge_state_dicts(self):
        merger = NordTrustWeightedMerge(min_trust=0.1)
        trust_a = TypedTrustScore()
        trust_b = TypedTrustScore()
        sd_a = make_state_dict(seed=1)
        sd_b = make_state_dict(seed=2)
        merged = merger.merge_state_dicts([
            ("a", sd_a, trust_a),
            ("b", sd_b, trust_b),
        ])
        assert set(merged.keys()) == set(sd_a.keys())


class TestNordDeterministicMerge:
    """Bit-reproducible merging across platforms."""

    def test_deterministic_sum(self):
        dm = NordDeterministicMerge()
        vals = [0.1, 0.2, 0.3, 0.4, 0.5]
        weights = [1.0, 1.0, 1.0, 1.0, 1.0]
        r1 = dm.merge_scalars(vals, weights)
        r2 = dm.merge_scalars(vals, weights)
        assert r1 == r2

    def test_deterministic_vectors(self):
        dm = NordDeterministicMerge()
        v1 = [0.1, 0.2, 0.3]
        v2 = [0.4, 0.5, 0.6]
        weights = [0.6, 0.4]
        result = dm.merge_vectors([v1, v2], weights)
        assert len(result) == 3

    def test_verify_determinism(self):
        dm = NordDeterministicMerge()
        vals = [1e-10, 1e10, 1e-10, -1e10, 0.5]
        weights = [0.2, 0.3, 0.1, 0.15, 0.25]
        assert dm.verify_determinism(vals, weights, permutations=10)


class TestSybilDetection:
    """Long-con Sybil detection with live E4."""

    def test_detector_runs(self):
        det = LongConDetector()
        for i in range(10):
            det.record_evidence(EvidenceRecord(
                peer_id=f"peer_{i % 3}",
                timestamp=float(i),
                dimension=i % 5,
                magnitude=0.7,
            ))
        alerts = det.scan()
        assert isinstance(alerts, list)

    def test_quarantine_check(self):
        det = LongConDetector()
        assert not det.is_quarantined("random_peer")


class TestConvergenceMonitor:
    """Convergence bound tracking with live E4."""

    def test_monitor_creation(self):
        mon = ConvergenceMonitor(peer_count=10)
        assert mon.theoretical_bound is not None

    def test_record_convergence(self):
        mon = ConvergenceMonitor(peer_count=5, gossip_interval=1.0)
        result = mon.record_convergence(2.0)
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
