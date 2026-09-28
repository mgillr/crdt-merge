# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Key ownership and revocation hardening tests."""
import hashlib
import hmac
import os
import sys

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


# -- Strict Ed25519: no HMAC fallback on a failed verification -------------
#
# KeyPair.verify used to fall back to HMAC-SHA256 keyed by the PUBLIC key
# whenever Ed25519 verification raised (including InvalidSignature), and
# KeyPair.sign / KeyPair.generate fell back to HMAC when cryptography was
# missing. hmac(public_key, message) is computable by anyone holding the
# public key, so it must never be accepted for an Ed25519 key.

def _public_key_tag(public_key, message):
    return hmac.new(public_key, message, hashlib.sha256).digest()


def _block_cryptography(monkeypatch):
    import cryptography.exceptions  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _e  # noqa: F401
    for name in [m for m in sys.modules
                 if m == "cryptography" or m.startswith("cryptography.")]:
        monkeypatch.setitem(sys.modules, name, None)


@pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
class TestStrictEd25519:

    def test_padded_public_key_tag_rejected(self):
        kp = KeyPair.generate()
        pub_only = KeyPair(public_key=kp.public_key)
        msg = b"attested update"
        assert pub_only.verify(msg, _public_key_tag(kp.public_key, msg) + b"\x00" * 32) is False

    def test_bare_public_key_tag_rejected(self):
        kp = KeyPair.generate()
        pub_only = KeyPair(public_key=kp.public_key)
        msg = b"attested update"
        assert pub_only.verify(msg, _public_key_tag(kp.public_key, msg)) is False

    def test_verify_peer_rejects_public_key_tag(self):
        alice = KeyManager("alice")
        bob = KeyManager("bob")
        bob.registry.register("alice", KeyPair(public_key=alice.current_key.public_key))
        msg = b"from alice"
        forged = _public_key_tag(alice.current_key.public_key, msg) + b"\x00" * 32
        assert bob.verify_peer("alice", msg, forged) is False
        assert bob.verify_peer("alice", msg, alice.sign(msg)) is True

    def test_revocation_forged_from_public_key_rejected(self):
        kp = KeyPair.generate()
        reg = PeerKeyRegistry()
        reg.register("alice", KeyPair(public_key=kp.public_key))
        payload = (
            kp.key_id.encode("utf-8") + b"\x00" + b"alice" + b"\x00"
            + b"compromise" + b"\x00" + b""
        )
        entry = RevocationEntry(
            key_id=kp.key_id, peer_id="alice", revoked_at=1.0,
            reason="compromise",
            proof=_public_key_tag(kp.public_key, payload) + b"\x00" * 32,
        )
        assert entry.verify(registry=reg) is False

    def test_sign_refuses_key_pair_that_is_not_ed25519(self):
        private = os.urandom(32)
        mismatched = KeyPair(public_key=hashlib.sha256(private).digest(), private_key=private)
        with pytest.raises(ValueError, match="Ed25519"):
            mismatched.sign(b"msg")

    def test_honest_signature_still_verifies(self):
        kp = KeyPair.generate()
        sig = kp.sign(b"hello")
        assert len(sig) == 64
        ed25519.Ed25519PublicKey.from_public_bytes(kp.public_key).verify(sig, b"hello")
        assert KeyPair(public_key=kp.public_key).verify(b"hello", sig) is True
        assert KeyPair(public_key=kp.public_key).verify(b"hello", sig[:32]) is False

    def test_missing_cryptography_generate_and_sign_fail_closed(self, monkeypatch):
        kp = KeyPair.generate()
        _block_cryptography(monkeypatch)
        with pytest.raises(RuntimeError, match="cryptography"):
            KeyPair.generate()
        with pytest.raises(RuntimeError, match="cryptography"):
            kp.sign(b"msg")

    def test_missing_cryptography_verify_fails_closed(self, monkeypatch):
        kp = KeyPair.generate()
        msg = b"msg"
        honest = kp.sign(msg)
        forged = _public_key_tag(kp.public_key, msg) + b"\x00" * 32
        _block_cryptography(monkeypatch)
        for sig in (forged, honest):
            with pytest.raises(RuntimeError, match="cryptography"):
                kp.verify(msg, sig)

    def test_hmac_mode_is_explicit_opt_in(self, monkeypatch):
        from crdt_merge.e4.resilience.key_manager import SCHEME_HMAC
        _block_cryptography(monkeypatch)  # HMAC mode needs no cryptography
        hk = KeyPair.generate(scheme=SCHEME_HMAC)
        assert hk.scheme == SCHEME_HMAC
        tag = hk.sign(b"msg")
        assert len(tag) == 32
        assert KeyPair(public_key=hk.public_key, scheme=SCHEME_HMAC).verify(b"msg", tag) is True
        assert hk.verify(b"msg", tag + b"\x00" * 32) is False  # exact tag only
        monkeypatch.undo()
        # the same public key without the explicit opt-in never takes the HMAC path
        assert KeyPair(public_key=hk.public_key).verify(b"msg", tag) is False
        assert KeyManager("carol", scheme=SCHEME_HMAC).current_key.scheme == SCHEME_HMAC

    def test_unknown_scheme_refused(self):
        with pytest.raises(ValueError, match="scheme"):
            KeyPair(public_key=b"x" * 32, scheme="none")
