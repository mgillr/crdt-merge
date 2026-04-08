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

"""Tests for post-quantum signature schemes."""

import time
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.pq_signatures import (
    HmacScheme,
    DilithiumLite,
    HybridScheme,
    register_scheme,
    get_scheme,
    available_schemes,
)


class TestHmacScheme:

    def test_name(self):
        s = HmacScheme()
        assert s.name() == "hmac-sha256"

    def test_generate_keypair(self):
        s = HmacScheme()
        priv, pub = s.generate_keypair()
        assert len(pub) > 0
        assert len(priv) > 0

    def test_sign_and_verify(self):
        s = HmacScheme()
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"hello")
        assert s.verify(pub, b"hello", sig)

    def test_wrong_message_fails(self):
        s = HmacScheme()
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"hello")
        assert not s.verify(pub, b"tampered", sig)

    def test_wrong_key_fails(self):
        s = HmacScheme()
        priv1, pub1 = s.generate_keypair()
        priv2, pub2 = s.generate_keypair()
        sig = s.sign(priv1, b"data")
        assert not s.verify(pub2, b"data", sig)

    def test_signature_size(self):
        s = HmacScheme()
        assert s.signature_size > 0

    def test_public_key_size(self):
        s = HmacScheme()
        assert s.public_key_size > 0


class TestDilithiumLite:

    def test_name(self):
        s = DilithiumLite()
        assert "dilithium" in s.name().lower()

    def test_generate_keypair(self):
        s = DilithiumLite()
        priv, pub = s.generate_keypair()
        assert len(pub) > 0
        assert len(priv) > 0

    def test_sign_and_verify(self):
        s = DilithiumLite()
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"test message")
        assert s.verify(pub, b"test message", sig)

    def test_wrong_key_fails(self):
        s = DilithiumLite()
        priv1, pub1 = s.generate_keypair()
        priv2, pub2 = s.generate_keypair()
        sig = s.sign(priv1, b"data")
        assert not s.verify(pub2, b"data", sig)


class TestHybridScheme:

    def test_name(self):
        s = HybridScheme()
        assert "hybrid" in s.name().lower()

    def test_sign_and_verify(self):
        s = HybridScheme()
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"dual protection")
        assert s.verify(pub, b"dual protection", sig)

    def test_tampered_fails(self):
        s = HybridScheme()
        priv, pub = s.generate_keypair()
        sig = s.sign(priv, b"original")
        assert not s.verify(pub, b"changed", sig)


class TestSchemeRegistry:

    def test_available_schemes(self):
        schemes = available_schemes()
        assert isinstance(schemes, list)
        assert len(schemes) >= 2

    def test_get_hmac(self):
        s = get_scheme("hmac-sha256")
        assert s is not None
        assert s.name() == "hmac-sha256"

    def test_sign_throughput(self):
        """1000 HMAC signs must complete quickly."""
        s = HmacScheme()
        priv, pub = s.generate_keypair()
        start = time.perf_counter()
        for i in range(1000):
            s.sign(priv, f"msg-{i}".encode())
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"too slow: {elapsed:.1f}s"
