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

"""Tests for ProofCarryingEvidence (TrustEvidence).

Covers evidence creation, cryptographic verification, tamper detection,
serialization roundtrip, and invalid proofs.
"""

import hashlib
import struct
import time

import pytest

from crdt_merge.e4.proof_evidence import (
    EVIDENCE_TYPES,
    TrustEvidence,
    pack_attestation_pair,
    pack_clock_pair,
    pack_delta_proof,
    pack_merkle_path,
    pack_state_pair,
)
from e4_factories import make_attestation_blob, make_equivocation_proof, make_clock_regression_proof, make_invalid_delta_proof, make_state_pair_proof


# ---------------------------------------------------------------------------
# Evidence creation
# ---------------------------------------------------------------------------

class TestTrustEvidenceCreation:

    def test_create_equivocation(self):
        """Creating equivocation evidence succeeds with valid type."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof(),
        )
        assert ev.evidence_type == "equivocation"
        assert ev.proof_type == "attestation_pair"

    def test_create_merkle_divergence(self):
        """Creating merkle_divergence evidence succeeds."""
        proof = pack_merkle_path([(["sibling_hash"], 0)])
        ev = TrustEvidence.create(
            observer="alice", target="bob",
            evidence_type="merkle_divergence", dimension="integrity",
            amount=0.05, proof=proof,
        )
        assert ev.proof_type == "merkle_path"

    def test_create_clock_regression(self):
        """Creating clock_regression evidence succeeds."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="clock_regression", dimension="causality",
            amount=0.1, proof=make_clock_regression_proof(),
        )
        assert ev.proof_type == "vector_clock_pair"

    def test_create_invalid_delta(self):
        """Creating invalid_delta evidence succeeds."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(),
        )
        assert ev.proof_type == "delta_verification"

    def test_create_trust_manipulation(self):
        """Creating trust_manipulation evidence succeeds."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="trust_manipulation", dimension="consistency",
            amount=0.1, proof=make_state_pair_proof(),
        )
        assert ev.proof_type == "trust_state_pair"

    def test_create_unknown_type_raises(self):
        """Unknown evidence type raises ValueError."""
        with pytest.raises(ValueError, match="unknown evidence type"):
            TrustEvidence.create(
                observer="a", target="b",
                evidence_type="unknown_type", dimension="integrity",
                amount=0.1, proof=b"\x00",
            )

    def test_create_uses_current_time(self):
        """Timestamp defaults to near-current time."""
        before = time.time()
        ev = TrustEvidence.create(
            observer="a", target="b",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof(),
        )
        after = time.time()
        assert before <= ev.timestamp <= after

    def test_create_custom_timestamp(self):
        """Custom timestamp is honoured."""
        ev = TrustEvidence.create(
            observer="a", target="b",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof(),
            timestamp=12345.0,
        )
        assert ev.timestamp == 12345.0


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class TestTrustEvidenceVerification:

    def test_verify_equivocation(self):
        """Valid equivocation proof verifies True."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof("eve", 1),
        )
        assert ev.verify() is True

    def test_verify_equivocation_same_content_fails(self):
        """Equivocation with identical content fails verification."""
        op_a = make_attestation_blob("eve", 1, "same_content")
        op_b = make_attestation_blob("eve", 1, "same_content")
        proof = pack_attestation_pair(op_a, op_b)
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=proof,
        )
        assert ev.verify() is False

    def test_verify_clock_regression(self):
        """Valid clock regression proof verifies True."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="clock_regression", dimension="causality",
            amount=0.1, proof=make_clock_regression_proof("eve"),
        )
        assert ev.verify() is True

    def test_verify_invalid_delta(self):
        """Valid invalid-delta proof verifies True (hash mismatch)."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(),
        )
        assert ev.verify() is True

    def test_verify_trust_manipulation(self):
        """Valid trust-manipulation proof verifies True (different states)."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="trust_manipulation", dimension="consistency",
            amount=0.1, proof=make_state_pair_proof(),
        )
        assert ev.verify() is True

    def test_verify_zero_amount_fails(self):
        """Evidence with amount <= 0 fails verification."""
        ev_bad = TrustEvidence(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.0, proof=make_equivocation_proof(),
            proof_type="attestation_pair", timestamp=1.0,
        )
        assert ev_bad.verify() is False

    def test_verify_wrong_proof_type_fails(self):
        """Mismatched proof_type fails verification."""
        ev = TrustEvidence(
            observer="a", target="b",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=make_equivocation_proof(),
            proof_type="merkle_path",
            timestamp=1.0,
        )
        assert ev.verify() is False

    def test_verify_truncated_proof_fails(self):
        """Truncated proof data returns False gracefully."""
        ev = TrustEvidence.create(
            observer="alice", target="eve",
            evidence_type="equivocation", dimension="integrity",
            amount=0.1, proof=b"\x00\x01",
        )
        assert ev.verify() is False


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestTrustEvidenceSerialization:

    def test_to_bytes_deterministic(self):
        """to_bytes() is deterministic."""
        ev = TrustEvidence.create(
            observer="a", target="b",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(target="b"),
            timestamp=100.0,
        )
        assert ev.to_bytes() == ev.to_bytes()

    def test_content_hash_hex(self):
        """content_hash returns valid SHA-256 hex."""
        ev = TrustEvidence.create(
            observer="a", target="b",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(target="b"),
            timestamp=100.0,
        )
        h = ev.content_hash()
        assert len(h) == 64
        int(h, 16)

    def test_content_hash_changes_on_mutation(self):
        """Different evidence produces different content hashes."""
        ev1 = TrustEvidence.create(
            observer="a", target="b",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(target="b"),
            timestamp=100.0,
        )
        ev2 = TrustEvidence.create(
            observer="a", target="c",
            evidence_type="invalid_delta", dimension="integrity",
            amount=0.1, proof=make_invalid_delta_proof(target="c"),
            timestamp=100.0,
        )
        assert ev1.content_hash() != ev2.content_hash()


# ---------------------------------------------------------------------------
# Pack helpers
# ---------------------------------------------------------------------------

class TestPackHelpers:

    def test_pack_attestation_pair_roundtrip(self):
        """pack_attestation_pair produces parsable bytes."""
        op_a = b"blob_a_" + b"\x00" * 64
        op_b = b"blob_b_" + b"\x00" * 64
        data = pack_attestation_pair(op_a, op_b)
        assert len(data) > 0
        len_a = struct.unpack("!I", data[:4])[0]
        assert data[4:4 + len_a] == op_a

    def test_pack_clock_pair(self):
        """pack_clock_pair produces parsable bytes."""
        before = b"peer=5"
        after = b"peer=3"
        data = pack_clock_pair(before, after)
        len_b = struct.unpack("!I", data[:4])[0]
        assert data[4:4 + len_b] == before

    def test_pack_delta_proof_requires_32_byte_hash(self):
        """pack_delta_proof raises ValueError on wrong hash length."""
        with pytest.raises(ValueError, match="32 bytes"):
            pack_delta_proof(b"\x00" * 16, b"delta")

    def test_pack_delta_proof_correct(self):
        """pack_delta_proof with 32-byte hash succeeds."""
        data = pack_delta_proof(b"\x00" * 32, b"delta")
        assert data[:32] == b"\x00" * 32
        assert data[32:] == b"delta"

    def test_pack_state_pair(self):
        """pack_state_pair produces parsable bytes."""
        data = pack_state_pair(b"state_a", b"state_b")
        len_a = struct.unpack("!I", data[:4])[0]
        assert data[4:4 + len_a] == b"state_a"

    def test_pack_merkle_path(self):
        """pack_merkle_path serializes and is non-empty."""
        path = [(["hash1", "hash2"], 1)]
        data = pack_merkle_path(path)
        assert len(data) > 0
        n_segs = struct.unpack("!H", data[:2])[0]
        assert n_segs == 1


# ---------------------------------------------------------------------------
# EVIDENCE_TYPES mapping
# ---------------------------------------------------------------------------

class TestEvidenceTypes:

    def test_five_types(self):
        """EVIDENCE_TYPES contains exactly 5 entries."""
        assert len(EVIDENCE_TYPES) == 5

    def test_keys(self):
        """All expected evidence types are present."""
        expected = {"equivocation", "merkle_divergence", "clock_regression",
                    "invalid_delta", "trust_manipulation"}
        assert set(EVIDENCE_TYPES.keys()) == expected
