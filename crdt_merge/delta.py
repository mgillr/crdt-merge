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

"""
Delta-State Dataset Sync — O(delta) synchronization instead of O(n).

Instead of exchanging full datasets, compute and ship only what changed.
Deltas are composable: delta(1→2) ⊔ delta(2→3) == delta(1→3).

Inspired by Almeida et al. (2018) δ-CRDTs, extended for tabular datasets.

Usage:
    from crdt_merge.delta import DeltaStore, compute_delta, apply_delta, compose_deltas

    store = DeltaStore(key="id")
    store.ingest(initial_records)

    # Later, compute what changed
    delta = store.compute_delta(updated_records)

    # Ship delta to remote (much smaller than full state)
    remote_store.apply_delta(delta)

    # Compose multiple deltas
    combined = compose_deltas(delta_1, delta_2, delta_3)
"""

from __future__ import annotations
import copy
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .strategies import MergeSchema, LWW

__all__ = ["Delta", "DeltaStore", "compute_delta", "apply_delta", "compose_deltas"]

class Delta:
    """
    Represents the minimal changeset between two dataset states.

    Contains:
        added: Records that are new
        modified: Records that changed (with new values)
        removed: Keys that were deleted
        version: Monotonic version counter
        timestamp: When this delta was computed
    """

    __slots__ = ('added', 'modified', 'removed', 'version', 'timestamp', 'source_node')

    def __init__(
        self,
        added: Optional[List[dict]] = None,
        modified: Optional[List[dict]] = None,
        removed: Optional[List[str]] = None,
        version: int = 0,
        timestamp: Optional[float] = None,
        source_node: str = "",
    ):
        """Initialize a Delta with changeset components.

        Args:
            added: Records that are new in this delta. Defaults to empty list.
            modified: Records that changed (with updated values). Defaults to empty list.
            removed: Keys of records that were deleted. Defaults to empty list.
            version: Monotonic version counter for ordering deltas.
            timestamp: Unix timestamp when this delta was computed. Defaults to
                current time.
            source_node: Identifier of the node that produced this delta.
        """
        self.added = added or []
        self.modified = modified or []
        self.removed = removed or []
        self.version = version
        self.timestamp = timestamp or time.time()
        self.source_node = source_node

    @property
    def size(self) -> int:
        """Total number of changes in this delta.

        Returns:
            int: Sum of added, modified, and removed record counts.
        """
        return len(self.added) + len(self.modified) + len(self.removed)

    @property
    def is_empty(self) -> bool:
        """Whether this delta contains no changes.

        Returns:
            bool: True if the delta has zero added, modified, and removed records.
        """
        return self.size == 0

    def to_dict(self) -> dict:
        """Serialize the delta to a plain dictionary.

        Returns:
            dict: Dictionary containing all delta fields (added, modified,
                removed, version, timestamp, source_node).
        """
        return {
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "version": self.version,
            "timestamp": self.timestamp,
            "source_node": self.source_node,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Delta:
        """Reconstruct a Delta from a dictionary.

        Args:
            d: Dictionary with delta fields as produced by ``to_dict()``.

        Returns:
            Delta: A new Delta instance.
        """
        return cls(
            added=d.get("added", []),
            modified=d.get("modified", []),
            removed=d.get("removed", []),
            version=d.get("version", 0),
            timestamp=d.get("timestamp"),
            source_node=d.get("source_node", ""),
        )

    def __repr__(self) -> str:
        """Return a concise summary string showing change counts and version."""
        return f"Delta(+{len(self.added)} ~{len(self.modified)} -{len(self.removed)}, v{self.version})"

def _record_hash(record: dict, key: str) -> str:
    """Hash a record's non-key content for change detection."""
    parts = []
    for k in sorted(record.keys()):
        if k != key:
            parts.append(f"{k}={record[k]}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

def compute_delta(
    old_records: List[dict],
    new_records: List[dict],
    key: str,
    version: int = 0,
    source_node: str = "",
) -> Delta:
    """
    Compute the minimal delta between old and new states.

    Returns only what changed — added, modified, removed.
    """
    old_index = {}
    old_hashes = {}
    for r in old_records:
        k = r.get(key)
        if k is not None:
            old_index[k] = r
            old_hashes[k] = _record_hash(r, key)

    new_index = {}
    new_hashes = {}
    for r in new_records:
        k = r.get(key)
        if k is not None:
            new_index[k] = r
            new_hashes[k] = _record_hash(r, key)

    added = []
    modified = []
    removed = []

    # Find added and modified
    for k, r in new_index.items():
        if k not in old_index:
            added.append(r)
        elif new_hashes[k] != old_hashes[k]:
            modified.append(r)

    # Find removed
    for k in old_index:
        if k not in new_index:
            removed.append(str(k))

    return Delta(added, modified, removed, version, source_node=source_node)

def apply_delta(
    records: List[dict],
    delta: Delta,
    key: str,
    schema: Optional[MergeSchema] = None,
) -> List[dict]:
    """
    Apply a delta to a record set, producing the updated state.

    Uses merge strategies for modified records if schema is provided.
    """
    index = {r.get(key): r for r in records if r.get(key) is not None}

    # Apply removals
    removed_set = set(delta.removed)
    for k in removed_set:
        index.pop(k, None)
        # Also try numeric key
        try:
            index.pop(int(k), None)
        except (ValueError, TypeError):
            pass

    # Apply modifications
    for r in delta.modified:
        k = r.get(key)
        if k in index and schema:
            old = index[k]
            all_cols = list(dict.fromkeys(list(old.keys()) + list(r.keys())))
            merged = {}
            for col in all_cols:
                va = old.get(col)
                vb = r.get(col)
                if va is None:
                    merged[col] = vb
                elif vb is None:
                    merged[col] = va
                elif va == vb:
                    merged[col] = va
                else:
                    strategy = schema.strategy_for(col)
                    merged[col] = strategy.resolve(va, vb)
            index[k] = merged
        else:
            index[k] = r

    # Apply additions
    for r in delta.added:
        k = r.get(key)
        if k is not None:
            index[k] = r

    return list(index.values())

def compose_deltas(*deltas: Delta, key: Optional[str] = None) -> Delta:
    """
    Compose multiple deltas into one: delta(1→2) ⊔ delta(2→3) == delta(1→3).

    This is the key composability property of δ-CRDTs.
    The result contains the net effect of all deltas applied in order.

    Args:
        *deltas: Delta objects to compose. Also accepts a single list/tuple of Deltas.
        key: Optional key field name for identity tracking. When provided,
             records are tracked by their key field value instead of content hash.
             This prevents duplicates when a record is added then modified.
    """
    # DEF-007: Handle case where a single list/tuple is passed instead of *args
    if len(deltas) == 1 and isinstance(deltas[0], (list, tuple)):
        deltas = tuple(deltas[0])

    if not deltas:
        return Delta()

    # Track the net effect
    net_added: Dict[str, dict] = {}  # identity → record
    net_modified: Dict[str, dict] = {}  # identity → record
    net_removed: Set[str] = set()

    def _record_id(record: dict) -> str:
        """Get a stable identity for a record."""
        if key and key in record:
            return str(record[key])
        return hashlib.sha256(str(sorted(record.items())).encode()).hexdigest()[:16]

    for delta in deltas:
        # Process removals first
        for k in delta.removed:
            net_added.pop(k, None)
            net_modified.pop(k, None)
            net_removed.add(k)

        # Process modifications
        for r in delta.modified:
            rid = _record_id(r)
            if rid in net_removed:
                # Was removed then modified — it's back, treat as add
                net_removed.discard(rid)
                net_added[rid] = r
            elif rid in net_added:
                # Was added, now modified — update the add
                net_added[rid] = r
            else:
                net_modified[rid] = r

        # Process additions
        for r in delta.added:
            rid = _record_id(r)
            net_removed.discard(rid)
            # If already in modified, promote to add with new content
            net_modified.pop(rid, None)
            net_added[rid] = r

    max_version = max((d.version for d in deltas), default=0)
    return Delta(
        added=list(net_added.values()),
        modified=list(net_modified.values()),
        removed=list(net_removed),
        version=max_version,
    )

class DeltaStore:
    """
    Stateful delta tracker — remembers the last known state and computes
    deltas automatically on each ingest.

    Usage:
        store = DeltaStore(key="id", node_id="node-1")
        store.ingest(initial_records)  # First ingest, no delta

        # Later...
        delta = store.ingest(updated_records)
        ship_to_remote(delta)  # Only send changes
    """

    def __init__(self, key: str, node_id: str = "default"):
        """Initialize a DeltaStore.

        Args:
            key: The field name used as the primary key for record identity.
            node_id: Identifier of this node, embedded in produced deltas.
        """
        self.key = key
        self.node_id = node_id
        self._version = 0
        self._current: Dict[Any, dict] = {}
        self._hashes: Dict[Any, str] = {}

    def ingest(self, records: List[dict]) -> Optional[Delta]:
        """
        Ingest new state and return the delta from previous state.
        First call returns None (no previous state to diff against).
        """
        new_index = {}
        new_hashes = {}
        for r in records:
            k = r.get(self.key)
            if k is not None:
                new_index[k] = r
                new_hashes[k] = _record_hash(r, self.key)

        if not self._current:
            # First ingest
            self._current = new_index
            self._hashes = new_hashes
            return None

        # Compute delta
        self._version += 1
        added = []
        modified = []
        removed = []

        for k, r in new_index.items():
            if k not in self._current:
                added.append(r)
            elif new_hashes[k] != self._hashes.get(k):
                modified.append(r)

        for k in self._current:
            if k not in new_index:
                removed.append(str(k))

        # Update current state
        self._current = new_index
        self._hashes = new_hashes

        return Delta(added, modified, removed, self._version,
                     source_node=self.node_id)

    @property
    def version(self) -> int:
        """Current version counter of the store.

        Returns:
            int: Monotonically increasing version, incremented on each ingest
                that produces a delta.
        """
        return self._version

    @property
    def size(self) -> int:
        """Number of records currently held in the store.

        Returns:
            int: Count of records in the current state snapshot.
        """
        return len(self._current)

    @property
    def records(self) -> List[dict]:
        """Current state as a list of records.

        Returns:
            List[dict]: All records in the store's latest snapshot.
        """
        return list(self._current.values())

    def __repr__(self) -> str:
        """Return a summary string with key field, record count, and version."""
        return f"DeltaStore(key={self.key!r}, records={self.size}, v{self._version})"
