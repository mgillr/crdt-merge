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

"""Aggregate proof-carrying operations for the E4 architecture.

Implements the aggregate PCO (ref 880-886) from the E4 specification.
Each CRDT operation carries a single 128-byte proof covering four
independently derivable properties:

  integrity  -- Merkle root matches local computation
  causality  -- clock snapshot consistent with known state
  trust      -- originator meets minimum trust threshold
  minimality -- delta bounds match claimed subtrees

Wire format: 64 B signature + 32 B aggregate hash + 32 B metadata.
Verification cost scales with the adaptive immune level (0-3).
"""

from __future__ import annotations

import hashlib
import struct
import time as _time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from crdt_merge.e4.typed_trust import TypedTrustScore

# -- SubtreeRef (shared with projection_delta) --------------------------

@dataclass(frozen=True)
class SubtreeRef:
    """Reference to a subtree in the high-arity Merkle tree (ref 811)."""

    path: Tuple[int, ...]    # index path from root, 0..B-1 per level
    depth: int               # depth in tree (max ~4 for B=256, n=1B)
    old_hash: str            # hash before change
    new_hash: str            # hash after change


# -- AggregateProofCarryingOperation -----------------------------------

@dataclass(frozen=True)
class AggregateProofCarryingOperation:
    """Single aggregate proof covering four CRDT operation properties.

    aggregate_hash = H(merkle_root || clock_state || trust_hash || bounds_hash)
    signature      = Ed25519(aggregate_hash, originator_key)

    Wire format: 128 bytes total
      - signature        64 B
      - aggregate_hash   32 B
      - metadata         32 B  (version, flags, timestamp, reserved)
    """

    aggregate_hash: bytes       # 32 bytes
    signature: bytes            # 64 bytes (Ed25519)
    originator_id: str
    metadata: bytes             # 32 bytes: version + flags + timestamp + pad

    # Property witnesses -- kept for independent derivation, not sent
    # on the wire as separate verified blobs.
    merkle_root_at_creation: str
    clock_snapshot: bytes
    trust_vector_hash: str
    delta_bounds: Tuple[SubtreeRef, ...]

    # -- construction ---------------------------------------------------

    @classmethod
    def build(
        cls,
        originator_id: str,
        signing_fn: object,
        merkle_root: str,
        clock_snapshot: bytes,
        trust_vector_hash: str,
        delta_bounds: Sequence[SubtreeRef],
        *,
        version: int = 1,
        flags: int = 0,
    ) -> AggregateProofCarryingOperation:
        """Compute the aggregate hash, sign it, and return a ready PCO."""
        bounds_tuple = tuple(delta_bounds)
        agg = _compute_aggregate_hash(
            merkle_root, clock_snapshot, trust_vector_hash, bounds_tuple,
        )
        meta = _build_metadata(version, flags)

        # signing_fn(hash_bytes) -> 64-byte signature
        sig = signing_fn(agg) if callable(signing_fn) else b"\x00" * 64
        if len(sig) != 64:
            raise ValueError("signature must be exactly 64 bytes")

        return cls(
            aggregate_hash=agg,
            signature=sig,
            originator_id=originator_id,
            metadata=meta,
            merkle_root_at_creation=merkle_root,
            clock_snapshot=clock_snapshot,
            trust_vector_hash=trust_vector_hash,
            delta_bounds=bounds_tuple,
        )

    # -- adaptive immune verification (ref 895) -------------------------

    def verify(
        self,
        state: object,
        trust_lattice: object,
        *,
        verification_level: int = 2,
    ) -> bool:
        """Verify at the specified adaptive immune level.

        Level 0: signature only                    O(1)
        Level 1: signature + Merkle root check     O(1)
        Level 2: full derivation of all four props O(k)
        Level 3: reject unconditionally            O(1)
        """
        if verification_level == 3:
            return False

        if not self._verify_signature():
            return False

        if verification_level == 0:
            return True

        if not self._derive_integrity(state):
            return False

        if verification_level == 1:
            return True

        if not self._derive_causality(state):
            return False
        if not self._derive_trust(trust_lattice):
            return False
        if not self._derive_minimality():
            return False

        return True

    # -- wire format ----------------------------------------------------

    def to_wire(self) -> bytes:
        """Serialize to the 128-byte wire format."""
        if len(self.signature) != 64:
            raise ValueError("bad signature length")
        if len(self.aggregate_hash) != 32:
            raise ValueError("bad hash length")
        meta = self.metadata[:32].ljust(32, b"\x00")
        return self.signature + self.aggregate_hash + meta

    @classmethod
    def from_wire(
        cls,
        data: bytes,
        originator_id: str,
        merkle_root: str = "",
        clock_snapshot: bytes = b"",
        trust_vector_hash: str = "",
        delta_bounds: Tuple[SubtreeRef, ...] = (),
    ) -> AggregateProofCarryingOperation:
        """Deserialize from the 128-byte wire format."""
        if len(data) < 128:
            raise ValueError("wire data must be at least 128 bytes")
        sig = data[:64]
        agg = data[64:96]
        meta = data[96:128]
        return cls(
            aggregate_hash=agg,
            signature=sig,
            originator_id=originator_id,
            metadata=meta,
            merkle_root_at_creation=merkle_root,
            clock_snapshot=clock_snapshot,
            trust_vector_hash=trust_vector_hash,
            delta_bounds=delta_bounds,
        )

    # -- internal verification ------------------------------------------

    def _verify_signature(self) -> bool:
        """Verify Ed25519 signature over the aggregate hash."""
        expected = _compute_aggregate_hash(
            self.merkle_root_at_creation,
            self.clock_snapshot,
            self.trust_vector_hash,
            self.delta_bounds,
        )
        if expected != self.aggregate_hash:
            return False
        return _verify_ed25519(
            self.signature, self.aggregate_hash, self.originator_id,
        )

    def _derive_integrity(self, state: object) -> bool:
        """Check Merkle root against known state (ref 883a)."""
        merkle = getattr(state, "merkle", None)
        if merkle is None:
            return True  # no Merkle tree available for comparison
        is_plausible = getattr(merkle, "is_plausible_root", None)
        if is_plausible is None:
            return True
        return is_plausible(self.merkle_root_at_creation)

    def _derive_causality(self, state: object) -> bool:
        """Check clock consistency with known causal history (ref 883b)."""
        clock = getattr(state, "clock", None)
        if clock is None:
            return True
        is_consistent = getattr(clock, "is_consistent_with", None)
        if is_consistent is None:
            return True
        return is_consistent(self.clock_snapshot)

    def _derive_trust(self, trust_lattice: object) -> bool:
        """Check originator meets minimum trust (ref 883c)."""
        get_trust = getattr(trust_lattice, "get_trust", None)
        if get_trust is None:
            return True
        trust: TypedTrustScore = get_trust(self.originator_id)
        from crdt_merge.e4.typed_trust import QUARANTINE_THRESHOLD
        return trust.overall_trust() >= QUARANTINE_THRESHOLD

    def _derive_minimality(self) -> bool:
        """Check delta bounds are internally consistent (ref 883d)."""
        return all(
            s.depth >= 0 and s.old_hash != s.new_hash
            for s in self.delta_bounds
        )

    # -- repr -----------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"AggregatePCO(originator={self.originator_id!r}, "
            f"hash={self.aggregate_hash[:8].hex()}..., "
            f"bounds={len(self.delta_bounds)})"
        )


# -- Module-level helpers -----------------------------------------------

def _compute_aggregate_hash(
    merkle_root: str,
    clock_snapshot: bytes,
    trust_vector_hash: str,
    delta_bounds: Tuple[SubtreeRef, ...],
) -> bytes:
    """H(merkle_root || clock_state || trust_hash || bounds_hash)."""
    bounds_hash = hashlib.sha256(
        b"".join(s.new_hash.encode("utf-8") for s in delta_bounds)
    ).digest()
    return hashlib.sha256(
        merkle_root.encode("utf-8")
        + clock_snapshot
        + trust_vector_hash.encode("utf-8")
        + bounds_hash
    ).digest()


def _build_metadata(version: int = 1, flags: int = 0) -> bytes:
    """32-byte metadata block: version(2) + flags(2) + timestamp(8) + pad(20)."""
    ts = int(_time.time())
    return struct.pack("!HHQ", version, flags, ts) + b"\x00" * 20


# ── Signature verification ────────────────────────────────────────────────

from crdt_merge.e4.signing import (  # noqa: E402
    SignatureVerificationNotConfigured,
    ed25519_verify,
    has_ed25519,
    load_ed25519,
)

# Module-level peer key registry.  Verification is strict Ed25519 against
# the registered key.  With no registry, verification raises unless the
# caller explicitly opted into unsigned mode.
_PEER_KEY_REGISTRY = None
_ALLOW_UNSIGNED = False


def configure_ed25519_verification(registry=None, *, allow_unsigned: bool = False) -> None:
    """Configure PCO signature verification.

    Args:
        registry: object with ``get_public_key(peer_id) -> bytes``.  Every
            PCO signature is then checked as Ed25519 under the originator's
            registered key (``cryptography`` required).
        allow_unsigned: explicit opt-in to the legacy unsigned mode, valid
            only with ``registry=None``: any 64-byte value is accepted as a
            signature, so nothing is authenticated.  Never the default.

    With neither (the default), verifying a PCO signature raises
    :class:`SignatureVerificationNotConfigured`.
    """
    global _PEER_KEY_REGISTRY, _ALLOW_UNSIGNED
    if registry is not None and allow_unsigned:
        raise ValueError("allow_unsigned cannot be combined with a key registry")
    _PEER_KEY_REGISTRY = registry
    _ALLOW_UNSIGNED = bool(allow_unsigned)


def has_real_crypto() -> bool:
    """Return True if the cryptography package is available."""
    return has_ed25519()


def _verify_ed25519(signature: bytes, message: bytes, peer_id: str) -> bool:
    """Strict Ed25519 verification of *signature* under *peer_id*'s key.

    No registry: raises SignatureVerificationNotConfigured, unless unsigned
    mode was explicitly enabled.  Registry: True only for a valid Ed25519
    signature under the registered 32-byte key; raises Ed25519Unavailable
    when the cryptography package is missing.  There is no other path.
    """
    if _PEER_KEY_REGISTRY is None:
        if _ALLOW_UNSIGNED:
            return isinstance(signature, (bytes, bytearray)) and len(signature) == 64
        raise SignatureVerificationNotConfigured(
            "PCO signature verification is not configured: call "
            "configure_ed25519_verification(registry), or opt into unsigned "
            "mode explicitly with configure_ed25519_verification(None, "
            "allow_unsigned=True)"
        )
    load_ed25519()  # raises Ed25519Unavailable before any lookup
    try:
        public_key = _PEER_KEY_REGISTRY.get_public_key(peer_id)
    except (KeyError, AttributeError):
        return False
    if not public_key:
        return False
    return ed25519_verify(public_key, message, signature)
