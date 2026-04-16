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

"""Observer authentication and timestamp binding for TrustEvidence.

Validates that evidence is bound to its observer cryptographically,
preventing spoofing and replay attacks.
"""
import time
import pytest
from crdt_merge.e4.proof_evidence import (
    TrustEvidence,
    configure_evidence_verification,
    pack_delta_proof,
)

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:
    _CRYPTO = False


class SimpleRegistry:
    def __init__(self):
        self._keys = {}

    def register(self, peer_id: str, key: bytes):
        self._keys[peer_id] = key

    def get_public_key(self, peer_id: str):
        return self._keys.get(peer_id)


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    configure_evidence_verification(None)


def make_valid_proof(target="eve"):
    delta_bytes = f"some bogus delta content from {target} node".encode("utf-8")
    wrong_hash = b"\x00" * 32
    return pack_delta_proof(wrong_hash, delta_bytes)


# ── Backward Compat ────────────────────────────────────────────────────────

class TestBackwardCompat:

    def test_unsigned_evidence_still_verifies(self):
        """Existing code that doesn't sign evidence still works."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
        )
        # No registry configured, no signature — verifies as before
        assert ev.verify() is True

    def test_no_signature_field_defaults_to_empty(self):
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
        )
        assert ev.observer_signature == b""
        assert ev.observer_public_key == b""


# ── Timestamp Binding (Replay Prevention) ─────────────────────────────────

class TestTimestampBinding:

    def test_fresh_evidence_verifies_with_max_age(self):
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
        )
        assert ev.verify(max_age_seconds=3600) is True

    def test_stale_evidence_rejected(self):
        """Evidence older than max_age is rejected -- prevents replay."""
        old_ts = time.time() - 86400  # 1 day old
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            timestamp=old_ts,
        )
        assert ev.verify(max_age_seconds=3600) is False

    def test_future_evidence_rejected(self):
        """Evidence from the future (beyond clock skew) is rejected."""
        future_ts = time.time() + 3600
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            timestamp=future_ts,
        )
        assert ev.verify(max_age_seconds=3600) is False

    def test_no_max_age_means_no_check(self):
        """Without max_age, old evidence still passes."""
        old_ts = time.time() - 86400
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            timestamp=old_ts,
        )
        assert ev.verify() is True  # no max_age


# ── HMAC Observer Authentication ──────────────────────────────────────────

class TestHMACObserverAuth:

    def test_hmac_signed_evidence_verifies(self):
        import hmac, hashlib
        shared_secret = b"observer_secret" + b"\x00" * 24

        def sign_fn(payload):
            return hmac.new(shared_secret, payload, hashlib.sha256).digest() + b"\x00" * 32

        reg = SimpleRegistry()
        reg.register("alice", shared_secret)
        configure_evidence_verification(reg)

        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            observer_signing_fn=sign_fn,
        )
        assert ev.verify(require_observer_auth=True) is True

    def test_hmac_spoofed_observer_rejected(self):
        """Attacker claims to be observer X but signs with their own key."""
        import hmac, hashlib
        alice_key = b"alice_real_secret_key" + b"\x00" * 12
        eve_key = b"eve_evil_key" + b"\x00" * 20

        def eve_sign(payload):
            # Eve signs with HER key but claims to be alice
            return hmac.new(eve_key, payload, hashlib.sha256).digest() + b"\x00" * 32

        reg = SimpleRegistry()
        reg.register("alice", alice_key)  # registry has Alice's real key
        configure_evidence_verification(reg)

        ev = TrustEvidence.create(
            observer="alice",  # spoofed observer
            target="eve", evidence_type="invalid_delta",
            dimension="integrity", amount=0.1, proof=make_valid_proof(),
            observer_signing_fn=eve_sign,  # but signed with eve's key
        )
        assert ev.verify(require_observer_auth=True) is False

    def test_auth_required_but_no_signature_fails(self):
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
        )
        assert ev.verify(require_observer_auth=True) is False


# ── Ed25519 Observer Authentication ──────────────────────────────────────

@pytest.mark.skipif(not _CRYPTO, reason="cryptography not installed")
class TestEd25519ObserverAuth:

    def test_real_signature_verifies(self):
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        def sign(payload):
            return alice_key.sign(payload)

        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            observer_signing_fn=sign,
        )
        assert ev.verify(require_observer_auth=True) is True

    def test_forged_signature_rejected(self):
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        # Attacker constructs evidence with garbage signature
        ev = TrustEvidence(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            proof_type="delta_verification",
            timestamp=time.time(),
            observer_signature=b"\x00" * 64,  # garbage
            observer_public_key=b"",
        )
        assert ev.verify(require_observer_auth=True) is False

    def test_tampered_fields_break_signature(self):
        """Changing any field after signing invalidates the signature."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            observer_signing_fn=lambda p: alice_key.sign(p),
        )

        # Tamper with the amount
        tampered = TrustEvidence(
            observer=ev.observer, target=ev.target,
            evidence_type=ev.evidence_type, dimension=ev.dimension,
            amount=0.9,  # tampered (was 0.1)
            proof=ev.proof, proof_type=ev.proof_type,
            timestamp=ev.timestamp,
            observer_signature=ev.observer_signature,
            observer_public_key=ev.observer_public_key,
        )
        assert tampered.verify(require_observer_auth=True) is False

    def test_auto_verify_when_signature_and_registry_present(self):
        """If signature exists + registry configured, verification is auto-enforced."""
        alice_key = ed25519.Ed25519PrivateKey.generate()
        reg = SimpleRegistry()
        reg.register("alice", alice_key.public_key().public_bytes_raw())
        configure_evidence_verification(reg)

        # Create evidence with forged signature
        ev = TrustEvidence(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            proof_type="delta_verification",
            timestamp=time.time(),
            observer_signature=b"\xff" * 64,  # forged
        )
        # Even without require_observer_auth, presence of sig + registry triggers check
        assert ev.verify() is False


# ── Configuration ─────────────────────────────────────────────────────────

class TestConfiguration:

    def test_configure_and_reset(self):
        reg = SimpleRegistry()
        configure_evidence_verification(reg)
        # When registry configured, signed evidence is validated
        ev = TrustEvidence(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_valid_proof(),
            proof_type="delta_verification",
            timestamp=time.time(),
            observer_signature=b"\xff" * 64,
        )
        assert ev.verify() is False  # bad signature caught

        configure_evidence_verification(None)
        # After reset, signature presence alone doesn't trigger check
        assert ev.verify() is True  # back to old behavior
