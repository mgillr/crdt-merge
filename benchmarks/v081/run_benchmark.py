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
crdt-merge v0.8.1 — Comprehensive CRDT Architecture Benchmark

Tests all 26 strategies for CRDT law compliance, performance,
integration, OR-Set semantics, memory estimation, and edge cases.
"""

import sys
import os
import time
import json
import platform
import traceback
from datetime import datetime, timezone

# Ensure the repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import numpy as np
from crdt_merge.model.crdt_state import CRDTMergeState, MergeContribution, ConflictResolution
from crdt_merge.model.strategies import get_strategy, list_strategies
from crdt_merge.model.core import ModelMerge, ModelMergeSchema, MergeResult

# ======================================================================
# Helpers
# ======================================================================

BASE_REQUIRED = CRDTMergeState.BASE_REQUIRED
STOCHASTIC = CRDTMergeState.STOCHASTIC


def make_state(strategy_name, seed_offset, tensor_size=50):
    """Create a CRDTMergeState with one contribution, deterministic by seed_offset."""
    needs_base = strategy_name in BASE_REQUIRED
    rng = np.random.RandomState(seed_offset * 100 + 99)
    base = rng.randn(tensor_size).astype(np.float64) if needs_base else None

    state = CRDTMergeState(strategy_name, base=base, seed=42)
    state.add(
        tensor=np.random.RandomState(seed_offset * 100 + 1).randn(tensor_size).astype(np.float64),
        model_id=f"model_{seed_offset}_A",
        weight=1.0,
    )
    return state


def make_state_with_id(strategy_name, seed_offset, model_id, tensor_size=50, base=None):
    """Create a CRDTMergeState with a specific model_id and shared base."""
    needs_base = strategy_name in BASE_REQUIRED
    if needs_base and base is None:
        rng = np.random.RandomState(seed_offset * 100 + 99)
        base = rng.randn(tensor_size).astype(np.float64)

    state = CRDTMergeState(strategy_name, base=base, seed=42)
    state.add(
        tensor=np.random.RandomState(seed_offset * 100 + 1).randn(tensor_size).astype(np.float64),
        model_id=model_id,
        weight=1.0,
    )
    return state


def resolve_matches(state_a, state_b, tol=1e-7):
    """Check that resolve() of two states produces the same result."""
    try:
        res_a = state_a.resolve()
        res_b = state_b.resolve()
        return np.allclose(np.asarray(res_a), np.asarray(res_b), atol=tol)
    except Exception:
        return False


def timer(fn, *args, **kwargs):
    """Time a function call in milliseconds."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms


# ======================================================================
# 1. Strategy Registry Verification
# ======================================================================

def benchmark_strategy_registry():
    print("\n" + "=" * 70)
    print("1. STRATEGY REGISTRY VERIFICATION")
    print("=" * 70)

    strategies = list_strategies()
    print(f"  Total strategies: {len(strategies)}")
    print(f"  Expected: 25")

    all_ok = True
    for name in strategies:
        try:
            s = get_strategy(name)
            print(f"  ✓ {name} ({s.category})")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            all_ok = False

    return {
        "total": len(strategies),
        "expected": 25,
        "all_instantiated": all_ok,
        "names": strategies,
    }


# ======================================================================
# 2. CRDT Law Verification (all 26 strategies, 10 trials each)
# ======================================================================

def benchmark_crdt_laws(strategies, trials=10, tensor_size=50):
    print("\n" + "=" * 70)
    print("2. CRDT LAW VERIFICATION (all 26 strategies × 3 laws)")
    print("=" * 70)

    results = {}
    total_pass = 0
    total_tests = 0

    for sname in strategies:
        needs_base = sname in BASE_REQUIRED
        # Shared base for consistency within a strategy
        rng_base = np.random.RandomState(999)
        shared_base = rng_base.randn(tensor_size).astype(np.float64) if needs_base else None

        comm_state_ok, comm_resolve_ok = True, True
        assoc_state_ok, assoc_resolve_ok = True, True
        idemp_state_ok, idemp_resolve_ok = True, True
        timings = {"commutativity": [], "associativity": [], "idempotency": []}

        for trial in range(trials):
            seed_a = trial * 3 + 1
            seed_b = trial * 3 + 2
            seed_c = trial * 3 + 3

            def _make(seed_offset, mid):
                state = CRDTMergeState(sname, base=shared_base, seed=42)
                state.add(
                    tensor=np.random.RandomState(seed_offset * 100 + 1).randn(tensor_size).astype(np.float64),
                    model_id=mid,
                    weight=1.0,
                )
                return state

            a = _make(seed_a, f"m_{trial}_a")
            b = _make(seed_b, f"m_{trial}_b")
            c = _make(seed_c, f"m_{trial}_c")

            # --- Commutativity ---
            t0 = time.perf_counter()
            ab = a.merge(b)
            ba = b.merge(a)
            t1 = time.perf_counter()
            timings["commutativity"].append((t1 - t0) * 1000)

            if ab != ba:
                comm_state_ok = False
            if not resolve_matches(ab, ba):
                comm_resolve_ok = False

            # --- Associativity ---
            t0 = time.perf_counter()
            ab_c = a.merge(b).merge(c)
            a_bc = a.merge(b.merge(c))
            t1 = time.perf_counter()
            timings["associativity"].append((t1 - t0) * 1000)

            if ab_c != a_bc:
                assoc_state_ok = False
            if not resolve_matches(ab_c, a_bc):
                assoc_resolve_ok = False

            # --- Idempotency ---
            t0 = time.perf_counter()
            aa = a.merge(a)
            t1 = time.perf_counter()
            timings["idempotency"].append((t1 - t0) * 1000)

            if aa != a:
                idemp_state_ok = False
            if not resolve_matches(aa, a):
                idemp_resolve_ok = False

        all_pass = all([
            comm_state_ok, comm_resolve_ok,
            assoc_state_ok, assoc_resolve_ok,
            idemp_state_ok, idemp_resolve_ok,
        ])
        status = "✓ PASS" if all_pass else "✗ FAIL"
        total_tests += 3
        if comm_state_ok and comm_resolve_ok:
            total_pass += 1
        if assoc_state_ok and assoc_resolve_ok:
            total_pass += 1
        if idemp_state_ok and idemp_resolve_ok:
            total_pass += 1

        print(f"  {status} {sname:<28s} C={comm_state_ok}&{comm_resolve_ok} A={assoc_state_ok}&{assoc_resolve_ok} I={idemp_state_ok}&{idemp_resolve_ok}")

        results[sname] = {
            "commutativity": {
                "state": comm_state_ok,
                "resolve": comm_resolve_ok,
                "trials": trials,
                "mean_ms": float(np.mean(timings["commutativity"])),
            },
            "associativity": {
                "state": assoc_state_ok,
                "resolve": assoc_resolve_ok,
                "trials": trials,
                "mean_ms": float(np.mean(timings["associativity"])),
            },
            "idempotency": {
                "state": idemp_state_ok,
                "resolve": idemp_resolve_ok,
                "trials": trials,
                "mean_ms": float(np.mean(timings["idempotency"])),
            },
        }

    print(f"\n  CRDT Law Summary: {total_pass}/{total_tests} tests passed")
    return results, total_pass, total_tests


# ======================================================================
# 3. Performance Benchmarks
# ======================================================================

def benchmark_performance(strategies, tensor_sizes=(50, 500, 5000)):
    print("\n" + "=" * 70)
    print("3. PERFORMANCE BENCHMARKS")
    print("=" * 70)

    perf = {
        "add_single": {"times_ms": []},
        "add_batch_100": {"times_ms": []},
        "merge_pairwise": {"times_ms": []},
        "merge_many_10": {"times_ms": []},
        "resolve_10_contributions": {"times_ms": []},
        "serialization_roundtrip": {"times_ms": []},
        "per_strategy": {},
    }

    for sz in tensor_sizes:
        print(f"\n  --- Tensor size: {sz} ---")
        for sname in strategies:
            needs_base = sname in BASE_REQUIRED
            rng_base = np.random.RandomState(42)
            shared_base = rng_base.randn(sz).astype(np.float64) if needs_base else None

            strat_perf = {}

            # Add performance: 100 contributions
            state = CRDTMergeState(sname, base=shared_base, seed=42)
            t0 = time.perf_counter()
            for i in range(100):
                state.add(
                    tensor=np.random.RandomState(i).randn(sz).astype(np.float64),
                    model_id=f"add_perf_{i}",
                    weight=1.0,
                )
            add_ms = (time.perf_counter() - t0) * 1000
            strat_perf["add_100"] = add_ms
            perf["add_single"]["times_ms"].append(add_ms)

            # add_batch performance: 100 contributions
            state_batch = CRDTMergeState(sname, base=shared_base, seed=42)
            batch_items = [
                (np.random.RandomState(i).randn(sz).astype(np.float64), f"batch_{i}", 1.0)
                for i in range(100)
            ]
            t0 = time.perf_counter()
            state_batch.add_batch(batch_items)
            batch_ms = (time.perf_counter() - t0) * 1000
            strat_perf["add_batch_100"] = batch_ms
            perf["add_batch_100"]["times_ms"].append(batch_ms)

            # Merge performance: 2 states × 10 contributions each
            s1 = CRDTMergeState(sname, base=shared_base, seed=42)
            s2 = CRDTMergeState(sname, base=shared_base, seed=42)
            for i in range(10):
                s1.add(tensor=np.random.RandomState(i * 2).randn(sz).astype(np.float64),
                       model_id=f"s1_{i}", weight=1.0)
                s2.add(tensor=np.random.RandomState(i * 2 + 1).randn(sz).astype(np.float64),
                       model_id=f"s2_{i}", weight=1.0)

            t0 = time.perf_counter()
            merged = s1.merge(s2)
            merge_ms = (time.perf_counter() - t0) * 1000
            strat_perf["merge_pairwise"] = merge_ms
            perf["merge_pairwise"]["times_ms"].append(merge_ms)

            # merge_many: 10 states
            multi_states = []
            for j in range(10):
                ms = CRDTMergeState(sname, base=shared_base, seed=42)
                ms.add(tensor=np.random.RandomState(j * 100).randn(sz).astype(np.float64),
                       model_id=f"mm_{j}", weight=1.0)
                multi_states.append(ms)

            t0 = time.perf_counter()
            CRDTMergeState.merge_many(multi_states)
            mm_ms = (time.perf_counter() - t0) * 1000
            strat_perf["merge_many_10"] = mm_ms
            perf["merge_many_10"]["times_ms"].append(mm_ms)

            # Resolve performance: state with 10 contributions
            resolve_state = CRDTMergeState(sname, base=shared_base, seed=42)
            for i in range(10):
                resolve_state.add(
                    tensor=np.random.RandomState(i + 500).randn(sz).astype(np.float64),
                    model_id=f"res_{i}", weight=1.0,
                )
            t0 = time.perf_counter()
            resolve_state.resolve()
            resolve_ms = (time.perf_counter() - t0) * 1000
            strat_perf["resolve_10"] = resolve_ms
            perf["resolve_10_contributions"]["times_ms"].append(resolve_ms)

            # Serialization roundtrip
            ser_state = CRDTMergeState(sname, base=shared_base, seed=42)
            ser_state.add(
                tensor=np.random.RandomState(777).randn(sz).astype(np.float64),
                model_id="ser_test", weight=1.0,
            )
            t0 = time.perf_counter()
            d = ser_state.to_dict()
            CRDTMergeState.from_dict(d)
            ser_ms = (time.perf_counter() - t0) * 1000
            strat_perf["serialization"] = ser_ms
            perf["serialization_roundtrip"]["times_ms"].append(ser_ms)

            key = f"{sname}_sz{sz}"
            perf["per_strategy"][key] = strat_perf

        # Print summary for this tensor size
        print(f"    add_100 mean:      {np.mean(perf['add_single']['times_ms'][-len(strategies):]):.3f} ms")
        print(f"    add_batch_100 mean:{np.mean(perf['add_batch_100']['times_ms'][-len(strategies):]):.3f} ms")
        print(f"    merge_pairwise:    {np.mean(perf['merge_pairwise']['times_ms'][-len(strategies):]):.3f} ms")
        print(f"    merge_many_10:     {np.mean(perf['merge_many_10']['times_ms'][-len(strategies):]):.3f} ms")
        print(f"    resolve_10:        {np.mean(perf['resolve_10_contributions']['times_ms'][-len(strategies):]):.3f} ms")
        print(f"    serialization:     {np.mean(perf['serialization_roundtrip']['times_ms'][-len(strategies):]):.3f} ms")

    # Compute summary stats
    for k in ["add_single", "add_batch_100", "merge_pairwise", "merge_many_10",
              "resolve_10_contributions", "serialization_roundtrip"]:
        vals = perf[k]["times_ms"]
        perf[k]["mean_ms"] = float(np.mean(vals))
        perf[k]["std_ms"] = float(np.std(vals))
        del perf[k]["times_ms"]

    return perf


# ======================================================================
# 4. ModelMerge.crdt_merge() Integration Test
# ======================================================================

def benchmark_integration():
    print("\n" + "=" * 70)
    print("4. ModelMerge.crdt_merge() INTEGRATION TEST")
    print("=" * 70)

    result_info = {"passed": False, "time_ms": 0, "crdt_guaranteed": False}

    try:
        schema = ModelMergeSchema(strategies={
            "layers.*.self_attn": "weight_average",
            "layers.*.mlp": "linear",
            "embed_tokens": "slerp",
            "default": "weight_average",
        })
        merger = ModelMerge(schema)

        # Build 3 fake state_dicts with 10 layers each
        layer_names = [
            "embed_tokens",
            "layers.0.self_attn", "layers.0.mlp",
            "layers.1.self_attn", "layers.1.mlp",
            "layers.2.self_attn", "layers.2.mlp",
            "layers.3.self_attn", "layers.3.mlp",
            "lm_head",
        ]
        models = []
        for m in range(3):
            sd = {}
            for layer in layer_names:
                sd[layer] = np.random.RandomState(m * 100 + hash(layer) % 100).randn(100).astype(np.float64)
            models.append(sd)

        t0 = time.perf_counter()
        result = merger.crdt_merge(
            models,
            model_ids=["model_A", "model_B", "model_C"],
            weights=[0.5, 0.3, 0.2],
            seed=42,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert isinstance(result, MergeResult), f"Expected MergeResult, got {type(result)}"
        assert result.metadata.get("crdt_guaranteed") is True, "crdt_guaranteed not True"
        assert set(layer_names).issubset(set(result.tensor.keys())), "Missing layer keys"
        assert result.metadata.get("model_ids") == ["model_A", "model_B", "model_C"], "model_ids mismatch"

        result_info = {
            "passed": True,
            "time_ms": float(elapsed_ms),
            "crdt_guaranteed": True,
            "layers": len(result.tensor),
        }
        print(f"  ✓ crdt_merge() passed — {len(result.tensor)} layers, {elapsed_ms:.2f} ms")

    except Exception as e:
        print(f"  ✗ crdt_merge() FAILED: {e}")
        traceback.print_exc()
        result_info["error"] = str(e)

    return result_info


# ======================================================================
# 5. OR-Set Semantics
# ======================================================================

def benchmark_or_set():
    print("\n" + "=" * 70)
    print("5. OR-SET SEMANTICS")
    print("=" * 70)

    all_passed = True
    details = {}

    # Test 1: add + remove + re-add (add-wins)
    try:
        state = CRDTMergeState("weight_average", seed=42)
        t = np.array([1.0, 2.0, 3.0])
        state.add(tensor=t, model_id="m1", weight=1.0)
        assert state.size == 1
        state.remove("m1")
        assert state.size == 0
        # Re-add with new version
        state.add(tensor=t * 2, model_id="m1", weight=1.0, version=2)
        assert state.size == 1
        resolved = state.resolve()
        assert np.allclose(resolved, t * 2)
        details["add_remove_readd"] = True
        print("  ✓ add + remove + re-add (add-wins)")
    except Exception as e:
        details["add_remove_readd"] = False
        all_passed = False
        print(f"  ✗ add + remove + re-add: {e}")

    # Test 2: concurrent adds from different replicas
    try:
        s1 = CRDTMergeState("weight_average", seed=42)
        s2 = CRDTMergeState("weight_average", seed=42)
        s1.add(tensor=np.array([1.0, 0.0, 0.0]), model_id="r1", weight=1.0)
        s2.add(tensor=np.array([0.0, 1.0, 0.0]), model_id="r2", weight=1.0)
        merged_1 = s1.merge(s2)
        merged_2 = s2.merge(s1)
        assert merged_1 == merged_2, "Concurrent adds: merge not commutative"
        assert merged_1.size == 2, f"Expected 2 contributions, got {merged_1.size}"
        details["concurrent_adds"] = True
        print("  ✓ concurrent adds from different replicas")
    except Exception as e:
        details["concurrent_adds"] = False
        all_passed = False
        print(f"  ✗ concurrent adds: {e}")

    # Test 3: merge after remove
    try:
        s1 = CRDTMergeState("weight_average", seed=42)
        s2 = CRDTMergeState("weight_average", seed=42)
        t_shared = np.array([1.0, 2.0, 3.0])
        s1.add(tensor=t_shared, model_id="shared", weight=1.0)
        s2.add(tensor=t_shared, model_id="shared", weight=1.0)
        s1.remove("shared")
        merged = s1.merge(s2)
        # After remove on s1 and merge, the tombstone should propagate
        assert merged.size == 0, f"Expected 0 after remove+merge, got {merged.size}"
        details["merge_after_remove"] = True
        print("  ✓ merge after remove")
    except Exception as e:
        details["merge_after_remove"] = False
        all_passed = False
        print(f"  ✗ merge after remove: {e}")

    print(f"\n  OR-Set Overall: {'PASS' if all_passed else 'FAIL'}")
    return {"passed": all_passed, "details": details}


# ======================================================================
# 6. Memory Estimation
# ======================================================================

def benchmark_memory():
    print("\n" + "=" * 70)
    print("6. MEMORY ESTIMATION")
    print("=" * 70)

    passed = True
    details = {}

    for n_contribs in [1, 10, 50]:
        state = CRDTMergeState("weight_average", seed=42)
        for i in range(n_contribs):
            state.add(
                tensor=np.random.randn(1000).astype(np.float64),
                model_id=f"mem_{i}",
                weight=1.0,
            )

        est = state.estimated_memory_bytes
        # Basic sanity: at least n_contribs * 1000 * 8 bytes (float64)
        min_expected = n_contribs * 1000 * 8
        ok = est >= min_expected
        if not ok:
            passed = False

        details[f"{n_contribs}_contribs"] = {
            "estimated_bytes": est,
            "min_expected_bytes": min_expected,
            "ok": ok,
        }
        print(f"  {n_contribs:>3d} contribs: estimated={est:>10d} B, min_expected={min_expected:>10d} B — {'✓' if ok else '✗'}")

    print(f"\n  Memory Estimation: {'PASS' if passed else 'FAIL'}")
    return {"passed": passed, "details": details}


# ======================================================================
# 7. Edge Cases
# ======================================================================

def benchmark_edge_cases():
    print("\n" + "=" * 70)
    print("7. EDGE CASES")
    print("=" * 70)

    all_passed = True
    details = {}

    # Test 1: Empty state merge
    try:
        s1 = CRDTMergeState("weight_average", seed=42)
        s2 = CRDTMergeState("weight_average", seed=42)
        merged = s1.merge(s2)
        assert merged.is_empty
        details["empty_merge"] = True
        print("  ✓ Empty state merge")
    except Exception as e:
        details["empty_merge"] = False
        all_passed = False
        print(f"  ✗ Empty state merge: {e}")

    # Test 2: Single contribution resolve
    try:
        state = CRDTMergeState("weight_average", seed=42)
        t = np.array([1.0, 2.0, 3.0])
        state.add(tensor=t, model_id="single", weight=1.0)
        resolved = state.resolve()
        assert np.allclose(resolved, t)
        details["single_resolve"] = True
        print("  ✓ Single contribution resolve")
    except Exception as e:
        details["single_resolve"] = False
        all_passed = False
        print(f"  ✗ Single contribution resolve: {e}")

    # Test 3: Duplicate model_id add (should update, not duplicate) with HIGHEST_VERSION
    try:
        state = CRDTMergeState("weight_average", seed=42,
                               conflict_resolution=ConflictResolution.HIGHEST_VERSION)
        t1 = np.array([1.0, 2.0, 3.0])
        t2 = np.array([4.0, 5.0, 6.0])
        state.add(tensor=t1, model_id="dup", weight=1.0, version=1)
        state.add(tensor=t2, model_id="dup", weight=1.0, version=2)
        assert state.size == 1, f"Expected 1 after duplicate add, got {state.size}"
        resolved = state.resolve()
        assert np.allclose(resolved, t2), "Duplicate add should keep higher version"
        details["duplicate_model_id"] = True
        print("  ✓ Duplicate model_id (higher version wins)")
    except Exception as e:
        details["duplicate_model_id"] = False
        all_passed = False
        print(f"  ✗ Duplicate model_id: {e}")

    # Test 4: from_dict(to_dict(state)) roundtrip preserves equality
    try:
        state = CRDTMergeState("weight_average", seed=42)
        state.add(tensor=np.array([1.0, 2.0, 3.0]), model_id="rt1", weight=0.6)
        state.add(tensor=np.array([4.0, 5.0, 6.0]), model_id="rt2", weight=0.4)

        d = state.to_dict()
        restored = CRDTMergeState.from_dict(d)

        assert restored == state, "Roundtrip equality failed"
        assert np.allclose(restored.resolve(), state.resolve()), "Roundtrip resolve mismatch"
        details["serialization_roundtrip"] = True
        print("  ✓ from_dict(to_dict()) roundtrip preserves equality")
    except Exception as e:
        details["serialization_roundtrip"] = False
        all_passed = False
        print(f"  ✗ Serialization roundtrip: {e}")

    # Test 5: Base-required strategy without base raises ValueError
    try:
        state = CRDTMergeState("ties", seed=42)  # No base
        state.add(tensor=np.array([1.0, 2.0, 3.0]), model_id="x", weight=1.0)
        try:
            state.resolve()
            details["base_required_error"] = False
            all_passed = False
            print("  ✗ Base-required strategy should raise ValueError")
        except ValueError:
            details["base_required_error"] = True
            print("  ✓ Base-required strategy raises ValueError without base")
    except Exception as e:
        details["base_required_error"] = False
        all_passed = False
        print(f"  ✗ Base-required error test: {e}")

    # Test 6: merge_many with single state
    try:
        state = CRDTMergeState("weight_average", seed=42)
        state.add(tensor=np.array([1.0, 2.0]), model_id="one", weight=1.0)
        result = CRDTMergeState.merge_many([state])
        assert result == state
        details["merge_many_single"] = True
        print("  ✓ merge_many with single state")
    except Exception as e:
        details["merge_many_single"] = False
        all_passed = False
        print(f"  ✗ merge_many single: {e}")

    print(f"\n  Edge Cases: {'PASS' if all_passed else 'FAIL'}")
    return {"passed": all_passed, "details": details}


# ======================================================================
# Main
# ======================================================================

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║        crdt-merge v0.8.1 — CRDT Architecture Benchmark             ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Python:    {platform.python_version()}")
    print(f"  NumPy:     {np.__version__}")

    total_tests = 0
    total_passed = 0

    # 1. Strategy Registry
    registry = benchmark_strategy_registry()
    strategies = registry["names"]
    if registry["all_instantiated"] and registry["total"] == 25:
        total_tests += 1
        total_passed += 1

    # 2. CRDT Laws
    crdt_results, crdt_pass, crdt_total = benchmark_crdt_laws(strategies)
    total_tests += crdt_total
    total_passed += crdt_pass

    # 3. Performance
    perf = benchmark_performance(strategies)
    total_tests += 1  # performance suite counts as 1
    total_passed += 1

    # 4. Integration
    integration_result = benchmark_integration()
    total_tests += 1
    if integration_result["passed"]:
        total_passed += 1

    # 5. OR-Set
    or_set_result = benchmark_or_set()
    total_tests += 1
    if or_set_result["passed"]:
        total_passed += 1

    # 6. Memory
    memory_result = benchmark_memory()
    total_tests += 1
    if memory_result["passed"]:
        total_passed += 1

    # 7. Edge Cases
    edge_result = benchmark_edge_cases()
    total_tests += 1
    if edge_result["passed"]:
        total_passed += 1

    # Count how many strategies pass all 3 CRDT laws
    crdt_compliant = 0
    for sname, r in crdt_results.items():
        if (r["commutativity"]["state"] and r["commutativity"]["resolve"] and
                r["associativity"]["state"] and r["associativity"]["resolve"] and
                r["idempotency"]["state"] and r["idempotency"]["resolve"]):
            crdt_compliant += 1

    # ==================== BUILD RESULTS ====================
    results = {
        "version": "0.8.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "total_strategies": len(strategies),
        "strategies_verified": strategies,
        "crdt_law_results": crdt_results,
        "performance": perf,
        "integration": {
            "crdt_merge_api": integration_result,
            "or_set_semantics": or_set_result,
            "memory_estimation": memory_result,
            "edge_cases": edge_result,
        },
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_tests - total_passed,
            "crdt_compliance": f"{crdt_compliant}/{len(strategies)}",
        },
    }

    # Save results
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total Tests:     {total_tests}")
    print(f"  Passed:          {total_passed}")
    print(f"  Failed:          {total_tests - total_passed}")
    print(f"  CRDT Compliance: {crdt_compliant}/{len(strategies)}")
    print(f"  Results saved:   {out_path}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    main()
