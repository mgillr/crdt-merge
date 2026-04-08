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

"""Tests for key lifecycle management (Okonkwo §9)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.key_manager import (
    KeyManager, KeyPair, PeerKeyRegistry, RevocationEntry,
)


class TestKeyPair:
    def test_generate_produces_valid_keys(self):
        kp = KeyPair.generate()
        assert len(kp.public_key) == 32
        assert kp.private_key is not None
        assert len(kp.key_id) == 16

    def test_sign_verify_roundtrip(self):
        kp = KeyPair.generate()
        msg = b"test message"
        sig = kp.sign(msg)
        assert kp.verify(msg, sig)

    def test_verify_fails_on_tampered_message(self):
        kp = KeyPair.generate()
        sig = kp.sign(b"original")
        assert not kp.verify(b"tampered", sig)

    def test_sign_without_private_key_raises(self):
        kp = KeyPair(public_key=b"x" * 32)
        with pytest.raises(ValueError):
            kp.sign(b"test")

    def test_unique_key_ids(self):
        ids = {KeyPair.generate().key_id for _ in range(50)}
        assert len(ids) == 50


class TestPeerKeyRegistry:
    def test_register_and_retrieve(self):
        reg = PeerKeyRegistry()
        kp = KeyPair.generate()
        reg.register("peer-1", kp)
        assert reg.current_key("peer-1") == kp

    def test_unknown_peer_returns_none(self):
        reg = PeerKeyRegistry()
        assert reg.current_key("unknown") is None

    def test_revocation_invalidates_key(self):
        reg = PeerKeyRegistry()
        kp = KeyPair.generate()
        reg.register("peer-1", kp)
        rev = RevocationEntry(
            key_id=kp.key_id, peer_id="peer-1",
            revoked_at=0.0, proof=b"proof",
        )
        reg.revoke(rev)
        assert reg.is_revoked(kp.key_id)
        assert reg.current_key("peer-1") is None

    def test_merge_union(self):
        r1 = PeerKeyRegistry()
        r2 = PeerKeyRegistry()
        k1 = KeyPair.generate()
        k2 = KeyPair.generate()
        r1.register("peer-1", k1)
        r2.register("peer-2", k2)
        merged = r1.merge(r2)
        assert merged.peer_count == 2
        assert merged.current_key("peer-1") is not None
        assert merged.current_key("peer-2") is not None

    def test_merge_revocations_union(self):
        r1 = PeerKeyRegistry()
        r2 = PeerKeyRegistry()
        kp = KeyPair.generate()
        r1.register("peer-1", kp)
        r2.register("peer-1", kp)
        rev = RevocationEntry(key_id=kp.key_id, peer_id="peer-1", revoked_at=0.0, proof=b"p")
        r1.revoke(rev)
        merged = r1.merge(r2)
        assert merged.is_revoked(kp.key_id)


class TestKeyManager:
    def test_initialization(self):
        km = KeyManager("peer-1")
        assert km.peer_id == "peer-1"
        assert km.current_key is not None

    def test_sign_and_verify(self):
        km1 = KeyManager("peer-1")
        km2 = KeyManager("peer-2")
        # Register peer-1's key with km2
        km2.registry.register("peer-1", KeyPair(public_key=km1.current_key.public_key))
        msg = b"hello"
        sig = km1.sign(msg)
        assert km2.verify_peer("peer-1", msg, sig)

    def test_key_rotation(self):
        km = KeyManager("peer-1")
        old_id = km.current_key.key_id
        new_key, revocation = km.rotate_key()
        assert km.current_key.key_id != old_id
        assert revocation.key_id == old_id
        assert km.registry.is_revoked(old_id)

    def test_emergency_revoke(self):
        km = KeyManager("peer-1")
        kid = km.current_key.key_id
        rev = km.emergency_revoke("compromise")
        assert rev.key_id == kid
        assert rev.reason == "compromise"
        assert km.registry.is_revoked(kid)
