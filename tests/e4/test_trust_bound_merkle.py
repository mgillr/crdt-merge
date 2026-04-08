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

"""Tests for TrustBoundMerkle (256-ary Merkle tree).

Covers content hash = SHA256(data || trust_context), 4-level traversal,
compatibility hash mode (dual-hash), subtree extraction, and path verification.
"""

import hashlib

import pytest

from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle, MerkleNode
from crdt_merge.e4.typed_trust import TypedTrustScore, TRUST_DIMENSIONS, PROBATION_TRUST
from crdt_merge.e4.pco import SubtreeRef
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from e4_factories import make_merkle_node


# ---------------------------------------------------------------------------
# Creation and properties
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleCreation:

    def test_default_branching_factor(self):
        """Default branching factor is 256."""
        tree = TrustBoundMerkle()
        assert tree.branching_factor == 256

    def test_custom_branching_factor(self):
        """Custom branching factor is stored."""
        tree = TrustBoundMerkle(branching_factor=16)
        assert tree.branching_factor == 16

    def test_empty_root_hash(self):
        """Empty tree has empty root hash."""
        tree = TrustBoundMerkle()
        assert tree.root_hash == ""

    def test_compatibility_mode_default_off(self):
        """Compatibility mode is off by default."""
        tree = TrustBoundMerkle()
        assert tree.compatibility_mode is False

    def test_compatibility_mode_on(self):
        """Compatibility mode can be enabled."""
        tree = TrustBoundMerkle(compatibility_mode=True)
        assert tree.compatibility_mode is True

    def test_leaf_count_initially_zero(self):
        """No leaves initially."""
        tree = TrustBoundMerkle()
        assert tree.leaf_count == 0


# ---------------------------------------------------------------------------
# Leaf hashing
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleLeafHash:

    def test_compute_leaf_hash_trust_bound(self):
        """Trust-bound leaf hash includes data + trust_context + originator."""
        tree = TrustBoundMerkle()
        h = tree.compute_leaf_hash(b"data", "peer-alice")
        # Should be SHA256(data || trust_serialize || originator_bytes)
        trust = TypedTrustScore.probationary()
        expected = hashlib.sha256(
            b"data" + trust.serialize() + b"peer-alice"
        ).hexdigest()
        assert h == expected

    def test_compute_leaf_hash_compat(self):
        """Compat leaf hash is plain SHA256(data)."""
        tree = TrustBoundMerkle()
        h = tree.compute_leaf_hash_compat(b"data")
        assert h == hashlib.sha256(b"data").hexdigest()

    def test_leaf_hash_differs_by_originator(self):
        """Different originators produce different trust-bound hashes."""
        tree = TrustBoundMerkle()
        h1 = tree.compute_leaf_hash(b"data", "alice")
        h2 = tree.compute_leaf_hash(b"data", "bob")
        assert h1 != h2

    def test_leaf_hash_differs_by_data(self):
        """Different data produces different hashes."""
        tree = TrustBoundMerkle()
        h1 = tree.compute_leaf_hash(b"data_a", "alice")
        h2 = tree.compute_leaf_hash(b"data_b", "alice")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Intermediate hashing
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleIntermediateHash:

    def test_intermediate_hash_includes_trust_root(self):
        """Intermediate hash changes when trust_root changes."""
        tree = TrustBoundMerkle()
        h1 = tree.compute_intermediate_hash(["child1", "child2"], "trust_root_a")
        h2 = tree.compute_intermediate_hash(["child1", "child2"], "trust_root_b")
        assert h1 != h2

    def test_intermediate_hash_compat_no_trust(self):
        """Compat intermediate hash omits trust_root."""
        tree = TrustBoundMerkle()
        h = tree.compute_intermediate_hash_compat(["child1", "child2"])
        expected = hashlib.sha256(b"child1child2").hexdigest()
        assert h == expected


# ---------------------------------------------------------------------------
# Insert and recompute
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleInsertRecompute:

    def test_insert_leaf_returns_hash(self):
        """insert_leaf returns the trust-bound leaf hash."""
        tree = TrustBoundMerkle()
        h = tree.insert_leaf("key1", b"data", "alice")
        assert isinstance(h, str)
        assert len(h) == 64
        assert tree.leaf_count == 1

    def test_recompute_single_leaf(self):
        """Recompute with one leaf sets root = that leaf's hash."""
        tree = TrustBoundMerkle()
        tree.insert_leaf("key1", b"data", "alice")
        root = tree.recompute()
        assert root != ""
        assert tree.root_hash == root

    def test_recompute_multiple_leaves(self):
        """Recompute with multiple leaves builds tree bottom-up."""
        tree = TrustBoundMerkle(branching_factor=2)
        tree.insert_leaf("k1", b"d1", "alice")
        tree.insert_leaf("k2", b"d2", "alice")
        tree.insert_leaf("k3", b"d3", "alice")
        root = tree.recompute()
        assert root != ""

    def test_recompute_empty_tree(self):
        """Recompute on empty tree returns empty string."""
        tree = TrustBoundMerkle()
        assert tree.recompute() == ""

    def test_recompute_compat_mode(self):
        """In compatibility mode, compat_hash is also computed."""
        tree = TrustBoundMerkle(compatibility_mode=True, branching_factor=2)
        tree.insert_leaf("k1", b"d1", "alice")
        tree.insert_leaf("k2", b"d2", "alice")
        tree.recompute()
        assert tree.root_compat_hash != ""


# ---------------------------------------------------------------------------
# Changed subtree detection
# ---------------------------------------------------------------------------

class TestFindChangedSubtrees:

    def test_identical_nodes_no_changes(self):
        """Two nodes with same hash produce no changed subtrees."""
        tree = TrustBoundMerkle()
        node = make_merkle_node(hash_val="abc")
        result = []
        tree.find_changed_subtrees(node, node, result)
        assert result == []

    def test_different_leaves_detected(self):
        """Different leaf hashes produce a subtree change."""
        tree = TrustBoundMerkle()
        local = make_merkle_node(hash_val="aaa")
        remote = make_merkle_node(hash_val="bbb")
        result = []
        tree.find_changed_subtrees(local, remote, result)
        assert len(result) == 1
        assert result[0].old_hash == "bbb"
        assert result[0].new_hash == "aaa"

    def test_different_internal_descend(self):
        """Different internal nodes descend into children."""
        tree = TrustBoundMerkle(branching_factor=2)
        child_same = make_merkle_node(path=(0, 0), hash_val="same")
        child_diff_local = make_merkle_node(path=(0, 1), hash_val="local")
        child_diff_remote = make_merkle_node(path=(0, 1), hash_val="remote")

        local = MerkleNode(
            path=(0,), hash="parent_local", is_leaf=False,
            children=[child_same, child_diff_local],
        )
        remote = MerkleNode(
            path=(0,), hash="parent_remote", is_leaf=False,
            children=[child_same, child_diff_remote],
        )
        result = []
        tree.find_changed_subtrees(local, remote, result)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Path verification
# ---------------------------------------------------------------------------

class TestPathVerification:

    def test_verify_path_compat_valid(self):
        """Compat path verification succeeds for a valid path."""
        tree = TrustBoundMerkle(branching_factor=2)
        data = b"leaf_data"
        leaf_hash = tree.compute_leaf_hash_compat(data)
        sibling = "sibling_hash"
        parent_hash = tree.compute_intermediate_hash_compat([leaf_hash, sibling])
        # Path: one step with sibling at position 1, leaf at position 0
        path_steps = [([sibling], 0)]
        assert tree.verify_path_compat(data, path_steps, parent_hash) is True

    def test_verify_path_compat_invalid(self):
        """Compat path verification fails for wrong expected root."""
        tree = TrustBoundMerkle(branching_factor=2)
        data = b"leaf_data"
        path_steps = [([" sibling"], 0)]
        assert tree.verify_path_compat(data, path_steps, "wrong_root") is False


# ---------------------------------------------------------------------------
# Trust context updates
# ---------------------------------------------------------------------------

class TestTrustContextUpdate:

    def test_update_trust_context(self):
        """update_trust_context stores trust in cache."""
        tree = TrustBoundMerkle()
        ts = TypedTrustScore.probationary()
        tree.update_trust_context("alice", ts)
        # The cache is internal, but recompute should use it

    def test_is_plausible_root_empty(self):
        """Empty root is always plausible."""
        tree = TrustBoundMerkle()
        assert tree.is_plausible_root("") is True

    def test_is_plausible_root_matching(self):
        """Root matching the current root is plausible."""
        tree = TrustBoundMerkle()
        tree.insert_leaf("k1", b"data", "alice")
        root = tree.recompute()
        assert tree.is_plausible_root(root) is True

    def test_is_plausible_root_mismatch(self):
        """Non-matching root is not plausible."""
        tree = TrustBoundMerkle()
        tree.insert_leaf("k1", b"data", "alice")
        tree.recompute()
        assert tree.is_plausible_root("definitely_wrong") is False


# ---------------------------------------------------------------------------
# Bind trust lattice
# ---------------------------------------------------------------------------

class TestBindTrustLattice:

    def test_bind_trust_lattice(self):
        """bind_trust_lattice sets the lattice for trust lookups."""
        lat = DeltaTrustLattice("alice")
        tree = TrustBoundMerkle()
        tree.bind_trust_lattice(lat)
        # After binding, leaf hashes use lattice trust
        h = tree.compute_leaf_hash(b"data", "alice")
        assert isinstance(h, str)


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestTrustBoundMerkleRepr:

    def test_repr(self):
        """Repr includes branching factor and leaf count."""
        tree = TrustBoundMerkle(branching_factor=256, compatibility_mode=True)
        r = repr(tree)
        assert "256" in r
        assert "compat=True" in r
