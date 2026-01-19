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
crdt-merge v0.8.2 — Comprehensive Benchmark Suite

Benchmarks:
  1. Context Memory System  (ContextBloom, MemorySidecar, ContextMerge, ContextConsolidator)
  2. Agentic AI             (AgentState, SharedKnowledge)
  3. Core regression         (DataFrame merge, streaming, CRDT law verification, wire)
"""

import os
import sys
import time
import random
import platform
from datetime import datetime, timezone

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import crdt_merge
from crdt_merge import (
    GCounter,
    PNCounter,
    LWWRegister,
    LWWMap,
    ORSet,
    VectorClock,
    serialize,
    deserialize,
    merge,
    merge_stream,
    StreamStats,
)
from crdt_merge.context.bloom import ContextBloom
from crdt_merge.context.sidecar import MemorySidecar
from crdt_merge.context.merge import ContextMerge
from crdt_merge.context.consolidator import ContextConsolidator
from crdt_merge.agentic import AgentState, SharedKnowledge, Fact
from crdt_merge.verify import verify_crdt
from crdt_merge.dataframe import merge as df_merge

# ======================================================================
# Helpers
# ======================================================================

WIDTH = 80


def header(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * WIDTH)
    print(f"  {title}")
    print("=" * WIDTH)


def row(label: str, value: str, unit: str = "") -> None:
    """Print a table row."""
    combined = f"{value} {unit}".strip()
    print(f"  {label:<48s} {combined:>28s}")


def divider() -> None:
    print("  " + "-" * (WIDTH - 4))


def fmt_ops(ops: float) -> str:
    """Format an operations-per-second number."""
    if ops >= 1e9:
        return f"{ops / 1e9:.2f}B"
    if ops >= 1e6:
        return f"{ops / 1e6:.2f}M"
    if ops >= 1e3:
        return f"{ops / 1e3:.1f}K"
    return f"{ops:.1f}"


def fmt_time(seconds: float) -> str:
    """Format a time duration."""
    if seconds < 1e-6:
        return f"{seconds * 1e9:.1f} ns"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    if seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    return f"{seconds:.3f} s"


def bench(fn, n_iters: int = 1, warmup: int = 0):
    """Run fn n_iters times, return (total_seconds, result_of_last_call)."""
    result = None
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n_iters):
        result = fn()
    elapsed = time.perf_counter() - t0
    return elapsed, result


# ======================================================================
# 1. Context Memory System Benchmarks
# ======================================================================

def bench_context_bloom():
    header("Context Memory — ContextBloom")

    for n in [100_000, 1_000_000]:
        cb = ContextBloom(expected_items=n)
        # Add phase
        t0 = time.perf_counter()
        for i in range(n):
            cb.add(f"key_{i}")
        add_elapsed = time.perf_counter() - t0
        add_ops = n / add_elapsed

        # Contains phase (positive lookups)
        t0 = time.perf_counter()
        for i in range(n):
            cb.contains(f"key_{i}")
        contains_elapsed = time.perf_counter() - t0
        contains_ops = n / contains_elapsed

        label_n = fmt_ops(n)
        row(f"ContextBloom add ({label_n} items)", fmt_ops(add_ops), "ops/sec")
        row(f"ContextBloom contains ({label_n} items)", fmt_ops(contains_ops), "ops/sec")
        row(f"  avg add latency", fmt_time(add_elapsed / n))
        row(f"  avg contains latency", fmt_time(contains_elapsed / n))
        divider()

    # False positive rate check
    cb = ContextBloom(expected_items=100_000)
    for i in range(100_000):
        cb.add(f"real_{i}")
    false_positives = sum(1 for i in range(100_000) if cb.contains(f"fake_{i}"))
    fp_rate = false_positives / 100_000
    row("False positive rate (100K items)", f"{fp_rate:.4%}")


def bench_memory_sidecar():
    header("Context Memory — MemorySidecar")

    # Create sidecars
    n = 100_000
    t0 = time.perf_counter()
    sidecars = []
    for i in range(n):
        ms = MemorySidecar(
            fact_id=f"fact_{i}",
            content_hash=f"hash_{i:08x}",
            topic=random.choice(["science", "history", "math", "code"]),
            source_agent=f"agent_{i % 10}",
            confidence=random.uniform(0.5, 1.0),
            tags=[random.choice(["important", "verified", "recent"])],
        )
        sidecars.append(ms)
    create_elapsed = time.perf_counter() - t0
    row(f"Create {fmt_ops(n)} MemorySidecars", fmt_time(create_elapsed))
    row(f"  avg create latency", fmt_time(create_elapsed / n))

    # Filter (matches_filter)
    t0 = time.perf_counter()
    matches = 0
    for ms in sidecars:
        if ms.matches_filter(topic="science", min_confidence=0.7):
            matches += 1
    filter_elapsed = time.perf_counter() - t0
    filter_ops = n / filter_elapsed
    row(f"Filter {fmt_ops(n)} sidecars", fmt_ops(filter_ops), "ops/sec")
    row(f"  avg filter latency", fmt_time(filter_elapsed / n))
    row(f"  matches found", f"{matches}")

    # to_dict / from_dict roundtrip
    t0 = time.perf_counter()
    for ms in sidecars[:10_000]:
        d = ms.to_dict()
        MemorySidecar.from_dict(d)
    rt_elapsed = time.perf_counter() - t0
    row(f"to_dict/from_dict roundtrip (10K)", fmt_time(rt_elapsed))
    row(f"  avg roundtrip latency", fmt_time(rt_elapsed / 10_000))


def bench_context_merge():
    header("Context Memory — ContextMerge")

    def make_memories(agent_id, n):
        return [
            {
                "fact": f"memory_{agent_id}_{i}_content",
                "source": agent_id,
                "topic": "benchmark",
                "confidence": random.uniform(0.6, 1.0),
            }
            for i in range(n)
        ]

    for n in [1_000, 10_000, 50_000]:
        mems_a = make_memories("agent_a", n)
        mems_b = make_memories("agent_b", n)
        cm = ContextMerge(strategy="lww")

        t0 = time.perf_counter()
        result = cm.merge(mems_a, mems_b)
        elapsed = time.perf_counter() - t0

        label = fmt_ops(n)
        row(
            f"ContextMerge 2 agents × {label} memories",
            fmt_time(elapsed),
        )
        row(f"  merged memories", f"{len(result.memories)}")
        row(f"  duplicates found", f"{result.duplicates_found}")
        divider()


def bench_context_consolidator():
    header("Context Memory — ContextConsolidator")
    from crdt_merge.context import MemoryChunk

    for n in [10_000, 50_000]:
        # Build MemoryChunk list
        chunks = []
        for i in range(n):
            sidecar = MemorySidecar(
                fact_id=f"fact_{i}",
                content_hash=f"hash_{i:08x}",
                topic=random.choice(["a", "b", "c"]),
                source_agent="agent_0",
            )
            chunks.append(MemoryChunk(fact=f"memory_{i}", sidecar=sidecar))

        cc = ContextConsolidator()
        t0 = time.perf_counter()
        blocks = cc.consolidate(chunks)
        elapsed = time.perf_counter() - t0

        label = fmt_ops(n)
        row(f"Consolidate {label} memories → blocks", fmt_time(elapsed))
        row(f"  blocks produced", f"{len(blocks)}")


# ======================================================================
# 2. Agentic AI Benchmarks
# ======================================================================

def bench_agent_state():
    header("Agentic AI — AgentState.merge")

    for n_facts in [100, 500, 1000]:
        a = AgentState(agent_id="agent_a")
        b = AgentState(agent_id="agent_b")

        for i in range(n_facts):
            a.add_fact(f"fact_{i}", f"val_a_{i}", confidence=0.9)
            b.add_fact(f"fact_{i}", f"val_b_{i}", confidence=0.8)

        # Also add unique facts
        for i in range(n_facts, n_facts + n_facts // 2):
            a.add_fact(f"unique_a_{i}", f"uniq_a_{i}")
        for i in range(n_facts, n_facts + n_facts // 2):
            b.add_fact(f"unique_b_{i}", f"uniq_b_{i}")

        n_iters = max(1, 1000 // n_facts)
        t0 = time.perf_counter()
        for _ in range(n_iters):
            merged = a.merge(b)
        elapsed = time.perf_counter() - t0
        avg = elapsed / n_iters
        ops = n_iters / elapsed

        row(
            f"AgentState.merge ({n_facts} overlapping facts)",
            fmt_time(avg),
            f"({fmt_ops(ops)} merges/sec)",
        )
        row(f"  merged fact count", f"{len(merged.list_facts())}")
        divider()


def bench_shared_knowledge():
    header("Agentic AI — SharedKnowledge.merge")

    for n_agents in [2, 5, 10, 20]:
        facts_per_agent = 200

        agents = []
        for a_idx in range(n_agents):
            agent = AgentState(agent_id=f"agent_{a_idx}")
            for f_idx in range(facts_per_agent):
                agent.add_fact(
                    f"shared_fact_{f_idx}",
                    f"v_{a_idx}_{f_idx}",
                    confidence=random.uniform(0.5, 1.0),
                )
            for f_idx in range(50):
                agent.add_fact(
                    f"unique_{a_idx}_{f_idx}",
                    f"u_{a_idx}_{f_idx}",
                )
            agents.append(agent)

        n_iters = max(1, 100 // n_agents)
        t0 = time.perf_counter()
        for _ in range(n_iters):
            result = SharedKnowledge.merge(*agents)
        elapsed = time.perf_counter() - t0
        avg = elapsed / n_iters

        row(
            f"SharedKnowledge.merge ({n_agents} agents × {facts_per_agent} facts)",
            fmt_time(avg),
        )
        divider()


# ======================================================================
# 3. Core Regression Benchmarks
# ======================================================================

def bench_dataframe_merge():
    header("Core — DataFrame Merge")

    def make_df(n, prefix):
        return [
            {"id": i, "ts": i + (1 if prefix == "b" else 0), "name": f"{prefix}_{i}", "score": random.random()}
            for i in range(n)
        ]

    for n in [1_000, 10_000, 100_000]:
        df_a = make_df(n, "a")
        df_b = make_df(n, "b")

        t0 = time.perf_counter()
        result = df_merge(df_a, df_b, key="id", timestamp_col="ts")
        elapsed = time.perf_counter() - t0

        label = fmt_ops(n)
        rows_sec = n / elapsed
        row(f"DataFrame merge ({label} rows)", fmt_time(elapsed), f"({fmt_ops(rows_sec)} rows/sec)")
        row(f"  output rows", f"{len(result)}")
        divider()


def bench_streaming_merge():
    header("Core — Streaming Merge")

    n = 100_000

    def gen_stream(prefix, n):
        for i in range(n):
            yield {"id": i, "ts": i, "val": f"{prefix}_{i}"}

    stats = StreamStats()
    t0 = time.perf_counter()
    total_rows = 0
    for batch in merge_stream(
        gen_stream("a", n),
        gen_stream("b", n),
        key="id",
        batch_size=5000,
        timestamp_col="ts",
        stats=stats,
    ):
        total_rows += len(batch)
    elapsed = time.perf_counter() - t0

    rows_sec = total_rows / elapsed
    row(f"Streaming merge ({fmt_ops(n)} rows × 2 sources)", fmt_time(elapsed))
    row(f"  total output rows", f"{total_rows}")
    row(f"  throughput", f"{fmt_ops(rows_sec)} rows/sec")


def bench_crdt_law_verification():
    header("Core — CRDT Law Verification")

    crdts = {
        "GCounter": (
            lambda a, b: a.merge(b),
            lambda: _random_gcounter(),
        ),
        "PNCounter": (
            lambda a, b: a.merge(b),
            lambda: _random_pncounter(),
        ),
        "LWWRegister": (
            lambda a, b: a.merge(b),
            lambda: _random_lwwregister(),
        ),
        "ORSet": (
            lambda a, b: a.merge(b),
            lambda: _random_orset(),
        ),
    }

    trials = 1000
    for name, (merge_fn, gen_fn) in crdts.items():
        t0 = time.perf_counter()
        result = verify_crdt(merge_fn, gen_fn, trials=trials)
        elapsed = time.perf_counter() - t0

        status = "✅ PASS" if result.passed else "❌ FAIL"
        row(f"verify_crdt({name}, {trials} trials)", f"{status}", f"({fmt_time(elapsed)})")


def _random_gcounter():
    gc = GCounter()
    for _ in range(random.randint(1, 5)):
        gc.increment(f"node_{random.randint(0, 3)}", random.randint(1, 100))
    return gc


def _random_pncounter():
    pc = PNCounter()
    for _ in range(random.randint(1, 5)):
        pc.increment(f"node_{random.randint(0, 3)}", random.randint(1, 50))
    for _ in range(random.randint(0, 3)):
        pc.decrement(f"node_{random.randint(0, 3)}", random.randint(1, 20))
    return pc


def _random_lwwregister():
    r = LWWRegister()
    r.set(random.choice(["alpha", "beta", "gamma", "delta"]))
    return r


def _random_orset():
    s = ORSet()
    for _ in range(random.randint(1, 6)):
        s.add(random.choice(["a", "b", "c", "d", "e"]))
    for _ in range(random.randint(0, 2)):
        s.remove(random.choice(["a", "b", "c", "d", "e"]))
    return s


def bench_wire_serialization():
    header("Core — Wire Serialization Roundtrip")

    crdts = {
        "GCounter": _random_gcounter,
        "PNCounter": _random_pncounter,
        "LWWRegister": _random_lwwregister,
        "ORSet": _random_orset,
    }

    n_iters = 10_000
    for name, gen_fn in crdts.items():
        obj = gen_fn()
        data = serialize(obj)
        wire_bytes = len(data)

        t0 = time.perf_counter()
        for _ in range(n_iters):
            d = serialize(obj)
            _ = deserialize(d)
        elapsed = time.perf_counter() - t0
        avg = elapsed / n_iters
        ops = n_iters / elapsed

        row(
            f"{name} serialize+deserialize ({wire_bytes}B wire)",
            fmt_time(avg),
            f"({fmt_ops(ops)} roundtrips/sec)",
        )


# ======================================================================
# Main
# ======================================================================

def main():
    print("=" * WIDTH)
    print(f"  crdt-merge v{crdt_merge.__version__} — Benchmark Suite")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Python {platform.python_version()} on {platform.system()} {platform.machine()}")
    print("=" * WIDTH)

    t_total = time.perf_counter()

    # 1. Context Memory
    bench_context_bloom()
    bench_memory_sidecar()
    bench_context_merge()
    bench_context_consolidator()

    # 2. Agentic AI
    bench_agent_state()
    bench_shared_knowledge()

    # 3. Core regression
    bench_dataframe_merge()
    bench_streaming_merge()
    bench_crdt_law_verification()
    bench_wire_serialization()

    total_elapsed = time.perf_counter() - t_total
    header("Summary")
    row("Total benchmark time", fmt_time(total_elapsed))
    print()


if __name__ == "__main__":
    main()
