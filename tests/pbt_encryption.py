# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Property-based tests for crdt_merge.encryption.

Tests field-level encryption invariants: encrypt/decrypt roundtrips,
key isolation, wrong-key rejection, and order-tag consistency using the
XOR-legacy backend (stdlib only, always available).
"""

import warnings

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from crdt_merge.encryption import (
    EncryptedMerge,
    EncryptedValue,
    StaticKeyProvider,
    XORLegacyBackend,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEY_32 = b"0" * 32  # stable 32-byte key for most tests
_KEY_32_B = b"1" * 32  # a different key

_json_scalar = st.one_of(
    st.integers(min_value=-10_000, max_value=10_000),
    st.floats(
        min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
    ),
    st.text(max_size=32),
    st.booleans(),
    st.none(),
)


def _make_em(key: bytes = _KEY_32) -> EncryptedMerge:
    """Create an EncryptedMerge with XOR-legacy backend, suppressing warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return EncryptedMerge(StaticKeyProvider(key), backend="xor-legacy")


# ---------------------------------------------------------------------------
# Roundtrip — encrypt_field / decrypt_field
# ---------------------------------------------------------------------------


@given(value=_json_scalar)
@settings(max_examples=50)
def test_encrypt_decrypt_roundtrip_scalar(value):
    """encrypt_field then decrypt_field returns the original scalar value."""
    em = _make_em()
    ev = em.encrypt_field(value, "col_a")
    recovered = em.decrypt_field(ev)
    assert recovered == value


@given(value=st.text(max_size=128))
@settings(max_examples=50)
def test_encrypt_decrypt_roundtrip_string(value):
    """Roundtrip works for arbitrary Unicode strings."""
    em = _make_em()
    ev = em.encrypt_field(value, "name")
    assert em.decrypt_field(ev) == value


@given(value=st.binary(max_size=0))
@settings(max_examples=50)
def test_encrypt_decrypt_empty_bytes_as_value(value):
    """Empty-bytes-derived value (b'') stringified roundtrip is stable."""
    em = _make_em()
    # We store the binary as a list of ints since JSON can't store raw bytes
    raw_list = list(value)
    ev = em.encrypt_field(raw_list, "data")
    assert em.decrypt_field(ev) == raw_list


@given(
    field_name=st.text(min_size=1, max_size=16, alphabet="abcdefghijklmnopqrstuvwxyz_"),
    value=_json_scalar,
)
@settings(max_examples=50)
def test_encrypt_decrypt_various_field_names(field_name, value):
    """Roundtrip holds across arbitrary field names (per-field key derivation)."""
    em = _make_em()
    ev = em.encrypt_field(value, field_name)
    assert em.decrypt_field(ev) == value


# ---------------------------------------------------------------------------
# Different keys produce different ciphertext
# ---------------------------------------------------------------------------


@given(value=st.integers(min_value=0, max_value=1_000_000))
@settings(max_examples=50)
def test_different_keys_produce_different_ciphertext(value):
    """Two different master keys encrypt the same value to different ciphertexts."""
    em_a = _make_em(_KEY_32)
    em_b = _make_em(_KEY_32_B)
    ev_a = em_a.encrypt_field(value, "score")
    ev_b = em_b.encrypt_field(value, "score")
    # Ciphertexts should not match (with overwhelming probability)
    assert ev_a.ciphertext != ev_b.ciphertext


# ---------------------------------------------------------------------------
# Wrong key cannot decrypt
# ---------------------------------------------------------------------------


@given(value=st.text(min_size=1, max_size=32))
@settings(max_examples=50)
def test_wrong_key_raises_on_decrypt(value):
    """Decrypting with a different key raises ValueError (auth failure)."""
    em_encrypt = _make_em(_KEY_32)
    em_wrong = _make_em(_KEY_32_B)
    ev = em_encrypt.encrypt_field(value, "secret")
    with pytest.raises((ValueError, Exception)):
        em_wrong.decrypt_field(ev)


# ---------------------------------------------------------------------------
# Empty plaintext (via empty list / empty string)
# ---------------------------------------------------------------------------


@given(empty=st.just(""))
@settings(max_examples=50)
def test_empty_string_roundtrip(empty):
    """Empty string encrypts and decrypts back to empty string."""
    em = _make_em()
    ev = em.encrypt_field(empty, "notes")
    assert em.decrypt_field(ev) == empty


@given(empty_list=st.just([]))
@settings(max_examples=50)
def test_empty_list_roundtrip(empty_list):
    """Empty list roundtrips correctly."""
    em = _make_em()
    ev = em.encrypt_field(empty_list, "tags")
    assert em.decrypt_field(ev) == empty_list


# ---------------------------------------------------------------------------
# EncryptedValue serialisation roundtrip
# ---------------------------------------------------------------------------


@given(value=_json_scalar)
@settings(max_examples=50)
def test_encrypted_value_to_from_dict_roundtrip(value):
    """EncryptedValue.to_dict / from_dict roundtrip preserves all fields."""
    em = _make_em()
    ev = em.encrypt_field(value, "col")
    d = ev.to_dict()
    restored = EncryptedValue.from_dict(d)
    assert restored.ciphertext == ev.ciphertext
    assert restored.nonce == ev.nonce
    assert restored.tag == ev.tag
    assert restored.order_tag == ev.order_tag
    assert restored.field_name == ev.field_name


# ---------------------------------------------------------------------------
# Order tag consistency
# ---------------------------------------------------------------------------


@given(value=st.integers(min_value=-100, max_value=100))
@settings(max_examples=50)
def test_same_value_same_order_tag(value):
    """Encrypting the same value twice produces the same order_tag (deterministic HMAC)."""
    em = _make_em()
    ev1 = em.encrypt_field(value, "x")
    ev2 = em.encrypt_field(value, "x")
    assert ev1.order_tag == ev2.order_tag


@given(
    v1=st.integers(min_value=0, max_value=100),
    v2=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=50)
def test_order_tag_comparison_reflexive(v1, v2):
    """EncryptedValue comparison via order_tag is consistent."""
    em = _make_em()
    ev1 = em.encrypt_field(v1, "score")
    ev2 = em.encrypt_field(v2, "score")
    # Reflexivity: ev == ev
    assert ev1 == ev1
    assert ev2 == ev2
    # Trichotomy
    assert (ev1 < ev2) or (ev1 > ev2) or (ev1 == ev2)


# ---------------------------------------------------------------------------
# encrypt_records / decrypt_records roundtrip
# ---------------------------------------------------------------------------


@given(
    names=st.lists(st.text(min_size=1, max_size=8, alphabet="abcde"), min_size=1, max_size=3),
    scores=st.lists(st.integers(0, 100), min_size=1, max_size=3),
)
@settings(max_examples=50)
def test_encrypt_decrypt_records_roundtrip(names, scores):
    """encrypt_records + decrypt_records recovers the original records."""
    assume(len(names) == len(scores))
    records = [
        {"id": i, "name": n, "score": s}
        for i, (n, s) in enumerate(zip(names, scores))
    ]
    em = _make_em()
    enc = em.encrypt_records(records, fields=["name", "score"], key="id")
    dec = em.decrypt_records(enc, fields=["name", "score"])
    for orig, recovered in zip(records, dec):
        assert recovered["name"] == orig["name"]
        assert recovered["score"] == orig["score"]
        assert recovered["id"] == orig["id"]


# ---------------------------------------------------------------------------
# Backend — XORLegacyBackend direct property test
# ---------------------------------------------------------------------------


@given(plaintext=st.binary(min_size=0, max_size=128))
@settings(max_examples=50)
def test_xor_backend_roundtrip(plaintext):
    """XORLegacyBackend encrypt/decrypt roundtrips arbitrary bytes."""
    backend = XORLegacyBackend()
    key = _KEY_32
    ct, nonce, tag = backend.encrypt(key, plaintext)
    recovered = backend.decrypt(key, ct, nonce, tag)
    assert recovered == plaintext
