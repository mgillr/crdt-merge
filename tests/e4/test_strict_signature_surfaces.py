# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""Fail-closed signature verification across the E4 surfaces.

Each test pins one rule:

- PCO signatures: no registry means verification is not configured, which
  is an error.  Unsigned mode is explicit opt-in.  No HMAC tier exists.
- Evidence: the observer key comes from the registry only, a registry
  means every piece of evidence must be signed, and attestation signatures
  inside equivocation proofs are verified.  No HMAC tier exists.
- Signature schemes: HMAC is not a default, is not the classical half of
  HybridScheme, and is keyed by a shared secret rather than a public key.
- Revocations: without a registry, a revocation proof does not verify.

New names are imported inside the tests so that this module still loads
against older code.
"""

import hashlib
import hmac
import os
import sys
import time

import pytest

from crdt_merge.e4 import pco as pco_mod
from crdt_merge.e4 import proof_evidence as ev_mod
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    configure_ed25519_verification,
)
from crdt_merge.e4.proof_evidence import (
    TrustEvidence,
    configure_evidence_verification,
    pack_attestation_pair,
    pack_delta_proof,
)
from crdt_merge.e4.resilience.key_manager import RevocationEntry

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _CRYPTO = True
except ImportError:  # pragma: no cover
    _CRYPTO = False

pytestmark = pytest.mark.skipif(not _CRYPTO, reason="cryptography required")


class Registry:
    def __init__(self):
        self._k = {}

    def register(self, pid, pub):
        self._k[pid] = pub

    def get_public_key(self, pid):
        return self._k.get(pid)


@pytest.fixture
def strict():
    """The shipped defaults: nothing configured, nothing opted into."""
    configure_ed25519_verification(None)
    configure_evidence_verification(None)
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)


def _block_cryptography(monkeypatch):
    import cryptography.exceptions  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _e  # noqa: F401
    for name in [m for m in sys.modules
                 if m == "cryptography" or m.startswith("cryptography.")]:
        monkeypatch.setitem(sys.modules, name, None)
    for mod in (pco_mod, ev_mod):
        monkeypatch.setattr(mod, "_HAS_CRYPTO", False, raising=False)


def _tag(key, message):
    return hmac.new(key, message, hashlib.sha256).digest()


def _pco(originator, signing_fn):
    return AggregateProofCarryingOperation.build(
        originator_id=originator, signing_fn=signing_fn,
        merkle_root="r", clock_snapshot=b"c", trust_vector_hash="t",
        delta_bounds=[],
    )


def _evidence(observer="alice", target="eve", signing_fn=None, public_key=b"",
              evidence_type="invalid_delta", proof=None):
    return TrustEvidence.create(
        observer=observer, target=target, evidence_type=evidence_type,
        dimension="integrity", amount=0.1,
        proof=proof if proof is not None else pack_delta_proof(
            b"\x00" * 32, f"content from {target} node".encode()),
        observer_signing_fn=signing_fn, observer_public_key=public_key,
    )


# -- PCO signatures ---------------------------------------------------------

class TestPcoFailsClosed:

    def test_no_registry_is_an_error_not_an_accept(self, strict):
        p = _pco("alice", lambda h: b"\x00" * 64)
        with pytest.raises(RuntimeError, match="not configured"):
            p.verify(None, None, verification_level=0)

    def test_public_key_tag_rejected_for_non_ed25519_key(self, strict):
        reg = Registry()
        reg.register("alice", b"A" * 33)
        configure_ed25519_verification(reg)
        p = _pco("alice", lambda h: _tag(b"A" * 33, h) + b"\x00" * 32)
        assert p.verify(None, None, verification_level=0) is False

    def test_missing_cryptography_with_registry_raises(self, strict, monkeypatch):
        key = ed25519.Ed25519PrivateKey.generate()
        pub = key.public_key().public_bytes_raw()
        reg = Registry()
        reg.register("alice", pub)
        configure_ed25519_verification(reg)
        p = _pco("alice", lambda h: _tag(pub, h) + b"\x00" * 32)
        _block_cryptography(monkeypatch)
        with pytest.raises(RuntimeError, match="cryptography"):
            p.verify(None, None, verification_level=0)

    def test_unsigned_mode_is_explicit_opt_in(self, strict):
        configure_ed25519_verification(None, allow_unsigned=True)
        assert _pco("alice", lambda h: b"\x00" * 64).verify(
            None, None, verification_level=0) is True
        configure_ed25519_verification(None)
        with pytest.raises(RuntimeError, match="not configured"):
            _pco("alice", lambda h: b"\x00" * 64).verify(None, None, verification_level=0)
        with pytest.raises(ValueError):
            configure_ed25519_verification(Registry(), allow_unsigned=True)

    def test_real_signature_still_verifies(self, strict):
        """Control: passes before and after."""
        key = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", key.public_key().public_bytes_raw())
        configure_ed25519_verification(reg)
        assert _pco("alice", key.sign).verify(None, None, verification_level=0) is True


# -- Evidence observer authentication ----------------------------------------

class TestEvidenceFailsClosed:

    def test_no_registry_is_an_error_not_an_accept(self, strict):
        with pytest.raises(RuntimeError, match="not configured"):
            _evidence().verify()

    def test_embedded_key_not_trusted_for_unregistered_observer(self, strict):
        mallory = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", ed25519.Ed25519PrivateKey.generate().public_key().public_bytes_raw())
        configure_evidence_verification(reg)
        ev = _evidence(observer="carol", signing_fn=mallory.sign,
                       public_key=mallory.public_key().public_bytes_raw())
        assert ev.verify(require_observer_auth=True) is False

    def test_embedded_key_not_trusted_without_registry(self, strict):
        mallory = ed25519.Ed25519PrivateKey.generate()
        configure_evidence_verification(None, allow_unauthenticated=True)
        ev = _evidence(observer="alice", signing_fn=mallory.sign,
                       public_key=mallory.public_key().public_bytes_raw())
        assert ev.verify(require_observer_auth=True) is False

    def test_unsigned_evidence_rejected_once_a_registry_is_set(self, strict):
        alice = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice.public_key().public_bytes_raw())
        configure_evidence_verification(reg)
        assert _evidence(observer="alice").verify() is False

    def test_public_key_tag_rejected_for_non_ed25519_key(self, strict):
        reg = Registry()
        reg.register("alice", b"K" * 33)
        configure_evidence_verification(reg)
        forged = _evidence(observer="alice",
                           signing_fn=lambda p: _tag(b"K" * 33, p) + b"\x00" * 32)
        assert forged.verify(require_observer_auth=True) is False

    def test_missing_cryptography_with_registry_raises(self, strict, monkeypatch):
        alice = ed25519.Ed25519PrivateKey.generate()
        pub = alice.public_key().public_bytes_raw()
        reg = Registry()
        reg.register("alice", pub)
        configure_evidence_verification(reg)
        forged = _evidence(observer="alice", signing_fn=lambda p: _tag(pub, p) + b"\x00" * 32)
        _block_cryptography(monkeypatch)
        with pytest.raises(RuntimeError, match="cryptography"):
            forged.verify(require_observer_auth=True)

    def test_unauthenticated_mode_is_explicit_opt_in(self, strict):
        configure_evidence_verification(None, allow_unauthenticated=True)
        assert _evidence().verify() is True
        configure_evidence_verification(None)
        with pytest.raises(RuntimeError, match="not configured"):
            _evidence().verify()
        with pytest.raises(ValueError):
            configure_evidence_verification(Registry(), allow_unauthenticated=True)

    def test_signed_evidence_still_verifies(self, strict):
        """Control: passes before and after."""
        alice = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice.public_key().public_bytes_raw())
        configure_evidence_verification(reg)
        ev = _evidence(observer="alice", signing_fn=alice.sign)
        assert ev.verify(require_observer_auth=True) is True


class TestEquivocationAttestations:

    @staticmethod
    def _blob(signer, seq, content, sig):
        return f"{signer}\x00{seq}\x00{content}\x00".encode() + sig

    def _setup(self):
        alice = ed25519.Ed25519PrivateKey.generate()
        eve = ed25519.Ed25519PrivateKey.generate()
        reg = Registry()
        reg.register("alice", alice.public_key().public_bytes_raw())
        reg.register("eve", eve.public_key().public_bytes_raw())
        configure_evidence_verification(reg)
        return alice, eve

    def test_unsigned_attestations_do_not_convict(self, strict):
        alice, _ = self._setup()
        proof = pack_attestation_pair(
            self._blob("eve", 1, "A", b"\x00" * 64),
            self._blob("eve", 1, "B", b"\x00" * 64),
        )
        ev = _evidence(observer="alice", target="eve", evidence_type="equivocation",
                       proof=proof, signing_fn=alice.sign)
        assert ev.verify(require_observer_auth=True) is False

    def test_attestations_signed_by_the_accused_convict(self, strict):
        from crdt_merge.e4.proof_evidence import sign_attestation
        alice, eve = self._setup()
        proof = pack_attestation_pair(
            sign_attestation("eve", 1, "A", eve.sign),
            sign_attestation("eve", 1, "B", eve.sign),
        )
        ev = _evidence(observer="alice", target="eve", evidence_type="equivocation",
                       proof=proof, signing_fn=alice.sign)
        assert ev.verify(require_observer_auth=True) is True

    def test_attestations_signed_by_someone_else_do_not_convict(self, strict):
        alice, _ = self._setup()

        def by_alice(content):
            text = f"eve\x001\x00{content}\x00".encode()
            return text + alice.sign(b"crdt-merge/e4/attestation/v1\x00" + text)

        proof = pack_attestation_pair(by_alice("A"), by_alice("B"))
        ev = _evidence(observer="alice", target="eve", evidence_type="equivocation",
                       proof=proof, signing_fn=alice.sign)
        assert ev.verify(require_observer_auth=True) is False


# -- Signature schemes ---------------------------------------------------------

class TestSchemes:

    def test_hmac_is_not_a_registered_default(self):
        from crdt_merge.e4.resilience.pq_signatures import available_schemes
        assert "hmac-sha256" not in available_schemes()

    def test_hybrid_classical_half_cannot_be_forged_from_public_key(self):
        import struct
        from crdt_merge.e4.resilience.pq_signatures import HybridScheme
        h = HybridScheme()
        priv, pub = h.generate_keypair()
        msg = b"attested update"
        genuine = h.sign(priv, msg)
        c_pub = pub[2:2 + struct.unpack("!H", pub[:2])[0]]
        c_len = struct.unpack("!H", genuine[:2])[0]
        pq_sig = genuine[2 + c_len:]
        forged_c = _tag(c_pub, msg)
        forged = struct.pack("!H", len(forged_c)) + forged_c + pq_sig
        assert h.verify(pub, msg, genuine) is True
        assert h.verify(pub, msg, forged) is False

    def test_hmac_scheme_keyed_by_shared_secret(self):
        from crdt_merge.e4.resilience.pq_signatures import HmacScheme
        s = HmacScheme()
        secret, verify_key = s.generate_keypair()
        assert verify_key == secret
        msg = b"m"
        assert s.verify(verify_key, msg, s.sign(secret, msg)) is True
        derived = hashlib.sha256(secret).digest()
        assert s.verify(secret, msg, _tag(derived, msg)) is False

    def test_ed25519_scheme(self, monkeypatch):
        from crdt_merge.e4.resilience.pq_signatures import Ed25519Scheme, get_scheme
        s = get_scheme("ed25519")
        assert isinstance(s, Ed25519Scheme)
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"m")
        assert len(sig) == 64 and s.verify(pub, b"m", sig) is True
        assert s.verify(pub, b"x", sig) is False
        assert s.verify(pub, b"m", _tag(pub, b"m") + b"\x00" * 32) is False
        assert s.generate_keypair(b"s" * 32) == s.generate_keypair(b"s" * 32)
        _block_cryptography(monkeypatch)
        with pytest.raises(RuntimeError, match="cryptography"):
            s.verify(pub, b"m", sig)
        with pytest.raises(RuntimeError, match="cryptography"):
            s.sign(priv, b"m")


# -- Revocations ---------------------------------------------------------------

class TestRevocation:

    def test_no_registry_does_not_verify(self):
        entry = RevocationEntry(key_id="k", peer_id="p", revoked_at=time.time(),
                                proof=os.urandom(64))
        assert entry.verify() is False
