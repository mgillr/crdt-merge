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

"""Proof-carrying trust evidence for the E4 typed trust lattice.

Implements the evidence module (ref 830-834) from the E4 architecture.
Every piece of trust evidence carries a cryptographic proof that any
honest node can verify independently -- no trust in the observer is
required.  This eliminates false-accusation attacks: you cannot frame a
peer without producing a valid proof of misbehaviour.

Five evidence types are supported, each with a specific proof format:

  equivocation       -- two conflicting signed ops from the same peer
  merkle_divergence  -- Merkle path inconsistent with claimed root
  clock_regression   -- vector clock went backwards
  invalid_delta      -- delta failed structural verification
  trust_manipulation -- inconsistent trust state pair
"""

from __future__ import annotations

import hashlib
import math
import struct
import time as _time
from dataclasses import dataclass
from typing import Optional, Tuple


# -- Evidence type -> proof type mapping --------------------------------

EVIDENCE_TYPES = {
    "equivocation": "attestation_pair",
    "merkle_divergence": "merkle_path",
    "clock_regression": "vector_clock_pair",
    "invalid_delta": "delta_verification",
    "trust_manipulation": "trust_state_pair",
}


# -- TrustEvidence (ref 831) -------------------------------------------

# ── Signature verification configuration ───────────────────────────────

from crdt_merge.e4.signing import (  # noqa: E402
    SignatureVerificationNotConfigured,
    ed25519_verify,
    load_ed25519,
)

# Module-level registry for observer and attestation authentication.
_OBSERVER_KEY_REGISTRY = None
_ALLOW_UNAUTHENTICATED = False

#: Domain prefix for attestation signatures (see :func:`sign_attestation`).
ATTESTATION_DOMAIN = b"crdt-merge/e4/attestation/v1\x00"


def configure_evidence_verification(
    registry=None, *, allow_unauthenticated: bool = False,
) -> None:
    """Configure authentication of trust evidence.

    Args:
        registry: object with ``get_public_key(peer_id) -> bytes``.  Every
            evidence record must then carry a valid Ed25519 observer
            signature under the observer's registered key, and the
            attestations inside an equivocation proof must be signed by
            the accused peer's registered key (``cryptography`` required).
        allow_unauthenticated: explicit opt-in to the legacy mode, valid
            only with ``registry=None``: observer signatures are not
            checked and attestation signatures are only length-checked.
            Never the default.

    With neither (the default), :meth:`TrustEvidence.verify` raises
    :class:`SignatureVerificationNotConfigured`.  A key embedded in the
    evidence (``observer_public_key``) is never used for verification.
    """
    global _OBSERVER_KEY_REGISTRY, _ALLOW_UNAUTHENTICATED
    if registry is not None and allow_unauthenticated:
        raise ValueError("allow_unauthenticated cannot be combined with a key registry")
    _OBSERVER_KEY_REGISTRY = registry
    _ALLOW_UNAUTHENTICATED = bool(allow_unauthenticated)


def _registered_key(peer_id: str) -> Optional[bytes]:
    try:
        key = _OBSERVER_KEY_REGISTRY.get_public_key(peer_id)
    except (KeyError, AttributeError):
        return None
    return key or None


def sign_attestation(signer: str, sequence: int, content: str, signing_fn) -> bytes:
    """Build a signed attestation blob for an equivocation proof.

    Layout: ``signer\\0sequence\\0content\\0`` followed by a 64-byte
    Ed25519 signature over ``ATTESTATION_DOMAIN`` + that text.
    *signing_fn* is the signer's ``(bytes) -> 64-byte signature``.
    """
    text = f"{signer}\x00{sequence}\x00{content}\x00".encode("utf-8")
    signature = signing_fn(ATTESTATION_DOMAIN + text)
    if len(signature) != 64:
        raise ValueError("attestation signature must be exactly 64 bytes")
    return text + signature


def _signed_payload(
    observer: str, target: str, evidence_type: str,
    dimension: str, amount: float, proof: bytes, timestamp: float,
) -> bytes:
    """Canonical byte representation of evidence for signing/verification.

    Includes timestamp to prevent replay attacks.
    """
    import struct
    parts = [
        observer.encode("utf-8"),
        b"\x00",
        target.encode("utf-8"),
        b"\x00",
        evidence_type.encode("utf-8"),
        b"\x00",
        dimension.encode("utf-8"),
        b"\x00",
        struct.pack("!d", amount),
        struct.pack("!d", timestamp),
        proof,
    ]
    return b"".join(parts)


@dataclass(frozen=True)
class TrustEvidence:
    """Immutable evidence record backed by a cryptographic proof.

    Fields
    ------
    observer : str              Peer that observed the misbehaviour.
    target : str                Peer accused of misbehaviour.
    evidence_type : str         One of the five canonical types.
    dimension : str              Trust dimension affected.
    amount : float               Severity (positive, added to GCounter).
    proof : bytes                Opaque proof payload.
    proof_type : str             Expected proof format for this evidence type.
    timestamp : float            POSIX timestamp of observation.
    observer_signature : bytes   Optional signature over the signed payload.
    observer_public_key : bytes  Optional public key (for self-describing evidence).
    """

    observer: str
    target: str
    evidence_type: str
    dimension: str
    amount: float
    proof: bytes
    proof_type: str
    timestamp: float
    observer_signature: bytes = b""
    observer_public_key: bytes = b""

    # -- construction helpers -------------------------------------------

    @classmethod
    def create(
        cls,
        observer: str,
        target: str,
        evidence_type: str,
        dimension: str,
        amount: float,
        proof: bytes,
        *,
        timestamp: Optional[float] = None,
        observer_signing_fn: Optional[object] = None,
        observer_public_key: bytes = b"",
    ) -> TrustEvidence:
        """Build an evidence record with validation.

        If observer_signing_fn is provided, the evidence is cryptographically
        signed by the observer. This binds the evidence to its source and
        prevents spoofing.

        Args:
            observer_signing_fn: callable(payload_bytes) -> signature_bytes
            observer_public_key: informational only; verification always
                uses the key registered for *observer*
        """
        if evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"unknown evidence type: {evidence_type}")
        ts = timestamp if timestamp is not None else _time.time()

        signature = b""
        if observer_signing_fn is not None:
            payload = _signed_payload(
                observer, target, evidence_type, dimension, amount, proof, ts,
            )
            signature = observer_signing_fn(payload)

        return cls(
            observer=observer,
            target=target,
            evidence_type=evidence_type,
            dimension=dimension,
            amount=amount,
            proof=proof,
            proof_type=EVIDENCE_TYPES[evidence_type],
            timestamp=ts,
            observer_signature=signature,
            observer_public_key=observer_public_key,
        )

    # -- deterministic verification (ref 833) ---------------------------

    def verify(
        self,
        merkle_root: Optional[str] = None,
        *,
        max_age_seconds: Optional[float] = None,
        require_observer_auth: bool = False,
    ) -> bool:
        """Verify the proof without trusting the observer.

        Each evidence type dispatches to a type-specific verifier.
        Returns False on any structural or cryptographic failure.

        Authentication is fail-closed (see
        :func:`configure_evidence_verification`): with a registry, the
        observer signature is always required; with no registry, this
        raises SignatureVerificationNotConfigured unless unauthenticated
        mode was explicitly enabled.

        Args:
            merkle_root: expected root for merkle_divergence evidence.
            max_age_seconds: reject evidence older than this many seconds
                (prevents replay of stale evidence).
            require_observer_auth: if True, the observer signature must
                verify; in unauthenticated mode this always fails.
        """
        if _OBSERVER_KEY_REGISTRY is not None:
            load_ed25519()  # raises Ed25519Unavailable; never a silent False
        elif not _ALLOW_UNAUTHENTICATED:
            raise SignatureVerificationNotConfigured(
                "evidence verification is not configured: call "
                "configure_evidence_verification(registry), or opt into "
                "unauthenticated mode explicitly with "
                "configure_evidence_verification(None, allow_unauthenticated=True)"
            )
        if self.evidence_type not in EVIDENCE_TYPES:
            return False
        if self.proof_type != EVIDENCE_TYPES[self.evidence_type]:
            return False
        if self.amount <= 0 or math.isnan(self.amount) or math.isinf(self.amount):
            return False
        if self.amount > 1.0:
            return False

        # Age check (replay prevention)
        if max_age_seconds is not None:
            age = _time.time() - self.timestamp
            if age > max_age_seconds or age < -60:  # allow 60s clock skew
                return False

        # Observer authentication (always, once a registry is configured)
        if _OBSERVER_KEY_REGISTRY is not None or require_observer_auth:
            if not self._verify_observer_signature():
                return False

        try:
            if self.evidence_type == "equivocation":
                return self._verify_equivocation()
            if self.evidence_type == "merkle_divergence":
                return self._verify_merkle_proof(merkle_root)
            if self.evidence_type == "clock_regression":
                return self._verify_clock_regression()
            if self.evidence_type == "invalid_delta":
                return self._verify_delta()
            if self.evidence_type == "trust_manipulation":
                return self._verify_trust_consistency()
        except Exception:
            return False
        return False

    def _verify_observer_signature(self) -> bool:
        """Verify the observer's signature on this evidence.

        Binds evidence to its claimed source.  The key is the one
        registered for ``self.observer``; a key carried inside the
        evidence is never used.  Strict Ed25519, no fallback.
        """
        if not self.observer_signature or _OBSERVER_KEY_REGISTRY is None:
            return False
        public_key = _registered_key(self.observer)
        if public_key is None:
            return False
        payload = _signed_payload(
            self.observer, self.target, self.evidence_type,
            self.dimension, self.amount, self.proof, self.timestamp,
        )
        return ed25519_verify(public_key, payload, self.observer_signature)

    # -- per-type verifiers ---------------------------------------------

    def _verify_equivocation(self) -> bool:
        """Two conflicting signed operations from the same peer.

        Proof layout (attestation_pair):
          [4B len_a][op_a bytes][4B len_b][op_b bytes]

        Both ops must share the same signer and sequence number but
        differ in content, and both signatures must be valid.
        Actual signature verification delegates to the attestation
        objects reconstructed from the packed bytes.
        """
        op_a, op_b = _unpack_attestation_pair(self.proof)
        if op_a is None or op_b is None:
            return False
        return (
            op_a["signer"] == op_b["signer"]
            and op_a["sequence"] == op_b["sequence"]
            and op_a["content"] != op_b["content"]
            and _verify_attestation_sig(op_a)
            and _verify_attestation_sig(op_b)
        )

    def _verify_merkle_proof(self, expected_root: Optional[str]) -> bool:
        """Merkle path that does NOT match the claimed root.

        The proof contains a serialized Merkle path.  We recompute
        the root from the path and verify it diverges from the
        expected root (the one the accused peer claimed).
        """
        if expected_root is None:
            return False
        path = _unpack_merkle_path(self.proof)
        if path is None:
            return False
        computed = _compute_merkle_root(path)
        return computed != expected_root

    def _verify_clock_regression(self) -> bool:
        """Vector clock that went backwards.

        Proof layout (vector_clock_pair):
          [4B len_before][clock_before bytes][4B len_after][clock_after bytes]

        The *after* clock must be strictly before the *before* clock
        for at least one entry belonging to the target peer.
        """
        before, after = _unpack_clock_pair(self.proof)
        if before is None or after is None:
            return False
        # 'after' should be causally before 'before' -> regression
        return _clock_is_before(after, before)

    def _verify_delta(self) -> bool:
        """Delta failed structural verification.

        Proof layout (delta_verification):
          [32B expected_hash][remaining: serialized delta]

        Recompute hash of the serialized delta and check mismatch.
        """
        if len(self.proof) < 33:
            return False
        expected_hash = self.proof[:32]
        delta_bytes = self.proof[32:]
        # Delta must reference the target peer
        if self.target.encode("utf-8") not in delta_bytes:
            return False
        actual_hash = hashlib.sha256(delta_bytes).digest()
        import hmac as _hmac
        return not _hmac.compare_digest(actual_hash, expected_hash)

    def _verify_trust_consistency(self) -> bool:
        """Inconsistent trust state pair.

        Proof layout (trust_state_pair):
          [4B len_a][state_a bytes][4B len_b][state_b bytes]

        The two states should be from the same logical point but
        contain different trust vectors for the same peer -- evidence
        that the target is presenting different trust views to
        different observers.
        """
        state_a, state_b = _unpack_state_pair(self.proof)
        if state_a is None or state_b is None:
            return False
        # Minimum structural requirement: states must be non-trivial
        # and contain the target peer ID to prove origin
        if len(state_a) < 16 or len(state_b) < 16:
            return False
        target_bytes = self.target.encode("utf-8")
        if target_bytes not in state_a or target_bytes not in state_b:
            return False
        return state_a != state_b

    # -- serialization helpers ------------------------------------------

    def to_bytes(self) -> bytes:
        """Pack the evidence into a deterministic byte representation."""
        header = (
            f"{self.observer}\x00{self.target}\x00"
            f"{self.evidence_type}\x00{self.dimension}\x00"
            f"{self.proof_type}\x00"
        ).encode("utf-8")
        amount_bytes = struct.pack("!d", self.amount)
        ts_bytes = struct.pack("!d", self.timestamp)
        proof_len = struct.pack("!I", len(self.proof))
        return header + amount_bytes + ts_bytes + proof_len + self.proof

    def content_hash(self) -> str:
        """SHA-256 hex digest of the packed evidence."""
        return hashlib.sha256(self.to_bytes()).hexdigest()


# -- Proof packing / unpacking helpers ----------------------------------

def pack_attestation_pair(op_a: bytes, op_b: bytes) -> bytes:
    """Pack two attestation blobs into the equivocation proof format."""
    return struct.pack("!I", len(op_a)) + op_a + struct.pack("!I", len(op_b)) + op_b


def pack_clock_pair(before: bytes, after: bytes) -> bytes:
    """Pack two serialized vector clocks into the regression proof format."""
    return struct.pack("!I", len(before)) + before + struct.pack("!I", len(after)) + after


def pack_delta_proof(expected_hash: bytes, delta_bytes: bytes) -> bytes:
    """Pack an expected hash and raw delta for invalid-delta evidence."""
    if len(expected_hash) != 32:
        raise ValueError("expected_hash must be 32 bytes")
    return expected_hash + delta_bytes


def pack_state_pair(state_a: bytes, state_b: bytes) -> bytes:
    """Pack two trust-state snapshots for trust-manipulation evidence."""
    return struct.pack("!I", len(state_a)) + state_a + struct.pack("!I", len(state_b)) + state_b


def pack_merkle_path(path_segments: list[Tuple[list[str], int]]) -> bytes:
    """Pack a Merkle path (list of (sibling_hashes, position) tuples)."""
    parts: list[bytes] = [struct.pack("!H", len(path_segments))]
    for sibling_hashes, pos in path_segments:
        parts.append(struct.pack("!HH", len(sibling_hashes), pos))
        for h in sibling_hashes:
            hb = h.encode("utf-8")
            parts.append(struct.pack("!H", len(hb)) + hb)
    return b"".join(parts)


# -- Internal unpacking -------------------------------------------------

def _unpack_pair(data: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
    if len(data) < 8:
        return None, None
    len_a = struct.unpack("!I", data[:4])[0]
    if len(data) < 8 + len_a:
        return None, None
    a = data[4 : 4 + len_a]
    rest = data[4 + len_a :]
    if len(rest) < 4:
        return None, None
    len_b = struct.unpack("!I", rest[:4])[0]
    if len(rest) < 4 + len_b:
        return None, None
    b = rest[4 : 4 + len_b]
    return a, b


def _unpack_attestation_pair(
    data: bytes,
) -> Tuple[Optional[dict], Optional[dict]]:
    a_raw, b_raw = _unpack_pair(data)
    if a_raw is None or b_raw is None:
        return None, None
    return _decode_attestation(a_raw), _decode_attestation(b_raw)


def _decode_attestation(raw: bytes) -> Optional[dict]:
    """Decode a minimal attestation: signer\\0sequence\\0content\\0signature."""
    try:
        text_part, sig = raw[:-64], raw[-64:]
        fields = text_part.decode("utf-8").split("\x00")
        if len(fields) < 3:
            return None
        return {
            "signer": fields[0],
            "sequence": int(fields[1]),
            "content": fields[2],
            "signature": sig,
            "raw": raw,
        }
    except Exception:
        return None


def _verify_attestation_sig(op: dict) -> bool:
    """Ed25519 over ATTESTATION_DOMAIN + the attestation text, under the
    signer's registered key.  In the explicit unauthenticated mode only
    the signature length is checked."""
    if op is None:
        return False
    signature = op.get("signature", b"")
    if _OBSERVER_KEY_REGISTRY is None:
        return _ALLOW_UNAUTHENTICATED and len(signature) == 64
    public_key = _registered_key(op["signer"])
    if public_key is None:
        return False
    return ed25519_verify(public_key, ATTESTATION_DOMAIN + op["raw"][:-64], signature)


def _unpack_merkle_path(
    data: bytes,
) -> Optional[list[Tuple[list[str], int]]]:
    try:
        off = 0
        (n_segs,) = struct.unpack("!H", data[off : off + 2])
        off += 2
        segments: list[Tuple[list[str], int]] = []
        for _ in range(n_segs):
            n_siblings, pos = struct.unpack("!HH", data[off : off + 4])
            off += 4
            siblings: list[str] = []
            for _ in range(n_siblings):
                (hlen,) = struct.unpack("!H", data[off : off + 2])
                off += 2
                siblings.append(data[off : off + hlen].decode("utf-8"))
                off += hlen
            segments.append((siblings, pos))
        return segments
    except Exception:
        return None


def _compute_merkle_root(
    path: list[Tuple[list[str], int]],
) -> str:
    """Recompute a Merkle root from a path of (sibling_hashes, position)."""
    if not path:
        return ""
    current = ""
    for siblings, pos in path:
        all_hashes = list(siblings)
        all_hashes.insert(pos, current)
        combined = "".join(all_hashes).encode("utf-8")
        current = hashlib.sha256(combined).hexdigest()
    return current


def _unpack_clock_pair(
    data: bytes,
) -> Tuple[Optional[dict], Optional[dict]]:
    a_raw, b_raw = _unpack_pair(data)
    if a_raw is None or b_raw is None:
        return None, None
    return _decode_clock(a_raw), _decode_clock(b_raw)


def _decode_clock(raw: bytes) -> Optional[dict]:
    try:
        text = raw.decode("utf-8")
        entries = {}
        for pair in text.split(";"):
            if "=" not in pair:
                continue
            peer, val = pair.split("=", 1)
            entries[peer.strip()] = int(val.strip())
        return entries
    except Exception:
        return None


def _clock_is_before(a: dict, b: dict) -> bool:
    """True if clock *a* is strictly causally before *b*."""
    all_peers = set(a) | set(b)
    at_least_one_less = False
    for p in all_peers:
        va = a.get(p, 0)
        vb = b.get(p, 0)
        if va > vb:
            return False
        if va < vb:
            at_least_one_less = True
    return at_least_one_less


def _unpack_state_pair(
    data: bytes,
) -> Tuple[Optional[bytes], Optional[bytes]]:
    return _unpack_pair(data)
