#!/usr/bin/env python3

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

"""
crdt-merge v0.8.0 — Granular CRDT Law Diagnostic Suite
========================================================
PURPOSE:
    Determines *exactly* which strategies satisfy which CRDT laws,
    *why* they fail, and classifies each failure as:
        - ARCHITECTURE : the merge algorithm is mathematically incapable
        - BENCHMARK    : the verification harness is broken (missing base, etc.)
        - DECLARATION  : the strategy's crdt_properties dict is wrong

Each test is isolated, parameterised, and produces machine-readable JSON
plus a human-readable markdown report.

Outputs:
    crdt_law_diagnostics.json   — machine-readable results
    CRDT_LAW_DIAGNOSTICS.md     — human-readable report with root causes
"""

import copy
import json
import math
import os
import random
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── crdt-merge imports ──────────────────────────────────────────────
from crdt_merge.model.strategies import list_strategies, get_strategy
from crdt_merge.model.strategies.base import (
    ModelMergeStrategy,
    _approx_equal,
    _normalize_weights,
    _to_array,
)

# ════════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════════

TRIALS          = 100           # trials per test
TENSOR_SIZE     = 32            # elements per test tensor
TOLERANCE       = 1e-6          # floating-point tolerance
RANDOM_SEED     = 42

# Strategies that need a `base` tensor
BASE_REQUIRED = {
    "task_arithmetic", "ties", "dare", "dare_ties", "della",
    "model_breadcrumbs", "emr", "star", "svd_knot_tying", "adarank",
    "negative_merge", "split_unlearn_merge", "safe_merge",
}

# Strategies that use internal RNG (stochastic)
STOCHASTIC = {
    "dare", "dare_ties", "della", "evolutionary_merge", "genetic_merge",
    "split_unlearn_merge",
}

# ════════════════════════════════════════════════════════════════════
# Tensor generators
# ════════════════════════════════════════════════════════════════════

def make_tensor(seed: int, size: int = TENSOR_SIZE) -> list:
    """Generate a reproducible random tensor."""
    rng = np.random.RandomState(seed)
    return rng.randn(size).tolist()

def make_base(size: int = TENSOR_SIZE) -> list:
    """Stable base model tensor."""
    rng = np.random.RandomState(9999)
    return rng.randn(size).tolist()

# ════════════════════════════════════════════════════════════════════
# Comparison helpers
# ════════════════════════════════════════════════════════════════════

def tensors_equal(a, b, tol=TOLERANCE) -> Tuple[bool, float]:
    """Return (equal, max_diff)."""
    la = _to_list(a)
    lb = _to_list(b)
    if len(la) != len(lb):
        return False, float('inf')
    diffs = [abs(x - y) for x, y in zip(la, lb)]
    max_diff = max(diffs) if diffs else 0.0
    return max_diff < tol, max_diff

def _to_list(x):
    if isinstance(x, np.ndarray):
        return x.ravel().tolist()
    if isinstance(x, (list, tuple)):
        flat = []
        for item in x:
            if isinstance(item, (list, tuple)):
                flat.extend(item)
            else:
                flat.append(float(item))
        return flat
    return [float(x)]

# ════════════════════════════════════════════════════════════════════
# Test result containers
# ════════════════════════════════════════════════════════════════════

@dataclass
class PropertyResult:
    """Result for a single CRDT property test."""
    property_name: str
    passed: bool
    trials_run: int
    failures: int
    error_type: Optional[str] = None      # "ValueError", "TypeError", etc.
    error_msg: Optional[str] = None
    max_deviation: float = 0.0            # worst-case numerical difference
    example_failure: Optional[dict] = None # first failure details
    root_cause: str = "UNKNOWN"           # ARCHITECTURE | BENCHMARK | DECLARATION

@dataclass
class StrategyDiagnostic:
    """Full diagnostic for one strategy."""
    strategy_name: str
    category: str
    requires_base: bool
    is_stochastic: bool
    declared_properties: Dict[str, Any]
    commutativity: Optional[PropertyResult] = None
    associativity: Optional[PropertyResult] = None
    idempotency: Optional[PropertyResult] = None
    determinism: Optional[PropertyResult] = None
    # Cross-check
    declaration_mismatches: List[str] = field(default_factory=list)
    overall_verdict: str = ""

# ════════════════════════════════════════════════════════════════════
# Core test functions
# ════════════════════════════════════════════════════════════════════

def test_commutativity(strat: ModelMergeStrategy, name: str,
                       trials: int = TRIALS) -> PropertyResult:
    """Test: merge([A, B]) == merge([B, A])"""
    res = PropertyResult("commutativity", True, trials, 0)
    base = make_base() if name in BASE_REQUIRED else None
    
    for t in range(trials):
        a = make_tensor(t * 3 + 0)
        b = make_tensor(t * 3 + 1)
        
        try:
            kwargs = {"seed": 42} if name in STOCHASTIC else {}
            ab = strat.merge([a, b], base=base, **kwargs)
            ba = strat.merge([b, a], base=base, **kwargs)
            eq, diff = tensors_equal(ab, ba)
            if not eq:
                res.passed = False
                res.failures += 1
                res.max_deviation = max(res.max_deviation, diff)
                if res.example_failure is None:
                    res.example_failure = {
                        "trial": t,
                        "max_diff": round(diff, 10),
                        "a_seed": t * 3 + 0,
                        "b_seed": t * 3 + 1,
                    }
        except Exception as e:
            res.passed = False
            res.failures += 1
            if res.error_type is None:
                res.error_type = type(e).__name__
                res.error_msg = str(e)[:200]
                res.example_failure = {"trial": t, "exception": str(e)[:200]}
    
    # Classify root cause
    if res.passed:
        res.root_cause = "NONE"
    elif res.error_type == "ValueError" and "base" in (res.error_msg or "").lower():
        res.root_cause = "BENCHMARK"
    elif name in STOCHASTIC and res.failures > 0 and res.error_type is None:
        res.root_cause = "ARCHITECTURE"
    elif res.error_type is None and res.failures > 0:
        res.root_cause = "ARCHITECTURE"
    else:
        res.root_cause = "BENCHMARK"
    
    return res

def test_associativity(strat: ModelMergeStrategy, name: str,
                       trials: int = TRIALS) -> PropertyResult:
    """Test: merge([merge([A,B]), C]) == merge([A, merge([B,C])])"""
    res = PropertyResult("associativity", True, trials, 0)
    base = make_base() if name in BASE_REQUIRED else None
    
    for t in range(trials):
        a = make_tensor(t * 3 + 0)
        b = make_tensor(t * 3 + 1)
        c = make_tensor(t * 3 + 2)
        
        try:
            kwargs = {"seed": 42} if name in STOCHASTIC else {}
            ab = strat.merge([a, b], base=base, **kwargs)
            # Convert to list to ensure clean input
            ab_list = _to_list(ab)
            ab_c = strat.merge([ab_list, c], base=base, **kwargs)
            
            bc = strat.merge([b, c], base=base, **kwargs)
            bc_list = _to_list(bc)
            a_bc = strat.merge([a, bc_list], base=base, **kwargs)
            
            eq, diff = tensors_equal(ab_c, a_bc)
            if not eq:
                res.passed = False
                res.failures += 1
                res.max_deviation = max(res.max_deviation, diff)
                if res.example_failure is None:
                    res.example_failure = {
                        "trial": t,
                        "max_diff": round(diff, 10),
                        "description": "merge(merge(A,B),C) ≠ merge(A,merge(B,C))",
                    }
        except Exception as e:
            res.passed = False
            res.failures += 1
            if res.error_type is None:
                res.error_type = type(e).__name__
                res.error_msg = str(e)[:200]
                res.example_failure = {"trial": t, "exception": str(e)[:200]}
    
    # Classify
    if res.passed:
        res.root_cause = "NONE"
    elif res.error_type == "ValueError" and "base" in (res.error_msg or "").lower():
        res.root_cause = "BENCHMARK"
    elif res.error_type is None and res.failures > 0:
        # Pure numerical divergence = mathematical limitation
        res.root_cause = "ARCHITECTURE"
    else:
        res.root_cause = "BENCHMARK"
    
    return res

def test_idempotency(strat: ModelMergeStrategy, name: str,
                     trials: int = TRIALS) -> PropertyResult:
    """Test: merge([A, A]) == A"""
    res = PropertyResult("idempotency", True, trials, 0)
    base = make_base() if name in BASE_REQUIRED else None
    
    for t in range(trials):
        a = make_tensor(t)
        a_copy = list(a)  # fresh copy
        
        try:
            kwargs = {"seed": 42} if name in STOCHASTIC else {}
            aa = strat.merge([a, a_copy], base=base, **kwargs)
            eq, diff = tensors_equal(aa, a)
            if not eq:
                res.passed = False
                res.failures += 1
                res.max_deviation = max(res.max_deviation, diff)
                if res.example_failure is None:
                    res.example_failure = {
                        "trial": t,
                        "max_diff": round(diff, 10),
                        "description": "merge(A, A) ≠ A",
                    }
        except Exception as e:
            res.passed = False
            res.failures += 1
            if res.error_type is None:
                res.error_type = type(e).__name__
                res.error_msg = str(e)[:200]
                res.example_failure = {"trial": t, "exception": str(e)[:200]}
    
    # Classify
    if res.passed:
        res.root_cause = "NONE"
    elif res.error_type == "ValueError" and "base" in (res.error_msg or "").lower():
        res.root_cause = "BENCHMARK"
    elif name in STOCHASTIC and res.error_type is None:
        res.root_cause = "ARCHITECTURE"
    elif res.error_type is None and res.failures > 0:
        res.root_cause = "ARCHITECTURE"
    else:
        res.root_cause = "BENCHMARK"
    
    return res

def test_determinism(strat: ModelMergeStrategy, name: str,
                     trials: int = TRIALS) -> PropertyResult:
    """Test: merge([A, B]) called twice with same inputs → same output."""
    res = PropertyResult("determinism", True, trials, 0)
    base = make_base() if name in BASE_REQUIRED else None
    
    for t in range(trials):
        a = make_tensor(t * 2)
        b = make_tensor(t * 2 + 1)
        
        try:
            kwargs = {"seed": 42} if name in STOCHASTIC else {}
            r1 = strat.merge([list(a), list(b)], base=list(base) if base else None, **kwargs)
            r2 = strat.merge([list(a), list(b)], base=list(base) if base else None, **kwargs)
            eq, diff = tensors_equal(r1, r2)
            if not eq:
                res.passed = False
                res.failures += 1
                res.max_deviation = max(res.max_deviation, diff)
                if res.example_failure is None:
                    res.example_failure = {
                        "trial": t,
                        "max_diff": round(diff, 10),
                        "description": "Same inputs produced different outputs",
                    }
        except Exception as e:
            res.passed = False
            res.failures += 1
            if res.error_type is None:
                res.error_type = type(e).__name__
                res.error_msg = str(e)[:200]
    
    if res.passed:
        res.root_cause = "NONE"
    elif res.error_type is not None:
        res.root_cause = "BENCHMARK"
    else:
        res.root_cause = "ARCHITECTURE"
    
    return res

# ════════════════════════════════════════════════════════════════════
# Bug-specific regression tests
# ════════════════════════════════════════════════════════════════════

def test_verify_crdt_base_bug() -> Dict[str, Any]:
    """
    BUG-001: verify_crdt() does not pass `base=` to strategies that require it.
    
    This test proves the benchmark harness itself is broken: calling
    strategy.verify_crdt() on a base-requiring strategy will raise ValueError
    on every trial, causing all properties to be incorrectly marked as failed.
    """
    results = {}
    for name in sorted(BASE_REQUIRED):
        try:
            strat = get_strategy(name)
        except Exception:
            results[name] = {"status": "STRATEGY_NOT_FOUND"}
            continue
        
        # Call verify_crdt exactly as the benchmark does — WITHOUT base
        v = strat.verify_crdt(trials=5)
        
        # If all three are False AND failures are 5/5, the bug is confirmed
        all_failed = not v["commutative"] and not v["associative"] and not v["idempotent"]
        full_failure_count = (
            v["failures"]["commutative"] == 5 and
            v["failures"]["associative"] == 5 and
            v["failures"]["idempotent"] == 5
        )
        
        results[name] = {
            "verify_crdt_result": {k: v for k, v in v.items() if k != "failures"},
            "failure_counts": v["failures"],
            "bug_confirmed": all_failed and full_failure_count,
            "diagnosis": (
                "BUG CONFIRMED: verify_crdt() raises ValueError on every trial "
                "because base= is never passed. All properties falsely report FAIL."
                if all_failed and full_failure_count
                else "Partial failure — investigate further"
            ),
        }
    return results

def test_summary_ignores_model_laws() -> Dict[str, Any]:
    """
    BUG-002: Benchmark summary reports "All CRDT laws passed: ✅" but only
    checks primitive CRDT results, completely ignoring model_law_verification.
    """
    # Load the actual benchmark results
    results_path = os.path.join(os.path.dirname(__file__), "all_results.json")
    if not os.path.exists(results_path):
        return {"status": "SKIPPED", "reason": "all_results.json not found"}
    
    with open(results_path) as f:
        bench = json.load(f)
    
    primitive_passed = bench.get("law_verification", {}).get("all_passed", False)
    model_laws = bench.get("model_law_verification", {}).get("strategies", {})
    
    model_failures = {}
    for strat, props in model_laws.items():
        fails = [k for k, v in props.items() if not v]
        if fails:
            model_failures[strat] = fails
    
    summary_claims_all_passed = bench.get("summary", {}).get("crdt_laws_passed", False)
    
    return {
        "primitive_laws_passed": primitive_passed,
        "model_strategy_failures": model_failures,
        "summary_claims_all_passed": summary_claims_all_passed,
        "bug_confirmed": summary_claims_all_passed and len(model_failures) > 0,
        "diagnosis": (
            "BUG CONFIRMED: Summary says '✅ ALL PASSED' but model strategies have "
            f"{len(model_failures)} failing strategies: {list(model_failures.keys())}. "
            "The summary only checks results['law_verification']['all_passed'] (primitives) "
            "and ignores results['model_law_verification'] entirely."
        ) if summary_claims_all_passed and len(model_failures) > 0 else "No bug detected",
    }

def test_weight_average_associativity_proof() -> Dict[str, Any]:
    """
    BUG-003: weight_average declares associative=True but weighted averaging
    is MATHEMATICALLY non-associative when applied pairwise.
    
    Proof: merge(merge(A,B), C) = 0.25A + 0.25B + 0.5C
           merge(A, merge(B,C)) = 0.5A + 0.25B + 0.25C
           These are NOT equal.
    """
    strat = get_strategy("weight_average")
    
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    c = [0.0, 0.0, 1.0]
    
    # Left association: merge(merge(A,B), C)
    ab = strat.merge([a, b])       # [0.5, 0.5, 0.0]
    ab_c = strat.merge([ab, c])    # [0.25, 0.25, 0.5]
    
    # Right association: merge(A, merge(B,C))
    bc = strat.merge([b, c])       # [0.0, 0.5, 0.5]
    a_bc = strat.merge([a, bc])    # [0.5, 0.25, 0.25]
    
    eq, diff = tensors_equal(ab_c, a_bc)
    
    return {
        "a": a, "b": b, "c": c,
        "merge_ab": _to_list(ab),
        "merge_ab_c": _to_list(ab_c),
        "merge_bc": _to_list(bc),
        "merge_a_bc": _to_list(a_bc),
        "equal": eq,
        "max_diff": round(diff, 10),
        "declared_associative": strat.crdt_properties.get("associative"),
        "bug_confirmed": not eq and strat.crdt_properties.get("associative") == True,
        "diagnosis": (
            "BUG CONFIRMED: weight_average claims associative=True but "
            "merge(merge(A,B),C) = [0.25, 0.25, 0.5] ≠ merge(A,merge(B,C)) = [0.5, 0.25, 0.25]. "
            "Pairwise weighted averaging is mathematically non-associative. "
            "The crdt_properties declaration is WRONG."
        ) if not eq else "No bug detected",
    }

def test_declaration_vs_reality() -> Dict[str, Any]:
    """
    BUG-004: Cross-check every strategy's crdt_properties declaration against
    actual empirical test results.
    """
    mismatches = {}
    all_strats = list_strategies()
    base = make_base()
    
    for name in all_strats:
        strat = get_strategy(name)
        declared = strat.crdt_properties
        
        # Run quick empirical check (10 trials)
        needs_base = name in BASE_REQUIRED
        kwargs = {"seed": 42} if name in STOCHASTIC else {}
        
        empirical = {"commutative": True, "associative": True, "idempotent": True}
        errors = {}
        
        for t in range(10):
            a = make_tensor(t * 3)
            b = make_tensor(t * 3 + 1)
            c = make_tensor(t * 3 + 2)
            b_arg = base if needs_base else None
            
            # Commutativity
            try:
                ab = strat.merge([a, b], base=b_arg, **kwargs)
                ba = strat.merge([b, a], base=b_arg, **kwargs)
                eq, _ = tensors_equal(ab, ba)
                if not eq:
                    empirical["commutative"] = False
            except Exception as e:
                empirical["commutative"] = False
                errors["commutative"] = str(e)[:100]
            
            # Associativity
            try:
                ab = strat.merge([a, b], base=b_arg, **kwargs)
                ab_c = strat.merge([_to_list(ab), c], base=b_arg, **kwargs)
                bc = strat.merge([b, c], base=b_arg, **kwargs)
                a_bc = strat.merge([a, _to_list(bc)], base=b_arg, **kwargs)
                eq, _ = tensors_equal(ab_c, a_bc)
                if not eq:
                    empirical["associative"] = False
            except Exception as e:
                empirical["associative"] = False
                errors["associativity"] = str(e)[:100]
            
            # Idempotency
            try:
                aa = strat.merge([a, list(a)], base=b_arg, **kwargs)
                eq, _ = tensors_equal(aa, a)
                if not eq:
                    empirical["idempotent"] = False
            except Exception as e:
                empirical["idempotent"] = False
                errors["idempotency"] = str(e)[:100]
        
        # Compare declared vs empirical
        strat_mismatches = []
        for prop in ["commutative", "associative", "idempotent"]:
            decl = declared.get(prop)
            emp = empirical[prop]
            # "conditional" declarations are treated as non-boolean
            if isinstance(decl, bool) and decl != emp:
                strat_mismatches.append({
                    "property": prop,
                    "declared": decl,
                    "empirical": emp,
                    "issue": f"Declares {prop}={decl} but empirically {prop}={emp}",
                })
        
        if strat_mismatches:
            mismatches[name] = {
                "declared": {k: v for k, v in declared.items()},
                "empirical": empirical,
                "mismatches": strat_mismatches,
                "errors": errors if errors else None,
            }
    
    return {
        "strategies_with_mismatches": list(mismatches.keys()),
        "total_mismatches": sum(len(v["mismatches"]) for v in mismatches.values()),
        "details": mismatches,
    }

# ════════════════════════════════════════════════════════════════════
# Main runner
# ════════════════════════════════════════════════════════════════════

def run_full_diagnostic() -> dict:
    """Run every test, return complete diagnostic report."""
    
    print("=" * 70)
    print("  crdt-merge v0.8.0 — Granular CRDT Law Diagnostic Suite")
    print("=" * 70)
    
    all_strategies = list_strategies()
    print(f"\nDiscovered {len(all_strategies)} strategies: {', '.join(all_strategies)}\n")
    
    # ── Phase 1: Per-strategy CRDT law tests ──────────────────────────
    print("Phase 1: Testing CRDT laws per strategy...")
    print("-" * 60)
    
    diagnostics: Dict[str, dict] = {}
    
    for name in all_strategies:
        strat = get_strategy(name)
        print(f"  Testing {name:30s} ... ", end="", flush=True)
        
        diag = StrategyDiagnostic(
            strategy_name=name,
            category=strat.category,
            requires_base=name in BASE_REQUIRED,
            is_stochastic=name in STOCHASTIC,
            declared_properties=strat.crdt_properties,
        )
        
        t0 = time.time()
        diag.commutativity = test_commutativity(strat, name)
        diag.associativity = test_associativity(strat, name)
        diag.idempotency = test_idempotency(strat, name)
        diag.determinism = test_determinism(strat, name)
        elapsed = time.time() - t0
        
        # Check declaration mismatches
        for prop_name, result in [
            ("commutative", diag.commutativity),
            ("associative", diag.associativity),
            ("idempotent", diag.idempotency),
        ]:
            declared = strat.crdt_properties.get(prop_name)
            if isinstance(declared, bool) and declared and not result.passed:
                diag.declaration_mismatches.append(
                    f"Declares {prop_name}=True but empirically FAILS"
                )
            elif isinstance(declared, bool) and not declared and result.passed:
                diag.declaration_mismatches.append(
                    f"Declares {prop_name}=False but empirically PASSES (conservative)"
                )
        
        # Overall verdict
        all_pass = all([
            diag.commutativity.passed,
            diag.associativity.passed,
            diag.idempotency.passed,
        ])
        if all_pass:
            diag.overall_verdict = "TRUE_CRDT"
        elif diag.commutativity.passed and diag.idempotency.passed:
            diag.overall_verdict = "PARTIAL_CRDT (commutative+idempotent only)"
        elif any(r.error_type for r in [diag.commutativity, diag.associativity, diag.idempotency]):
            diag.overall_verdict = "UNTESTABLE (benchmark bugs prevent verification)"
        else:
            diag.overall_verdict = "NOT_CRDT"
        
        c = "✅" if diag.commutativity.passed else "❌"
        a = "✅" if diag.associativity.passed else "❌"
        i = "✅" if diag.idempotency.passed else "❌"
        d = "✅" if diag.determinism.passed else "❌"
        print(f"C{c} A{a} I{i} D{d}  ({elapsed:.2f}s)  [{diag.overall_verdict}]")
        
        diagnostics[name] = asdict(diag)
    
    # ── Phase 2: Bug-specific regression tests ────────────────────────
    print(f"\n{'='*60}")
    print("Phase 2: Bug-specific regression tests")
    print("-" * 60)
    
    bug_tests = {}
    
    print("  BUG-001: verify_crdt() missing base parameter ... ", end="", flush=True)
    bug_tests["BUG-001_verify_crdt_base"] = test_verify_crdt_base_bug()
    confirmed = sum(1 for v in bug_tests["BUG-001_verify_crdt_base"].values()
                    if isinstance(v, dict) and v.get("bug_confirmed"))
    print(f"CONFIRMED in {confirmed}/{len(BASE_REQUIRED)} strategies")
    
    print("  BUG-002: Summary ignores model law failures ... ", end="", flush=True)
    bug_tests["BUG-002_summary_ignores_model"] = test_summary_ignores_model_laws()
    b2 = bug_tests["BUG-002_summary_ignores_model"]
    print(f"{'CONFIRMED' if b2.get('bug_confirmed') else 'NOT FOUND'}")
    
    print("  BUG-003: weight_average false associativity claim ... ", end="", flush=True)
    bug_tests["BUG-003_weight_average_assoc"] = test_weight_average_associativity_proof()
    b3 = bug_tests["BUG-003_weight_average_assoc"]
    print(f"{'CONFIRMED' if b3.get('bug_confirmed') else 'NOT FOUND'}")
    
    print("  BUG-004: Declaration vs reality cross-check ... ", end="", flush=True)
    bug_tests["BUG-004_declaration_mismatches"] = test_declaration_vs_reality()
    b4 = bug_tests["BUG-004_declaration_mismatches"]
    print(f"{b4.get('total_mismatches', 0)} mismatches across {len(b4.get('strategies_with_mismatches', []))} strategies")
    
    # ── Phase 3: Classification matrix ────────────────────────────────
    print(f"\n{'='*60}")
    print("Phase 3: Root cause classification")
    print("-" * 60)
    
    classification = {
        "ARCHITECTURE": [],  # math limitation
        "BENCHMARK": [],     # test harness bug
        "DECLARATION": [],   # wrong crdt_properties
        "TRUE_CRDT": [],     # passes all laws
    }
    
    for name, diag in diagnostics.items():
        causes = set()
        for prop in ["commutativity", "associativity", "idempotency"]:
            prop_data = diag.get(prop, {})
            if not prop_data.get("passed", True):
                causes.add(prop_data.get("root_cause", "UNKNOWN"))
        
        if not causes:
            classification["TRUE_CRDT"].append(name)
        else:
            for cause in causes:
                if cause in classification:
                    classification[cause].append(name)
        
        if diag.get("declaration_mismatches"):
            classification["DECLARATION"].append(name)
    
    # Deduplicate
    for k in classification:
        classification[k] = sorted(set(classification[k]))
    
    for cat, strats in classification.items():
        print(f"  {cat:15s}: {len(strats):2d} strategies — {', '.join(strats) if strats else '(none)'}")
    
    # ── Assemble final report ─────────────────────────────────────────
    report = {
        "meta": {
            "version": "0.8.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trials_per_test": TRIALS,
            "tensor_size": TENSOR_SIZE,
            "tolerance": TOLERANCE,
        },
        "strategy_diagnostics": diagnostics,
        "bug_regression_tests": bug_tests,
        "classification": classification,
    }
    
    return report

# ════════════════════════════════════════════════════════════════════
# Report generation
# ════════════════════════════════════════════════════════════════════

def generate_markdown_report(report: dict) -> str:
    """Generate human-readable markdown diagnostic report."""
    
    lines = [
        "# crdt-merge v0.8.0 — CRDT Law Diagnostic Report",
        "",
        f"**Generated:** {report['meta']['timestamp']}",
        f"**Trials per test:** {report['meta']['trials_per_test']}",
        f"**Tensor size:** {report['meta']['tensor_size']}",
        f"**Tolerance:** {report['meta']['tolerance']}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]
    
    diags = report["strategy_diagnostics"]
    total = len(diags)
    true_crdts = [n for n, d in diags.items() if d["overall_verdict"] == "TRUE_CRDT"]
    untestable = [n for n, d in diags.items() if "UNTESTABLE" in d["overall_verdict"]]
    not_crdts = [n for n, d in diags.items() if "NOT_CRDT" in d["overall_verdict"]]
    partial = [n for n, d in diags.items() if "PARTIAL" in d["overall_verdict"]]
    
    lines.append(f"| Category | Count | Strategies |")
    lines.append(f"|----------|-------|------------|")
    lines.append(f"| ✅ True CRDT | {len(true_crdts)} | {', '.join(true_crdts) or '—'} |")
    lines.append(f"| ⚠️ Partial CRDT | {len(partial)} | {', '.join(partial) or '—'} |")
    lines.append(f"| ❌ Not CRDT | {len(not_crdts)} | {', '.join(not_crdts) or '—'} |")
    lines.append(f"| 🔧 Untestable (harness bug) | {len(untestable)} | {', '.join(untestable) or '—'} |")
    lines.append("")
    
    # Bugs found
    bugs = report["bug_regression_tests"]
    lines.append("## Confirmed Bugs")
    lines.append("")
    
    for bug_id, data in bugs.items():
        if isinstance(data, dict) and data.get("bug_confirmed"):
            lines.append(f"### {bug_id}")
            lines.append(f"**Diagnosis:** {data.get('diagnosis', 'N/A')}")
            lines.append("")
        elif isinstance(data, dict) and not data.get("bug_confirmed") and "diagnosis" in data:
            if "CONFIRMED" in str(data.get("diagnosis", "")):
                lines.append(f"### {bug_id}")
                lines.append(f"**Diagnosis:** {data.get('diagnosis', 'N/A')}")
                lines.append("")
    
    # BUG-001 detail
    bug1 = bugs.get("BUG-001_verify_crdt_base", {})
    confirmed_strats = [k for k, v in bug1.items() if isinstance(v, dict) and v.get("bug_confirmed")]
    if confirmed_strats:
        lines.append("### BUG-001: verify_crdt() Missing Base Parameter")
        lines.append(f"**Affected strategies ({len(confirmed_strats)}):** {', '.join(confirmed_strats)}")
        lines.append("")
        lines.append("The `verify_crdt()` method in `base.py` calls `self.merge([a, b])` **without passing `base=`**.")
        lines.append("For strategies that require a base model, this raises `ValueError` on every trial,")
        lines.append("causing all three CRDT properties to be falsely reported as FAILED.")
        lines.append("")
    
    # BUG-004 detail
    bug4 = bugs.get("BUG-004_declaration_mismatches", {})
    if bug4.get("total_mismatches", 0) > 0:
        lines.append("### BUG-004: Declaration vs Reality Mismatches")
        lines.append("")
        lines.append("| Strategy | Property | Declared | Empirical |")
        lines.append("|----------|----------|----------|-----------|")
        for strat_name, info in bug4.get("details", {}).items():
            for mm in info.get("mismatches", []):
                lines.append(f"| `{strat_name}` | {mm['property']} | {mm['declared']} | {mm['empirical']} |")
        lines.append("")
    
    # Full test matrix
    lines.append("---")
    lines.append("")
    lines.append("## Full CRDT Law Test Matrix")
    lines.append("")
    lines.append("| # | Strategy | Category | Comm. | Assoc. | Idemp. | Determ. | Verdict | Root Causes |")
    lines.append("|---|----------|----------|:-----:|:------:|:------:|:-------:|---------|-------------|")
    
    for idx, (name, d) in enumerate(sorted(diags.items()), 1):
        cat = d["category"]
        c = "✅" if d["commutativity"]["passed"] else "❌"
        a = "✅" if d["associativity"]["passed"] else "❌"
        i = "✅" if d["idempotency"]["passed"] else "❌"
        det = "✅" if d["determinism"]["passed"] else "❌"
        verdict = d["overall_verdict"]
        
        causes = set()
        for prop in ["commutativity", "associativity", "idempotency"]:
            rc = d[prop]["root_cause"]
            if rc != "NONE":
                causes.add(rc)
        cause_str = ", ".join(sorted(causes)) if causes else "—"
        
        lines.append(f"| {idx} | `{name}` | {cat} | {c} | {a} | {i} | {det} | {verdict} | {cause_str} |")
    
    lines.append("")
    
    # Detailed failure analysis for key strategies
    lines.append("---")
    lines.append("")
    lines.append("## Detailed Failure Analysis")
    lines.append("")
    
    for name, d in sorted(diags.items()):
        has_failures = any(
            not d[p]["passed"] for p in ["commutativity", "associativity", "idempotency"]
        )
        if not has_failures:
            continue
        
        lines.append(f"### `{name}`")
        lines.append(f"**Category:** {d['category']}  ")
        lines.append(f"**Requires base:** {d['requires_base']}  ")
        lines.append(f"**Stochastic:** {d['is_stochastic']}  ")
        lines.append(f"**Verdict:** {d['overall_verdict']}")
        lines.append("")
        
        for prop in ["commutativity", "associativity", "idempotency"]:
            pd = d[prop]
            if pd["passed"]:
                continue
            lines.append(f"- **{prop}:** ❌ FAIL — {pd['failures']}/{pd['trials_run']} trials failed")
            if pd["error_type"]:
                lines.append(f"  - Exception: `{pd['error_type']}: {pd['error_msg']}`")
            if pd["max_deviation"] > 0:
                lines.append(f"  - Max deviation: `{pd['max_deviation']:.2e}`")
            lines.append(f"  - Root cause: **{pd['root_cause']}**")
            if pd.get("example_failure"):
                lines.append(f"  - Example: `{json.dumps(pd['example_failure'])}`")
            lines.append("")
        
        if d.get("declaration_mismatches"):
            lines.append("**Declaration mismatches:**")
            for mm in d["declaration_mismatches"]:
                lines.append(f"- ⚠️ {mm}")
            lines.append("")
    
    # Root cause classification
    lines.append("---")
    lines.append("")
    lines.append("## Root Cause Classification")
    lines.append("")
    cls = report["classification"]
    lines.append(f"### ARCHITECTURE ({len(cls.get('ARCHITECTURE', []))} strategies)")
    lines.append("The merge algorithm itself is mathematically incapable of satisfying the law.")
    lines.append(f"Strategies: {', '.join(cls.get('ARCHITECTURE', [])) or '(none)'}")
    lines.append("")
    lines.append(f"### BENCHMARK ({len(cls.get('BENCHMARK', []))} strategies)")
    lines.append("The verification harness is broken — typically because `base=` is not passed.")
    lines.append(f"Strategies: {', '.join(cls.get('BENCHMARK', [])) or '(none)'}")
    lines.append("")
    lines.append(f"### DECLARATION ({len(cls.get('DECLARATION', []))} strategies)")
    lines.append("The strategy's `crdt_properties` dict claims properties it doesn't have.")
    lines.append(f"Strategies: {', '.join(cls.get('DECLARATION', [])) or '(none)'}")
    lines.append("")
    lines.append(f"### TRUE_CRDT ({len(cls.get('TRUE_CRDT', []))} strategies)")
    lines.append("Passes all three CRDT laws empirically.")
    lines.append(f"Strategies: {', '.join(cls.get('TRUE_CRDT', [])) or '(none)'}")
    lines.append("")
    
    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("### Immediate Fixes (Benchmark / Harness)")
    lines.append("1. **Fix `verify_crdt()` in `base.py`** — detect base-requiring strategies and pass a generated base tensor")
    lines.append("2. **Fix benchmark summary** in `run_benchmark.py` — include `model_law_verification` results in the all-passed check")
    lines.append("3. **Fix `crdt_properties` declarations** — update strategies that incorrectly claim associativity or commutativity")
    lines.append("")
    lines.append("### Architecture Fixes")
    lines.append("4. **`weight_average`** — non-associative by mathematical definition. Either:")
    lines.append("   - Change declaration to `associative=False` (honest)")
    lines.append("   - Re-implement merge to use N-way averaging instead of pairwise (makes it associative)")
    lines.append("5. **`linear`/`slerp`** — sequential pairwise interpolation is non-associative. Already correctly declared.")
    lines.append("6. **Stochastic strategies** (`dare`, `della`, `dare_ties`) — non-deterministic by design. Mark clearly as non-CRDT.")
    lines.append("7. **Rename `ModelCRDT`** — most strategies are NOT CRDTs. Consider `ModelMerge` to avoid false guarantees.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by crdt-merge v0.8.0 granular diagnostic suite*")
    
    return "\n".join(lines)

# ════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    report = run_full_diagnostic()
    
    outdir = os.path.dirname(os.path.abspath(__file__))
    
    # JSON output
    json_path = os.path.join(outdir, "crdt_law_diagnostics.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n✅ JSON → {json_path}")
    
    # Markdown report
    md = generate_markdown_report(report)
    md_path = os.path.join(outdir, "CRDT_LAW_DIAGNOSTICS.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"✅ Report → {md_path}")
    
    # Exit code: non-zero if any bugs confirmed
    bugs = report.get("bug_regression_tests", {})
    any_bugs = any(
        isinstance(v, dict) and v.get("bug_confirmed")
        for v in bugs.values()
    )
    sys.exit(1 if any_bugs else 0)
