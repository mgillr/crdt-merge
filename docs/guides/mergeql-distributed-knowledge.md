# MergeQL: A Query Language for Distributed Knowledge

> **Patent — UK Application No. 2607132.4, GB2608127.3**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## SQL Was Designed for a Single Source of Truth

SQL assumes one database. One transaction log. One consistent view of the world.

Distributed data doesn't work that way. When your data lives across multiple services, organisations, regions, or replicas, you don't have one source of truth — you have many, each partially right, some conflicting.

The current answer is ETL: extract data from all sources, load it into a centralised warehouse, run SQL there. This introduces:
- **Latency** — data is stale by the time you query it
- **Cost** — warehouses are expensive at scale
- **Compliance risk** — centralising sensitive data from multiple orgs creates a single breach target
- **Convergence blindness** — the ETL process doesn't know or care whether a merge is CRDT-correct

**MergeQL is SQL-like syntax for CRDT-correct distributed merge.** You express what you want to merge and how to resolve conflicts. MergeQL handles convergence, provenance, and conflict resolution — all in one statement.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MergeQL Query                                               │
│                                                              │
│  MERGE users_nyc, users_london, users_berlin                 │
│  ON id                                                       │
│  STRATEGY name='lww', salary='max', status='priority'        │
│  WHERE region != 'excluded'                                  │
│  LIMIT 10000                                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ parsed to MergeAST
                       ┌─────────────────────────────────────────────────────────────┐
│  MergeQL Engine                                              │
│                                                              │
│  1. Parse → MergeAST (sources, key, strategies, filters)     │
│  2. Plan  → MergePlan (estimated rows, steps, Arrow backend) │
│  3. Execute → apply MergeSchema over registered sources      │
│  4. Return → MergeQLResult (data, plan, conflicts, provenance│
└─────────────────────────────────────────────────────────────┘
```

The Layer 2 deterministic strategy function is invoked once over the full joined dataset, not pairwise — preserving CRDT correctness regardless of source count.

---

## Quick Start

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()

# Register named data sources
ql.register("users_nyc",    [
    {"id": "U1", "name": "Alice", "salary": 95000, "status": "active"},
    {"id": "U2", "name": "Bob",   "salary": 87000, "status": "inactive"},
])
ql.register("users_london", [
    {"id": "U1", "name": "Alice", "salary": 98000,  "status": "active"},   # salary conflict
    {"id": "U3", "name": "Carol", "salary": 102000, "status": "active"},
])

# Express the merge as a query
result = ql.execute("""
    MERGE users_nyc, users_london
    ON id
    STRATEGY salary='max', status='lww'
""")

print(f"Merged {len(result.data)} records in {result.merge_time_ms:.1f}ms")
print(f"Conflicts resolved: {result.conflicts}")

for row in result.data:
    print(f"  {row['id']}: {row['name']}, salary={row['salary']}, status={row['status']}")
# U1: Alice, salary=98000 (max wins), status=active
# U2: Bob, salary=87000, status=inactive
# U3: Carol, salary=102000, status=active
```

---

## Cookbook: All Strategy Types

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("source_a", [{"id": "1", "name": "Alice", "score": 80, "tags": ["admin"], "bio": "Short bio"}])
ql.register("source_b", [{"id": "1", "name": "Alice", "score": 95, "tags": ["user"],  "bio": "Longer bio here"}])

# LWW — last write wins (default for most fields)
r = ql.execute("MERGE source_a, source_b ON id STRATEGY name='lww'")

# MaxWins — higher value wins
r = ql.execute("MERGE source_a, source_b ON id STRATEGY score='max'")
assert r.data[0]["score"] == 95

# MinWins — lower value wins
r = ql.execute("MERGE source_a, source_b ON id STRATEGY score='min'")
assert r.data[0]["score"] == 80

# UnionSet — combine sets without duplicates
r = ql.execute("MERGE source_a, source_b ON id STRATEGY tags='union'")
# tags will contain both ["admin", "user"]

# Concat — append values
r = ql.execute("MERGE source_a, source_b ON id STRATEGY bio='concat'")

# LongestWins — keep the longer string
r = ql.execute("MERGE source_a, source_b ON id STRATEGY bio='longest'")
assert r.data[0]["bio"] == "Longer bio here"

# Multiple strategies in one query
r = ql.execute("""
    MERGE source_a, source_b
    ON id
    STRATEGY name='lww', score='max', tags='union', bio='longest'
""")
```

---

## Cookbook: Three or More Sources

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("shard_east",  [{"id": "1", "views": 1200, "likes": 450}])
ql.register("shard_west",  [{"id": "1", "views": 800,  "likes": 320}, {"id": "2", "views": 600, "likes": 180}])
ql.register("shard_eu",    [{"id": "1", "views": 950,  "likes": 410}, {"id": "3", "views": 300, "likes": 90}])

# CRDT-correct merge across all three shards — order doesn't matter
result = ql.execute("""
    MERGE shard_east, shard_west, shard_eu
    ON id
    STRATEGY views='max', likes='max'
""")

# ID "1" appears in all three — max values selected deterministically
r1 = next(r for r in result.data if r["id"] == "1")
assert r1["views"] == 1200   # max across shards
assert r1["likes"] == 450    # max across shards
print(f"Merged {len(result.data)} unique records from 3 shards")
```

---

## Cookbook: WHERE Filtering

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("events_all", [
    {"id": "E1", "type": "purchase", "amount": 150},
    {"id": "E2", "type": "refund",   "amount": -50},
    {"id": "E3", "type": "purchase", "amount": 300},
])
ql.register("events_mobile", [
    {"id": "E4", "type": "purchase", "amount": 75},
    {"id": "E2", "type": "refund",   "amount": -45},  # conflict on E2
])

# Filter before merge — only keep purchases
result = ql.execute("""
    MERGE events_all, events_mobile
    ON id
    STRATEGY amount='max'
    WHERE type='purchase'
""")

ids = {r["id"] for r in result.data}
assert "E2" not in ids   # refunds filtered out
print(f"Purchase events: {len(result.data)}")
```

---

## Cookbook: LIMIT and Column Mapping

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("products_v1", [
    {"product_id": "P1", "price": 29.99, "stock": 100},
    {"product_id": "P2", "price": 49.99, "stock": 50},
])
ql.register("products_v2", [
    {"id": "P1", "price": 31.99, "qty": 110},   # renamed columns
    {"id": "P3", "price": 19.99, "qty": 200},
])

# MAP renames columns before merge
result = ql.execute("""
    MERGE products_v1, products_v2
    ON product_id
    STRATEGY price='max', stock='max'
    MAP id -> product_id, qty -> stock
    LIMIT 10
""")

print(f"Products merged: {len(result.data)}")
```

---

## Cookbook: EXPLAIN — Inspect the Execution Plan

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("users_a", [{"id": f"{i}", "name": f"User{i}", "score": i} for i in range(1000)])
ql.register("users_b", [{"id": f"{i}", "name": f"User{i}", "score": i * 2} for i in range(500, 1500)])

# EXPLAIN shows the plan without executing
result = ql.execute("""
    EXPLAIN MERGE users_a, users_b
    ON id
    STRATEGY score='max'
""")

print(result.plan)
# MergePlan
#   Sources: users_a, users_b
#   Key: id
#   Strategies: {'score': 'max'}
#   Estimated rows: 1500
#   Schema evolution: False
#   Arrow backend: False
#   Steps:
#     1. Validate sources: users_a (1000 rows), users_b (1000 rows)
#     2. Align schema: no evolution needed
#     3. Merge on key='id' using strategies: score=MaxWins
#     4. Resolve conflicts (estimated 500 overlapping keys)
#     5. Return 1500 rows
```

---

## Cookbook: Custom Strategy Functions

```python
from crdt_merge.mergeql import MergeQL
from crdt_merge.strategies import Custom

ql = MergeQL()

# Register a custom resolver
def trust_verified_source(a, b):
    """Always prefer the value from a verified source."""
    if isinstance(a, dict) and a.get("verified"):
        return a["value"]
    if isinstance(b, dict) and b.get("verified"):
        return b["value"]
    return a if a is not None else b

ql.register_strategy("trusted", Custom(trust_verified_source))

ql.register("source_a", [{"id": "1", "rating": {"value": 4.2, "verified": True}}])
ql.register("source_b", [{"id": "1", "rating": {"value": 4.8, "verified": False}}])

result = ql.execute("""
    MERGE source_a, source_b
    ON id
    STRATEGY rating='custom:trusted'
""")
```

---

## Scenario: Multi-Region Database Synchronisation

A SaaS application runs databases in three regions: US-EAST, EU-WEST, APAC. Each region writes locally. Periodic sync needed — without losing any writes, without a coordinator.

```python
from crdt_merge.mergeql import MergeQL
from crdt_merge.gossip import GossipState

ql = MergeQL()

# Register each regional database snapshot
ql.register("db_us_east", us_east_records)
ql.register("db_eu_west", eu_west_records)
ql.register("db_apac",    apac_records)

# CRDT-correct sync in one statement
result = ql.execute("""
    MERGE db_us_east, db_eu_west, db_apac
    ON user_id
    STRATEGY
        email='lww',
        subscription_tier='max',
        last_login='max',
        feature_flags='union',
        display_name='lww'
""")

# Same query run on any region produces identical output
# No coordinator, no round-trip, no data loss
print(f"Synced {len(result.data)} users across 3 regions")
print(f"Conflicts resolved: {result.conflicts}")
print(f"Time: {result.merge_time_ms:.1f}ms")
```

---

## Scenario: Distributed Knowledge Graph Merge

Five research teams each maintain a knowledge graph (entities + facts). They want to merge their knowledge without sharing raw data pipelines.

```python
from crdt_merge.mergeql import MergeQL
from crdt_merge.agentic import AgentState, SharedKnowledge

ql = MergeQL()

# Each team registers their knowledge base
ql.register("team_genomics",    genomics_facts)    # [{"entity_id": ..., "fact_type": ..., "value": ..., "confidence": ...}]
ql.register("team_proteomics",  proteomics_facts)
ql.register("team_metabolomics",metabolomics_facts)
ql.register("team_clinical",    clinical_facts)
ql.register("team_imaging",     imaging_facts)

# Merge all knowledge, keeping highest-confidence facts for each entity
result = ql.execute("""
    MERGE team_genomics, team_proteomics, team_metabolomics, team_clinical, team_imaging
    ON entity_id
    STRATEGY
        value='lww',
        confidence='max',
        citations='union',
        last_updated='max'
    WHERE confidence > 0.5
""")

# 5-team knowledge graph merged and deduplicated
# No central coordinator — any team can run this query and get identical results
print(f"Knowledge graph: {len(result.data)} facts")
print(f"High-confidence facts: {sum(1 for r in result.data if r['confidence'] > 0.8)}")
```

---

## Scenario: IoT Sensor Data Reconciliation

1,000 IoT sensors report temperature readings. Sensors occasionally fail and report stale values. CRDT merge with max-timestamp strategy ensures only the latest valid reading wins.

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()

# Readings from primary and backup sensor networks
ql.register("primary_net",  primary_readings)   # [{"sensor_id": ..., "temp": ..., "timestamp": ..., "status": ...}]
ql.register("backup_net",   backup_readings)
ql.register("edge_cache",   cached_readings)

# Most recent valid reading wins; status union for diagnostics
result = ql.execute("""
    MERGE primary_net, backup_net, edge_cache
    ON sensor_id
    STRATEGY
        temp='lww',
        timestamp='max',
        status='union',
        battery_level='min'
    WHERE status != 'fault'
""")

# Latest valid reading for each sensor, stale readings discarded
print(f"Active sensors: {len(result.data)}")
faulty = sum(1 for r in result.data if "fault" in r.get("status", []))
print(f"Sensors with fault history: {faulty}")
```

---

## Scenario: dbt + MergeQL — Convergent Transformations

crdt-merge integrates with dbt for CRDT-correct transformations in your data pipeline:

```python
# In your dbt Python model:
from crdt_merge.mergeql import MergeQL

def model(dbt, session):
    ql = MergeQL()

    # Load source tables from dbt ref()
    ql.register("orders_us",  dbt.ref("stg_orders_us").to_records())
    ql.register("orders_eu",  dbt.ref("stg_orders_eu").to_records())
    ql.register("orders_apac",dbt.ref("stg_orders_apac").to_records())

    result = ql.execute("""
        MERGE orders_us, orders_eu, orders_apac
        ON order_id
        STRATEGY
            amount='max',
            status='lww',
            updated_at='max',
            tags='union'
    """)

    return session.createDataFrame(result.data)
```

---

## Accessing Provenance from MergeQL

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("source_a", [{"id": "1", "value": 100}, {"id": "2", "value": 200}])
ql.register("source_b", [{"id": "1", "value": 150}, {"id": "3", "value": 300}])

result = ql.execute("""
    MERGE source_a, source_b
    ON id
    STRATEGY value='max'
""")

# Full per-row provenance
if result.provenance:
    for prov in result.provenance:
        print(f"Row {prov['key']}: origin={prov['origin']}, conflicts={prov['conflict_count']}")
```

---

## MergeQL vs SQL: When to Use Each

| Situation | Use SQL | Use MergeQL |
|---|---|---|
| Single database, one source of truth | | — |
| Multi-source merge with known conflict resolution | — | |
| Convergence guarantees required | — | |
| Data from multiple organisations | — | |
| Need provenance per-row | — | |
| CRDT compliance required | — | |
| Complex joins (foreign keys, GROUP BY) | | — |
| Simple key-based reconciliation | — | |

MergeQL is not a general-purpose query language — it is specifically designed for **key-based record reconciliation across multiple sources** with CRDT correctness.

---

## Full MergeQL Syntax Reference

```
MERGE source1, source2 [, source3 ...]
ON key_column
[STRATEGY field1='strategy1' [, field2='strategy2' ...]]
[WHERE field='value']
[MAP old_column -> new_column [, ...]]
[LIMIT n]

Prefix with EXPLAIN to get plan without execution.

Strategies:
  lww           Last-Write-Wins (default)
  max / maxwins Higher value wins
  min / minwins Lower value wins
  union         Set union (for lists/sets)
  concat        Append values
  longest       Longer string wins
  priority      Priority-based (requires custom resolver)
  custom:<name> Custom registered strategy
```

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [Guide — Privacy-Preserving Merge](./privacy-preserving-merge.md)
- [API Reference — MergeQL](../api-reference/layer2-analytics/mergeql.md)
- [Performance Tuning Guide](../guides/performance-tuning.md)
