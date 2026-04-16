# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Key ownership and revocation hardening tests."""
import pytest
from crdt_merge.e4.resilience.key_manager import KeyPair, KeyManager, RevocationEntry, PeerKeyRegistry

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:
    _CRYPTO = False


class TestKeyPairRealCrypto:

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_generate_produces_ed25519_keys(self):
        kp = KeyPair.generate()
        assert len(kp.public_key) == 32
        assert len(kp.private_key) == 32

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_sign_produces_real_ed25519_signature(self):
        kp = KeyPair.generate()
        sig = kp.sign(b"test message")
        assert len(sig) == 64  # Ed25519 signature is 64 bytes

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_verify_real_ed25519(self):
        kp = KeyPair.generate()
        sig = kp.sign(b"hello")
        assert kp.verify(b"hello", sig) is True

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_verify_rejects_tampered_message(self):
        kp = KeyPair.generate()
        sig = kp.sign(b"original")
        assert kp.verify(b"tampered", sig) is False

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_verify_rejects_wrong_key(self):
        kp_a = KeyPair.generate()
        kp_b = KeyPair.generate()
        sig = kp_a.sign(b"msg")
        # Verify against wrong public key
        assert kp_b.verify(b"msg", sig) is False

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_sign_without_private_key_raises(self):
        kp = KeyPair.generate()
        pub_only = KeyPair(public_key=kp.public_key)
        with pytest.raises(ValueError):
            pub_only.sign(b"msg")


class TestRevocationProof:

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_revocation_with_real_signature_verifies(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", kp)

        # Sign the revocation payload with the key being revoked
        payload = (
            kp.key_id.encode("utf-8") + b"\x00"
            + b"alice\x00"
            + b"compromised\x00"
            + b""  # no successor
        )
        proof = kp.sign(payload)

        entry = RevocationEntry(
            key_id=kp.key_id, peer_id="alice",
            revoked_at=1.0, reason="compromised",
            proof=proof,
        )
        assert entry.verify(registry=reg) is True

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_revocation_with_forged_proof_rejected(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", kp)

        entry = RevocationEntry(
            key_id=kp.key_id, peer_id="alice",
            revoked_at=1.0, reason="compromised",
            proof=b"\x00" * 64,  # forged
        )
        assert entry.verify(registry=reg) is False

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_revocation_wrong_key_id_rejected(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", kp)

        entry = RevocationEntry(
            key_id="nonexistent_key_id", peer_id="alice",
            revoked_at=1.0, reason="test",
            proof=kp.sign(b"whatever"),
        )
        assert entry.verify(registry=reg) is False

    def test_revocation_backward_compat_no_registry(self):
        """Without registry, any non-empty proof passes (backward compat)."""
        entry = RevocationEntry(
            key_id="k", peer_id="p",
            revoked_at=1.0, proof=b"\x01",
        )
        assert entry.verify() is True

    def test_revocation_empty_proof_fails(self):
        entry = RevocationEntry(
            key_id="k", peer_id="p",
            revoked_at=1.0, proof=b"",
        )
        assert entry.verify() is False


class TestKeyManagerLifecycle:

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_key_rotation_with_real_crypto(self):
        mgr = KeyManager("alice")
        old_key = mgr.current_key

        new_key, revocation = mgr.rotate_key()
        assert new_key.key_id != old_key.key_id
        # Revocation proof should verify against the registry
        assert revocation.verify(registry=mgr.registry) is True

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_sign_and_verify_peer(self):
        mgr_a = KeyManager("alice")
        mgr_b = KeyManager("bob")

        # Bob registers Alice's key
        mgr_b.registry.register("alice", KeyPair(public_key=mgr_a.current_key.public_key))

        # Alice signs a message
        sig = mgr_a.sign(b"from alice")
        # Bob verifies
        assert mgr_b.verify_peer("alice", b"from alice", sig) is True
        assert mgr_b.verify_peer("alice", b"tampered", sig) is False

    @pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
    def test_emergency_revoke(self):
        mgr = KeyManager("alice")
        old_key_id = mgr.current_key.key_id
        entry = mgr.emergency_revoke(reason="key leaked")
        assert entry.key_id == old_key_id
        assert mgr.registry.revocation_count >= 1
        assert mgr.registry.is_revoked(old_key_id)
