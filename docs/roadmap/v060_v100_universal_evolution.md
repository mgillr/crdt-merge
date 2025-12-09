# crdt-merge: The Universal Evolution
## v0.6.0 → v1.0.0 — From Library to Platform

**Author:** Optitransfer AG Strategy  
**Date:** 2026-03-28  
**Classification:** Strategic Product Architecture  
**Constraint:** ALL changes ADDITIVE ONLY — zero breaking changes to existing API  
**Principle:** Python is the reference implementation. Everything else speaks its protocol.

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

**This is our moat. This is the universal evolution.**

---

## 2. The Gold Standard: What Makes Us Unbeatable

### 14 Differentiators Nobody Can Match Together

| # | Differentiator | Competition | crdt-merge v1.0 |
|---|----------------|-------------|-----------------|
| 1 | **Composable per-field strategy DSL** | RxDB has rigid JSON operators | ✅ MergeSchema with 8+ strategies across 20+ languages |
| 2 | **Runtime CRDT verification** | Propel (ETH) does compile-time only | ✅ `verify_crdt()` proves any custom merge is valid at runtime |
| 3 | **Per-field merge provenance** | Automerge tracks ops, not decisions | ✅ Human-readable audit trail: who, what, why, which strategy |
| 4 | **Python-first, universally portable** | Automerge: 1 Rust core + bindings | ✅ Python reference → Rust protocol engine → 20+ languages via FFI/WASM |
| 5 | **Zero dependencies** | Loro: 23 MB. Automerge: MB. | ✅ 21 KB wheel. Embeds anywhere. |
| 6 | **Probabilistic CRDTs** | Nobody packages HLL/Bloom/CMS as CRDTs | ✅ Mergeable distributed analytics at edge |
| 7 | **Gossip-based multi-node sync** | All competitors are single-node | ✅ Built-in gossip + anti-entropy for horizontal scaling |
| 8 | **Data engineering integrations** | Nobody connects CRDTs to Kafka/dbt/Airflow | ✅ First-class connectors for the modern data stack |
| 9 | **AI agent CRDT tools** | Nobody | ✅ LangChain/LlamaIndex tools for multi-agent state merge |
| 10 | **WASM universal runtime** | Loro/Automerge have WASM but for editing | ✅ Protocol engine → WASM for dataset merging in browsers, edge, serverless |
| 11 | **End-to-end encryption + RBAC** | Nobody at the merge layer | ✅ Defense-grade encrypted sync with per-field role permissions |
| 12 | **Compliance toolkit** | Nobody | ✅ GDPR/SOX/HIPAA audit trail + right-to-erasure built in |
| 13 | **Formal published specification** | None have one | ✅ RFC-style wire format + merge semantics spec — anyone can build conformant implementations |
| 14 | **2,000+ tests, 278 A100 measurements** | Unmatched | ✅ Battle-tested on GPU hardware at 100M-row scale |

---

## 3. The Architecture: Python-First, Universally Portable

### The Key Insight

We do NOT rewrite the Python codebase. We do NOT replace it with Rust. Instead:

1. **Python is the reference implementation** — all innovation happens here first
2. **The v0.5.0 wire format IS the universal protocol** — it's language-agnostic bytes
3. **A thin Rust "protocol engine"** (`libcrdt_merge`, ~1,000 lines) implements ONLY the wire format parsing + CRDT merge semantics + serialization
4. **FFI wrappers** around that Rust engine give every language the ability to serialize, deserialize, and merge CRDTs
5. **Language-specific SDKs** add ergonomic APIs on top (DataFrame integration for Python, Stream API for Java, etc.)

```
Python (full-featured reference, ~10K lines)
    │
    │  defines the protocol spec
    │  (wire format, merge semantics, strategies)
    ▼
Rust Protocol Engine (~1,000 lines)
    │
    │  implements ONLY:
    │  - wire format parse/emit
    │  - CRDT merge operations
    │  - schema evaluation
    │  - deterministic serialization
    ▼
┌───────────────────────────────────┐
│        libcrdt_merge C ABI        │
│   (cbindgen → .so / .dylib / .dll)│
└──────────┬──────────┬─────────────┘
           │          │
     FFI wrappers     WASM build
     (20+ langs)      (wasm-pack)
```

### Why This Model Wins

| Concern | "Rewrite in Rust" | Our Model: "Protocol Engine" |
|---------|-------------------|-------------------------------|
| **Python stays primary?** | ❌ Gets sidelined | ✅ Stays the reference forever |
| **Effort** | Rewrite 3,790+ lines | ~1,000 lines (protocol only) |
| **Bug risk** | Two competing codebases | One spec, one engine, thin wrappers |
| **Innovation speed** | Gate new features on Rust port | Ship in Python first, engine catches up |
| **Who uses what** | Developers confused about "which one" | Python users: use Python. Everyone else: FFI. Clear. |
| **Wire compatibility** | Must stay in sync | Guaranteed — engine speaks Python's exact bytes |

### The Interop Test (The Gold Standard)

```
Python serialize → Rust engine deserialize → merge → serialize → Python deserialize
```

If this roundtrip passes for every CRDT type, the protocol engine is correct. Period.

---

## 4. The Complete Evolution: v0.1.0 → v1.0.0

### v0.1.0 — "The Launch Release" 🌱

**Codename:** Origin
**Theme:** Core merge algebra — prove the concept
**Zero breaking changes:** N/A — first release

The beginning. A single module with a single function: `merge()`. Last-Writer-Wins conflict resolution for tabular data. The question answered: *can CRDT semantics work for batch dataset reconciliation?* Yes.

---

### v0.2.0 — "The IP Protection Release" 🛡️

**Codename:** Foundation
**Theme:** Establish cross-language presence, protect the intellectual property
**Zero breaking changes:** All additive

Published to 4 package registries simultaneously (PyPI, npm, crates.io, Maven Central). Basic CRDTs: GCounter, PNCounter, LWWRegister, LWWMap, ORSet. The "plant the flag" release — establish prior art across every major ecosystem.

| Metric | Value |
|--------|-------|
| **Languages** | Python, TypeScript, Rust, Java |
| **Lines** | 1,578 |
| **Tests** | 133 |

---

### v0.3.0 — "The Schema Release" 📐

**Codename:** Composability
**Theme:** Per-field merge strategies — the category-defining innovation
**Zero breaking changes:** All additive

Introduced `MergeSchema` — the composable per-field strategy DSL. Also: delta sync for bandwidth-efficient replication, streaming merge for O(batch_size) memory. This is the release that made crdt-merge unique.

| Feature | What It Does |
|---------|-------------|
| **MergeSchema** | Per-field strategy DSL (MaxWins, MinWins, UnionSet, LWW, etc.) |
| **Delta sync** | Compute + apply deltas — only send what changed |
| **Streaming merge** | Generator-based O(batch_size) memory merge |

| Metric | Value |
|--------|-------|
| **Lines** | 2,820 |
| **Tests** | 175 |

---

### v0.4.0 — "The Trust Release" 🔍

**Codename:** Auditability
**Theme:** Know WHY every merge decision was made
**Zero breaking changes:** All additive

Two modules that transform crdt-merge from "useful library" to "auditable infrastructure": per-field provenance (every merge decision logged with who/what/why/which-strategy) and runtime CRDT verification (`@verified_merge` proves custom merge functions satisfy CRDT laws).

| Feature | What It Does |
|---------|-------------|
| **Provenance** | Per-field audit trail: source, strategy, winner, original values |
| **Verification** | Runtime proof that merge functions satisfy commutativity, associativity, idempotency |

| Metric | Value |
|--------|-------|
| **Lines** | 2,820 |
| **Tests** | 175 |

---

### v0.5.0 — "The Protocol Release" 📡

**Codename:** Interop
**Theme:** Cross-language wire format — the universal protocol
**Zero breaking changes:** All additive

The release that made crdt-merge a protocol, not just a library. Compact binary wire format (serialize → compress → transmit → decompress → deserialize). Probabilistic CRDTs (HyperLogLog, Bloom filter, Count-Min Sketch). Deduplication engine. Fuzzy matching. 13 modules, 3,790 lines, 423 tests.

| Feature | What It Does |
|---------|-------------|
| **Wire format** | Compact binary serialization for all CRDT types |
| **Compression** | zlib + zstd, 5-10× reduction |
| **Probabilistic CRDTs** | MergeableHLL, MergeableBloom, MergeableCMS |
| **Deduplication** | Exact + fuzzy dedup with configurable thresholds |

| Metric | Value |
|--------|-------|
| **Modules** | 13 |
| **Lines** | 3,790 |
| **Tests** | 423 |

---

### v0.5.1 — "The Hotfix Release" 🔧

**Theme:** Fix critical API gaps before any new feature work
**Release timing:** IMMEDIATE
**Zero breaking changes:** All fixes are additive validation + parameter additions

The flagship `merge()` function now accepts `MergeSchema` for per-field strategies. Plus: input validation (key/prefer), None handling in `merge_dicts()`, `__all__` exports across all 13 modules, docstring improvements. 24 defects resolved from documentation audit.

| Fix | What It Does |
|-----|-------------|
| **merge() + MergeSchema** | Flagship function now uses the flagship feature |
| **Key validation** | `KeyError` on non-existent key column |
| **Prefer validation** | `ValueError` on invalid prefer values |
| **None handling** | `merge_dicts()` treats None as missing |
| **`__all__` exports** | All 13 modules export clean public APIs |

| Metric | Value |
|--------|-------|
| **Lines** | ~3,880 |
| **Tests** | ~438 |
| **Defects fixed** | 24 |

---

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
- **Multi-region sync**: EU, US, Asia warehouses sync automatically via gossip
- **Threat intelligence**: Security IOCs propagate across all nodes in a mesh
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
# Any language can sync via HTTP — the server IS the universal adapter
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
**Theme:** Python defines the protocol. One Rust engine implements it. Every language wraps that engine.  
**Zero breaking changes:** Existing Python API untouched — this adds universal access ON TOP.

#### Architecture: `libcrdt_merge` — The Protocol Engine

Python is the reference implementation. It defines what correct behavior looks like. The Rust "protocol engine" is a thin (~1,000 line) implementation of **only the wire format + merge semantics** — it reads the exact same bytes Python's `serialize()` produces. Every other language wraps this engine via FFI. Nobody rewrites the merge algebra.

```
Python (reference implementation, ~8,000 lines)
    │
    │  defines: strategies, schemas, streaming,
    │  provenance, verification, gossip, integrations
    │
    │  publishes: wire format specification
    ▼
Rust Protocol Engine (~1,000 lines)
    │
    │  implements ONLY:
    │  ✓ wire format parse/emit
    │  ✓ CRDT merge operations (per the spec)
    │  ✓ schema evaluation
    │  ✓ deterministic serialization
    │
    │  does NOT implement:
    │  ✗ gossip / networking
    │  ✗ integrations
    │  ✗ compliance / RBAC
    │  ✗ streaming (handled by language-native I/O)
    ▼
┌─────────────────────────────────────┐
│         libcrdt_merge C ABI          │
│  (cbindgen → .so / .dylib / .dll)    │
└──────────┬───────────┬──────────────┘
           │           │
    FFI Wrappers      WASM build
    ┌──────┤          (wasm-pack)
    │      │              │
    │  Go (cgo)          Browser JS
    │  C# (P/Invoke)     Node.js / Deno / Bun
    │  Swift (C interop)  Cloudflare Workers
    │  Ruby (fiddle)      Fastly Compute
    │  PHP (FFI 7.4+)    Fermyon Spin
    │  Dart (dart:ffi)    Wasmtime / Wasmer
    │  Elixir (Rustler)
    │  Lua (LuaJIT FFI)
    │  R (.Call / Rcpp)
    │  C/C++ (direct)
    │  Zig (C interop)
    │  Haskell (FFI)
    │  OCaml (ctypes)
    │  Perl (FFI::Platypus)
    │
    └─ JVM (JNI):
       Java, Kotlin, Scala, Clojure, Groovy
```

This is exactly how **libsignal** (Signal), **libsodium** (NaCl), and **SQLite** achieve universal adoption — one core, wrappers everywhere.

#### Why Protocol Engine, Not "Rewrite in Rust"

| Concern | "Rewrite in Rust" | Protocol Engine |
|---------|-------------------|-----------------|
| **Python stays primary?** | ❌ Gets sidelined | ✅ Reference forever — all innovation starts here |
| **Effort** | Rewrite 8,000+ lines | ~1,000 lines (protocol only) |
| **Bug risk** | Two competing codebases | One spec, one thin engine, thin wrappers |
| **Innovation speed** | Gate new features on Rust port | Ship in Python first, engine catches up |
| **Developer confusion** | "Which codebase is canonical?" | Python is canonical. Engine is the translator. |
| **Wire compatibility** | Must stay in sync manually | Guaranteed — engine speaks Python's exact bytes |
| **Impact on Python users** | None — or worse, neglect | None — Python gets better, engine follows |

#### The C ABI: `libcrdt_merge.h`

```c
// Auto-generated by cbindgen from Rust source
// Every language calls these same functions

// === Lifecycle ===
crdt_context_t*  crdt_context_new(void);
void             crdt_context_free(crdt_context_t* ctx);

// === Core Merge ===
crdt_result_t    crdt_merge(
    const crdt_context_t* ctx,
    const uint8_t* record_a, size_t len_a,
    const uint8_t* record_b, size_t len_b,
    const uint8_t* schema,   size_t schema_len
);

// === Wire Format ===
crdt_wire_t      crdt_serialize(const uint8_t* state, size_t len, uint8_t type_tag);
crdt_result_t    crdt_deserialize(const uint8_t* wire, size_t wire_len);
crdt_wire_t      crdt_compress(const uint8_t* wire, size_t wire_len, uint8_t algo);
crdt_result_t    crdt_decompress(const uint8_t* compressed, size_t len);

// === Schema ===
crdt_schema_t*   crdt_schema_new(void);
void             crdt_schema_add_field(crdt_schema_t* s, const char* name, uint8_t strategy);
void             crdt_schema_free(crdt_schema_t* s);

// === CRDTs ===
crdt_gcounter_t* crdt_gcounter_new(const char* node_id);
void             crdt_gcounter_increment(crdt_gcounter_t* c, int64_t amount);
crdt_gcounter_t* crdt_gcounter_merge(const crdt_gcounter_t* a, const crdt_gcounter_t* b);
int64_t          crdt_gcounter_value(const crdt_gcounter_t* c);
void             crdt_gcounter_free(crdt_gcounter_t* c);
// ... same pattern for PNCounter, LWWMap, ORSet, HLL, Bloom, CMS

// === Delta ===
crdt_delta_t*    crdt_compute_delta(const uint8_t* old, size_t old_len,
                                     const uint8_t* new_, size_t new_len,
                                     const char* key);
crdt_result_t    crdt_apply_delta(const uint8_t* state, size_t state_len,
                                   const crdt_delta_t* delta);

// === Streaming ===
crdt_stream_t*   crdt_merge_stream_new(const crdt_schema_t* schema, const char* key);
void             crdt_merge_stream_push(crdt_stream_t* s, const uint8_t* record, size_t len);
crdt_result_t    crdt_merge_stream_finish(crdt_stream_t* s);
void             crdt_merge_stream_free(crdt_stream_t* s);

// === Memory ===
void             crdt_bytes_free(uint8_t* ptr, size_t len);
```

#### Language Wrapper Tiers

**Tier 1 — Native Ports** (full idiomatic implementations, independent of C ABI):

| Language | Package | Registry | Status |
|----------|---------|----------|--------|
| **Python** | `crdt-merge` | PyPI | ✅ Reference (v0.5.0) |
| **Rust** | `crdt-merge` | crates.io | ✅ v0.2.0 + protocol engine |
| **TypeScript** | `crdt-merge` | npm | ✅ v0.2.0, parity planned |
| **Java** | `crdt-merge` | Maven Central | 📋 v0.2.0, parity planned |

**Tier 2 — FFI Wrappers** (thin wrappers around `libcrdt_merge` protocol engine):

| Language | FFI Mechanism | Package | Registry | Use Case |
|----------|---------------|---------|----------|----------|
| **Go** | cgo | `crdt-merge-go` | Go modules | Cloud infrastructure, Kubernetes operators |
| **C#/.NET** | P/Invoke | `CrdtMerge` | NuGet | Enterprise, Unity, .NET microservices |
| **Swift** | C interop | `CRDTMerge` | Swift PM | iOS/macOS apps, Apple ecosystem |
| **Ruby** | fiddle/FFI | `crdt-merge` | RubyGems | Rails apps, data scripts |
| **PHP** | FFI (7.4+) | `crdt-merge` | Packagist | WordPress, Laravel, web backends |
| **Dart/Flutter** | dart:ffi | `crdt_merge` | pub.dev | Mobile apps (iOS + Android) |
| **Elixir** | Rustler NIF | `crdt_merge` | Hex.pm | Real-time systems, Phoenix |
| **Lua** | LuaJIT FFI | `crdt-merge` | LuaRocks | Game engines, embedded systems, Redis |
| **Zig** | C interop | `crdt-merge` | — | Systems programming, game engines |
| **Haskell** | FFI | `crdt-merge` | Hackage | Functional programming, formal methods |
| **OCaml** | ctypes | `crdt-merge` | opam | Finance, compilers, formal verification |
| **Perl** | FFI::Platypus | `CRDT::Merge` | CPAN | Legacy systems, text processing |
| **R** | .Call / Rcpp | `crdtmerge` | CRAN | Data science, statistics |
| **C/C++** | Direct | `libcrdt_merge` | vcpkg/Conan | Embedded, high-performance, native apps |

**Tier 3 — JVM Languages** (share Java port or use JNI to protocol engine):

| Language | Mechanism | Package |
|----------|-----------|---------|
| **Kotlin** | JVM interop / JNI | Same Maven artifact |
| **Scala** | JVM interop / JNI | Same Maven artifact |
| **Clojure** | JVM interop | Same Maven artifact |
| **Groovy** | JVM interop | Same Maven artifact |

**Tier 4 — WASM** (Rust protocol engine → wasm-pack, runs anywhere with a WASM host):

| Runtime | Platform | Use Case |
|---------|----------|----------|
| **Browser** | Chrome/Firefox/Safari | Client-side CRDT merge in web apps |
| **Node.js** | Server | JS/TS apps that want native speed |
| **Deno** | Server/Edge | Modern JS runtime |
| **Bun** | Server | Fast JS runtime |
| **Cloudflare Workers** | Edge | Edge-first CRDT sync |
| **Fastly Compute** | Edge | Edge CRDT at CDN scale |
| **Fermyon Spin** | Edge | Serverless WASM |
| **Wasmtime** | Any | Standalone WASM runtime |
| **Wasmer** | Any | Universal WASM runtime |

**Total: 4 native + 14 FFI + 5 JVM + 9 WASM runtimes = 20+ languages from one protocol engine.**

#### How a New Language Gets Added (The Wrapper Recipe)

Adding a new language takes 1-3 days using this template:

1. **Create the FFI binding file** (~100-200 lines): Declare the C ABI functions from `libcrdt_merge.h` using the language's FFI mechanism
2. **Create ergonomic wrappers** (~200-400 lines): Wrap raw C calls in idiomatic classes/structs (e.g., Go struct with methods, Swift class with ARC)
3. **Memory management**: Handle `crdt_*_free()` calls — use the language's destructor/finalizer pattern
4. **Run the certification test suite**: Python serialize → FFI deserialize → merge → serialize → Python deserialize. All CRDT types must roundtrip.
5. **Publish**: Package for the language's registry with pre-built `libcrdt_merge` binaries for Linux/macOS/Windows × x86_64/arm64

**Go example wrapper:**

```go
package crdtmerge

// #cgo LDFLAGS: -lcrdt_merge
// #include <libcrdt_merge.h>
import "C"
import "unsafe"

type GCounter struct {
    ptr *C.crdt_gcounter_t
}

func NewGCounter(nodeID string) *GCounter {
    cNodeID := C.CString(nodeID)
    defer C.free(unsafe.Pointer(cNodeID))
    return &GCounter{ptr: C.crdt_gcounter_new(cNodeID)}
}

func (g *GCounter) Increment(amount int64) {
    C.crdt_gcounter_increment(g.ptr, C.int64_t(amount))
}

func (g *GCounter) Merge(other *GCounter) *GCounter {
    return &GCounter{ptr: C.crdt_gcounter_merge(g.ptr, other.ptr)}
}

func (g *GCounter) Value() int64 {
    return int64(C.crdt_gcounter_value(g.ptr))
}

func (g *GCounter) Close() {
    C.crdt_gcounter_free(g.ptr)
}
```

Every other FFI wrapper follows the exact same structure adapted to that language's conventions.

#### Cross-Language Certification Test Suite

The gold standard: **any two implementations can exchange data perfectly**.

```
Test Matrix (every pair):
  Python ↔ Rust ↔ TypeScript ↔ Java ↔ Go ↔ C# ↔ Swift ↔ Ruby ↔ WASM

For each pair, for each CRDT type:
  ✅ serialize in Language A → deserialize in Language B
  ✅ merge in Language A produces identical result to merge in Language B
  ✅ compress → decompress roundtrip across languages
  ✅ schema roundtrip (same DSL, same behavior)
  ✅ delta compute in A → apply in B → same result

Certification output:
  crdt-merge-interop-report.json
  {
    "python_to_rust": {"gcounter": "PASS", "pncounter": "PASS", ...},
    "rust_to_go": {"gcounter": "PASS", "pncounter": "PASS", ...},
    ...
    "total_pairs_tested": 36,
    "total_assertions": 2160,
    "failures": 0
  }
```

#### Wire Format Specification v1.0

Published as a formal specification (RFC-style). Python's current wire format becomes the spec:

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

#### Delivery Timeline

| Phase | Languages | Effort | Priority |
|-------|-----------|--------|----------|
| **Phase 0** | Rust protocol engine (`libcrdt_merge`) | ~2 weeks | 🔴 Critical — everything depends on this |
| **Phase 1** | Go, C#, Swift (highest demand) | ~1 week each | 🔴 Critical |
| **Phase 2** | Ruby, PHP, Dart/Flutter (web/mobile) | ~3-5 days each | 🟡 High |
| **Phase 3** | Elixir, Lua, R (niche but loyal) | ~3-5 days each | 🟢 Medium |
| **Phase 4** | Zig, Haskell, OCaml, Perl (completeness) | ~2-3 days each | ⚪ Nice-to-have |
| **WASM** | All 9 runtimes via wasm-pack | ~2 weeks total | 🔴 Critical (parallel with Phase 1) |

#### What This Enables
- **Polyglot microservices**: Python data pipeline → Go API server → Swift mobile app — all speak the same wire format
- **Mobile-native**: Dart/Flutter for cross-platform mobile, Swift for iOS-native
- **Game engines**: Lua (Roblox), Zig/C++ (Unreal), C# (Unity)
- **Data science**: R and Python for statistical analysis with CRDT semantics
- **Legacy systems**: PHP, Perl, Ruby — CRDT merge for existing codebases
- **Formal methods**: Haskell, OCaml — verification-friendly languages love CRDTs
- **Edge everywhere**: WASM runs on Cloudflare, Fastly, Deno, browsers — CRDT merge at the CDN

#### Test Targets
- Cross-language roundtrip: every pair of implementations (36+ pairs)
- Performance parity: FFI wrappers within 1.5x of native Rust baseline
- WASM: browser + Node + Deno + Cloudflare Workers certification
- **~800 new tests (across all languages), total ~1,700**

#### Lines Estimate: ~8,000 (Python core) + ~1,000 Rust protocol engine + ~400 per FFI wrapper (~6,000 wrapper code)

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
- **~300 new tests, total ~2,000**

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

| Requirement | Python | Rust | TS | Java | Go | C# | Swift | Ruby | PHP | Dart | Elixir | WASM |
|-------------|:------:|:----:|:--:|:----:|:--:|:--:|:-----:|:----:|:---:|:----:|:------:|:----:|
| Core merge | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Schema DSL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wire format | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Delta sync | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Provenance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Verification | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Probabilistic | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gossip | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — | ✅ | — |
| Encryption | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Compliance | ✅ | ✅ | — | ✅ | — | — | — | — | — | — | — | — |
| **Wire roundtrip** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

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
| **Python lines** | 791 | 3,790 | ~10,000 |
| **Total lines (all languages)** | ~5,000 | ~10,000 | ~50,000 |
| **Languages** | 4 | 4 | 20+ (4 native + 14 FFI + WASM) |
| **Tests (Python)** | 133 | 423 | ~2,000 |
| **Tests (all languages)** | 1,347 | ~1,800 | ~10,000 |
| **Modules (Python)** | 5 | 13 | ~22 |
| **Strategies** | 1 (LWW) | 8 | 8+ (stable) |
| **Wire format types** | 0 | 5 | 12+ |
| **Integrations** | 0 | 0 | 6 (Kafka, Flink, dbt, Airflow, LangChain, HTTP server) |
| **Package registries** | 3 | 3 | 14+ (PyPI, npm, crates.io, Maven, Go modules, NuGet, SPM, RubyGems, Packagist, pub.dev, Hex.pm, LuaRocks, CRAN, Hackage) |

---

## 5. Evolution Summary

| Version | Codename | Theme | Key Features | Lines | Tests |
|---------|----------|-------|-------------|-------|-------|
| v0.1.0 | Launch | Origin | Core merge | — | — |
| v0.2.0 | IP Protection | Foundation | 4 languages, basic CRDTs | 1,578 | 133 |
| v0.3.0 | The Schema Release | Composability | Schema DSL, delta sync, streaming | 2,820 | 175 |
| v0.4.0 | The Trust Release | Auditability | Provenance, verification | 2,820 | 175 |
| v0.5.0 | The Protocol Release | Interop | Wire format, compression, probabilistic CRDTs | 3,790 | 423 |
| **v0.6.0** | **The Distributed Release** | **Scaling** | **Gossip, vector clocks, Merkle anti-entropy** | **~4,800** | **~620** |
| **v0.7.0** | **The Integration Release** | **Ecosystem** | **Kafka, Flink, dbt, Airflow, LangChain, HTTP server** | **~6,500** | **~920** |
| **v0.8.0** | **The Polyglot Release** | **Universal** | **Protocol engine, 20+ languages via FFI, WASM, certified roundtrip** | **~8,000** | **~1,700** |
| **v0.9.0** | **The Enterprise Release** | **Trust** | **Encryption, RBAC, compliance, observability** | **~9,000** | **~2,000** |
| **v1.0.0** | **The Platform Release** | **Definitive** | **API freeze, formal spec, security audit, full docs** | **~10,000** | **~2,000** |

---

## 6. The Narrative Arc

### v0.2.0 → v0.5.0: "We Built the Core"
> A 21 KB library with composable merge strategies, provenance, verification, and a cross-language wire format. Zero dependencies. 423 tests. The only library for batch dataset reconciliation.

### v0.6.0 → v0.7.0: "We Made It Distributed"
> Multi-node gossip sync, anti-entropy, and connectors for every major data tool. The merge algebra that works at the edge, in the cloud, and in your Kafka pipeline.

### v0.8.0: "We Made It Universal"
> Python defines the protocol. A thin Rust engine implements it. FFI wrappers give every language access. Python serialize → Go deserialize → Swift consume → Dart display. One protocol, every language.

### v0.9.0 → v1.0.0: "We Made It Enterprise"
> Encryption, RBAC, compliance, observability. HIPAA/SOX/GDPR ready. Formal specification. Security-audited. The platform.

### The One-Liner
**"The SQLAlchemy of distributed data merging — composable, verifiable, auditable, and it speaks 20+ languages through one protocol engine."**

---

## 7. Universal Evolution Checklist

What makes this a universal platform — features nobody else has, all in one library:

- [ ] **Only library for batch dataset reconciliation** (category of one)
- [ ] **Composable per-field merge strategy DSL** (not rigid operators)
- [ ] **Runtime CRDT formal verification** (not just compile-time)
- [ ] **Per-field merge provenance with compliance-ready audit** (human-readable why)
- [ ] **Python-first, universally portable** (reference impl → protocol engine → 20+ languages via FFI/WASM)
- [ ] **Zero dependencies** (21 KB — embeds anywhere)
- [ ] **Built-in gossip protocol for horizontal scaling** (not just single-node)
- [ ] **Kafka/Flink/dbt/Airflow/LangChain integrations** (connected to the stack)
- [ ] **WASM universal runtime** (browser, edge, serverless)
- [ ] **End-to-end encryption + RBAC** (defense-grade sync)
- [ ] **Probabilistic CRDTs** (HLL, Bloom, CMS with merge semantics)
- [ ] **Formal published specification** (anyone can build a conformant implementation)
- [ ] **2,000+ tests across 20+ languages** (battle-tested)
- [ ] **Apache-2.0 open core** (maximum adoption, CLA for future flexibility)

**When all boxes are checked: that's the platform. That's the moat. That's the universal evolution.**

---

## 8. The Ecosystem Effect

```
crdt-merge v1.0.0 (Apache-2.0, open, 20+ languages)
    │
    │  Python reference + libcrdt_merge protocol engine
    │
    ├── crdt-merge-server (HTTP/gRPC microservice)
    ├── crdt-merge-kafka (stream processing)
    ├── crdt-merge-flink (stream analytics)
    ├── crdt-merge-dbt (analytics engineering)
    ├── crdt-merge-airflow (orchestration)
    └── crdt-merge-langchain (AI agents)
        ↓ all used by
    Applications built on the crdt-merge protocol
```

The open core builds the ecosystem.  
The protocol engine creates universal access.  
The integrations make it sticky.  
The wire format creates network effects.  
The standard wins.

---

*Copyright 2026 Ryan Gillespie — Optitransfer AG*  
*Contact: rgillespie83@icloud.com, data@optitransfer.ch*
