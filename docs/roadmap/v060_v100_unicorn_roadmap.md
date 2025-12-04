# crdt-merge: The Unicorn Roadmap
## v0.6.0 → v1.0.0 — From Library to Platform

**Author:** Optitransfer AG Strategy  
**Date:** 2026-03-28  
**Classification:** Strategic Product Architecture  
**Constraint:** ALL changes ADDITIVE ONLY — zero breaking changes to existing API

---

## 1. Competitive Intelligence (March 2026)

### The Landscape We're NOT Competing With

| Library | Focus | Languages | Size | What They Do |
|---------|-------|-----------|------|-------------|
| **Loro 1.0** | Real-time collaborative editing | Rust, JS/WASM, Swift | 23 MB | Rich text, movable tree, version control DAG, Eg-walker. 30x import speed. Git-like branching for docs. |
| **Automerge** | JSON document collaboration | Rust core + JS/Python bindings | Heavy (MB) | JSON data model, automerge-repo networking, operation history |
| **Yjs** | Text editing (YATA algorithm) | JS/TS | Medium | Modular framework, shared types, network-agnostic. Powers Velt. |
| **Diamond Types** | Extremely fast list CRDTs | Rust, JS | Small | Eg-walker reference implementation, benchmarks 5000x over Automerge |
| **DSON (Helsing)** | Delta-state JSON, defense-grade | Rust | Small | Military-grade, delta CRDTs for JSON documents |
| **Velt** | Commercial collaboration platform | JS/TS (React) | SaaS | Uses Yjs internally, sells UI components + infrastructure |
| **Liveblocks** | Managed collaboration SaaS | JS/TS | SaaS | SOC2/HIPAA compliant, presence, cursors, managed backend |
| **MS Fluid** | Enterprise collaboration | JS/TS | Heavy | Server-side OT, Azure integration, Microsoft ecosystem |
| **RxDB** | Offline-first database | JS/TS | Medium | MongoDB-style CRDT operators, static JSON resolution |

### The Category We OWN

**Batch Dataset Reconciliation — Merge Algebra for Tabular Data**

| Library | Focus | Languages | Size |
|---------|-------|-----------|------|
| **crdt-merge** | Dataset merging, per-field strategy DSL, streaming, provenance, verification | **Python, TS, Rust, Java** | **21 KB** |
| *(empty)* | | | |

**We have ZERO competitors in our actual category.**

Every library above solves **real-time collaborative editing** — Google Docs, Figma, multiplayer apps. crdt-merge solves **batch dataset reconciliation** — distributed systems collected data independently, they need to merge their datasets with deterministic, auditable, composable conflict resolution.

### What Loro 1.0 Does That We Should Study (Not Copy)

Loro's 1.0 release (Sep 2025) introduced:
1. **Lazy loading with block-level storage** — imports 10-100x faster by not parsing unused history
2. **Shallow snapshots** — like Git shallow clone, strips old history for faster sync
3. **Version control DAG** — Git-like branching, checkout, fork, merge for documents
4. **LSM-inspired internal storage** — 4KB blocks, compressed, loaded on demand

**What this means for us:** These are document-editing optimizations. Our path is different — we need to optimize for **tabular data at scale**, **cross-language wire interop**, and **integration with the data engineering stack**. But the lazy loading and block-level storage concepts could inspire our streaming pipeline evolution.

### The Gap Nobody Fills

**Nobody connects CRDTs to the data engineering stack.** There is no:
- CRDT merge operator for Kafka/Flink streams
- CRDT materialization for dbt
- CRDT task for Airflow/Dagster pipelines
- CRDT tool for LangChain/LlamaIndex AI agents
- CRDT microservice for HTTP/gRPC sync
- CRDT gossip protocol for multi-node dataset sync
- CRDT library with runtime formal verification

**This is our moat. This is the unicorn path.**

---

## 2. The Gold Standard: What Makes Us Unbeatable

### 10 Differentiators Nobody Can Match Together

| # | Differentiator | Competition | crdt-merge v1.0 |
|---|----------------|-------------|-----------------|
| 1 | **Composable per-field strategy DSL** | RxDB has rigid JSON operators | ✅ MergeSchema with 8+ strategies across 6+ languages |
| 2 | **Runtime CRDT verification** | Propel (ETH) does compile-time only | ✅ `verify_crdt()` proves any custom merge is valid at runtime |
| 3 | **Per-field merge provenance** | Automerge tracks ops, not decisions | ✅ Human-readable audit trail: who, what, why, which strategy |
| 4 | **Cross-language wire format** | Automerge: 1 Rust core + bindings | ✅ 6+ independent implementations, certified roundtrip |
| 5 | **Zero dependencies** | Loro: 23 MB. Automerge: MB. | ✅ 21 KB wheel. Embeds anywhere. |
| 6 | **Probabilistic CRDTs** | Nobody packages HLL/Bloom/CMS as CRDTs | ✅ Mergeable distributed analytics at edge |
| 7 | **Gossip-based multi-node sync** | All competitors are single-node | ✅ Built-in gossip + anti-entropy for horizontal scaling |
| 8 | **Data engineering integrations** | Nobody connects CRDTs to Kafka/dbt/Airflow | ✅ First-class connectors for the modern data stack |
| 9 | **AI agent CRDT tools** | Nobody | ✅ LangChain/LlamaIndex tools for multi-agent state merge |
| 10 | **WASM universal runtime** | Loro/Automerge have WASM but for editing | ✅ One Rust core for dataset merging everywhere |

---

## 3. The Five Releases: v0.6.0 → v1.0.0

### v0.6.0 — "The Distributed Release" 🌐

**Codename:** Network  
**Theme:** Take crdt-merge from single-node library to distributed system component  
**Zero breaking changes:** All new modules, existing API untouched

#### New Module: `crdt_merge.gossip`

```python
from crdt_merge.gossip import MergeNode, GossipConfig

# Create a merge node that syncs with peers
node = MergeNode(
    node_id="warehouse-eu",
    config=GossipConfig(
        bind_addr="0.0.0.0:7946",
        seed_peers=["warehouse-us:7946", "warehouse-asia:7946"],
        sync_interval_ms=5000,      # Gossip every 5s
        anti_entropy_interval_ms=30000,  # Full Merkle check every 30s
    )
)

# Local mutations — automatically gossiped to peers
node.apply({"user_123": {"name": "Alice", "score": 100}})

# Receive callback when remote data arrives
@node.on_sync
def handle_sync(delta, source_node):
    print(f"Got {len(delta)} changes from {source_node}")

# Query current merged state
state = node.get_state()  # Converged across all nodes
```

#### New Module: `crdt_merge.vector_clock`

```python
from crdt_merge.vector_clock import VectorClock, VersionVector

# Causal ordering for multi-node events
vc = VectorClock()
vc.increment("node_a")      # {node_a: 1}
vc.increment("node_a")      # {node_a: 2}
vc.increment("node_b")      # {node_a: 2, node_b: 1}

# Compare causality
vc_a = VectorClock({"node_a": 3, "node_b": 1})
vc_b = VectorClock({"node_a": 2, "node_b": 2})
vc_a.compare(vc_b)  # "concurrent" — neither happened before the other

# Merge vector clocks (element-wise max — a CRDT itself!)
merged = vc_a.merge(vc_b)  # {node_a: 3, node_b: 2}
```

#### New Module: `crdt_merge.antientropy`

```python
from crdt_merge.antientropy import MerkleTree, SyncProtocol

# Efficient diff detection via Merkle trees
tree_a = MerkleTree.from_state(state_a, key="id")
tree_b = MerkleTree.from_state(state_b, key="id")

# Compare roots — if equal, states are identical (O(1))
if tree_a.root_hash != tree_b.root_hash:
    # Find exactly which keys differ (O(log n) comparisons)
    diff_keys = SyncProtocol.find_diff(tree_a, tree_b)
    # Exchange only the differing records
    delta = SyncProtocol.create_delta(state_a, diff_keys)
```

#### Feature Summary

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| **Gossip protocol** | Automatic peer-to-peer dataset sync | Multi-node without central coordinator |
| **Vector clocks** | Causal ordering of distributed events | Know what happened-before what |
| **Merkle anti-entropy** | O(log n) diff detection between nodes | Only transfer what's different |
| **Peer discovery** | Seed-based mesh topology | Nodes find each other automatically |
| **Conflict-free by design** | Uses existing merge strategies | All CRDT properties preserved at network level |

#### What This Enables
- **MembraneDB**: Multi-region deployment — EU, US, Asia warehouses sync automatically
- **HiveGuard**: Threat intel gossip — IOCs propagate across all security nodes
- **Edge computing**: Laptop/phone collects data offline → syncs to cloud via gossip

#### Test Targets
- Multi-node convergence: 10 nodes, 100K records, all orderings converge
- Partition tolerance: network split → heal → convergence within 3 sync rounds
- Anti-entropy: 1M records, find 100 diffs in < 50ms
- **~200 new tests, total ~620**

#### Lines Estimate: ~4,800 total (up from 3,790)

---

### v0.7.0 — "The Integration Release" 🔌

**Codename:** Ecosystem  
**Theme:** Connect crdt-merge to every tool in the modern data stack  
**Zero breaking changes:** All new modules/packages, existing API untouched

#### New Package: `crdt-merge-server`

A standalone microservice for HTTP/gRPC CRDT sync:

```bash
pip install crdt-merge-server
crdt-merge-server --port 8080 --schema schema.yaml
```

```yaml
# schema.yaml
collections:
  users:
    key: id
    strategy:
      name: lww
      score: max_wins
      tags: union_set
    sync:
      gossip: true
      peers: ["node-b:8080", "node-c:8080"]
```

```python
# Any language can sync via HTTP
import requests

# Push local state
requests.post("http://localhost:8080/api/v1/merge", json={
    "collection": "users",
    "records": [{"id": "u1", "name": "Alice", "score": 100}]
})

# Pull merged state
response = requests.get("http://localhost:8080/api/v1/state/users")
merged_records = response.json()["records"]
```

#### New Package: `crdt-merge-kafka`

Kafka Streams CRDT merge operator:

```python
from crdt_merge.kafka import CRDTMergeProcessor

processor = CRDTMergeProcessor(
    input_topic="raw-events",
    output_topic="merged-state",
    key_field="id",
    schema=my_schema,
    bootstrap_servers="kafka:9092"
)
processor.run()  # Continuous CRDT merge on Kafka stream
```

#### New Package: `crdt-merge-flink`

Apache Flink CRDT merge operator:

```python
from crdt_merge.flink import CRDTMergeFunction

# Use as a Flink ProcessFunction
env.add_source(kafka_source) \
   .key_by(lambda r: r["id"]) \
   .process(CRDTMergeFunction(schema=my_schema)) \
   .add_sink(kafka_sink)
```

#### New Package: `crdt-merge-dbt`

dbt custom materialization:

```sql
-- models/merged_users.sql
{{ config(materialized='crdt_merge', key='id', strategy='schema.yaml') }}

SELECT * FROM {{ source('raw', 'users_source_a') }}
UNION ALL
SELECT * FROM {{ source('raw', 'users_source_b') }}
```

#### New Package: `crdt-merge-airflow`

Airflow / Dagster task operator:

```python
from crdt_merge.airflow import CRDTMergeOperator

merge_task = CRDTMergeOperator(
    task_id="merge_daily_data",
    source_a="s3://bucket/source_a/",
    source_b="s3://bucket/source_b/",
    output="s3://bucket/merged/",
    key="id",
    schema="schema.yaml",
)
```

#### New Package: `crdt-merge-langchain`

LangChain / LlamaIndex tool for AI agents:

```python
from crdt_merge.langchain import CRDTMergeTool

# Give AI agents the ability to merge distributed state
tool = CRDTMergeTool(
    name="merge_agent_state",
    description="Merge state from multiple agents using CRDT strategies",
    schema=my_schema,
)

# Agent can now merge observations from multiple sub-agents
agent = initialize_agent(tools=[tool, ...], llm=llm)
agent.run("Merge the customer data from all regional agents")
```

#### Feature Summary

| Package | What It Does | Ecosystem |
|---------|-------------|-----------|
| `crdt-merge-server` | HTTP/gRPC CRDT sync microservice | Any language via REST |
| `crdt-merge-kafka` | Kafka Streams merge operator | Event streaming |
| `crdt-merge-flink` | Flink ProcessFunction | Stream processing |
| `crdt-merge-dbt` | Custom CRDT materialization | Analytics engineering |
| `crdt-merge-airflow` | Airflow/Dagster operator | Orchestration |
| `crdt-merge-langchain` | LangChain/LlamaIndex tool | AI agents |

#### What This Enables
- **Data teams**: CRDT merge as a first-class dbt materialization — no custom code
- **Platform teams**: CRDT merge in Kafka/Flink pipelines — real-time conflict resolution
- **AI teams**: Multi-agent state merging — agents collect data independently, merge via CRDT
- **Any team**: HTTP API for language-agnostic CRDT sync

#### Test Targets
- Integration tests for each connector against real services
- End-to-end: Kafka producer → CRDT merge → Kafka consumer roundtrip
- dbt: run + test against DuckDB/PostgreSQL
- **~300 new tests, total ~920**

#### Lines Estimate: ~6,500 total (core) + ~3,000 (connectors)

---

### v0.8.0 — "The Polyglot Release" 🌍

**Codename:** Universal  
**Theme:** One wire format, every language, certified interop  
**Zero breaking changes:** New implementations, existing Python API untouched

#### Rust Core → WASM Universal Runtime

```rust
// crdt-merge-rs v0.8.0 — the reference implementation
use crdt_merge::{MergeSchema, Strategy, merge, serialize, deserialize};

let schema = MergeSchema::new()
    .field("name", Strategy::LWW)
    .field("score", Strategy::MaxWins)
    .field("tags", Strategy::UnionSet);

let merged = merge(&record_a, &record_b, &schema);
let wire_bytes = serialize(&merged);  // Canonical binary format
```

```bash
# Compile to WASM — runs in browser, Node, Deno, Cloudflare Workers
wasm-pack build --target web
```

#### Cross-Language Port Matrix

| Language | Package | Registry | Wire Format | Schema DSL | Streaming | Gossip | Status |
|----------|---------|----------|:-----------:|:----------:|:---------:|:------:|--------|
| **Python** | `crdt-merge` | PyPI | ✅ | ✅ | ✅ | ✅ | Reference (v0.8.0) |
| **Rust** | `crdt-merge` | crates.io | ✅ | ✅ | ✅ | ✅ | Full parity |
| **TypeScript** | `crdt-merge` | npm | ✅ | ✅ | ✅ | ✅ | Full parity |
| **Java** | `crdt-merge` | Maven Central | ✅ | ✅ | ✅ | ✅ | Full parity |
| **Go** | `crdt-merge` | Go modules | ✅ | ✅ | ✅ | — | Core parity |
| **C#/.NET** | `CrdtMerge` | NuGet | ✅ | ✅ | ✅ | — | Core parity |
| **Swift** | `CRDTMerge` | Swift Package Manager | ✅ | ✅ | — | — | Wire + schema |
| **WASM** | `crdt-merge-wasm` | npm | ✅ | ✅ | ✅ | ✅ | Universal runtime |

#### Cross-Language Certification Test Suite

The gold standard: **any two implementations can exchange data perfectly**.

```
Test: Python serialize → Rust deserialize → merge → serialize → TypeScript deserialize
Test: Java serialize → Go deserialize → merge → serialize → Python deserialize
Test: WASM serialize → Swift deserialize → merge → serialize → C# deserialize

For each combination:
  ✅ GCounter roundtrip
  ✅ PNCounter roundtrip
  ✅ LWWMap roundtrip
  ✅ ORSet roundtrip
  ✅ MergeSchema roundtrip
  ✅ Delta roundtrip
  ✅ Provenance roundtrip
  ✅ HLL/Bloom/CMS roundtrip
  ✅ Compressed wire format roundtrip
  ✅ Merge produces identical result regardless of which language runs it
```

#### Wire Format Specification v1.0

Published as a formal specification (RFC-style):

```
CRDT-MERGE Wire Format v1.0
============================

Header (12 bytes):
  [0-3]  Magic: 0x43524454 ("CRDT")
  [4]    Format version: 0x01
  [5]    Type tag:
         0x01 = GCounter
         0x02 = PNCounter
         0x03 = LWWRegister
         0x04 = LWWMap
         0x05 = ORSet
         0x06 = MergeableHLL
         0x07 = MergeableBloom
         0x08 = MergeableCMS
         0x09 = Delta
         0x0A = MergeSchema
  [6]    Compression: 0x00=none, 0x01=zlib, 0x02=zstd
  [7-11] Payload length (uint40, big-endian)

Payload (variable):
  MessagePack-encoded state according to type-specific schema
  (see Type Specifications below)

All implementations MUST produce byte-identical output for the same logical state.
Deterministic serialization: keys sorted lexicographically, IEEE 754 doubles.
```

#### What This Enables
- **Polyglot microservices**: Python data pipeline → Rust edge node → Go API server — all speak the same wire format
- **Browser-native**: WASM build runs CRDT merge in the browser with near-native speed
- **Mobile**: Swift package for iOS, Kotlin/Java for Android
- **Edge**: Cloudflare Workers, Deno Deploy, Fly.io — WASM runs everywhere

#### Test Targets
- Cross-language roundtrip: every pair of implementations
- Performance parity: within 2x of Rust baseline for all languages
- WASM: browser + Node + Deno certification
- **~500 new tests (across all languages), total ~1,400**

---

### v0.9.0 — "The Enterprise Release" 🏢

**Codename:** Trust  
**Theme:** Security, compliance, observability — everything enterprises need  
**Zero breaking changes:** All new modules, existing API untouched

#### New Module: `crdt_merge.encryption`

End-to-end encryption for wire format:

```python
from crdt_merge.encryption import EncryptedWire, KeyPair

# Generate node keypair
keys = KeyPair.generate()

# Encrypt before sending over network
encrypted = EncryptedWire.encrypt(
    wire_bytes,
    recipient_public_key=peer_public_key,
    sender_private_key=keys.private_key
)

# Decrypt on receiving end
decrypted = EncryptedWire.decrypt(
    encrypted,
    sender_public_key=peer_public_key,
    recipient_private_key=my_private_key
)

# CRDT properties preserved — decrypt → deserialize → merge still works
```

#### New Module: `crdt_merge.rbac`

Role-based merge permissions:

```python
from crdt_merge.rbac import MergePolicy, Role

policy = MergePolicy({
    "patient_name":    Role.ADMIN_ONLY,        # Only admin nodes can modify
    "appointment":     Role.ANY,                # Any node can modify
    "diagnosis":       Role.roles(["doctor"]),  # Only doctor-role nodes
    "billing":         Role.roles(["billing", "admin"]),
})

# Merge respects permissions — unauthorized field changes are rejected
result = merge(record_a, record_b, schema=my_schema, policy=policy, 
               node_role="nurse")
# nurse can modify appointment but not patient_name or diagnosis
```

#### New Module: `crdt_merge.observability`

OpenTelemetry instrumentation:

```python
from crdt_merge.observability import instrument, MergeDashboard

# Auto-instrument all merge operations
instrument(
    otlp_endpoint="http://otel-collector:4317",
    service_name="crdt-merge-warehouse",
    metrics=True,    # merge latency, throughput, conflict rate
    traces=True,     # per-operation trace spans
    logs=True,       # merge decision audit log
)

# Prometheus metrics exposed automatically:
# crdt_merge_operations_total{strategy="max_wins", result="b_wins"}
# crdt_merge_latency_seconds{operation="merge", size="10000"}
# crdt_merge_conflicts_total{field="score", strategy="max_wins"}
# crdt_merge_gossip_sync_duration_seconds{peer="node-b"}
# crdt_merge_wire_bytes_total{direction="sent", compressed="true"}
```

#### New Module: `crdt_merge.compliance`

GDPR/SOX/HIPAA compliance toolkit:

```python
from crdt_merge.compliance import ComplianceAuditor, GDPRExporter

auditor = ComplianceAuditor(
    storage="postgresql://localhost/audit",
    retention_days=2555,  # 7 years for SOX
)

# Every merge operation is audit-logged
result = merge(record_a, record_b, schema=my_schema, auditor=auditor)

# GDPR Article 15 — Right of Access
exporter = GDPRExporter(auditor)
user_data = exporter.export_user_data(user_id="user_123")
# Returns: every merge decision that affected this user's data,
# with timestamps, source nodes, strategies applied, original values

# GDPR Article 17 — Right to Erasure
exporter.erase_user_data(user_id="user_123")
# Cryptographic erasure — user's data in all CRDT states replaced with tombstones
```

#### Formal Specification v1.0

Published as a standalone document:

```
The crdt-merge Formal Specification v1.0
========================================

1. Definitions
   1.1 Merge Algebra — the mathematical framework
   1.2 CRDT Properties — commutativity, associativity, idempotency
   1.3 Wire Format — canonical binary representation

2. Data Types
   2.1 Primitive CRDTs (GCounter, PNCounter, LWWRegister, LWWMap, ORSet)
   2.2 Probabilistic CRDTs (MergeableHLL, MergeableBloom, MergeableCMS)
   2.3 Composite Types (MergeSchema, Delta, Provenance)

3. Merge Strategies
   3.1 Built-in strategies (LWW, MaxWins, MinWins, UnionSet, etc.)
   3.2 Custom strategy requirements
   3.3 Verification criteria

4. Wire Format Specification
   4.1 Header format
   4.2 Payload encoding (MessagePack)
   4.3 Compression
   4.4 Deterministic serialization rules

5. Gossip Protocol
   5.1 Peer discovery
   5.2 Anti-entropy via Merkle trees
   5.3 Partition tolerance guarantees

6. Security
   6.1 Wire encryption
   6.2 Role-based merge permissions
   6.3 Compliance guarantees

7. Conformance Tests
   7.1 Required test suite for certification
   7.2 Cross-language roundtrip requirements
   7.3 Performance baselines
```

#### What This Enables
- **Healthcare**: HIPAA-compliant patient data merge across hospital systems
- **Finance**: SOX audit trail for every data merge in trading systems
- **Government**: Defense-grade encrypted CRDT sync between classified nodes
- **Any enterprise**: "Show me every merge decision that affected this record"

#### Test Targets
- Encryption: roundtrip with all CRDT types, key rotation, forward secrecy
- RBAC: permission enforcement across all merge functions
- Observability: metrics accuracy, trace completeness
- Compliance: audit log integrity, GDPR erasure verification
- **~300 new tests, total ~1,700**

---

### v1.0.0 — "The Platform Release" 🚀

**Codename:** Platform  
**Theme:** Everything stable, certified, documented — the definitive release  
**Zero breaking changes:** API freeze, stability guarantee

#### What v1.0.0 Means

1. **API Freeze** — All public APIs frozen. Semantic versioning from here.
2. **Cross-Language Certification** — Every language implementation passes the same 500+ test suite
3. **Performance Certification** — Published benchmarks for all languages on standard hardware
4. **Security Audit** — Independent third-party security audit of core + wire format + encryption
5. **Formal Spec Published** — The crdt-merge specification v1.0 is a standalone document
6. **Full Documentation** — User guide, API reference, tutorials, architecture docs

#### The v1.0.0 Certification Matrix

| Requirement | Python | Rust | TS | Java | Go | C# | Swift | WASM |
|-------------|:------:|:----:|:--:|:----:|:--:|:--:|:-----:|:----:|
| Core merge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Schema DSL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wire format | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Delta sync | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Provenance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Verification | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Probabilistic | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gossip | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Encryption | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Compliance | ✅ | ✅ | — | ✅ | — | — | — | — |
| **Wire roundtrip** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

#### Documentation Deliverables

| Document | Pages | Audience |
|----------|-------|----------|
| **User Guide** | ~80 | Developers: quick start → advanced usage |
| **API Reference** | ~120 | All public functions, all languages |
| **Architecture Guide** | ~40 | Contributors: internals, design decisions |
| **Wire Format Spec** | ~30 | Implementors: build your own implementation |
| **Integration Guides** | ~60 | Per-connector: Kafka, Flink, dbt, Airflow, LangChain |
| **Security Guide** | ~20 | Enterprise: encryption, RBAC, compliance |
| **Migration Guide** | ~10 | Upgrading from v0.x |

#### The Numbers at v1.0.0

| Metric | v0.2.0 | v0.5.0 (current) | v1.0.0 (target) |
|--------|--------|-------------------|-----------------|
| **Python lines** | 791 | 3,790 | ~8,000 |
| **Total lines (all languages)** | ~5,000 | ~10,000 | ~50,000 |
| **Languages** | 4 | 4 | 8 |
| **Tests (Python)** | 133 | 423 | ~2,000 |
| **Tests (all languages)** | 1,347 | ~1,800 | ~10,000 |
| **Modules (Python)** | 5 | 13 | ~22 |
| **Strategies** | 1 (LWW) | 8 | 8+ (stable) |
| **Wire format types** | 0 | 5 | 12+ |
| **Integrations** | 0 | 0 | 6 (Kafka, Flink, dbt, Airflow, LangChain, HTTP server) |
| **Package registries** | 3 | 3 | 8 (PyPI, npm, crates.io, Maven, Go, NuGet, SPM, npm/wasm) |

---

## 4. Evolution Summary

| Version | Codename | Theme | Key Features | Lines | Tests |
|---------|----------|-------|-------------|-------|-------|
| v0.1.0 | Launch | Origin | Core merge | — | — |
| v0.2.0 | IP Protection | Foundation | 4 languages, basic CRDTs | 1,578 | 133 |
| v0.3.0 | The Schema Release | Composability | Schema DSL, delta sync, streaming | 2,820 | 175 |
| v0.4.0 | The Trust Release | Auditability | Provenance, verification | 2,820 | 175 |
| v0.5.0 | The Protocol Release | Interop | Wire format, compression, probabilistic | 3,790 | 423 |
| **v0.6.0** | **The Distributed Release** | **Scaling** | **Gossip, vector clocks, anti-entropy** | **~4,800** | **~620** |
| **v0.7.0** | **The Integration Release** | **Ecosystem** | **Kafka, Flink, dbt, Airflow, LangChain, HTTP server** | **~6,500** | **~920** |
| **v0.8.0** | **The Polyglot Release** | **Universal** | **WASM, 8 languages, certified roundtrip** | **~8,000** | **~1,400** |
| **v0.9.0** | **The Enterprise Release** | **Trust** | **Encryption, RBAC, compliance, observability** | **~9,000** | **~1,700** |
| **v1.0.0** | **The Platform Release** | **Definitive** | **API freeze, formal spec, security audit, full docs** | **~10,000** | **~2,000** |

---

## 5. The Narrative Arc

### v0.2.0 → v0.5.0: "We Built the Core"
> A 21 KB library with composable merge strategies, provenance, verification, and a cross-language wire format. Zero dependencies. 423 tests. The only library for batch dataset reconciliation.

### v0.6.0 → v0.7.0: "We Made It Distributed"
> Multi-node gossip sync, anti-entropy, and connectors for every major data tool. The merge algebra that works at the edge, in the cloud, and in your Kafka pipeline.

### v0.8.0: "We Made It Universal"
> One wire format, 8 languages, WASM runtime. Python serialize → Rust merge → TypeScript consume. Certified cross-language interop.

### v0.9.0 → v1.0.0: "We Made It Enterprise"
> Encryption, RBAC, compliance, observability. HIPAA/SOX/GDPR ready. Formal specification. Security-audited. The platform.

### The One-Liner (Updated)
**"The SQLAlchemy of distributed data merging — composable, verifiable, auditable, and it speaks 8 languages."**

---

## 6. The Unicorn Checklist

What makes this a unicorn — features nobody else has, all in one library:

- [ ] **Only library for batch dataset reconciliation** (category of one)
- [ ] **Composable per-field merge strategy DSL** (not rigid operators)
- [ ] **Runtime CRDT formal verification** (not just compile-time)
- [ ] **Per-field merge provenance with compliance-ready audit** (human-readable why)
- [ ] **Cross-language wire format with certified roundtrip** (8 languages, one spec)
- [ ] **Zero dependencies** (21 KB — embeds anywhere)
- [ ] **Built-in gossip protocol for horizontal scaling** (not just single-node)
- [ ] **Kafka/Flink/dbt/Airflow/LangChain integrations** (connected to the stack)
- [ ] **WASM universal runtime** (browser, edge, serverless)
- [ ] **End-to-end encryption + RBAC** (defense-grade sync)
- [ ] **Probabilistic CRDTs** (HLL, Bloom, CMS with merge semantics)
- [ ] **Formal published specification** (anyone can build a conformant implementation)
- [ ] **10,000+ tests across 8 languages** (battle-tested)
- [ ] **Apache-2.0 open core** (maximum adoption, CLA for future flexibility)

**When all boxes are checked: that's the platform. That's the moat. That's the unicorn.**

---

## 7. What This Means for the Product Stack

```
crdt-merge v1.0.0 (Apache-2.0, open, moated, 8 languages)
    ├── crdt-merge-server (HTTP/gRPC microservice)
    ├── crdt-merge-kafka (stream processing)
    ├── crdt-merge-flink (stream analytics)
    ├── crdt-merge-dbt (analytics engineering)
    ├── crdt-merge-airflow (orchestration)
    └── crdt-merge-langchain (AI agents)
        ↓ all used by
    MembraneDB (BSL/proprietary, $9-$999/mo)
        ↓ used by
    Enterprise clients (healthcare, finance, logistics, defense, AI)
```

The free core (crdt-merge) builds the ecosystem.
The integrations make it sticky.
The wire format creates network effects.
The products (MembraneDB) monetize it.

---

*Copyright 2026 Ryan Gillespie — Optitransfer AG*  
*Contact: rgillespie83@icloud.com, data@optitransfer.ch*
