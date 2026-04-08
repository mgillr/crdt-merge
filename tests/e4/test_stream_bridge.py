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

"""Tests for TrustStreamMerge, StreamChunk, and ChunkResult.

Covers streaming merge with trust, windowed verification, stream acceptance,
per-chunk validation, and early-stop on failure.
"""

import pytest

from crdt_merge.e4.integration.stream_bridge import (
    TrustStreamMerge,
    StreamChunk,
    ChunkResult,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
)
from crdt_merge.e4.typed_trust import TypedTrustScore
from e4_factories import make_delta


# ---------------------------------------------------------------------------
# StreamChunk and ChunkResult
# ---------------------------------------------------------------------------

class TestStreamChunk:

    def test_creation(self):
        """StreamChunk stores delta, sequence, and stream_id."""
        delta = make_delta()
        chunk = StreamChunk(delta=delta, sequence=0, stream_id="s1")
        assert chunk.sequence == 0
        assert chunk.stream_id == "s1"

    def test_default_stream_id(self):
        """Default stream_id is empty string."""
        delta = make_delta()
        chunk = StreamChunk(delta=delta, sequence=5)
        assert chunk.stream_id == ""


class TestChunkResult:

    def test_accepted_result(self):
        """ChunkResult accepted=True."""
        cr = ChunkResult(accepted=True, sequence=0)
        assert cr.accepted is True
        assert cr.sequence == 0

    def test_rejected_result(self):
        """ChunkResult accepted=False with reason."""
        cr = ChunkResult(accepted=False, sequence=1, reason="bad PCO")
        assert cr.accepted is False
        assert cr.reason == "bad PCO"

    def test_frozen(self):
        """ChunkResult is frozen."""
        cr = ChunkResult(accepted=True, sequence=0)
        with pytest.raises(AttributeError):
            cr.accepted = False


# ---------------------------------------------------------------------------
# TrustStreamMerge creation
# ---------------------------------------------------------------------------

class TestTrustStreamMergeCreation:

    def test_create_no_deps(self):
        """Can create TrustStreamMerge with no dependencies."""
        tsm = TrustStreamMerge()
        assert tsm.active_stream_ids() == []

    def test_create_with_min_trust(self):
        """Custom min_trust is stored."""
        tsm = TrustStreamMerge(min_trust=0.3)
        assert tsm._min_trust == 0.3

    def test_bind_verifier(self):
        """bind_verifier sets the verifier."""
        tsm = TrustStreamMerge()
        verifier = AdaptiveVerificationController()
        tsm.bind_verifier(verifier)

    def test_bind_state(self):
        """bind_state sets application state."""
        tsm = TrustStreamMerge()
        tsm.bind_state({"state": True})


# ---------------------------------------------------------------------------
# accept_stream gate
# ---------------------------------------------------------------------------

class TestAcceptStream:

    def test_accept_stream_no_lattice(self):
        """Without lattice's get_trust, stream is accepted."""
        tsm = TrustStreamMerge()
        # Pass an object without get_trust
        assert tsm.accept_stream("peer", "s1", object()) is True

    def test_accept_stream_high_trust(self):
        """Peer with trust > min_trust is accepted."""
        lattice = DeltaTrustLattice("local", initial_peers={"alice"})
        tsm = TrustStreamMerge(min_trust=0.1)
        result = tsm.accept_stream("alice", "s1", lattice)
        assert result is True
        assert "s1" in tsm.active_stream_ids()

    def test_reject_stream_low_trust(self):
        """Peer below min_trust is rejected."""
        lattice = DeltaTrustLattice("local", initial_peers={"evil"})
        # Drive trust down by adding evidence directly
        old_score = lattice.get_trust("evil")
        new_ev = {dim: {"obs": 0.95} for dim in ["integrity", "causality", "consistency",
                                                    "gossip", "model", "context"]}
        lattice._trust_scores["evil"] = TypedTrustScore(_evidence=new_ev)

        tsm = TrustStreamMerge(min_trust=0.5)
        result = tsm.accept_stream("evil", "s_evil", lattice)
        assert result is False


# ---------------------------------------------------------------------------
# validate_chunk
# ---------------------------------------------------------------------------

class TestValidateChunk:

    def test_no_verifier_accepts(self):
        """Without verifier, all chunks are accepted."""
        tsm = TrustStreamMerge()
        delta = make_delta()
        chunk = StreamChunk(delta=delta, sequence=0, stream_id="s1")
        cr = tsm.validate_chunk(chunk)
        assert cr.accepted is True
        assert cr.sequence == 0

    def test_chunk_recorded_in_stream_results(self):
        """Validated chunk appears in stream_results."""
        tsm = TrustStreamMerge()
        delta = make_delta()
        chunk = StreamChunk(delta=delta, sequence=0, stream_id="s1")
        tsm.validate_chunk(chunk)
        results = tsm.stream_results("s1")
        assert len(results) == 1
        assert results[0].accepted is True

    def test_multiple_chunks_accumulated(self):
        """Multiple chunks for same stream_id accumulate results."""
        tsm = TrustStreamMerge()
        for i in range(5):
            chunk = StreamChunk(delta=make_delta(), sequence=i, stream_id="s1")
            tsm.validate_chunk(chunk)
        assert len(tsm.stream_results("s1")) == 5


# ---------------------------------------------------------------------------
# validate_stream
# ---------------------------------------------------------------------------

class TestValidateStream:

    def test_validate_stream_all_accepted(self):
        """All chunks in a stream pass -> all accepted."""
        tsm = TrustStreamMerge()
        chunks = [
            StreamChunk(delta=make_delta(), sequence=i, stream_id="s2")
            for i in range(3)
        ]
        results = tsm.validate_stream(chunks)
        assert len(results) == 3
        assert all(r.accepted for r in results)

    def test_validate_stream_empty(self):
        """Empty stream produces empty results."""
        tsm = TrustStreamMerge()
        results = tsm.validate_stream([])
        assert results == []


# ---------------------------------------------------------------------------
# close_stream
# ---------------------------------------------------------------------------

class TestCloseStream:

    def test_close_removes_stream(self):
        """close_stream removes the stream from active list."""
        tsm = TrustStreamMerge()
        chunk = StreamChunk(delta=make_delta(), sequence=0, stream_id="s1")
        tsm.validate_chunk(chunk)
        assert "s1" in tsm.active_stream_ids()
        tsm.close_stream("s1")
        assert "s1" not in tsm.active_stream_ids()

    def test_close_nonexistent_is_noop(self):
        """Closing a non-existent stream is a no-op."""
        tsm = TrustStreamMerge()
        tsm.close_stream("nonexistent")  # Should not raise


# ---------------------------------------------------------------------------
# stream_results for unknown stream
# ---------------------------------------------------------------------------

class TestStreamIntrospection:

    def test_stream_results_unknown(self):
        """stream_results for unknown stream returns empty list."""
        tsm = TrustStreamMerge()
        assert tsm.stream_results("unknown") == []

    def test_active_stream_ids(self):
        """active_stream_ids lists all streams with results."""
        tsm = TrustStreamMerge()
        for sid in ["s1", "s2", "s3"]:
            chunk = StreamChunk(delta=make_delta(), sequence=0, stream_id=sid)
            tsm.validate_chunk(chunk)
        ids = tsm.active_stream_ids()
        assert set(ids) == {"s1", "s2", "s3"}
