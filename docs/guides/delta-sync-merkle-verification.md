# Delta Sync and Merkle Verification: Bandwidth-Efficient Distributed Convergence

> **Patent — UK Application No. 2607132.4, GB2608127.3**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Full-Dataset Sync Tax

Every distributed database pays it. Every replication protocol pays it. The sync tax: to verify two replicas are consistent, or to bring them back into sync after divergence, you must compare their state.

**Naive approach:** Ship full datasets. A 100GB database with 1% of records changed ships 100GB. The 99% that didn't change is wasted bandwidth.

**Smarter approach:** Delta-CRDTs (Almeida et al., 2018) — compute only the difference (the delta) and send that. A 100GB database with 1% changed sends 1GB.

**crdt-merge adds two properties that delta-CRDTs alone don't have:**

1. **Composable deltas.** `delta(v1→v2) ⊕ delta(v2→v3) == delta(v1→v3)`. You can chain deltas across hops without reconstructing intermediate states. Three-hop replication sends 3× the delta, not 3× the full dataset.

2. **Merkle verification.** After sync, prove convergence in O(1) (one root hash comparison). If not converged, locate the exact divergent keys in O(log n) without scanning all records.

Together these properties enable **bandwidth-efficient distributed sync with mathematically verifiable correctness** — a combination that no existing replication protocol provides as a composable library primitive.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Delta — the unit of change                                  │
│                                                              │
│  added:    List[record]     (new records since last version) │
│  modified: List[record]     (changed records)               │
│  removed:  List[key]        (deleted keys)                  │
│  version:  int              (monotonic)                     │
│  source_node: str                                           │
│                                                              │
│  compose_deltas(d1, d2) = net effect = additive CRDT        │
│  delta(v1→v2) ⊕ delta(v2→v3) ≡ delta(v1→v3)               │
└──────────────────────┬──────────────────────────────────────┘
                       │ apply_delta(records, delta)
                       ┌─────────────────────────────────────────────────────────────┐
│  MerkleTree — convergence verification                       │
│                                                              │
│  root_hash = SHA-256 of all (key, content_hash) pairs       │
│                                                              │
│  Same dataset → same root_hash (deterministic)              │
│  Different dataset → different root_hash (with probability  │
│                       1 - 2^-256 ≈ 1.0)                    │
│                                                              │
│  merkle_diff(tree_a, tree_b):                               │
│    identical root → done in O(1)                            │
│    different root → locate divergent keys in O(log n)        │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start: Delta Computation and Application

```python
from crdt_merge.delta import compute_delta, apply_delta, compose_deltas, DeltaStore

# Snapshot at version 1
records_v1 = [
    {"id": "A", "value": 100, "status": "active"},
    {"id": "B", "value": 200, "status": "active"},
    {"id": "C", "value": 300, "status": "active"},
]

# Snapshot at version 2: A modified, D added, C removed
records_v2 = [
    {"id": "A", "value": 150, "status": "active"},   # modified
    {"id": "B", "value": 200, "status": "active"},   # unchanged
    {"id": "D", "value": 400, "status": "new"},      # added
    # C is removed
]

# Compute the delta between versions
delta = compute_delta(records_v1, records_v2, key="id", version=2, source_node="primary")

print(f"Added: {len(delta.added)} records")    # 1 (D)
print(f"Modified: {len(delta.modified)} records")  # 1 (A)
print(f"Removed: {len(delta.removed)} keys")   # 1 (C)
print(f"Delta size: {delta.size} changes (vs {len(records_v1)} full records)")

# Apply the delta to a replica that has v1
replica_v1 = list(records_v1)  # replica's current state
replica_v2 = apply_delta(replica_v1, delta, key="id")

assert len(replica_v2) == 3  # A, B, D
assert next(r for r in replica_v2 if r["id"] == "A")["value"] == 150
assert not any(r["id"] == "C" for r in replica_v2)
```

---

## Cookbook: Delta Composition — Chain Sync Without Full State

```python
from crdt_merge.delta import compute_delta, compose_deltas, DeltaStore

# Three versions of a dataset
v1 = [{"id": "1", "v": 1}, {"id": "2", "v": 2}]
v2 = [{"id": "1", "v": 10}, {"id": "2", "v": 2}, {"id": "3", "v": 3}]
v3 = [{"id": "1", "v": 10}, {"id": "3", "v": 30}, {"id": "4", "v": 4}]
# v3: no change to 1, 2 removed, 3 modified, 4 added

d1_2 = compute_delta(v1, v2, key="id", version=2)  # v1 → v2
d2_3 = compute_delta(v2, v3, key="id", version=3)  # v2 → v3

# Compose: the net effect of both deltas
# Result ≡ compute_delta(v1, v3, key="id")
d1_3_composed = compose_deltas(d1_2, d2_3, key="id")

# Verify: composed delta applied to v1 gives v3
from crdt_merge.delta import apply_delta
result = apply_delta(v1, d1_3_composed, key="id")

expected_ids = {"1", "3", "4"}
actual_ids = {r["id"] for r in result}
assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"

print(f"Composed delta size: {d1_3_composed.size}")
# Net: 1 modified, 1 removed, 2 added = 4 changes
# vs 4 changes sent twice (d1→2 + d2→3) = 5 total ops
# Composition eliminates the intermediate 2→3 record modification
```

---

## Cookbook: DeltaStore — Stateful Delta Tracking

```python
from crdt_merge.delta import DeltaStore

# DeltaStore tracks state and computes deltas automatically
store = DeltaStore(key="id", node_id="primary")

# Initial ingest
initial_records = [{"id": f"R{i:04d}", "value": i} for i in range(1000)]
delta_0 = store.ingest(initial_records)
print(f"Version: {store.version}, Size: {store.size}")  # v=1, size=1000
print(f"Initial delta: {delta_0}")  # None (first ingest, no diff)

# Next batch: 50 new records + 10 modified
new_records = (
    [{"id": f"R{i:04d}", "value": i * 2} for i in range(0, 10)]  # 10 modified
    + [{"id": f"R{i:04d}", "value": i} for i in range(1000, 1050)]  # 50 new
)
updated = initial_records[10:] + new_records  # 990 unchanged + 10 modified + 50 new
delta_1 = store.ingest(updated)

print(f"Delta size: {delta_1.size} changes (vs {store.size} full records)")
print(f"Modified: {len(delta_1.modified)}, Added: {len(delta_1.added)}")
# Delta: 60 changes (vs 1040 full records)

# Replicas only need the delta
replica_records = initial_records[:]  # replica at v1
from crdt_merge.delta import apply_delta
synced = apply_delta(replica_records, delta_1, key="id")
print(f"Replica synced to v{store.version}: {len(synced)} records")
```

---

## Quick Start: Merkle Verification

```python
from crdt_merge.merkle import MerkleTree, merkle_diff, compare_datasets

# Two replicas that should be identical
records_primary = [
    {"id": "A", "name": "Alice", "score": 95},
    {"id": "B", "name": "Bob",   "score": 87},
    {"id": "C", "name": "Carol", "score": 92},
]

records_replica = list(records_primary)  # perfect copy

# Build Merkle trees
tree_primary = MerkleTree.from_records(records_primary, key="id")
tree_replica  = MerkleTree.from_records(records_replica,  key="id")

# Verify: one hash comparison
diff = merkle_diff(tree_primary, tree_replica)
print(f"Identical: {diff.is_identical}")  # True
print(f"Comparisons made: {diff.comparisons_made}")  # 1 (root hash match → done)
```

---

## Cookbook: Locate Divergence in O(log n)

```python
from crdt_merge.merkle import MerkleTree, merkle_diff

# Two replicas that have diverged
primary = [{"id": f"R{i:04d}", "val": i} for i in range(10_000)]
replica = list(primary)

# Introduce 3 divergences
replica[500]["val"] = 99999     # modified
replica[2000]["val"] = 88888    # modified
primary.append({"id": "R10000", "val": 10000})  # added to primary only

tree_p = MerkleTree.from_records(primary, key="id")
tree_r = MerkleTree.from_records(replica,  key="id")

diff = merkle_diff(tree_p, tree_r)

print(f"Identical: {diff.is_identical}")       # False
print(f"Differences: {diff.num_differences}")   # 3

print(f"Only in primary:  {diff.only_in_left}")      # ['R10000']
print(f"Only in replica:  {diff.only_in_right}")     # []
print(f"Modified keys:    {diff.common_different}")  # ['R0500', 'R2000']

print(f"Comparisons made: {diff.comparisons_made}")
# O(log n) — compare ~14 nodes to find 3 divergent keys in 10,000 records
# vs 10,000 comparisons for naive scan

# Repair: sync only the 3 divergent records
records_to_sync = [r for r in primary if r["id"] in diff.only_in_left | diff.common_different]
print(f"Records to sync: {len(records_to_sync)} (vs {len(primary)} full dataset)")
```

---

## Cookbook: Dataset Comparison (Convenience API)

```python
from crdt_merge.merkle import compare_datasets

# Direct comparison without building MerkleTree objects explicitly
records_a = [{"id": f"{i}", "value": i} for i in range(100_000)]
records_b = list(records_a)
records_b[50_000]["value"] = -1  # one divergence

diff = compare_datasets(records_a, records_b, key="id")

print(f"Divergent keys: {diff.common_different}")  # ['50000']
print(f"Is identical: {diff.is_identical}")        # False
print(f"Comparisons: {diff.comparisons_made}")     # O(log 100000) ≈ 17
```

---

## Scenario: Geo-Distributed Database — 10x Bandwidth Reduction

A SaaS application replicates its user database across US, EU, and APAC. Each region receives ~50K writes per day out of a 5M record database.

```python
from crdt_merge.delta import DeltaStore, compose_deltas
from crdt_merge.merkle import MerkleTree, merkle_diff

# Primary (US): DeltaStore tracks all changes
primary_store = DeltaStore(key="user_id", node_id="us-primary")

# Daily sync cycle
def sync_region(primary: DeltaStore, replica_records: list, replica_name: str) -> dict:
    """Sync primary → replica using delta. Verify with Merkle."""

    # 1. Compute delta (only changes since last sync)
    # In production: track last sync version per replica
    current_state = primary_store.records
    delta = primary_store.ingest(current_state)  # would compute from last version

    # 2. Ship delta (not full state)
    delta_size_mb = delta.size * 0.5 / 1024  # ~0.5KB per record change
    full_size_mb  = len(current_state) * 0.5 / 1024
    print(f"[{replica_name}] Delta: {delta_size_mb:.1f}MB vs full: {full_size_mb:.1f}MB")
    print(f"[{replica_name}] Bandwidth saved: {(1 - delta_size_mb/full_size_mb)*100:.0f}%")

    # 3. Apply delta to replica
    from crdt_merge.delta import apply_delta
    synced_replica = apply_delta(replica_records, delta, key="user_id")

    # 4. Merkle verification — O(1) proof of convergence
    tree_primary = MerkleTree.from_records(current_state, key="user_id")
    tree_replica  = MerkleTree.from_records(synced_replica,  key="user_id")
    diff = merkle_diff(tree_primary, tree_replica)

    return {
        "converged": diff.is_identical,
        "divergent_keys": list(diff.common_different | diff.only_in_left | diff.only_in_right),
        "bandwidth_saved_pct": (1 - delta_size_mb / full_size_mb) * 100,
    }


# Example: 5M records, 50K daily changes
print("Without deltas: 5M records × 3 regions = 15M record transfers/day")
print("With deltas: 50K changes × 3 regions = 150K record transfers/day")
print("Bandwidth reduction: 99%")
print("Verification: O(log 5M) ≈ 23 Merkle comparisons per region")
```

---

## Scenario: Multi-Hop Replication — Composable Deltas

A data pipeline replicates through three hops: Primary → Staging → QA → Production. Each hop adds its own transformations. Composable deltas ensure the final state can be verified against the original.

```python
from crdt_merge.delta import compute_delta, compose_deltas, apply_delta

# Three transformation stages
def transform_staging(records):
    """Staging: add staging metadata."""
    return [dict(r, staging_ts=1000) for r in records]

def transform_qa(records):
    """QA: add quality scores."""
    return [dict(r, qa_score=0.95) for r in records]

# Original data
v_primary = [{"id": f"{i}", "value": i} for i in range(1000)]

# Each stage transforms
v_staging = transform_staging(v_primary)
v_qa      = transform_qa(v_staging)

# Compute individual deltas
d_primary_staging = compute_delta(v_primary, v_staging, key="id", version=1)
d_staging_qa      = compute_delta(v_staging,  v_qa,     key="id", version=2)

# Compose: skip intermediate state — send directly to production
d_primary_qa = compose_deltas(d_primary_staging, d_staging_qa, key="id")

# Production applies composed delta directly from primary state
v_production = apply_delta(v_primary, d_primary_qa, key="id")

# Verify using Merkle
from crdt_merge.merkle import compare_datasets
diff = compare_datasets(v_qa, v_production, key="id")
print(f"Primary → Production via composed delta: {diff.is_identical}")  # True

print(f"Individual deltas: {d_primary_staging.size + d_staging_qa.size} total ops")
print(f"Composed delta:    {d_primary_qa.size} total ops (net change only)")
```

---

## Scenario: Apache Arrow Flight — High-Throughput Delta Sync

crdt-merge's delta system integrates with Apache Arrow Flight for high-throughput binary sync:

```python
from crdt_merge.arrow import ArrowMerge
from crdt_merge.delta import compute_delta, apply_delta
import pyarrow as pa

# Convert DataFrame to Arrow
table_v1 = pa.table({
    "id": ["A", "B", "C"],
    "value": [100, 200, 300],
})
table_v2 = pa.table({
    "id": ["A", "B", "D"],
    "value": [150, 200, 400],   # A modified, C removed, D added
})

# Convert to records for delta computation
records_v1 = table_v1.to_pydict()
records_v2 = table_v2.to_pydict()

# Delta of Arrow tables
rows_v1 = [{"id": r, "value": v} for r, v in zip(records_v1["id"], records_v1["value"])]
rows_v2 = [{"id": r, "value": v} for r, v in zip(records_v2["id"], records_v2["value"])]

delta = compute_delta(rows_v1, rows_v2, key="id")
print(f"Arrow delta: {delta.size} row changes")

# Apply and convert back to Arrow
synced = apply_delta(rows_v1, delta, key="id")
result_table = pa.table({
    "id":    [r["id"] for r in synced],
    "value": [r["value"] for r in synced],
})
print(f"Synced Arrow table: {result_table.num_rows} rows")
```

---

## Performance: Why O(log n) Matters at Scale

| Dataset size | Naive scan | Merkle diff | Speedup |
|---|---|---|---|
| 10,000 records | 10,000 comparisons | ~14 comparisons | **714x** |
| 100,000 records | 100,000 comparisons | ~17 comparisons | **5,882x** |
| 1,000,000 records | 1,000,000 comparisons | ~20 comparisons | **50,000x** |
| 10,000,000 records | 10,000,000 comparisons | ~24 comparisons | **416,667x** |

For a 10M-record database, Merkle verification is 400,000× faster than record-by-record comparison. At crdt-merge's benchmark rate of 138K records/sec for tree building, a 10M record Merkle tree builds in ~72 seconds. Subsequent verifications are O(1) if nothing changed, or O(log n) if divergence occurred.

---

## Integration: Delta + Merkle + Gossip

The full sync loop combines all three:

```python
from crdt_merge.delta import DeltaStore
from crdt_merge.merkle import MerkleTree, merkle_diff
from crdt_merge.gossip import GossipState

def full_sync_loop(local_store: DeltaStore, remote_records: list, key: str):
    """Complete sync: delta transfer → apply → Merkle verify → gossip remediation."""

    # 1. Compute and ship delta
    delta = compute_delta(local_store.records, remote_records, key=key)

    # 2. Apply delta
    synced = apply_delta(local_store.records, delta, key=key)

    # 3. Verify convergence
    local_tree  = MerkleTree.from_records(local_store.records, key=key)
    remote_tree = MerkleTree.from_records(remote_records, key=key)
    diff = merkle_diff(local_tree, remote_tree)

    if diff.is_identical:
        return synced, True

    # 4. Divergence detected — find and repair the specific keys
    divergent_keys = diff.common_different | diff.only_in_left | diff.only_in_right
    print(f"Divergence: {len(divergent_keys)} keys need repair")

    # 5. Request only the divergent records (gossip anti-entropy)
    repair_records = [r for r in remote_records if str(r[key]) in divergent_keys]
    repair_delta = compute_delta(synced, repair_records + synced, key=key)
    fully_synced = apply_delta(synced, repair_delta, key=key)

    return fully_synced, True
```

## E4 Trust-Bound Merkle Verification

v0.9.5 introduces trust-bound Merkle trees that integrate the E4 trust layer into delta verification. The 256-ary tree structure achieves 0.500 bit diffusion across depth-4 trees, scaling to 1 billion leaves without degradation.

```python
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.integration.merkle_bridge import TrustBoundMerkleTree

lattice = DeltaTrustLattice(peer_id="sync-node-1")
tree = TrustBoundMerkleTree(trust_lattice=lattice, arity=256)

# Each leaf carries a trust annotation; verification depth scales with peer trust
tree.insert_verified(record_key="user:1001", data=payload, trust_score=0.92)
```

Projection delta encoding achieves 1.45M ops/s, binding trust metadata to every delta without additional round trips. Untrusted peers trigger full Merkle path verification; trusted peers use a fast-path that skips intermediate nodes. The result is bandwidth-efficient sync with per-peer trust enforcement built into the verification layer.

See [E4 Architecture](../e4/E4-MASTER-ARCHITECTURE.md) for the full trust-bound Merkle specification.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Gossip Protocol: Distributed Sync Without a Server](./gossip-serverless-sync.md)
- [Guide — Probabilistic CRDTs](./probabilistic-crdt-analytics.md)
- [Guide — MergeQL: A Query Language for Distributed Knowledge](./mergeql-distributed-knowledge.md)
- [API Reference — DeltaStore](../api-reference/layer1-core/delta.md)
- [API Reference — MerkleTree](../api-reference/layer1-core/merkle.md)
- [Wire Protocol Reference](../guides/wire-protocol.md)
