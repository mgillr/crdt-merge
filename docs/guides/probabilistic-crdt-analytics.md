# Probabilistic CRDTs: Federated Analytics Without a Central Aggregator

> **Patent — UK Application No. 2607132.4, GB2608127.3**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Exact-Count Problem at Scale

You want to know: how many unique users visited your platform this week? Across 500 edge nodes, each seeing a different slice of traffic.

**The naive answer:** Collect all user IDs at a central aggregator, deduplicate. Cost: ship all the data. At 1B events/day across 500 nodes, that's petabytes of transfer per week. And the aggregator is a single point of failure.

**The approximate answer everyone uses:** HyperLogLog. Count cardinality in O(m) space with ~0.81% error. But every existing HyperLogLog implementation requires a **central merge step** — you can't merge two HLLs on different nodes without one of them acting as the coordinator.

**crdt-merge's answer:** `MergeableHLL`, `MergeableBloom`, and `MergeableCMS` — probabilistic data structures that are **native CRDTs**. Their merge operations are commutative, associative, and idempotent by mathematical construction. No central coordinator. Any node can merge with any other node in any order and arrive at the same answer.

This is not an implementation trick. It is a fundamental property of these structures: HyperLogLog's merge operation is register-max (pointwise maximum). That is trivially commutative and associative. The same for Bloom filter bitwise-OR and Count-Min Sketch per-cell max. These data structures were always CRDTs — crdt-merge exposes that property as a composable API.

---

## The Three Probabilistic CRDTs

### MergeableHLL — Cardinality Estimation

```
Memory: O(2^precision) bytes   (~16KB at precision=14)
Error:  1.04 / sqrt(2^precision) ≈ 0.81% at precision=14
Merge:  register-max (commutative, associative, idempotent)
Use:    "How many unique X?" without storing X
```

### MergeableBloom — Set Membership

```
Memory: O(-n × ln(fp_rate) / ln(2)^2)
Error:  fp_rate false positives (no false negatives)
Merge:  bitwise OR (commutative, associative, idempotent)
Use:    "Have we seen X before?" without storing X
```

### MergeableCMS — Frequency Estimation

```
Memory: O(width × depth)
Error:  ε-approximation, probability ≥ 1 - δ
Merge:  per-cell max (commutative, associative, idempotent)
Use:    "How many times did X appear?" at massive scale
```

---

## Quick Start

```python
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS

# HyperLogLog: count unique users across edge nodes
hll_edge_1 = MergeableHLL(precision=14)
hll_edge_2 = MergeableHLL(precision=14)

for user_id in edge_1_traffic:  # e.g., 50M events
    hll_edge_1.add(user_id)

for user_id in edge_2_traffic:  # e.g., 50M events (overlapping)
    hll_edge_2.add(user_id)

# Merge — commutative, any order, same result
merged_hll = hll_edge_1.merge(hll_edge_2)
print(f"Unique users (estimated): {merged_hll.cardinality():,.0f}")
print(f"Standard error: ±{merged_hll.standard_error():.2%}")
# Memory used: 16KB instead of storing 100M user IDs (gigabytes)
```

---

## Cookbook: HyperLogLog for Federated Cardinality

```python
from crdt_merge.probabilistic import MergeableHLL

# 500 CDN edge nodes, each counting unique page views
# Node reports only 16KB HLL state — not all user IDs
edge_nodes = [MergeableHLL(precision=14) for _ in range(500)]

# Each node counts its local traffic
for i, node in enumerate(edge_nodes):
    # Simulate 2M unique users per node with 40% overlap
    for j in range(2_000_000):
        user_id = f"user_{(j + i * 1_200_000) % 3_000_000}"  # 40% overlap
        node.add(user_id)

# Hierarchical merge — no central server needed
# Level 1: merge within region (50 nodes per region, 10 regions)
regional_hlls = []
for r in range(10):
    regional = edge_nodes[r * 50]
    for n in edge_nodes[r * 50 + 1 : (r + 1) * 50]:
        regional = regional.merge(n)
    regional_hlls.append(regional)

# Level 2: merge across regions
global_hll = regional_hlls[0]
for r in regional_hlls[1:]:
    global_hll = global_hll.merge(r)

print(f"Global unique users: {global_hll.cardinality():,.0f}")
print(f"Error: ±{global_hll.standard_error():.2%}")
print(f"Total memory: {14 * 16_384 / 1024:.0f} KB (vs {3_000_000 * 8 / 1024 / 1024:.0f} MB exact)")
# ~220 KB for 500 nodes vs 23 MB for exact counting — 100x compression
```

---

## Cookbook: Bloom Filter for Distributed Deduplication

```python
from crdt_merge.probabilistic import MergeableBloom

# Three workers processing an event stream — deduplicate events without coordination
# Each worker maintains a Bloom filter of seen event IDs

worker_a = MergeableBloom(capacity=10_000_000, fp_rate=0.001)
worker_b = MergeableBloom(capacity=10_000_000, fp_rate=0.001)
worker_c = MergeableBloom(capacity=10_000_000, fp_rate=0.001)

# Workers process events in parallel
for event_id in worker_a_events:
    if not worker_a.contains(event_id):
        worker_a.add(event_id)
        process_event(event_id)  # process only new events

for event_id in worker_b_events:
    if not worker_b.contains(event_id):
        worker_b.add(event_id)
        process_event(event_id)

for event_id in worker_c_events:
    if not worker_c.contains(event_id):
        worker_c.add(event_id)
        process_event(event_id)

# Periodic sync: merge Bloom filters — bitwise OR, commutative, any order
merged = worker_a.merge(worker_b).merge(worker_c)

# All workers now have the global dedup view
# Update each worker with the merged state
worker_a = merged
worker_b = merged  # They all share the same merged filter
worker_c = merged

print(f"False positive rate: {merged.estimated_fp_rate():.4%}")
print(f"Memory: {merged.bit_count / 8 / 1024:.0f} KB per worker")
```

---

## Cookbook: Count-Min Sketch for Heavy Hitter Detection

```python
from crdt_merge.probabilistic import MergeableCMS

# Detect top trending topics across distributed news feeds
# Each region counts topic mentions locally

region_eu = MergeableCMS(width=2000, depth=7)
region_us = MergeableCMS(width=2000, depth=7)
region_apac = MergeableCMS(width=2000, depth=7)

# Each region processes its local event stream
topics_eu   = ["AI", "AI", "climate", "AI", "EU_policy", "climate"]
topics_us   = ["AI", "election", "AI", "AI", "climate", "AI"]
topics_apac = ["AI", "trade", "trade", "climate", "AI"]

for topic in topics_eu:
    region_eu.add(topic)
for topic in topics_us:
    region_us.add(topic)
for topic in topics_apac:
    region_apac.add(topic)

# Merge all regions — per-cell max, commutative
global_cms = region_eu.merge(region_us).merge(region_apac)

# Query global frequency estimates
topics_to_check = ["AI", "climate", "election", "trade", "EU_policy"]
for topic in topics_to_check:
    count = global_cms.estimate(topic)
    print(f"{topic}: ~{count} mentions")
# AI: ~10, climate: ~5, election: ~2, trade: ~2, EU_policy: ~1
```

---

## Scenario: Real-Time Fraud Detection at Global Scale

A payment network processes 50,000 transactions per second across 200 regional processing nodes. Detecting whether a card has been used recently (in the last 5 minutes) requires distributed state.

**Today:** Centralized Redis cluster. All 200 nodes write card-seen events to Redis. Redis is the bottleneck: maximum 1M ops/sec. At 50K TPS × 200 nodes = 10M ops/sec, Redis is saturated.

**With MergeableBloom:**

```python
from crdt_merge.probabilistic import MergeableBloom
import time

class FraudDetectionNode:
    """Each processing node maintains its own Bloom filter window."""

    def __init__(self, node_id: str, window_minutes: int = 5):
        self.node_id = node_id
        self.window_minutes = window_minutes
        # Two filters: current window + previous (sliding window)
        self.current = MergeableBloom(capacity=5_000_000, fp_rate=0.001)
        self.previous = MergeableBloom(capacity=5_000_000, fp_rate=0.001)
        self._window_start = time.time()

    def is_duplicate(self, card_hash: str) -> bool:
        """O(k) membership test — no network call."""
        return self.current.contains(card_hash) or self.previous.contains(card_hash)

    def record_transaction(self, card_hash: str):
        """O(k) insert — no network call."""
        # Rotate window if needed
        if time.time() - self._window_start > self.window_minutes * 60:
            self.previous = self.current
            self.current = MergeableBloom(capacity=5_000_000, fp_rate=0.001)
            self._window_start = time.time()
        self.current.add(card_hash)

    def sync(self, peer_node: "FraudDetectionNode"):
        """Merge peer's filter — bitwise OR, no coordinator."""
        self.current = self.current.merge(peer_node.current)
        self.previous = self.previous.merge(peer_node.previous)


# 200 nodes, each processing 250 TPS locally — no Redis bottleneck
nodes = [FraudDetectionNode(f"node-{i}") for i in range(200)]

# Each node operates independently, syncing with 3 random peers every 10 seconds
# Convergence: every card seen by any node becomes globally visible in O(log 200) = 8 sync rounds
# At 10s gossip intervals: 80 seconds to global convergence — well within 5-minute fraud window

# False positive rate: 0.1% → 50 false declines per 50,000 TPS = acceptable
print("Fraud detection: decentralized, O(1) per transaction, no Redis dependency")
```

---

## Scenario: A/B Test Analytics Without a Data Warehouse

A product team runs 50 simultaneous A/B tests across a web application. Each test records conversion events. No data warehouse — just edge nodes.

```python
from crdt_merge.probabilistic import MergeableHLL, MergeableCMS

class ABTestNode:
    """Edge node tracking A/B test metrics locally."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        # One HLL per test variant for unique user counting
        self.unique_users: dict[str, MergeableHLL] = {}
        # One CMS per test for event frequency
        self.event_counts: dict[str, MergeableCMS] = {}

    def record_exposure(self, test_id: str, variant: str, user_id: str):
        key = f"{test_id}:{variant}"
        if key not in self.unique_users:
            self.unique_users[key] = MergeableHLL(precision=12)
        self.unique_users[key].add(user_id)

    def record_conversion(self, test_id: str, variant: str, event_type: str):
        key = f"{test_id}:{variant}"
        if key not in self.event_counts:
            self.event_counts[key] = MergeableCMS(width=1000, depth=5)
        self.event_counts[key].add(event_type)

    def merge(self, other: "ABTestNode") -> "ABTestNode":
        merged = ABTestNode(f"{self.node_id}+{other.node_id}")
        all_keys = set(self.unique_users) | set(other.unique_users)
        for key in all_keys:
            a = self.unique_users.get(key, MergeableHLL(precision=12))
            b = other.unique_users.get(key, MergeableHLL(precision=12))
            merged.unique_users[key] = a.merge(b)
        return merged

    def conversion_rate(self, test_id: str, variant: str) -> float:
        key = f"{test_id}:{variant}"
        users = self.unique_users.get(key)
        events = self.event_counts.get(key)
        if not users or not events:
            return 0.0
        return events.estimate("conversion") / max(users.cardinality(), 1)


# 10 edge nodes, each tracking their local traffic
edge_nodes = [ABTestNode(f"edge-{i}") for i in range(10)]

# After traffic period — merge all nodes into global view
global_view = edge_nodes[0]
for node in edge_nodes[1:]:
    global_view = global_view.merge(node)

# Report conversion rates — no warehouse query, no ETL pipeline
for test_id in ["test_checkout", "test_landing", "test_pricing"]:
    for variant in ["control", "treatment"]:
        rate = global_view.conversion_rate(test_id, variant)
        print(f"{test_id} / {variant}: {rate:.2%} conversion")
```

---

## Scenario: Distributed Model Usage Monitoring

100 inference nodes each serve LLM requests. Monitor token usage, unique users, and model versions without a central metrics database.

```python
from crdt_merge.probabilistic import MergeableHLL, MergeableCMS

class InferenceMetricsNode:
    def __init__(self, node_id: str):
        self.unique_users = MergeableHLL(precision=14)
        self.token_counts = MergeableCMS(width=2000, depth=7)
        self.model_usage = MergeableCMS(width=500, depth=5)

    def record_request(self, user_id: str, model: str, tokens: int):
        self.unique_users.add(user_id)
        self.token_counts.add("total_tokens", count=tokens)
        self.model_usage.add(model)

    def merge(self, other: "InferenceMetricsNode") -> "InferenceMetricsNode":
        merged = InferenceMetricsNode(f"merged")
        merged.unique_users = self.unique_users.merge(other.unique_users)
        merged.token_counts = self.token_counts.merge(other.token_counts)
        merged.model_usage = self.model_usage.merge(other.model_usage)
        return merged


# 100 inference nodes
nodes = [InferenceMetricsNode(f"inference-{i}") for i in range(100)]

# Global metrics: merge all nodes
global_metrics = nodes[0]
for node in nodes[1:]:
    global_metrics = global_metrics.merge(node)

print(f"Daily active users: {global_metrics.unique_users.cardinality():,.0f} (±{global_metrics.unique_users.standard_error():.2%})")
print(f"Total tokens: {global_metrics.token_counts.estimate('total_tokens'):,.0f}")
# No Prometheus, no ClickHouse, no central aggregator
```

---

## Why Probabilistic CRDTs Are Fundamental

The insight that probabilistic data structures are natural CRDTs has deeper implications than analytics efficiency:

**They solve the fundamental space-accuracy tradeoff in distributed systems.** Exact CRDTs (GCounters, ORSets) require space proportional to the data. At billion-user scale, this is infeasible. Probabilistic CRDTs offer a formal way to trade a small, bounded, known amount of accuracy for O(1) space — and because they are CRDTs, they maintain all convergence guarantees.

**They enable federated analytics without data centralisation.** When regulations prohibit sharing raw data (GDPR, HIPAA), approximate summaries — cardinalities, frequency sketches, membership — can often be shared without exposing underlying data. Probabilistic CRDTs make these summaries mergeable without a coordinator.

**The error bounds are provable and controllable.** Unlike heuristic approximations, the error of HLL, Bloom, and CMS is mathematically bounded and configurable at construction time. A system designer can choose the space-accuracy tradeoff explicitly.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Gossip Protocol: Distributed Sync Without a Server](./gossip-serverless-sync.md)
- [Guide — Delta Sync and Merkle Verification](./delta-sync-merkle-verification.md)
- [Guide — Privacy-Preserving Merge](./privacy-preserving-merge.md)
- [API Reference — Probabilistic CRDTs](../api-reference/layer2-analytics/probabilistic.md)
