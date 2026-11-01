# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Battle-hardened attack suite against E4 v0.9.6.

Each test simulates a real cryptographic attack. Tests PASS when the
attack is defeated. All run with real crypto (cryptography + liboqs).
"""
import pytest
import time
import hashlib
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    configure_ed25519_verification,
)
from crdt_merge.e4.proof_evidence import (
    TrustEvidence, pack_delta_proof,
    configure_evidence_verification,
)
from crdt_merge.e4.resilience.key_manager import KeyPair, RevocationEntry, PeerKeyRegistry

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:
    _CRYPTO = False

try:
    from crdt_merge.e4.resilience.pq_signatures import Dilithium3Scheme, has_real_pq
    _HAS_PQ = has_real_pq()
except ImportError:
    _HAS_PQ = False


pytestmark = pytest.mark.skipif(not _CRYPTO, reason="cryptography required")


class Registry:
    def __init__(self):
        self._k = {}

    def register(self, pid, pub):
        self._k[pid] = pub

    def get_public_key(self, pid):
        return self._k.get(pid)


@pytest.fixture(autouse=True)
def reset():
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)


# ── Attack Class 1: Signature Forgery ─────────────────────────────────────

class TestSignatureForgery:

    def test_zero_signature_rejected_with_registry(self):
        """Old stub attack: submit b'\\x00' * 64 as signature."""
        key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        fake_pco = AggregateProofCarryingOperation.build(
            originator_id="alice",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="r", clock_snapshot=b"c",
            trust_vector_hash="t", delta_bounds=[],
        )
        assert fake_pco.verify(None, None, verification_level=0) is False

    def test_random_64_bytes_rejected(self):
        """64 random bytes does NOT pass as a valid signature."""
        import os
        key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        fake_pco = AggregateProofCarryingOperation.build(
            originator_id="alice",
            signing_fn=lambda h: os.urandom(64),
            merkle_root="r", clock_snapshot=b"c",
            trust_vector_hash="t", delta_bounds=[],
        )
        assert fake_pco.verify(None, None, verification_level=0) is False

    def test_signature_from_different_key_rejected(self):
        """Alice signs with her key, claim to be bob -- rejected."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        bob_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        reg.register("bob", bob_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        # Alice's key signs, but claims to be bob
        evil_pco = AggregateProofCarryingOperation.build(
            originator_id="bob",  # spoofed
            signing_fn=lambda h: alice_key.sign(h),  # alice's key
            merkle_root="r", clock_snapshot=b"c",
            trust_vector_hash="t", delta_bounds=[],
        )
        assert evil_pco.verify(None, None, verification_level=0) is False


# ── Attack Class 2: Evidence Spoofing ────────────────────────────────────

class TestEvidenceSpoofing:

    def test_unsigned_evidence_rejected_with_registry(self):
        """Registry configured -- evidence without signature fails auth check."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        evidence = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"some content from eve node"),
        )
        assert evidence.verify(require_observer_auth=True) is False

    def test_observer_spoofing_rejected(self):
        """Eve signs with her key but claims observer=alice -- rejected."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        eve_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        reg.register("eve", eve_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        forged = TrustEvidence.create(
            observer="alice",  # spoofed
            target="bob",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from bob node"),
            observer_signing_fn=lambda p: eve_key.sign(p),  # eve's key
        )
        assert forged.verify(require_observer_auth=True) is False

    def test_tampered_amount_breaks_signature(self):
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from eve node"),
            observer_signing_fn=lambda p: alice_key.sign(p),
        )

        # Tamper amount
        tampered = TrustEvidence(
            observer=ev.observer, target=ev.target,
            evidence_type=ev.evidence_type, dimension=ev.dimension,
            amount=0.95,  # tampered
            proof=ev.proof, proof_type=ev.proof_type,
            timestamp=ev.timestamp,
            observer_signature=ev.observer_signature,
            observer_public_key=ev.observer_public_key,
        )
        assert tampered.verify(require_observer_auth=True) is False


# ── Attack Class 3: Replay Attacks ───────────────────────────────────────

class TestReplayAttacks:

    def test_stale_evidence_rejected_with_max_age(self):
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        old = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from eve node"),
            observer_signing_fn=lambda p: alice_key.sign(p),
            timestamp=time.time() - 86400,  # 1 day old
        )
        assert old.verify(max_age_seconds=3600) is False

    def test_future_evidence_rejected(self):
        future = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from eve node"),
            timestamp=time.time() + 7200,  # 2hrs in future
        )
        assert future.verify(max_age_seconds=3600) is False


# ── Attack Class 4: Revocation Forgery ───────────────────────────────────

class TestRevocationForgery:

    def test_empty_proof_revocation_rejected(self):
        entry = RevocationEntry(
            key_id="k", peer_id="p",
            revoked_at=time.time(), proof=b"",
        )
        assert entry.verify() is False

    def test_garbage_proof_rejected_with_registry(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", kp)

        entry = RevocationEntry(
            key_id=kp.key_id, peer_id="alice",
            revoked_at=time.time(), reason="test",
            proof=b"\xff" * 64,  # garbage
        )
        assert entry.verify(registry=reg) is False

    def test_wrong_key_id_revocation_rejected(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", kp)

        # Sign a valid-shaped payload with right key but wrong key_id
        fake_payload = b"wrong_id\x00alice\x00test\x00"
        entry = RevocationEntry(
            key_id="wrong_key_id",  # doesn't exist
            peer_id="alice",
            revoked_at=time.time(), reason="test",
            proof=kp.sign(fake_payload),
        )
        assert entry.verify(registry=reg) is False


# ── Attack Class 5: Real Post-Quantum Crypto ─────────────────────────────

@pytest.mark.skipif(not _HAS_PQ, reason="liboqs not available")
class TestPQCrypto:

    def test_ml_dsa_65_signatures_work(self):
        scheme = Dilithium3Scheme()
        priv, pub = scheme.generate_keypair()
        sig = scheme.sign(priv, b"msg")
        assert scheme.verify(pub, b"msg", sig) is True

    def test_ml_dsa_65_rejects_forged_signature(self):
        scheme = Dilithium3Scheme()
        _, pub_a = scheme.generate_keypair()
        priv_b, _ = scheme.generate_keypair()
        # Try to forge with different key
        sig = scheme.sign(priv_b, b"msg")
        assert scheme.verify(pub_a, b"msg", sig) is False

    def test_ml_dsa_65_rejects_tampered_message(self):
        scheme = Dilithium3Scheme()
        priv, pub = scheme.generate_keypair()
        sig = scheme.sign(priv, b"original")
        assert scheme.verify(pub, b"tampered", sig) is False


# ── Attack Class 6: Full Stack Integration ───────────────────────────────

class TestFullStackHardening:

    def test_full_adversarial_chain_blocked(self):
        """
        Attacker tries every trick:
          1. Forge PCO signature (blocked at PCO verify)
          2. Forge observer signature (blocked at evidence verify)
          3. Replay old evidence (blocked at age check)
          4. Forge revocation (blocked at registry verify)
        """
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)
        configure_evidence_verification(reg)

        # Attack 1: fake PCO
        fake_pco = AggregateProofCarryingOperation.build(
            originator_id="alice",
            signing_fn=lambda h: b"\xff" * 64,
            merkle_root="r", clock_snapshot=b"c",
            trust_vector_hash="t", delta_bounds=[],
        )
        assert fake_pco.verify(None, None, verification_level=0) is False

        # Attack 2: unsigned evidence with registry
        unsigned = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from eve node"),
        )
        assert unsigned.verify(require_observer_auth=True) is False

        # Attack 3: old evidence replay
        old_sig_ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1,
            proof=pack_delta_proof(b"\x00" * 32, b"data from eve node"),
            observer_signing_fn=lambda p: alice_key.sign(p),
            timestamp=time.time() - 100000,
        )
        assert old_sig_ev.verify(max_age_seconds=3600) is False

        # Attack 4: fake revocation
        kp = KeyPair.generate()
        peer_reg = PeerKeyRegistry()
        peer_reg.register("alice", kp)
        fake_revoc = RevocationEntry(
            key_id="nonexistent", peer_id="alice",
            revoked_at=time.time(), proof=b"\xff" * 64,
        )
        assert fake_revoc.verify(registry=peer_reg) is False
