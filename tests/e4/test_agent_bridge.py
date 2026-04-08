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

"""Tests for TrustAgentState and TrustAnnotatedEntry.

Covers agent state sync with trust, memory context handling,
trust-weighted conflict resolution, and snapshot import/export.
"""

import pytest

from crdt_merge.e4.integration.agent_bridge import (
    TrustAgentState,
    TrustAnnotatedEntry,
)
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.typed_trust import TypedTrustScore


# ---------------------------------------------------------------------------
# TrustAnnotatedEntry
# ---------------------------------------------------------------------------

class TestTrustAnnotatedEntry:

    def test_creation(self):
        """TrustAnnotatedEntry stores all fields."""
        entry = TrustAnnotatedEntry(
            key="k1", value="v1", peer_id="alice",
            trust_at_write=0.8, timestamp=100.0,
        )
        assert entry.key == "k1"
        assert entry.value == "v1"
        assert entry.peer_id == "alice"
        assert entry.trust_at_write == 0.8
        assert entry.timestamp == 100.0

    def test_default_timestamp(self):
        """Default timestamp is 0.0."""
        entry = TrustAnnotatedEntry(
            key="k", value="v", peer_id="p", trust_at_write=0.5,
        )
        assert entry.timestamp == 0.0


# ---------------------------------------------------------------------------
# TrustAgentState: creation and binding
# ---------------------------------------------------------------------------

class TestTrustAgentStateCreation:

    def test_create_no_lattice(self):
        """Can create TrustAgentState without a lattice."""
        state = TrustAgentState()
        assert state.size == 0

    def test_create_with_lattice(self):
        """Can create TrustAgentState with a lattice."""
        lattice = DeltaTrustLattice("local")
        state = TrustAgentState(trust_lattice=lattice)
        assert state.size == 0

    def test_bind_trust_lattice(self):
        """bind_trust_lattice sets the lattice post-init."""
        state = TrustAgentState()
        lattice = DeltaTrustLattice("local")
        state.bind_trust_lattice(lattice)
        # No assertion error - bound successfully


# ---------------------------------------------------------------------------
# put and get
# ---------------------------------------------------------------------------

class TestTrustAgentStatePutGet:

    def test_put_and_get(self):
        """put stores entry; get retrieves it."""
        state = TrustAgentState()
        entry = state.put("k1", "v1", "alice")
        assert entry.key == "k1"
        assert entry.value == "v1"
        retrieved = state.get("k1")
        assert retrieved is entry

    def test_get_missing_returns_none(self):
        """get returns None for missing key."""
        state = TrustAgentState()
        assert state.get("nonexistent") is None

    def test_put_with_timestamp(self):
        """put respects custom timestamp."""
        state = TrustAgentState()
        entry = state.put("k1", "v1", "alice", timestamp=42.0)
        assert entry.timestamp == 42.0

    def test_put_default_trust_no_lattice(self):
        """Without lattice, trust defaults to 0.5 (probation)."""
        state = TrustAgentState()
        entry = state.put("k1", "v1", "alice")
        assert entry.trust_at_write == 0.5

    def test_put_with_lattice_trust(self):
        """With lattice, trust is looked up from lattice."""
        lattice = DeltaTrustLattice("local", initial_peers={"alice"})
        state = TrustAgentState(trust_lattice=lattice)
        entry = state.put("k1", "v1", "alice")
        # alice is probationary -> overall_trust() == 0.5
        assert entry.trust_at_write == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestTrustAgentStateDelete:

    def test_delete_existing(self):
        """delete removes and returns the entry."""
        state = TrustAgentState()
        state.put("k1", "v1", "alice")
        deleted = state.delete("k1")
        assert deleted is not None
        assert deleted.key == "k1"
        assert state.get("k1") is None

    def test_delete_missing(self):
        """delete returns None for missing key."""
        state = TrustAgentState()
        assert state.delete("nonexistent") is None


# ---------------------------------------------------------------------------
# Conflict resolution: trust-weighted
# ---------------------------------------------------------------------------

class TestConflictResolution:

    def test_higher_trust_wins(self):
        """Higher trust entry wins in a conflict."""
        state = TrustAgentState(trust_weight_context=True)
        # Manually set entries to control trust
        state._entries["k"] = TrustAnnotatedEntry(
            key="k", value="low_trust", peer_id="evil",
            trust_at_write=0.2, timestamp=10.0,
        )
        entry = state.put("k", "high_trust", "good", timestamp=5.0)
        # Without lattice, new entry gets 0.5 trust > 0.2
        result = state.get("k")
        assert result.value == "high_trust"

    def test_equal_trust_lww(self):
        """Equal trust falls back to LWW (later timestamp wins)."""
        state = TrustAgentState(trust_weight_context=True)
        state._entries["k"] = TrustAnnotatedEntry(
            key="k", value="older", peer_id="alice",
            trust_at_write=0.5, timestamp=1.0,
        )
        entry = state.put("k", "newer", "bob", timestamp=2.0)
        result = state.get("k")
        assert result.value == "newer"

    def test_trust_weight_disabled(self):
        """With trust_weight_context=False, LWW only."""
        state = TrustAgentState(trust_weight_context=False)
        state._entries["k"] = TrustAnnotatedEntry(
            key="k", value="old", peer_id="alice",
            trust_at_write=0.9, timestamp=1.0,
        )
        state.put("k", "new", "bob", timestamp=2.0)
        result = state.get("k")
        assert result.value == "new"


# ---------------------------------------------------------------------------
# merge_context
# ---------------------------------------------------------------------------

class TestMergeContext:

    def test_merge_disjoint_keys(self):
        """Merging disjoint states unions all entries."""
        s1 = TrustAgentState()
        s1.put("k1", "v1", "alice")
        s2 = TrustAgentState()
        s2.put("k2", "v2", "bob")
        merged = s1.merge_context(s2)
        assert merged.size == 2
        assert merged.get("k1").value == "v1"
        assert merged.get("k2").value == "v2"

    def test_merge_conflicting_keys(self):
        """Merging conflicting keys resolves via trust."""
        s1 = TrustAgentState()
        s1._entries["k"] = TrustAnnotatedEntry(
            key="k", value="v1", peer_id="alice",
            trust_at_write=0.9, timestamp=1.0,
        )
        s2 = TrustAgentState()
        s2._entries["k"] = TrustAnnotatedEntry(
            key="k", value="v2", peer_id="bob",
            trust_at_write=0.3, timestamp=2.0,
        )
        merged = s1.merge_context(s2)
        # alice has higher trust -> her value wins
        assert merged.get("k").value == "v1"

    def test_merge_one_sided(self):
        """Merge with empty state returns the non-empty entries."""
        s1 = TrustAgentState()
        s1.put("k1", "v1", "alice")
        s2 = TrustAgentState()
        merged = s1.merge_context(s2)
        assert merged.size == 1


# ---------------------------------------------------------------------------
# snapshot / load_snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:

    def test_snapshot_returns_dict(self):
        """snapshot() returns a dict of entries."""
        state = TrustAgentState()
        state.put("k1", "v1", "alice")
        snap = state.snapshot()
        assert "k1" in snap
        assert snap["k1"].value == "v1"

    def test_load_snapshot(self):
        """load_snapshot replaces all entries."""
        state = TrustAgentState()
        entry = TrustAnnotatedEntry(
            key="k1", value="v1", peer_id="alice",
            trust_at_write=0.5, timestamp=0.0,
        )
        state.load_snapshot({"k1": entry})
        assert state.get("k1") is entry
        assert state.size == 1


# ---------------------------------------------------------------------------
# ranked_entries and peer_contributions
# ---------------------------------------------------------------------------

class TestIntrospection:

    def test_ranked_entries_by_trust(self):
        """ranked_entries sorts by trust_at_write descending."""
        state = TrustAgentState()
        state._entries["a"] = TrustAnnotatedEntry("a", "v", "p1", 0.9)
        state._entries["b"] = TrustAnnotatedEntry("b", "v", "p2", 0.3)
        state._entries["c"] = TrustAnnotatedEntry("c", "v", "p3", 0.7)
        ranked = state.ranked_entries()
        trusts = [e.trust_at_write for e in ranked]
        assert trusts == sorted(trusts, reverse=True)

    def test_peer_contributions(self):
        """peer_contributions counts entries per peer."""
        state = TrustAgentState()
        state.put("k1", "v1", "alice")
        state.put("k2", "v2", "alice")
        state.put("k3", "v3", "bob")
        contributions = state.peer_contributions()
        assert contributions["alice"] == 2
        assert contributions["bob"] == 1

    def test_size(self):
        """size property counts entries."""
        state = TrustAgentState()
        assert state.size == 0
        state.put("k1", "v1", "alice")
        assert state.size == 1
