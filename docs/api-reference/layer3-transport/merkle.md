# merkle

> Layer 3 — Sync & Transport
> Source: `crdt_merge/merkle.py`  
> LOC: 421 (AST-verified)

## Overview
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

## Classes

### `MerkleNode`
`@dataclass`  


A single node in the Merkle tree.

Leaf nodes have ``children=None``; internal nodes have a list of child
:class:`MerkleNode` instances.  Every node stores the key range it
covers and the number of records in its subtree.

#### Properties

##### `is_leaf: bool`
Return ``True`` if this is a leaf node.

#### Methods

##### `to_dict(self) -> dict`

Serialise this node (and children) to a plain dict.

##### `@classmethod from_dict(cls, d: dict) -> MerkleNode`
Decorators: `@classmethod`

Deserialise from a plain dict.

---

### `MerkleTree`

Merkle tree over a keyed record set.

Records are indexed by an arbitrary string key.  The tree is rebuilt
lazily whenever the underlying records change (insert / delete).

**CRDT contract** — implements ``merge()``, ``to_dict()``, and
``from_dict()`` so it can participate in the ``crdt-merge`` ecosystem.

#### Constructor
```python
__init__(self, branching_factor: int = 16) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `branching_factor` | `int` | `16` | — |

#### Properties

##### `root_hash: str`
Root hash — if two trees share this, their datasets are identical.

##### `root: Optional[MerkleNode]`
The root :class:`MerkleNode`, or ``None`` for empty trees.

##### `size: int`
Number of records in the tree.

##### `branching_factor: int`
Maximum children per internal node.

##### `height: int`
Tree height (0 for empty, 1 for single leaf, etc.).

#### Methods

##### `@classmethod from_records(cls, records: List[dict], key: str, branching_factor: int = 16) -> MerkleTree`
Decorators: `@classmethod`

Build a tree from a list of record dicts.

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

##### `@staticmethod _hash_record(record: dict, key: str) -> str`
Decorators: `@staticmethod`

Deterministic SHA-256 of a record's *content* (excluding key).

##### `@staticmethod _hash_children(children_hashes: List[str]) -> str`
Decorators: `@staticmethod`

Hash a sequence of child hashes into a parent hash.

##### `_rebuild(self) -> None`

(Re)build the tree structure from ``self._records``.

##### `_ensure_built(self) -> None`

Lazily rebuild if dirty.

##### `insert(self, key: str, record: dict) -> None`

Insert or update a record.  Marks tree as dirty for lazy rebuild.

Parameters
----------
key:
    The record key (will be stringified).
record:
    Full record dict.

##### `delete(self, key: str) -> bool`

Remove a record.  Returns ``True`` if it existed.

Parameters
----------
key:
    The record key (will be stringified).

##### `contains(self, key: str) -> bool`

Check whether *key* is present.

##### `get_hash(self, key: str) -> Optional[str]`

Return the content hash for *key*, or ``None`` if missing.

##### `get_record(self, key: str) -> Optional[dict]`

Return the full record for *key*, or ``None``.

##### `keys(self) -> List[str]`

Return sorted list of all keys.

##### `merge(self, other: MerkleTree) -> MerkleTree`

Merge two trees.  Returns a **new** instance.

For keys present in both trees the version with the *higher*
content hash wins — this is arbitrary but deterministic, making
the merge commutative, associative, and idempotent.

##### `to_dict(self) -> dict`

Serialise to a plain dict (the CRDT trinity).

##### `@classmethod from_dict(cls, d: dict) -> MerkleTree`
Decorators: `@classmethod`

Deserialise from a plain dict (the CRDT trinity).

##### `__eq__(self, other: object) -> bool`

##### `__ne__(self, other: object) -> bool`

##### `__repr__(self) -> str`

##### `__len__(self) -> int`

##### `__contains__(self, key: str) -> bool`

---

### `MerkleDiff`
`@dataclass`  


Result of comparing two Merkle trees.

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

#### Properties

##### `is_identical: bool`
``True`` when the two trees are identical.

##### `num_differences: int`
Total number of differing keys.

#### Methods

##### `to_dict(self) -> dict`

Serialise to a plain dict.

##### `__repr__(self) -> str`

---

## Functions

### `merkle_diff(tree_a: MerkleTree, tree_b: MerkleTree) -> MerkleDiff`

Efficiently diff two Merkle trees.

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

| Parameter | Type | Default |
|-----------|------|---------|
| `tree_a` | `MerkleTree` | `—` |
| `tree_b` | `MerkleTree` | `—` |

### `compare_datasets(records_a: List[dict], records_b: List[dict], key: str = 'id', branching_factor: int = 16) -> MerkleDiff`

Build two Merkle trees and diff them in one call.

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

| Parameter | Type | Default |
|-----------|------|---------|
| `records_a` | `List[dict]` | `—` |
| `records_b` | `List[dict]` | `—` |
| `key` | `str` | `'id'` |
| `branching_factor` | `int` | `16` |

## Constants

| Name | Type | Value |
|------|------|-------|
| `_EMPTY_HASH` | `str` | `hashlib.sha256(b'empty').hexdigest()` |

## Analysis Notes

Approved by: Auditor (Team 1), Cross-validated by Teams 2–4  
Last reviewed: 2026-03-31
