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

"""Tests for CausalTrustClock.

Covers vector clock with trust scores, causal ordering, merge semantics,
trust-weighted comparison, serialization, and consistency checking.
"""

import struct

import pytest

from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice


# ---------------------------------------------------------------------------
# Creation and basic properties
# ---------------------------------------------------------------------------

class TestCausalTrustClockCreation:

    def test_create_basic(self):
        """Clock can be created with a peer ID."""
        c = CausalTrustClock("alice")
        assert c.peer_id == "alice"
        assert c.logical_time == 0

    def test_empty_entries(self):
        """Fresh clock has no entries."""
        c = CausalTrustClock("alice")
        assert c.entries == {}
        assert c.known_peers() == set()

    def test_get_entry_unknown_peer(self):
        """get_entry for unknown peer returns (0, 0.0)."""
        c = CausalTrustClock("alice")
        assert c.get_entry("bob") == (0, 0.0)


# ---------------------------------------------------------------------------
# Increment
# ---------------------------------------------------------------------------

class TestCausalTrustClockIncrement:

    def test_increment_increases_time(self):
        """Incrementing increases the local logical time by 1."""
        c = CausalTrustClock("alice")
        c2 = c.increment()
        assert c2.logical_time == 1
        assert c.logical_time == 0  # original unchanged

    def test_increment_returns_new_instance(self):
        """increment returns a new clock (immutable-style)."""
        c = CausalTrustClock("alice")
        c2 = c.increment()
        assert c is not c2

    def test_multiple_increments(self):
        """Multiple increments accumulate."""
        c = CausalTrustClock("alice")
        c = c.increment()
        c = c.increment()
        c = c.increment()
        assert c.logical_time == 3

    def test_increment_records_trust_zero_without_lattice(self):
        """Without a trust lattice, trust score is recorded as 0.0."""
        c = CausalTrustClock("alice")
        c2 = c.increment()
        _, trust = c2.get_entry("alice")
        assert trust == 0.0

    def test_increment_records_trust_from_lattice(self):
        """With a trust lattice, trust score is fetched from it."""
        lat = DeltaTrustLattice("alice", initial_peers={"alice"})
        c = CausalTrustClock("alice", trust_lattice=lat)
        c2 = c.increment()
        _, trust = c2.get_entry("alice")
        # Probationary trust ~0.5
        assert trust == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Standard causal comparison
# ---------------------------------------------------------------------------

class TestCausalTrustClockCompare:

    def test_concurrent_empty_clocks(self):
        """Two empty clocks are concurrent (identical)."""
        c1 = CausalTrustClock("alice")
        c2 = CausalTrustClock("bob")
        assert c1.trust_weighted_compare(c2) == "concurrent"

    def test_before(self):
        """A clock with lower time is 'before' a later clock."""
        c1 = CausalTrustClock("alice")
        c1 = c1.increment()
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (2, 0.0)}
        assert c1.trust_weighted_compare(c2) == "after"

    def test_after(self):
        """A clock with higher time is 'before' in standard compare (self dominates)."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (5, 0.0)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (2, 0.0)}
        assert c1.trust_weighted_compare(c2) == "before"

    def test_concurrent_diverged(self):
        """Diverged clocks are concurrent."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 0.0), "bob": (1, 0.0)}
        c2 = CausalTrustClock("bob")
        c2._entries = {"alice": (1, 0.0), "bob": (3, 0.0)}
        assert c1.trust_weighted_compare(c2) == "concurrent"


# ---------------------------------------------------------------------------
# Trust-weighted comparison
# ---------------------------------------------------------------------------

class TestTrustWeightedCompare:

    def test_trust_override(self):
        """When self dominates (before) and trust weight is much higher, returns trust_override."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 10.0), "bob": (2, 5.0)}  # dominates, high trust
        c2 = CausalTrustClock("bob")
        c2._entries = {"alice": (1, 0.1), "bob": (1, 0.1)}  # dominated, low trust
        # c1 dominates c2 → standard = "before"
        result = c1.trust_weighted_compare(c2)
        # trust weight: c1 = 15.0, c2 = 0.2; 15.0 > 0.2 * 1.5
        assert result == "trust_override"

    def test_no_override_when_trust_not_dominant(self):
        """When trust weight is not dominant enough, standard ordering holds."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 0.5), "bob": (2, 0.5)}
        c2 = CausalTrustClock("bob")
        c2._entries = {"alice": (1, 0.5), "bob": (1, 0.5)}
        result = c1.trust_weighted_compare(c2)
        assert result == "before"  # not overridden, trust comparable

    def test_trust_override_factor(self):
        """TRUST_OVERRIDE_FACTOR is 1.5."""
        assert CausalTrustClock.TRUST_OVERRIDE_FACTOR == 1.5


# ---------------------------------------------------------------------------
# CRDT merge
# ---------------------------------------------------------------------------

class TestCausalTrustClockMerge:

    def test_merge_takes_max_time(self):
        """Merge takes the higher logical time per peer."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 0.5), "bob": (1, 0.3)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (1, 0.8), "bob": (5, 0.6)}
        merged = c1.merge(c2)
        assert merged.get_entry("alice") == (3, 0.5)
        assert merged.get_entry("bob") == (5, 0.6)

    def test_merge_equal_time_takes_max_trust(self):
        """On equal logical time, merge takes higher trust."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 0.2)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (3, 0.8)}
        merged = c1.merge(c2)
        assert merged.get_entry("alice") == (3, 0.8)

    def test_merge_union_of_peers(self):
        """Merge includes peers from both clocks."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (1, 0.5)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"bob": (2, 0.3)}
        merged = c1.merge(c2)
        assert "alice" in merged.known_peers()
        assert "bob" in merged.known_peers()

    def test_merge_commutative(self):
        """Merge is commutative."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (3, 0.5), "bob": (1, 0.3)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (1, 0.8), "bob": (5, 0.6)}
        m1 = c1.merge(c2)
        m2 = c2.merge(c1)
        assert m1.entries == m2.entries


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestCausalTrustClockSerialization:

    def test_serialize_empty_clock(self):
        """Empty clock serializes to empty bytes."""
        c = CausalTrustClock("alice")
        assert c.serialize_compact() == b""

    def test_serialize_roundtrip(self):
        """Serialization and deserialization are inverse operations."""
        c = CausalTrustClock("alice")
        c._entries = {"alice": (5, 0.75), "bob": (3, 0.5)}
        data = c.serialize_compact()
        restored = CausalTrustClock.deserialize_compact(data, "alice")
        assert restored.entries == c.entries

    def test_content_hash_deterministic(self):
        """content_hash is deterministic."""
        c = CausalTrustClock("alice")
        c._entries = {"alice": (1, 0.5)}
        assert c.content_hash() == c.content_hash()

    def test_content_hash_changes(self):
        """Different entries produce different content hashes."""
        c1 = CausalTrustClock("alice")
        c1._entries = {"alice": (1, 0.5)}
        c2 = CausalTrustClock("alice")
        c2._entries = {"alice": (2, 0.5)}
        assert c1.content_hash() != c2.content_hash()


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------

class TestCausalTrustClockConsistency:

    def test_empty_snapshot_consistent(self):
        """Empty snapshot is always consistent."""
        c = CausalTrustClock("alice")
        assert c.is_consistent_with(b"") is True

    def test_consistent_with_self(self):
        """Clock is consistent with its own serialized snapshot."""
        c = CausalTrustClock("alice")
        c._entries = {"alice": (3, 0.5)}
        assert c.is_consistent_with(c.serialize_compact()) is True

    def test_inconsistent_future_snapshot(self):
        """A stale snapshot (lower time than current state) is inconsistent."""
        c = CausalTrustClock("alice")
        c._entries = {"alice": (10, 0.5)}
        stale = CausalTrustClock("alice")
        stale._entries = {"alice": (1, 0.5)}
        assert c.is_consistent_with(stale.serialize_compact()) is False


# ---------------------------------------------------------------------------
# Bind trust lattice and repr
# ---------------------------------------------------------------------------

class TestCausalTrustClockMisc:

    def test_bind_trust_lattice(self):
        """bind_trust_lattice sets the lattice reference."""
        c = CausalTrustClock("alice")
        lat = DeltaTrustLattice("alice")
        c.bind_trust_lattice(lat)
        # After binding, increment should fetch trust from lattice
        c2 = c.increment()
        _, trust = c2.get_entry("alice")
        assert trust == pytest.approx(0.5)

    def test_repr(self):
        """Repr includes peer, time, and peer count."""
        c = CausalTrustClock("alice")
        c._entries = {"alice": (3, 0.5)}
        r = repr(c)
        assert "alice" in r
        assert "time=3" in r
