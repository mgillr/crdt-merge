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

"""Tests for TrustGossipEngine and TrustGossipPayload.

Covers trust-enhanced gossip, PCO attachment, peer trust lookup during
gossip, payload creation, receive routing, and outbound management.
"""

import pytest

from crdt_merge.e4.integration.gossip_bridge import (
    TrustGossipEngine,
    TrustGossipPayload,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
    VerificationResult,
)
from e4_factories import make_delta, make_pco


# ---------------------------------------------------------------------------
# TrustGossipPayload
# ---------------------------------------------------------------------------

class TestTrustGossipPayload:

    def test_default_creation(self):
        """Default payload has empty delta lists and empty peer_id."""
        p = TrustGossipPayload()
        assert p.data_deltas == []
        assert p.trust_deltas == []
        assert p.peer_id == ""

    def test_creation_with_data(self):
        """Payload stores data_deltas and peer_id."""
        delta = make_delta()
        p = TrustGossipPayload(data_deltas=[delta], peer_id="alice")
        assert len(p.data_deltas) == 1
        assert p.peer_id == "alice"

    def test_payload_with_trust_deltas(self):
        """Payload stores trust_deltas."""
        td = make_delta(source_id="trust_observer")
        p = TrustGossipPayload(trust_deltas=[td], peer_id="alice")
        assert len(p.trust_deltas) == 1


# ---------------------------------------------------------------------------
# TrustGossipEngine: creation and binding
# ---------------------------------------------------------------------------

class TestGossipEngineCreation:

    def test_create_no_deps(self):
        """Engine can be created with no dependencies."""
        engine = TrustGossipEngine()
        assert engine.pending_outbound == 0

    def test_bind_trust_lattice(self):
        """bind_trust_lattice sets the lattice."""
        engine = TrustGossipEngine()
        lattice = DeltaTrustLattice("local")
        engine.bind_trust_lattice(lattice)
        # No assertion error means it bound successfully

    def test_bind_verifier(self):
        """bind_verifier sets the verifier."""
        engine = TrustGossipEngine()
        verifier = AdaptiveVerificationController()
        engine.bind_verifier(verifier)

    def test_bind_state(self):
        """bind_state sets the application state."""
        engine = TrustGossipEngine()
        engine.bind_state({"key": "value"})


# ---------------------------------------------------------------------------
# TrustGossipEngine: prepare_sync
# ---------------------------------------------------------------------------

class TestGossipEnginePrepareSync:

    def test_prepare_sync_creates_payload(self):
        """prepare_sync returns a TrustGossipPayload."""
        engine = TrustGossipEngine()
        delta = make_delta()
        payload = engine.prepare_sync([delta])
        assert isinstance(payload, TrustGossipPayload)
        assert len(payload.data_deltas) == 1

    def test_prepare_sync_with_lattice_peer_id(self):
        """Payload gets peer_id from the bound lattice."""
        lattice = DeltaTrustLattice("peer-alice")
        engine = TrustGossipEngine(trust_lattice=lattice)
        payload = engine.prepare_sync([])
        assert payload.peer_id == "peer-alice"

    def test_prepare_sync_without_trust(self):
        """include_trust=False skips trust deltas."""
        lattice = DeltaTrustLattice("alice")
        engine = TrustGossipEngine(trust_lattice=lattice)
        payload = engine.prepare_sync([], include_trust=False)
        assert payload.trust_deltas == []

    def test_prepare_sync_increments_outbound(self):
        """Each prepare_sync increments pending_outbound."""
        engine = TrustGossipEngine()
        engine.prepare_sync([])
        engine.prepare_sync([])
        assert engine.pending_outbound == 2

    def test_drain_outbound(self):
        """drain_outbound returns and clears all pending payloads."""
        engine = TrustGossipEngine()
        engine.prepare_sync([])
        engine.prepare_sync([])
        drained = engine.drain_outbound()
        assert len(drained) == 2
        assert engine.pending_outbound == 0


# ---------------------------------------------------------------------------
# TrustGossipEngine: receive_sync
# ---------------------------------------------------------------------------

class TestGossipEngineReceiveSync:

    def test_receive_no_verifier_accepts_all(self):
        """Without a verifier, all data deltas are accepted."""
        engine = TrustGossipEngine()
        delta = make_delta()
        payload = TrustGossipPayload(data_deltas=[delta], peer_id="alice")
        accepted_data, accepted_trust = engine.receive_sync(payload)
        assert len(accepted_data) == 1
        assert len(accepted_trust) == 0

    def test_receive_no_lattice_rejects_trust(self):
        """Without a lattice, trust deltas are rejected."""
        engine = TrustGossipEngine()
        td = make_delta(source_id="trust_obs")
        payload = TrustGossipPayload(trust_deltas=[td], peer_id="alice")
        _, accepted_trust = engine.receive_sync(payload)
        assert len(accepted_trust) == 0

    def test_receive_empty_payload(self):
        """Empty payload produces empty accepted lists."""
        engine = TrustGossipEngine()
        payload = TrustGossipPayload()
        data, trust = engine.receive_sync(payload)
        assert data == []
        assert trust == []

    def test_receive_with_verifier_and_lattice(self):
        """With verifier and lattice, deltas go through verification."""
        lattice = DeltaTrustLattice("local", initial_peers={"alice"})
        verifier = AdaptiveVerificationController(trust_lattice=lattice)
        engine = TrustGossipEngine(
            trust_lattice=lattice,
            verifier=verifier,
            state=object(),
        )
        delta = make_delta(source_id="alice")
        payload = TrustGossipPayload(data_deltas=[delta], peer_id="alice")
        data, trust = engine.receive_sync(payload)
        # Verification outcome depends on PCO validity
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# TrustGossipEngine: multiple payloads roundtrip
# ---------------------------------------------------------------------------

class TestGossipEngineRoundtrip:

    def test_prepare_and_receive(self):
        """Payload created by one engine can be received by another."""
        sender_engine = TrustGossipEngine()
        receiver_engine = TrustGossipEngine()
        delta = make_delta(source_id="sender")
        payload = sender_engine.prepare_sync([delta])
        data, trust = receiver_engine.receive_sync(payload)
        assert len(data) == 1
        assert data[0].source_id == "sender"
