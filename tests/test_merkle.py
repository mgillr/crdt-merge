# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.merkle — Merkle tree construction, diff, and CRDT merge."""

from __future__ import annotations

import random

import pytest

from crdt_merge.merkle import MerkleDiff, MerkleNode, MerkleTree, merkle_diff
from crdt_merge.verify import (
    verify_associative,
    verify_commutative,
    verify_convergence,
    verify_idempotent,
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_records(n: int, prefix: str = "k", seed: int | None = None) -> list[dict]:
    """Generate *n* test records with deterministic ids."""
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()
    return [{"id": f"{prefix}{i}", "value": rng.randint(0, 1000)} for i in range(n)]


def _eq_merkle(a: MerkleTree, b: MerkleTree) -> bool:
    """Equality based on root hash — the canonical CRDT equality for MerkleTree."""
    return a.root_hash == b.root_hash


def gen_merkle_tree() -> MerkleTree:
    """Generator for property-based CRDT verification tests."""
    n = random.randint(1, 50)
    records = [{"id": f"k{i}", "value": random.randint(0, 100)} for i in range(n)]
    return MerkleTree.from_records(records, key="id")


# ─── 1. MerkleTree creation ────────────────────────────────────────────────

class TestMerkleTreeCreation:
    def test_empty_tree(self):
        tree = MerkleTree()
        assert tree.size == 0
        assert tree.root_hash  # non-empty hash string
        assert tree.root is None

    def test_from_records_basic(self):
        records = _make_records(10, seed=42)
        tree = MerkleTree.from_records(records, key="id")
        assert tree.size == 10
        assert tree.root is not None
        assert len(tree.root_hash) == 64  # SHA-256 hex = 64 chars

    def test_from_records_branching_factor(self):
        records = _make_records(20, seed=7)
        t4 = MerkleTree.from_records(records, key="id", branching_factor=4)
        t16 = MerkleTree.from_records(records, key="id", branching_factor=16)
        # Same data → same root hash regardless of branching factor?
        # Actually no: branching factor affects tree structure & internal hashes.
        # But both trees should have the same size.
        assert t4.size == t16.size == 20
        assert t4.height >= t16.height  # smaller BF → taller tree


# ─── 2. MerkleTree.root_hash ───────────────────────────────────────────────

class TestRootHash:
    def test_deterministic(self):
        records = _make_records(15, seed=99)
        t1 = MerkleTree.from_records(records, key="id")
        t2 = MerkleTree.from_records(records, key="id")
        assert t1.root_hash == t2.root_hash

    def test_different_data_different_hash(self):
        r1 = [{"id": "a", "value": 1}]
        r2 = [{"id": "a", "value": 2}]
        t1 = MerkleTree.from_records(r1, key="id")
        t2 = MerkleTree.from_records(r2, key="id")
        assert t1.root_hash != t2.root_hash

    def test_empty_tree_hash(self):
        t1 = MerkleTree()
        t2 = MerkleTree(branching_factor=4)
        # Both empty → same hash
        assert t1.root_hash == t2.root_hash


# ─── 3. MerkleTree.insert ──────────────────────────────────────────────────

class TestInsert:
    def test_insert_new_record(self):
        tree = MerkleTree()
        tree.insert("k0", {"id": "k0", "value": 42})
        assert tree.size == 1
        assert tree.contains("k0")

    def test_update_existing_record(self):
        tree = MerkleTree.from_records([{"id": "k0", "value": 1}], key="id")
        old_hash = tree.root_hash
        tree.insert("k0", {"id": "k0", "value": 999})
        assert tree.size == 1  # still one record
        assert tree.root_hash != old_hash

    def test_hash_changes_after_insert(self):
        tree = MerkleTree.from_records(_make_records(5, seed=1), key="id")
        h_before = tree.root_hash
        tree.insert("new_key", {"id": "new_key", "value": 0})
        assert tree.root_hash != h_before
        assert tree.size == 6


# ─── 4. MerkleTree.delete ──────────────────────────────────────────────────

class TestDelete:
    def test_delete_existing(self):
        tree = MerkleTree.from_records(_make_records(5, seed=3), key="id")
        assert tree.delete("k0") is True
        assert tree.size == 4
        assert not tree.contains("k0")

    def test_delete_missing(self):
        tree = MerkleTree.from_records(_make_records(3, seed=4), key="id")
        assert tree.delete("nonexistent") is False
        assert tree.size == 3


# ─── 5. MerkleTree.contains / get_hash ─────────────────────────────────────

class TestContainsGetHash:
    def test_present_key(self):
        tree = MerkleTree.from_records([{"id": "x", "value": 10}], key="id")
        assert tree.contains("x")
        h = tree.get_hash("x")
        assert h is not None and len(h) == 64

    def test_missing_key(self):
        tree = MerkleTree.from_records([{"id": "x", "value": 10}], key="id")
        assert not tree.contains("y")
        assert tree.get_hash("y") is None


# ─── 6. MerkleTree.merge ───────────────────────────────────────────────────

class TestMerge:
    def test_disjoint_records(self):
        a = MerkleTree.from_records([{"id": "a1", "v": 1}], key="id")
        b = MerkleTree.from_records([{"id": "b1", "v": 2}], key="id")
        merged = a.merge(b)
        assert merged.size == 2
        assert merged.contains("a1")
        assert merged.contains("b1")

    def test_overlapping_higher_hash_wins(self):
        a = MerkleTree.from_records([{"id": "k", "v": 1}], key="id")
        b = MerkleTree.from_records([{"id": "k", "v": 2}], key="id")
        m1 = a.merge(b)
        m2 = b.merge(a)
        assert m1.size == 1
        # Both orders yield the same result (commutative)
        assert m1.root_hash == m2.root_hash

    def test_empty_merge(self):
        a = MerkleTree.from_records(_make_records(5, seed=10), key="id")
        b = MerkleTree()
        merged = a.merge(b)
        assert merged.size == 5
        assert merged.root_hash == a.root_hash

    def test_returns_new_instance(self):
        a = MerkleTree.from_records([{"id": "1", "v": 1}], key="id")
        b = MerkleTree.from_records([{"id": "2", "v": 2}], key="id")
        merged = a.merge(b)
        assert merged is not a
        assert merged is not b
        # Originals unchanged
        assert a.size == 1
        assert b.size == 1


# ─── 7. merkle_diff — identical ─────────────────────────────────────────────

class TestDiffIdentical:
    def test_same_trees_identical(self):
        records = _make_records(20, seed=50)
        a = MerkleTree.from_records(records, key="id")
        b = MerkleTree.from_records(records, key="id")
        diff = merkle_diff(a, b)
        assert diff.is_identical
        assert diff.comparisons_made == 1  # short-circuit at root

    def test_empty_trees_identical(self):
        diff = merkle_diff(MerkleTree(), MerkleTree())
        assert diff.is_identical
        assert diff.comparisons_made == 1


# ─── 8. merkle_diff — different ─────────────────────────────────────────────

class TestDiffDifferent:
    def test_only_left_keys(self):
        a = MerkleTree.from_records([{"id": "a", "v": 1}, {"id": "b", "v": 2}], key="id")
        b = MerkleTree.from_records([{"id": "a", "v": 1}], key="id")
        diff = merkle_diff(a, b)
        assert "b" in diff.only_in_left
        assert len(diff.only_in_right) == 0

    def test_only_right_keys(self):
        a = MerkleTree.from_records([{"id": "a", "v": 1}], key="id")
        b = MerkleTree.from_records([{"id": "a", "v": 1}, {"id": "c", "v": 3}], key="id")
        diff = merkle_diff(a, b)
        assert "c" in diff.only_in_right
        assert len(diff.only_in_left) == 0

    def test_common_different_keys(self):
        a = MerkleTree.from_records([{"id": "x", "v": 1}], key="id")
        b = MerkleTree.from_records([{"id": "x", "v": 999}], key="id")
        diff = merkle_diff(a, b)
        assert "x" in diff.common_different
        assert len(diff.only_in_left) == 0
        assert len(diff.only_in_right) == 0


# ─── 9. Serialisation ──────────────────────────────────────────────────────

class TestSerialisation:
    def test_roundtrip(self):
        tree = MerkleTree.from_records(_make_records(15, seed=77), key="id")
        d = tree.to_dict()
        restored = MerkleTree.from_dict(d)
        assert restored.size == tree.size
        assert restored.root_hash == tree.root_hash

    def test_roundtrip_preserves_root_hash(self):
        records = [{"id": f"r{i}", "value": i * 3} for i in range(25)]
        tree = MerkleTree.from_records(records, key="id")
        original_hash = tree.root_hash
        d = tree.to_dict()
        restored = MerkleTree.from_dict(d)
        assert restored.root_hash == original_hash
        # And a second roundtrip
        d2 = restored.to_dict()
        assert MerkleTree.from_dict(d2).root_hash == original_hash


# ─── 10. CRDT law verification ─────────────────────────────────────────────

class TestCRDTLaws:
    def test_merkle_commutative(self):
        result = verify_commutative(
            lambda a, b: a.merge(b), gen_merkle_tree, trials=200, eq_fn=_eq_merkle,
        )
        assert result.passed, f"Commutativity failed: {result.first_failure}"

    def test_merkle_associative(self):
        result = verify_associative(
            lambda a, b: a.merge(b), gen_merkle_tree, trials=200, eq_fn=_eq_merkle,
        )
        assert result.passed, f"Associativity failed: {result.first_failure}"

    def test_merkle_idempotent(self):
        result = verify_idempotent(
            lambda a, b: a.merge(b), gen_merkle_tree, trials=200, eq_fn=_eq_merkle,
        )
        assert result.passed, f"Idempotency failed: {result.first_failure}"

    def test_merkle_convergence(self):
        result = verify_convergence(
            lambda a, b: a.merge(b), gen_merkle_tree, trials=100, eq_fn=_eq_merkle,
        )
        assert result.passed, f"Convergence failed: {result.first_failure}"


# ─── 11. Scale tests ───────────────────────────────────────────────────────

class TestScale:
    def test_10k_records_build_and_diff(self):
        records = _make_records(10_000, seed=123)
        tree = MerkleTree.from_records(records, key="id")
        assert tree.size == 10_000
        assert tree.root is not None

        # Diff with itself → identical, 1 comparison
        diff = merkle_diff(tree, tree)
        assert diff.is_identical
        assert diff.comparisons_made == 1

        # Diff with slightly different tree
        records2 = list(records)
        records2[0] = {"id": "k0", "value": -1}
        tree2 = MerkleTree.from_records(records2, key="id")
        diff2 = merkle_diff(tree, tree2)
        assert not diff2.is_identical
        assert "k0" in diff2.common_different

    def test_large_tree_merge(self):
        a_records = _make_records(5000, prefix="a", seed=1)
        b_records = _make_records(5000, prefix="b", seed=2)
        a = MerkleTree.from_records(a_records, key="id")
        b = MerkleTree.from_records(b_records, key="id")
        merged = a.merge(b)
        assert merged.size == 10_000
        # Originals unchanged
        assert a.size == 5000
        assert b.size == 5000


# ─── 12. Edge cases ────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_none_values_in_records(self):
        records = [
            {"id": "k0", "name": None, "count": None},
            {"id": "k1", "name": "hello", "count": 5},
        ]
        tree = MerkleTree.from_records(records, key="id")
        assert tree.size == 2
        assert tree.root_hash  # should not crash

    def test_non_string_keys(self):
        records = [
            {"id": 123, "value": "a"},
            {"id": 456, "value": "b"},
        ]
        tree = MerkleTree.from_records(records, key="id")
        assert tree.size == 2
        assert tree.contains("123")
        assert tree.contains("456")

    def test_empty_records_list(self):
        tree = MerkleTree.from_records([], key="id")
        assert tree.size == 0
        assert tree.root is None
        # Merging empty with empty
        merged = tree.merge(MerkleTree())
        assert merged.size == 0


# ─── Additional edge-case & integration tests ──────────────────────────────

class TestMerkleNodeSerde:
    """MerkleNode to_dict / from_dict round-trip."""

    def test_leaf_roundtrip(self):
        leaf = MerkleNode(hash="abc123", children=None, key_range=("a", "a"), count=1)
        d = leaf.to_dict()
        restored = MerkleNode.from_dict(d)
        assert restored.hash == leaf.hash
        assert restored.is_leaf
        assert restored.count == 1

    def test_internal_roundtrip(self):
        child = MerkleNode(hash="child", children=None, key_range=("a", "a"), count=1)
        parent = MerkleNode(hash="parent", children=[child], key_range=("a", "a"), count=1)
        d = parent.to_dict()
        restored = MerkleNode.from_dict(d)
        assert not restored.is_leaf
        assert len(restored.children) == 1  # type: ignore[arg-type]
        assert restored.children[0].hash == "child"  # type: ignore[index]
