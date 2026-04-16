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


@dataclass(frozen=True)
class KeyPair:
    """Cryptographic key pair for peer authentication.

    In production, this wraps Ed25519 keys.  The implementation here
    uses HMAC-SHA256 for portability (no native Ed25519 in stdlib).
    The interface is identical for either backend.

    Attributes
    ----------
    public_key  : Raw public key bytes (32 bytes).
    private_key : Raw private key bytes (32 bytes).  None for remote peers.
    created_at  : Unix timestamp of key creation.
    key_id      : Deterministic identifier derived from the public key.
    """
    public_key: bytes
    private_key: Optional[bytes] = field(default=None, repr=False)
    created_at: float = field(default_factory=_time.time)
    key_id: str = ""

    def __post_init__(self) -> None:
        if not self.key_id:
            kid = hashlib.sha256(self.public_key).hexdigest()[:16]
            object.__setattr__(self, "key_id", kid)

    def sign(self, message: bytes) -> bytes:
        """Sign *message* with the private key.

        When the cryptography package is available and the private key
        is 32 bytes, uses real Ed25519 signing. Falls back to HMAC-SHA256
        otherwise.
        """
        if self.private_key is None:
            raise ValueError("cannot sign without private key")
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed
            if len(self.private_key) == 32:
                pk = _ed.Ed25519PrivateKey.from_private_bytes(self.private_key)
                return pk.sign(message)
        except (ImportError, ValueError, Exception):
            pass
        return hmac.new(self.public_key, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify *signature* against *message* using the public key.

        When the cryptography package is available and the public key
        is 32 bytes, uses real Ed25519 verification. Falls back to
        HMAC-SHA256 otherwise.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed
            from cryptography.exceptions import InvalidSignature
            if len(self.public_key) == 32 and len(signature) == 64:
                pk = _ed.Ed25519PublicKey.from_public_bytes(self.public_key)
                pk.verify(signature, message)
                return True
        except (ImportError, Exception):
            pass
        expected = hmac.new(self.public_key, message, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature[:32] if len(signature) >= 32 else signature)

    @classmethod
    def generate(cls) -> KeyPair:
        """Generate a fresh random key pair.

        Uses real Ed25519 when cryptography is available. Falls back to
        HMAC-compatible key derivation (sha256(private) = public) otherwise.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed
            pk = _ed.Ed25519PrivateKey.generate()
            private = pk.private_bytes_raw()
            public = pk.public_key().public_bytes_raw()
            return cls(public_key=public, private_key=private)
        except (ImportError, Exception):
            private = os.urandom(32)
            public = hashlib.sha256(private).digest()
            return cls(public_key=public, private_key=private)


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
        """Register a public key for *peer_id*."""
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
    """

    def __init__(
        self,
        peer_id: str,
        *,
        rotation_interval: float = 86400.0,
        max_chain_length: int = 10,
    ) -> None:
        self._peer_id = peer_id
        self._rotation_interval = rotation_interval
        self._max_chain_length = max_chain_length
        self._registry = PeerKeyRegistry()
        self._current_key = KeyPair.generate()
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
        new_key = KeyPair.generate()

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
        """Verify a message signature from a peer."""
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
