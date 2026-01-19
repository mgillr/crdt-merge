# Merkle Trees

Merkle hash trees for efficient incremental dataset sync.

## Quick Example

```python
from crdt_merge.merkle import MerkleTree, merkle_diff
tree = MerkleTree.from_records(dataset, key="id")
diff = merkle_diff(tree_a, tree_b)
```

---

## API Reference

## `crdt_merge.merkle`

> Merkle Tree — content-addressable hash trees for efficient dataset synchronization.

**Module:** `crdt_merge.merkle`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `MerkleDiff(differing_keys: 'Set[str]', only_in_left: 'Set[str]', only_in_right: 'Set[str]', common_different: 'Set[str]', comparisons_made: 'int') -> None`

Result of comparing two Merkle trees.

**Properties:**

- `is_identical` — ``True`` when the two trees are identical.
- `num_differences` — Total number of differing keys.

**Methods:**

- `to_dict(self) -> 'dict'` — Serialise to a plain dict.

#### `MerkleNode(hash: 'str', children: 'Optional[List[MerkleNode]]' = None, key_range: 'Optional[Tuple[str, str]]' = None, count: 'int' = 0) -> None`

A single node in the Merkle tree.

**Properties:**

- `is_leaf` — Return ``True`` if this is a leaf node.

**Methods:**

- `from_dict(d: 'dict') -> 'MerkleNode'` — Deserialise from a plain dict.
- `to_dict(self) -> 'dict'` — Serialise this node (and children) to a plain dict.

#### `MerkleTree(branching_factor: 'int' = 16) -> 'None'`

Merkle tree over a keyed record set.

**Properties:**

- `branching_factor` — Maximum children per internal node.
- `height` — Tree height (0 for empty, 1 for single leaf, etc.).
- `root` — The root :class:`MerkleNode`, or ``None`` for empty trees.
- `root_hash` — Root hash — if two trees share this, their datasets are identical.
- `size` — Number of records in the tree.

**Methods:**

- `contains(self, key: 'str') -> 'bool'` — Check whether *key* is present.
- `delete(self, key: 'str') -> 'bool'` — Remove a record.  Returns ``True`` if it existed.
- `from_dict(d: 'dict') -> 'MerkleTree'` — Deserialise from a plain dict (the CRDT trinity).
- `from_records(records: 'List[dict]', key: 'str', branching_factor: 'int' = 16) -> 'MerkleTree'` — Build a tree from a list of record dicts.
- `get_hash(self, key: 'str') -> 'Optional[str]'` — Return the content hash for *key*, or ``None`` if missing.
- `get_record(self, key: 'str') -> 'Optional[dict]'` — Return the full record for *key*, or ``None``.
- `insert(self, key: 'str', record: 'dict') -> 'None'` — Insert or update a record.  Marks tree as dirty for lazy rebuild.
- `keys(self) -> 'List[str]'` — Return sorted list of all keys.
- `merge(self, other: 'MerkleTree') -> 'MerkleTree'` — Merge two trees.  Returns a **new** instance.
- `to_dict(self) -> 'dict'` — Serialise to a plain dict (the CRDT trinity).

### Functions

#### `compare_datasets(records_a: 'List[dict]', records_b: 'List[dict]', key: 'str' = 'id', branching_factor: 'int' = 16) -> 'MerkleDiff'`

Build two Merkle trees and diff them in one call.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `merkle_diff(tree_a: 'MerkleTree', tree_b: 'MerkleTree') -> 'MerkleDiff'`

Efficiently diff two Merkle trees.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
