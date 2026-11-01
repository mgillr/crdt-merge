# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Origin-bound trust delta tests.

Verifies that trust deltas are cryptographically bound to their
originator via both the PCO signature and the embedded evidence
signature. Spoofed origins are rejected at the lattice boundary.
"""
import pytest
import hashlib
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.typed_trust import TypedTrustScore
from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import (
    TrustEvidence,
    pack_delta_proof,
    configure_evidence_verification,
)

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:
    _CRYPTO = False


class SimpleRegistry:
    def __init__(self):
        self._keys = {}

    def register(self, peer_id: str, public_key: bytes):
        self._keys[peer_id] = public_key

    def get_public_key(self, peer_id: str):
        return self._keys.get(peer_id)


def make_delta_proof(target="eve"):
    delta_bytes = f"some bogus delta content from {target} node".encode("utf-8")
    return pack_delta_proof(b"\x00" * 32, delta_bytes)


@pytest.fixture(autouse=True)
def reset_registries():
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)


@pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
class TestOriginBinding:
    """Trust deltas are cryptographically tied to their origin."""

    def test_real_signed_delta_pco_verifies(self):
        """Alice signs a trust delta, the PCO signature verifies against her key."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        alice_pub = alice_key.public_key().public_bytes_raw()

        reg = SimpleRegistry()
        reg.register("alice", alice_pub)
        configure_ed25519_verification(reg)

        # Alice's lattice signs with her real key
        alice_lattice = DeltaTrustLattice(
            "alice", initial_peers={"alice", "eve"},
            signing_fn=lambda h: alice_key.sign(h),
        )

        evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_delta_proof("eve"),
        )
        delta = alice_lattice.observe_and_propagate(evidence)

        # The delta's PCO signature verifies at level 0 (sig-only)
        assert delta.pco.verify(None, None, verification_level=0) is True

    def test_forged_pco_signature_rejected_at_pco_layer(self):
        """Attacker forges PCO with fake signature -- PCO verify fails."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        # Mallory crafts a trust delta claiming to be alice, but with fake sig
        mallory_lattice = DeltaTrustLattice(
            "alice",  # spoofed origin
            initial_peers={"alice", "eve"},
            signing_fn=lambda h: b"\x00" * 64,  # fake sig, not from alice's key
        )
        evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_delta_proof("eve"),
        )
        delta = mallory_lattice.observe_and_propagate(evidence)

        # The PCO signature does NOT verify against alice's real key
        assert delta.pco.verify(None, None, verification_level=0) is False

    def test_forged_evidence_observer_rejected(self):
        """Attacker submits evidence claiming another observer -- rejected."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        eve_key = ed25519.Ed25519PrivateKey.generate()

        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        reg.register("eve", eve_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)
        configure_evidence_verification(reg)

        # Eve crafts evidence claiming alice observed bob misbehaving
        # Eve signs with HER key, but claims observer="alice"
        forged_evidence = TrustEvidence.create(
            observer="alice",  # spoofed
            target="bob",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_delta_proof("bob"),
            observer_signing_fn=lambda p: eve_key.sign(p),  # Eve's key
        )

        # Even with verified PCO origin (Eve's own lattice), the evidence
        # fails because the observer signature doesn't match alice's key
        # The verify call enforces require_observer_auth via registry
        assert forged_evidence.verify() is False

    def test_replay_of_old_signed_delta_rejected(self):
        """Old evidence replayed -- can be rejected with max_age_seconds."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        import time
        old_ts = time.time() - 86400  # 1 day old

        old_evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_delta_proof("eve"),
            observer_signing_fn=lambda p: alice_key.sign(p),
            timestamp=old_ts,
        )

        # Fresh check passes (signature valid)
        assert old_evidence.verify() is True
        # With max_age enforcement, stale evidence rejected
        assert old_evidence.verify(max_age_seconds=3600) is False


class TestBackwardCompat:
    """Existing tests using stub signatures still work."""

    def test_unsigned_delta_flow_unchanged(self):
        """No registry configured -- stub path works as before."""
        lattice = DeltaTrustLattice(
            "alice", initial_peers={"alice", "eve"},
            signing_fn=lambda h: b"\x00" * 64,
        )
        evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_delta_proof("eve"),
        )
        delta = lattice.observe_and_propagate(evidence)
        assert delta is not None
        assert delta.pco.originator_id == "alice"
