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

"""Real Ed25519 verification tests for PCO.

Validates the three-tier signature verification:
  Tier 0: stub (legacy, no registry)
  Tier 1: HMAC (registry configured, no cryptography)
  Tier 2: Ed25519 (registry configured + cryptography available)
"""
import pytest
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    configure_ed25519_verification,
    has_real_crypto,
    _verify_ed25519,
)

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:
    _CRYPTO = False


class SimplePeerRegistry:
    """Minimal registry implementation for testing."""

    def __init__(self):
        self._keys = {}

    def register(self, peer_id: str, public_key: bytes):
        self._keys[peer_id] = public_key

    def get_public_key(self, peer_id: str):
        return self._keys.get(peer_id)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry after each test -- prevents test pollution."""
    yield
    configure_ed25519_verification(None)


# ── Tier 0: Stub (backward compat) ─────────────────────────────────────────

class TestStubBehavior:

    def test_stub_accepts_any_64_byte_sig(self):
        """Without registry: 64 bytes passes, anything else fails."""
        assert _verify_ed25519(b"\x00" * 64, b"msg", "any_peer") is True
        assert _verify_ed25519(b"\xff" * 64, b"msg", "any_peer") is True

    def test_stub_rejects_wrong_size(self):
        assert _verify_ed25519(b"\x00" * 63, b"msg", "peer") is False
        assert _verify_ed25519(b"\x00" * 65, b"msg", "peer") is False
        assert _verify_ed25519(b"", b"msg", "peer") is False

    def test_pco_build_works_without_registry(self):
        """Existing PCO construction still works."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-a",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="root",
            clock_snapshot=b"clk",
            trust_vector_hash="tvh",
            delta_bounds=[],
        )
        assert len(pco.to_wire()) == 128


# ── Tier 1: HMAC fallback ──────────────────────────────────────────────────

class TestHMACTier:

    def test_hmac_with_registry_verifies(self):
        """Registry with HMAC key accepts matching HMAC signature."""
        import hmac, hashlib
        reg = SimplePeerRegistry()
        shared_secret = b"A" * 32
        reg.register("peer-a", shared_secret)

        # Make verify see "no cryptography" by using non-32-byte key
        reg_non_ed = SimplePeerRegistry()
        reg_non_ed.register("peer-a", shared_secret + b"extra")  # 37 bytes, not Ed25519
        configure_ed25519_verification(reg_non_ed)

        message = b"signed message"
        valid_sig = hmac.new(shared_secret + b"extra", message, hashlib.sha256).digest() + b"\x00" * 32
        assert _verify_ed25519(valid_sig, message, "peer-a") is True

    def test_hmac_rejects_wrong_key(self):
        """Different HMAC key must fail verification."""
        import hmac, hashlib
        reg = SimplePeerRegistry()
        reg.register("peer-a", b"A" * 40)  # not 32, forces HMAC path
        configure_ed25519_verification(reg)

        message = b"signed message"
        wrong_sig = hmac.new(b"B" * 40, message, hashlib.sha256).digest() + b"\x00" * 32
        assert _verify_ed25519(wrong_sig, message, "peer-a") is False

    def test_hmac_rejects_unknown_peer(self):
        reg = SimplePeerRegistry()
        configure_ed25519_verification(reg)
        assert _verify_ed25519(b"\x00" * 64, b"msg", "unknown") is False


# ── Tier 2: Real Ed25519 ──────────────────────────────────────────────────

@pytest.mark.skipif(not _CRYPTO, reason="cryptography package not installed")
class TestEd25519Real:

    def test_real_ed25519_accepts_valid_signature(self):
        reg = SimplePeerRegistry()
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key_bytes = private_key.public_key().public_bytes_raw()
        reg.register("peer-a", public_key_bytes)
        configure_ed25519_verification(reg)

        message = b"signed message"
        signature = private_key.sign(message)
        assert _verify_ed25519(signature, message, "peer-a") is True

    def test_real_ed25519_rejects_tampered_message(self):
        reg = SimplePeerRegistry()
        private_key = ed25519.Ed25519PrivateKey.generate()
        reg.register("peer-a", private_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        signature = private_key.sign(b"original message")
        assert _verify_ed25519(signature, b"tampered message", "peer-a") is False

    def test_real_ed25519_rejects_wrong_peer(self):
        reg = SimplePeerRegistry()
        key_a = ed25519.Ed25519PrivateKey.generate()
        key_b = ed25519.Ed25519PrivateKey.generate()
        reg.register("peer-a", key_a.public_key().public_bytes_raw())
        reg.register("peer-b", key_b.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        message = b"from peer a"
        sig_a = key_a.sign(message)
        # Signature from peer-a verified against peer-b's key must fail
        assert _verify_ed25519(sig_a, message, "peer-b") is False
        # But verified against peer-a's key must pass
        assert _verify_ed25519(sig_a, message, "peer-a") is True

    def test_real_ed25519_rejects_random_bytes(self):
        """64 bytes of random data is NOT accepted as a valid signature."""
        reg = SimplePeerRegistry()
        private_key = ed25519.Ed25519PrivateKey.generate()
        reg.register("peer-a", private_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        # THIS is the key security fix: random 64 bytes no longer passes
        assert _verify_ed25519(b"\x00" * 64, b"message", "peer-a") is False
        assert _verify_ed25519(b"\xff" * 64, b"message", "peer-a") is False

    def test_real_ed25519_rejects_unknown_peer(self):
        reg = SimplePeerRegistry()
        key = ed25519.Ed25519PrivateKey.generate()
        reg.register("known", key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        signature = key.sign(b"msg")
        assert _verify_ed25519(signature, b"msg", "unknown") is False

    def test_pco_with_real_ed25519_roundtrip(self):
        """Full PCO build and verify cycle with real Ed25519."""
        reg = SimplePeerRegistry()
        private_key = ed25519.Ed25519PrivateKey.generate()
        reg.register("peer-a", private_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        def sign_fn(aggregate_hash: bytes) -> bytes:
            return private_key.sign(aggregate_hash)

        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-a",
            signing_fn=sign_fn,
            merkle_root="r",
            clock_snapshot=b"c",
            trust_vector_hash="t",
            delta_bounds=[],
        )
        # At Level 0, real signature verification should pass
        assert pco.verify(None, None, verification_level=0) is True

    def test_pco_with_fake_signature_fails_with_registry(self):
        """Old stub signatures (zero bytes) no longer work when registry is configured."""
        reg = SimplePeerRegistry()
        private_key = ed25519.Ed25519PrivateKey.generate()
        reg.register("peer-a", private_key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)

        # Old-style stub signing (zero bytes) is rejected
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-a",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="r",
            clock_snapshot=b"c",
            trust_vector_hash="t",
            delta_bounds=[],
        )
        assert pco.verify(None, None, verification_level=0) is False


# ── Configuration ─────────────────────────────────────────────────────────

class TestConfiguration:

    def test_has_real_crypto_reports_availability(self):
        assert has_real_crypto() == _CRYPTO

    def test_configure_then_reset(self):
        reg = SimplePeerRegistry()
        configure_ed25519_verification(reg)
        # Now requires registered peer
        assert _verify_ed25519(b"\x00" * 64, b"m", "unknown") is False

        configure_ed25519_verification(None)
        # Back to stub behavior
        assert _verify_ed25519(b"\x00" * 64, b"m", "unknown") is True

    def test_backward_compat_default_behavior(self):
        """By default, stub behavior is preserved for legacy tests."""
        # No registry configured — stub behavior
        assert _verify_ed25519(b"\x00" * 64, b"msg", "any") is True
