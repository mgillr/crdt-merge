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

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
crdt-merge v0.3.0 — Absolute Ceiling Stress Tests
===================================================
Progressive scale testing across ALL modules to find exact breaking points.
"""
import time, sys, gc, json, traceback
import tracemalloc
from contextlib import contextmanager

RESULTS = []

def record(suite, test, scale, metric, value, unit, notes=""):
    r = {"suite": suite, "test": test, "scale": scale,
         "metric": metric, "value": round(value, 4), "unit": unit, "notes": notes}
    RESULTS.append(r)
    print(f"  [{suite}] {test} @ {scale:,}: {metric}={value:.4f} {unit} {notes}")

@contextmanager
def mem_track():
    gc.collect()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    yield lambda: (tracemalloc.get_traced_memory()[1] - baseline) / (1024*1024)
    tracemalloc.stop()

def gen_rows(n, prefix="a", fields=5):
    return [dict(_id=f"{prefix}_{i}", _ts=float(i), **{f"f{j}": f"v_{prefix}_{i}_{j}" for j in range(fields)}) for i in range(n)]

def gen_conflict_pair(n, overlap=0.5):
    olap = int(n * overlap)
    uniq = n - olap
    a = [{"_id": f"r_{i}", "_ts": float(i), "val": f"a_{i}", "score": i%100, "tags": f"t{i%10}"} for i in range(n)]
    b = [{"_id": f"new_{i}", "_ts": float(i+n), "val": f"b_{i}", "score": (i+50)%100, "tags": f"t{(i+5)%10}"} for i in range(uniq)]
    b += [{"_id": f"r_{i}", "_ts": float(i+n), "val": f"b_c_{i}", "score": (i+25)%100, "tags": f"t{(i+3)%10}"} for i in range(olap)]
    return a, b

# =============================================================
# SUITE 1: CORE merge() — list-of-dicts mode
# =============================================================
def test_core_merge():
    from crdt_merge import merge
    print("\n" + "="*60)
    print("SUITE 1: CORE merge() — Progressive Scale")
    print("="*60)
    
    scales = [1_000, 5_000, 10_000, 50_000, 100_000, 200_000, 500_000]
    for n in scales:
        gc.collect()
        a, b = gen_conflict_pair(n)
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                result = merge(a, b, key="_id", timestamp_col="_ts")
                elapsed = time.perf_counter() - t0
                mb = peak()
                tp = (len(a)+len(b)) / elapsed
                record("core", "merge", n, "time_sec", elapsed, "s")
                record("core", "merge", n, "throughput", tp, "rows/s")
                record("core", "merge", n, "peak_mb", mb, "MB")
                record("core", "merge", n, "output_rows", len(result), "rows")
            except MemoryError:
                record("core", "merge", n, "status", 0, "OOM"); break
            except Exception as e:
                record("core", "merge", n, "status", 0, "ERROR", str(e)[:120]); break
        del a, b
        try: del result
        except: pass
        gc.collect()
        if mb > 1024: break

# =============================================================
# SUITE 2: STRATEGIES — MergeSchema.resolve_row at scale
# =============================================================
def test_strategies():
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority
    print("\n" + "="*60)
    print("SUITE 2: STRATEGIES — Schema Resolution")
    print("="*60)
    
    schema = MergeSchema(default=LWW(), score=MaxWins(), tags=UnionSet(","), 
                         status=Priority(["draft","review","approved","published"]))
    
    scales = [1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
    for n in scales:
        gc.collect()
        ra = [{"_id": f"r_{i}", "_ts": float(i), "val": f"a_{i}", "score": i%100, "tags": f"t{i%5}", "status": "draft"} for i in range(n)]
        rb = [{"_id": f"r_{i}", "_ts": float(i+n), "val": f"b_{i}", "score": (i+50)%100, "tags": f"t{(i+3)%5}", "status": "review"} for i in range(n)]
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                merged = [schema.resolve_row(a, b, timestamp_col="_ts") for a, b in zip(ra, rb)]
                elapsed = time.perf_counter() - t0
                mb = peak()
                record("strategies", "resolve_row", n, "time_sec", elapsed, "s")
                record("strategies", "resolve_row", n, "throughput", n/elapsed, "rows/s")
                record("strategies", "resolve_row", n, "peak_mb", mb, "MB")
                # Verify correctness
                assert merged[0]["status"] == "review", "Priority failed"
                record("strategies", "resolve_row", n, "correct", 1, "bool")
            except MemoryError:
                record("strategies", "resolve_row", n, "status", 0, "OOM"); break
            except Exception as e:
                record("strategies", "resolve_row", n, "status", 0, "ERROR", str(e)[:120]); break
        del ra, rb, merged; gc.collect()
        if mb > 1024: break

# =============================================================
# SUITE 3: STREAMING merge_stream — O(batch) proof
# =============================================================
def test_streaming():
    from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats
    print("\n" + "="*60)
    print("SUITE 3: STREAMING merge_stream — O(batch) Proof")
    print("="*60)
    
    scales = [10_000, 50_000, 100_000, 200_000, 500_000]
    for n in scales:
        gc.collect()
        a, b = gen_conflict_pair(n)
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                stats = StreamStats()
                out = []
                for batch in merge_stream(a, b, key="_id", timestamp_col="_ts", batch_size=5000, stats=stats):
                    out.extend(batch)
                elapsed = time.perf_counter() - t0
                mb = peak()
                record("streaming", "merge_stream", n, "time_sec", elapsed, "s")
                record("streaming", "merge_stream", n, "throughput", (len(a)+len(b))/elapsed, "rows/s")
                record("streaming", "merge_stream", n, "peak_mb", mb, "MB")
                record("streaming", "merge_stream", n, "output_rows", len(out), "rows")
                record("streaming", "merge_stream", n, "batches", stats.batches_processed, "batches")
            except MemoryError:
                record("streaming", "merge_stream", n, "status", 0, "OOM"); break
            except Exception as e:
                record("streaming", "merge_stream", n, "status", 0, "ERROR", str(e)[:120]); break
        del a, b, out; gc.collect()
        if mb > 1024: break
    
    # SORTED STREAM
    print("\n  --- merge_sorted_stream ---")
    scales2 = [10_000, 50_000, 100_000, 500_000, 1_000_000]
    for n in scales2:
        gc.collect()
        da = [{"_id": f"r_{i:08d}", "_ts": float(i), "v": f"a_{i}"} for i in range(0, n*2, 2)]
        db = [{"_id": f"r_{i:08d}", "_ts": float(i+1), "v": f"b_{i}"} for i in range(0, n*2, 2)]
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                stats = StreamStats()
                count = 0
                for batch in merge_sorted_stream(iter(da), iter(db), key="_id", timestamp_col="_ts", stats=stats):
                    count += len(batch)
                elapsed = time.perf_counter() - t0
                mb = peak()
                record("sorted_stream", "merge_sorted", n, "time_sec", elapsed, "s")
                record("sorted_stream", "merge_sorted", n, "throughput", (len(da)+len(db))/elapsed, "rows/s")
                record("sorted_stream", "merge_sorted", n, "peak_mb", mb, "MB")
                record("sorted_stream", "merge_sorted", n, "output_rows", count, "rows")
            except MemoryError:
                record("sorted_stream", "merge_sorted", n, "status", 0, "OOM"); break
            except Exception as e:
                record("sorted_stream", "merge_sorted", n, "status", 0, "ERROR", str(e)[:120]); break
        del da, db; gc.collect()
        if mb > 1024: break

# =============================================================
# SUITE 4: BATCH TUNING — optimal batch_size at 100K
# =============================================================
def test_batch_tuning():
    from crdt_merge.streaming import merge_stream, StreamStats
    print("\n" + "="*60)
    print("SUITE 4: BATCH SIZE TUNING @ 100K rows")
    print("="*60)
    
    N = 100_000
    a, b = gen_conflict_pair(N)
    for bs in [100, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000]:
        gc.collect()
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                stats = StreamStats()
                ct = 0
                for batch in merge_stream(a, b, key="_id", timestamp_col="_ts", batch_size=bs, stats=stats):
                    ct += len(batch)
                elapsed = time.perf_counter() - t0
                mb = peak()
                record("batch_tune", f"bs_{bs}", N, "time_sec", elapsed, "s")
                record("batch_tune", f"bs_{bs}", N, "throughput", (len(a)+len(b))/elapsed, "rows/s")
                record("batch_tune", f"bs_{bs}", N, "peak_mb", mb, "MB")
                record("batch_tune", f"bs_{bs}", N, "batches", stats.batches_processed, "batches")
            except Exception as e:
                record("batch_tune", f"bs_{bs}", N, "status", 0, "ERROR", str(e)[:120])
    del a, b; gc.collect()

# =============================================================
# SUITE 5: VERIFICATION — CRDT property proof throughput
# =============================================================
def test_verification():
    from crdt_merge.verify import verify_crdt, verify_commutative, verify_associative, verify_idempotent
    from crdt_merge import merge
    print("\n" + "="*60)
    print("SUITE 5: VERIFICATION — Property Proof Throughput")
    print("="*60)
    
    counter = [0]
    def my_merge(a, b):
        return merge(a, b, key="_id", timestamp_col="_ts")
    def gen_ds():
        counter[0] += 1
        return gen_rows(20, prefix=f"g{counter[0]}", fields=3)
    
    for trials in [10, 50, 100, 500]:
        gc.collect()
        t0 = time.perf_counter()
        try:
            result = verify_crdt(my_merge, gen_fn=gen_ds, trials=trials)
            elapsed = time.perf_counter() - t0
            all_ok = result.commutativity.passed and result.associativity.passed and result.idempotency.passed
            record("verify", f"full_{trials}", trials, "time_sec", elapsed, "s")
            record("verify", f"full_{trials}", trials, "throughput", trials/elapsed, "trials/s")
            record("verify", f"full_{trials}", trials, "all_passed", 1 if all_ok else 0, "bool")
        except Exception as e:
            record("verify", f"full_{trials}", trials, "status", 0, "ERROR", str(e)[:120])

# =============================================================
# SUITE 6: DELTA SYNC — compute_delta + apply_delta at scale
# =============================================================
def test_delta():
    from crdt_merge.delta import compute_delta, apply_delta, compose_deltas, Delta
    print("\n" + "="*60)
    print("SUITE 6: DELTA SYNC — Compute + Apply + Compose")
    print("="*60)
    
    scales = [1_000, 10_000, 50_000, 100_000, 500_000]
    for n in scales:
        gc.collect()
        old = gen_rows(n, "old", 5)
        # Modify 30%, add 10%, remove 10%
        new = list(old)
        mod_count = n // 3
        for i in range(mod_count):
            new[i] = {**new[i], "f0": f"MODIFIED_{i}"}
        add_count = n // 10
        for i in range(add_count):
            new.append({"_id": f"added_{i}", "_ts": float(n+i), **{f"f{j}": f"new_{i}_{j}" for j in range(5)}})
        # remove 10%
        new = new[n//10:]
        
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                delta = compute_delta(old, new, key="_id", source_node="test")
                elapsed_compute = time.perf_counter() - t0
                
                t1 = time.perf_counter()
                result = apply_delta(old, delta, key="_id")
                elapsed_apply = time.perf_counter() - t1
                mb = peak()
                
                record("delta", "compute", n, "time_sec", elapsed_compute, "s")
                record("delta", "compute", n, "throughput", n/elapsed_compute, "rows/s")
                record("delta", "apply", n, "time_sec", elapsed_apply, "s")
                record("delta", "apply", n, "throughput", n/elapsed_apply, "rows/s")
                record("delta", "combined", n, "peak_mb", mb, "MB")
                added = len(delta.added) if delta.added else 0
                modified = len(delta.modified) if delta.modified else 0
                removed = len(delta.removed) if delta.removed else 0
                record("delta", "delta_size", n, "added", added, "rows")
                record("delta", "delta_size", n, "modified", modified, "rows")
                record("delta", "delta_size", n, "removed", removed, "rows")
            except MemoryError:
                record("delta", "combined", n, "status", 0, "OOM"); break
            except Exception as e:
                record("delta", "combined", n, "status", 0, "ERROR", str(e)[:120]); break
        del old, new; gc.collect()
        if mb > 1024: break
    
    # Compose deltas
    print("\n  --- compose_deltas ---")
    for num_deltas in [5, 10, 50]:
        gc.collect()
        deltas = []
        for i in range(num_deltas):
            d = compute_delta(
                gen_rows(1000, f"c{i}", 3),
                gen_rows(1000, f"c{i+1}", 3),
                key="_id", source_node=f"node_{i}"
            )
            deltas.append(d)
        t0 = time.perf_counter()
        composed = compose_deltas(*deltas)
        elapsed = time.perf_counter() - t0
        record("delta_compose", f"compose_{num_deltas}", num_deltas, "time_sec", elapsed, "s")

# =============================================================
# SUITE 7: JSON MERGE — Deep nested structures
# =============================================================
def test_json_merge():
    from crdt_merge import merge_dicts
    print("\n" + "="*60)
    print("SUITE 7: JSON MERGE — Deep Nested Structures")
    print("="*60)
    
    def nested(depth, breadth, pfx):
        if depth == 0: return f"{pfx}_leaf"
        return {f"k{i}": nested(depth-1, breadth, f"{pfx}_{i}") for i in range(breadth)}
    
    for depth, breadth, label in [(3,3,"3x3"),(4,3,"4x3"),(5,3,"5x3"),(3,5,"3x5"),(4,5,"4x5"),(5,5,"5x5"),(6,4,"6x4"),(7,3,"7x3")]:
        gc.collect()
        a, b = nested(depth, breadth, "a"), nested(depth, breadth, "b")
        t0 = time.perf_counter()
        try:
            result = merge_dicts(a, b)
            elapsed = time.perf_counter() - t0
            leaves = breadth ** depth
            record("json", f"nested_{label}", leaves, "time_sec", elapsed, "s")
            record("json", f"nested_{label}", leaves, "throughput", leaves/elapsed, "leaves/s")
        except RecursionError:
            record("json", f"nested_{label}", breadth**depth, "status", 0, "RECURSION"); break
        except Exception as e:
            record("json", f"nested_{label}", breadth**depth, "status", 0, "ERROR", str(e)[:80])

# =============================================================
# SUITE 8: FUZZY DEDUP — O(n²) ceiling
# =============================================================
def test_dedup():
    from crdt_merge import dedup_records
    print("\n" + "="*60)
    print("SUITE 8: FUZZY DEDUP — O(n²) Ceiling")
    print("="*60)
    
    scales = [100, 500, 1_000, 2_000, 5_000, 10_000]
    for n in scales:
        gc.collect()
        rows = [{"_id": f"r_{i}", "name": f"Product {i} {'Premium' if i%3==0 else 'Standard'}"} for i in range(n)]
        rows += [{"_id": f"dup_{i}", "name": f"Product {i} Premiumm"} for i in range(n//5)]
        
        with mem_track() as peak:
            t0 = time.perf_counter()
            try:
                result, removed = dedup_records(rows, columns=["name"], method="fuzzy", threshold=0.8)
                elapsed = time.perf_counter() - t0
                mb = peak()
                record("dedup", "fuzzy", n, "time_sec", elapsed, "s")
                record("dedup", "fuzzy", n, "throughput", len(rows)/elapsed, "rows/s")
                record("dedup", "fuzzy", n, "peak_mb", mb, "MB")
                record("dedup", "fuzzy", n, "removed", removed, "dupes")
            except Exception as e:
                record("dedup", "fuzzy", n, "status", 0, "ERROR", str(e)[:120]); break
        del rows; gc.collect()
        if elapsed > 30:
            record("dedup", "fuzzy", n, "ceiling", elapsed, "s", "stopped: >30s"); break

# =============================================================
# RUN ALL
# =============================================================
if __name__ == "__main__":
    print("="*60)
    print("crdt-merge v0.3.0 — ABSOLUTE CEILING STRESS TESTS")
    print(f"Python: {sys.version}")
    print("="*60)
    
    for name, fn in [("Core Merge", test_core_merge), ("Strategies", test_strategies),
                     ("Streaming", test_streaming), ("Batch Tuning", test_batch_tuning),
                     ("Verification", test_verification), ("Delta Sync", test_delta),
                     ("JSON Merge", test_json_merge), ("Fuzzy Dedup", test_dedup)]:
        try:
            fn()
        except Exception as e:
            print(f"\n*** SUITE {name} CRASHED: {e} ***")
            traceback.print_exc()
    
    with open("/tmp/crdt_merge_stress_results.json", "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(RESULTS)} measurements saved")
    print("="*60)
