# Strategy Test Results — bert-tiny Weights

**Date**: 2026-03-31
**Model**: prajjwal1/bert-tiny (49 tensors, 17.3 MB)
**Test tensor**: bert.encoder.layer.0.attention.self.query.weight (128×128)
**Replicas**: 3 simulated fine-tuned variants (σ=0.01×std noise)
**crdt-merge version**: 0.9.2
**Backend**: numpy (pure-python fallback, no torch)

## Summary

| Metric | Count |
|--------|-------|
| **Total strategies** | 26 |
| **PASS** | 26 |
| **FAIL** | 0 |
| **PASS with warnings** | 0 |

## Full Results

| # | Strategy | Class | Category | Status | Time (ms) | Output Shape |
|---|----------|-------|----------|--------|-----------|--------------|
| 1 | `ada_merging` | `AdaptiveMerging` | Weighted / Importance | ✅ PASS | 62.39 | [128, 128] |
| 2 | `adarank` | `AdaptiveRankPruning` | Subspace / Sparsification | ✅ PASS | 17.88 | [128, 128] |
| 3 | `dam` | `DifferentiableAdaptiveMerging` | Weighted / Importance | ✅ PASS | 36.57 | [128, 128] |
| 4 | `dare` | `DareDropAndRescale` | Subspace / Sparsification | ✅ PASS | 9.44 | [128, 128] |
| 5 | `dare_ties` | `DareTiesHybrid` | Subspace / Sparsification | ✅ PASS | 41.02 | [128, 128] |
| 6 | `della` | `DellaDropElectLowRank` | Subspace / Sparsification | ✅ PASS | 31.04 | [128, 128] |
| 7 | `dual_projection` | `DualProjectionMerge` | continual | ✅ PASS | 16.5 | [128, 128] |
| 8 | `emr` | `EMRMerge` | Subspace / Sparsification | ✅ PASS | 3.45 | [128, 128] |
| 9 | `evolutionary_merge` | `EvolutionaryMerge` | Evolutionary | ✅ PASS | 13600.86 | [128, 128] |
| 10 | `fisher_merge` | `FisherMerge` | Weighted / Importance | ✅ PASS | 1.37 | [128, 128] |
| 11 | `genetic_merge` | `GeneticMerge` | Evolutionary | ✅ PASS | 13583.9 | [128, 128] |
| 12 | `led_merge` | `LEDMerge` | Safety-Aware | ✅ PASS | 20.32 | [128, 128] |
| 13 | `linear` | `LinearInterpolation` | interpolation | ✅ PASS | 1.05 | [128, 128] |
| 14 | `model_breadcrumbs` | `ModelBreadcrumbs` | Subspace / Sparsification | ✅ PASS | 3.5 | [128, 128] |
| 15 | `negative_merge` | `NegativeMerge` | Unlearning | ✅ PASS | 1.18 | [128, 128] |
| 16 | `regression_mean` | `RegressionMean` | Weighted / Importance | ✅ PASS | 1.29 | [128, 128] |
| 17 | `representation_surgery` | `RepresentationSurgery` | Post-Calibration | ✅ PASS | 1.36 | [128, 128] |
| 18 | `safe_merge` | `SafeMerge` | Safety-Aware | ✅ PASS | 10.36 | [128, 128] |
| 19 | `slerp` | `SphericalLinearInterpolation` | interpolation | ✅ PASS | 1.86 | [128, 128] |
| 20 | `split_unlearn_merge` | `SplitUnlearnMerge` | Unlearning | ✅ PASS | 9.92 | [128, 128] |
| 21 | `star` | `SpectralTruncationAdaptiveRescaling` | Subspace / Sparsification | ✅ PASS | 19.1 | [128, 128] |
| 22 | `svd_knot_tying` | `SVDKnotTying` | Subspace / Sparsification | ✅ PASS | 24.83 | [128, 128] |
| 23 | `task_arithmetic` | `TaskArithmetic` | task_vector | ✅ PASS | 1.2 | [128, 128] |
| 24 | `ties` | `TIESMerge` | Subspace / Sparsification | ✅ PASS | 4.57 | [128, 128] |
| 25 | `weight_average` | `WeightAverage` | averaging | ✅ PASS | 0.87 | [128, 128] |
| 26 | `weight_scope_alignment` | `WeightScopeAlignment` | Post-Calibration | ✅ PASS | 2.01 | [128, 128] |

## Notes

- All strategies successfully merged 3 replica tensors using numpy backend
- Evolutionary strategies (evolutionary_merge, genetic_merge) are significantly slower (~13.6s) due to population-based search
- Most deterministic strategies complete in <50ms
- No NaN or Inf values detected in any output
- Weights used: [0.4, 0.3, 0.3] with base tensor provided for task-vector strategies
