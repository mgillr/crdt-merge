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

"""Tests for AggregateProofCarryingOperation and SubtreeRef.

Covers creation from 4 components, single-verify aggregate,
wire format (128 bytes), invalid aggregates, and partial verification.
"""

import hashlib
import struct

import pytest

from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    SubtreeRef,
    _compute_aggregate_hash,
    _build_metadata,
)
from crdt_merge.e4.typed_trust import TypedTrustScore, QUARANTINE_THRESHOLD


# ---------------------------------------------------------------------------
# SubtreeRef
# ---------------------------------------------------------------------------

class TestSubtreeRef:

    def test_creation(self):
        """SubtreeRef stores path, depth, old_hash, new_hash."""
        sr = SubtreeRef(path=(0, 1), depth=2, old_hash="aaa", new_hash="bbb")
        assert sr.path == (0, 1)
        assert sr.depth == 2

    def test_frozen(self):
        """SubtreeRef is a frozen dataclass."""
        sr = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")
        with pytest.raises(AttributeError):
            sr.depth = 5

    def test_equality(self):
        """SubtreeRefs with same fields compare equal."""
        sr1 = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")
        sr2 = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")
        assert sr1 == sr2

    def test_inequality_different_hash(self):
        """SubtreeRefs with different new_hash are not equal."""
        sr1 = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")
        sr2 = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="c")
        assert sr1 != sr2


# ---------------------------------------------------------------------------
# AggregateProofCarryingOperation build
# ---------------------------------------------------------------------------

class TestAggregatePCOBuild:

    def test_build_basic(self):
        """build() creates a PCO with all fields populated."""
        bounds = [SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")]
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-alice",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="root_hash",
            clock_snapshot=b"clock_bytes",
            trust_vector_hash="tvh",
            delta_bounds=bounds,
        )
        assert pco.originator_id == "peer-alice"
        assert len(pco.signature) == 64
        assert len(pco.aggregate_hash) == 32
        assert len(pco.metadata) == 32

    def test_build_with_signing_fn(self):
        """Custom signing function is invoked with aggregate hash."""
        captured = {}
        def my_sign(h):
            captured["hash"] = h
            return b"\xAA" * 64
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-bob",
            signing_fn=my_sign,
            merkle_root="mr",
            clock_snapshot=b"cs",
            trust_vector_hash="tvh",
            delta_bounds=[],
        )
        assert captured["hash"] == pco.aggregate_hash
        assert pco.signature == b"\xAA" * 64

    def test_build_bad_signature_length_raises(self):
        """Signing function returning wrong length raises ValueError."""
        with pytest.raises(ValueError, match="64 bytes"):
            AggregateProofCarryingOperation.build(
                originator_id="peer",
                signing_fn=lambda h: b"\x00" * 32,
                merkle_root="", clock_snapshot=b"",
                trust_vector_hash="", delta_bounds=[],
            )

    def test_build_none_signing_fn_uses_zeros(self):
        """None signing_fn falls back to 64 zero bytes."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer",
            signing_fn=None,
            merkle_root="", clock_snapshot=b"",
            trust_vector_hash="", delta_bounds=[],
        )
        assert pco.signature == b"\x00" * 64

    def test_aggregate_hash_deterministic(self):
        """Same inputs produce same aggregate hash."""
        kwargs = dict(
            originator_id="peer",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="root", clock_snapshot=b"clock",
            trust_vector_hash="tvh",
            delta_bounds=[SubtreeRef((0,), 1, "a", "b")],
        )
        pco1 = AggregateProofCarryingOperation.build(**kwargs)
        pco2 = AggregateProofCarryingOperation.build(**kwargs)
        assert pco1.aggregate_hash == pco2.aggregate_hash


# ---------------------------------------------------------------------------
# Wire format (128 bytes)
# ---------------------------------------------------------------------------

class TestAggregatePCOWireFormat:

    def test_to_wire_length(self):
        """to_wire() produces exactly 128 bytes."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"",
            trust_vector_hash="", delta_bounds=[],
        )
        wire = pco.to_wire()
        assert len(wire) == 128

    def test_to_wire_layout(self):
        """Wire layout: 64B sig + 32B hash + 32B metadata."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer",
            signing_fn=lambda h: b"\xFF" * 64,
            merkle_root="", clock_snapshot=b"",
            trust_vector_hash="", delta_bounds=[],
        )
        wire = pco.to_wire()
        assert wire[:64] == b"\xFF" * 64
        assert wire[64:96] == pco.aggregate_hash

    def test_from_wire_roundtrip(self):
        """from_wire can reconstruct a PCO from wire bytes."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-alice",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="mr", clock_snapshot=b"cs",
            trust_vector_hash="tvh", delta_bounds=[],
        )
        wire = pco.to_wire()
        restored = AggregateProofCarryingOperation.from_wire(
            wire,
            originator_id="peer-alice",
            merkle_root="mr",
            clock_snapshot=b"cs",
            trust_vector_hash="tvh",
        )
        assert restored.signature == pco.signature
        assert restored.aggregate_hash == pco.aggregate_hash

    def test_from_wire_too_short_raises(self):
        """from_wire with < 128 bytes raises ValueError."""
        with pytest.raises(ValueError, match="128 bytes"):
            AggregateProofCarryingOperation.from_wire(b"\x00" * 64, "peer")


# ---------------------------------------------------------------------------
# Verification levels
# ---------------------------------------------------------------------------

class TestAggregatePCOVerification:

    def _make_verified_pco(self, bounds=None):
        bounds = bounds or []
        return AggregateProofCarryingOperation.build(
            originator_id="peer-alice",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="",
            clock_snapshot=b"",
            trust_vector_hash="",
            delta_bounds=bounds,
        )

    def test_level_3_always_rejects(self):
        """Level 3 verification always returns False."""
        pco = self._make_verified_pco()
        assert pco.verify(None, None, verification_level=3) is False

    def test_level_0_signature_only(self):
        """Level 0 accepts when signature is valid."""
        pco = self._make_verified_pco()
        assert pco.verify(None, None, verification_level=0) is True

    def test_level_1_signature_plus_integrity(self):
        """Level 1 checks signature + Merkle root plausibility."""
        pco = self._make_verified_pco()
        assert pco.verify(object(), None, verification_level=1) is True

    def test_level_2_full_verification(self):
        """Level 2 checks all four properties."""
        bounds = [SubtreeRef((0,), 1, "old", "new")]
        pco = self._make_verified_pco(bounds)
        assert pco.verify(object(), object(), verification_level=2) is True

    def test_bad_aggregate_hash_rejects(self):
        """Mismatched aggregate hash causes signature rejection."""
        pco = self._make_verified_pco()
        bad_pco = AggregateProofCarryingOperation(
            aggregate_hash=b"\xFF" * 32,
            signature=pco.signature,
            originator_id=pco.originator_id,
            metadata=pco.metadata,
            merkle_root_at_creation=pco.merkle_root_at_creation,
            clock_snapshot=pco.clock_snapshot,
            trust_vector_hash=pco.trust_vector_hash,
            delta_bounds=pco.delta_bounds,
        )
        assert bad_pco.verify(None, None, verification_level=0) is False

    def test_minimality_fails_same_hashes(self):
        """Minimality check fails when old_hash == new_hash."""
        bounds = [SubtreeRef((0,), 1, "same", "same")]
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"",
            trust_vector_hash="", delta_bounds=bounds,
        )
        assert pco.verify(object(), object(), verification_level=2) is False


# ---------------------------------------------------------------------------
# Aggregate hash computation
# ---------------------------------------------------------------------------

class TestAggregateHash:

    def test_compute_aggregate_hash_deterministic(self):
        """Same inputs always yield the same 32-byte hash."""
        h1 = _compute_aggregate_hash("root", b"clock", "tvh", ())
        h2 = _compute_aggregate_hash("root", b"clock", "tvh", ())
        assert h1 == h2
        assert len(h1) == 32

    def test_compute_aggregate_hash_changes_on_input(self):
        """Different inputs produce different hashes."""
        h1 = _compute_aggregate_hash("root_a", b"clock", "tvh", ())
        h2 = _compute_aggregate_hash("root_b", b"clock", "tvh", ())
        assert h1 != h2


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:

    def test_build_metadata_length(self):
        """_build_metadata produces exactly 32 bytes."""
        meta = _build_metadata()
        assert len(meta) == 32

    def test_build_metadata_version(self):
        """Version field is packed into first 2 bytes."""
        meta = _build_metadata(version=42, flags=0)
        version = struct.unpack("!H", meta[:2])[0]
        assert version == 42


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestAggregatePCORepr:

    def test_repr(self):
        """PCO repr includes originator and hash prefix."""
        pco = AggregateProofCarryingOperation.build(
            originator_id="peer-x",
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="", clock_snapshot=b"",
            trust_vector_hash="", delta_bounds=[],
        )
        r = repr(pco)
        assert "peer-x" in r
        assert "AggregatePCO" in r
