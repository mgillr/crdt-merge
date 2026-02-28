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
Merkle Tree — content-addressable hash trees for efficient dataset synchronization.

Provides O(log n) comparison of record sets through hierarchical hashing.
Two datasets with matching root hashes are guaranteed identical. When they
differ, ``merkle_diff`` identifies exactly which keys diverge.

CRDT merge semantics: for duplicate keys the *higher* content-hash wins,
giving a deterministic, commutative, associative, and idempotent merge.

Usage::

    from crdt_merge.merkle import MerkleTree, merkle_diff

    tree_a = MerkleTree.from_records(records_a, key="id")
    tree_b = MerkleTree.from_records(records_b, key="id")

    if tree_a.root_hash != tree_b.root_hash:
        diff = merkle_diff(tree_a, tree_b)
        print(diff.only_in_left, diff.only_in_right, diff.common_different)

    merged = tree_a.merge(tree_b)  # NEW instance — originals unchanged
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

__all__ = [
    "MerkleNode",
    "MerkleTree",
    "MerkleDiff",
    "merkle_diff",
    "compare_datasets",
]

# ─── Sentinel hash for empty trees ──────────────────────────────────────────

_EMPTY_HASH: str = hashlib.sha256(b"empty").hexdigest()

# ─── MerkleNode ─────────────────────────────────────────────────────────────

@dataclass
class MerkleNode:
    """A single node in the Merkle tree.

    Leaf nodes have ``children=None``; internal nodes have a list of child
    :class:`MerkleNode` instances.  Every node stores the key range it
    covers and the number of records in its subtree.
    """

    hash: str                                    # SHA-256 hex digest
    children: Optional[List[MerkleNode]] = None  # None for leaf nodes
    key_range: Optional[Tuple[str, str]] = None  # (min_key, max_key)
    count: int = 0                               # records in subtree

    @property
    def is_leaf(self) -> bool:
        """Return ``True`` if this is a leaf node."""
        return self.children is None

    def to_dict(self) -> dict:
        """Serialise this node (and children) to a plain dict."""
        d: Dict[str, Any] = {
            "hash": self.hash,
            "count": self.count,
        }
        if self.key_range is not None:
            d["key_range"] = list(self.key_range)
        if self.children is not None:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MerkleNode:
        """Deserialise from a plain dict."""
        children = None
        if "children" in d and d["children"] is not None:
            children = [cls.from_dict(c) for c in d["children"]]
        kr = tuple(d["key_range"]) if "key_range" in d and d["key_range"] is not None else None
        return cls(
            hash=d["hash"],
            children=children,
            key_range=kr,  # type: ignore[arg-type]  # kr is Tuple[Any, ...] from tuple(), but field expects Optional[Tuple[str, str]]
            count=d.get("count", 0),
        )

# ─── MerkleTree ─────────────────────────────────────────────────────────────

class MerkleTree:
    """Merkle tree over a keyed record set.

    Records are indexed by an arbitrary string key.  The tree is rebuilt
    lazily whenever the underlying records change (insert / delete).

    **CRDT contract** — implements ``merge()``, ``to_dict()``, and
    ``from_dict()`` so it can participate in the ``crdt-merge`` ecosystem.
    """

    def __init__(self, branching_factor: int = 16) -> None:
        """Initialise a MerkleTree.

        Args:
            branching_factor (int): Number of children per internal node (default 16).
                Affects tree depth as log(n)/log(factor). Higher values = shallower
                tree, larger proofs. Lower values = deeper tree, smaller proofs.
                Default 16 balances proof size and tree depth for datasets of
                1K–10M leaves.
        """
        if branching_factor < 2:
            branching_factor = 2
        self._branching_factor: int = branching_factor
        self._records: Dict[str, str] = {}       # key → content_hash
        self._record_data: Dict[str, dict] = {}  # key → full record
        self._root: Optional[MerkleNode] = None
        self._dirty: bool = True                  # needs rebuild?

    # ── Construction ────────────────────────────────────────────────────

    @classmethod
    def from_records(
        cls,
        records: List[dict],
        key: str,
        branching_factor: int = 16,
    ) -> MerkleTree:
        """Build a tree from a list of record dicts.

        Each record must contain the field given by *key*.  The content
        hash is computed over all *other* fields.

        Parameters
        ----------
        records:
            List of dicts representing records.
        key:
            Field name used as the unique record key.
        branching_factor:
            Maximum children per internal node (default 16).
        """
        if records is None:
            records = []
        tree = cls(branching_factor)
        for record in records:
            if record is None:
                continue
            k = str(record.get(key, ""))
            tree._records[k] = cls._hash_record(record, key)
            tree._record_data[k] = dict(record)
        tree._rebuild()
        return tree

    # ── Hashing helpers ─────────────────────────────────────────────────

    @staticmethod
    def _hash_record(record: dict, key: str) -> str:
        """Deterministic SHA-256 of a record's *content* (excluding key)."""
        content = {}
        for k in sorted(record.keys()):
            if k == key:
                continue
            v = record[k]
            content[k] = v
        payload = json.dumps(content, sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _hash_children(children_hashes: List[str]) -> str:
        """Hash a sequence of child hashes into a parent hash."""
        combined = "|".join(children_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    # ── Tree build / rebuild ────────────────────────────────────────────

    def _rebuild(self) -> None:
        """(Re)build the tree structure from ``self._records``."""
        if not self._records:
            self._root = None
            self._dirty = False
            return

        sorted_keys = sorted(self._records.keys())

        # Create leaf nodes
        leaves: List[MerkleNode] = []
        for k in sorted_keys:
            leaf = MerkleNode(
                hash=self._records[k],
                children=None,
                key_range=(k, k),
                count=1,
            )
            leaves.append(leaf)

        # Build upward until we have a single root
        current_level: List[MerkleNode] = leaves
        bf = self._branching_factor

        while len(current_level) > 1:
            next_level: List[MerkleNode] = []
            num_groups = math.ceil(len(current_level) / bf)
            for g in range(num_groups):
                group = current_level[g * bf : (g + 1) * bf]
                child_hashes = [c.hash for c in group]
                parent_hash = self._hash_children(child_hashes)
                min_key = group[0].key_range[0] if group[0].key_range else ""
                max_key = group[-1].key_range[1] if group[-1].key_range else ""
                total_count = sum(c.count for c in group)
                parent = MerkleNode(
                    hash=parent_hash,
                    children=list(group),
                    key_range=(min_key, max_key),
                    count=total_count,
                )
                next_level.append(parent)
            current_level = next_level

        self._root = current_level[0]
        self._dirty = False

    def _ensure_built(self) -> None:
        """Lazily rebuild if dirty."""
        if self._dirty:
            self._rebuild()

    # ── Public rebuild API ──────────────────────────────────────────────

    @property
    def is_dirty(self) -> bool:
        """Return ``True`` if the tree needs to be rebuilt before querying.

        The tree becomes dirty after any ``insert()`` or ``delete()`` call.
        It is automatically rebuilt on the next property access (lazy build),
        but callers can check this flag to decide whether to call
        ``rebuild()`` explicitly (e.g. to amortise cost at a convenient time).
        """
        return self._dirty

    def rebuild(self) -> "MerkleTree":
        """Explicitly rebuild the tree from the current record set.

        Normally the tree is rebuilt lazily on first access after a mutation.
        Use this method to trigger the rebuild eagerly — for example, to
        amortise the cost at a predictable point in time rather than on the
        first subsequent read.

        Returns:
            ``self``, so that calls can be chained: ``tree.insert(k, r).rebuild()``.
        """
        self._rebuild()
        return self

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def root_hash(self) -> str:
        """Root hash — if two trees share this, their datasets are identical."""
        self._ensure_built()
        if self._root is not None:
            return self._root.hash
        return _EMPTY_HASH

    @property
    def root(self) -> Optional[MerkleNode]:
        """The root :class:`MerkleNode`, or ``None`` for empty trees."""
        self._ensure_built()
        return self._root

    @property
    def size(self) -> int:
        """Number of records in the tree."""
        return len(self._records)

    @property
    def branching_factor(self) -> int:
        """Maximum children per internal node."""
        return self._branching_factor

    @property
    def height(self) -> int:
        """Tree height (0 for empty, 1 for single leaf, etc.)."""
        self._ensure_built()
        if self._root is None:
            return 0
        h = 1
        node = self._root
        while node.children:
            h += 1
            node = node.children[0]
        return h

    # ── Mutation ────────────────────────────────────────────────────────

    def insert(self, key: str, record: dict) -> None:
        """Insert or update a record.  Marks tree as dirty for lazy rebuild.

        Parameters
        ----------
        key:
            The record key (will be stringified).
        record:
            Full record dict.
        """
        k = str(key)
        # Determine which field to exclude when hashing — guess "id" or use
        # the key itself if it appears in the record.
        exclude = None
        if k in (str(record.get("id", "")),):
            exclude = "id"
        else:
            # Try to find the key value in the record
            for field_name, field_val in record.items():
                if str(field_val) == k:
                    exclude = field_name
                    break
        if exclude is None:
            exclude = "id"
        self._records[k] = self._hash_record(record, exclude)
        self._record_data[k] = dict(record)
        self._dirty = True

    def delete(self, key: str) -> bool:
        """Remove a record.  Returns ``True`` if it existed.

        Parameters
        ----------
        key:
            The record key (will be stringified).
        """
        k = str(key)
        if k in self._records:
            del self._records[k]
            del self._record_data[k]
            self._dirty = True
            return True
        return False

    def contains(self, key: str) -> bool:
        """Check whether *key* is present."""
        return str(key) in self._records

    def get_hash(self, key: str) -> Optional[str]:
        """Return the content hash for *key*, or ``None`` if missing."""
        return self._records.get(str(key))

    def get_record(self, key: str) -> Optional[dict]:
        """Return the full record for *key*, or ``None``."""
        data = self._record_data.get(str(key))
        return dict(data) if data is not None else None

    def keys(self) -> List[str]:
        """Return sorted list of all keys."""
        return sorted(self._records.keys())

    # ── CRDT merge ──────────────────────────────────────────────────────

    def merge(self, other: MerkleTree) -> MerkleTree:
        """Merge two trees.  Returns a **new** instance.

        For keys present in both trees the version with the *higher*
        content hash wins — this is arbitrary but deterministic, making
        the merge commutative, associative, and idempotent.
        """
        if not isinstance(other, MerkleTree):
            raise TypeError(f"Cannot merge MerkleTree with {type(other).__name__}")

        result = MerkleTree(self._branching_factor)
        all_keys = set(self._records) | set(other._records)

        for k in all_keys:
            in_self = k in self._records
            in_other = k in other._records
            if in_self and in_other:
                # Both have it — higher hash wins for determinism
                if self._records[k] >= other._records[k]:
                    result._records[k] = self._records[k]
                    result._record_data[k] = dict(self._record_data[k])
                else:
                    result._records[k] = other._records[k]
                    result._record_data[k] = dict(other._record_data[k])
            elif in_self:
                result._records[k] = self._records[k]
                result._record_data[k] = dict(self._record_data[k])
            else:
                result._records[k] = other._records[k]
                result._record_data[k] = dict(other._record_data[k])

        result._dirty = True
        return result

    # ── Serialisation ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialise to a plain dict (the CRDT trinity)."""
        return {
            "type": "merkle_tree",
            "branching_factor": self._branching_factor,
            "records": dict(self._records),
            "record_data": {k: dict(v) for k, v in self._record_data.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> MerkleTree:
        """Deserialise from a plain dict (the CRDT trinity)."""
        if d is None:
            return cls()
        tree = cls(d.get("branching_factor", 16))
        tree._records = dict(d.get("records", {}))
        tree._record_data = {k: dict(v) for k, v in d.get("record_data", {}).items()}
        tree._dirty = True
        return tree

    # ── Dunder ──────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MerkleTree):
            return NotImplemented
        return self.root_hash == other.root_hash

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, MerkleTree):
            return NotImplemented
        return self.root_hash != other.root_hash

    def __repr__(self) -> str:
        return f"MerkleTree(size={self.size}, hash={self.root_hash[:12]}...)"

    def __len__(self) -> int:
        return self.size

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

# ─── MerkleDiff ─────────────────────────────────────────────────────────────

@dataclass
class MerkleDiff:
    """Result of comparing two Merkle trees.

    Attributes
    ----------
    differing_keys:
        All keys that differ (union of the three subsets below).
    only_in_left:
        Keys present only in the left (first) tree.
    only_in_right:
        Keys present only in the right (second) tree.
    common_different:
        Keys present in *both* trees but with different content hashes.
    comparisons_made:
        Number of hash comparisons performed (1 if roots match).
    """

    differing_keys: Set[str]
    only_in_left: Set[str]
    only_in_right: Set[str]
    common_different: Set[str]
    comparisons_made: int

    @property
    def is_identical(self) -> bool:
        """``True`` when the two trees are identical."""
        return len(self.differing_keys) == 0

    @property
    def num_differences(self) -> int:
        """Total number of differing keys."""
        return len(self.differing_keys)

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "differing_keys": sorted(self.differing_keys),
            "only_in_left": sorted(self.only_in_left),
            "only_in_right": sorted(self.only_in_right),
            "common_different": sorted(self.common_different),
            "comparisons_made": self.comparisons_made,
            "is_identical": self.is_identical,
        }

    def __repr__(self) -> str:
        return (
            f"MerkleDiff(diffs={self.num_differences}, "
            f"left_only={len(self.only_in_left)}, "
            f"right_only={len(self.only_in_right)}, "
            f"common_diff={len(self.common_different)}, "
            f"comparisons={self.comparisons_made})"
        )

# ─── Top-level diff function ────────────────────────────────────────────────

def merkle_diff(tree_a: MerkleTree, tree_b: MerkleTree) -> MerkleDiff:
    """Efficiently diff two Merkle trees.

    If the root hashes match the trees are identical and only **1**
    comparison is performed.  Otherwise all keys are compared to
    identify the exact set of differences.

    Parameters
    ----------
    tree_a:
        The "left" tree.
    tree_b:
        The "right" tree.

    Returns
    -------
    MerkleDiff
        Detailed breakdown of the differences.
    """
    if tree_a is None or tree_b is None:
        raise TypeError("Both trees must be non-None MerkleTree instances")

    comparisons: int = 1  # root comparison always happens

    # Short-circuit: root hashes match → identical
    if tree_a.root_hash == tree_b.root_hash:
        return MerkleDiff(
            differing_keys=set(),
            only_in_left=set(),
            only_in_right=set(),
            common_different=set(),
            comparisons_made=comparisons,
        )

    # Full scan — compare record-level hashes
    keys_a = set(tree_a._records.keys())
    keys_b = set(tree_b._records.keys())

    only_left = keys_a - keys_b
    only_right = keys_b - keys_a
    common = keys_a & keys_b

    common_diff: Set[str] = set()
    for k in common:
        comparisons += 1
        if tree_a._records[k] != tree_b._records[k]:
            common_diff.add(k)

    all_diff = only_left | only_right | common_diff

    return MerkleDiff(
        differing_keys=all_diff,
        only_in_left=only_left,
        only_in_right=only_right,
        common_different=common_diff,
        comparisons_made=comparisons,
    )

# ─── Convenience: build + diff in one call ──────────────────────────────────

def compare_datasets(
    records_a: List[dict],
    records_b: List[dict],
    key: str = "id",
    branching_factor: int = 16,
) -> MerkleDiff:
    """Build two Merkle trees and diff them in one call.

    Parameters
    ----------
    records_a, records_b:
        Two lists of record dicts to compare.
    key:
        Field name used as the unique record key.
    branching_factor:
        Branching factor for the trees.

    Returns
    -------
    MerkleDiff
    """
    tree_a = MerkleTree.from_records(records_a, key=key, branching_factor=branching_factor)
    tree_b = MerkleTree.from_records(records_b, key=key, branching_factor=branching_factor)
    return merkle_diff(tree_a, tree_b)
