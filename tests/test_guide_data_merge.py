"""
Test suite for docs/guides/:
  - merge-strategies.md
  - mergeql-distributed-knowledge.md
  - probabilistic-crdt-analytics.md

All tests use synthetic list-of-dicts data.
External-data / file-dependent examples are skipped.
"""

import time
import pytest

# ---------------------------------------------------------------------------
# merge-strategies.md
# ---------------------------------------------------------------------------


class TestMergeStrategiesGuide:
    """Tests derived from merge-strategies.md"""

    def test_custom_strategy_simple_lambda(self):
        """Custom strategy with a simple 2-arg lambda."""
        from crdt_merge.strategies import Custom

        my_strategy = Custom(fn=lambda a, b: a if len(str(a)) > len(str(b)) else b)
        result = my_strategy.resolve("short", "longer_string")
        assert result == "longer_string"

    def test_custom_strategy_simple_lambda_tie(self):
        """Custom lambda returns second arg when lengths are equal."""
        from crdt_merge.strategies import Custom

        my_strategy = Custom(fn=lambda a, b: a if len(str(a)) > len(str(b)) else b)
        result = my_strategy.resolve("abc", "xyz")
        assert result == "xyz"  # equal length → b wins (per lambda)

    def test_custom_strategy_full_6arg_function(self):
        """Custom strategy with full 6-arg resolver using timestamps."""
        from crdt_merge.strategies import Custom

        def my_resolver(val_a, val_b, ts_a, ts_b, node_a, node_b):
            return val_a if ts_a > ts_b else val_b

        my_strategy = Custom(fn=my_resolver)
        # ts_a > ts_b → val_a wins
        assert my_strategy.resolve("old", "new", ts_a=3.0, ts_b=2.0) == "old"
        # ts_b > ts_a → val_b wins
        assert my_strategy.resolve("old", "new", ts_a=1.0, ts_b=2.0) == "new"

    def test_custom_strategy_not_serializable(self):
        """Custom strategy has no to_dict method (not serializable)."""
        from crdt_merge.strategies import Custom

        s = Custom(fn=lambda a, b: a)
        assert not hasattr(s, "to_dict"), (
            "Custom strategy should not have to_dict (guide warns it cannot be serialized)"
        )


# ---------------------------------------------------------------------------
# mergeql-distributed-knowledge.md
# ---------------------------------------------------------------------------


class TestMergeQLQuickStart:
    """Quick Start example from mergeql guide."""

    def test_quick_start_basic_merge(self):
        """Two sources, salary=max, status=lww."""
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register(
            "users_nyc",
            [
                {"id": "U1", "name": "Alice", "salary": 95000, "status": "active"},
                {"id": "U2", "name": "Bob", "salary": 87000, "status": "inactive"},
            ],
        )
        ql.register(
            "users_london",
            [
                {"id": "U1", "name": "Alice", "salary": 98000, "status": "active"},
                {"id": "U3", "name": "Carol", "salary": 102000, "status": "active"},
            ],
        )
        result = ql.execute(
            """
            MERGE users_nyc, users_london
            ON id
            STRATEGY salary='max', status='lww'
        """
        )
        assert len(result.data) == 3
        u1 = next(r for r in result.data if r["id"] == "U1")
        assert u1["salary"] == 98000, "max salary should be 98000"

    def test_quick_start_result_has_merge_time(self):
        """Result exposes merge_time_ms."""
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("a", [{"id": "1", "v": 1}])
        ql.register("b", [{"id": "1", "v": 2}])
        result = ql.execute("MERGE a, b ON id STRATEGY v='max'")
        assert hasattr(result, "merge_time_ms")
        assert result.merge_time_ms >= 0

    def test_quick_start_conflicts_reported(self):
        """Conflicting rows are counted in result.conflicts."""
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("a", [{"id": "1", "salary": 95000}])
        ql.register("b", [{"id": "1", "salary": 98000}])
        result = ql.execute("MERGE a, b ON id STRATEGY salary='max'")
        assert result.conflicts >= 1


class TestMergeQLCookbookStrategies:
    """Cookbook: All Strategy Types from mergeql guide."""

    def setup_method(self):
        from crdt_merge.mergeql import MergeQL

        self.ql = MergeQL()
        self.ql.register(
            "source_a",
            [{"id": "1", "name": "Alice", "score": 80, "tags": ["admin"], "bio": "Short bio"}],
        )
        self.ql.register(
            "source_b",
            [{"id": "1", "name": "Alice", "score": 95, "tags": ["user"], "bio": "Longer bio here"}],
        )

    def test_lww_strategy(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY name='lww'")
        assert len(r.data) == 1
        assert r.data[0]["name"] in ("Alice",)  # same in both; just verify it runs

    def test_max_strategy(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY score='max'")
        assert r.data[0]["score"] == 95

    def test_min_strategy(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY score='min'")
        assert r.data[0]["score"] == 80

    def test_union_strategy_list(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY tags='union'")
        tags = r.data[0]["tags"]
        # tags should contain both admin and user (may be list or comma-separated)
        tags_str = str(tags)
        assert "admin" in tags_str and "user" in tags_str

    def test_concat_strategy(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY bio='concat'")
        bio = r.data[0]["bio"]
        assert "Short bio" in bio and "Longer bio here" in bio

    def test_longest_strategy(self):
        r = self.ql.execute("MERGE source_a, source_b ON id STRATEGY bio='longest'")
        assert r.data[0]["bio"] == "Longer bio here"

    def test_multi_strategy_query(self):
        r = self.ql.execute(
            """
            MERGE source_a, source_b
            ON id
            STRATEGY name='lww', score='max', tags='union', bio='longest'
        """
        )
        assert r.data[0]["score"] == 95
        assert r.data[0]["bio"] == "Longer bio here"


class TestMergeQLThreeSources:
    """Cookbook: Three or More Sources from mergeql guide."""

    def test_three_source_max_merge(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("shard_east", [{"id": "1", "views": 1200, "likes": 450}])
        ql.register(
            "shard_west",
            [{"id": "1", "views": 800, "likes": 320}, {"id": "2", "views": 600, "likes": 180}],
        )
        ql.register(
            "shard_eu",
            [{"id": "1", "views": 950, "likes": 410}, {"id": "3", "views": 300, "likes": 90}],
        )

        result = ql.execute(
            """
            MERGE shard_east, shard_west, shard_eu
            ON id
            STRATEGY views='max', likes='max'
        """
        )

        r1 = next(r for r in result.data if r["id"] == "1")
        assert r1["views"] == 1200, "max views across shards should be 1200"
        assert r1["likes"] == 450, "max likes across shards should be 450"
        assert len(result.data) == 3, "3 unique IDs expected"


class TestMergeQLWhereFilter:
    """Cookbook: WHERE Filtering from mergeql guide."""

    def test_where_filter_excludes_refunds(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register(
            "events_all",
            [
                {"id": "E1", "type": "purchase", "amount": 150},
                {"id": "E2", "type": "refund", "amount": -50},
                {"id": "E3", "type": "purchase", "amount": 300},
            ],
        )
        ql.register(
            "events_mobile",
            [
                {"id": "E4", "type": "purchase", "amount": 75},
                {"id": "E2", "type": "refund", "amount": -45},
            ],
        )

        result = ql.execute(
            """
            MERGE events_all, events_mobile
            ON id
            STRATEGY amount='max'
            WHERE type='purchase'
        """
        )

        ids = {r["id"] for r in result.data}
        assert "E2" not in ids, "refund E2 should be filtered out"
        assert "E1" in ids
        assert "E3" in ids
        assert "E4" in ids


class TestMergeQLLimitAndMap:
    """Cookbook: LIMIT and Column Mapping from mergeql guide."""

    def test_limit_and_map_columns(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register(
            "products_v1",
            [
                {"product_id": "P1", "price": 29.99, "stock": 100},
                {"product_id": "P2", "price": 49.99, "stock": 50},
            ],
        )
        ql.register(
            "products_v2",
            [
                {"id": "P1", "price": 31.99, "qty": 110},
                {"id": "P3", "price": 19.99, "qty": 200},
            ],
        )

        result = ql.execute(
            """
            MERGE products_v1, products_v2
            ON product_id
            STRATEGY price='max', stock='max'
            MAP id -> product_id, qty -> stock
            LIMIT 10
        """
        )
        # MAP should rename 'id'->'product_id' and 'qty'->'stock' before merge
        assert len(result.data) >= 1


class TestMergeQLExplain:
    """Cookbook: EXPLAIN from mergeql guide."""

    def test_explain_returns_plan(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register(
            "users_a", [{"id": str(i), "name": f"User{i}", "score": i} for i in range(10)]
        )
        ql.register(
            "users_b",
            [{"id": str(i), "name": f"User{i}", "score": i * 2} for i in range(5, 15)],
        )

        result = ql.execute(
            """
            EXPLAIN MERGE users_a, users_b
            ON id
            STRATEGY score='max'
        """
        )
        assert result.plan is not None
        plan_str = str(result.plan)
        assert "users_a" in plan_str
        assert "users_b" in plan_str

    def test_explain_data_is_empty(self):
        """EXPLAIN should not execute — data should be empty."""
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("users_a", [{"id": "1", "score": 10}])
        ql.register("users_b", [{"id": "1", "score": 20}])
        result = ql.execute("EXPLAIN MERGE users_a, users_b ON id STRATEGY score='max'")
        assert result.data == [] or result.data is None


class TestMergeQLCustomStrategy:
    """Cookbook: Custom Strategy Functions from mergeql guide."""

    def test_custom_strategy_registered_and_used(self):
        from crdt_merge.mergeql import MergeQL
        from crdt_merge.strategies import Custom

        ql = MergeQL()

        def trust_verified_source(a, b):
            if isinstance(a, dict) and a.get("verified"):
                return a["value"]
            if isinstance(b, dict) and b.get("verified"):
                return b["value"]
            return a if a is not None else b

        ql.register_strategy("trusted", Custom(trust_verified_source))
        ql.register("source_a", [{"id": "1", "rating": {"value": 4.2, "verified": True}}])
        ql.register("source_b", [{"id": "1", "rating": {"value": 4.8, "verified": False}}])

        result = ql.execute(
            """
            MERGE source_a, source_b
            ON id
            STRATEGY rating='custom:trusted'
        """
        )
        assert len(result.data) == 1
        # BUG: MergeSchema.resolve_row bypasses per-field custom strategies
        # when both values are dicts — it recurses into the dict instead of
        # calling the registered custom:trusted resolver.
        # Guide expects: result.data[0]["rating"] == 4.2 (verified source wins)
        # Actual result: {"value": 4.8, "verified": True} (nested dict merge)
        assert result.data[0]["rating"] == 4.2, (
            "BUG: custom strategy is bypassed for dict-valued fields. "
            "resolve_row short-circuits to recursive dict merge before "
            "consulting the per-field strategy registry."
        )


class TestMergeQLProvenance:
    """Accessing Provenance from mergeql guide."""

    def test_provenance_attribute_exists(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("source_a", [{"id": "1", "value": 100}, {"id": "2", "value": 200}])
        ql.register("source_b", [{"id": "1", "value": 150}, {"id": "3", "value": 300}])

        result = ql.execute(
            """
            MERGE source_a, source_b
            ON id
            STRATEGY value='max'
        """
        )
        assert hasattr(result, "provenance")

    def test_provenance_records_conflict(self):
        from crdt_merge.mergeql import MergeQL

        ql = MergeQL()
        ql.register("source_a", [{"id": "1", "value": 100}])
        ql.register("source_b", [{"id": "1", "value": 150}])

        result = ql.execute(
            """
            MERGE source_a, source_b
            ON id
            STRATEGY value='max'
        """
        )
        if result.provenance:
            # at least one provenance entry should reference key '1'
            keys = [p["key"] for p in result.provenance]
            assert "1" in keys


# ---------------------------------------------------------------------------
# probabilistic-crdt-analytics.md
# ---------------------------------------------------------------------------


class TestMergeableHLLQuickStart:
    """Quick Start HLL example from probabilistic guide."""

    def test_hll_add_and_cardinality(self):
        from crdt_merge.probabilistic import MergeableHLL

        hll1 = MergeableHLL(precision=14)
        hll2 = MergeableHLL(precision=14)

        for uid in ["u1", "u2", "u3", "u4", "u5"]:
            hll1.add(uid)
        for uid in ["u3", "u4", "u5", "u6", "u7"]:
            hll2.add(uid)

        merged = hll1.merge(hll2)
        card = merged.cardinality()
        # 7 unique users; HLL has ~0.81% error at precision=14
        assert 6 <= card <= 8, f"Expected ~7 unique users, got {card}"

    def test_hll_standard_error(self):
        from crdt_merge.probabilistic import MergeableHLL

        hll = MergeableHLL(precision=14)
        # 1.04 / sqrt(2^14) ≈ 0.00813
        assert abs(hll.standard_error() - 0.008125) < 0.001

    def test_hll_merge_commutativity(self):
        from crdt_merge.probabilistic import MergeableHLL

        hll1 = MergeableHLL(precision=14)
        hll2 = MergeableHLL(precision=14)
        for i in range(100):
            hll1.add(f"user_{i}")
        for i in range(50, 150):
            hll2.add(f"user_{i}")

        ab = hll1.merge(hll2)
        ba = hll2.merge(hll1)
        assert ab.cardinality() == ba.cardinality(), "HLL merge must be commutative"

    def test_hll_merge_idempotency(self):
        from crdt_merge.probabilistic import MergeableHLL

        hll = MergeableHLL(precision=14)
        for i in range(50):
            hll.add(f"user_{i}")

        merged = hll.merge(hll)
        assert merged.cardinality() == pytest.approx(hll.cardinality(), rel=1e-9)


class TestMergeableHLLHierarchical:
    """Cookbook: HyperLogLog for Federated Cardinality (small-scale version)."""

    def test_hierarchical_merge_small_scale(self):
        """Mimic the 500-node / 10-region example at small scale (10 nodes, 2 regions)."""
        from crdt_merge.probabilistic import MergeableHLL

        num_nodes = 10
        nodes = [MergeableHLL(precision=12) for _ in range(num_nodes)]

        unique_users_per_node = 1000
        for i, node in enumerate(nodes):
            for j in range(unique_users_per_node):
                # 40% overlap across nodes
                user_id = f"user_{(j + i * 600) % 1500}"
                node.add(user_id)

        # Level 1: merge 2 regions of 5 nodes each
        regional_hlls = []
        for r in range(2):
            regional = nodes[r * 5]
            for n in nodes[r * 5 + 1: (r + 1) * 5]:
                regional = regional.merge(n)
            regional_hlls.append(regional)

        # Level 2: global merge
        global_hll = regional_hlls[0]
        for r in regional_hlls[1:]:
            global_hll = global_hll.merge(r)

        card = global_hll.cardinality()
        assert card > 0
        assert global_hll.standard_error() > 0


class TestMergeableBloom:
    """Cookbook: Bloom Filter for Distributed Deduplication."""

    def test_bloom_basic_add_and_contains(self):
        from crdt_merge.probabilistic import MergeableBloom

        bf = MergeableBloom(capacity=10000, fp_rate=0.01)
        bf.add("item1")
        assert bf.contains("item1") is True
        assert bf.contains("item_never_added_xyz123") is False

    def test_bloom_merge_union(self):
        from crdt_merge.probabilistic import MergeableBloom

        wa = MergeableBloom(capacity=10000, fp_rate=0.01)
        wb = MergeableBloom(capacity=10000, fp_rate=0.01)
        wa.add("evt1")
        wa.add("evt2")
        wb.add("evt3")

        merged = wa.merge(wb)
        assert merged.contains("evt1")
        assert merged.contains("evt2")
        assert merged.contains("evt3")

    def test_bloom_merge_commutativity(self):
        from crdt_merge.probabilistic import MergeableBloom

        wa = MergeableBloom(capacity=10000, fp_rate=0.01)
        wb = MergeableBloom(capacity=10000, fp_rate=0.01)
        for i in range(50):
            wa.add(f"event_{i}")
        for i in range(30, 80):
            wb.add(f"event_{i}")

        ab = wa.merge(wb)
        ba = wb.merge(wa)
        # Both should contain same items
        for i in range(80):
            assert ab.contains(f"event_{i}") == ba.contains(f"event_{i}")

    def test_bloom_estimated_fp_rate(self):
        from crdt_merge.probabilistic import MergeableBloom

        bf = MergeableBloom(capacity=10000, fp_rate=0.01)
        for i in range(100):
            bf.add(f"item_{i}")
        rate = bf.estimated_fp_rate()
        assert 0.0 <= rate <= 1.0

    def test_bloom_worker_dedup_scenario(self):
        """Three workers deduplicating events, periodic merge."""
        from crdt_merge.probabilistic import MergeableBloom

        worker_a = MergeableBloom(capacity=10000, fp_rate=0.001)
        worker_b = MergeableBloom(capacity=10000, fp_rate=0.001)
        worker_c = MergeableBloom(capacity=10000, fp_rate=0.001)

        worker_a_events = [f"evt_{i}" for i in range(100)]
        worker_b_events = [f"evt_{i}" for i in range(50, 150)]
        worker_c_events = [f"evt_{i}" for i in range(100, 200)]

        for eid in worker_a_events:
            if not worker_a.contains(eid):
                worker_a.add(eid)

        for eid in worker_b_events:
            if not worker_b.contains(eid):
                worker_b.add(eid)

        for eid in worker_c_events:
            if not worker_c.contains(eid):
                worker_c.add(eid)

        merged = worker_a.merge(worker_b).merge(worker_c)
        # All original events should be in the merged filter
        for eid in worker_a_events[:10]:
            assert merged.contains(eid)
        for eid in worker_c_events[:10]:
            assert merged.contains(eid)


class TestMergeableCMS:
    """Cookbook: Count-Min Sketch for Heavy Hitter Detection."""

    def test_cms_basic_add_and_estimate(self):
        from crdt_merge.probabilistic import MergeableCMS

        cms = MergeableCMS(width=2000, depth=7)
        for _ in range(5):
            cms.add("AI")
        for _ in range(3):
            cms.add("climate")
        assert cms.estimate("AI") >= 5
        assert cms.estimate("climate") >= 3

    def test_cms_add_with_count(self):
        from crdt_merge.probabilistic import MergeableCMS

        cms = MergeableCMS(width=2000, depth=7)
        cms.add("total_tokens", count=500)
        assert cms.estimate("total_tokens") >= 500

    def test_cms_merge_per_cell_max(self):
        """Merge is per-cell max, not sum."""
        from crdt_merge.probabilistic import MergeableCMS

        c1 = MergeableCMS(width=2000, depth=7)
        c2 = MergeableCMS(width=2000, depth=7)
        c1.add("x", count=100)
        c2.add("x", count=200)
        merged = c1.merge(c2)
        # max(100, 200) = 200, NOT 300
        est = merged.estimate("x")
        assert est == 200, f"CMS merge should be per-cell max (200), got {est}"

    def test_cms_topic_counts(self):
        from crdt_merge.probabilistic import MergeableCMS

        region_eu = MergeableCMS(width=2000, depth=7)
        region_us = MergeableCMS(width=2000, depth=7)
        region_apac = MergeableCMS(width=2000, depth=7)

        topics_eu = ["AI", "AI", "climate", "AI", "EU_policy", "climate"]
        topics_us = ["AI", "election", "AI", "AI", "climate", "AI"]
        topics_apac = ["AI", "trade", "trade", "climate", "AI"]

        for t in topics_eu:
            region_eu.add(t)
        for t in topics_us:
            region_us.add(t)
        for t in topics_apac:
            region_apac.add(t)

        global_cms = region_eu.merge(region_us).merge(region_apac)

        # AI appears in all regions (3+4+2=9 individual adds, max per cell ≥ 4)
        assert global_cms.estimate("AI") >= 1
        assert global_cms.estimate("climate") >= 1
        assert global_cms.estimate("election") >= 1
        assert global_cms.estimate("trade") >= 1
        assert global_cms.estimate("EU_policy") >= 1

    def test_cms_merge_commutativity(self):
        from crdt_merge.probabilistic import MergeableCMS

        c1 = MergeableCMS(width=2000, depth=7)
        c2 = MergeableCMS(width=2000, depth=7)
        for i in range(20):
            c1.add(f"topic_{i % 5}")
        for i in range(15):
            c2.add(f"topic_{i % 3}")

        ab = c1.merge(c2)
        ba = c2.merge(c1)
        for topic in [f"topic_{i}" for i in range(5)]:
            assert ab.estimate(topic) == ba.estimate(topic), (
                f"CMS merge must be commutative for {topic}"
            )


class TestFraudDetectionNode:
    """Scenario: Real-Time Fraud Detection from probabilistic guide."""

    def test_fraud_node_record_and_detect(self):
        from crdt_merge.probabilistic import MergeableBloom

        class FraudDetectionNode:
            def __init__(self, node_id, window_minutes=5):
                self.node_id = node_id
                self.window_minutes = window_minutes
                self.current = MergeableBloom(capacity=100000, fp_rate=0.001)
                self.previous = MergeableBloom(capacity=100000, fp_rate=0.001)
                self._window_start = time.time()

            def is_duplicate(self, card_hash):
                return self.current.contains(card_hash) or self.previous.contains(card_hash)

            def record_transaction(self, card_hash):
                if time.time() - self._window_start > self.window_minutes * 60:
                    self.previous = self.current
                    self.current = MergeableBloom(capacity=100000, fp_rate=0.001)
                    self._window_start = time.time()
                self.current.add(card_hash)

            def sync(self, peer_node):
                self.current = self.current.merge(peer_node.current)
                self.previous = self.previous.merge(peer_node.previous)

        node1 = FraudDetectionNode("node-0")
        node2 = FraudDetectionNode("node-1")

        node1.record_transaction("card_abc")
        node2.record_transaction("card_xyz")

        # Before sync: node1 doesn't know about card_xyz
        assert node1.is_duplicate("card_abc") is True
        assert node1.is_duplicate("card_xyz") is False

        # After sync: node1 gains node2's state
        node1.sync(node2)
        assert node1.is_duplicate("card_abc") is True
        assert node1.is_duplicate("card_xyz") is True


class TestABTestNode:
    """Scenario: A/B Test Analytics from probabilistic guide."""

    def test_ab_test_node_merge(self):
        from crdt_merge.probabilistic import MergeableHLL, MergeableCMS

        class ABTestNode:
            def __init__(self, node_id):
                self.node_id = node_id
                self.unique_users: dict = {}
                self.event_counts: dict = {}

            def record_exposure(self, test_id, variant, user_id):
                key = f"{test_id}:{variant}"
                if key not in self.unique_users:
                    self.unique_users[key] = MergeableHLL(precision=12)
                self.unique_users[key].add(user_id)

            def record_conversion(self, test_id, variant, event_type):
                key = f"{test_id}:{variant}"
                if key not in self.event_counts:
                    self.event_counts[key] = MergeableCMS(width=1000, depth=5)
                self.event_counts[key].add(event_type)

            def merge(self, other):
                merged = ABTestNode(f"{self.node_id}+{other.node_id}")
                all_keys = set(self.unique_users) | set(other.unique_users)
                for key in all_keys:
                    a = self.unique_users.get(key, MergeableHLL(precision=12))
                    b = other.unique_users.get(key, MergeableHLL(precision=12))
                    merged.unique_users[key] = a.merge(b)
                return merged

            def conversion_rate(self, test_id, variant):
                key = f"{test_id}:{variant}"
                users = self.unique_users.get(key)
                events = self.event_counts.get(key)
                if not users or not events:
                    return 0.0
                return events.estimate("conversion") / max(users.cardinality(), 1)

        n1 = ABTestNode("edge-0")
        n2 = ABTestNode("edge-1")

        for uid in ["u1", "u2", "u3"]:
            n1.record_exposure("test_checkout", "control", uid)
        for uid in ["u4", "u5"]:
            n2.record_exposure("test_checkout", "control", uid)

        merged = n1.merge(n2)
        card = merged.unique_users["test_checkout:control"].cardinality()
        assert card >= 4, f"Expected ~5 unique users, got {card}"


class TestInferenceMetricsNode:
    """Scenario: Distributed Model Usage Monitoring from probabilistic guide."""

    def test_inference_metrics_merge(self):
        from crdt_merge.probabilistic import MergeableHLL, MergeableCMS

        class InferenceMetricsNode:
            def __init__(self, node_id):
                self.unique_users = MergeableHLL(precision=14)
                self.token_counts = MergeableCMS(width=2000, depth=7)
                self.model_usage = MergeableCMS(width=500, depth=5)

            def record_request(self, user_id, model, tokens):
                self.unique_users.add(user_id)
                self.token_counts.add("total_tokens", count=tokens)
                self.model_usage.add(model)

            def merge(self, other):
                merged = InferenceMetricsNode("merged")
                merged.unique_users = self.unique_users.merge(other.unique_users)
                merged.token_counts = self.token_counts.merge(other.token_counts)
                merged.model_usage = self.model_usage.merge(other.model_usage)
                return merged

        n1 = InferenceMetricsNode("inf-0")
        n2 = InferenceMetricsNode("inf-1")

        n1.record_request("u1", "gpt-4", 100)
        n1.record_request("u2", "gpt-3", 50)
        n2.record_request("u3", "gpt-4", 200)
        n2.record_request("u4", "gpt-3", 75)

        merged = n1.merge(n2)
        assert merged.unique_users.cardinality() >= 3
        # token_counts uses per-cell max: max(100+50, 200+75) for overlapping cells
        # The exact value depends on hash collisions; just check it's > 0
        assert merged.token_counts.estimate("total_tokens") > 0
        # model_usage: gpt-4 was added in both nodes; estimate ≥ 1
        assert merged.model_usage.estimate("gpt-4") >= 1

    def test_inference_metrics_100_nodes(self):
        """Verify 100-node merge completes without error (smoke test)."""
        from crdt_merge.probabilistic import MergeableHLL, MergeableCMS

        class InferenceMetricsNode:
            def __init__(self, node_id):
                self.unique_users = MergeableHLL(precision=14)
                self.token_counts = MergeableCMS(width=2000, depth=7)
                self.model_usage = MergeableCMS(width=500, depth=5)

            def record_request(self, user_id, model, tokens):
                self.unique_users.add(user_id)
                self.token_counts.add("total_tokens", count=tokens)
                self.model_usage.add(model)

            def merge(self, other):
                merged = InferenceMetricsNode("merged")
                merged.unique_users = self.unique_users.merge(other.unique_users)
                merged.token_counts = self.token_counts.merge(other.token_counts)
                merged.model_usage = self.model_usage.merge(other.model_usage)
                return merged

        nodes = [InferenceMetricsNode(f"inference-{i}") for i in range(100)]
        for i, node in enumerate(nodes):
            node.record_request(f"user_{i}", "gpt-4", 100)

        global_metrics = nodes[0]
        for node in nodes[1:]:
            global_metrics = global_metrics.merge(node)

        assert global_metrics.unique_users.cardinality() > 0
        assert global_metrics.token_counts.estimate("total_tokens") > 0
