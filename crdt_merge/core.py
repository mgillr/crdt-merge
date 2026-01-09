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
        self._counts: Dict[str, int] = {}
        if node_id and initial > 0:
            self._counts[node_id] = initial

    @property
    def value(self) -> int:
        return sum(self._counts.values())

    def increment(self, node_id: str, amount: int = 1) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"GCounter increment amount must be int, got {type(amount).__name__}")
        if amount < 0:
            raise ValueError("GCounter only supports non-negative increments")
        self._counts[node_id] = self._counts.get(node_id, 0) + amount

    def merge(self, other: GCounter) -> GCounter:
        result = GCounter()
        all_keys = set(self._counts) | set(other._counts)
        for k in all_keys:
            result._counts[k] = max(self._counts.get(k, 0), other._counts.get(k, 0))
        return result

    def to_dict(self) -> dict:
        return {"type": "g_counter", "counts": dict(self._counts)}

    @classmethod
    def from_dict(cls, d: dict) -> GCounter:
        c = cls()
        c._counts = dict(d.get("counts", {}))
        return c

    def __repr__(self):
        return f"GCounter(value={self.value}, nodes={len(self._counts)})"

class PNCounter:
    """Positive-Negative counter — supports both increment and decrement.
    
    Internally two G-Counters: one for increments, one for decrements.
    Perfect for: stock levels, balance tracking, bidirectional counters.
    """
    __slots__ = ('_pos', '_neg')

    def __init__(self):
        self._pos = GCounter()
        self._neg = GCounter()

    @property
    def value(self) -> int:
        return self._pos.value - self._neg.value

    def increment(self, node_id: str, amount: int = 1) -> None:
        self._pos.increment(node_id, amount)

    def decrement(self, node_id: str, amount: int = 1) -> None:
        self._neg.increment(node_id, amount)

    def merge(self, other: PNCounter) -> PNCounter:
        result = PNCounter()
        result._pos = self._pos.merge(other._pos)
        result._neg = self._neg.merge(other._neg)
        return result

    def to_dict(self) -> dict:
        return {"type": "pn_counter", "pos": self._pos.to_dict(), "neg": self._neg.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> PNCounter:
        c = cls()
        c._pos = GCounter.from_dict(d["pos"])
        c._neg = GCounter.from_dict(d["neg"])
        return c

    def __repr__(self):
        return f"PNCounter(value={self.value})"

class LWWRegister:
    """Last-Writer-Wins Register — stores a single value, latest timestamp wins.
    
    Perfect for: single-cell updates (name, email, status), any scalar field.
    """
    __slots__ = ('_value', '_timestamp', '_node_id')

    def __init__(self, value: Any = None, timestamp: Optional[float] = None, node_id: str = ""):
        self._value = value
        self._timestamp = timestamp or 0.0
        self._node_id = node_id

    @property
    def value(self) -> Any:
        return self._value

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def set(self, value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._value = value
        self._timestamp = ts
        self._node_id = node_id

    def merge(self, other: LWWRegister) -> LWWRegister:
        if other._timestamp > self._timestamp:
            return LWWRegister(other._value, other._timestamp, other._node_id)
        elif other._timestamp == self._timestamp:
            # Tie-break on node_id for determinism
            if other._node_id > self._node_id:
                return LWWRegister(other._value, other._timestamp, other._node_id)
        return LWWRegister(self._value, self._timestamp, self._node_id)

    def to_dict(self) -> dict:
        return {"type": "lww_register", "value": self._value, "timestamp": self._timestamp, "node_id": self._node_id}

    @classmethod
    def from_dict(cls, d: dict) -> LWWRegister:
        return cls(d["value"], d["timestamp"], d.get("node_id", ""))

    def __repr__(self):
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
        # element -> set of unique tags
        self._elements: Dict[Hashable, Set[str]] = {}

    @property
    def value(self) -> set:
        return {e for e, tags in self._elements.items() if tags}

    def add(self, element: Hashable) -> str:
        tag = uuid.uuid4().hex[:12]
        if element not in self._elements:
            self._elements[element] = set()
        self._elements[element].add(tag)
        return tag

    def remove(self, element: Hashable) -> None:
        if element in self._elements:
            self._elements[element] = set()

    def contains(self, element: Hashable) -> bool:
        return bool(self._elements.get(element))

    def merge(self, other: ORSet) -> ORSet:
        result = ORSet()
        all_elements = set(self._elements) | set(other._elements)
        for e in all_elements:
            tags_a = self._elements.get(e, set())
            tags_b = other._elements.get(e, set())
            result._elements[e] = tags_a | tags_b
        return result

    def to_dict(self) -> dict:
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
        return f"ORSet(size={len(self.value)})"

class LWWMap:
    """Last-Writer-Wins Map — a dictionary where each key is an LWW Register.
    
    Concurrent writes to different keys: both preserved.
    Concurrent writes to same key: latest timestamp wins.
    
    Perfect for: row-level merges, metadata dicts, config objects.
    """
    __slots__ = ('_registers', '_tombstones')

    def __init__(self):
        self._registers: Dict[str, LWWRegister] = {}
        self._tombstones: Dict[str, float] = {}  # key -> deletion timestamp

    def set(self, key: str, value: Any, timestamp: Optional[float] = None, node_id: str = "") -> None:
        ts = timestamp if timestamp is not None else time.time()
        if key not in self._registers:
            self._registers[key] = LWWRegister()
        self._registers[key].set(value, ts, node_id)
        # Remove tombstone if this write is newer
        if key in self._tombstones and ts > self._tombstones[key]:
            del self._tombstones[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._tombstones:
            return default
        reg = self._registers.get(key)
        return reg.value if reg else default

    def delete(self, key: str, timestamp: Optional[float] = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._tombstones[key] = ts

    @property
    def value(self) -> dict:
        result = {}
        for k, reg in self._registers.items():
            if k not in self._tombstones or reg.timestamp > self._tombstones[k]:
                result[k] = reg.value
        return result

    def merge(self, other: LWWMap) -> LWWMap:
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
        return {
            "type": "lww_map",
            "registers": {k: v.to_dict() for k, v in self._registers.items()},
            "tombstones": dict(self._tombstones)
        }

    @classmethod
    def from_dict(cls, d: dict) -> LWWMap:
        m = cls()
        for k, v in d.get("registers", {}).items():
            m._registers[k] = LWWRegister.from_dict(v)
        m._tombstones = dict(d.get("tombstones", {}))
        return m

    def __repr__(self):
        return f"LWWMap(keys={len(self.value)})"
