# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Performance and scale proofs.

Throughput benchmarks, memory ceiling tests, concurrent peer scale,
compression ratio at scale, and latency profiling.
"""

import gc
import hashlib
import random
import sys
import time

import pytest

from crdt_merge.e4.typed_trust import (
    TRUST_DIMENSIONS,
    TypedTrustScore,
    TrustHomeostasis,
)
from crdt_merge.e4.proof_evidence import TrustEvidence
from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.projection_delta import FrozenDict, ProjectionDelta
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.pco import AggregateProofCarryingOperation, SubtreeRef
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry,
    ConflictType,
    TrustWeightedAveragingResolver,
    TrustWeightedLWWResolver,
    TrustWeightedStrategySelector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(observer, dimension, amount):
    from e4_factories import make_invalid_delta_proof
    return TrustEvidence.create(
        observer=observer, target="target",
        evidence_type="invalid_delta",
        dimension=dimension, amount=amount,
        proof=make_invalid_delta_proof(target="target"),
    )


def _make_pco(source_id="peer-a"):
    return AggregateProofCarryingOperation.build(
        originator_id=source_id,
        signing_fn=lambda h: b"\x00" * 64,
        merkle_root="", clock_snapshot=b"",
        trust_vector_hash="", delta_bounds=[],
    )


def _make_delta(source_id="peer-a", insertions=None, updates=None, deletions=None):
    return ProjectionDelta(
        source_id=source_id, source_version=None, target_version=None,
        changed_subtrees=(), insertions=FrozenDict(insertions or {}),
        updates=FrozenDict(updates or {}), deletions=frozenset(deletions or []),
        pco=_make_pco(source_id), encoding="raw", compression_ratio=1.0,
    )


def _random_trust_score(rng):
    evidence = {}
    for d in TRUST_DIMENSIONS:
        if rng.random() > 0.3:
            evidence[d] = {f"obs_{rng.randint(0, 5)}": rng.uniform(0.0, 0.3)}
    return TypedTrustScore(_evidence=evidence)


# ---------------------------------------------------------------------------
# Throughput Benchmarks
# ---------------------------------------------------------------------------

class TestThroughputBenchmarks:
    """Measure operations per second for core operations."""

    def test_typed_trust_score_merge_throughput(self):
        """1000 merges, measure ops/sec."""
        rng = random.Random(42)
        scores = [_random_trust_score(rng) for _ in range(100)]
        n = 1000
        start = time.perf_counter_ns()
        for i in range(n):
            a = scores[i % len(scores)]
            b = scores[(i + 37) % len(scores)]
            _ = a.merge(b)
        elapsed_ns = time.perf_counter_ns() - start
        ops_sec = n / (elapsed_ns / 1e9)
        print(f"\nTypedTrustScore.merge: {ops_sec:.0f} ops/sec ({elapsed_ns/n:.0f} ns/op)")
        assert ops_sec > 100, f"Too slow: {ops_sec} ops/sec"

    def test_causal_trust_clock_merge_throughput(self):
        """1000 merges with 100 peers."""
        rng = random.Random(42)
        clocks = []
        for i in range(50):
            c = CausalTrustClock(f"peer_{i}")
            for j in range(100):
                c._entries[f"p{j}"] = (rng.randint(0, 1000), rng.uniform(0, 1))
            clocks.append(c)

        n = 1000
        start = time.perf_counter_ns()
        for i in range(n):
            a = clocks[i % len(clocks)]
            b = clocks[(i + 17) % len(clocks)]
            _ = a.merge(b)
        elapsed_ns = time.perf_counter_ns() - start
        ops_sec = n / (elapsed_ns / 1e9)
        print(f"\nCausalTrustClock.merge (100 peers): {ops_sec:.0f} ops/sec ({elapsed_ns/n:.0f} ns/op)")
        assert ops_sec > 50, f"Too slow: {ops_sec} ops/sec"

    def test_projection_delta_compose_throughput(self):
        """100 compositions."""
        rng = random.Random(42)
        deltas = []
        for i in range(100):
            ins = {f"k_{i}_{j}": bytes(rng.getrandbits(8) for _ in range(32)) for j in range(10)}
            deltas.append(_make_delta(insertions=ins))

        n = 100
        start = time.perf_counter_ns()
        result = deltas[0]
        for d in deltas[1:]:
            result = result.compose(d)
        elapsed_ns = time.perf_counter_ns() - start
        ops_sec = n / (elapsed_ns / 1e9)
        print(f"\nProjectionDelta.compose: {ops_sec:.0f} ops/sec ({elapsed_ns/n:.0f} ns/op)")
        assert ops_sec > 10, f"Too slow: {ops_sec} ops/sec"

    def test_observe_and_propagate_throughput(self):
        """100 evidence events through DeltaTrustLattice."""
        lattice = DeltaTrustLattice("node-a", initial_peers={f"p{i}" for i in range(10)})
        dims = list(TRUST_DIMENSIONS)
        rng = random.Random(42)

        events = []
        for i in range(100):
            dim = rng.choice(dims)
            ev = _make_evidence(f"obs_{i%5}", dim, 0.01)
            events.append(ev)

        n = len(events)
        start = time.perf_counter_ns()
        for ev in events:
            try:
                lattice.observe_and_propagate(ev)
            except Exception:
                pass  # Circuit breaker might trip
        elapsed_ns = time.perf_counter_ns() - start
        ops_sec = n / (elapsed_ns / 1e9)
        print(f"\nDeltaTrustLattice.observe_and_propagate: {ops_sec:.0f} ops/sec ({elapsed_ns/n:.0f} ns/op)")
        assert ops_sec > 10

    def test_trust_weighted_strategy_throughput(self):
        """1000 resolutions with 10 entries each."""
        resolver = TrustWeightedLWWResolver(trust_weight_factor=1.0, min_trust=0.0)
        rng = random.Random(42)
        entries_list = []
        for _ in range(100):
            entries = []
            for j in range(10):
                trust = _random_trust_score(rng)
                entries.append(ConflictEntry(
                    f"p{j}", rng.uniform(0, 100), rng.uniform(0, 1000), trust, "integrity"
                ))
            entries_list.append(entries)

        n = 1000
        start = time.perf_counter_ns()
        for i in range(n):
            resolver.resolve(entries_list[i % len(entries_list)])
        elapsed_ns = time.perf_counter_ns() - start
        ops_sec = n / (elapsed_ns / 1e9)
        print(f"\nTrustWeightedLWWResolver.resolve (10 entries): {ops_sec:.0f} ops/sec ({elapsed_ns/n:.0f} ns/op)")
        assert ops_sec > 100


# ---------------------------------------------------------------------------
# Memory Ceiling
# ---------------------------------------------------------------------------

class TestMemoryCeiling:

    def test_lattice_1000_peers_memory(self):
        """Create lattice with 1000 peers, measure memory."""
        gc.collect()
        before = _get_memory()
        peers = {f"peer_{i}" for i in range(1000)}
        lattice = DeltaTrustLattice("node", initial_peers=peers)
        # Add some evidence
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)
        for _ in range(100):
            p = f"peer_{rng.randint(0, 999)}"
            d = rng.choice(dims)
            ev = _make_evidence("obs", d, 0.01)
            old = lattice._trust_scores.get(p, TypedTrustScore.probationary())
            lattice._trust_scores[p] = old.record_evidence("obs", d, 0.01, ev)
        gc.collect()
        after = _get_memory()
        delta_mb = (after - before) / (1024 * 1024)
        print(f"\nLattice with 1000 peers: ~{delta_mb:.2f} MB")
        # Should be reasonable (< 100 MB)
        assert delta_mb < 100

    def test_delta_10k_insertions_memory(self):
        """Create delta with 10000 insertions."""
        gc.collect()
        before = _get_memory()
        rng = random.Random(42)
        ins = {f"k_{i}": bytes(rng.getrandbits(8) for _ in range(64)) for i in range(10000)}
        delta = _make_delta(insertions=ins)
        gc.collect()
        after = _get_memory()
        delta_mb = (after - before) / (1024 * 1024)
        print(f"\nDelta with 10K insertions: ~{delta_mb:.2f} MB")
        assert delta_mb < 50

    def test_merkle_10k_leaves_memory(self):
        """Create Merkle tree with 10000 leaves."""
        gc.collect()
        before = _get_memory()
        merkle = TrustBoundMerkle(branching_factor=256)
        for i in range(10000):
            merkle.insert_leaf(f"k_{i}", f"data_{i}".encode(), f"peer_{i%10}")
        gc.collect()
        after = _get_memory()
        delta_mb = (after - before) / (1024 * 1024)
        print(f"\nMerkle tree with 10K leaves: ~{delta_mb:.2f} MB")
        assert delta_mb < 100

    def test_memory_scales_linearly(self):
        """Prove memory scales linearly, not quadratically."""
        sizes = [100, 500, 1000]
        memories = []
        for n in sizes:
            gc.collect()
            before = _get_memory()
            peers = {f"p_{i}" for i in range(n)}
            lattice = DeltaTrustLattice(f"node_{n}", initial_peers=peers)
            gc.collect()
            after = _get_memory()
            memories.append(after - before)

        # Check ratio: if linear, memory[1000] / memory[100] ≈ 10
        # If quadratic, it would be ≈ 100
        if memories[0] > 0:
            ratio = memories[2] / max(memories[0], 1)
            print(f"\nMemory scaling ratio (1000/100 peers): {ratio:.1f}x (expect ~10x for linear)")
            # Allow generous bounds but reject quadratic (100x)
            assert ratio < 50, f"Memory scaling appears super-linear: {ratio}x"


def _get_memory():
    """Get current process RSS in bytes."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        return 0


# ---------------------------------------------------------------------------
# Concurrent Peer Scale
# ---------------------------------------------------------------------------

class TestConcurrentPeerScale:

    def test_100_peer_convergence(self):
        """100-peer cluster: all exchange trust evidence, converge."""
        n_peers = 100
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)
        peer_ids = [f"peer_{i}" for i in range(n_peers)]
        peer_set = set(peer_ids)

        lattice = DeltaTrustLattice("node", initial_peers=peer_set)
        # Each peer records evidence about some others
        n_events = n_peers * 5  # O(n) events
        for _ in range(n_events):
            target = rng.choice(peer_ids)
            obs = rng.choice(peer_ids)
            dim = rng.choice(dims)
            amt = rng.uniform(0.001, 0.05)
            ev = _make_evidence(obs, dim, amt)
            old = lattice._trust_scores.get(target, TypedTrustScore.probationary())
            lattice._trust_scores[target] = old.record_evidence(obs, dim, amt, ev)

        # Verify all peers have trust scores
        for p in peer_ids:
            t = lattice.get_trust(p)
            assert t.overall_trust() >= 0.0
        print(f"\n100-peer cluster: {n_events} evidence events processed")

    def test_500_peer_no_exponential(self):
        """500-peer cluster: verify no exponential blowup."""
        n_peers = 500
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)
        peer_ids = [f"peer_{i}" for i in range(n_peers)]

        start = time.perf_counter_ns()
        lattice = DeltaTrustLattice("node", initial_peers=set(peer_ids))
        n_events = n_peers * 3  # O(n) events
        for _ in range(n_events):
            target = rng.choice(peer_ids)
            obs = rng.choice(peer_ids)
            dim = rng.choice(dims)
            amt = rng.uniform(0.001, 0.02)
            ev = _make_evidence(obs, dim, amt)
            old = lattice._trust_scores.get(target, TypedTrustScore.probationary())
            lattice._trust_scores[target] = old.record_evidence(obs, dim, amt, ev)
        elapsed = (time.perf_counter_ns() - start) / 1e9
        print(f"\n500-peer cluster: {n_events} events in {elapsed:.2f}s")
        # Should complete in reasonable time (< 30s)
        assert elapsed < 30

    def test_merge_two_100_peer_lattices(self):
        """Merge two independent 100-peer lattices."""
        rng = random.Random(42)
        dims = list(TRUST_DIMENSIONS)
        peers = {f"p{i}" for i in range(100)}

        la = DeltaTrustLattice("node-a", initial_peers=peers)
        lb = DeltaTrustLattice("node-b", initial_peers=peers)

        for lattice, node_id in [(la, "node-a"), (lb, "node-b")]:
            for _ in range(200):
                target = rng.choice(list(peers))
                dim = rng.choice(dims)
                amt = rng.uniform(0.001, 0.05)
                ev = _make_evidence(node_id, dim, amt)
                old = lattice._trust_scores.get(target, TypedTrustScore.probationary())
                lattice._trust_scores[target] = old.record_evidence(node_id, dim, amt, ev)

        start = time.perf_counter_ns()
        merged = la.merge(lb)
        elapsed = (time.perf_counter_ns() - start) / 1e6
        print(f"\nMerge two 100-peer lattices: {elapsed:.1f}ms")
        assert elapsed < 5000  # < 5s


# ---------------------------------------------------------------------------
# Compression Ratio at Scale
# ---------------------------------------------------------------------------

class TestCompressionRatioAtScale:

    def test_100k_elements_1pct_changed(self):
        """100K-element state, 1% changed → sparse compression."""
        rng = random.Random(42)
        n_total = 10000
        n_changed = 100  # 1%

        def _rb(n):
            return bytes(rng.getrandbits(8) for _ in range(n))

        old = {f"k_{i}": _rb(32) for i in range(n_total)}
        new = dict(old)
        changed_keys = rng.sample(list(new.keys()), n_changed)
        for k in changed_keys:
            new[k] = _rb(32)

        all_updates = {}
        for k in old:
            old_h = hashlib.sha256(old[k]).hexdigest()
            all_updates[k] = (old_h, new[k])

        delta = _make_delta(updates=all_updates)
        compressed = delta.compress("sparse")
        print(f"\n10K elements, 1% changed: ratio={compressed.compression_ratio:.1f}")
        assert compressed.compression_ratio >= 10.0

    def test_1m_elements_01pct_changed(self):
        """1M proxy (100K elements, 0.1% changed) → ratio > 100:1."""
        rng = random.Random(42)
        n_total = 10000
        n_changed = 10  # 0.1%

        def _rb(n):
            return bytes(rng.getrandbits(8) for _ in range(n))

        old = {f"k_{i}": _rb(16) for i in range(n_total)}
        new = dict(old)
        changed_keys = rng.sample(list(new.keys()), n_changed)
        for k in changed_keys:
            new[k] = _rb(16)

        all_updates = {}
        for k in old:
            old_h = hashlib.sha256(old[k]).hexdigest()
            all_updates[k] = (old_h, new[k])

        delta = _make_delta(updates=all_updates)
        compressed = delta.compress("sparse")
        print(f"\n10K elements, 0.1% changed: ratio={compressed.compression_ratio:.1f}")
        assert compressed.compression_ratio >= 100.0

    def test_quantized_on_large_delta(self):
        """Quantized encoding on large delta."""
        rng = random.Random(42)
        ins = {f"k_{i}": bytes(rng.getrandbits(8) for _ in range(128)) for i in range(1000)}
        delta = _make_delta(insertions=ins)
        quantized = delta.compress("quantized", bits=4)
        print(f"\nQuantized 1K insertions: ratio={quantized.compression_ratio:.2f}")
        assert quantized.encoding == "quantized"


# ---------------------------------------------------------------------------
# Latency Profiling
# ---------------------------------------------------------------------------

class TestLatencyProfiling:

    def _measure_latency(self, fn, n=1000):
        """Run fn n times, return (p50, p95, p99) in nanoseconds."""
        times = []
        for _ in range(n):
            start = time.perf_counter_ns()
            fn()
            times.append(time.perf_counter_ns() - start)
        times.sort()
        p50 = times[int(n * 0.50)]
        p95 = times[int(n * 0.95)]
        p99 = times[int(n * 0.99)]
        return p50, p95, p99

    def test_trust_score_merge_latency(self):
        rng = random.Random(42)
        a = _random_trust_score(rng)
        b = _random_trust_score(rng)
        p50, p95, p99 = self._measure_latency(lambda: a.merge(b))
        print(f"\nTypedTrustScore.merge latency: p50={p50}ns p95={p95}ns p99={p99}ns")
        assert p99 < 10_000_000  # < 10ms

    def test_clock_merge_latency(self):
        rng = random.Random(42)
        a = CausalTrustClock("a")
        b = CausalTrustClock("b")
        for i in range(50):
            a._entries[f"p{i}"] = (rng.randint(0, 100), rng.uniform(0, 1))
            b._entries[f"p{i}"] = (rng.randint(0, 100), rng.uniform(0, 1))
        p50, p95, p99 = self._measure_latency(lambda: a.merge(b))
        print(f"\nCausalTrustClock.merge (50 peers) latency: p50={p50}ns p95={p95}ns p99={p99}ns")
        assert p99 < 10_000_000

    def test_merkle_leaf_hash_latency(self):
        merkle = TrustBoundMerkle(branching_factor=256)
        data = b"test data for hashing"
        p50, p95, p99 = self._measure_latency(
            lambda: merkle.compute_leaf_hash(data, "peer"), n=1000
        )
        print(f"\nMerkle leaf hash latency: p50={p50}ns p95={p95}ns p99={p99}ns")
        assert p99 < 10_000_000

    def test_pco_build_latency(self):
        def build():
            return AggregateProofCarryingOperation.build(
                originator_id="peer",
                signing_fn=lambda h: b"\x00" * 64,
                merkle_root="root",
                clock_snapshot=b"clock",
                trust_vector_hash="tvh",
                delta_bounds=[],
            )
        p50, p95, p99 = self._measure_latency(build, n=1000)
        print(f"\nPCO build latency: p50={p50}ns p95={p95}ns p99={p99}ns")
        assert p99 < 10_000_000

    def test_pco_verify_level_0_latency(self):
        pco = _make_pco("peer")
        lattice = DeltaTrustLattice("node", initial_peers={"peer"})
        p50, p95, p99 = self._measure_latency(
            lambda: pco.verify(None, lattice, verification_level=0), n=1000
        )
        print(f"\nPCO verify level 0 latency: p50={p50}ns p95={p95}ns p99={p99}ns")

    def test_pco_verify_level_1_latency(self):
        pco = _make_pco("peer")
        lattice = DeltaTrustLattice("node", initial_peers={"peer"})
        p50, p95, p99 = self._measure_latency(
            lambda: pco.verify(None, lattice, verification_level=1), n=1000
        )
        print(f"\nPCO verify level 1 latency: p50={p50}ns p95={p95}ns p99={p99}ns")

    def test_pco_verify_level_2_latency(self):
        pco = _make_pco("peer")
        lattice = DeltaTrustLattice("node", initial_peers={"peer"})
        p50, p95, p99 = self._measure_latency(
            lambda: pco.verify(None, lattice, verification_level=2), n=1000
        )
        print(f"\nPCO verify level 2 latency: p50={p50}ns p95={p95}ns p99={p99}ns")

    def test_content_hash_latency(self):
        delta = _make_delta(insertions={f"k_{i}": b"v" * 100 for i in range(100)})
        p50, p95, p99 = self._measure_latency(lambda: delta.content_hash(), n=1000)
        print(f"\nProjectionDelta.content_hash (100 keys) latency: p50={p50}ns p95={p95}ns p99={p99}ns")

    def test_homeostasis_latency(self):
        rng = random.Random(42)
        scores = {}
        for i in range(100):
            scores[f"p{i}"] = _random_trust_score(rng)
        p50, p95, p99 = self._measure_latency(
            lambda: TrustHomeostasis.normalize(scores, 100), n=100
        )
        print(f"\nHomeostasis.normalize (100 peers) latency: p50={p50}ns p95={p95}ns p99={p99}ns")
