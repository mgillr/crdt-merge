# crdt-merge v0.6.0 — A100 Benchmark Analysis

**Hardware:** NVIDIA A100-SXM4-40GB · 83.5 GB RAM · 12 vCPUs · Google Colab  
**Date:** 2026-03-28  
**Scale multiplier:** 10× (A100 tier)  
**Total benchmarks:** 78 (all passed)

---

## Executive Summary

The A100 stress test validates v0.6.0 across all 20 modules at production scale. Key headline numbers:

| Metric | Result |
|--------|--------|
| **Peak throughput** | 4.14M ops/s (GCounter increment) |
| **DataFrame merge** | 75K rows/s sustained at 10M rows |
| **Streaming merge** | 594K rows/s (50K batch) → 491K rows/s (1M) |
| **Arrow vs Pandas** | **2.5× consistent speedup** across 500K–50M rows |
| **Wire protocol** | All 14 types roundtrip, 50 B–8.2 KB per type |
| **CRDT verification** | 5/5 types pass all 3 laws |
| **Gossip convergence** | 100 nodes converge in 1 round |

---

## Throughput Rankings

Sorted by peak ops/s, showing scaling behavior:

| # | Operation | Peak ops/s | Scale Range | Scaling Behavior |
|---|-----------|-----------|-------------|-----------------|
| 1 | GCounter increment | **4.14M** | 10K → 500K | Flat — zero degradation |
| 2 | VectorClock ops | **1.06M** | 100K → 2M | Flat — zero degradation |
| 3 | Stream merge | **594K** | 50K → 1M | 17% degradation (memory pressure) |
| 4 | Merge dicts | **530K** | 10K → 500K | 41% degradation (hash table growth) |
| 5 | Gossip updates | **474K** | 10K → 200K | 47% degradation (state growth) |
| 6 | JSON lines merge | **456K** | 10K → 200K | 7% degradation — nearly flat |
| 7 | HLL add | **433K** | 100K → 2M | Flat — zero degradation |
| 8 | Schema evolution | **443K** | 1K → 20K cols | 14% degradation |
| 9 | Dedup strings | **333K** | 100K → 2M | 18% degradation |
| 10 | Bloom add | **178K** | 100K → 2M | Flat — zero degradation |
| 11 | Serialize batch | **170K** | 1K → 50K | Flat — zero degradation |
| 12 | MergeSchema merge | **149K** | 10K → 200K | **Improves** 83K→149K (amortized overhead) |
| 13 | Merkle tree build | **138K** | 50K → 1M | 22% degradation |
| 14 | Provenance merge | **81K** | 50K → 500K | **Improves** 71K→81K (amortized overhead) |
| 15 | DataFrame merge | **77K** | 100K → 10M | 2% degradation — rock stable |

### Scaling Analysis

**Flat scalers** (zero meaningful throughput loss at 10–100× scale):
- GCounter, VectorClock, HLL, Bloom, Serialize batch — these have O(1) per-operation cost

**Improvers** (throughput actually increases with scale):
- MergeSchema: Fixed overhead amortizes → 83K→149K (+80%)
- Provenance: Same pattern → 71K→81K (+14%)

**Graceful degraders** (predictable, manageable throughput loss):
- Stream merge, Dedup strings, Merkle build — all stay within 25% of peak

**Notable**: DataFrame merge at **75K rows/s sustained across 100K→10M rows** with only 2% degradation. This is the core merge path used by most users.

---

## Arrow vs Pandas — The Real Numbers

| Rows | Arrow (s) | Pandas (s) | Speedup |
|------|----------|-----------|---------|
| 500,000 | 2.11 | 5.32 | **2.53×** |
| 5,000,000 | 21.27 | 54.15 | **2.55×** |
| 50,000,000 | 222.47 | 550.57 | **2.47×** |

**Consistent 2.5× speedup** at all scales. The speedup is stable because:
- Arrow optimizes the data shuffling and columnar operations
- Per-field strategy resolution still runs in Python
- The bottleneck shifts from "data movement" (Pandas) to "strategy application" (Python)

**Interpretation**: The Arrow path delivers a solid 2.5× improvement for the full merge pipeline. The theoretical 10-50× speedup applies to the data layer operations alone — achieving that for end-to-end merge requires pushing strategy resolution into native code (planned for the Rust protocol engine).

---

## Wire Protocol Sizes

All 14 CRDT types serialize/deserialize correctly:

| Type | Wire Size | Notes |
|------|----------|-------|
| VectorClock | 50 B | Smallest — compact clock state |
| GCounter | 65 B | Single-node counter |
| GossipEntry | 107 B | Individual gossip update |
| ORSet | 111 B | Small set with unique tags |
| DottedVersionVector | 111 B | Version vector with dot |
| LWWRegister | 123 B | Timestamped value |
| SchemaChange | 144 B | Schema evolution record |
| PNCounter | 163 B | Increment + decrement maps |
| LWWMap | 172 B | Multi-field timestamped map |
| MerkleTree | 287 B | Hash tree with children |
| GossipState | 253 B | Multi-entry gossip state |
| MergeableBloom | 380 B | Bloom filter bit array |
| MergeableCMS | 1.1 KB | Count-Min Sketch matrix |
| MergeableHLL | 8.2 KB | HyperLogLog registers |

---

## CRDT Verification

All 5 tested types pass all 3 CRDT laws:

| Type | Commutative | Associative | Idempotent |
|------|:-----------:|:-----------:|:----------:|
| GCounter | | | |
| PNCounter | | | |
| LWWRegister | | | |
| ORSet | | | |
| VectorClock | | | |

---

## Parallel vs Sequential

| Mode | 1M rows | Time |
|------|---------|------|
| Sequential | 1.5M merged | 10.7s |
| Parallel | 1.5M merged | 20.5s |

**Parallel is 0.52× (slower)**. This is expected: Python's GIL + multiprocessing serialization overhead exceeds the merge compute time. Parallel merge shines for I/O-bound workloads (merging from multiple remote sources) or when using the Rust protocol engine.

---

## Gossip Protocol

- **100-node convergence**: 1 round to full convergence
- **Update throughput**: 474K→253K ops/s (10K→200K updates)

---

## Integration Pipelines

All 5 cross-system pipelines execute successfully:

| Pipeline | Time | Description |
|----------|------|-------------|
| Pipeline 1 | 4.2ms | CRDT → merge → provenance |
| Pipeline 2 | 0.7ms | JSON → merge → export |
| Pipeline 3 | 8.2ms | Schema → merge → diff |
| Pipeline 4 | 1.9ms | Wire → deserialize → merge |
| Pipeline 5 | 4.7ms | Full stack: schema + merge + provenance + wire |

---

## Files

- `crdt_merge_v060_a100_benchmark.json` — Raw benchmark data (78 measurements)
- `throughput_grid.png` — 9-panel throughput scaling charts
- `arrow_vs_pandas.png` — Arrow vs Pandas comparison chart

---

*Generated from A100 stress test notebook: `notebooks/v060_a100_stress_test.ipynb`*
