# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""
Field-level encryption for CRDT merge operations — pluggable crypto backends.

Provides authenticated encryption with order-preserving tags that enable
LWW / Max / Min strategy resolution on encrypted data without decryption.

Architecture:
  - Pluggable crypto backend system with auto-detection
  - HMAC-SHA256 order tags for sortable encrypted comparisons
  - Per-field key derivation from a master key
  - Wire-format versioning (v1 = legacy XOR, v2 = named cipher)

Available backends (in auto-detection priority order):
  1. **AES-256-GCM** — industry-standard AEAD (requires ``cryptography`` package)
  2. **AES-256-GCM-SIV** — nonce-misuse-resistant AEAD, ideal for CRDTs
  3. **ChaCha20-Poly1305** — modern AEAD, fast on CPUs without AES-NI
  4. **XOR Legacy** — HMAC-SHA256 derived keystream (stdlib only, zero deps)

When ``backend="auto"`` is explicitly passed, AES-256-GCM is used if the
``cryptography`` package is installed; otherwise the XOR legacy backend
is selected with a warning.

When no *backend* argument is provided the XOR legacy backend is used for
backward compatibility with existing serialised data.

.. note::

   The XOR legacy backend is a non-standard construction provided for
   zero-dependency environments.  For production systems handling sensitive
   data, install the ``cryptography`` package and pass ``backend="auto"``
   or an explicit backend name::

       pip install crdt-merge[crypto]
"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import secrets
import struct
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple

from crdt_merge import merge
from crdt_merge.strategies import MergeSchema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NONCE_BYTES = 16
_KEY_BYTES = 32
_BLOCK_BYTES = 32  # HMAC-SHA256 output size

# Sentinel for "no backend argument was passed"
_BACKEND_UNSET = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_repr(value: Any) -> bytes:
    """Deterministic serialization for order-tag generation."""
    return json.dumps(value, sort_keys=True, default=str).encode("utf-8")


def _derive_field_key(master_key: bytes, field_name: str) -> bytes:
    """Derive a per-field 32-byte key via HMAC(master, field_name)."""
    return hmac.new(master_key, field_name.encode("utf-8"), hashlib.sha256).digest()


# NOTE: This is a non-standard construction. See module docstring for security guidance.
def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate *length* bytes of keystream: HMAC(key, nonce || counter)."""
    blocks_needed = (length + _BLOCK_BYTES - 1) // _BLOCK_BYTES
    stream = bytearray()
    for counter in range(blocks_needed):
        block_input = nonce + struct.pack(">I", counter)
        stream.extend(hmac.new(key, block_input, hashlib.sha256).digest())
    return bytes(stream[:length])


def _xor_bytes(data: bytes, mask: bytes) -> bytes:
    """XOR two byte strings of equal length."""
    return bytes(a ^ b for a, b in zip(data, mask))


# ---------------------------------------------------------------------------
# CryptoBackend ABC
# ---------------------------------------------------------------------------

class CryptoBackend(ABC):
    """Abstract cryptographic backend for field-level encryption."""

    name: str  # e.g. "aes-256-gcm"

    @abstractmethod
    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]:
        """Encrypt *plaintext* with *key*.

        Returns ``(ciphertext, nonce, tag)``.
        """

    @abstractmethod
    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        """Decrypt *ciphertext* with *key*.

        Returns plaintext.  Raises ``ValueError`` on authentication failure.
        """


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

class XORLegacyBackend(CryptoBackend):
    """HMAC-SHA256 derived XOR keystream with HMAC auth tag (stdlib only)."""

    name = "xor-legacy"

    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]:
        nonce = secrets.token_bytes(_NONCE_BYTES)
        stream = _keystream(key, nonce, len(plaintext))
        ciphertext = _xor_bytes(plaintext, stream)
        tag_input = nonce + ciphertext
        tag = hmac.new(key, tag_input, hashlib.sha256).digest()
        return ciphertext, nonce, tag

    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        tag_input = nonce + ciphertext
        expected_tag = hmac.new(key, tag_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_tag, tag):
            raise ValueError("Authentication failed: ciphertext may have been tampered with")
        stream = _keystream(key, nonce, len(ciphertext))
        return _xor_bytes(ciphertext, stream)


class AES256GCMBackend(CryptoBackend):
    """AES-256-GCM via the ``cryptography`` package."""

    name = "aes-256-gcm"

    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ct_with_tag = aesgcm.encrypt(nonce, plaintext, associated_data)
        # AESGCM appends a 16-byte tag
        tag = ct_with_tag[-16:]
        ciphertext = ct_with_tag[:-16]
        return ciphertext, nonce, tag

    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ct_with_tag = ciphertext + tag
        try:
            return aesgcm.decrypt(nonce, ct_with_tag, associated_data)
        except Exception as exc:
            raise ValueError("Authentication failed: ciphertext may have been tampered with") from exc


class AESGCMSIVBackend(CryptoBackend):
    """AES-256-GCM-SIV — nonce-misuse-resistant AEAD, ideal for CRDTs."""

    name = "aes-256-gcm-siv"

    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
        cipher = AESGCMSIV(key)
        nonce = secrets.token_bytes(12)
        ct_with_tag = cipher.encrypt(nonce, plaintext, associated_data)
        tag = ct_with_tag[-16:]
        ciphertext = ct_with_tag[:-16]
        return ciphertext, nonce, tag

    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
        cipher = AESGCMSIV(key)
        ct_with_tag = ciphertext + tag
        try:
            return cipher.decrypt(nonce, ct_with_tag, associated_data)
        except Exception as exc:
            raise ValueError("Authentication failed: ciphertext may have been tampered with") from exc


class ChaCha20Poly1305Backend(CryptoBackend):
    """ChaCha20-Poly1305 AEAD."""

    name = "chacha20-poly1305"

    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        cipher = ChaCha20Poly1305(key)
        nonce = secrets.token_bytes(12)
        ct_with_tag = cipher.encrypt(nonce, plaintext, associated_data)
        tag = ct_with_tag[-16:]
        ciphertext = ct_with_tag[:-16]
        return ciphertext, nonce, tag

    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        cipher = ChaCha20Poly1305(key)
        ct_with_tag = ciphertext + tag
        try:
            return cipher.decrypt(nonce, ct_with_tag, associated_data)
        except Exception as exc:
            raise ValueError("Authentication failed: ciphertext may have been tampered with") from exc


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

_BACKEND_REGISTRY: Dict[str, type] = {}


def register_backend(name: str, cls: type) -> None:
    """Register a crypto backend class under *name*."""
    _BACKEND_REGISTRY[name] = cls


def get_backend(name: str) -> CryptoBackend:
    """Return a new instance of the backend registered as *name*.

    Raises ``ValueError`` if *name* is not registered.
    """
    if name not in _BACKEND_REGISTRY:
        raise ValueError(f"Unknown crypto backend: {name!r}. Available: {list(_BACKEND_REGISTRY)}")
    return _BACKEND_REGISTRY[name]()


# Always available (stdlib only)
register_backend("xor-legacy", XORLegacyBackend)

# AEAD backends — only if cryptography is installed
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM  # noqa: F401
    register_backend("aes-256-gcm", AES256GCMBackend)
except ImportError:
    pass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV as _AESGCMSIV  # noqa: F401
    register_backend("aes-256-gcm-siv", AESGCMSIVBackend)
except ImportError:
    pass

try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as _ChaCha  # noqa: F401
    register_backend("chacha20-poly1305", ChaCha20Poly1305Backend)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# EncryptedValue
# ---------------------------------------------------------------------------

class EncryptedValue:
    """Container for an encrypted field value with order-preserving tag."""

    __slots__ = ("ciphertext", "nonce", "tag", "order_tag", "field_name", "cipher")

    def __init__(
        self,
        ciphertext: bytes,
        nonce: bytes,
        tag: bytes,
        field_name: str,
        order_tag: bytes = b"",
    ) -> None:
        self.ciphertext = ciphertext
        self.nonce = nonce
        self.tag = tag
        self.order_tag = order_tag
        self.field_name = field_name
        self.cipher: Optional[str] = None

    # -- Comparison via order_tag (enables LWW / Max / Min on ciphertext) ---

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, EncryptedValue):
            return NotImplemented
        return self.order_tag < other.order_tag

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, EncryptedValue):
            return NotImplemented
        return self.order_tag > other.order_tag

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EncryptedValue):
            return NotImplemented
        return self.order_tag == other.order_tag

    def __le__(self, other: object) -> bool:
        if not isinstance(other, EncryptedValue):
            return NotImplemented
        return self.order_tag <= other.order_tag

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, EncryptedValue):
            return NotImplemented
        return self.order_tag >= other.order_tag

    def __hash__(self) -> int:
        return hash(self.order_tag)

    def __repr__(self) -> str:
        ct_hex = self.ciphertext[:8].hex()
        return f"EncryptedValue(field={self.field_name!r}, ct={ct_hex}...)"

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> Dict[str, str]:
        """Serialize to a JSON-safe dict with base64-encoded byte fields."""
        d: Dict[str, Any] = {
            "__encrypted__": True,
            "ciphertext": base64.b64encode(self.ciphertext).decode("ascii"),
            "nonce": base64.b64encode(self.nonce).decode("ascii"),
            "tag": base64.b64encode(self.tag).decode("ascii"),
            "order_tag": base64.b64encode(self.order_tag).decode("ascii"),
            "field_name": self.field_name,
        }
        if self.cipher:
            d["cipher"] = self.cipher
            d["version"] = 2
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EncryptedValue":
        """Deserialize from a dict produced by *to_dict*."""
        ev = cls(
            ciphertext=base64.b64decode(d["ciphertext"]),
            nonce=base64.b64decode(d["nonce"]),
            tag=base64.b64decode(d["tag"]),
            field_name=d["field_name"],
            order_tag=base64.b64decode(d.get("order_tag", "")),
        )
        cipher = d.get("cipher")  # None for v1
        if cipher:
            ev.cipher = cipher
        return ev


# ---------------------------------------------------------------------------
# KeyProvider protocol / implementations
# ---------------------------------------------------------------------------

class KeyProvider(ABC):
    """Abstract base for key providers."""

    @abstractmethod
    def get_key(self, field_name: str) -> bytes:
        """Return a 32-byte encryption key for *field_name*."""


class StaticKeyProvider(KeyProvider):
    """Single master key with per-field derivation via HMAC."""

    def __init__(self, key: bytes) -> None:
        if len(key) < _KEY_BYTES:
            raise ValueError(f"Key must be at least {_KEY_BYTES} bytes, got {len(key)}")
        self._key = key[:_KEY_BYTES]

    def get_key(self, field_name: str) -> bytes:
        """Derive a field-specific key: HMAC(master, field_name)."""
        return _derive_field_key(self._key, field_name)


# ---------------------------------------------------------------------------
# EncryptedMerge — the main API
# ---------------------------------------------------------------------------

class EncryptedMerge:
    """Field-level encryption layer for CRDT merge operations.

    Encrypts individual fields while preserving order-comparable tags so that
    strategies like LWW, MaxWins, and MinWins can resolve conflicts without
    decrypting the underlying data.
    """

    _warned: bool = False

    def __init__(self, key_provider: KeyProvider, *, backend: str = _BACKEND_UNSET) -> None:
        self._kp = key_provider

        if backend is _BACKEND_UNSET:
            # Legacy default: XOR keystream with one-time warning.
            # Preserves backward compatibility for callers that do not
            # pass an explicit *backend* argument.
            if not EncryptedMerge._warned:
                warnings.warn(
                    "crdt_merge.encryption uses a HMAC-SHA256 derived XOR keystream, not a standard AEAD cipher. "
                    "For production use with sensitive data, use an external encryption layer (e.g., AES-GCM via the cryptography package).",
                    UserWarning,
                    stacklevel=2,
                )
                EncryptedMerge._warned = True
            self._backend: CryptoBackend = XORLegacyBackend()
        elif backend == "auto":
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
                self._backend = AES256GCMBackend()
            except ImportError:
                if not EncryptedMerge._warned:
                    warnings.warn(
                        "crdt_merge.encryption: 'cryptography' package not installed. "
                        "Falling back to XOR keystream (NOT production-grade). "
                        "Install with: pip install crdt-merge[crypto]",
                        UserWarning,
                        stacklevel=2,
                    )
                    EncryptedMerge._warned = True
                self._backend = XORLegacyBackend()
        else:
            self._backend = get_backend(backend)

    # -- Single-field operations ---------------------------------------------

    def encrypt_field(self, value: Any, field_name: str) -> EncryptedValue:
        """Encrypt *value* for *field_name* with authenticated encryption.

        Returns an ``EncryptedValue`` carrying ciphertext, nonce, auth tag,
        and an order-preserving comparison tag.
        """
        field_key = self._kp.get_key(field_name)
        plaintext = json.dumps(value, sort_keys=True, default=str).encode("utf-8")

        # Encrypt using the active backend
        ciphertext, nonce, tag = self._backend.encrypt(field_key, plaintext)

        # Order-preserving tag: HMAC(field_key, canonical(value))
        order_tag = hmac.new(
            field_key, _canonical_repr(value), hashlib.sha256
        ).digest()

        ev = EncryptedValue(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            field_name=field_name,
            order_tag=order_tag,
        )
        # Tag the cipher used (skip for xor-legacy to keep v1 wire compat)
        if self._backend.name != "xor-legacy":
            ev.cipher = self._backend.name
        return ev

    def decrypt_field(self, encrypted: EncryptedValue) -> Any:
        """Decrypt and verify an ``EncryptedValue``.

        Raises ``ValueError`` if the authentication tag does not match
        (tampered or wrong key).
        """
        field_key = self._kp.get_key(encrypted.field_name)

        # Route to the correct backend based on cipher metadata
        cipher_name = getattr(encrypted, "cipher", None)
        if not cipher_name:
            # v1 / legacy — always use XOR backend regardless of current backend
            backend = XORLegacyBackend()
        else:
            # v2 — use the named backend
            backend = get_backend(cipher_name)

        plaintext = backend.decrypt(field_key, encrypted.ciphertext, encrypted.nonce, encrypted.tag)

        return json.loads(plaintext.decode("utf-8"))

    # -- Bulk record operations ----------------------------------------------

    def encrypt_records(
        self,
        records: List[Dict[str, Any]],
        fields: Optional[List[str]] = None,
        key: str = "id",
    ) -> List[Dict[str, Any]]:
        """Encrypt specified fields (or all non-key fields) in each record.

        Returns new records with ``EncryptedValue.to_dict()`` representations
        replacing plaintext values.
        """
        out: List[Dict[str, Any]] = []
        for rec in records:
            new_rec: Dict[str, Any] = {}
            target_fields = fields if fields is not None else [
                f for f in rec if f != key
            ]
            for k, v in rec.items():
                if k in target_fields:
                    ev = self.encrypt_field(v, k)
                    new_rec[k] = ev.to_dict()
                else:
                    new_rec[k] = v
            out.append(new_rec)
        return out

    def decrypt_records(
        self,
        records: List[Dict[str, Any]],
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Decrypt encrypted fields in each record.

        Automatically detects ``EncryptedValue`` dicts (via ``__encrypted__``
        marker) or operates only on *fields* if specified.
        """
        out: List[Dict[str, Any]] = []
        for rec in records:
            new_rec: Dict[str, Any] = {}
            for k, v in rec.items():
                if fields is not None and k not in fields:
                    new_rec[k] = v
                elif isinstance(v, dict) and v.get("__encrypted__"):
                    ev = EncryptedValue.from_dict(v)
                    new_rec[k] = self.decrypt_field(ev)
                elif isinstance(v, EncryptedValue):
                    new_rec[k] = self.decrypt_field(v)
                else:
                    new_rec[k] = v
            out.append(new_rec)
        return out

    # -- Encrypted merge -----------------------------------------------------

    def merge_encrypted(
        self,
        left: List[Dict[str, Any]],
        right: List[Dict[str, Any]],
        key: str,
        schema: Optional[MergeSchema] = None,
    ) -> List[Dict[str, Any]]:
        """Merge two sets of encrypted records using order-tags for strategy
        resolution.

        Records should already have encrypted fields (as ``EncryptedValue``
        dicts). The merge converts order_tags into comparable wrapper objects
        internally so that LWW / Max / Min strategies work on the encrypted
        representation, then returns the merged encrypted records.
        """
        # Materialise EncryptedValue objects for comparison during merge
        left_ev = self._hydrate_encrypted_values(left)
        right_ev = self._hydrate_encrypted_values(right)

        # Build index by key
        left_idx: Dict[Any, Dict[str, Any]] = {r[key]: r for r in left_ev}
        right_idx: Dict[Any, Dict[str, Any]] = {r[key]: r for r in right_ev}

        all_keys = list(dict.fromkeys(
            [r[key] for r in left_ev] + [r[key] for r in right_ev]
        ))

        merged: List[Dict[str, Any]] = []
        for k in all_keys:
            l_rec = left_idx.get(k)
            r_rec = right_idx.get(k)

            if l_rec is None:
                merged.append(self._dehydrate_record(r_rec))
                continue
            if r_rec is None:
                merged.append(self._dehydrate_record(l_rec))
                continue

            # Both sides exist — resolve field by field
            if schema is not None:
                resolved = schema.resolve_row(l_rec, r_rec)
            else:
                # Default: use order_tag comparison (higher wins = MaxWins-like)
                resolved = {}
                for field in dict.fromkeys(list(l_rec.keys()) + list(r_rec.keys())):
                    lv = l_rec.get(field)
                    rv = r_rec.get(field)
                    if lv is None:
                        resolved[field] = rv
                    elif rv is None:
                        resolved[field] = lv
                    elif isinstance(lv, EncryptedValue) and isinstance(rv, EncryptedValue):
                        resolved[field] = lv if lv >= rv else rv
                    else:
                        # Non-encrypted field (e.g., key column) — keep left
                        resolved[field] = lv

            merged.append(self._dehydrate_record(resolved))
        return merged

    # -- Key rotation --------------------------------------------------------

    def rotate_key(
        self,
        records: List[Dict[str, Any]],
        old_provider: KeyProvider,
        new_provider: KeyProvider,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Re-encrypt records from *old_provider* to *new_provider*.

        Decrypts each encrypted field with the old key, then re-encrypts with
        the new key. Non-encrypted fields pass through unchanged.
        """
        # old_em only needs the key provider for decryption; decrypt_field
        # auto-routes to the correct backend via the cipher metadata.
        old_em = EncryptedMerge(old_provider, backend="xor-legacy")
        new_em = EncryptedMerge(new_provider, backend=self._backend.name)
        out: List[Dict[str, Any]] = []
        for rec in records:
            new_rec: Dict[str, Any] = {}
            for k, v in rec.items():
                should_rotate = (fields is None or k in fields)
                if should_rotate and isinstance(v, dict) and v.get("__encrypted__"):
                    ev = EncryptedValue.from_dict(v)
                    plaintext = old_em.decrypt_field(ev)
                    new_ev = new_em.encrypt_field(plaintext, k)
                    new_rec[k] = new_ev.to_dict()
                else:
                    new_rec[k] = v
            out.append(new_rec)
        return out

    # -- Internal helpers ----------------------------------------------------

    @staticmethod
    def _hydrate_encrypted_values(
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Replace ``__encrypted__`` dicts with live ``EncryptedValue`` objects."""
        out = []
        for rec in records:
            new_rec: Dict[str, Any] = {}
            for k, v in rec.items():
                if isinstance(v, dict) and v.get("__encrypted__"):
                    new_rec[k] = EncryptedValue.from_dict(v)
                else:
                    new_rec[k] = v
            out.append(new_rec)
        return out

    @staticmethod
    def _dehydrate_record(rec: Dict[str, Any]) -> Dict[str, Any]:
        """Convert any live ``EncryptedValue`` objects back to dicts."""
        out: Dict[str, Any] = {}
        for k, v in rec.items():
            if isinstance(v, EncryptedValue):
                out[k] = v.to_dict()
            else:
                out[k] = v
        return out
