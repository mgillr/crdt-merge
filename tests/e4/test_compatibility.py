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

"""Tests for CompatibilityHashMode / CompatibilityController.

Covers dual-hash generation, pre-E4 interop, migration path,
fallback behavior, handshake negotiation, and peer upgrades.
"""

import pytest

from crdt_merge.e4.compatibility import (
    CompatibilityController,
    CompatibilityMode,
    CompatHandshake,
    PeerCapability,
    _mode_to_capability,
)
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle


# ---------------------------------------------------------------------------
# CompatibilityMode enum
# ---------------------------------------------------------------------------

class TestCompatibilityMode:

    def test_e4_only(self):
        """E4_ONLY mode value."""
        assert CompatibilityMode.E4_ONLY.value == "e4_only"

    def test_dual_hash(self):
        """DUAL_HASH mode value."""
        assert CompatibilityMode.DUAL_HASH.value == "dual_hash"

    def test_legacy_only(self):
        """LEGACY_ONLY mode value."""
        assert CompatibilityMode.LEGACY_ONLY.value == "legacy_only"


# ---------------------------------------------------------------------------
# PeerCapability enum
# ---------------------------------------------------------------------------

class TestPeerCapability:

    def test_pre_e4_value(self):
        """PRE_E4 has value 0."""
        assert PeerCapability.PRE_E4.value == 0

    def test_e4_dual_value(self):
        """E4_DUAL has value 1."""
        assert PeerCapability.E4_DUAL.value == 1

    def test_e4_full_value(self):
        """E4_FULL has value 2."""
        assert PeerCapability.E4_FULL.value == 2


# ---------------------------------------------------------------------------
# CompatHandshake
# ---------------------------------------------------------------------------

class TestCompatHandshake:

    def test_creation(self):
        """CompatHandshake stores peer_id, capability, and version."""
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_FULL)
        assert hs.peer_id == "bob"
        assert hs.capability == PeerCapability.E4_FULL
        assert hs.version == 1

    def test_frozen(self):
        """CompatHandshake is frozen."""
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.PRE_E4)
        with pytest.raises(AttributeError):
            hs.peer_id = "eve"


# ---------------------------------------------------------------------------
# CompatibilityController creation
# ---------------------------------------------------------------------------

class TestCompatibilityControllerCreation:

    def test_default_mode(self):
        """Default mode is E4_ONLY."""
        ctrl = CompatibilityController()
        assert ctrl.default_mode == CompatibilityMode.E4_ONLY

    def test_custom_default_mode(self):
        """Custom default mode is respected."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.LEGACY_ONLY)
        assert ctrl.default_mode == CompatibilityMode.LEGACY_ONLY

    def test_set_default_mode(self):
        """set_default_mode changes the default."""
        ctrl = CompatibilityController()
        ctrl.set_default_mode(CompatibilityMode.DUAL_HASH)
        assert ctrl.default_mode == CompatibilityMode.DUAL_HASH


# ---------------------------------------------------------------------------
# Handshake negotiation
# ---------------------------------------------------------------------------

class TestHandshakeNegotiation:

    def test_both_e4_full(self):
        """Two E4_FULL peers negotiate E4_ONLY."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_FULL)
        mode = ctrl.process_handshake(hs)
        assert mode == CompatibilityMode.E4_ONLY

    def test_local_e4_remote_pre_e4(self):
        """E4 local + PRE_E4 remote -> DUAL_HASH."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hs = CompatHandshake(peer_id="legacy-peer", capability=PeerCapability.PRE_E4)
        mode = ctrl.process_handshake(hs)
        assert mode == CompatibilityMode.DUAL_HASH

    def test_both_pre_e4(self):
        """Two PRE_E4 peers negotiate LEGACY_ONLY."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.LEGACY_ONLY)
        hs = CompatHandshake(peer_id="old-peer", capability=PeerCapability.PRE_E4)
        mode = ctrl.process_handshake(hs)
        assert mode == CompatibilityMode.LEGACY_ONLY

    def test_e4_dual_both(self):
        """Two E4_DUAL peers negotiate DUAL_HASH."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.DUAL_HASH)
        hs = CompatHandshake(peer_id="dual-peer", capability=PeerCapability.E4_DUAL)
        mode = ctrl.process_handshake(hs)
        assert mode == CompatibilityMode.DUAL_HASH


# ---------------------------------------------------------------------------
# mode_for_peer
# ---------------------------------------------------------------------------

class TestModeForPeer:

    def test_unknown_peer_returns_default(self):
        """Unknown peer gets the system default mode."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        assert ctrl.mode_for_peer("unknown") == CompatibilityMode.E4_ONLY

    def test_known_peer_returns_negotiated(self):
        """Known peer returns the negotiated mode."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.PRE_E4)
        ctrl.process_handshake(hs)
        assert ctrl.mode_for_peer("bob") == CompatibilityMode.DUAL_HASH


# ---------------------------------------------------------------------------
# Build handshake
# ---------------------------------------------------------------------------

class TestBuildHandshake:

    def test_build_e4_only(self):
        """E4_ONLY default builds E4_FULL capability."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hs = ctrl.build_handshake("alice")
        assert hs.peer_id == "alice"
        assert hs.capability == PeerCapability.E4_FULL

    def test_build_legacy(self):
        """LEGACY_ONLY default builds PRE_E4 capability."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.LEGACY_ONLY)
        hs = ctrl.build_handshake("alice")
        assert hs.capability == PeerCapability.PRE_E4


# ---------------------------------------------------------------------------
# Dual hash computation
# ---------------------------------------------------------------------------

class TestComputeHashes:

    def test_e4_only_mode(self):
        """E4_ONLY mode returns only 'e4' hash."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hashes = ctrl.compute_hashes(b"data", "originator", "unknown-peer")
        assert "e4" in hashes
        assert "legacy" not in hashes

    def test_legacy_only_mode(self):
        """LEGACY_ONLY mode returns only 'legacy' hash."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.LEGACY_ONLY)
        hashes = ctrl.compute_hashes(b"data", "originator", "unknown-peer")
        assert "legacy" in hashes
        assert "e4" not in hashes

    def test_dual_hash_mode(self):
        """DUAL_HASH mode returns both 'e4' and 'legacy' hashes."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.DUAL_HASH)
        hashes = ctrl.compute_hashes(b"data", "originator", "unknown-peer")
        assert "e4" in hashes
        assert "legacy" in hashes

    def test_with_merkle_tree(self):
        """When a Merkle tree is bound, it computes trust-bound hashes."""
        merkle = TrustBoundMerkle()
        ctrl = CompatibilityController(
            default_mode=CompatibilityMode.DUAL_HASH, merkle=merkle,
        )
        hashes = ctrl.compute_hashes(b"data", "alice", "unknown-peer")
        assert hashes["e4"] == merkle.compute_leaf_hash(b"data", "alice")
        assert hashes["legacy"] == merkle.compute_leaf_hash_compat(b"data")


# ---------------------------------------------------------------------------
# Migration path
# ---------------------------------------------------------------------------

class TestMigrationPath:

    def test_peers_ready_for_e4_only(self):
        """Identifies peers in DUAL_HASH with E4_FULL capability."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.DUAL_HASH)
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_FULL)
        ctrl.process_handshake(hs)  # negotiated DUAL_HASH (because local is DUAL mode)
        # Actually local is E4_DUAL, remote is E4_FULL -> DUAL_HASH
        ready = ctrl.peers_ready_for_e4_only()
        assert "bob" in ready

    def test_upgrade_peer_legacy_to_dual(self):
        """Upgrade a peer from LEGACY to DUAL when capable."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.LEGACY_ONLY)
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_DUAL)
        ctrl.process_handshake(hs)  # negotiated DUAL_HASH
        # Now manually set peer to LEGACY for testing upgrade
        ctrl._negotiated["bob"] = CompatibilityMode.LEGACY_ONLY
        new_mode = ctrl.upgrade_peer("bob")
        assert new_mode == CompatibilityMode.DUAL_HASH

    def test_upgrade_peer_dual_to_e4_only(self):
        """Upgrade a peer from DUAL to E4_ONLY when both are E4_FULL."""
        ctrl = CompatibilityController(default_mode=CompatibilityMode.E4_ONLY)
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_FULL)
        ctrl.process_handshake(hs)
        # Force back to DUAL for test
        ctrl._negotiated["bob"] = CompatibilityMode.DUAL_HASH
        new_mode = ctrl.upgrade_peer("bob")
        assert new_mode == CompatibilityMode.E4_ONLY


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

class TestCompatIntrospection:

    def test_known_peers(self):
        """known_peers returns peer capabilities."""
        ctrl = CompatibilityController()
        hs = CompatHandshake(peer_id="bob", capability=PeerCapability.E4_FULL)
        ctrl.process_handshake(hs)
        peers = ctrl.known_peers()
        assert peers["bob"] == PeerCapability.E4_FULL

    def test_peer_count_by_mode(self):
        """peer_count_by_mode returns counts per mode."""
        ctrl = CompatibilityController()
        ctrl.process_handshake(
            CompatHandshake(peer_id="a", capability=PeerCapability.E4_FULL)
        )
        ctrl.process_handshake(
            CompatHandshake(peer_id="b", capability=PeerCapability.PRE_E4)
        )
        counts = ctrl.peer_count_by_mode()
        assert sum(counts.values()) == 2

    def test_bind_merkle(self):
        """bind_merkle injects a Merkle tree."""
        ctrl = CompatibilityController()
        merkle = TrustBoundMerkle()
        ctrl.bind_merkle(merkle)
        # Should use merkle for hash computation now

    def test_mode_to_capability_helper(self):
        """_mode_to_capability maps modes to capabilities correctly."""
        assert _mode_to_capability(CompatibilityMode.E4_ONLY) == PeerCapability.E4_FULL
        assert _mode_to_capability(CompatibilityMode.DUAL_HASH) == PeerCapability.E4_DUAL
        assert _mode_to_capability(CompatibilityMode.LEGACY_ONLY) == PeerCapability.PRE_E4
