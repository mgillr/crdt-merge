# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""The legacy unsigned / unauthenticated modes are escape hatches for tests.

These tests run WITHOUT the conftest opt-ins: the ``strict`` fixture clears
both modes and removes the guard variable, so they see exactly what a user
of the library sees.  They prove that

* the default rejects an arbitrary 64-byte signature (PCO and evidence),
* switching an opt-in on without the guard raises, and
* switching it on with the guard works but warns loudly.
"""

import logging
import os
import time
import warnings

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
    pack_delta_proof,
)
from crdt_merge.e4.signing import SignatureVerificationNotConfigured

GUARD = "CRDT_MERGE_INSECURE_TEST_MODE"
ARBITRARY_SIGNATURE = b"\x00" * 64


class _Registry:
    def __init__(self):
        self._keys = {}

    def register(self, peer_id, key):
        self._keys[peer_id] = key

    def get_public_key(self, peer_id):
        return self._keys[peer_id]


@pytest.fixture(autouse=True)
def strict(_explicit_legacy_unsigned_mode, monkeypatch):
    """Undo the conftest opt-ins: strict defaults, no guard variable."""
    configure_ed25519_verification(None)
    configure_evidence_verification(None)
    monkeypatch.delenv(GUARD, raising=False)
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)


def _pco(signing_fn=lambda h: ARBITRARY_SIGNATURE):
    return AggregateProofCarryingOperation.build(
        originator_id="alice", signing_fn=signing_fn,
        merkle_root="r", clock_snapshot=b"c", trust_vector_hash="t",
        delta_bounds=[],
    )


def _evidence(signature=ARBITRARY_SIGNATURE):
    ev = TrustEvidence.create(
        observer="alice", target="eve", evidence_type="invalid_delta",
        dimension="integrity", amount=0.1,
        proof=pack_delta_proof(b"\x00" * 32, b"content from eve node"),
    )
    object.__setattr__(ev, "observer_signature", signature)
    return ev


# -- 1. an arbitrary 64-byte signature is rejected by default --------------

class TestDefaultRejectsArbitrarySignature:

    def test_pco_default_raises(self):
        with pytest.raises(SignatureVerificationNotConfigured):
            _pco().verify(None, None, verification_level=0)

    def test_pco_with_registry_rejects(self):
        reg = _Registry()
        reg.register("alice", b"A" * 32)
        configure_ed25519_verification(reg)
        assert _pco().verify(None, None, verification_level=0) is False

    def test_evidence_default_raises(self):
        with pytest.raises(SignatureVerificationNotConfigured):
            _evidence().verify()

    def test_evidence_with_registry_rejects(self):
        reg = _Registry()
        reg.register("alice", b"A" * 32)
        configure_evidence_verification(reg)
        assert _evidence().verify() is False
        assert _evidence().verify(require_observer_auth=True) is False

    def test_attestation_default_rejects(self):
        op = {"signer": "eve", "raw": b"x" * 80, "signature": ARBITRARY_SIGNATURE}
        assert ev_mod._verify_attestation_sig(op) is False


# -- 2. an opt-in without the guard raises -----------------------------------

class TestOptInRequiresGuard:

    def test_unsigned_without_guard_raises(self):
        with pytest.raises(RuntimeError, match=GUARD):
            configure_ed25519_verification(None, allow_unsigned=True)
        # nothing was activated
        with pytest.raises(SignatureVerificationNotConfigured):
            _pco().verify(None, None, verification_level=0)

    def test_unauthenticated_without_guard_raises(self):
        with pytest.raises(RuntimeError, match=GUARD):
            configure_evidence_verification(None, allow_unauthenticated=True)
        with pytest.raises(SignatureVerificationNotConfigured):
            _evidence().verify()

    @pytest.mark.parametrize("value", ["", "0", "true", "yes", "2", " 1"])
    def test_only_the_exact_value_one_counts(self, monkeypatch, value):
        monkeypatch.setenv(GUARD, value)
        with pytest.raises(RuntimeError, match=GUARD):
            configure_ed25519_verification(None, allow_unsigned=True)
        with pytest.raises(RuntimeError, match=GUARD):
            configure_evidence_verification(None, allow_unauthenticated=True)

    def test_registry_plus_opt_in_is_still_a_value_error(self):
        with pytest.raises(ValueError):
            configure_ed25519_verification(_Registry(), allow_unsigned=True)
        with pytest.raises(ValueError):
            configure_evidence_verification(_Registry(), allow_unauthenticated=True)


# -- 3. an opt-in with the guard works and warns ------------------------------

class TestOptInWithGuardWarns:

    @pytest.fixture(autouse=True)
    def _guard(self, monkeypatch):
        monkeypatch.setenv(GUARD, "1")

    def test_unsigned_warns_and_logs(self, caplog):
        with caplog.at_level(logging.WARNING):
            with pytest.warns(UserWarning, match="INSECURE") as rec:
                configure_ed25519_verification(None, allow_unsigned=True)
        assert any(r.levelno == logging.WARNING and "allow_unsigned" in r.getMessage()
                   for r in caplog.records)
        assert type(rec[0].message).__name__ == "InsecureConfigurationWarning"
        # and it really is the legacy mode: any 64-byte value passes
        assert pco_mod._verify_ed25519(ARBITRARY_SIGNATURE, b"m", "x") is True

    def test_unauthenticated_warns_and_logs(self, caplog):
        with caplog.at_level(logging.WARNING):
            with pytest.warns(UserWarning, match="INSECURE") as rec:
                configure_evidence_verification(None, allow_unauthenticated=True)
        assert any(r.levelno == logging.WARNING and "allow_unauthenticated" in r.getMessage()
                   for r in caplog.records)
        assert type(rec[0].message).__name__ == "InsecureConfigurationWarning"
        assert _evidence().verify() is True

    def test_strict_configuration_does_not_warn(self):
        reg = _Registry()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            configure_ed25519_verification(reg)
            configure_ed25519_verification(None)
            configure_evidence_verification(reg)
            configure_evidence_verification(None)
