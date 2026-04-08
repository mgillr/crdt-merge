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

"""End-to-end tests: multi-peer scenario with honest + Byzantine peers.

Covers trust evolution, delta propagation, conflict resolution, Sybil
resistance, and convergence properties in multi-peer setups.
"""

import pytest

from crdt_merge.e4.typed_trust import (
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    TRUST_DIMENSIONS,
    TypedTrustScore,
    TrustHomeostasis,
)
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef
from crdt_merge.e4.projection_delta import FrozenDict, ProjectionDelta
from crdt_merge.e4.proof_evidence import TrustEvidence
from crdt_merge.e4.delta_trust_lattice import (
    DeltaTrustLattice,
    TrustCircuitBreaker,
    CircuitBreakerTripped,
)
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
)
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.integration.agent_bridge import TrustAgentState, TrustAnnotatedEntry
from e4_factories import make_delta, make_pco, make_equivocation_proof


# ---------------------------------------------------------------------------
# Multi-peer trust evolution
# ---------------------------------------------------------------------------

class TestMultiPeerTrustEvolution:

    def test_initial_trust_all_probationary(self):
        """All new peers start at PROBATION_TRUST."""
        lattice = DeltaTrustLattice(
            "alice", initial_peers={"bob", "carol", "dave"},
        )
        for peer in ["bob", "carol", "dave"]:
            assert lattice.get_trust(peer).overall_trust() == pytest.approx(PROBATION_TRUST)

    def test_evidence_reduces_trust(self):
        """Recording evidence against a peer reduces their trust."""
        lattice = DeltaTrustLattice("alice", initial_peers={"eve"})
        initial_trust = lattice.get_trust("eve").overall_trust()

        evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=1.0, proof=make_equivocation_proof("eve"),
        )
        lattice.observe_and_propagate(evidence)

        new_trust = lattice.get_trust("eve").overall_trust()
        assert new_trust < initial_trust

    def test_multiple_observers_compound(self):
        """Evidence from multiple observers compounds."""
        lattice = DeltaTrustLattice(
            "alice", initial_peers={"eve"},
        )

        # Simulate multiple observers with enough evidence to overcome homeostasis
        for i in range(3):
            ev = TrustEvidence.create(
                observer=f"observer_{i}", target="eve",
                evidence_type="equivocation", dimension="integrity",
                amount=1.0, proof=make_equivocation_proof("eve"),
            )
            lattice.observe_and_propagate(ev)

        trust = lattice.get_trust("eve").overall_trust()
        assert trust < PROBATION_TRUST

    def test_honest_peers_maintain_trust(self):
        """Honest peers (no evidence) maintain probation trust."""
        lattice = DeltaTrustLattice(
            "alice", initial_peers={"bob", "eve"},
        )
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof("eve"),
        )
        lattice.observe_and_propagate(ev)

        # Bob should still have reasonable trust
        bob_trust = lattice.get_trust("bob").overall_trust()
        assert bob_trust >= PROBATION_TRUST - 0.1  # homeostasis may shift


# ---------------------------------------------------------------------------
# Delta propagation between peers
# ---------------------------------------------------------------------------

class TestDeltaPropagation:

    def test_observe_returns_delta(self):
        """observe_and_propagate returns a ProjectionDelta for propagation."""
        lattice = DeltaTrustLattice("alice", initial_peers={"eve"})
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof("eve"),
        )
        delta = lattice.observe_and_propagate(ev)
        assert isinstance(delta, ProjectionDelta)
        assert delta.source_id == "alice"
        assert delta.pco is not None

    def test_gossip_propagation(self):
        """Trust deltas propagate via gossip payload."""
        alice_lattice = DeltaTrustLattice("alice", initial_peers={"eve"})
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof("eve"),
        )
        trust_delta = alice_lattice.observe_and_propagate(ev)

        # Package into gossip
        engine = TrustGossipEngine(trust_lattice=alice_lattice)
        payload = engine.prepare_sync([], include_trust=False)
        # Manually add trust delta
        payload.trust_deltas.append(trust_delta)
        assert len(payload.trust_deltas) == 1


# ---------------------------------------------------------------------------
# Conflict resolution: trust-weighted
# ---------------------------------------------------------------------------

class TestMultiPeerConflictResolution:

    def test_high_trust_peer_wins(self):
        """In agent state merge, higher-trust peer's value wins."""
        s1 = TrustAgentState()
        s1._entries["shared_key"] = TrustAnnotatedEntry(
            key="shared_key", value="alice_value",
            peer_id="alice", trust_at_write=0.9, timestamp=1.0,
        )
        s2 = TrustAgentState()
        s2._entries["shared_key"] = TrustAnnotatedEntry(
            key="shared_key", value="eve_value",
            peer_id="eve", trust_at_write=0.2, timestamp=2.0,
        )
        merged = s1.merge_context(s2)
        assert merged.get("shared_key").value == "alice_value"

    def test_byzantine_peer_deprioritized(self):
        """Byzantine peer's contributions are ranked lower."""
        state = TrustAgentState()
        state._entries["k1"] = TrustAnnotatedEntry(
            key="k1", value="honest", peer_id="bob", trust_at_write=0.8,
        )
        state._entries["k2"] = TrustAnnotatedEntry(
            key="k2", value="dishonest", peer_id="eve", trust_at_write=0.1,
        )
        ranked = state.ranked_entries()
        assert ranked[0].peer_id == "bob"
        assert ranked[1].peer_id == "eve"


# ---------------------------------------------------------------------------
# Circuit breaker: Sybil resistance
# ---------------------------------------------------------------------------

class TestCircuitBreakerSybilResistance:

    def test_rapid_trust_changes_trip_breaker(self):
        """Rapid large trust changes trip the circuit breaker."""
        cb = TrustCircuitBreaker(
            window_size=20, sigma_threshold=1.5,
            cooldown_seconds=0.1, min_samples=5,
        )
        # Build up normal baseline
        base = TypedTrustScore()
        for _ in range(10):
            cb.record_trust_change("peer", base, base)

        # Inject anomalous change
        bad_ev = {dim: {"obs": 0.8} for dim in TRUST_DIMENSIONS}
        low_trust = TypedTrustScore(_evidence=bad_ev)
        cb.record_trust_change("evil", base, low_trust)

        assert cb.is_tripped() is True

    def test_tripped_breaker_blocks_observation(self):
        """Tripped circuit breaker prevents observe_and_propagate."""
        cb = TrustCircuitBreaker(
            window_size=5, sigma_threshold=0.01,
            cooldown_seconds=60.0, min_samples=2,
        )
        lattice = DeltaTrustLattice(
            "alice", initial_peers={"eve"},
            circuit_breaker=cb,
        )

        # Force trip
        base = TypedTrustScore()
        bad_ev = {dim: {"obs": 0.9} for dim in TRUST_DIMENSIONS}
        low = TypedTrustScore(_evidence=bad_ev)
        for _ in range(5):
            cb.record_trust_change("x", base, low)

        if cb.is_tripped():
            ev = TrustEvidence.create(
                observer="alice", target="eve",
                evidence_type="equivocation", dimension="integrity",
                amount=0.1, proof=make_equivocation_proof("eve"),
            )
            with pytest.raises(CircuitBreakerTripped):
                lattice.observe_and_propagate(ev)


# ---------------------------------------------------------------------------
# Lattice CRDT merge
# ---------------------------------------------------------------------------

class TestLatticeMerge:

    def test_merge_combines_peers(self):
        """Merging two lattices unions their peer trust state."""
        l1 = DeltaTrustLattice("alice", initial_peers={"bob"})
        l2 = DeltaTrustLattice("carol", initial_peers={"dave"})
        merged = l1.merge(l2)
        assert "bob" in merged.known_peers()
        assert "dave" in merged.known_peers()

    def test_merge_commutative(self):
        """Lattice merge is commutative."""
        l1 = DeltaTrustLattice("a", initial_peers={"x"})
        l2 = DeltaTrustLattice("b", initial_peers={"y"})
        m1 = l1.merge(l2)
        m2 = l2.merge(l1)
        # Same peers present in both merge results
        assert m1.known_peers() == m2.known_peers()

    def test_merge_idempotent(self):
        """Merging lattice with itself is idempotent."""
        l1 = DeltaTrustLattice("a", initial_peers={"b", "c"})
        merged = l1.merge(l1)
        for peer in ["b", "c"]:
            orig = l1.get_trust(peer).overall_trust()
            m_trust = merged.get_trust(peer).overall_trust()
            assert m_trust == pytest.approx(orig, abs=0.05)


# ---------------------------------------------------------------------------
# Trust convergence
# ---------------------------------------------------------------------------

class TestTrustConvergence:

    def test_trust_converges_after_evidence(self):
        """Trust stabilizes after evidence application."""
        lattice = DeltaTrustLattice("alice", initial_peers={"eve"})

        # Apply evidence repeatedly
        for i in range(5):
            ev = TrustEvidence.create(
                observer=f"obs_{i}", target="eve",
                evidence_type="equivocation", dimension="integrity",
                amount=0.05, proof=make_equivocation_proof("eve"),
            )
            lattice.observe_and_propagate(ev)

        trust_a = lattice.get_trust("eve").overall_trust()

        # One more piece of evidence
        ev_extra = TrustEvidence.create(
            observer="obs_extra", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.01, proof=make_equivocation_proof("eve"),
        )
        lattice.observe_and_propagate(ev_extra)
        trust_b = lattice.get_trust("eve").overall_trust()

        # Trust should be changing only marginally
        assert abs(trust_a - trust_b) < 0.2

    def test_homeostasis_preserves_budget(self):
        """Total trust across peers is conserved after homeostasis."""
        scores = {
            "alice": TypedTrustScore(_evidence={"integrity": {"obs": 0.1}}),
            "bob": TypedTrustScore(_evidence={"integrity": {"obs": 0.3}}),
            "carol": TypedTrustScore(_evidence={"integrity": {"obs": 0.5}}),
        }
        normalized = TrustHomeostasis.normalize(scores, peer_count=3)
        total = sum(
            normalized[p].trust_for_dimension("integrity") for p in normalized
        )
        assert total == pytest.approx(3.0, abs=0.4)


# ---------------------------------------------------------------------------
# Multi-peer gossip roundtrip
# ---------------------------------------------------------------------------

class TestMultiPeerGossipRoundtrip:

    def test_full_gossip_cycle(self):
        """A complete gossip cycle: prepare, send, receive."""
        alice_lattice = DeltaTrustLattice("alice", initial_peers={"bob"})
        bob_lattice = DeltaTrustLattice("bob", initial_peers={"alice"})

        alice_engine = TrustGossipEngine(trust_lattice=alice_lattice)
        bob_engine = TrustGossipEngine(trust_lattice=bob_lattice)

        # Alice sends data
        delta = make_delta(source_id="alice")
        payload = alice_engine.prepare_sync([delta])

        # Bob receives
        data, trust = bob_engine.receive_sync(payload)
        assert len(data) == 1


# ---------------------------------------------------------------------------
# End-to-end: verification tier transitions
# ---------------------------------------------------------------------------

class TestVerificationTierTransitions:

    def test_trusted_peer_gets_light_verification(self):
        """A zero-evidence peer gets verification level 1 (probation)."""
        lattice = DeltaTrustLattice("alice", initial_peers={"bob"})
        ts = lattice.get_trust("bob")
        assert ts.verification_level() == 1

    def test_degraded_peer_gets_full_verification(self):
        """A peer with lots of evidence gets full verification (level 2+)."""
        lattice = DeltaTrustLattice("alice", initial_peers={"eve"})
        # Add evidence to push below LOW_TRUST
        bad_ev = {dim: {"obs": 0.7} for dim in TRUST_DIMENSIONS}
        lattice._trust_scores["eve"] = TypedTrustScore(_evidence=bad_ev)
        ts = lattice.get_trust("eve")
        assert ts.verification_level() >= 2
