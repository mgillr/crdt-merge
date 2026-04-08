# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
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
Core CRDT primitives — mathematically proven conflict-free replicated data types.

Every type here satisfies the CRDT convergence theorem:
  - Commutative:  merge(A, B) == merge(B, A)
  - Associative:  merge(merge(A, B), C) == merge(A, merge(B, C))
  - Idempotent:   merge(A, A) == A

This means ANY number of replicas can merge in ANY order and ALWAYS converge
to the same correct state — no coordination, no locks, no conflicts.
"""

from __future__ import annotations
import copy
import time
import uuid
from typing import Any, Dict, Hashable, Optional, Set, Tuple

__all__ = ["GCounter", "PNCounter", "LWWRegister", "ORSet", "LWWMap"]

class GCounter:
    """Grow-only counter. Each node has its own slot; value = sum of all slots.
    
    Perfect for: page views, download counts, event counters — anything that only goes up.
    """
    __slots__ = ('_counts',)

    def __init__(self, node_id: Optional[str] = None, initial: int = 0):
        """Initialize a new grow-only counter.

        Args:
            node_id: Optional node identifier. If provided together with a
                positive ``initial`` value, the counter is seeded with that
                amount for the given node.
            initial: Starting count for ``node_id``. Only applied when
                ``node_id`` is truthy and ``initial`` is greater than zero.
        """
        self._counts: Dict[str, int] = {}
        if node_id and initial > 0:
            self._counts[node_id] = initial

    @property
    def value(self) -> int:
        """Return the aggregate counter value (sum of all per-node slots).

        Returns:
            The total count across every node that has incremented this
            counter.
        """
        return sum(self._counts.values())

    def increment(self, node_id: str, amount: int = 1) -> None:
        """Increment the counter for a specific node.

        Args:
            node_id: Identifier of the node performing the increment.
            amount: Non-negative integer to add. Defaults to 1.

        Raises:
            TypeError: If ``amount`` is not an ``int`` (or is a ``bool``).
            ValueError: If ``amount`` is negative.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"GCounter increment amount must be int, got {type(amount).__name__}")
        if amount < 0:
            raise ValueError("GCounter only supports non-negative increments")
        self._counts[node_id] = self._counts.get(node_id, 0) + amount

    def merge(self, other: GCounter) -> GCounter:
        """Merge this counter with another, returning a new GCounter.

        For each node slot the maximum of the two values is taken, ensuring
        the merge is commutative, associative, and idempotent.

        Args:
            other: The remote GCounter state to merge with.

        Returns:
            A new ``GCounter`` representing the merged state.
        """
        result = GCounter()
        all_keys = set(self._counts) | set(other._counts)
        for k in all_keys:
            result._counts[k] = max(self._counts.get(k, 0), other._counts.get(k, 0))
        return result

    def to_dict(self) -> dict:
        """Serialize the counter to a plain dictionary.

        Returns:
            A dict with keys ``"type"`` (``"g_counter"``) and ``"counts"``
            (a mapping of node IDs to their counts).
        """
        return {"type": "g_counter", "counts": dict(self._counts)}

    @classmethod
    def from_dict(cls, d: dict) -> GCounter:
        """Deserialize a GCounter from a dictionary.

        Args:
            d: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A reconstructed ``GCounter`` instance.
        """
        c = cls()
        c._counts = dict(d.get("counts", {}))
        return c

    def __repr__(self):
        """Return a human-readable representation showing value and node count."""
        return f"GCounter(value={self.value}, nodes={len(self._counts)})"

class PNCounter:
    """Positive-Negative counter — supports both increment and decrement.
    
    Internally two G-Counters: one for increments, one for decrements.
    Perfect for: stock levels, balance tracking, bidirectional counters.
    """
    __slots__ = ('_pos', '_neg')

    def __init__(self):
        """Initialize a PNCounter with zeroed positive and negative GCounters."""
        self._pos = GCounter()
        self._neg = GCounter()

    @property
    def value(self) -> int:
        """Return the net counter value (positive total minus negative total).

        Returns:
            The difference between all increments and all decrements.
        """
        return self._pos.value - self._neg.value

    def increment(self, node_id: str, amount: int = 1) -> None:
        """Increment the counter for a specific node.

        Delegates to the internal positive ``GCounter``.

        Args:
            node_id: Identifier of the node performing the increment.
            amount: Non-negative integer to add. Defaults to 1.

        Raises:
            TypeError: If ``amount`` is not an ``int``.
            ValueError: If ``amount`` is negative.
        """
        self._pos.increment(node_id, amount)

    def decrement(self, node_id: str, amount: int = 1) -> None:
        """Decrement the counter for a specific node.

        Delegates to the internal negative ``GCounter``.

        Args:
            node_id: Identifier of the node performing the decrement.
            amount: Non-negative integer to subtract. Defaults to 1.

        Raises:
            TypeError: If ``amount`` is not an ``int``.
            ValueError: If ``amount`` is negative.
        """
        self._neg.increment(node_id, amount)

    def merge(self, other: PNCounter) -> PNCounter:
        """Merge this counter with another, returning a new PNCounter.

        Both the positive and negative internal GCounters are merged
        independently, preserving commutativity, associativity, and
        idempotency.

        Args:
            other: The remote PNCounter state to merge with.

        Returns:
            A new ``PNCounter`` representing the merged state.
        """
        result = PNCounter()
        result._pos = self._pos.merge(other._pos)
        result._neg = self._neg.merge(other._neg)
        return result

    def to_dict(self) -> dict:
        """Serialize the counter to a plain dictionary.

        Returns:
            A dict with keys ``"type"`` (``"pn_counter"``), ``"pos"``, and
            ``"neg"`` (each a serialized GCounter).
        """
        return {"type": "pn_counter", "pos": self._pos.to_dict(), "neg": self._neg.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> PNCounter:
        """Deserialize a PNCounter from a dictionary.

        Args:
            d: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A reconstructed ``PNCounter`` instance.
        """
        c = cls()
        c._pos = GCounter.from_dict(d["pos"])
        c._neg = GCounter.from_dict(d["neg"])
        return c

    def __repr__(self):
        """Return a human-readable representation showing the net value."""
        return f"PNCounter(value={self.value})"

class LWWRegister:
    """Last-Writer-Wins Register — stores a single value, latest timestamp wins.
    
    Perfect for: single-cell updates (name, email, status), any scalar field.

    Tie-breaking behavior:
        When two updates have identical timestamps, the node_id is used as a
        deterministic tie-breaker via **lexicographic** (Python string ``>``)
        comparison.  This means ``"node9" > "node10"`` is True — lexicographic
        ordering does NOT match numeric ordering.  This is intentional: any
        total order that is deterministic across all replicas satisfies the
        CRDT convergence requirement; lexicographic comparison is the simplest
        such order for arbitrary string identifiers.
    """
    __slots__ = ('_value', '_timestamp', '_node_id')

    def __init__(self, value: Any = None, timestamp: Optional[float] = None, node_id: str = ""):
        """Initialize an LWW register.

        Args:
            value: The initial value to store. Defaults to ``None``.
            timestamp: POSIX timestamp of the write. Defaults to ``0.0``
                when ``None`` is passed.
            node_id: Identifier of the authoring node, used for
                deterministic tie-breaking when timestamps are equal.
        """
        self._value = value
        self._timestamp = timestamp or 0.0
        self._node_id = node_id

    @property
    def value(self) -> Any:
        """Return the currently stored value.

        Returns:
            The value held by this register.
        """
        return self._value

    @property
    def timestamp(self) -> float:
        """Return the POSIX timestamp of the last write.

        Returns:
            The timestamp associated with the current value.
        """
        return self._timestamp

    def set(self, value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None:
        """Overwrite the register with a new value.

        Args:
            value: The new value to store.
            timestamp: POSIX timestamp for the write. If ``None``, the
                current wall-clock time (``time.time()``) is used.
            node_id: Identifier of the authoring node, used for
                tie-breaking during merge.
        """
        ts = timestamp if timestamp is not None else time.time()
        self._value = value
        self._timestamp = ts
        self._node_id = node_id

    def merge(self, other: LWWRegister) -> LWWRegister:
        """Merge this register with another, returning a new LWWRegister.

        The register with the higher timestamp wins. When timestamps are
        equal, the ``node_id`` with the greater lexicographic value is
        chosen as a deterministic tie-breaker — ensuring the merge is
        commutative, associative, and idempotent.

        Note:
            Lexicographic comparison means ``"node9" > "node10"`` is
            ``True``. Any consistent total order satisfies CRDT
            convergence; lexicographic ordering is the simplest for
            arbitrary string identifiers.

        Args:
            other: The remote LWWRegister state to merge with.

        Returns:
            A new ``LWWRegister`` containing the winning value.
        """
        if other._timestamp > self._timestamp:
            return LWWRegister(other._value, other._timestamp, other._node_id)
        elif other._timestamp == self._timestamp:
            # Tie-break on node_id using lexicographic (string) comparison.
            # Lexicographic order is deterministic across all replicas, which
            # is the only requirement for CRDT convergence.  Note that
            # "node9" > "node10" is True under this ordering.
            if other._node_id > self._node_id:
                return LWWRegister(other._value, other._timestamp, other._node_id)
        return LWWRegister(self._value, self._timestamp, self._node_id)

    def to_dict(self) -> dict:
        """Serialize the register to a plain dictionary.

        Returns:
            A dict with keys ``"type"`` (``"lww_register"``), ``"value"``,
            ``"timestamp"``, and ``"node_id"``.
        """
        return {"type": "lww_register", "value": self._value, "timestamp": self._timestamp, "node_id": self._node_id}

    @classmethod
    def from_dict(cls, d: dict) -> LWWRegister:
        """Deserialize an LWWRegister from a dictionary.

        Args:
            d: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A reconstructed ``LWWRegister`` instance.
        """
        return cls(d["value"], d["timestamp"], d.get("node_id", ""))

    def __repr__(self):
        """Return a human-readable representation showing value and timestamp."""
        return f"LWWRegister(value={self._value!r}, ts={self._timestamp})"

class ORSet:
    """Observed-Remove Set — add and remove elements without conflicts.
    
    Each element is tagged with a unique ID on add. Remove kills specific tags,
    so concurrent add+remove of the same element resolves correctly (add wins
    over concurrent remove — the "add-wins" semantics).
    
    Perfect for: membership lists, tag sets, deduplication sets.
    """
    __slots__ = ('_elements',)

    def __init__(self):
        """Initialize an empty observed-remove set."""
        # element -> set of unique tags
        self._elements: Dict[Hashable, Set[str]] = {}

    @property
    def value(self) -> set:
        """Return the set of currently live elements.

        An element is considered live if it has at least one associated tag.

        Returns:
            A plain ``set`` of elements that have not been fully removed.
        """
        return {e for e, tags in self._elements.items() if tags}

    def add(self, element: Hashable) -> str:
        """Add an element to the set, tagging it with a unique identifier.

        If the element already exists, a new tag is added alongside any
        existing tags, ensuring that concurrent removes of older tags do
        not accidentally delete this addition (add-wins semantics).

        Args:
            element: A hashable value to insert into the set.

        Returns:
            The unique 12-character hex tag assigned to this addition.
        """
        tag = uuid.uuid4().hex[:12]
        if element not in self._elements:
            self._elements[element] = set()
        self._elements[element].add(tag)
        return tag

    def remove(self, element: Hashable) -> None:
        """Remove an element by clearing all of its associated tags.

        After this call the element will no longer appear in :attr:`value`.
        However, a concurrent ``add`` on another replica may re-introduce
        the element upon merge (add-wins semantics).

        Args:
            element: The element to remove. No error is raised if the
                element is absent.
        """
        if element in self._elements:
            self._elements[element] = set()

    def remove_tag(self, element: Hashable, tag: str) -> None:
        """Remove a specific tag for *element*, keeping other tags intact.

        Unlike :meth:`remove` (which clears ALL tags for the element), this
        method allows selective tag removal.  The element remains in the set
        as long as it still has at least one tag.

        Args:
            element: The element whose tag should be removed.
            tag: The specific unique tag to discard.

        Raises:
            KeyError: If *element* is not present in the internal map.
        """
        if element not in self._elements:
            raise KeyError(f"{element!r} not found in ORSet")
        self._elements[element].discard(tag)

    def contains(self, element: Hashable) -> bool:
        """Check whether an element is currently in the set.

        An element is considered present if it has at least one live tag.

        Args:
            element: The hashable value to look up.

        Returns:
            ``True`` if the element has at least one tag, ``False``
            otherwise.
        """
        return bool(self._elements.get(element))

    def merge(self, other: ORSet) -> ORSet:
        """Merge this set with another, returning a new ORSet.

        Tags for each element are combined via set union so that an
        element is live in the result if it is live in *either* replica.
        This guarantees add-wins semantics and is commutative, associative,
        and idempotent.

        Args:
            other: The remote ORSet state to merge with.

        Returns:
            A new ``ORSet`` representing the merged state.
        """
        result = ORSet()
        all_elements = set(self._elements) | set(other._elements)
        for e in all_elements:
            tags_a = self._elements.get(e, set())
            tags_b = other._elements.get(e, set())
            result._elements[e] = tags_a | tags_b
        return result

    def to_dict(self) -> dict:
        """Serialize the set to a plain dictionary.

        Non-string element keys are converted to strings and their original
        type is recorded in an ``"element_types"`` map so that
        :meth:`from_dict` can restore the correct Python type.

        Returns:
            A dict with key ``"type"`` (``"or_set"``), ``"elements"``
            (mapping of stringified keys to tag lists), and optionally
            ``"element_types"`` for non-string keys.
        """
        import json
        elements = {}
        type_map = {}
        for k, v in self._elements.items():
            str_key = str(k)
            elements[str_key] = list(v)
            # Preserve original type info for non-string keys
            if not isinstance(k, str):
                type_map[str_key] = type(k).__name__
        result = {"type": "or_set", "elements": elements}
        if type_map:
            result["element_types"] = type_map
        return result

    @classmethod
    def from_dict(cls, d: dict) -> ORSet:
        """Deserialize an ORSet from a dictionary.

        Restores non-string element keys (``int``, ``float``, ``bool``)
        using the ``"element_types"`` map produced by :meth:`to_dict`.

        Args:
            d: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A reconstructed ``ORSet`` instance.
        """
        s = cls()
        type_map = d.get("element_types", {})
        _type_coerce = {"int": int, "float": float, "bool": lambda x: x.lower() == "true"}
        for k, tags in d.get("elements", {}).items():
            if k in type_map and type_map[k] in _type_coerce:
                restored_key = _type_coerce[type_map[k]](k)
            else:
                restored_key = k
            s._elements[restored_key] = set(tags)
        return s

    def __repr__(self):
        """Return a human-readable representation showing the number of live elements."""
        return f"ORSet(size={len(self.value)})"

class LWWMap:
    """Last-Writer-Wins Map — a dictionary where each key is an LWW Register.
    
    Concurrent writes to different keys: both preserved.
    Concurrent writes to same key: latest timestamp wins.
    
    Perfect for: row-level merges, metadata dicts, config objects.
    """
    __slots__ = ('_registers', '_tombstones')

    def __init__(self):
        """Initialize an empty LWW map with no registers or tombstones."""
        self._registers: Dict[str, LWWRegister] = {}
        self._tombstones: Dict[str, float] = {}  # key -> deletion timestamp

    def set(self, key: str, value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None:
        """Set a key to a value, creating or updating the underlying LWW register.

        If the key was previously deleted (tombstoned) and this write's
        timestamp is newer than the tombstone, the tombstone is removed so
        the key becomes visible again.

        Args:
            key: The map key to write.
            value: The value to associate with ``key``.
            timestamp: POSIX timestamp for the write. If ``None``, the
                current wall-clock time (``time.time()``) is used.
            node_id: Identifier of the authoring node, used for
                tie-breaking when timestamps are equal during merge.
        """
        ts = timestamp if timestamp is not None else time.time()
        if key not in self._registers:
            self._registers[key] = LWWRegister()
        self._registers[key].set(value, ts, node_id)
        # Remove tombstone if this write is newer
        if key in self._tombstones and ts > self._tombstones[key]:
            del self._tombstones[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value for a key.

        Returns ``default`` if the key has been deleted (tombstoned) or was
        never set.

        Args:
            key: The map key to look up.
            default: Value to return when the key is missing or deleted.
                Defaults to ``None``.

        Returns:
            The current value for ``key``, or ``default`` if absent or
            tombstoned.
        """
        if key in self._tombstones:
            return default
        reg = self._registers.get(key)
        return reg.value if reg else default

    def delete(self, key: str, timestamp: Optional[float] = None) -> None:
        """Mark a key as deleted by recording a tombstone timestamp.

        The key will be hidden from :attr:`value` and :meth:`get` as long
        as the tombstone timestamp is ≥ the register's timestamp. A
        subsequent :meth:`set` with a newer timestamp will revive the key.

        Args:
            key: The map key to delete.
            timestamp: POSIX timestamp for the deletion. If ``None``, the
                current wall-clock time (``time.time()``) is used.
        """
        ts = timestamp if timestamp is not None else time.time()
        self._tombstones[key] = ts

    @property
    def value(self) -> dict:
        """Return a snapshot of all live (non-tombstoned) key-value pairs.

        A key is included only if its register's timestamp is strictly
        greater than any tombstone timestamp for that key.

        Returns:
            A plain ``dict`` mapping keys to their current values.
        """
        result = {}
        for k, reg in self._registers.items():
            if k not in self._tombstones or reg.timestamp > self._tombstones[k]:
                result[k] = reg.value
        return result

    def merge(self, other: LWWMap) -> LWWMap:
        """Merge this map with another, returning a new LWWMap.

        Registers for each key are merged via :meth:`LWWRegister.merge`
        (latest timestamp wins; lexicographic ``node_id`` tie-breaking).
        Tombstones are merged by taking the latest deletion timestamp per
        key. The result is commutative, associative, and idempotent.

        Args:
            other: The remote LWWMap state to merge with.

        Returns:
            A new ``LWWMap`` representing the merged state.
        """
        result = LWWMap()
        all_keys = set(self._registers) | set(other._registers)
        for k in all_keys:
            a = self._registers.get(k)
            b = other._registers.get(k)
            if a and b:
                result._registers[k] = a.merge(b)
            elif a:
                result._registers[k] = LWWRegister(a.value, a.timestamp, a._node_id)
            else:
                result._registers[k] = LWWRegister(b.value, b.timestamp, b._node_id)
        # Merge tombstones — latest deletion wins
        for k in set(self._tombstones) | set(other._tombstones):
            ts_a = self._tombstones.get(k, 0)
            ts_b = other._tombstones.get(k, 0)
            max_ts = max(ts_a, ts_b)
            if max_ts > 0:
                result._tombstones[k] = max_ts
        return result

    def to_dict(self) -> dict:
        """Serialize the map to a plain dictionary.

        Returns:
            A dict with keys ``"type"`` (``"lww_map"``), ``"registers"``
            (each value a serialized LWWRegister), and ``"tombstones"``
            (mapping of keys to deletion timestamps).
        """
        return {
            "type": "lww_map",
            "registers": {k: v.to_dict() for k, v in self._registers.items()},
            "tombstones": dict(self._tombstones)
        }

    @classmethod
    def from_dict(cls, d: dict) -> LWWMap:
        """Deserialize an LWWMap from a dictionary.

        Args:
            d: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A reconstructed ``LWWMap`` instance.
        """
        m = cls()
        for k, v in d.get("registers", {}).items():
            m._registers[k] = LWWRegister.from_dict(v)
        m._tombstones = dict(d.get("tombstones", {}))
        return m

    def __repr__(self):
        """Return a human-readable representation showing the number of live keys."""
        return f"LWWMap(keys={len(self.value)})"
