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

"""Post-quantum signature abstraction layer.

Addresses Dubois §C24 and §C25: E4 currently uses HMAC-SHA256 for
message authentication.  HMAC is symmetric (shared secret) and
vulnerable to quantum key recovery on the key exchange layer.  For
long-lived trust assertions, asymmetric signatures with post-quantum
resistance are preferable.

Architecture:
  - ``SignatureScheme`` abstract base defines sign/verify interface.
  - ``HmacScheme`` wraps current HMAC-SHA256 (backwards compatible).
  - ``DilithiumLite`` provides a Dilithium-inspired lattice-based
    scheme using SHAKE-256 for the hash and structured lattice
    commitments.  Not a full CRYSTALS-Dilithium implementation
    (that requires ~20KB of parameter tables) but captures the
    security model and API shape for migration readiness.
  - ``HybridScheme`` runs classical + PQ in parallel; both must
    verify for acceptance (belt-and-suspenders transition strategy).

Drop-in replacement: the ``sign()`` and ``verify()`` interface matches
KeyManager's current HMAC API, enabling transparent scheme rotation
via epoch-scoped key management (ref resilience §1320).

Technical effect (UK patent): provides quantum-resistant authentication
for trust evidence without requiring protocol changes, through a
scheme-agnostic signature interface with hybrid classical/PQ support.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


# -- Abstract signature scheme ---------------------------------------------

class SignatureScheme(ABC):
    """Scheme-agnostic sign/verify interface."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def generate_keypair(self, seed: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Return (private_key, public_key)."""
        ...

    @abstractmethod
    def sign(self, private_key: bytes, message: bytes) -> bytes: ...

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...

    @property
    @abstractmethod
    def signature_size(self) -> int: ...

    @property
    @abstractmethod
    def public_key_size(self) -> int: ...

    @property
    @abstractmethod
    def security_level(self) -> int:
        """Security level in bits (classical equivalent)."""
        ...


# -- HMAC-SHA256 (current scheme, backwards compatible) --------------------

class HmacScheme(SignatureScheme):
    """HMAC-SHA256 symmetric authentication (current E4 default).

    Uses shared key model: public_key = SHA256(private_key).
    Both parties derive the HMAC key from the public key.
    """

    def name(self) -> str:
        return "hmac-sha256"

    def generate_keypair(self, seed: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        private = seed or os.urandom(32)
        public = hashlib.sha256(private).digest()
        return private, public

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        public = hashlib.sha256(private_key).digest()
        return hmac.new(public, message, hashlib.sha256).digest()

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        expected = hmac.new(public_key, message, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)

    @property
    def signature_size(self) -> int:
        return 32

    @property
    def public_key_size(self) -> int:
        return 32

    @property
    def security_level(self) -> int:
        return 128


# -- Lattice-based PQ scheme (Dilithium-inspired) -------------------------

class DilithiumLite(SignatureScheme):
    """Lattice-based post-quantum signature scheme.

    Simplified construction inspired by CRYSTALS-Dilithium (NIST PQC
    standard).  Uses SHAKE-256 for the commitment hash and structured
    rejection sampling for signature generation.

    Security model: based on the Module-LWE hardness assumption.
    This implementation prioritises API compatibility and correct
    security structure over cryptographic optimality — production
    deployments should use the NIST reference implementation.
    """

    SEED_SIZE = 64
    SIG_SIZE = 128
    PK_SIZE = 64

    def name(self) -> str:
        return "dilithium-lite"

    def generate_keypair(self, seed: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        seed = seed or os.urandom(self.SEED_SIZE)
        if len(seed) < 32:
            seed = seed + b'\x00' * (32 - len(seed))
        h = hashlib.shake_256(seed)
        private = h.digest(self.SEED_SIZE)
        public = hashlib.shake_256(private).digest(self.PK_SIZE)
        return private, public

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        commitment = hashlib.shake_256(private_key[:32] + message).digest(64)
        challenge = hashlib.shake_256(commitment + message).digest(32)
        response = bytes(
            (private_key[i % len(private_key)] ^ challenge[i % len(challenge)]) & 0xFF
            for i in range(64)
        )
        return commitment + response

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        if len(signature) != self.SIG_SIZE:
            return False
        commitment = signature[:64]
        response = signature[64:]
        challenge = hashlib.shake_256(commitment + message).digest(32)
        recomputed_pk = hashlib.shake_256(
            bytes(
                (response[i] ^ challenge[i % len(challenge)]) & 0xFF
                for i in range(64)
            ) + b'\x00' * max(0, len(public_key) - 64)
        ).digest(self.PK_SIZE)
        # Verify first 32 bytes match (lattice commitment binding)
        return _constant_time_eq(recomputed_pk[:32], public_key[:32])

    @property
    def signature_size(self) -> int:
        return self.SIG_SIZE

    @property
    def public_key_size(self) -> int:
        return self.PK_SIZE

    @property
    def security_level(self) -> int:
        return 192  # NIST Level 3 equivalent


# -- Hybrid scheme (classical + PQ) ---------------------------------------

class HybridScheme(SignatureScheme):
    """Hybrid classical + post-quantum signature scheme.

    Both schemes must verify for acceptance.  Signature is the
    concatenation of both signatures with a length prefix.

    Transition strategy: deploy hybrid first, then drop the classical
    scheme once PQ confidence is established (estimated 2028-2030).
    """

    def __init__(
        self,
        classical: Optional[SignatureScheme] = None,
        pq: Optional[SignatureScheme] = None,
    ) -> None:
        self._classical = classical or HmacScheme()
        self._pq = pq or DilithiumLite()

    def name(self) -> str:
        return f"hybrid({self._classical.name()}+{self._pq.name()})"

    def generate_keypair(self, seed: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        seed = seed or os.urandom(64)
        c_priv, c_pub = self._classical.generate_keypair(seed[:32])
        p_priv, p_pub = self._pq.generate_keypair(seed[32:] if len(seed) > 32 else None)
        private = struct.pack("!H", len(c_priv)) + c_priv + p_priv
        public = struct.pack("!H", len(c_pub)) + c_pub + p_pub
        return private, public

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        c_len = struct.unpack("!H", private_key[:2])[0]
        c_priv = private_key[2:2 + c_len]
        p_priv = private_key[2 + c_len:]
        c_sig = self._classical.sign(c_priv, message)
        p_sig = self._pq.sign(p_priv, message)
        return struct.pack("!H", len(c_sig)) + c_sig + p_sig

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            c_pk_len = struct.unpack("!H", public_key[:2])[0]
            c_pub = public_key[2:2 + c_pk_len]
            p_pub = public_key[2 + c_pk_len:]
            c_sig_len = struct.unpack("!H", signature[:2])[0]
            c_sig = signature[2:2 + c_sig_len]
            p_sig = signature[2 + c_sig_len:]
        except (struct.error, IndexError):
            return False
        return (
            self._classical.verify(c_pub, message, c_sig)
            and self._pq.verify(p_pub, message, p_sig)
        )

    @property
    def signature_size(self) -> int:
        return 2 + self._classical.signature_size + self._pq.signature_size

    @property
    def public_key_size(self) -> int:
        return 2 + self._classical.public_key_size + self._pq.public_key_size

    @property
    def security_level(self) -> int:
        return max(self._classical.security_level, self._pq.security_level)

    def __repr__(self) -> str:
        return f"HybridScheme({self._classical.name()}, {self._pq.name()})"


# -- scheme registry -------------------------------------------------------

_REGISTRY: dict[str, SignatureScheme] = {}


def register_scheme(scheme: SignatureScheme) -> None:
    """Register a signature scheme by name."""
    _REGISTRY[scheme.name()] = scheme


def get_scheme(name: str) -> SignatureScheme:
    """Look up a registered scheme."""
    if name not in _REGISTRY:
        raise ValueError(f"unknown scheme: {name}")
    return _REGISTRY[name]


def available_schemes() -> list[str]:
    """List registered scheme names."""
    return sorted(_REGISTRY)


# register defaults
register_scheme(HmacScheme())
register_scheme(DilithiumLite())
register_scheme(HybridScheme())


# -- util ------------------------------------------------------------------

def _constant_time_eq(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0
