"""Performance benchmarks — verify the speed claims."""
import time
from crdt_merge.core import GCounter, LWWRegister, ORSet
from crdt_merge.dataframe import merge
from crdt_merge.dedup import dedup_list, MinHashDedup


class TestPerformance:
    def test_gcounter_throughput(self):
        c = GCounter()
        start = time.perf_counter()
        for i in range(100_000):
            c.increment("n1")
        elapsed = time.perf_counter() - start
        ops_per_sec = 100_000 / elapsed
        print(f"\nGCounter: {ops_per_sec:,.0f} ops/sec")
        assert ops_per_sec > 500_000  # Should be >500K ops/sec

    def test_merge_throughput(self):
        a = GCounter()
        b = GCounter()
        for i in range(100):
            a.increment(f"n_{i}", 10)
            b.increment(f"n_{i}", 20)
        start = time.perf_counter()
        for _ in range(10_000):
            a.merge(b)
        elapsed = time.perf_counter() - start
        ops_per_sec = 10_000 / elapsed
        print(f"\nGCounter merge (100 nodes): {ops_per_sec:,.0f} merges/sec")
        assert ops_per_sec > 10_000

    def test_dataframe_merge_10k_rows(self):
        a = [{"id": i, "val": f"a_{i}", "score": i * 1.1} for i in range(10_000)]
        b = [{"id": i, "val": f"b_{i}", "score": i * 2.2} for i in range(5_000, 15_000)]
        start = time.perf_counter()
        result = merge(a, b, key="id")
        elapsed = time.perf_counter() - start
        print(f"\nDataFrame merge (10K+10K → 15K): {elapsed*1000:.1f}ms")
        assert len(result) == 15_000
        assert elapsed < 5.0  # Should be under 5s

    def test_dedup_10k(self):
        items = [f"item_{i % 5000}" for i in range(10_000)]  # 50% dupes
        start = time.perf_counter()
        unique, dups = dedup_list(items)
        elapsed = time.perf_counter() - start
        print(f"\nDedup 10K items (50% dupes): {elapsed*1000:.1f}ms → {len(unique)} unique")
        assert len(unique) == 5_000
        assert elapsed < 2.0

    def test_orset_10k(self):
        s = ORSet()
        start = time.perf_counter()
        for i in range(10_000):
            s.add(f"item_{i}")
        elapsed = time.perf_counter() - start
        ops_per_sec = 10_000 / elapsed
        print(f"\nORSet add: {ops_per_sec:,.0f} ops/sec")
        assert len(s.value) == 10_000

    def test_minhash_1k(self):
        mh = MinHashDedup(num_hashes=64, threshold=0.5)
        items = [f"This is test document number {i} with some varying content about topic {i%10}" for i in range(1000)]
        start = time.perf_counter()
        unique = mh.dedup(items, text_fn=lambda x: x)
        elapsed = time.perf_counter() - start
        print(f"\nMinHash dedup 1K docs: {elapsed*1000:.1f}ms → {len(unique)} unique")
        assert elapsed < 30.0
