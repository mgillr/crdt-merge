# Distributed Sync Recipes

## Recipe 1: Gossip-Based Sync

```python
from crdt_merge.gossip import GossipState, anti_entropy

# Two nodes with local state
node_a = GossipState(node_id="west")
node_b = GossipState(node_id="east")

node_a.update("user:1", {"name": "Alice", "score": 85})
node_b.update("user:1", {"name": "Bob", "score": 90})
node_b.update("user:2", {"name": "Carol", "score": 70})

# Build compact digests (key → hash)
digest_a = node_a.digest()
digest_b = node_b.digest()

# Stateless anti-entropy: figure out what differs
diff = anti_entropy(digest_a, digest_b)
# diff = {"missing_local": [...], "missing_remote": [...], "different": [...]}

# Node A pulls entries it is missing or that differ
keys_a_needs = set(diff["missing_local"] + diff["different"])
entries_for_a = node_b.get_entries(keys_a_needs)
node_a.apply_entries(entries_for_a)

# Node B pulls entries it is missing or that differ
keys_b_needs = set(diff["missing_remote"] + diff["different"])
entries_for_b = node_a.get_entries(keys_b_needs)
node_b.apply_entries(entries_for_b)

# Both nodes now see the same keys
assert node_a.digest() == node_b.digest()
```

## Recipe 2: Merkle Tree Diff

```python
from crdt_merge.merkle import MerkleTree, merkle_diff

records_a = [
    {"id": "key1", "value": "val1"},
    {"id": "key2", "value": "val2"},
]
records_b = [
    {"id": "key1", "value": "val1"},
    {"id": "key3", "value": "val3"},
]

tree_a = MerkleTree.from_records(records_a, key="id")
tree_b = MerkleTree.from_records(records_b, key="id")

diff = merkle_diff(tree_a, tree_b)
# diff.only_in_left  = {"key2"}  — keys only in tree_a
# diff.only_in_right = {"key3"}  — keys only in tree_b
# diff.common_different = set()  — keys in both with different content
```

## Recipe 3: Delta Compression

```python
from crdt_merge.delta import DeltaStore, compute_delta, apply_delta

# --- Stateful tracking with DeltaStore ---
store = DeltaStore(key="id", node_id="node-1")

# First ingest: establishes baseline (returns None)
initial = [
    {"id": "user:1", "score": 80},
    {"id": "user:2", "score": 60},
]
store.ingest(initial)

# Second ingest: returns only what changed
updated = [
    {"id": "user:1", "score": 90},   # modified
    {"id": "user:2", "score": 60},   # unchanged
    {"id": "user:3", "score": 75},   # added
]
delta = store.ingest(updated)
# delta.added    = [{"id": "user:3", "score": 75}]
# delta.modified = [{"id": "user:1", "score": 90}]
# delta.removed  = []

# --- One-shot diff with compute_delta / apply_delta ---
old_state = [{"id": "a", "val": 1}, {"id": "b", "val": 2}]
new_state = [{"id": "a", "val": 1}, {"id": "c", "val": 3}]

d = compute_delta(old_state, new_state, key="id")
rebuilt = apply_delta(old_state, d, key="id")
# rebuilt contains "a" (unchanged) and "c" (added); "b" is removed
```
