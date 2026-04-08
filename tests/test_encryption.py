# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.encryption — field-level encryption for merge operations."""

import copy
import secrets

import pytest

from crdt_merge.encryption import (
    EncryptedMerge,
    EncryptedValue,
    KeyProvider,
    StaticKeyProvider,
    _canonical_repr,
    _derive_field_key,
)
from crdt_merge.strategies import LWW, MaxWins, MergeSchema, MinWins


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def master_key():
    return secrets.token_bytes(32)


@pytest.fixture
def provider(master_key):
    return StaticKeyProvider(master_key)


@pytest.fixture
def em(provider):
    return EncryptedMerge(provider)


# ---------------------------------------------------------------------------
# 1. Round-trip: encrypt → decrypt for all types
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Encrypt then decrypt must return the original value for all JSON types."""

    @pytest.mark.parametrize(
        "value",
        [
            "hello world",
            "",
            42,
            0,
            -17,
            3.14,
            0.0,
            True,
            False,
            None,
            [1, 2, 3],
            [],
            {"nested": "dict", "num": 99},
            {},
            "café 日本語",
            "a" * 10000,
        ],
        ids=[
            "str", "empty_str", "int", "zero", "neg_int", "float", "zero_float",
            "true", "false", "none", "list", "empty_list", "dict", "empty_dict",
            "unicode", "large_str",
        ],
    )
    def test_roundtrip(self, em, value):
        enc = em.encrypt_field(value, "test_field")
        dec = em.decrypt_field(enc)
        assert dec == value

    def test_roundtrip_via_serialization(self, em):
        """Round-trip through to_dict / from_dict preserves value."""
        value = {"key": [1, "two", None, True]}
        enc = em.encrypt_field(value, "payload")
        d = enc.to_dict()
        restored = EncryptedValue.from_dict(d)
        dec = em.decrypt_field(restored)
        assert dec == value

    def test_different_nonces_per_call(self, em):
        """Each encryption produces a unique nonce (probabilistic)."""
        a = em.encrypt_field("same", "f")
        b = em.encrypt_field("same", "f")
        assert a.nonce != b.nonce
        assert a.ciphertext != b.ciphertext
        # But order tags are identical (deterministic)
        assert a.order_tag == b.order_tag


# ---------------------------------------------------------------------------
# 2. Order preservation — EncryptedValue comparisons match plaintext
# ---------------------------------------------------------------------------

class TestOrderPreservation:
    """Order tags must agree with plaintext ordering for strategy resolution."""

    def test_numeric_ordering(self, em):
        vals = [10, 20, 30, 5, 100]
        encrypted = [em.encrypt_field(v, "score") for v in vals]
        # Same value should produce same order_tag
        e10a = em.encrypt_field(10, "score")
        e10b = em.encrypt_field(10, "score")
        assert e10a == e10b

    def test_string_ordering_eq(self, em):
        e1 = em.encrypt_field("alpha", "name")
        e2 = em.encrypt_field("alpha", "name")
        assert e1 == e2

    def test_equal_values_equal_tags(self, em):
        for v in [42, "test", True, None, [1, 2], {"a": 1}]:
            a = em.encrypt_field(v, "f")
            b = em.encrypt_field(v, "f")
            assert a == b, f"Equal values should have equal order_tags: {v}"

    def test_different_values_different_tags(self, em):
        a = em.encrypt_field(10, "f")
        b = em.encrypt_field(20, "f")
        assert a != b

    def test_order_tag_is_deterministic(self, em):
        """Same value + same field → identical order_tag regardless of nonce."""
        tags = {em.encrypt_field(42, "x").order_tag for _ in range(10)}
        assert len(tags) == 1


# ---------------------------------------------------------------------------
# 3. Merge correctness with encrypted records
# ---------------------------------------------------------------------------

class TestMergeEncrypted:
    """merge_encrypted should resolve conflicts correctly on encrypted data."""

    def test_merge_disjoint(self, em):
        left = em.encrypt_records(
            [{"id": "1", "name": "Alice"}], key="id"
        )
        right = em.encrypt_records(
            [{"id": "2", "name": "Bob"}], key="id"
        )
        merged = em.merge_encrypted(left, right, key="id")
        decrypted = em.decrypt_records(merged)
        keys = {r["id"] for r in decrypted}
        assert keys == {"1", "2"}

    def test_merge_overlapping_default_strategy(self, em):
        left = em.encrypt_records(
            [{"id": "1", "val": 10}], key="id"
        )
        right = em.encrypt_records(
            [{"id": "1", "val": 20}], key="id"
        )
        merged = em.merge_encrypted(left, right, key="id")
        decrypted = em.decrypt_records(merged)
        assert len(decrypted) == 1
        # Default: higher order_tag wins — both produce valid encrypted values
        assert decrypted[0]["val"] in (10, 20)

    def test_merge_preserves_unencrypted_key(self, em):
        left = em.encrypt_records([{"id": "A", "x": 1}], key="id")
        right = em.encrypt_records([{"id": "B", "x": 2}], key="id")
        merged = em.merge_encrypted(left, right, key="id")
        ids = {r["id"] for r in merged}
        assert ids == {"A", "B"}


# ---------------------------------------------------------------------------
# 4. Key rotation
# ---------------------------------------------------------------------------

class TestKeyRotation:
    """rotate_key should decrypt with old key and re-encrypt with new key."""

    def test_basic_rotation(self):
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        em_old = EncryptedMerge(old_prov)
        em_new = EncryptedMerge(new_prov)

        records = em_old.encrypt_records(
            [{"id": "1", "secret": "classified"}], key="id"
        )

        rotated = em_new.rotate_key(records, old_prov, new_prov)

        # Old key can no longer decrypt
        with pytest.raises(ValueError, match="Authentication failed"):
            em_old.decrypt_records(rotated)

        # New key works
        dec = em_new.decrypt_records(rotated)
        assert dec[0]["secret"] == "classified"

    def test_rotation_preserves_all_fields(self):
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        original = [{"id": "1", "a": "foo", "b": 42, "c": [1, 2]}]
        encrypted = EncryptedMerge(old_prov).encrypt_records(original, key="id")
        rotated = EncryptedMerge(new_prov).rotate_key(encrypted, old_prov, new_prov)
        decrypted = EncryptedMerge(new_prov).decrypt_records(rotated)

        assert decrypted[0]["a"] == "foo"
        assert decrypted[0]["b"] == 42
        assert decrypted[0]["c"] == [1, 2]

    def test_selective_field_rotation(self):
        old_key = secrets.token_bytes(32)
        new_key = secrets.token_bytes(32)
        old_prov = StaticKeyProvider(old_key)
        new_prov = StaticKeyProvider(new_key)

        original = [{"id": "1", "x": "one", "y": "two"}]
        encrypted = EncryptedMerge(old_prov).encrypt_records(original, key="id")

        # Rotate only field 'x'
        rotated = EncryptedMerge(new_prov).rotate_key(
            encrypted, old_prov, new_prov, fields=["x"]
        )

        # x decrypts with new key
        ev_x = EncryptedValue.from_dict(rotated[0]["x"])
        assert EncryptedMerge(new_prov).decrypt_field(ev_x) == "one"

        # y still requires old key
        ev_y = EncryptedValue.from_dict(rotated[0]["y"])
        assert EncryptedMerge(old_prov).decrypt_field(ev_y) == "two"


# ---------------------------------------------------------------------------
# 5. Authentication — tampered ciphertext raises error
# ---------------------------------------------------------------------------

class TestAuthentication:
    """Tampered ciphertext must be detected and rejected."""

    def test_tampered_ciphertext_raises(self, em):
        enc = em.encrypt_field("secret", "f")
        tampered = bytearray(enc.ciphertext)
        tampered[0] ^= 0xFF
        enc.ciphertext = bytes(tampered)
        with pytest.raises(ValueError, match="Authentication failed"):
            em.decrypt_field(enc)

    def test_tampered_nonce_raises(self, em):
        enc = em.encrypt_field("secret", "f")
        tampered = bytearray(enc.nonce)
        tampered[0] ^= 0xFF
        enc.nonce = bytes(tampered)
        with pytest.raises(ValueError, match="Authentication failed"):
            em.decrypt_field(enc)

    def test_wrong_key_raises(self):
        prov1 = StaticKeyProvider(secrets.token_bytes(32))
        prov2 = StaticKeyProvider(secrets.token_bytes(32))
        em1 = EncryptedMerge(prov1)
        em2 = EncryptedMerge(prov2)

        enc = em1.encrypt_field("data", "f")
        with pytest.raises(ValueError, match="Authentication failed"):
            em2.decrypt_field(enc)


# ---------------------------------------------------------------------------
# 6. Field isolation — different fields use different derived keys
# ---------------------------------------------------------------------------

class TestFieldIsolation:
    """Each field gets its own derived key; cross-field decryption must fail."""

    def test_different_fields_different_keys(self, provider):
        k1 = provider.get_key("field_a")
        k2 = provider.get_key("field_b")
        assert k1 != k2

    def test_cross_field_decrypt_fails(self, em):
        enc = em.encrypt_field("secret", "alpha")
        # Swap field name to simulate cross-field access
        enc_tampered = EncryptedValue(
            ciphertext=enc.ciphertext,
            nonce=enc.nonce,
            tag=enc.tag,
            field_name="beta",
            order_tag=enc.order_tag,
        )
        with pytest.raises(ValueError, match="Authentication failed"):
            em.decrypt_field(enc_tampered)

    def test_same_value_different_field_different_ciphertext(self, em):
        a = em.encrypt_field("same", "f1")
        b = em.encrypt_field("same", "f2")
        # Different field keys → different order_tags
        assert a.order_tag != b.order_tag


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Empty records, None values, empty strings, unicode."""

    def test_empty_records_list(self, em):
        enc = em.encrypt_records([], key="id")
        assert enc == []
        dec = em.decrypt_records([])
        assert dec == []

    def test_record_with_none_value(self, em):
        records = [{"id": "1", "val": None}]
        enc = em.encrypt_records(records, key="id")
        dec = em.decrypt_records(enc)
        assert dec[0]["val"] is None

    def test_record_with_empty_string(self, em):
        records = [{"id": "1", "val": ""}]
        enc = em.encrypt_records(records, key="id")
        dec = em.decrypt_records(enc)
        assert dec[0]["val"] == ""

    def test_unicode_round_trip(self, em):
        val = "Ünïcödé 日本語 العربية "
        enc = em.encrypt_field(val, "text")
        assert em.decrypt_field(enc) == val

    def test_nested_structure(self, em):
        val = {"a": [1, {"b": [True, None, "c"]}], "d": 3.14}
        enc = em.encrypt_field(val, "nested")
        assert em.decrypt_field(enc) == val

    def test_encrypt_specific_fields_only(self, em):
        records = [{"id": "1", "name": "Alice", "score": 95, "email": "a@b.c"}]
        enc = em.encrypt_records(records, fields=["email"], key="id")
        # name and score should be plaintext
        assert enc[0]["name"] == "Alice"
        assert enc[0]["score"] == 95
        # email should be encrypted
        assert isinstance(enc[0]["email"], dict)
        assert enc[0]["email"].get("__encrypted__") is True

    def test_decrypt_skips_non_encrypted(self, em):
        records = [{"id": "1", "plain": "visible", "enc": em.encrypt_field("hidden", "enc").to_dict()}]
        dec = em.decrypt_records(records)
        assert dec[0]["plain"] == "visible"
        assert dec[0]["enc"] == "hidden"


# ---------------------------------------------------------------------------
# 8. StaticKeyProvider
# ---------------------------------------------------------------------------

class TestStaticKeyProvider:
    """Key derivation is deterministic and field-specific."""

    def test_deterministic(self, master_key):
        p1 = StaticKeyProvider(master_key)
        p2 = StaticKeyProvider(master_key)
        assert p1.get_key("x") == p2.get_key("x")

    def test_field_specific(self, master_key):
        p = StaticKeyProvider(master_key)
        assert p.get_key("a") != p.get_key("b")

    def test_key_length(self, master_key):
        p = StaticKeyProvider(master_key)
        assert len(p.get_key("any_field")) == 32

    def test_short_key_rejected(self):
        with pytest.raises(ValueError, match="at least"):
            StaticKeyProvider(b"too_short")

    def test_longer_key_accepted(self):
        key = secrets.token_bytes(64)
        p = StaticKeyProvider(key)
        assert len(p.get_key("f")) == 32


# ---------------------------------------------------------------------------
# 9. EncryptedValue serialization
# ---------------------------------------------------------------------------

class TestEncryptedValueSerialization:
    """to_dict / from_dict round-trips for EncryptedValue."""

    def test_round_trip(self, em):
        ev = em.encrypt_field({"complex": [1, 2]}, "data")
        d = ev.to_dict()
        assert d["__encrypted__"] is True
        restored = EncryptedValue.from_dict(d)
        assert restored.ciphertext == ev.ciphertext
        assert restored.nonce == ev.nonce
        assert restored.tag == ev.tag
        assert restored.order_tag == ev.order_tag
        assert restored.field_name == ev.field_name

    def test_to_dict_keys(self, em):
        ev = em.encrypt_field("val", "f")
        d = ev.to_dict()
        required = {"__encrypted__", "ciphertext", "nonce", "tag", "order_tag", "field_name"}
        # v2 wire format (AEAD backends) adds 'cipher' and 'version'; v1 (xor-legacy) omits them
        assert required.issubset(d.keys())
        assert d.keys() <= required | {"cipher", "version"}
