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
crdt-merge v0.8.0 — Benchmark Suite
====================================
Every measurement maps to a live crdt_merge.* API call.
Covers all prior-version benchmarks + all new v0.8.0 model merge features.

Outputs:
  - all_results.json     (machine-readable)
  - ANALYSIS.md          (human-readable report)
"""
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _bench(fn, label, ops=None, warmup=1, iters=3):
    """Run fn, return best-of-iters timing dict."""
    for _ in range(warmup):
        fn()
    best = float('inf')
    for _ in range(iters):
        t0 = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - t0
        best = min(best, elapsed)
    d = {"time": round(best, 6), "label": label}
    if ops:
        d["ops"] = ops
        d["ops_per_sec"] = round(ops / best)
    return d, result

def _fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.0f}K"
    return str(n)

def _make_model(layers, size=64, seed=0):
    rng = np.random.RandomState(seed)
    return {layer: rng.randn(size).tolist() for layer in layers}

def _make_model_np(layers, size=64, seed=0):
    rng = np.random.RandomState(seed)
    return {layer: rng.randn(size) for layer in layers}

def _make_adapter(modules, rank=4, in_f=8, out_f=8, seed=0):
    rng = np.random.RandomState(seed)
    return {mod: {"lora_A": rng.randn(rank, in_f), "lora_B": rng.randn(out_f, rank)} for mod in modules}

results = {"meta": {
    "version": "0.8.0",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "platform": platform.platform(),
    "python": platform.python_version(),
}}
report_lines = []

def section(title):
    report_lines.append(f"\n## {title}\n")
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def log(msg):
    report_lines.append(msg)
    print(msg)

# ═════════════════════════════════════════════════════════════════
# 1. CRDT PRIMITIVE THROUGHPUT
# ═════════════════════════════════════════════════════════════════
section("CRDT Primitive Throughput")

from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet
from crdt_merge.clocks import VectorClock

log("| Primitive | API | Ops | Ops/sec | Time |")
log("|-----------|-----|-----|---------|------|")

results["crdt_primitives"] = {}

# GCounter.increment
def bench_gcounter():
    c = GCounter()
    for i in range(1_000_000):
        c.increment("n1")
    return c
d, _ = _bench(bench_gcounter, "GCounter.increment", ops=1_000_000)
results["crdt_primitives"]["GCounter.increment"] = d
log(f"| GCounter.increment | `GCounter.increment()` | 1M | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# PNCounter.mixed
def bench_pncounter():
    c = PNCounter()
    for i in range(500_000):
        if i % 3: c.increment("n1")
        else: c.decrement("n1")
    return c
d, _ = _bench(bench_pncounter, "PNCounter.mixed", ops=500_000)
results["crdt_primitives"]["PNCounter.mixed"] = d
log(f"| PNCounter.mixed | `PNCounter.increment/decrement()` | 500K | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# VectorClock.increment
def bench_vclock():
    vc = VectorClock()
    for i in range(500_000):
        vc.increment("node_1")
    return vc
d, _ = _bench(bench_vclock, "VectorClock.increment", ops=500_000)
results["crdt_primitives"]["VectorClock.increment"] = d
log(f"| VectorClock.increment | `VectorClock.increment()` | 500K | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# LWWRegister.merge
def bench_lww():
    a = LWWRegister("a", 1.0)
    b = LWWRegister("b", 2.0)
    for i in range(200_000):
        a.merge(b)
    return a
d, _ = _bench(bench_lww, "LWWRegister.merge", ops=200_000)
results["crdt_primitives"]["LWWRegister.merge"] = d
log(f"| LWWRegister.merge | `LWWRegister.merge()` | 200K | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# ORSet.add+merge
def bench_orset():
    s = ORSet()
    for i in range(100_000):
        s.add(f"item_{i}")
    return s
d, _ = _bench(bench_orset, "ORSet.add+merge", ops=100_000)
results["crdt_primitives"]["ORSet.add+merge"] = d
log(f"| ORSet.add+merge | `ORSet.add()` | 100K | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 2. MERGE ENGINE SCALING (Python)
# ═════════════════════════════════════════════════════════════════
section("Merge Engine Scaling — Python")

from crdt_merge.dataframe import merge

log("| Rows | API | rows/s | Time |")
log("|------|-----|--------|------|")

results["python_engine"] = {}
for n in [10_000, 50_000, 100_000, 500_000]:
    a = [{"id": i, "val": f"a_{i}", "score": float(i)} for i in range(n)]
    b = [{"id": i, "val": f"b_{i}", "score": float(i*2)} for i in range(n//2, n + n//2)]
    def run_merge(a=a, b=b):
        return merge(a, b, key="id")
    d, res = _bench(run_merge, f"python_{n}", ops=n)
    d["output_rows"] = len(res)
    d["rows_per_sec"] = round(n / d["time"])
    results["python_engine"][str(n)] = d
    log(f"| {n:>9,} | `merge(a, b, key='id')` | {_fmt(d['rows_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 3. STREAMING MERGE
# ═════════════════════════════════════════════════════════════════
section("Streaming Merge")

from crdt_merge.streaming import merge_stream

log("| Rows | API | Throughput | Time |")
log("|------|-----|-----------|------|")

results["streaming"] = {}
for n in [100_000, 500_000]:
    source_a = [{"id": i, "val": f"a_{i}"} for i in range(n)]
    source_b = [{"id": i, "val": f"b_{i}"} for i in range(n // 2, n + n // 2)]
    def run_stream(a=source_a, b=source_b):
        batches = list(merge_stream(a, b, key="id"))
        return sum(len(batch) for batch in batches)
    d, total_rows = _bench(run_stream, f"stream_{n}", ops=n)
    d["rows_per_sec"] = round(n / d["time"])
    d["output_rows"] = total_rows
    results["streaming"][str(n)] = d
    log(f"| {n:>9,} | `merge_stream(a, b, key='id')` | {_fmt(d['rows_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 4. WIRE PROTOCOL (v0.8.0.1 with msgpack support)
# ═════════════════════════════════════════════════════════════════
section("Wire Protocol")

from crdt_merge.wire import serialize, deserialize

results["wire_protocol"] = {}

# Roundtrip benchmark
counter = GCounter()
counter.increment("n1", 100)
def run_wire():
    for _ in range(100_000):
        data = serialize(counter)
        obj = deserialize(data)
    return obj
d, _ = _bench(run_wire, "wire_roundtrip", ops=100_000)
d["per_sec"] = round(100_000 / d["time"])
results["wire_protocol"]["roundtrips"] = 100_000
results["wire_protocol"]["time"] = d["time"]
results["wire_protocol"]["per_sec"] = d["per_sec"]
log(f"| Metric | Value |")
log(f"|--------|-------|")
log(f"| Roundtrips | **{100_000:,}** in **{d['time']:.3f}s** |")
log(f"| Throughput | **{_fmt(d['per_sec'])}/sec** |")
log(f"| API | `wire.serialize()` / `wire.deserialize()` |")

# ═════════════════════════════════════════════════════════════════
# 5. CRDT LAW VERIFICATION
# ═════════════════════════════════════════════════════════════════
section("CRDT Law Verification")

import copy

results["law_verification"] = {"total": 0, "passed": 0}

def _crdt_merge(x, y):
    """Merge two CRDT objects, return the merged CRDT object."""
    return copy.deepcopy(x).merge(copy.deepcopy(y))

log("| Type | Commutativity | Associativity | Idempotence | API |")
log("|------|:---:|:---:|:---:|-----|")

gc_a, gc_b, gc_c = GCounter(), GCounter(), GCounter()
gc_a.increment("n1", 10); gc_b.increment("n2", 20); gc_c.increment("n3", 30)

pn_a, pn_b, pn_c = PNCounter(), PNCounter(), PNCounter()
pn_a.increment("n1", 10); pn_b.increment("n2", 20); pn_c.increment("n3", 30)

lww_a = LWWRegister("a", 1.0)
lww_b = LWWRegister("b", 2.0)
lww_c = LWWRegister("c", 3.0)

all_passed = True
for name, a_orig, b_orig, c_orig in [("GCounter", gc_a, gc_b, gc_c), ("PNCounter", pn_a, pn_b, pn_c),
                                      ("LWWRegister", lww_a, lww_b, lww_c)]:
    # Fresh copies for each test to avoid mutation effects
    a, b, c = copy.deepcopy(a_orig), copy.deepcopy(b_orig), copy.deepcopy(c_orig)
    # Commutativity: merge(a,b).value == merge(b,a).value
    r_ab = _crdt_merge(copy.deepcopy(a), copy.deepcopy(b)).value
    r_ba = _crdt_merge(copy.deepcopy(b), copy.deepcopy(a)).value
    comm = r_ab == r_ba
    # Idempotence: merge(a,a).value == a.value
    r_aa = _crdt_merge(copy.deepcopy(a), copy.deepcopy(a)).value
    idem = r_aa == a.value
    # Associativity: merge(merge(a,b), c).value == merge(a, merge(b,c)).value
    r_ab_c = _crdt_merge(_crdt_merge(copy.deepcopy(a), copy.deepcopy(b)), copy.deepcopy(c)).value
    r_a_bc = _crdt_merge(copy.deepcopy(a), _crdt_merge(copy.deepcopy(b), copy.deepcopy(c))).value
    assoc = r_ab_c == r_a_bc

    passed = sum([comm, idem, assoc])
    results["law_verification"]["total"] += 3
    results["law_verification"]["passed"] += passed
    if passed < 3: all_passed = False
    log(f"| {name} | {'✅' if comm else '❌'} | {'✅' if assoc else '❌'} | {'✅' if idem else '❌'} | `{name}.merge()` |")

results["law_verification"]["all_passed"] = all_passed
log(f"\n**Result: {'✅ ALL PASSED' if all_passed else '❌ FAILURES'}**")

# ═════════════════════════════════════════════════════════════════
# 6. MODEL MERGE — ALL 25 STRATEGIES (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Model Merge — 25 Strategy Benchmark")

from crdt_merge.model.core import ModelCRDT, ModelMergeSchema
from crdt_merge.model.strategies import list_strategies

STRATEGIES = list_strategies()
log(f"**{len(STRATEGIES)} strategies** benchmarked, each merging 3 models × 10 layers × 64 params\n")
log("| # | Strategy | API | Merges/sec | Time (1000 merges) |")
log("|---|----------|-----|-----------|-------------------|")

results["model_strategies"] = {}
layers = [f"layer{i}.weight" for i in range(10)]

for idx, strat in enumerate(STRATEGIES, 1):
    schema = ModelMergeSchema(strategies={"default": strat})
    crdt = ModelCRDT(schema)
    m1 = _make_model(layers, size=64, seed=1)
    m2 = _make_model(layers, size=64, seed=2)
    m3 = _make_model(layers, size=64, seed=3)
    base = _make_model(layers, size=64, seed=0)
    
    # Evolutionary/genetic strategies are compute-heavy (search-based)
    if strat in ('evolutionary_merge', 'genetic_merge'):
        n_merges = 5
    else:
        n_merges = 100
    def run_strat(crdt=crdt, m1=m1, m2=m2, m3=m3, base=base, n=n_merges):
        for _ in range(n):
            crdt.merge([m1, m2, m3], base_model=base, weights=[0.4, 0.35, 0.25])
    
    d, _ = _bench(run_strat, strat, ops=n_merges, warmup=0, iters=1)
    d["merges_per_sec"] = round(n_merges / d["time"])
    results["model_strategies"][strat] = d
    log(f"| {idx} | `{strat}` | `ModelCRDT.merge()` | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 7. MODEL MERGE SCALING (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Model Merge Scaling (weight_average)")

log("| Layers × Params | Total Params | API | Merges/sec | Time |")
log("|-----------------|-------------|-----|-----------|------|")

results["model_scaling"] = {}
for n_layers, param_size in [(10, 64), (32, 256), (64, 512), (128, 1024)]:
    total_params = n_layers * param_size
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    crdt = ModelCRDT(schema)
    lyrs = [f"layer{i}.weight" for i in range(n_layers)]
    m1 = _make_model(lyrs, size=param_size, seed=1)
    m2 = _make_model(lyrs, size=param_size, seed=2)
    base = _make_model(lyrs, size=param_size, seed=0)
    
    n_merges = max(10, min(100, 100_000 // total_params))
    def run_scale(crdt=crdt, m1=m1, m2=m2, base=base, n=n_merges):
        for _ in range(n):
            crdt.merge([m1, m2], base_model=base)
    
    d, _ = _bench(run_scale, f"scale_{n_layers}x{param_size}", ops=n_merges, warmup=0, iters=1)
    d["merges_per_sec"] = round(n_merges / d["time"])
    d["total_params"] = total_params
    results["model_scaling"][f"{n_layers}x{param_size}"] = d
    log(f"| {n_layers} × {param_size} | {total_params:>9,} | `ModelCRDT.merge()` | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 8. LoRA ADAPTER MERGING (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("LoRA Adapter Merging")

from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

log("| Test | API | Config | Merges/sec | Time |")
log("|------|-----|--------|-----------|------|")

results["lora_merge"] = {}

# Basic 2-adapter merge
schema = LoRAMergeSchema(strategies={"default": "weight_average"})
lora = LoRAMerge(schema)
modules = ["q_proj", "k_proj", "v_proj", "o_proj"]

for n_adapters, rank in [(2, 4), (2, 16), (4, 8), (8, 4)]:
    adapters = [_make_adapter(modules, rank=rank, in_f=64, out_f=64, seed=i) for i in range(n_adapters)]
    n_ops = 100
    def run_lora(lora=lora, adapters=adapters, n=n_ops):
        for _ in range(n):
            lora.merge_adapters(adapters)
    
    label = f"{n_adapters}adapt_r{rank}"
    d, _ = _bench(run_lora, label, ops=n_ops, warmup=0, iters=2)
    d["merges_per_sec"] = round(n_ops / d["time"])
    results["lora_merge"][label] = d
    log(f"| {n_adapters} adapters, rank={rank} | `LoRAMerge.merge_adapters()` | 4 modules, 64×64 | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# Rank harmonization strategies
for rank_strat in ["max", "min", "mean"]:
    a1 = _make_adapter(["q_proj"], rank=4, in_f=64, out_f=64, seed=1)
    a2 = _make_adapter(["q_proj"], rank=8, in_f=64, out_f=64, seed=2)
    n_ops = 200
    def run_harm(lora=lora, a1=a1, a2=a2, rs=rank_strat, n=n_ops):
        for _ in range(n):
            lora.merge_adapters([a1, a2], rank_strategy=rs)
    
    label = f"rank_harm_{rank_strat}"
    d, _ = _bench(run_harm, label, ops=n_ops, warmup=0, iters=2)
    d["merges_per_sec"] = round(n_ops / d["time"])
    results["lora_merge"][label] = d
    log(f"| Rank harmonization ({rank_strat}) | `merge_adapters(rank_strategy='{rank_strat}')` | r4+r8 | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 9. CONTINUAL MERGE (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Continual Merge")

from crdt_merge.model.continual import ContinualMerge

log("| Absorptions | API | Time | Absorptions/sec |")
log("|------------|-----|------|----------------|")

results["continual_merge"] = {}
for n_absorb in [100, 500]:
    base = _make_model([f"l{i}" for i in range(16)], size=128, seed=0)
    incoming = [_make_model([f"l{i}" for i in range(16)], size=128, seed=s) for s in range(1, n_absorb+1)]
    
    def run_continual(base=base, incoming=incoming, n=n_absorb):
        cm = ContinualMerge(base, strategy='weight_average', memory_budget=1.0)
        for model in incoming:
            cm.absorb(model)
        return cm.export()
    
    d, _ = _bench(run_continual, f"absorb_{n_absorb}", ops=n_absorb, warmup=0, iters=2)
    d["absorptions_per_sec"] = round(n_absorb / d["time"])
    results["continual_merge"][str(n_absorb)] = d
    log(f"| {n_absorb} | `ContinualMerge.absorb()` | {d['time']:.3f}s | {_fmt(d['absorptions_per_sec'])}/s |")

# ═════════════════════════════════════════════════════════════════
# 10. FEDERATED LEARNING (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Federated Learning Bridge")

from crdt_merge.model.federated import FederatedMerge

log("| Clients | API | Strategy | Rounds/sec | Time |")
log("|---------|-----|----------|-----------|------|")

results["federated_merge"] = {}
for n_clients, strategy in [(10, "fedavg"), (50, "fedavg"), (10, "fedprox")]:
    lyrs = [f"l{i}" for i in range(8)]
    models = [_make_model(lyrs, size=64, seed=s) for s in range(n_clients)]
    global_model = _make_model(lyrs, size=64, seed=999)
    n_rounds = 100
    
    def run_fed(models=models, strat=strategy, n=n_rounds, nc=n_clients, gm=global_model):
        for _ in range(n):
            fm = FederatedMerge(strategy=strat, mu=0.01)
            for c, m in enumerate(models):
                fm.submit(f"client_{c}", m, num_samples=100)
            if strat == "fedprox":
                fm.aggregate(global_model=gm)
            else:
                fm.aggregate()
    
    label = f"{n_clients}c_{strategy}"
    d, _ = _bench(run_fed, label, ops=n_rounds, warmup=0, iters=2)
    d["rounds_per_sec"] = round(n_rounds / d["time"])
    results["federated_merge"][label] = d
    log(f"| {n_clients} | `FederatedMerge.submit/aggregate()` | {strategy} | {_fmt(d['rounds_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 11. MULTI-STAGE PIPELINE (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Multi-Stage Merge Pipeline")

from crdt_merge.model.pipeline import MergePipeline

log("| Stages | API | Pipelines/sec | Time |")
log("|--------|-----|-------------|------|")

results["pipeline"] = {}
for n_stages in [2, 5, 10]:
    stages = []
    for s in range(n_stages):
        m1 = _make_model([f"l{i}" for i in range(8)], size=64, seed=s*10)
        m2 = _make_model([f"l{i}" for i in range(8)], size=64, seed=s*10+1)
        stages.append({
            "name": f"stage_{s}",
            "strategy": "weight_average",
            "models": [m1, m2],
        })
    
    n_ops = 200
    def run_pipe(stages=stages, n=n_ops):
        for _ in range(n):
            pipe = MergePipeline(stages)
            pipe.execute()
    
    d, _ = _bench(run_pipe, f"pipe_{n_stages}", ops=n_ops, warmup=0, iters=2)
    d["pipelines_per_sec"] = round(n_ops / d["time"])
    results["pipeline"][f"{n_stages}_stages"] = d
    log(f"| {n_stages} | `MergePipeline.execute()` | {_fmt(d['pipelines_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 12. GPU MERGE — CPU PATH (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("GPU Merge (CPU fallback path)")

results["gpu_merge_cpu"] = {}
try:
    from crdt_merge.model.gpu import GPUMerge
    gm = GPUMerge(device='cpu')
    
    log("| Layers × Params | API | Merges/sec | Time |")
    log("|-----------------|-----|-----------|------|")
    
    for n_layers, param_size in [(10, 64), (32, 256), (64, 512)]:
        lyrs = [f"l{i}" for i in range(n_layers)]
        m1 = _make_model(lyrs, size=param_size, seed=1)
        m2 = _make_model(lyrs, size=param_size, seed=2)
        
        n_ops = 200
        def run_gpu(gm=gm, m1=m1, m2=m2, n=n_ops):
            for _ in range(n):
                gm.merge([m1, m2], strategy='weight_average')
        
        label = f"gpu_cpu_{n_layers}x{param_size}"
        d, _ = _bench(run_gpu, label, ops=n_ops, warmup=0, iters=2)
        d["merges_per_sec"] = round(n_ops / d["time"])
        results["gpu_merge_cpu"][f"{n_layers}x{param_size}"] = d
        log(f"| {n_layers} × {param_size} | `GPUMerge.merge(device='cpu')` | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")
except ImportError:
    log("*Skipped — requires `pip install crdt-merge[gpu]` (PyTorch)*")
    results["gpu_merge_cpu"]["status"] = "skipped_no_torch"

# ═════════════════════════════════════════════════════════════════
# 13. SAFETY ANALYSIS (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Safety-Critical Layer Detection")

from crdt_merge.model.safety import SafetyAnalyzer

log("| Layers | API | Analyses/sec | Time |")
log("|--------|-----|-------------|------|")

results["safety_analysis"] = {}
sa = SafetyAnalyzer()
for n_layers in [10, 50, 100]:
    lyrs = [f"layer{i}.weight" for i in range(n_layers)]
    models_np = [_make_model(lyrs, size=128, seed=s) for s in range(3)]
    
    n_ops = 200
    def run_safety(sa=sa, models=models_np, n=n_ops):
        for _ in range(n):
            sa.safety_report(models)
    
    d, _ = _bench(run_safety, f"safety_{n_layers}", ops=n_ops, warmup=0, iters=2)
    d["analyses_per_sec"] = round(n_ops / d["time"])
    results["safety_analysis"][f"{n_layers}_layers"] = d
    log(f"| {n_layers} | `SafetyAnalyzer.safety_report()` | {_fmt(d['analyses_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 14. CONFLICT HEATMAPS (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Conflict Heatmaps")

from crdt_merge.model.heatmap import ConflictHeatmap

log("| Layers | Models | API | Heatmaps/sec | Time |")
log("|--------|--------|-----|-------------|------|")

results["conflict_heatmaps"] = {}
for n_layers, n_models in [(10, 2), (32, 3), (64, 5)]:
    lyrs = [f"l{i}" for i in range(n_layers)]
    models_dict = [_make_model(lyrs, size=128, seed=s) for s in range(n_models)]
    
    n_ops = 200
    def run_heatmap(models=models_dict, n=n_ops):
        for _ in range(n):
            hm = ConflictHeatmap.from_models(models)
            hm.to_dict()
    
    label = f"{n_layers}L_{n_models}M"
    d, _ = _bench(run_heatmap, label, ops=n_ops, warmup=0, iters=2)
    d["heatmaps_per_sec"] = round(n_ops / d["time"])
    results["conflict_heatmaps"][label] = d
    log(f"| {n_layers} | {n_models} | `ConflictHeatmap.from_models()` | {_fmt(d['heatmaps_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 15. PROVENANCE TRACKING (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Provenance Tracking")

from crdt_merge.model.provenance import ProvenanceTracker

log("| Layers Tracked | API | Tracks/sec | Time |")
log("|---------------|-----|-----------|------|")

results["provenance_tracking"] = {}
for n_layers in [10, 50, 100]:
    tensors = [[float(j) for j in range(64)] for _ in range(3)]
    result_t = [float(j) * 0.5 for j in range(64)]
    
    n_ops = 500
    def run_prov(n=n_ops, nl=n_layers, t=tensors, r=result_t):
        pt = ProvenanceTracker()
        for _ in range(n):
            for i in range(nl):
                pt.track_merge(f"layer{i}", t, [0.4, 0.35, 0.25], "weight_average", r)
        return pt.summary()
    
    d, _ = _bench(run_prov, f"prov_{n_layers}", ops=n_ops * n_layers, warmup=0, iters=2)
    d["tracks_per_sec"] = round(d["ops"] / d["time"])
    results["provenance_tracking"][f"{n_layers}_layers"] = d
    log(f"| {n_layers} | `ProvenanceTracker.track_merge()` | {_fmt(d['tracks_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 16. MERGEKIT COMPATIBILITY (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("MergeKit Compatibility")

from crdt_merge.model.formats import export_mergekit_config, import_mergekit_config

log("| Operation | API | Ops/sec | Time |")
log("|-----------|-----|---------|------|")

results["mergekit_compat"] = {}

schema = ModelMergeSchema(strategies={"default": "slerp", "layer0.weight": "ties"})
n_ops = 10_000
def run_export(n=n_ops):
    for _ in range(n):
        export_mergekit_config(schema, ["model_a", "model_b"])
d, _ = _bench(run_export, "mergekit_export", ops=n_ops)
results["mergekit_compat"]["export"] = d
log(f"| Export | `export_mergekit_config()` | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

cfg = export_mergekit_config(schema, ["model_a", "model_b"])
def run_import(n=n_ops):
    for _ in range(n):
        import_mergekit_config(cfg)
d, _ = _bench(run_import, "mergekit_import", ops=n_ops)
results["mergekit_compat"]["import"] = d
log(f"| Import | `import_mergekit_config()` | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

def run_roundtrip(n=n_ops):
    for _ in range(n):
        c = export_mergekit_config(schema, ["model_a", "model_b"])
        import_mergekit_config(c)
d, _ = _bench(run_roundtrip, "mergekit_roundtrip", ops=n_ops)
results["mergekit_compat"]["roundtrip"] = d
log(f"| Roundtrip | `export → import` | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 17. MODEL MERGE WITH PROVENANCE (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Model Merge with Provenance")

log("| Layers | API | Merges/sec | Time |")
log("|--------|-----|-----------|------|")

results["merge_with_provenance"] = {}
for n_layers in [10, 32, 64]:
    lyrs = [f"l{i}" for i in range(n_layers)]
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    crdt = ModelCRDT(schema)
    m1 = _make_model(lyrs, size=64, seed=1)
    m2 = _make_model(lyrs, size=64, seed=2)
    base = _make_model(lyrs, size=64, seed=0)
    
    n_ops = 200
    def run_mp(crdt=crdt, m1=m1, m2=m2, base=base, n=n_ops):
        for _ in range(n):
            crdt.merge_with_provenance([m1, m2], base_model=base)
    
    d, _ = _bench(run_mp, f"prov_merge_{n_layers}", ops=n_ops, warmup=0, iters=2)
    d["merges_per_sec"] = round(n_ops / d["time"])
    results["merge_with_provenance"][f"{n_layers}_layers"] = d
    log(f"| {n_layers} | `ModelCRDT.merge_with_provenance()` | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 18. CRDT LAW VERIFICATION FOR MODEL MERGE (NEW v0.8.0)
# ═════════════════════════════════════════════════════════════════
section("Model CRDT Law Verification")

from crdt_merge.model.strategies import list_strategies, get_strategy
from crdt_merge.model.strategies.base import CRDTTier

results["model_law_verification"] = {"strategies": {}}

log("| Strategy | Tier | Commutativity | Associativity | Idempotence | API | Trials |")
log("|----------|------|:---:|:---:|:---:|-----|--------|")

for strat in sorted(list_strategies()):
    schema = ModelMergeSchema(strategies={"default": strat})
    crdt = ModelCRDT(schema)
    v = crdt.verify(strategy=strat, trials=50)
    strat_result = v.get(strat, {})
    comm = strat_result.get("commutative", False)
    assoc = strat_result.get("associative", False)
    idem = strat_result.get("idempotent", False)
    needs_base = strat_result.get("needs_base", False)
    tier = get_strategy(strat).crdt_tier.value
    results["model_law_verification"]["strategies"][strat] = {
        "commutative": comm, "associative": assoc, "idempotent": idem,
        "needs_base": needs_base, "tier": tier,
    }
    c = "✅" if comm else "❌"
    a = "✅" if assoc else "❌"
    ip = "✅" if idem else "❌"
    log(f"| `{strat}` | {tier} | {c} | {a} | {ip} | `ModelMerge.verify()` | 50 |")

# ═════════════════════════════════════════════════════════════════
# 19. JSON MERGE (carry forward)
# ═════════════════════════════════════════════════════════════════
section("JSON / Dict Merge")

from crdt_merge.json_merge import merge_dicts

log("| Keys | API | Merges/sec | Time |")
log("|------|-----|-----------|------|")

results["json_merge"] = {}
for n_keys in [100, 1000, 10_000]:
    a = {f"key_{i}": f"val_a_{i}" for i in range(n_keys)}
    b = {f"key_{i}": f"val_b_{i}" for i in range(n_keys // 2, n_keys + n_keys // 2)}
    
    n_ops = 1000
    def run_json(a=a, b=b, n=n_ops):
        for _ in range(n):
            merge_dicts(a, b)
    
    d, _ = _bench(run_json, f"json_{n_keys}", ops=n_ops, warmup=0, iters=2)
    d["merges_per_sec"] = round(n_ops / d["time"])
    results["json_merge"][f"{n_keys}_keys"] = d
    log(f"| {n_keys:,} | `merge_dicts(a, b)` | {_fmt(d['merges_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 20. DEDUP (carry forward)
# ═════════════════════════════════════════════════════════════════
section("Dedup")

from crdt_merge.dedup import dedup_list, MinHashDedup

log("| Operation | API | Items | Ops/sec | Time |")
log("|-----------|-----|-------|---------|------|")

results["dedup"] = {}

items_50k = [f"item_{i % 25000}" for i in range(50_000)]
def run_dedup():
    return dedup_list(items_50k)
d, _ = _bench(run_dedup, "dedup_50k")
results["dedup"]["exact_50k"] = d
log(f"| Exact dedup | `dedup_list()` | 50K (50% dupes) | — | {d['time']:.3f}s |")

mh = MinHashDedup(num_hashes=64, threshold=0.5)
docs = [f"This is document {i} about topic {i%20} with unique content {i*7}" for i in range(1000)]
def run_minhash():
    return mh.dedup(docs, text_fn=lambda x: x)
d, _ = _bench(run_minhash, "minhash_1k")
results["dedup"]["minhash_1k"] = d
log(f"| MinHash dedup | `MinHashDedup.dedup()` | 1K docs | — | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# 21. DELTA OPERATIONS (carry forward + DEF-007 fix verification)
# ═════════════════════════════════════════════════════════════════
section("Delta Operations")

from crdt_merge.delta import Delta, compose_deltas

log("| Operation | API | Ops | Ops/sec | Time |")
log("|-----------|-----|-----|---------|------|")

results["delta_ops"] = {}

n_ops = 50_000
d1 = Delta(added=[{"id": 1, "score": 2.0}], modified=[], removed=[], version=1, timestamp=1.0, source_node="n1")
d2 = Delta(added=[], modified=[{"id": 1, "score": 3.0}], removed=[], version=2, timestamp=2.0, source_node="n2")

def run_delta_compose():
    for _ in range(n_ops):
        compose_deltas(d1, d2, key="id")
d, _ = _bench(run_delta_compose, "compose_deltas", ops=n_ops)
results["delta_ops"]["compose_pair"] = d
log(f"| Compose pair | `compose_deltas(d1, d2)` | {_fmt(n_ops)} | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# DEF-007: compose_deltas with list (fixed)
def run_delta_list():
    for _ in range(n_ops):
        compose_deltas([d1, d2], key="id")
d, _ = _bench(run_delta_list, "compose_deltas_list", ops=n_ops)
results["delta_ops"]["compose_list"] = d
log(f"| Compose list (DEF-007 fix) | `compose_deltas([d1, d2])` | {_fmt(n_ops)} | {_fmt(d['ops_per_sec'])}/s | {d['time']:.3f}s |")

# ═════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════
section("Summary")

total_measurements = 0
for key, val in results.items():
    if key == "meta": continue
    if isinstance(val, dict):
        total_measurements += len(val)

log(f"**Total measurements:** {total_measurements}")
# Check model strategy CRDT law compliance
model_laws = results.get("model_law_verification", {}).get("strategies", {})
model_all_passed = True
model_failures = []
for strat_name, props in model_laws.items():
    for prop in ("commutative", "associative", "idempotent"):
        if props.get(prop) is False:
            model_all_passed = False
            model_failures.append(f"{strat_name}.{prop}")

primitive_passed = results["law_verification"]["all_passed"]
all_laws_passed = primitive_passed and model_all_passed

log(f"**Primitive CRDT laws passed:** {'✅' if primitive_passed else '❌'}")
log(f"**Model merge CRDT laws passed:** {'✅' if model_all_passed else '❌'}")
if model_failures:
    log(f"  Model failures: {', '.join(model_failures)}")
log(f"**All CRDT laws passed:** {'✅' if all_laws_passed else '❌'}")
log(f"**Platform:** {results['meta']['platform']}")
log(f"**Python:** {results['meta']['python']}")
log(f"**Version:** {results['meta']['version']}")
log(f"**Timestamp:** {results['meta']['timestamp']}")

results["summary"] = {
    "total_measurements": total_measurements,
    "primitive_crdt_laws_passed": primitive_passed,
    "model_crdt_laws_passed": model_all_passed,
    "crdt_laws_passed": all_laws_passed,
    "model_law_failures": model_failures,
}

# ═════════════════════════════════════════════════════════════════
# OUTPUT FILES
# ═════════════════════════════════════════════════════════════════
import os
outdir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(outdir, "all_results.json"), "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n✅ JSON → {outdir}/all_results.json")

header = f"""# crdt-merge v0.8.0 — Benchmark Report

**Generated:** {results['meta']['timestamp']}

**Platform:** {results['meta']['platform']}

**Python:** {results['meta']['python']}

**Total measurements:** {total_measurements}

---
"""

with open(os.path.join(outdir, "ANALYSIS.md"), "w") as f:
    f.write(header)
    f.write("\n".join(report_lines))
    f.write("\n\n---\n\n*Generated by crdt-merge v0.8.0 benchmark suite*\n")
print(f"✅ Report → {outdir}/ANALYSIS.md")
