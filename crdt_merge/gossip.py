# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Gossip protocol state management for distributed CRDT synchronization.

This module provides the STATE MACHINE for gossip-based sync.
You provide the transport (HTTP, TCP, UDP, etc.).
crdt-merge provides the merge logic.

Key design: NO networking. NO scheduling. Pure state machine.

The GossipState class manages a key-value store where each entry is tracked
with a VectorClock for causal ordering. Anti-entropy methods enable efficient
synchronisation by comparing compact digests rather than full state.

All CRDT types implement:
  - merge()    — returns a NEW instance (never mutates)
  - to_dict()  — serialise to a plain dict
  - from_dict() — deserialise from a plain dict

CRDT convergence guarantees:
  - Commutative:  merge(A, B) == merge(B, A)
  - Associative:  merge(merge(A, B), C) == merge(A, merge(B, C))
  - Idempotent:   merge(A, A) == A

Usage:
    from crdt_merge.gossip import GossipState, GossipEntry, anti_entropy

    state = GossipState("node-1")
    state.update("user:42", {"name": "Alice"})
    state.update("user:43", {"name": "Bob"})

    # Anti-entropy: compare digests to find what needs syncing
    local_digest = state.digest()
    push_keys, pull_keys = state.anti_entropy_push_pull(remote_digest)

    # Apply remote entries received over the wire
    count = state.apply_entries(remote_entries)

    # Full merge of two complete states
    merged = state_a.merge(state_b)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from crdt_merge.clocks import Ordering, VectorClock

# ═════════════════════════════════════════════════════════════════════════════
# GossipEntry — a single key-value entry with causal metadata
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class GossipEntry:
    """A single entry in the gossip key-value store.

    Each entry tracks:
      - key:       the unique identifier for this datum
      - value:     the application payload (any JSON-serialisable value)
      - clock:     a VectorClock recording the causal history of this entry
      - tombstone: whether the entry has been logically deleted

    Tombstoned entries are retained so that deletes propagate through
    the gossip protocol — they will eventually be reaped by compaction.
    """

    key: str
    value: Any
    clock: VectorClock
    tombstone: bool = False

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON encoding."""
        return {
            "key": self.key,
            "value": self.value,
            "clock": self.clock.to_dict(),
            "tombstone": self.tombstone,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GossipEntry:
        """Deserialize from a plain dict.

        Args:
            d: A dict previously produced by ``to_dict()``.

        Returns:
            A new GossipEntry instance.
        """
        return cls(
            key=d["key"],
            value=d["value"],
            clock=VectorClock.from_dict(d["clock"]),
            tombstone=d.get("tombstone", False),
        )

    def __repr__(self) -> str:
        tomb = " [TOMBSTONE]" if self.tombstone else ""
        return (
            f"GossipEntry(key={self.key!r}, value={self.value!r}, "
            f"clock={self.clock}{tomb})"
        )

# ═════════════════════════════════════════════════════════════════════════════
# GossipState — the gossip protocol state machine
# ═════════════════════════════════════════════════════════════════════════════

class GossipState:
    """Gossip protocol state machine for distributed CRDT synchronization.

    Manages a replicated key-value store where every mutation is tracked
    by a VectorClock. Provides anti-entropy methods to efficiently detect
    and resolve differences between replicas.

    Parameters:
        node_id: Unique identifier for this node in the cluster.
        fanout:  Number of peers to contact per gossip round (default 3).

    Example::

        state = GossipState("node-1", fanout=2)
        state.update("sensor:temp", 22.5)
        digest = state.digest()
    """

    def __init__(self, node_id: str, fanout: int = 3) -> None:
        self._node_id: str = node_id
        self._fanout: int = fanout
        self._entries: Dict[str, GossipEntry] = {}
        self._clock: VectorClock = VectorClock()

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def node_id(self) -> str:
        """The unique identifier of this node."""
        return self._node_id

    @property
    def fanout(self) -> int:
        """The gossip fanout (number of peers per round)."""
        return self._fanout

    @property
    def size(self) -> int:
        """Count of live (non-tombstoned) entries."""
        return sum(1 for e in self._entries.values() if not e.tombstone)

    @property
    def clock(self) -> VectorClock:
        """The node-level vector clock reflecting all observed events."""
        return self._clock

    # ── Mutations ──────────────────────────────────────────────────────────

    def update(self, key: str, value: Any, clock: Optional[VectorClock] = None) -> VectorClock:
        """Insert or update a key-value pair.

        Increments this node's logical clock.  If *clock* is provided
        (e.g. when replaying a remote event), it is merged with the
        current clock to preserve causality.

        Args:
            key:   The key to upsert.
            value: The new value.
            clock: Optional external clock to merge in.

        Returns:
            The updated node-level VectorClock.
        """
        self._clock = self._clock.increment(self._node_id)
        entry_clock = clock.merge(self._clock) if clock else self._clock

        # Only update if new clock dominates or wins the concurrent tiebreak
        existing = self._entries.get(key)
        if existing is None or self._should_update(existing.clock, entry_clock):
            self._entries[key] = GossipEntry(
                key=key, value=value, clock=entry_clock, tombstone=False,
            )
        return self._clock

    def delete(self, key: str) -> VectorClock:
        """Logically delete a key by tombstoning it.

        The entry is retained with ``tombstone=True`` so the deletion
        propagates to other nodes during anti-entropy sync.

        Args:
            key: The key to delete.

        Returns:
            The updated node-level VectorClock.
        """
        self._clock = self._clock.increment(self._node_id)
        existing = self._entries.get(key)
        if existing is not None:
            self._entries[key] = GossipEntry(
                key=key, value=existing.value, clock=self._clock, tombstone=True,
            )
        else:
            self._entries[key] = GossipEntry(
                key=key, value=None, clock=self._clock, tombstone=True,
            )
        return self._clock

    # ── Reads ──────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Get the live value for *key*, or ``None`` if missing / tombstoned."""
        entry = self._entries.get(key)
        if entry is not None and not entry.tombstone:
            return entry.value
        return None

    def get_entry(self, key: str) -> Optional[GossipEntry]:
        """Get the raw GossipEntry for *key*, including tombstones."""
        return self._entries.get(key)

    def get_entries(self, keys: Set[str]) -> List[GossipEntry]:
        """Get raw GossipEntry objects for a set of keys.

        Keys not present in the store are silently skipped.

        Args:
            keys: The set of keys to retrieve.

        Returns:
            A list of GossipEntry objects (order not guaranteed).
        """
        return [self._entries[k] for k in keys if k in self._entries]

    # ── Digest & Anti-entropy ──────────────────────────────────────────────

    def digest(self) -> Dict[str, str]:
        """Build a compact digest of the current state.

        Returns a dict mapping each key to a short hex hash derived from
        the entry's value, clock, and tombstone flag.  Two nodes with the
        same digest for a key are in agreement; different hashes indicate
        a difference that anti-entropy should resolve.

        Returns:
            ``{key: hex_hash}`` for every entry (including tombstones).
        """
        result: Dict[str, str] = {}
        for key, entry in self._entries.items():
            content = json.dumps(
                {
                    "v": str(entry.value),
                    "c": entry.clock.to_dict(),
                    "t": entry.tombstone,
                },
                sort_keys=True,
            )
            result[key] = hashlib.sha256(content.encode()).hexdigest()[:16]
        return result

    def anti_entropy_push(self, remote_digest: Dict[str, str]) -> Set[str]:
        """Determine which keys this node should *push* to the remote.

        A key should be pushed when the remote is either missing it entirely
        or has a different hash (indicating a stale or divergent version).

        Args:
            remote_digest: The remote node's digest.

        Returns:
            Set of keys that need to be pushed to the remote.
        """
        local_digest = self.digest()
        to_push: Set[str] = set()
        for key, local_hash in local_digest.items():
            if key not in remote_digest or remote_digest[key] != local_hash:
                to_push.add(key)
        return to_push

    def anti_entropy_pull(self, remote_digest: Dict[str, str]) -> Set[str]:
        """Determine which keys this node should *pull* from the remote.

        A key should be pulled when we are missing it or our hash differs
        from the remote's.

        Args:
            remote_digest: The remote node's digest.

        Returns:
            Set of keys to request from the remote.
        """
        local_digest = self.digest()
        to_pull: Set[str] = set()
        for key, remote_hash in remote_digest.items():
            if key not in local_digest or local_digest[key] != remote_hash:
                to_pull.add(key)
        return to_pull

    def anti_entropy_push_pull(
        self, remote_digest: Dict[str, str]
    ) -> Tuple[Set[str], Set[str]]:
        """Bidirectional anti-entropy: determine push and pull sets.

        This is equivalent to calling ``anti_entropy_push`` and
        ``anti_entropy_pull`` but may be more convenient.

        Args:
            remote_digest: The remote node's digest.

        Returns:
            A tuple ``(keys_to_push, keys_to_pull)``.
        """
        return (
            self.anti_entropy_push(remote_digest),
            self.anti_entropy_pull(remote_digest),
        )

    # ── Applying remote entries ────────────────────────────────────────────

    def apply_entries(self, entries: List[GossipEntry]) -> int:
        """Apply a batch of entries received from a remote node.

        Each entry is accepted only if its clock dominates or wins the
        concurrent tiebreak against the locally held version.  The node
        clock is advanced to incorporate the causal history of every
        accepted entry.

        Args:
            entries: Remote entries to apply.

        Returns:
            Number of entries that caused a local update.
        """
        updates = 0
        for entry in entries:
            existing = self._entries.get(entry.key)
            if existing is None or self._should_update(existing.clock, entry.clock):
                self._entries[entry.key] = GossipEntry(
                    key=entry.key,
                    value=entry.value,
                    clock=entry.clock,
                    tombstone=entry.tombstone,
                )
                # Merge remote clock into our node clock to maintain causality
                self._clock = self._clock.merge(entry.clock)
                updates += 1
        return updates

    # ── Conflict resolution ────────────────────────────────────────────────

    def _should_update(
        self, old_clock: VectorClock, new_clock: VectorClock
    ) -> bool:
        """Determine whether *new_clock* should replace *old_clock*.

        The new clock wins if it is strictly AFTER the old clock.
        In the CONCURRENT case a deterministic tiebreak is applied so
        all nodes converge to the same value regardless of message order.

        The tiebreak compares the sorted string representation of the
        clock dicts — this is arbitrary but deterministic.

        Returns:
            ``True`` if the entry with *new_clock* should replace the one
            with *old_clock*.
        """
        ordering = old_clock.compare(new_clock)
        if ordering == Ordering.BEFORE:  # old < new → update
            return True
        if ordering == Ordering.CONCURRENT:
            # Deterministic tiebreak: lexicographic comparison of sorted items
            return str(sorted(new_clock.value.items())) >= str(
                sorted(old_clock.value.items())
            )
        return False  # EQUAL or AFTER → don't update

    # ── CRDT merge ─────────────────────────────────────────────────────────

    @staticmethod
    def _deterministic_entry_key(entry: GossipEntry) -> tuple:
        """Build an order-independent comparison key for deterministic tiebreaks.

        Used by ``merge()`` to guarantee commutativity and associativity
        when vector clocks are concurrent or equal.  The key is a tuple
        that can be compared with ``>=`` to pick a stable winner.
        """
        return (str(entry.value), entry.tombstone)

    def merge(self, other: GossipState) -> GossipState:
        """Merge two GossipState instances. Returns a NEW instance.

        The merged state contains the union of all keys.  Entry clocks
        are always merged (element-wise max).  Value selection uses a
        deterministic content-based comparison so that the result is
        independent of argument order and grouping.

        Satisfies: commutative, associative, idempotent.

        Args:
            other: The other GossipState to merge with.

        Returns:
            A new GossipState representing the merged state.
        """
        result = GossipState(self._node_id, self._fanout)
        result._clock = self._clock.merge(other._clock)

        all_keys = set(self._entries) | set(other._entries)
        for key in all_keys:
            a = self._entries.get(key)
            b = other._entries.get(key)
            if a is not None and b is not None:
                merged_clock = a.clock.merge(b.clock)
                # Deterministic value selection: pick the entry whose
                # content sorts higher.  This is commutative (order of
                # a, b doesn't matter) and associative (max is
                # associative), so the CRDT laws hold.
                if self._deterministic_entry_key(a) >= self._deterministic_entry_key(b):
                    winner_value, winner_tomb = a.value, a.tombstone
                else:
                    winner_value, winner_tomb = b.value, b.tombstone
                result._entries[key] = GossipEntry(
                    key=key,
                    value=winner_value,
                    clock=merged_clock,
                    tombstone=winner_tomb,
                )
            elif a is not None:
                result._entries[key] = GossipEntry(
                    key=key, value=a.value, clock=a.clock, tombstone=a.tombstone,
                )
            else:
                assert b is not None
                result._entries[key] = GossipEntry(
                    key=key, value=b.value, clock=b.clock, tombstone=b.tombstone,
                )
        return result

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the full state to a plain dict."""
        return {
            "type": "gossip_state",
            "node_id": self._node_id,
            "fanout": self._fanout,
            "entries": {k: e.to_dict() for k, e in self._entries.items()},
            "clock": self._clock.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> GossipState:
        """Deserialize from a plain dict.

        Args:
            d: A dict previously produced by ``to_dict()``.

        Returns:
            A new GossipState instance.
        """
        state = cls(d["node_id"], d.get("fanout", 3))
        state._clock = VectorClock.from_dict(d.get("clock", {}))
        for k, e in d.get("entries", {}).items():
            state._entries[k] = GossipEntry.from_dict(e)
        return state

    # ── Dunder methods ─────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GossipState):
            return NotImplemented
        return (
            self._node_id == other._node_id
            and self._fanout == other._fanout
            and self._clock == other._clock
            and self._entries == other._entries
        )

    def __repr__(self) -> str:
        return (
            f"GossipState(node_id={self._node_id!r}, "
            f"size={self.size}, clock={self._clock})"
        )

# ═════════════════════════════════════════════════════════════════════════════
# Standalone anti-entropy helper
# ═════════════════════════════════════════════════════════════════════════════

def anti_entropy(
    local_digest: Dict[str, str], remote_digest: Dict[str, str]
) -> Dict[str, list]:
    """Compare two digests and classify keys by sync action needed.

    This is a pure function operating on digest dicts — it does not need
    access to any GossipState.  Useful when you want anti-entropy logic
    in a stateless layer (e.g. a gateway or coordinator).

    Args:
        local_digest:  ``{key: hash}`` from the local node.
        remote_digest: ``{key: hash}`` from the remote node.

    Returns:
        A dict with three lists::

            {
                "missing_local":  [keys in remote but not local],
                "missing_remote": [keys in local but not remote],
                "different":      [keys in both with different hashes],
            }
    """
    local_keys = set(local_digest)
    remote_keys = set(remote_digest)

    missing_local = sorted(remote_keys - local_keys)
    missing_remote = sorted(local_keys - remote_keys)
    different = sorted(
        k
        for k in local_keys & remote_keys
        if local_digest[k] != remote_digest[k]
    )

    return {
        "missing_local": missing_local,
        "missing_remote": missing_remote,
        "different": different,
    }
