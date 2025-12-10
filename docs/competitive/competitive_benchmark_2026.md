# crdt-merge Competitive Analysis & Benchmark Report

**Date:** March 28, 2026  
**Version:** crdt-merge v0.5.1  
**Classification:** Strategic — Internal Use  

---

## 1. Executive Summary

**crdt-merge** occupies a genuinely empty niche in the software landscape: a **library-level CRDT merge toolkit for structured data** with per-field conflict-resolution strategies, provenance tracking, and formal verification.

The broader CRDT ecosystem is thriving — Yjs dominates real-time collaboration (21.5K ⭐), Loro 1.0 shipped a landmark release with Eg-walker and rich text, and Electric SQL is gaining traction in local-first sync (10K ⭐). But none of these tools solve the problem crdt-merge targets: **batch dataset merge/reconciliation with deterministic, per-field strategies and an audit trail.**

Today, teams reconciling conflicting datasets reach for `pandas.merge()` (which offers zero conflict resolution), ad-hoc Python scripts, or manual spreadsheet work. There is no production-grade library that treats dataset merge as a CRDT algebra problem with configurable strategies per column, provenance, verification, and streaming support.

crdt-merge is that library. With 13 modules, 425 tests, zero dependencies, and published packages on PyPI, npm, and crates.io, it is the only tool in its class. Its roadmap — Arrow-native performance (v0.6), SQL integration via MergeQL (v0.7), AI model weight merging (v0.8), and GDPR-compliant reversible merge (v0.9) — targets high-value gaps that no competitor is pursuing.

**Strategic position:** First mover in an uncontested niche with a defensible roadmap. The risk is not competition — it's adoption. The opportunity is enormous if crdt-merge becomes the standard primitive for deterministic data reconciliation.

---

## 2. crdt-merge Capability Inventory

### 2.1 Current State (v0.5.1)

| Dimension | Detail |
|---|---|
| **Codebase** | 13 modules, 4,028 LOC (Python reference) |
| **Tests** | 425 total — 422 pass, 2 skip, 1 expected fail |
| **Language ports** | Python (PyPI), TypeScript (npm), Rust (crates.io), Java (source) |
| **Dependencies** | Zero external dependencies (core library) |
| **License** | Apache-2.0 |
| **GitHub** | mgillr/crdt-merge — ⭐ 0, 🍴 0 (newly public) |

### 2.2 Feature Map

| Category | Features |
|---|---|
| **Core CRDTs** | GCounter, PNCounter, LWWRegister, ORSet, LWWMap |
| **Merge Strategies** | LWW, MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins, Custom (user-defined function) |
| **MergeSchema DSL** | Per-field strategy assignment: `MergeSchema(default=LWW(), overrides={"score": MaxWins(), "tags": UnionSet()})` |
| **DataFrame Merge** | `merge(df_a, df_b, key="id", schema=schema)` — pandas, Polars, or any dict-like |
| **Provenance** | Per-field source tracking, full audit trail |
| **Streaming** | `merge_stream()`, `merge_sorted_stream()` — O(1) memory, 1.2M rows/sec |
| **Delta Sync** | `compute_delta()`, `apply_delta()`, `compose_deltas()`, `DeltaStore` |
| **Verification** | `verify_crdt()`, `verified_merge()` — runtime proof of commutativity, associativity, idempotence, convergence |
| **Wire Protocol** | `serialize()` / `deserialize()` — binary format with compression, cross-language compatible |
| **Deduplication** | Exact, fuzzy (Dice coefficient), MinHash probabilistic |
| **Probabilistic** | MergeableHLL (cardinality), MergeableBloom (membership), MergeableCMS (frequency) |
| **JSON Merge** | `merge_dicts()` — deep recursive dict merge with None handling |
| **HuggingFace** | `merge_datasets()`, `dedup_dataset()` — HuggingFace Datasets integration |
| **Diff** | `diff(df_a, df_b, key)` — structural diff between datasets |

### 2.3 Performance Benchmarks (A100 GPU, Google Colab)

| Version | Measurements | Highlight |
|---|---|---|
| v0.3.0 | 173 | 1.2M rows/sec streaming, <0.1s for 10K rows |
| v0.4.0 | 55 | Strategies + provenance benchmarked |
| v0.5.0 | 50 | Wire protocol + probabilistic benchmarked |

### 2.4 Roadmap

| Version | Codename | Key Features | Strategic Impact |
|---|---|---|---|
| **v0.6.0** | Arrow | Arrow-native merge (10–50× speedup), schema evolution (column mapping, type coercion), async merge, multi-key support | Transforms from "neat library" to production pipeline component |
| **v0.7.0** | SQL | MergeQL (DuckDB SQL: `SELECT * FROM crdt_merge(a, b)`), self-merging Parquet files | Reaches every SQL-literate data user |
| **v0.8.0** | Intelligence | ModelCRDT (AI model weight merging — TIES, DARE, SLERP as strategies), conflict topology visualization | Captures exploding LLM model merging wave |
| **v0.9.0** | Compliance | UnmergeEngine (reversible CRDT merge for GDPR erasure), parallel merge | GDPR/AI Act compliance that nobody else offers |
| **v1.0.0** | Platform | Stable APIs, Rust protocol engine (~1,000 LOC), FFI wrappers for all languages | Production-grade, multi-language foundation |

---

## 3. Competitive Landscape

### 3.1 Real-time CRDT Libraries

These are **not direct competitors** — they solve real-time collaborative editing, not batch dataset merge. They are included for landscape context.

| Project | ⭐ Stars | 🍴 Forks | Language | Last Active | Status | Notes |
|---|---|---|---|---|---|---|
| **Yjs** | 21,524 | 753 | JavaScript | 2026-03-27 | 🟢 Active | Dominant in real-time collab. Vast ecosystem of bindings and editors. |
| **Automerge** | 6,110 | 239 | JavaScript | 2026-03-26 | 🟢 Active | Pioneer of CRDT concept for developers. Strong academic lineage (Martin Kleppmann). |
| **Loro** | 5,464 | 137 | Rust | 2026-03-27 | 🟢 Active | Loro 1.0 (Sept 2025) — Eg-walker algorithm, Peritext+Fugue rich text, MovableTree, Git-like version control, LSM-based lazy loading, 10–100× import speedup. A technical tour de force. |

**Assessment:** This category is mature and well-served. Yjs is the ecosystem leader; Loro is the performance/features leader. crdt-merge should **never** compete here. Different problem domain entirely.

### 3.2 CRDT Databases

These embed CRDTs into database storage/replication layers. Not direct competitors — crdt-merge is a library, not a database.

| Project | ⭐ Stars | 🍴 Forks | Language | Last Active | Status | Notes |
|---|---|---|---|---|---|---|
| **Gun.js** | 18,989 | 1,235 | JavaScript | 2026-03-01 | 🟢 Active | Graph-based CRDT, P2P, Lamport clocks. Large community. |
| **OrbitDB** | 8,760 | 592 | JavaScript | 2026-02-22 | 🟢 Active | IPFS-based distributed DB. Niche but stable. |
| **Ditto** | Proprietary | — | Closed | — | 🟢 Active | $82M Series B. Enterprise CRDT mesh (BLE, WiFi, P2P). Military/defense/logistics. |
| **DefraDB** | ~900 | — | Go | — | 🟡 Slow | Source Inc. P2P document DB with CRDT. Intermittent development. |
| **Riak KV** | ~5,000 | — | Erlang | ~2023 | 🔴 Stale | TI Tokyo acquired. No meaningful activity since 2023. |

**Assessment:** Gun.js and OrbitDB are community-driven with large install bases but narrow use cases. Ditto is the well-funded commercial player targeting IoT/edge. None of these solve batch dataset merge.

### 3.3 Local-first Sync

Sync engines that keep local and remote data in sync. Adjacent to crdt-merge's delta sync but fundamentally different architecture.

| Project | ⭐ Stars | 🍴 Forks | Language | Last Active | Status | Notes |
|---|---|---|---|---|---|---|
| **Electric SQL** | 10,030 | 317 | Elixir | 2026-03-28 | 🟢 Active | Postgres sync, local-first. Growing fast — the rising star of this category. |
| **cr-sqlite** | 3,668 | 112 | Rust | 2024-10-25 | 🔴 Stale | No commits since Oct 2024. Vulcan Labs pivoted. Effectively dead. |
| **PowerSync** | 646 | 66 | TypeScript | 2026-03-26 | 🟢 Active | Sync engine for Postgres/MongoDB. Smaller but maintained. |
| **TanStack DB** | — | — | TypeScript | Recent | 🟢 Active | Query-driven sync, integrates with Electric/PowerSync. New entrant. |
| **PGlite** | — | — | TypeScript | Recent | 🟢 Active | Postgres in browser via WASM. Complementary to sync engines. |

**Assessment:** Electric SQL is the one to watch — it's growing rapidly and backed by a strong team. cr-sqlite's death leaves a gap in the "CRDTs in SQLite" space. None of these are merge toolkits; they're sync infrastructure.

### 3.4 Data Merge Tools — Our REAL Competitive Space

These are **the actual alternatives** teams use when they need to merge conflicting datasets.

| Tool | Language | Last Active | Status | Conflict Resolution | Per-field Strategies | Provenance | Verification |
|---|---|---|---|---|---|---|---|
| **pandas.merge()** | Python | Ongoing | 🟢 Active | ❌ None — SQL-like joins only | ❌ None | ❌ None | ❌ None |
| **Polars join** | Rust+Python | Ongoing | 🟢 Active | ❌ None — SQL-like joins only | ❌ None | ❌ None | ❌ None |
| **DuckDB MERGE INTO** | C++ | Ongoing | 🟢 Active | ⚡ SQL MERGE (SCD Type 2 upserts) | ❌ None | ❌ None | ❌ None |
| **dbt merge** | SQL | Ongoing | 🟢 Active | ⚡ SQL MERGE semantics | ❌ None | ❌ None | ❌ None |
| **Great Expectations** | Python | Ongoing | 🟢 Active | ❌ None (validation only) | ❌ None | ❌ None | ⚡ Data quality checks |
| **Ad-hoc scripts** | Any | — | — | ⚡ Custom, fragile | ⚡ Manual, per-project | ❌ None | ❌ None |
| **Manual reconciliation** | Spreadsheet | — | — | ⚡ Human judgment | ⚡ Manual, per-cell | ❌ None | ❌ None |
| **crdt-merge** | Python/TS/Rust/Java | 2026-03-28 | 🟢 Active | ✅ Full CRDT algebra | ✅ 8+ built-in + custom | ✅ Full per-field | ✅ Runtime proof |

**Assessment:** This is where crdt-merge's value proposition is clearest. Every existing tool either offers zero conflict resolution (pandas, Polars) or limited SQL MERGE semantics (DuckDB, dbt). **Nobody — literally nobody — does per-field CRDT merge with configurable strategies.** The real "competitors" are ad-hoc scripts and manual processes, which is the best possible competitive position for a new library.

### 3.5 Data Lakehouses

Warehouse-scale data management platforms. Not competitors — they operate at a completely different layer.

| Project | ⭐ Stars | Language | Last Active | Status | Notes |
|---|---|---|---|---|---|
| **Delta Lake** | 8,000+ | Scala/Rust | Ongoing | 🟢 Active | Schema evolution, ACID, time travel. Databricks ecosystem. |
| **Apache Iceberg** | 7,000+ | Java | Ongoing | 🟢 Active | Schema evolution, partitioning. Snowflake/AWS/Netflix backing. |
| **Apache Hudi** | 5,500+ | Java | Ongoing | 🟢 Active | Merge-on-read, incremental processing. |

**Assessment:** All three do warehouse MERGE (upsert/append semantics) with schema evolution. None offer per-field conflict-resolution strategies, provenance, or CRDT verification. They're infrastructure for petabyte-scale warehouses; crdt-merge is a library for algorithmic merge. Different layers entirely — and potentially **complementary** (crdt-merge could resolve conflicts before writing to Delta/Iceberg/Hudi).

### 3.6 Emerging Tech & Adjacent

| Project / Concept | Domain | Status | Notes |
|---|---|---|---|
| **mergekit** | LLM model merging | 🟢 Active | Popular HuggingFace tool. TIES, DARE, SLERP methods. Not CRDT-based. |
| **CRDV (SIGMOD 2025)** | CRDT+SQL theory | 📄 Paper | Defined CRDT+SQL formalism. Nobody has implemented it as a library. |
| **SQLRooms (FOSDEM 2026)** | CRDTs + SQL | 📄 Concept | Placed CRDTs alongside SQL but didn't merge them. |
| **Velt** | Real-time collab SDK | 🟢 Active | Commercial. Collaboration features, not CRDT merge. |
| **Model merging papers** | AI research | 📄 Exploding | Dozens of NeurIPS/ICML/CVPR 2025–2026 papers. CRDT connection unexplored. |

---

## 4. Feature Benchmark Matrix

Comprehensive feature comparison across all categories. Scoring: ✅ Full | ⚡ Partial | ❌ None | 🔮 Roadmap (crdt-merge only)

### 4.1 Core Merge Capabilities

| Feature | crdt-merge | pandas | Polars | DuckDB | Automerge | Yjs | Loro | Electric SQL | Delta Lake |
|---|---|---|---|---|---|---|---|---|---|
| **Key-based row merge** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Per-field strategies** | ✅ 8+ built-in | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Custom strategy function** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MergeSchema DSL** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **CRDT algebra** | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ⚡ | ❌ |
| **Conflict resolution** | ✅ Deterministic | ❌ | ❌ | ⚡ SQL MERGE | ✅ Auto | ✅ Auto | ✅ Auto | ⚡ LWW | ❌ |
| **Provenance tracking** | ✅ Per-field | ❌ | ❌ | ❌ | ❌ | ❌ | ⚡ Version | ❌ | ⚡ Time travel |
| **CRDT verification** | ✅ Runtime proof | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 4.2 Data & Performance

| Feature | crdt-merge | pandas | Polars | DuckDB | Automerge | Yjs | Loro | Electric SQL | Delta Lake |
|---|---|---|---|---|---|---|---|---|---|
| **Streaming merge** | ✅ O(1) mem | ❌ | ⚡ Lazy | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Throughput** | 1.2M rows/s | High | Very High | Very High | N/A | N/A | N/A | N/A | Very High |
| **Arrow-native** | 🔮 v0.6.0 | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Schema evolution** | 🔮 v0.6.0 | ❌ | ❌ | ⚡ | ❌ | ❌ | ❌ | ⚡ | ✅ |
| **Delta sync** | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ⚡ |
| **Multi-key support** | 🔮 v0.6.0 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Zero dependencies** | ✅ | ❌ (NumPy) | ❌ (native) | ❌ (native) | ❌ | ❌ | ❌ | ❌ | ❌ |

### 4.3 Advanced & Unique Features

| Feature | crdt-merge | pandas | Polars | DuckDB | Automerge | Yjs | Loro | Electric SQL | Delta Lake |
|---|---|---|---|---|---|---|---|---|---|
| **Deduplication** | ✅ Exact+Fuzzy+MinHash | ⚡ `drop_duplicates` | ⚡ `unique` | ⚡ `DISTINCT` | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Probabilistic structs** | ✅ HLL+Bloom+CMS | ❌ | ❌ | ⚡ HLL | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Wire protocol** | ✅ Binary+compress | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **HuggingFace integration** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **JSON deep merge** | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Structural diff** | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **SQL integration** | 🔮 MergeQL v0.7.0 | ❌ | ❌ | ✅ Native | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Model weight merge** | 🔮 v0.8.0 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Reversible merge (unmerge)** | 🔮 v0.9.0 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚡ Time travel |
| **Multi-language** | ✅ 4 languages | ❌ Python | ❌ Rust+Py | ❌ C++ | ✅ JS+Rust | ❌ JS | ❌ Rust | ❌ Elixir | ❌ Scala |

### 4.4 Summary Scorecard (features relevant to batch dataset merge)

| Criterion | crdt-merge | pandas.merge | Polars join | DuckDB MERGE | Ad-hoc scripts |
|---|---|---|---|---|---|
| Per-field conflict resolution | ✅ | ❌ | ❌ | ❌ | ⚡ |
| Configurable strategies | ✅ | ❌ | ❌ | ❌ | ⚡ |
| Provenance / audit trail | ✅ | ❌ | ❌ | ❌ | ❌ |
| CRDT guarantees (verified) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Streaming (large datasets) | ✅ | ❌ | ⚡ | ✅ | ⚡ |
| Delta/incremental sync | ✅ | ❌ | ❌ | ❌ | ⚡ |
| Deduplication | ✅ | ⚡ | ⚡ | ⚡ | ⚡ |
| Multi-language | ✅ | ❌ | ⚡ | ⚡ | ❌ |
| Zero dependencies | ✅ | ❌ | ❌ | ❌ | ✅ |
| Community / ecosystem | ❌ New | ✅ Massive | ✅ Growing | ✅ Growing | N/A |
| Documentation / examples | ⚡ | ✅ | ✅ | ✅ | ❌ |

---

## 5. Activity Status Assessment

### 🟢 Active (regular commits, maintained, growing)

| Project | Confidence | Trend |
|---|---|---|
| Yjs | High | Stable leader, enormous ecosystem |
| Automerge | High | Consistent development |
| Loro | High | Accelerating — 1.0 was a landmark release |
| Electric SQL | High | Fastest growing in local-first space |
| Gun.js | Medium | Active but community-driven, sporadic |
| OrbitDB | Medium | Steady maintenance |
| PowerSync | Medium | Smaller but consistent |
| Delta Lake / Iceberg / Hudi | High | Enterprise-backed, very active |
| DuckDB | High | One of the hottest projects in data |
| Ditto | High | Well-funded commercial ($82M) |

### 🟡 Slow (intermittent updates, uncertain trajectory)

| Project | Confidence | Risk |
|---|---|---|
| DefraDB | Medium | Source Inc resources unclear. P2P document DB with CRDT but slow pace. |

### 🔴 Stale (no meaningful updates in 6+ months)

| Project | Last Active | Notes |
|---|---|---|
| cr-sqlite | Oct 2024 | Matt Wonlaw / Vulcan Labs pivoted. 18 months without commits. Effectively dead. |

### ⚫ Dead / Legacy

| Project | Notes |
|---|---|
| Riak KV | TI Tokyo acquired. No meaningful activity since 2023. Legacy Erlang codebase. |

---

## 6. Gap Analysis

### 6.1 True Gaps — Where Nobody Competes (Our Opportunity)

These are genuine whitespace opportunities where crdt-merge is the **only** solution or where no solution exists at all.

| Gap | Current State | crdt-merge Position | Strategic Value |
|---|---|---|---|
| **Per-field merge strategies for structured data** | Nobody. Teams use ad-hoc scripts or manual processes. | ✅ Only solution. 8+ built-in strategies + custom. | 🔥 **Core moat.** This is our reason to exist. |
| **CRDT verification for merge operations** | No library offers runtime proof of CRDT properties. | ✅ `verify_crdt()` and `verified_merge()` are unique. | 🔥 High. Trust/audit differentiator. |
| **Provenance-tracked merge** | No merge tool tracks per-field source attribution. | ✅ Full per-field provenance. | 🔥 High. Compliance and debugging. |
| **CRDT algebra for SQL (MergeQL)** | CRDV paper (SIGMOD 2025) defined theory. Nobody implemented it. | 🔮 v0.7.0 MergeQL. Would be the **first implementation**. | 🔥 Very high. Massive addressable market. |
| **CRDT-based model weight merging** | mergekit exists but isn't CRDT-based. No formal algebra for model merge. | 🔮 v0.8.0 ModelCRDT (TIES, DARE, SLERP as strategies). | 🔥 High. AI/ML wave. |
| **Reversible merge (unmerge) for GDPR** | Nobody offers reversible CRDT merge. Delta Lake has time travel but not per-record erasure. | 🔮 v0.9.0 UnmergeEngine. | 🔥 High. Regulatory tailwind (EU AI Act 2025–2026). |
| **Mergeable probabilistic data structures** | No library packages HLL+Bloom+CMS as mergeable CRDTs. | ✅ MergeableHLL, MergeableBloom, MergeableCMS. | Medium. Niche but valuable for analytics pipelines. |
| **HuggingFace dataset merge** | No CRDT-aware merge for HuggingFace Datasets. | ✅ `merge_datasets()`, `dedup_dataset()`. | Medium. Growing ecosystem. |

### 6.2 Gaps Where We Should NOT Compete

These are well-served markets where entering would be a strategic mistake.

| Domain | Why Not | Who Owns It |
|---|---|---|
| **Real-time collaborative editing** | Mature, highly competitive, different architecture entirely. | Yjs (21.5K ⭐), Loro (5.4K ⭐), Automerge (6.1K ⭐) |
| **Rich text CRDTs** | Loro has Peritext+Fugue. Years of specialized research. | Loro |
| **Tree/graph CRDTs** | Loro's MovableTree is state-of-art. Specialized data structure. | Loro |
| **CRDT database persistence** | Product-level concern. Requires storage engine, networking. | Gun.js, OrbitDB, Ditto |
| **Mesh networking / P2P sync** | Requires networking stack, hardware integration. | Ditto ($82M), libp2p |
| **Warehouse-scale MERGE** | Petabyte-scale, requires distributed compute infrastructure. | Delta Lake, Iceberg, Hudi |
| **Data quality / validation** | Different problem (checking data, not merging it). | Great Expectations |
| **Real-time sync infrastructure** | Requires server infrastructure, CDC pipelines. | Electric SQL, PowerSync |

### 6.3 Gaps That Are Opportunities for Products Built on crdt-merge

These are valuable market opportunities that should be addressed by **products and services built on top of the core library**, not by the library itself.

| Opportunity | Why It's a Product, Not a Library Feature |
|---|---|
| Database with built-in CRDT merge | Requires persistence, networking, query engine — product scope |
| Visual merge conflict resolution UI | Requires frontend, UX design — product scope |
| Managed merge-as-a-service API | Requires infrastructure, billing, SLAs — product scope |
| Data pipeline orchestrator with CRDT merge | Requires workflow engine, scheduling — product scope |
| Enterprise compliance platform | Requires audit logging, role management, UI — product scope |

---

## 7. Academic & Research Landscape

### 7.1 Key Papers & Developments (2024–2026)

| Paper / Development | Venue | Year | Relevance to crdt-merge |
|---|---|---|---|
| **CRDV: Conflict-free Replicated Data Views** | SIGMOD 2025 | 2025 | Defined CRDT+SQL formalism. **Nobody has implemented it as a library.** MergeQL (v0.7.0) would be the first. |
| **SQLRooms** | FOSDEM 2026 | 2026 | CRDTs alongside SQL but didn't merge them. Validates the problem space. |
| **Loro 1.0 — Eg-walker algorithm** | Industry | 2025 | Breakthrough in real-time CRDT performance. Different domain but validates CRDT investment. |
| **TIES: Trimming, Electing, Merging** | NeurIPS 2023 | 2023 | Model weight merging — resolves parameter interference. ModelCRDT roadmap feature. |
| **DARE: Drop And Rescale** | arXiv 2024 | 2024 | Sparse model merging technique. ModelCRDT roadmap feature. |
| **SLERP (Spherical Linear Interpolation)** | Multiple | 2024+ | Standard for LLM weight interpolation. ModelCRDT roadmap feature. |
| **Model merging explosion** | NeurIPS/ICML/CVPR 2025–2026 | 2025–2026 | Dozens of papers on model merging + federated learning. **Nobody has unified under CRDT algebra.** |
| **EU AI Act enforcement** | Regulatory | 2025–2026 | Stricter GDPR + AI-specific data requirements. Drives demand for reversible merge and provenance. |

### 7.2 Emerging Trends

1. **Model merging as a discipline** — The LLM community has independently reinvented merge strategies (TIES, DARE, SLERP, Task Arithmetic) without the formal CRDT framework. There's a massive opportunity to unify these under CRDT algebra, providing commutativity/associativity guarantees for model merge.

2. **Local-first as architecture** — The local-first movement (Electric SQL, PowerSync, PGlite) is driving demand for sync primitives. crdt-merge's delta sync could serve as a building block.

3. **Data provenance for compliance** — EU AI Act and evolving GDPR enforcement are making data lineage a hard requirement. crdt-merge's per-field provenance tracking is ahead of the curve.

4. **CRDT+SQL convergence** — The CRDV paper (SIGMOD 2025) and SQLRooms (FOSDEM 2026) show academic interest in marrying CRDTs with SQL. MergeQL would be the **first practical implementation**.

5. **Reversible computation** — Growing interest in undo/unmerge capabilities for compliance. No existing CRDT library supports true reversible merge.

---

## 8. Strategic Recommendations

### 8.1 Overarching Strategy

**Be the standard primitive for deterministic data reconciliation.**

crdt-merge should be to dataset merge what `pandas.merge()` is to SQL joins — the obvious, default choice — but with the superpowers of per-field strategies, provenance, and CRDT guarantees. The library must remain pure: algorithms, strategies, verification, zero dependencies.

### 8.2 Priority Actions

#### Tier 1: Foundation (Critical Path to Adoption)

| Action | Rationale | Timeline |
|---|---|---|
| **Ship Arrow-native merge (v0.6.0)** | Performance is the #1 barrier to production adoption. 10–50× speedup makes crdt-merge viable for real pipelines. Polars and DuckDB users expect Arrow-speed. | Immediate |
| **Schema evolution (v0.6.0)** | The #1 real-world friction point. Datasets in the wild have mismatched columns, renamed fields, type differences. Without this, users hit walls on day one. | Immediate |
| **Build adoption through documentation & examples** | Zero stars, zero forks. The library needs a compelling README, cookbook, and comparison guides ("crdt-merge vs pandas.merge()" etc.). | Immediate |
| **Publish benchmarks publicly** | Performance data exists (173+ measurements). Publish as reproducible notebooks showing crdt-merge vs pandas vs Polars for merge-with-conflicts scenarios. | Immediate |

#### Tier 2: Market Expansion (Reach New Users)

| Action | Rationale | Timeline |
|---|---|---|
| **Ship MergeQL (v0.7.0)** | DuckDB has 30K+ stars. Putting CRDT merge in SQL (`SELECT * FROM crdt_merge(a, b)`) reaches every data analyst, not just Python devs. First implementation of CRDV theory. | Next |
| **Self-merging Parquet files (v0.7.0)** | Parquet is the lingua franca of data. If a Parquet file carries its merge schema, any tool can merge it deterministically. Viral distribution mechanism. | Next |
| **Target data engineering workflows** | Position as a drop-in addition to ETL/ELT pipelines. Integrations with Airflow, Dagster, Prefect. | Next |

#### Tier 3: Differentiation (Capture Emerging Waves)

| Action | Rationale | Timeline |
|---|---|---|
| **Ship ModelCRDT (v0.8.0)** | LLM model merging is exploding. Dozens of papers, no formal framework. Being the first to unify TIES/DARE/SLERP under CRDT algebra is a landmark contribution. | Medium-term |
| **Ship UnmergeEngine (v0.9.0)** | GDPR right-to-erasure + EU AI Act. Nobody else offers reversible CRDT merge. Regulatory tailwind is strong and growing. | Medium-term |

#### Tier 4: Platform (Lock-in via Standards)

| Action | Rationale | Timeline |
|---|---|---|
| **Rust protocol engine + FFI (v1.0.0)** | Single high-performance core with wrappers for every language. Becomes the reference implementation, not just a Python library. | Long-term |
| **Propose merge schema as a standard** | If MergeSchema becomes a recognized format (like JSON Schema or Apache Arrow), crdt-merge becomes the reference implementation of a standard, not just a library. | Long-term |

### 8.3 What NOT To Do

| Temptation | Why Resist |
|---|---|
| Add real-time sync | Yjs/Loro/Automerge own this. Different architecture. |
| Build a database | That's a product, not a library. Keep the core pure. |
| Add networking | Ditto has $82M and BLE/WiFi/P2P. Not our fight. |
| Chase stars with flashy demos | Stars don't equal adoption. Focus on being genuinely useful in production pipelines. |
| Compete on raw join performance | Polars and DuckDB will always be faster at simple joins. Compete on **what they can't do**: per-field strategies, provenance, verification. |

### 8.4 Competitive Moat Assessment

| Moat | Strength | Durability |
|---|---|---|
| **Per-field merge strategies** | 🔥 Strong — nobody else has this | High — requires deep CRDT knowledge to replicate |
| **CRDT verification** | 🔥 Strong — unique in the market | High — formal methods expertise required |
| **Provenance tracking** | 🔥 Strong — unique for merge tools | Medium — conceptually simple, execution matters |
| **Zero dependencies** | Medium — nice but not a moat | Low — easy to replicate |
| **Multi-language** | Medium — 4 ports is good | Medium — maintenance burden, but wide reach |
| **MergeQL (roadmap)** | 🔥 Very strong if first to implement CRDV | High — first-mover + DuckDB integration |
| **ModelCRDT (roadmap)** | 🔥 Very strong if first to formalize | Medium — AI moves fast, window is open now |
| **UnmergeEngine (roadmap)** | 🔥 Strong — regulatory moat | High — compliance requirements only grow |

---

## 9. Conclusion

crdt-merge sits in a genuinely uncontested niche. The competitive landscape is active and well-funded across adjacent categories — real-time CRDTs, CRDT databases, local-first sync, data lakehouses — but **none of them solve batch dataset merge with per-field CRDT strategies**.

The real competition is the status quo: `pandas.merge()` with no conflict resolution, ad-hoc scripts that nobody trusts, and manual reconciliation that doesn't scale. This is the best competitive position a new library can have — the alternative isn't a better product, it's doing the work by hand.

The roadmap is strategically sound. Arrow-native performance (v0.6.0) and schema evolution make crdt-merge production-ready. MergeQL (v0.7.0) democratizes access. ModelCRDT (v0.8.0) captures a wave. UnmergeEngine (v0.9.0) creates regulatory moat. The v1.0 platform cements multi-language leadership.

**The window is open.** The CRDV paper defined the theory; nobody built the library. Model merging is exploding; nobody formalized it under CRDTs. GDPR enforcement is tightening; nobody offers reversible merge. crdt-merge can be the standard if it executes on this roadmap.

---

*Generated March 28, 2026. Data sourced from GitHub API, academic databases, and industry analysis.*
