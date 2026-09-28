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

"""Key lifecycle management for E4 peer authentication.

Addresses Dr. Okonkwo's concern §9: PCO signatures and evidence proofs
assume each peer has a signing key, but the architecture doesn't specify
key distribution, rotation, or revocation.

Solution: a self-contained key management system that integrates with
the E4 trust lattice.  Key events (rotation, revocation) propagate as
trust evidence through the same delta pipeline.

Design principles:
  - No PKI required — peers exchange public keys during first contact
  - Key rotation uses forward-secure chaining (new key signs old key)
  - Revocation is a CRDT (grow-only revocation set, merged by union)
  - Key binding to trust: key rotation resets trust to probation
  - All key operations produce verifiable evidence

Technical effect (UK patent): eliminates external PKI dependency while
maintaining cryptographic authentication, reducing infrastructure
requirements for Byzantine-tolerant CRDT networks.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time as _time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


SCHEME_ED25519 = "ed25519"
SCHEME_HMAC = "hmac-sha256"
_SCHEMES = (SCHEME_ED25519, SCHEME_HMAC)


class Ed25519Unavailable(RuntimeError):
    """Raised when an Ed25519 key is used without the ``cryptography`` package."""


def _load_ed25519():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise Ed25519Unavailable(
            "Ed25519 keys require the cryptography package, a core "
            "dependency of crdt-merge; this environment is missing it "
            "(pip install 'cryptography>=41'). There is no implicit "
            "fallback."
        ) from exc
    return ed25519, InvalidSignature


def _derive_key_id(public_key: bytes, scheme: str) -> str:
    """Key id bound to (scheme, key bytes).

    Ed25519 keeps the historical ``sha256(public_key)[:16]`` so existing
    Ed25519 key ids are unchanged; every other scheme is domain-separated,
    so the same bytes never share an id across schemes.
    """
    if scheme == SCHEME_ED25519:
        material = public_key
    else:
        material = scheme.encode("ascii") + b"\x00" + public_key
    return hashlib.sha256(material).hexdigest()[:16]


@dataclass(frozen=True)
class KeyPair:
    """Cryptographic key for peer authentication.

    Two schemes, fixed per key, carried with the key, bound into
    ``key_id`` and never mixed:

    - ``"ed25519"``: real Ed25519 via the ``cryptography`` package (a
      core dependency).  Sign, verify and generate raise
      ``Ed25519Unavailable`` if the package is missing; verification
      accepts only a valid 64-byte Ed25519 signature and never falls back
      to anything else.  Exchange the public half with
      :meth:`export_public` and rebuild it with :meth:`from_public`.
    - ``"hmac-sha256"``: explicit opt-in only.  A shared-secret MAC, not
      a signature: the key is one secret, held in both ``public_key`` and
      ``private_key``, and whoever holds it can sign as well as verify, so
      it is never a public key.  Build it only with
      :meth:`from_shared_secret` (or ``generate(scheme="hmac-sha256")``)
      from a secret agreed out of band; never from key bytes received from
      the peer.  :meth:`export_public` refuses it.

    Constructing a key from public bytes alone requires an explicit
    ``scheme``; with a private key and no scheme, Ed25519 is assumed.

    Attributes
    ----------
    public_key  : Ed25519 public key (32 bytes), or the HMAC shared secret.
    private_key : Ed25519 private key, or the HMAC shared secret.  None for
                  a remote Ed25519 peer.
    created_at  : Unix timestamp of key creation.
    key_id      : Identifier derived from (scheme, public_key).
    scheme      : ``"ed25519"`` or ``"hmac-sha256"``.
    """
    public_key: bytes
    private_key: Optional[bytes] = field(default=None, repr=False)
    created_at: float = field(default_factory=_time.time)
    key_id: str = ""
    scheme: Optional[str] = None

    def __post_init__(self) -> None:
        if self.scheme is None:
            if self.private_key is None:
                raise TypeError(
                    "a KeyPair built from public key bytes needs an explicit "
                    "scheme; use KeyPair.from_public(public_key, scheme)"
                )
            object.__setattr__(self, "scheme", SCHEME_ED25519)
        if self.scheme not in _SCHEMES:
            raise ValueError(
                f"unknown key scheme {self.scheme!r}; expected one of {_SCHEMES}"
            )
        if self.scheme == SCHEME_HMAC and (
            not self.private_key or self.private_key != self.public_key
        ):
            raise ValueError(
                "hmac-sha256 keys are a shared secret, not a public key: build "
                "them with KeyPair.from_shared_secret(secret) from a secret "
                "agreed out of band, never from key bytes received from a peer"
            )
        derived = _derive_key_id(self.public_key, self.scheme)
        if not self.key_id:
            object.__setattr__(self, "key_id", derived)
        elif self.key_id != derived:
            raise ValueError(
                f"key_id {self.key_id!r} does not match the key and scheme "
                f"(expected {derived!r})"
            )

    @classmethod
    def from_public(
        cls, public_key: bytes, scheme: str, key_id: Optional[str] = None,
    ) -> KeyPair:
        """Rebuild a peer's verification key from exchanged public data.

        *scheme* is required and must be a public-key scheme; a *key_id*,
        when given, must match the one derived from (scheme, public_key).
        """
        if scheme == SCHEME_HMAC:
            raise ValueError(
                "hmac-sha256 keys are a shared secret and cannot be rebuilt "
                "from exchanged public data; use KeyPair.from_shared_secret "
                "with a secret agreed out of band"
            )
        return cls(public_key=public_key, scheme=scheme, key_id=key_id or "")

    @classmethod
    def from_shared_secret(cls, secret: bytes) -> KeyPair:
        """An HMAC-mode key from a secret agreed out of band."""
        if not secret:
            raise ValueError("the shared secret must be non-empty")
        return cls(public_key=secret, private_key=secret, scheme=SCHEME_HMAC)

    def export_public(self) -> Dict[str, object]:
        """The data a peer needs to verify this key's signatures:
        ``{"public_key", "scheme", "key_id"}``.  Refused for HMAC keys,
        which are shared secrets."""
        if self.scheme == SCHEME_HMAC:
            raise ValueError(
                "hmac-sha256 keys are a shared secret and are never exported "
                "as a public key"
            )
        return {
            "public_key": self.public_key,
            "scheme": self.scheme,
            "key_id": self.key_id,
        }

    def sign(self, message: bytes) -> bytes:
        """Sign *message* with the private key under this key's scheme.

        Ed25519 keys raise ``Ed25519Unavailable`` without the cryptography
        package and ``ValueError`` when the private key is not the Ed25519
        private key of ``public_key``.
        """
        if self.private_key is None:
            raise ValueError("cannot sign without private key")
        if self.scheme == SCHEME_HMAC:
            return hmac.new(self.private_key, message, hashlib.sha256).digest()
        ed25519, _ = _load_ed25519()
        if len(self.private_key) != 32:
            raise ValueError("not an Ed25519 private key (expected 32 raw bytes)")
        sk = ed25519.Ed25519PrivateKey.from_private_bytes(self.private_key)
        if sk.public_key().public_bytes_raw() != self.public_key:
            raise ValueError(
                "public key is not the Ed25519 public key of this private key"
            )
        return sk.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify *signature* against *message* under this key's scheme.

        Ed25519 keys: True only for a valid 64-byte Ed25519 signature;
        any failure returns False and nothing else is tried.  Raises
        ``Ed25519Unavailable`` without the cryptography package.
        """
        if not isinstance(signature, (bytes, bytearray)):
            return False
        if self.scheme == SCHEME_HMAC:
            expected = hmac.new(self.public_key, message, hashlib.sha256).digest()
            return hmac.compare_digest(expected, bytes(signature))
        ed25519, InvalidSignature = _load_ed25519()
        if len(self.public_key) != 32 or len(signature) != 64:
            return False
        try:
            pk = ed25519.Ed25519PublicKey.from_public_bytes(self.public_key)
            pk.verify(bytes(signature), message)
        except (InvalidSignature, ValueError):
            return False
        return True

    @classmethod
    def generate(cls, scheme: str = SCHEME_ED25519) -> KeyPair:
        """Generate a fresh random key pair.

        Ed25519 by default (raises ``Ed25519Unavailable`` without the
        cryptography package).  ``scheme="hmac-sha256"`` generates a random
        shared secret (see :meth:`from_shared_secret`); it is never chosen
        implicitly.
        """
        if scheme == SCHEME_HMAC:
            return cls.from_shared_secret(os.urandom(32))
        if scheme != SCHEME_ED25519:
            raise ValueError(
                f"unknown key scheme {scheme!r}; expected one of {_SCHEMES}"
            )
        ed25519, _ = _load_ed25519()
        sk = ed25519.Ed25519PrivateKey.generate()
        return cls(
            public_key=sk.public_key().public_bytes_raw(),
            private_key=sk.private_bytes_raw(),
            scheme=SCHEME_ED25519,
        )


@dataclass(frozen=True)
class RevocationEntry:
    """A revoked key record (CRDT element — grow-only set).

    Attributes
    ----------
    key_id     : The revoked key's identifier.
    peer_id    : The peer who owned the key.
    revoked_at : Unix timestamp of revocation.
    reason     : Human-readable revocation reason.
    successor  : Key ID of the replacement key (if rotated).
    proof      : Signature from the old key authorizing revocation.
    """
    key_id: str
    peer_id: str
    revoked_at: float
    reason: str = ""
    successor: str = ""
    proof: bytes = b""

    def verify(self, registry: Optional[PeerKeyRegistry] = None) -> bool:
        """Verify the revocation proof.

        When a registry is provided, the proof is validated as a real
        signature from the revoked key over the revocation payload.
        Without a registry, falls back to non-empty check (backward compat).
        """
        if not self.proof:
            return False
        if registry is None:
            return len(self.proof) > 0

        # Look up the revoked key in the registry
        chain = registry._keys.get(self.peer_id, [])
        old_key = None
        for k in chain:
            if k.key_id == self.key_id:
                old_key = k
                break
        if old_key is None:
            return False

        # Build the signed payload: key_id + peer_id + reason + successor
        payload = (
            self.key_id.encode("utf-8") + b"\x00"
            + self.peer_id.encode("utf-8") + b"\x00"
            + self.reason.encode("utf-8") + b"\x00"
            + self.successor.encode("utf-8")
        )
        return old_key.verify(payload, self.proof)


class PeerKeyRegistry:
    """Registry of known peer public keys (CRDT: grow-only map).

    Tracks current and historical keys for each peer.  Key rotation
    adds a new entry without removing the old one.  Revocation marks
    old keys as invalid.

    The registry merges by union: any key ever seen is retained.
    Conflict resolution: if two replicas have different current keys
    for the same peer, the one with the later creation timestamp wins.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, List[KeyPair]] = {}
        self._revocations: Set[RevocationEntry] = set()

    def register(self, peer_id: str, key: KeyPair) -> None:
        """Register a key for *peer_id*.

        A peer's scheme is fixed by its first registered key; a key with a
        different scheme is refused (ValueError), so a scheme cannot be
        swapped under an existing peer.  An HMAC key must be a secret
        agreed with the peer out of band.
        """
        chain = self._keys.get(peer_id, [])
        if chain and chain[0].scheme != key.scheme:
            raise ValueError(
                f"peer {peer_id!r} is recorded with scheme {chain[0].scheme!r}; "
                f"refusing a {key.scheme!r} key"
            )
        chain = self._keys.setdefault(peer_id, [])
        # Avoid duplicates
        if not any(k.key_id == key.key_id for k in chain):
            chain.append(key)

    def current_key(self, peer_id: str) -> Optional[KeyPair]:
        """Return the most recent non-revoked key for *peer_id*."""
        chain = self._keys.get(peer_id, [])
        revoked_ids = {r.key_id for r in self._revocations}
        valid = [k for k in chain if k.key_id not in revoked_ids]
        if not valid:
            return None
        return max(valid, key=lambda k: k.created_at)

    def revoke(self, entry: RevocationEntry) -> None:
        """Record a key revocation (grow-only, CRDT-safe)."""
        self._revocations.add(entry)

    def is_revoked(self, key_id: str) -> bool:
        """Check if a key has been revoked."""
        return any(r.key_id == key_id for r in self._revocations)

    def merge(self, other: PeerKeyRegistry) -> PeerKeyRegistry:
        """CRDT merge — union of keys and revocations."""
        merged = PeerKeyRegistry()
        # Merge key chains
        all_peers = set(self._keys) | set(other._keys)
        for pid in all_peers:
            self_chain = self._keys.get(pid, [])
            other_chain = other._keys.get(pid, [])
            seen: Set[str] = set()
            for k in self_chain + other_chain:
                if k.key_id not in seen:
                    merged.register(pid, k)
                    seen.add(k.key_id)
        # Merge revocations (set union)
        merged._revocations = self._revocations | other._revocations
        return merged

    @property
    def peer_count(self) -> int:
        return len(self._keys)

    @property
    def revocation_count(self) -> int:
        return len(self._revocations)

    def key_chain_length(self, peer_id: str) -> int:
        return len(self._keys.get(peer_id, []))


class KeyManager:
    """High-level key lifecycle management.

    Provides key generation, rotation, revocation, and verification
    integrated with the E4 trust system.

    Parameters
    ----------
    peer_id :
        Local peer identifier.
    rotation_interval :
        Seconds between automatic key rotations (default: 86400 = 24h).
    max_chain_length :
        Maximum key chain length before forced pruning (default: 10).
    scheme :
        Key scheme for generated and rotated keys: ``"ed25519"``
        (default) or the explicit opt-in ``"hmac-sha256"`` (see KeyPair).
    """

    def __init__(
        self,
        peer_id: str,
        *,
        rotation_interval: float = 86400.0,
        max_chain_length: int = 10,
        scheme: str = SCHEME_ED25519,
    ) -> None:
        self._peer_id = peer_id
        self._rotation_interval = rotation_interval
        self._max_chain_length = max_chain_length
        self._scheme = scheme
        self._registry = PeerKeyRegistry()
        self._current_key = KeyPair.generate(scheme=scheme)
        self._registry.register(peer_id, self._current_key)
        self._last_rotation = _time.time()

    @property
    def current_key(self) -> KeyPair:
        return self._current_key

    @property
    def registry(self) -> PeerKeyRegistry:
        return self._registry

    @property
    def peer_id(self) -> str:
        return self._peer_id

    def rotate_key(self) -> Tuple[KeyPair, RevocationEntry]:
        """Rotate to a new key pair.

        The old key signs its own revocation (forward-secure chain).
        Returns the new key pair and the revocation entry for the old key.
        """
        old_key = self._current_key
        new_key = KeyPair.generate(scheme=self._scheme)

        # Old key signs revocation payload (matches RevocationEntry.verify format)
        payload = (
            old_key.key_id.encode("utf-8") + b"\x00"
            + self._peer_id.encode("utf-8") + b"\x00"
            + b"routine rotation\x00"
            + new_key.key_id.encode("utf-8")
        )
        proof = old_key.sign(payload)

        revocation = RevocationEntry(
            key_id=old_key.key_id,
            peer_id=self._peer_id,
            revoked_at=_time.time(),
            reason="routine rotation",
            successor=new_key.key_id,
            proof=proof,
        )

        self._registry.revoke(revocation)
        self._registry.register(self._peer_id, new_key)
        self._current_key = new_key
        self._last_rotation = _time.time()

        return new_key, revocation

    def needs_rotation(self) -> bool:
        """Check if key rotation is due."""
        return (_time.time() - self._last_rotation) >= self._rotation_interval

    def sign(self, message: bytes) -> bytes:
        """Sign a message with the current key."""
        return self._current_key.sign(message)

    def verify_peer(
        self,
        peer_id: str,
        message: bytes,
        signature: bytes,
    ) -> bool:
        """Verify a message signature from a peer.

        Uses the peer's registered key under its recorded scheme.  For an
        HMAC-mode peer that key must be a secret agreed out of band
        (``KeyPair.from_shared_secret``); a key the peer sent over the
        channel being authenticated would let anyone who saw it forge.
        """
        key = self._registry.current_key(peer_id)
        if key is None:
            return False
        return key.verify(message, signature)

    def emergency_revoke(self, reason: str = "compromise") -> RevocationEntry:
        """Emergency key revocation without rotation.

        Used when a key is suspected compromised.  The peer must
        generate a new key through out-of-band means.
        """
        payload = (
            self._current_key.key_id.encode("utf-8") + b"\x00"
            + self._peer_id.encode("utf-8") + b"\x00"
            + reason.encode("utf-8") + b"\x00"
            + b""  # no successor
        )
        revocation = RevocationEntry(
            key_id=self._current_key.key_id,
            peer_id=self._peer_id,
            revoked_at=_time.time(),
            reason=reason,
            proof=self._current_key.sign(payload),
        )
        self._registry.revoke(revocation)
        return revocation

    def __repr__(self) -> str:
        return (
            f"KeyManager(peer={self._peer_id!r}, "
            f"key={self._current_key.key_id!r}, "
            f"peers={self._registry.peer_count})"
        )
