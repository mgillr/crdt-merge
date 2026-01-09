# crdt-merge v0.8.0 — CRDT Law Diagnostic Report

**Generated:** 2026-03-29T18:49:11.186922+00:00
**Trials per test:** 100
**Tensor size:** 32
**Tolerance:** 1e-06

---

## Executive Summary

| Category | Count | Strategies |
|----------|-------|------------|
| ✅ True CRDT | 0 | — |
| ⚠️ Partial CRDT | 12 | ada_merging, dam, fisher_merge, led_merge, linear, regression_mean, representation_surgery, safe_merge, slerp, svd_knot_tying, weight_average, weight_scope_alignment |
| ❌ Not CRDT | 13 | adarank, dare, dare_ties, della, emr, evolutionary_merge, genetic_merge, model_breadcrumbs, negative_merge, split_unlearn_merge, star, task_arithmetic, ties |
| 🔧 Untestable (harness bug) | 0 | — |

## Confirmed Bugs

### BUG-002_summary_ignores_model
**Diagnosis:** BUG CONFIRMED: Summary says '✅ ALL PASSED' but model strategies have 6 failing strategies: ['weight_average', 'linear', 'slerp', 'ties', 'dare', 'task_arithmetic']. The summary only checks results['law_verification']['all_passed'] (primitives) and ignores results['model_law_verification'] entirely.

### BUG-003_weight_average_assoc
**Diagnosis:** BUG CONFIRMED: weight_average claims associative=True but merge(merge(A,B),C) = [0.25, 0.25, 0.5] ≠ merge(A,merge(B,C)) = [0.5, 0.25, 0.25]. Pairwise weighted averaging is mathematically non-associative. The crdt_properties declaration is WRONG.

### BUG-001: verify_crdt() Missing Base Parameter
**Affected strategies (13):** adarank, dare, dare_ties, della, emr, model_breadcrumbs, negative_merge, safe_merge, split_unlearn_merge, star, svd_knot_tying, task_arithmetic, ties

The `verify_crdt()` method in `base.py` calls `self.merge([a, b])` **without passing `base=`**.
For strategies that require a base model, this raises `ValueError` on every trial,
causing all three CRDT properties to be falsely reported as FAILED.

### BUG-004: Declaration vs Reality Mismatches

| Strategy | Property | Declared | Empirical |
|----------|----------|----------|-----------|
| `adarank` | associative | True | False |
| `dare` | commutative | True | False |
| `dare_ties` | commutative | True | False |
| `della` | commutative | True | False |
| `emr` | associative | True | False |
| `evolutionary_merge` | commutative | True | False |
| `evolutionary_merge` | associative | True | False |
| `evolutionary_merge` | idempotent | True | False |
| `fisher_merge` | associative | True | False |
| `genetic_merge` | commutative | True | False |
| `genetic_merge` | associative | True | False |
| `led_merge` | associative | True | False |
| `model_breadcrumbs` | associative | True | False |
| `negative_merge` | associative | True | False |
| `regression_mean` | associative | True | False |
| `representation_surgery` | associative | True | False |
| `safe_merge` | associative | True | False |
| `split_unlearn_merge` | associative | True | False |
| `svd_knot_tying` | idempotent | False | True |
| `ties` | associative | True | False |
| `weight_average` | associative | True | False |
| `weight_scope_alignment` | associative | True | False |

---

## Full CRDT Law Test Matrix

| # | Strategy | Category | Comm. | Assoc. | Idemp. | Determ. | Verdict | Root Causes |
|---|----------|----------|:-----:|:------:|:------:|:-------:|---------|-------------|
| 1 | `ada_merging` | Weighted / Importance | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 2 | `adarank` | Subspace / Sparsification | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 3 | `dam` | Weighted / Importance | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 4 | `dare` | Subspace / Sparsification | ❌ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 5 | `dare_ties` | Subspace / Sparsification | ❌ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 6 | `della` | Subspace / Sparsification | ❌ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 7 | `emr` | Subspace / Sparsification | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 8 | `evolutionary_merge` | Evolutionary | ❌ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 9 | `fisher_merge` | Weighted / Importance | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 10 | `genetic_merge` | Evolutionary | ❌ | ❌ | ✅ | ✅ | NOT_CRDT | ARCHITECTURE |
| 11 | `led_merge` | Safety-Aware | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 12 | `linear` | interpolation | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 13 | `model_breadcrumbs` | Subspace / Sparsification | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 14 | `negative_merge` | Unlearning | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 15 | `regression_mean` | Weighted / Importance | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 16 | `representation_surgery` | Post-Calibration | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 17 | `safe_merge` | Safety-Aware | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 18 | `slerp` | interpolation | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 19 | `split_unlearn_merge` | Unlearning | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 20 | `star` | Subspace / Sparsification | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 21 | `svd_knot_tying` | Subspace / Sparsification | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 22 | `task_arithmetic` | task_vector | ✅ | ✅ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 23 | `ties` | Subspace / Sparsification | ✅ | ❌ | ❌ | ✅ | NOT_CRDT | ARCHITECTURE |
| 24 | `weight_average` | averaging | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |
| 25 | `weight_scope_alignment` | Post-Calibration | ✅ | ❌ | ✅ | ✅ | PARTIAL_CRDT (commutative+idempotent only) | ARCHITECTURE |

---

## Detailed Failure Analysis

### `ada_merging`
**Category:** Weighted / Importance  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 64/100 trials failed
  - Max deviation: `6.56e-05`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.12523e-05, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

### `adarank`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.81e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9697789612, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.58e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.2716746212, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `dam`
**Category:** Weighted / Importance  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

### `dare`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **commutativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `2.27e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 9.0033364699, "a_seed": 0, "b_seed": 1}`

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `9.15e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 70.7188093697, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.70e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 14.1437618739, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares commutative=True but empirically FAILS

### `dare_ties`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **commutativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.80e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 13.6579056435, "a_seed": 0, "b_seed": 1}`

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `9.15e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 70.7188093697, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.70e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 14.1437618739, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares commutative=True but empirically FAILS

### `della`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **commutativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `2.68e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 13.6464894491, "a_seed": 0, "b_seed": 1}`

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.98e+02`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 124.8948542137, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `4.76e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 31.8234642164, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares commutative=True but empirically FAILS

### `emr`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `4.19e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 3.0806178644, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.16e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 7.7790690307, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `evolutionary_merge`
**Category:** Evolutionary  
**Requires base:** False  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **commutativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `2.61e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.8501691164, "a_seed": 0, "b_seed": 1}`

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.47e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9809590056, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.64e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.2089641488, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares commutative=True but empirically FAILS
- ⚠️ Declares associative=True but empirically FAILS
- ⚠️ Declares idempotent=True but empirically FAILS

### `fisher_merge`
**Category:** Weighted / Importance  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.98e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.0003341915, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `genetic_merge`
**Category:** Evolutionary  
**Requires base:** False  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **commutativity:** ❌ FAIL — 84/100 trials failed
  - Max deviation: `2.23e-03`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.0001037983, "a_seed": 0, "b_seed": 1}`

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `4.37e-01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.2730999131, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares commutative=True but empirically FAILS
- ⚠️ Declares associative=True but empirically FAILS

### `led_merge`
**Category:** Safety-Aware  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 95/100 trials failed
  - Max deviation: `4.70e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.0609386509, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `linear`
**Category:** interpolation  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

### `model_breadcrumbs`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.81e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.0033996104, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `3.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 2.3294942149, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `negative_merge`
**Category:** Unlearning  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `3.64e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 2.7457451815, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.06e+01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 7.071880937, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `regression_mean`
**Category:** Weighted / Importance  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.97e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.0058792401, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `representation_surgery`
**Category:** Post-Calibration  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `safe_merge`
**Category:** Safety-Aware  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `3.97e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 2.4299662282, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `slerp`
**Category:** interpolation  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.09e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.8003397703, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

### `split_unlearn_merge`
**Category:** Unlearning  
**Requires base:** True  
**Stochastic:** True  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.23e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `4.63e-01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.1156822786, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `star`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.58e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9255658418, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.48e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.2716746212, "description": "merge(A, A) \u2260 A"}`

### `svd_knot_tying`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares idempotent=False but empirically PASSES (conservative)

### `task_arithmetic`
**Category:** task_vector  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `5.29e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 3.5359404685, "description": "merge(A, A) \u2260 A"}`

### `ties`
**Category:** Subspace / Sparsification  
**Requires base:** True  
**Stochastic:** False  
**Verdict:** NOT_CRDT

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `2.35e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 1.5426001836, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

- **idempotency:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `2.91e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 2.2225108333, "description": "merge(A, A) \u2260 A"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `weight_average`
**Category:** averaging  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `1.21e+00`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.9152483938, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

### `weight_scope_alignment`
**Category:** Post-Calibration  
**Requires base:** False  
**Stochastic:** False  
**Verdict:** PARTIAL_CRDT (commutative+idempotent only)

- **associativity:** ❌ FAIL — 100/100 trials failed
  - Max deviation: `6.63e-01`
  - Root cause: **ARCHITECTURE**
  - Example: `{"trial": 0, "max_diff": 0.6231285072, "description": "merge(merge(A,B),C) \u2260 merge(A,merge(B,C))"}`

**Declaration mismatches:**
- ⚠️ Declares associative=True but empirically FAILS

---

## Root Cause Classification

### ARCHITECTURE (25 strategies)
The merge algorithm itself is mathematically incapable of satisfying the law.
Strategies: ada_merging, adarank, dam, dare, dare_ties, della, emr, evolutionary_merge, fisher_merge, genetic_merge, led_merge, linear, model_breadcrumbs, negative_merge, regression_mean, representation_surgery, safe_merge, slerp, split_unlearn_merge, star, svd_knot_tying, task_arithmetic, ties, weight_average, weight_scope_alignment

### BENCHMARK (0 strategies)
The verification harness is broken — typically because `base=` is not passed.
Strategies: (none)

### DECLARATION (19 strategies)
The strategy's `crdt_properties` dict claims properties it doesn't have.
Strategies: adarank, dare, dare_ties, della, emr, evolutionary_merge, fisher_merge, genetic_merge, led_merge, model_breadcrumbs, negative_merge, regression_mean, representation_surgery, safe_merge, split_unlearn_merge, svd_knot_tying, ties, weight_average, weight_scope_alignment

### TRUE_CRDT (0 strategies)
Passes all three CRDT laws empirically.
Strategies: (none)

---

## Recommendations

### Immediate Fixes (Benchmark / Harness)
1. **Fix `verify_crdt()` in `base.py`** — detect base-requiring strategies and pass a generated base tensor
2. **Fix benchmark summary** in `run_benchmark.py` — include `model_law_verification` results in the all-passed check
3. **Fix `crdt_properties` declarations** — update strategies that incorrectly claim associativity or commutativity

### Architecture Fixes
4. **`weight_average`** — non-associative by mathematical definition. Either:
   - Change declaration to `associative=False` (honest)
   - Re-implement merge to use N-way averaging instead of pairwise (makes it associative)
5. **`linear`/`slerp`** — sequential pairwise interpolation is non-associative. Already correctly declared.
6. **Stochastic strategies** (`dare`, `della`, `dare_ties`) — non-deterministic by design. Mark clearly as non-CRDT.
7. **Rename `ModelCRDT`** — most strategies are NOT CRDTs. Consider `ModelMerge` to avoid false guarantees.

---

*Generated by crdt-merge v0.8.0 granular diagnostic suite*