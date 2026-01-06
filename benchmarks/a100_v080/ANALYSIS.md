# crdt-merge v0.8.0 — Benchmark Report

**Generated:** 2026-03-29T16:25:11.818651+00:00

**Platform:** Linux-6.12.54-x86_64-with

**Python:** 3.12.13

**Total measurements:** 85

---

## CRDT Primitive Throughput

| Primitive | API | Ops | Ops/sec | Time |
|-----------|-----|-----|---------|------|
| GCounter.increment | `GCounter.increment()` | 1M | 4.5M/s | 0.224s |
| PNCounter.mixed | `PNCounter.increment/decrement()` | 500K | 3.7M/s | 0.137s |
| VectorClock.increment | `VectorClock.increment()` | 500K | 950K/s | 0.526s |
| LWWRegister.merge | `LWWRegister.merge()` | 200K | 3.4M/s | 0.058s |
| ORSet.add+merge | `ORSet.add()` | 100K | 251K/s | 0.398s |

## Merge Engine Scaling — Python

| Rows | API | rows/s | Time |
|------|-----|--------|------|
|    10,000 | `merge(a, b, key='id')` | 182K/s | 0.055s |
|    50,000 | `merge(a, b, key='id')` | 174K/s | 0.287s |
|   100,000 | `merge(a, b, key='id')` | 170K/s | 0.589s |
|   500,000 | `merge(a, b, key='id')` | 159K/s | 3.138s |

## Streaming Merge

| Rows | API | Throughput | Time |
|------|-----|-----------|------|
|   100,000 | `merge_stream(a, b, key='id')` | 809K/s | 0.124s |
|   500,000 | `merge_stream(a, b, key='id')` | 779K/s | 0.642s |

## Wire Protocol

| Metric | Value |
|--------|-------|
| Roundtrips | **100,000** in **1.010s** |
| Throughput | **99K/sec** |
| API | `wire.serialize()` / `wire.deserialize()` |

## CRDT Law Verification

| Type | Commutativity | Associativity | Idempotence | API |
|------|:---:|:---:|:---:|-----|
| GCounter | ✅ | ✅ | ✅ | `GCounter.merge()` |
| PNCounter | ✅ | ✅ | ✅ | `PNCounter.merge()` |
| LWWRegister | ✅ | ✅ | ✅ | `LWWRegister.merge()` |

**Result: ✅ ALL PASSED**

## Model Merge — 25 Strategy Benchmark

**25 strategies** benchmarked, each merging 3 models × 10 layers × 64 params

| # | Strategy | API | Merges/sec | Time (1000 merges) |
|---|----------|-----|-----------|-------------------|
| 1 | `ada_merging` | `ModelCRDT.merge()` | 25/s | 4.034s |
| 2 | `adarank` | `ModelCRDT.merge()` | 222/s | 0.450s |
| 3 | `dam` | `ModelCRDT.merge()` | 36/s | 2.776s |
| 4 | `dare` | `ModelCRDT.merge()` | 274/s | 0.365s |
| 5 | `dare_ties` | `ModelCRDT.merge()` | 158/s | 0.631s |
| 6 | `della` | `ModelCRDT.merge()` | 218/s | 0.459s |
| 7 | `emr` | `ModelCRDT.merge()` | 180/s | 0.555s |
| 8 | `evolutionary_merge` | `ModelCRDT.merge()` | 2/s | 2.730s |
| 9 | `fisher_merge` | `ModelCRDT.merge()` | 370/s | 0.270s |
| 10 | `genetic_merge` | `ModelCRDT.merge()` | 2/s | 2.923s |
| 11 | `led_merge` | `ModelCRDT.merge()` | 302/s | 0.331s |
| 12 | `linear` | `ModelCRDT.merge()` | 278/s | 0.359s |
| 13 | `model_breadcrumbs` | `ModelCRDT.merge()` | 187/s | 0.534s |
| 14 | `negative_merge` | `ModelCRDT.merge()` | 322/s | 0.310s |
| 15 | `regression_mean` | `ModelCRDT.merge()` | 373/s | 0.268s |
| 16 | `representation_surgery` | `ModelCRDT.merge()` | 288/s | 0.347s |
| 17 | `safe_merge` | `ModelCRDT.merge()` | 265/s | 0.377s |
| 18 | `slerp` | `ModelCRDT.merge()` | 236/s | 0.423s |
| 19 | `split_unlearn_merge` | `ModelCRDT.merge()` | 285/s | 0.351s |
| 20 | `star` | `ModelCRDT.merge()` | 255/s | 0.393s |
| 21 | `svd_knot_tying` | `ModelCRDT.merge()` | 318/s | 0.315s |
| 22 | `task_arithmetic` | `ModelCRDT.merge()` | 331/s | 0.302s |
| 23 | `ties` | `ModelCRDT.merge()` | 175/s | 0.570s |
| 24 | `weight_average` | `ModelCRDT.merge()` | 387/s | 0.259s |
| 25 | `weight_scope_alignment` | `ModelCRDT.merge()` | 219/s | 0.457s |

## Model Merge Scaling (weight_average)

| Layers × Params | Total Params | API | Merges/sec | Time |
|-----------------|-------------|-----|-----------|------|
| 10 × 64 |       640 | `ModelCRDT.merge()` | 520/s | 0.192s |
| 32 × 256 |     8,192 | `ModelCRDT.merge()` | 143/s | 0.084s |
| 64 × 512 |    32,768 | `ModelCRDT.merge()` | 64/s | 0.156s |
| 128 × 1024 |   131,072 | `ModelCRDT.merge()` | 26/s | 0.383s |

## LoRA Adapter Merging

| Test | API | Config | Merges/sec | Time |
|------|-----|--------|-----------|------|
| 2 adapters, rank=4 | `LoRAMerge.merge_adapters()` | 4 modules, 64×64 | 355/s | 0.282s |
| 2 adapters, rank=16 | `LoRAMerge.merge_adapters()` | 4 modules, 64×64 | 347/s | 0.288s |
| 4 adapters, rank=8 | `LoRAMerge.merge_adapters()` | 4 modules, 64×64 | 202/s | 0.496s |
| 8 adapters, rank=4 | `LoRAMerge.merge_adapters()` | 4 modules, 64×64 | 106/s | 0.942s |
| Rank harmonization (max) | `merge_adapters(rank_strategy='max')` | r4+r8 | 1K/s | 0.155s |
| Rank harmonization (min) | `merge_adapters(rank_strategy='min')` | r4+r8 | 1K/s | 0.187s |
| Rank harmonization (mean) | `merge_adapters(rank_strategy='mean')` | r4+r8 | 1K/s | 0.146s |

## Continual Merge

| Absorptions | API | Time | Absorptions/sec |
|------------|-----|------|----------------|
| 100 | `ContinualMerge.absorb()` | 0.074s | 1K/s |
| 500 | `ContinualMerge.absorb()` | 0.375s | 1K/s |

## Federated Learning Bridge

| Clients | API | Strategy | Rounds/sec | Time |
|---------|-----|----------|-----------|------|
| 10 | `FederatedMerge.submit/aggregate()` | fedavg | 3K/s | 0.035s |
| 50 | `FederatedMerge.submit/aggregate()` | fedavg | 567/s | 0.176s |
| 10 | `FederatedMerge.submit/aggregate()` | fedprox | 572/s | 0.175s |

## Multi-Stage Merge Pipeline

| Stages | API | Pipelines/sec | Time |
|--------|-----|-------------|------|
| 2 | `MergePipeline.execute()` | 331/s | 0.605s |
| 5 | `MergePipeline.execute()` | 132/s | 1.517s |
| 10 | `MergePipeline.execute()` | 66/s | 3.031s |

## GPU Merge (CPU fallback path)

*Skipped — requires `pip install crdt-merge[gpu]` (PyTorch)*

## Safety-Critical Layer Detection

| Layers | API | Analyses/sec | Time |
|--------|-----|-------------|------|
| 10 | `SafetyAnalyzer.safety_report()` | 4K/s | 0.056s |
| 50 | `SafetyAnalyzer.safety_report()` | 725/s | 0.276s |
| 100 | `SafetyAnalyzer.safety_report()` | 363/s | 0.552s |

## Conflict Heatmaps

| Layers | Models | API | Heatmaps/sec | Time |
|--------|--------|-----|-------------|------|
| 10 | 2 | `ConflictHeatmap.from_models()` | 312/s | 0.641s |
| 32 | 3 | `ConflictHeatmap.from_models()` | 69/s | 2.917s |
| 64 | 5 | `ConflictHeatmap.from_models()` | 22/s | 9.171s |

## Provenance Tracking

| Layers Tracked | API | Tracks/sec | Time |
|---------------|-----|-----------|------|
| 10 | `ProvenanceTracker.track_merge()` | 4K/s | 1.176s |
| 50 | `ProvenanceTracker.track_merge()` | 4K/s | 5.880s |
| 100 | `ProvenanceTracker.track_merge()` | 4K/s | 11.818s |

## MergeKit Compatibility

| Operation | API | Ops/sec | Time |
|-----------|-----|---------|------|
| Export | `export_mergekit_config()` | 479K/s | 0.021s |
| Import | `import_mergekit_config()` | 221K/s | 0.045s |
| Roundtrip | `export → import` | 146K/s | 0.068s |

## Model Merge with Provenance

| Layers | API | Merges/sec | Time |
|--------|-----|-----------|------|
| 10 | `ModelCRDT.merge_with_provenance()` | 518/s | 0.386s |
| 32 | `ModelCRDT.merge_with_provenance()` | 162/s | 1.233s |
| 64 | `ModelCRDT.merge_with_provenance()` | 83/s | 2.407s |

## Model CRDT Law Verification

| Strategy | Commutativity | Associativity | Idempotence | API | Trials |
|----------|:---:|:---:|:---:|-----|--------|
| `weight_average` | ✅ | ❌ | ✅ | `ModelCRDT.verify()` | 50 |
| `linear` | ✅ | ❌ | ✅ | `ModelCRDT.verify()` | 50 |
| `slerp` | ✅ | ❌ | ✅ | `ModelCRDT.verify()` | 50 |
| `ties` | ❌ | ❌ | ❌ | `ModelCRDT.verify()` | 50 |
| `dare` | ❌ | ❌ | ❌ | `ModelCRDT.verify()` | 50 |
| `task_arithmetic` | ❌ | ❌ | ❌ | `ModelCRDT.verify()` | 50 |

## JSON / Dict Merge

| Keys | API | Merges/sec | Time |
|------|-----|-----------|------|
| 100 | `merge_dicts(a, b)` | 12K/s | 0.081s |
| 1,000 | `merge_dicts(a, b)` | 1K/s | 0.984s |
| 10,000 | `merge_dicts(a, b)` | 87/s | 11.433s |

## Dedup

| Operation | API | Items | Ops/sec | Time |
|-----------|-----|-------|---------|------|
| Exact dedup | `dedup_list()` | 50K (50% dupes) | — | 0.158s |
| MinHash dedup | `MinHashDedup.dedup()` | 1K docs | — | 1.682s |

## Delta Operations

| Operation | API | Ops | Ops/sec | Time |
|-----------|-----|-----|---------|------|
| Compose pair | `compose_deltas(d1, d2)` | 50K | 277K/s | 0.181s |
| Compose list (DEF-007 fix) | `compose_deltas([d1, d2])` | 50K | 262K/s | 0.191s |

## Summary

**Total measurements:** 85
**All CRDT laws passed:** ✅
**Platform:** Linux-6.12.54-x86_64-with
**Python:** 3.12.13
**Version:** 0.8.0
**Timestamp:** 2026-03-29T16:25:11.818651+00:00

---

*Generated by crdt-merge v0.8.0 benchmark suite*
