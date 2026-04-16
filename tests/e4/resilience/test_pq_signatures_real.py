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

"""Tests for real post-quantum signatures via liboqs.

DilithiumLite is honestly documented as hash-based (not PQ).
Dilithium3Scheme provides real NIST Level 3 PQ when oqs-python installed.
"""
import pytest
from crdt_merge.e4.resilience.pq_signatures import (
    DilithiumLite,
    Dilithium3Scheme,
    HmacScheme,
    has_real_pq,
    get_scheme,
    available_schemes,
)


class TestDilithiumLiteHonesty:
    """DilithiumLite is preserved for backward compat but honestly documented."""

    def test_security_level_is_honest(self):
        """Security level reflects reality: 128 bits, not 192."""
        scheme = DilithiumLite()
        assert scheme.security_level == 128

    def test_still_functions_for_backward_compat(self):
        """Existing integrations using DilithiumLite continue to work."""
        scheme = DilithiumLite()
        priv, pub = scheme.generate_keypair()
        sig = scheme.sign(priv, b"test message")
        assert scheme.verify(pub, b"test message", sig) is True

    def test_docstring_warns_not_post_quantum(self):
        """Docstring contains warning about not being PQ."""
        assert "NOT" in DilithiumLite.__doc__
        assert "hash-based" in DilithiumLite.__doc__.lower()


class TestDilithium3Availability:

    def test_has_real_pq_function_exists(self):
        result = has_real_pq()
        assert isinstance(result, bool)

    @pytest.mark.skipif(not has_real_pq(), reason="oqs-python not installed")
    def test_dilithium3_instantiable_when_available(self):
        scheme = Dilithium3Scheme()
        assert scheme.name() == "dilithium-3"
        assert scheme.security_level == 192

    def test_dilithium3_raises_without_oqs(self):
        """Without oqs-python, Dilithium3Scheme raises a clear error."""
        if has_real_pq():
            pytest.skip("oqs-python is available")
        with pytest.raises(RuntimeError, match="oqs-python"):
            Dilithium3Scheme()


@pytest.mark.skipif(not has_real_pq(), reason="oqs-python not installed")
class TestRealDilithium3:
    """Tests that only run when real PQ is available."""

    def test_keypair_generation(self):
        scheme = Dilithium3Scheme()
        priv, pub = scheme.generate_keypair()
        assert len(priv) > 0
        assert len(pub) > 0

    def test_sign_and_verify(self):
        scheme = Dilithium3Scheme()
        priv, pub = scheme.generate_keypair()
        sig = scheme.sign(priv, b"important message")
        assert scheme.verify(pub, b"important message", sig) is True

    def test_rejects_tampered_message(self):
        scheme = Dilithium3Scheme()
        priv, pub = scheme.generate_keypair()
        sig = scheme.sign(priv, b"original")
        assert scheme.verify(pub, b"tampered", sig) is False

    def test_rejects_wrong_public_key(self):
        scheme = Dilithium3Scheme()
        priv_a, _ = scheme.generate_keypair()
        _, pub_b = scheme.generate_keypair()
        sig = scheme.sign(priv_a, b"msg")
        assert scheme.verify(pub_b, b"msg", sig) is False


class TestRegistryIntegration:

    def test_hmac_still_registered(self):
        """Existing schemes remain registered."""
        scheme = get_scheme("hmac-sha256")
        assert scheme is not None

    def test_dilithium_lite_still_registered(self):
        scheme = get_scheme("dilithium-lite")
        assert isinstance(scheme, DilithiumLite)

    @pytest.mark.skipif(not has_real_pq(), reason="oqs-python not installed")
    def test_dilithium3_registered_when_available(self):
        scheme = get_scheme("dilithium-3")
        assert isinstance(scheme, Dilithium3Scheme)

    def test_available_schemes_list_includes_legacy(self):
        names = available_schemes()
        assert "hmac-sha256" in names
        assert "dilithium-lite" in names
