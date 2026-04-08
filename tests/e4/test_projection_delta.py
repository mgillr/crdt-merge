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

"""Tests for ProjectionDelta encoder, FrozenDict, and ProjectionDeltaManager.

Covers tree diff, sparse extraction, billion-parameter scaling,
compression ratios, and edge cases (empty diff, single param, all changed).
"""

import hashlib

import pytest

from crdt_merge.e4.projection_delta import (
    FrozenDict,
    ProjectionDelta,
    ProjectionDeltaManager,
    VALID_ENCODINGS,
    _compress_sparse,
    _compress_quantized,
)
from crdt_merge.e4.pco import SubtreeRef
from e4_factories import make_delta, make_pco


# ---------------------------------------------------------------------------
# FrozenDict
# ---------------------------------------------------------------------------

class TestFrozenDict:

    def test_create_from_dict(self):
        """FrozenDict wraps a plain dict."""
        fd = FrozenDict({"a": 1, "b": 2})
        assert fd["a"] == 1
        assert len(fd) == 2

    def test_create_from_kwargs(self):
        """FrozenDict can be created via keyword args."""
        fd = FrozenDict(a=1, b=2)
        assert fd["a"] == 1

    def test_immutable(self):
        """FrozenDict raises on assignment."""
        fd = FrozenDict({"a": 1})
        with pytest.raises(TypeError):
            fd["a"] = 2

    def test_iter(self):
        """FrozenDict supports iteration."""
        fd = FrozenDict({"a": 1, "b": 2})
        assert set(fd) == {"a", "b"}

    def test_hashable(self):
        """FrozenDict is hashable."""
        fd = FrozenDict({"a": 1})
        h = hash(fd)
        assert isinstance(h, int)

    def test_hash_deterministic(self):
        """Same contents yield same hash."""
        fd1 = FrozenDict({"a": 1, "b": 2})
        fd2 = FrozenDict({"a": 1, "b": 2})
        assert hash(fd1) == hash(fd2)

    def test_equality_with_dict(self):
        """FrozenDict compares equal to an equivalent dict."""
        fd = FrozenDict({"a": 1})
        assert fd == {"a": 1}

    def test_equality_frozen_frozen(self):
        """Two FrozenDicts with same data compare equal."""
        fd1 = FrozenDict({"x": 10})
        fd2 = FrozenDict({"x": 10})
        assert fd1 == fd2

    def test_repr(self):
        """Repr is readable."""
        fd = FrozenDict({"a": 1})
        assert "FrozenDict" in repr(fd)

    def test_empty(self):
        """Empty FrozenDict has length 0."""
        fd = FrozenDict()
        assert len(fd) == 0
        assert not fd


# ---------------------------------------------------------------------------
# ProjectionDelta creation and properties
# ---------------------------------------------------------------------------

class TestProjectionDeltaCreation:

    def test_create_empty(self):
        """Empty delta has no changes."""
        d = make_delta()
        assert d.is_empty()

    def test_create_with_insertions(self):
        """Delta with insertions is not empty."""
        d = make_delta(insertions={"k": b"v"})
        assert not d.is_empty()
        assert "k" in d.insertions

    def test_create_with_updates(self):
        """Delta with updates is not empty."""
        d = make_delta(updates={"k": ("old_h", b"new_v")})
        assert not d.is_empty()

    def test_create_with_deletions(self):
        """Delta with deletions is not empty."""
        d = make_delta(deletions=["k1", "k2"])
        assert not d.is_empty()
        assert "k1" in d.deletions

    def test_frozen(self):
        """ProjectionDelta is frozen."""
        d = make_delta()
        with pytest.raises(AttributeError):
            d.source_id = "other"

    def test_source_id_preserved(self):
        """source_id is stored correctly."""
        d = make_delta(source_id="peer-bob")
        assert d.source_id == "peer-bob"


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

class TestProjectionDeltaContentHash:

    def test_deterministic(self):
        """Same delta produces same content hash."""
        d = make_delta(insertions={"k": b"v"})
        assert d.content_hash() == d.content_hash()

    def test_different_data_different_hash(self):
        """Different deltas produce different hashes."""
        d1 = make_delta(insertions={"k": b"v1"})
        d2 = make_delta(insertions={"k": b"v2"})
        assert d1.content_hash() != d2.content_hash()

    def test_hash_hex_length(self):
        """Content hash is SHA-256 hex (64 chars)."""
        d = make_delta(insertions={"k": b"v"})
        assert len(d.content_hash()) == 64


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

class TestProjectionDeltaCompose:

    def test_compose_insertions(self):
        """B's insertions override A's."""
        d1 = make_delta(insertions={"k": b"v1"})
        d2 = make_delta(insertions={"k": b"v2"})
        composed = d1.compose(d2)
        assert composed.insertions["k"] == b"v2"

    def test_compose_insert_then_delete_cancels(self):
        """Insert in A->B + delete in B->C cancels out."""
        d1 = make_delta(insertions={"k": b"val"})
        d2 = make_delta(deletions=["k"])
        composed = d1.compose(d2)
        assert "k" not in composed.insertions
        # k remains in deletions since it's the net result
        assert "k" in composed.deletions

    def test_compose_delete_then_insert_insert_wins(self):
        """Delete in A->B + insert in B->C -> insertion wins."""
        d1 = make_delta(deletions=["k"])
        d2 = make_delta(insertions={"k": b"new"})
        composed = d1.compose(d2)
        assert "k" in composed.insertions
        assert "k" not in composed.deletions

    def test_compose_update_chain(self):
        """Chained updates keep A's old_hash and C's new_value."""
        d1 = make_delta(updates={"k": ("hash_a", b"val_b")})
        d2 = make_delta(updates={"k": ("hash_b", b"val_c")})
        composed = d1.compose(d2)
        old_h, new_v = composed.updates["k"]
        assert old_h == "hash_a"
        assert new_v == b"val_c"

    def test_compose_subtrees_merged(self):
        """Subtree refs from both deltas are merged by path."""
        s1 = SubtreeRef(path=(0,), depth=1, old_hash="a", new_hash="b")
        s2 = SubtreeRef(path=(0,), depth=1, old_hash="b", new_hash="c")
        d1 = make_delta(subtrees=[s1])
        d2 = make_delta(subtrees=[s2])
        composed = d1.compose(d2)
        assert len(composed.changed_subtrees) == 1
        ref = composed.changed_subtrees[0]
        assert ref.old_hash == "a"
        assert ref.new_hash == "c"

    def test_compose_preserves_target_version(self):
        """Composed delta uses other's target_version."""
        d1 = make_delta()
        d2 = make_delta()
        composed = d1.compose(d2)
        assert composed.target_version == d2.target_version

    def test_compose_uses_other_pco(self):
        """Composed delta uses the more recent (other's) PCO."""
        pco1 = make_pco(originator_id="alice")
        pco2 = make_pco(originator_id="bob")
        d1 = make_delta(pco=pco1)
        d2 = make_delta(pco=pco2)
        composed = d1.compose(d2)
        assert composed.pco.originator_id == "bob"


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------

class TestProjectionDeltaCompression:

    def test_compress_raw_identity(self):
        """Raw encoding is identity (ratio 1.0)."""
        d = make_delta(insertions={"k": b"v"})
        c = d.compress("raw")
        assert c.encoding == "raw"
        assert c.compression_ratio == 1.0

    def test_compress_sparse_strips_zero_diff(self):
        """Sparse encoding strips updates where old_hash == sha256(new_value)."""
        new_val = b"some_value"
        old_hash = hashlib.sha256(new_val).hexdigest()
        d = make_delta(updates={"k": (old_hash, new_val)})
        c = d.compress("sparse")
        assert "k" not in c.updates
        assert c.encoding == "sparse"

    def test_compress_sparse_keeps_real_changes(self):
        """Sparse encoding keeps updates with actual differences."""
        d = make_delta(updates={"k": ("wrong_hash", b"new_value")})
        c = d.compress("sparse")
        assert "k" in c.updates

    def test_compress_quantized(self):
        """Quantized encoding reduces value precision."""
        d = make_delta(insertions={"k": b"\xff\xfe\xfd"})
        c = d.compress("quantized", bits=4)
        assert c.encoding == "quantized"
        # each byte masked to 4 bits
        for b_val in c.insertions["k"]:
            assert b_val <= 0x0F

    def test_compress_invalid_encoding_raises(self):
        """Unknown encoding raises ValueError."""
        d = make_delta()
        with pytest.raises(ValueError, match="unknown encoding"):
            d.compress("lzma")

    def test_valid_encodings_constant(self):
        """VALID_ENCODINGS contains expected values."""
        assert "raw" in VALID_ENCODINGS
        assert "sparse" in VALID_ENCODINGS
        assert "quantized" in VALID_ENCODINGS


# ---------------------------------------------------------------------------
# with_pco
# ---------------------------------------------------------------------------

class TestProjectionDeltaWithPCO:

    def test_with_pco_replaces(self):
        """with_pco returns a new delta with replaced PCO."""
        d = make_delta()
        new_pco = make_pco(originator_id="peer-bob")
        d2 = d.with_pco(new_pco)
        assert d2.pco.originator_id == "peer-bob"
        assert d.pco.originator_id != "peer-bob"


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestProjectionDeltaRepr:

    def test_repr_includes_source(self):
        """Repr includes source_id."""
        d = make_delta(source_id="peer-alice")
        assert "peer-alice" in repr(d)

    def test_repr_includes_change_count(self):
        """Repr includes change count."""
        d = make_delta(insertions={"a": b"1", "b": b"2"})
        assert "changes=2" in repr(d)


# ---------------------------------------------------------------------------
# ProjectionDeltaManager
# ---------------------------------------------------------------------------

class TestProjectionDeltaManager:

    def test_record_and_latest(self):
        """record() stores delta; latest() retrieves it."""
        mgr = ProjectionDeltaManager()
        d = make_delta(source_id="alice")
        mgr.record(d)
        assert mgr.latest("alice") is d

    def test_latest_unknown_peer_none(self):
        """latest() returns None for unknown peer."""
        mgr = ProjectionDeltaManager()
        assert mgr.latest("unknown") is None

    def test_compose_range(self):
        """compose_range composes contiguous deltas."""
        mgr = ProjectionDeltaManager()
        d1 = make_delta(source_id="alice", insertions={"k1": b"v1"})
        d2 = make_delta(source_id="alice", insertions={"k2": b"v2"})
        mgr.record(d1)
        mgr.record(d2)
        composed = mgr.compose_range("alice")
        assert "k1" in composed.insertions
        assert "k2" in composed.insertions

    def test_compose_range_empty(self):
        """compose_range returns None for unknown peer."""
        mgr = ProjectionDeltaManager()
        assert mgr.compose_range("unknown") is None

    def test_max_history_enforced(self):
        """History is trimmed to max_history."""
        mgr = ProjectionDeltaManager(max_history=3)
        for i in range(10):
            mgr.record(make_delta(source_id="alice", insertions={f"k{i}": b"v"}))
        # Only last 3 should remain
        composed = mgr.compose_range("alice")
        assert len(composed.insertions) <= 3

    def test_clear_peer(self):
        """clear(peer_id) removes history for that peer."""
        mgr = ProjectionDeltaManager()
        mgr.record(make_delta(source_id="alice"))
        mgr.clear("alice")
        assert mgr.latest("alice") is None

    def test_clear_all(self):
        """clear() removes all history."""
        mgr = ProjectionDeltaManager()
        mgr.record(make_delta(source_id="alice"))
        mgr.record(make_delta(source_id="bob"))
        mgr.clear()
        assert mgr.peers() == []

    def test_peers(self):
        """peers() lists all tracked peer IDs."""
        mgr = ProjectionDeltaManager()
        mgr.record(make_delta(source_id="alice"))
        mgr.record(make_delta(source_id="bob"))
        assert set(mgr.peers()) == {"alice", "bob"}


# ---------------------------------------------------------------------------
# Edge cases: billion-parameter scaling simulation
# ---------------------------------------------------------------------------

class TestProjectionDeltaScaling:

    def test_many_insertions(self):
        """Delta with 1000 insertions is correctly constructed."""
        ins = {f"param_{i}": f"val_{i}".encode() for i in range(1000)}
        d = make_delta(insertions=ins)
        assert len(d.insertions) == 1000
        assert not d.is_empty()

    def test_many_subtrees(self):
        """Delta with many subtree refs is correctly stored."""
        refs = [SubtreeRef(path=(i,), depth=1, old_hash=f"o{i}", new_hash=f"n{i}")
                for i in range(100)]
        d = make_delta(subtrees=refs)
        assert len(d.changed_subtrees) == 100

    def test_all_changed_single_compose(self):
        """Composing 'all changed' deltas works."""
        d1 = make_delta(insertions={f"k{i}": b"a" for i in range(50)})
        d2 = make_delta(updates={f"k{i}": ("h", b"b") for i in range(50)})
        composed = d1.compose(d2)
        # All keys that were inserted then updated become insertions with new value
        for i in range(50):
            assert composed.insertions[f"k{i}"] == b"b"
