# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""Tests for crdt_merge.gossip — gossip protocol state management.

Covers: GossipState CRUD, anti-entropy, apply_entries, multi-node
convergence, serialization round-trips, CRDT law verification, and
edge cases.
"""

from __future__ import annotations

import random

import pytest

from crdt_merge.clocks import VectorClock
from crdt_merge.gossip import GossipEntry, GossipState, anti_entropy


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


def gen_gossip_state() -> GossipState:
    """Generate a random GossipState for property-based tests."""
    node = f"node-{random.randint(0, 5)}"
    state = GossipState(node)
    for _ in range(random.randint(0, 20)):
        key = f"key-{random.randint(0, 10)}"
        state.update(key, random.randint(0, 100))
    return state


# ═════════════════════════════════════════════════════════════════════════════
# 1. GossipState creation
# ═════════════════════════════════════════════════════════════════════════════


class TestGossipStateCreation:
    def test_default_creation(self) -> None:
        state = GossipState("node-1")
        assert state.node_id == "node-1"
        assert state.fanout == 3
        assert state.size == 0
        assert state.clock == VectorClock()

    def test_custom_fanout(self) -> None:
        state = GossipState("node-2", fanout=5)
        assert state.fanout == 5
        assert state.node_id == "node-2"


# ═════════════════════════════════════════════════════════════════════════════
# 2. GossipState.update
# ═════════════════════════════════════════════════════════════════════════════


class TestGossipStateUpdate:
    def test_update_new_key(self) -> None:
        state = GossipState("n1")
        state.update("key-a", "hello")
        assert state.get("key-a") == "hello"
        assert state.size == 1

    def test_update_existing_key(self) -> None:
        state = GossipState("n1")
        state.update("key-a", "v1")
        state.update("key-a", "v2")
        assert state.get("key-a") == "v2"
        assert state.size == 1

    def test_update_returns_clock(self) -> None:
        state = GossipState("n1")
        clock = state.update("key-a", 42)
        assert isinstance(clock, VectorClock)
        assert clock.get("n1") == 1
        clock2 = state.update("key-b", 43)
        assert clock2.get("n1") == 2


# ═════════════════════════════════════════════════════════════════════════════
# 3. GossipState.delete
# ═════════════════════════════════════════════════════════════════════════════


class TestGossipStateDelete:
    def test_delete_existing_key(self) -> None:
        state = GossipState("n1")
        state.update("key-a", "v1")
        assert state.size == 1
        state.delete("key-a")
        assert state.get("key-a") is None
        assert state.size == 0
        # Entry still exists as tombstone
        entry = state.get_entry("key-a")
        assert entry is not None
        assert entry.tombstone is True

    def test_delete_missing_key(self) -> None:
        state = GossipState("n1")
        state.delete("ghost")
        assert state.get("ghost") is None
        entry = state.get_entry("ghost")
        assert entry is not None
        assert entry.tombstone is True
        assert entry.value is None


# ═════════════════════════════════════════════════════════════════════════════
# 4. GossipState.get
# ═════════════════════════════════════════════════════════════════════════════


class TestGossipStateGet:
    def test_get_existing(self) -> None:
        state = GossipState("n1")
        state.update("k", 99)
        assert state.get("k") == 99

    def test_get_missing(self) -> None:
        state = GossipState("n1")
        assert state.get("nonexistent") is None

    def test_get_tombstoned(self) -> None:
        state = GossipState("n1")
        state.update("k", "val")
        state.delete("k")
        assert state.get("k") is None


# ═════════════════════════════════════════════════════════════════════════════
# 5. GossipState.digest
# ═════════════════════════════════════════════════════════════════════════════


class TestGossipStateDigest:
    def test_digest_non_empty(self) -> None:
        state = GossipState("n1")
        state.update("a", 1)
        state.update("b", 2)
        d = state.digest()
        assert "a" in d
        assert "b" in d
        assert len(d["a"]) == 16  # sha256[:16]
        assert len(d["b"]) == 16

    def test_digest_deterministic(self) -> None:
        state = GossipState("n1")
        state.update("x", "hello")
        d1 = state.digest()
        d2 = state.digest()
        assert d1 == d2


# ═════════════════════════════════════════════════════════════════════════════
# 6. Anti-entropy push
# ═════════════════════════════════════════════════════════════════════════════


class TestAntiEntropyPush:
    def test_push_detects_missing(self) -> None:
        state = GossipState("n1")
        state.update("a", 1)
        state.update("b", 2)
        # Remote has nothing
        to_push = state.anti_entropy_push({})
        assert to_push == {"a", "b"}

    def test_push_detects_stale(self) -> None:
        state = GossipState("n1")
        state.update("a", 1)
        remote_digest = {"a": "0000000000000000"}  # Stale hash
        to_push = state.anti_entropy_push(remote_digest)
        assert "a" in to_push


# ═════════════════════════════════════════════════════════════════════════════
# 7. Anti-entropy pull
# ═════════════════════════════════════════════════════════════════════════════


class TestAntiEntropyPull:
    def test_pull_detects_missing(self) -> None:
        state = GossipState("n1")
        remote_digest = {"remote-key": "abcdef1234567890"}
        to_pull = state.anti_entropy_pull(remote_digest)
        assert "remote-key" in to_pull

    def test_pull_detects_stale(self) -> None:
        state = GossipState("n1")
        state.update("k", 1)
        local_hash = state.digest()["k"]
        remote_digest = {"k": "different_hash__"}
        to_pull = state.anti_entropy_pull(remote_digest)
        assert "k" in to_pull


# ═════════════════════════════════════════════════════════════════════════════
# 8. Anti-entropy push-pull (bidirectional)
# ═════════════════════════════════════════════════════════════════════════════


class TestAntiEntropyPushPull:
    def test_bidirectional(self) -> None:
        s1 = GossipState("n1")
        s2 = GossipState("n2")
        s1.update("only-1", "a")
        s2.update("only-2", "b")
        s1.update("shared", "v1")
        s2.update("shared", "v2")

        to_push, to_pull = s1.anti_entropy_push_pull(s2.digest())
        assert "only-1" in to_push
        assert "only-2" in to_pull
        # "shared" differs so it should appear in both sets
        assert "shared" in to_push
        assert "shared" in to_pull


# ═════════════════════════════════════════════════════════════════════════════
# 9. apply_entries
# ═════════════════════════════════════════════════════════════════════════════


class TestApplyEntries:
    def test_apply_new_entries(self) -> None:
        s1 = GossipState("n1")
        s2 = GossipState("n2")
        s1.update("x", 100)
        s1.update("y", 200)
        entries = s1.get_entries({"x", "y"})
        count = s2.apply_entries(entries)
        assert count == 2
        assert s2.get("x") == 100
        assert s2.get("y") == 200

    def test_apply_concurrent_tiebreak(self) -> None:
        """Concurrent updates should be resolved deterministically."""
        s1 = GossipState("n1")
        s2 = GossipState("n2")
        s1.update("k", "from-n1")
        s2.update("k", "from-n2")

        # Apply s1's entry to s2 — if s1's clock wins the tiebreak it
        # should update, otherwise not.  Either way, it should not crash.
        entries_1 = s1.get_entries({"k"})
        s2.apply_entries(entries_1)

        # Apply s2's original entry to s1
        entries_2 = s2.get_entries({"k"})
        s1.apply_entries(entries_2)

        # Both should converge to the same value after full exchange
        assert s1.get("k") == s2.get("k")

    def test_apply_stale_entry_rejected(self) -> None:
        s1 = GossipState("n1")
        s1.update("k", "old")
        old_entry = s1.get_entry("k")
        assert old_entry is not None

        s1.update("k", "new")
        # Try to apply the old entry — should be rejected
        count = s1.apply_entries([old_entry])
        assert count == 0
        assert s1.get("k") == "new"


# ═════════════════════════════════════════════════════════════════════════════
# 10. Multi-node convergence
# ═════════════════════════════════════════════════════════════════════════════


class TestMultiNodeConvergence:
    def _sync_pair(self, a: GossipState, b: GossipState) -> None:
        """Full bidirectional sync between two nodes."""
        to_push, to_pull = a.anti_entropy_push_pull(b.digest())
        if to_push:
            b.apply_entries(a.get_entries(to_push))
        if to_pull:
            a.apply_entries(b.get_entries(to_pull))

    def test_three_node_convergence(self) -> None:
        nodes = [GossipState(f"n{i}") for i in range(3)]
        nodes[0].update("a", 1)
        nodes[1].update("b", 2)
        nodes[2].update("c", 3)
        nodes[0].update("shared", "v0")
        nodes[1].update("shared", "v1")

        # Multiple sync rounds until convergence
        for _ in range(3):
            for i in range(len(nodes)):
                for j in range(len(nodes)):
                    if i != j:
                        self._sync_pair(nodes[i], nodes[j])

        # All nodes should agree
        for key in ("a", "b", "c", "shared"):
            values = [n.get(key) for n in nodes]
            assert len(set(str(v) for v in values)) == 1, (
                f"Nodes diverge on {key}: {values}"
            )

    def test_five_node_convergence(self) -> None:
        nodes = [GossipState(f"n{i}") for i in range(5)]
        # Each node writes unique keys
        for i, node in enumerate(nodes):
            node.update(f"unique-{i}", i * 10)
        # Plus some shared keys
        nodes[0].update("hot", "alpha")
        nodes[3].update("hot", "beta")

        for _ in range(5):
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    self._sync_pair(nodes[i], nodes[j])

        # Unique keys visible everywhere
        for i in range(5):
            for node in nodes:
                assert node.get(f"unique-{i}") == i * 10

        # Shared key converged
        hot_values = {n.get("hot") for n in nodes}
        assert len(hot_values) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 11. Serialization round-trips
# ═════════════════════════════════════════════════════════════════════════════


class TestSerialization:
    def test_gossip_entry_roundtrip(self) -> None:
        entry = GossipEntry(
            key="k1",
            value={"nested": [1, 2, 3]},
            clock=VectorClock({"n1": 3, "n2": 1}),
            tombstone=False,
        )
        d = entry.to_dict()
        restored = GossipEntry.from_dict(d)
        assert restored.key == entry.key
        assert restored.value == entry.value
        assert restored.clock == entry.clock
        assert restored.tombstone == entry.tombstone

    def test_gossip_state_roundtrip(self) -> None:
        state = GossipState("n1", fanout=5)
        state.update("a", 1)
        state.update("b", "two")
        state.delete("a")

        d = state.to_dict()
        restored = GossipState.from_dict(d)
        assert restored.node_id == state.node_id
        assert restored.fanout == state.fanout
        assert restored.clock == state.clock
        assert restored.get("a") is None
        assert restored.get("b") == "two"
        assert restored.to_dict() == d


# ═════════════════════════════════════════════════════════════════════════════
# 12. CRDT law verification
# ═════════════════════════════════════════════════════════════════════════════


class TestCRDTLaws:
    """Property-based tests verifying CRDT merge laws."""

    N_TRIALS = 30

    def _states_equivalent(self, a: GossipState, b: GossipState) -> bool:
        """Check if two states have identical entries and merged clocks."""
        if a.clock != b.clock:
            return False
        all_keys = set(a.digest()) | set(b.digest())
        for key in all_keys:
            ea = a.get_entry(key)
            eb = b.get_entry(key)
            if ea is None or eb is None:
                return False
            if ea.value != eb.value or ea.tombstone != eb.tombstone:
                return False
            if ea.clock != eb.clock:
                return False
        return True

    def test_commutative(self) -> None:
        """merge(A, B) has same entries as merge(B, A)."""
        random.seed(42)
        for _ in range(self.N_TRIALS):
            a = gen_gossip_state()
            b = gen_gossip_state()
            ab = a.merge(b)
            ba = b.merge(a)
            # node_id comes from self, so compare entries/clock only
            assert ab.clock == ba.clock
            all_keys = set(ab.digest()) | set(ba.digest())
            for key in all_keys:
                ea = ab.get_entry(key)
                eb = ba.get_entry(key)
                assert ea is not None and eb is not None, f"Missing key {key}"
                assert ea.value == eb.value, f"Value mismatch on {key}"
                assert ea.tombstone == eb.tombstone, f"Tombstone mismatch on {key}"

    def test_associative(self) -> None:
        """merge(merge(A, B), C) equivalent to merge(A, merge(B, C))."""
        random.seed(43)
        for _ in range(self.N_TRIALS):
            a = gen_gossip_state()
            b = gen_gossip_state()
            c = gen_gossip_state()
            ab_c = a.merge(b).merge(c)
            a_bc = a.merge(b.merge(c))
            assert ab_c.clock == a_bc.clock
            all_keys = set(ab_c.digest()) | set(a_bc.digest())
            for key in all_keys:
                e1 = ab_c.get_entry(key)
                e2 = a_bc.get_entry(key)
                assert e1 is not None and e2 is not None
                assert e1.value == e2.value
                assert e1.tombstone == e2.tombstone

    def test_idempotent(self) -> None:
        """merge(A, A) == A."""
        random.seed(44)
        for _ in range(self.N_TRIALS):
            a = gen_gossip_state()
            aa = a.merge(a)
            assert self._states_equivalent(a, aa)

    def test_convergence(self) -> None:
        """All merge orderings produce the same result."""
        random.seed(45)
        for _ in range(self.N_TRIALS):
            a = gen_gossip_state()
            b = gen_gossip_state()
            c = gen_gossip_state()
            r1 = a.merge(b).merge(c)
            r2 = c.merge(a).merge(b)
            r3 = b.merge(c).merge(a)
            assert r1.clock == r2.clock == r3.clock
            all_keys = set(r1.digest()) | set(r2.digest()) | set(r3.digest())
            for key in all_keys:
                e1 = r1.get_entry(key)
                e2 = r2.get_entry(key)
                e3 = r3.get_entry(key)
                assert e1 is not None and e2 is not None and e3 is not None
                assert e1.value == e2.value == e3.value
                assert e1.tombstone == e2.tombstone == e3.tombstone


# ═════════════════════════════════════════════════════════════════════════════
# 13. Standalone anti_entropy function
# ═════════════════════════════════════════════════════════════════════════════


class TestStandaloneAntiEntropy:
    def test_anti_entropy_function(self) -> None:
        local = {"a": "hash_a", "b": "hash_b", "c": "hash_c_local"}
        remote = {"b": "hash_b", "c": "hash_c_remote", "d": "hash_d"}
        result = anti_entropy(local, remote)
        assert result["missing_local"] == ["d"]
        assert result["missing_remote"] == ["a"]
        assert result["different"] == ["c"]


# ═════════════════════════════════════════════════════════════════════════════
# 14. Edge cases
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_state_operations(self) -> None:
        state = GossipState("n1")
        assert state.get("anything") is None
        assert state.digest() == {}
        assert state.anti_entropy_push({}) == set()
        assert state.anti_entropy_pull({}) == set()
        assert state.apply_entries([]) == 0

        # Merge two empties
        other = GossipState("n2")
        merged = state.merge(other)
        assert merged.size == 0
        assert merged.clock == VectorClock()

        # get_entries with missing keys
        assert state.get_entries({"no", "keys"}) == []
