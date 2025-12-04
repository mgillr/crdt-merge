# crdt-merge: Updated Roadmap with Unicorn Innovations
## v0.5.1 → v1.0.0 — Features Integrated from Forensic Analysis

**Author:** Optitransfer AG Strategy
**Date:** 2026-03-28
**Source:** Forensic Reality Check + Three-Tier Innovation Synthesis
**Constraint:** ALL changes ADDITIVE ONLY — zero breaking changes to existing API

---

## Quick Reference: Where Each Unicorn Feature Lives

| # | Feature | Lines | Release | Rationale |
|---|---------|-------|---------|-----------|
| **0** | **Fix merge() + MergeSchema** | ~20 | **v0.5.1 HOTFIX** | The flagship function ignores the flagship feature. Ship immediately. |
| **1** | **Arrow-native merge** | ~800 | **v0.6.0** | 10-50× speedup required BEFORE distributed scaling makes sense |
| **2** | **Schema evolution** | ~300 | **v0.6.0** | Real datasets NEVER have identical schemas. Must fix before distributed sync |
| **3** | **MergeQL (DuckDB SQL)** | ~500 | **v0.7.0** | SQL interface IS an integration — every data warehouse user becomes a customer |
| **4** | **UnmergeEngine** | ~400 | **v0.9.0** | Reversible CRDT merge for GDPR erasure. Perfect fit for Enterprise compliance story |
| **5** | **ModelCRDT** | ~700 | **v0.8.0** | AI model merging (TIES/DARE/SLERP) as CRDT operations. Universal access for AI wave |

---

## v0.5.1 — "The Hotfix Release" 🔧

**Theme:** Fix embarrassing API gaps and critical bugs before any new feature work
**Release timing:** IMMEDIATE (< 1 week)
**Zero breaking changes:** All fixes are additive validation + parameter additions

### 🦄 Unicorn Feature #0: `merge()` Accepts MergeSchema

The per-field strategy DSL is our category-defining innovation. The flagship `merge()` function doesn't support it. This is 20 lines:

```python
# BEFORE (v0.5.0) — merge() only supports prefer="a"/"b"/"latest"
result = merge(df_a, df_b, key="id", prefer="latest")

# AFTER (v0.5.1) — merge() now accepts schema for per-field strategies
from crdt_merge.strategies import MergeSchema, MaxWins, LWW, UnionSet

schema = MergeSchema(
    default=LWW(),
    score=MaxWins(),
    tags=UnionSet()
)
result = merge(df_a, df_b, key="id", schema=schema)
```

**Implementation:**
```python
def merge(df_a, df_b, key=None, timestamp_col=None, prefer="latest",
          dedup=True, fuzzy_dedup=False, fuzzy_threshold=0.85,
          schema=None):  # ← NEW PARAMETER
    """
    If schema is provided, it takes precedence over prefer.
    Uses merge_with_provenance() internally for schema-based resolution,
    then converts back to DataFrame.
    """
    if schema is not None:
        from crdt_merge.provenance import merge_with_provenance
        merged, _ = merge_with_provenance(df_a, df_b, key=key, schema=schema)
        if isinstance(df_a, pd.DataFrame):
            return pd.DataFrame(merged)
        return merged
    # ... existing logic unchanged
```

### Critical Bug Fixes (from Doc Team Audit)

| Bug | Fix | Lines |
|-----|-----|-------|
| **#1**: `merge()` silently returns empty DataFrame with non-existent key | Add `KeyError` validation | ~5 |
| **#2**: `merge()` silently accepts invalid `prefer` values | Add `ValueError` validation | ~3 |
| **#5**: `merge_dicts()` doesn't treat None as missing | Align with `merge()`/`merge_with_provenance()` behavior | ~8 |
| **#10**: No `__all__` in any module | Add `__all__` to all 13 modules | ~50 |

### Test Impact
- **~15 new tests** for validation, schema parameter, None handling
- **Total: ~438 tests**

### Lines Impact: 3,790 → ~3,880 (trivial)

---

## v0.6.0 — "The Distributed Release" 🌐

**Codename:** Network
**Theme:** Performance foundation + distributed scaling
**What's NEW from unicorn analysis:** Arrow-native engine + schema evolution

### 🦄 Unicorn Feature #1: Arrow-Native Merge Engine

**The problem:** Currently, every merge converts DataFrames to Python dicts, iterates in Python, then converts back. This is criminally slow for large datasets.

**The solution:** New `crdt_merge.arrow` module that operates directly on Apache Arrow columnar memory:

```python
from crdt_merge.arrow import merge_arrow, ArrowMergeConfig

import pyarrow as pa

table_a = pa.table({"id": [1, 2, 3], "score": [80, 90, 70]})
table_b = pa.table({"id": [1, 2, 4], "score": [85, 88, 95]})

# Zero-copy columnar merge — stays in Arrow memory
result = merge_arrow(table_a, table_b, key="id", schema=my_schema)

# Native Polars integration
import polars as pl
df_a = pl.DataFrame({"id": [1, 2], "score": [80, 90]})
df_b = pl.DataFrame({"id": [1, 2], "score": [85, 88]})
result = merge_arrow(df_a.to_arrow(), df_b.to_arrow(), key="id", schema=my_schema)
merged_polars = pl.from_arrow(result)

# DuckDB direct table merge (feeds into MergeQL in v0.7.0)
import duckdb
conn = duckdb.connect()
conn.register("table_a", table_a)
conn.register("table_b", table_b)
```

**Why v0.6.0:** Distributed scaling without performance is pointless. Arrow-native merge makes gossip sync 10-50× faster. It also enables MergeQL in v0.7.0 (DuckDB speaks Arrow natively).

**Architecture:**
- New optional dependency: `pyarrow` (not required — existing dict-based merge untouched)
- `merge_arrow()` — top-level function for Arrow tables
- Internal: columnar hash join + strategy application without row-by-row Python iteration
- Falls through to existing merge logic for custom strategies that need Python callables

**Lines:** ~800
**Tests:** ~60 (merge correctness on Arrow, roundtrip conversions, Polars interop, performance regression)

### 🦄 Unicorn Feature #2: Schema Evolution During Merge

**The problem:** Real-world datasets NEVER have identical schemas. Source A has 12 columns, Source B has 15. Column names change. Types drift. Currently, merge silently drops or fails on mismatched schemas.

**The solution:** New `crdt_merge.evolution` module:

```python
from crdt_merge.evolution import EvolvingMerge, SchemaPolicy

policy = SchemaPolicy(
    missing_columns="fill_null",     # or "drop", "error"
    type_conflicts="coerce_wider",   # int → float, str stays str
    renamed_columns={"user_name": "name", "amt": "amount"},
    extra_columns="keep",            # or "drop"
)

result = EvolvingMerge(
    df_a,       # has: id, name, score, email
    df_b,       # has: id, user_name, score, phone, created_at
    key="id",
    schema=my_schema,
    evolution=policy
)
# Result has: id, name, score, email, phone, created_at
# "user_name" was renamed to "name" per policy
# "email" (only in A) filled with null for B-only rows
```

**Why v0.6.0:** Before distributed gossip sync, nodes MUST handle schema drift. In a mesh of 10 nodes evolving independently, schema evolution isn't optional — it's prerequisite infrastructure.

**Architecture:**
- New module `crdt_merge.evolution` (~300 lines)
- `SchemaPolicy` dataclass with configurable behaviors
- `EvolvingMerge()` wrapper that reconciles schemas before passing to core merge
- Integrates with `merge()`, `merge_stream()`, `merge_with_provenance()`
- Does NOT change core merge semantics — it normalizes inputs BEFORE merge

**Lines:** ~300
**Tests:** ~40 (type coercion, missing columns, renames, error cases)

### Existing v0.6.0 Features (Unchanged)

| Feature | Module | Lines |
|---------|--------|-------|
| Gossip protocol | `crdt_merge.gossip` | ~400 |
| Vector clocks | `crdt_merge.vector_clock` | ~200 |
| Merkle anti-entropy | `crdt_merge.antientropy` | ~400 |

### Updated Totals for v0.6.0

| Metric | Original Plan | With Unicorns |
|--------|--------------|---------------|
| **New lines** | ~1,010 | **~2,110** |
| **Total lines** | ~4,800 | **~5,900** |
| **New tests** | ~200 | **~300** |
| **Total tests** | ~620 | **~738** |
| **New modules** | 3 | **5** (+ arrow, evolution) |

---

## v0.7.0 — "The Integration Release" 🔌

**Codename:** Ecosystem
**Theme:** Connect crdt-merge to every tool in the modern data stack + SQL access
**What's NEW from unicorn analysis:** MergeQL (DuckDB SQL operator)

### 🦄 Unicorn Feature #3: MergeQL — CRDT Merge as a SQL Operator

**The problem:** Every data analyst knows SQL. None of them will learn a Python API to merge datasets. Putting CRDT merge in SQL opens the entire data warehouse universe.

**The solution:** DuckDB extension that exposes crdt-merge as SQL functions:

```sql
-- Install the crdt-merge DuckDB extension
INSTALL crdt_merge FROM 'https://crdt-merge.dev/duckdb';
LOAD crdt_merge;

-- Simple merge — LWW by default
SELECT * FROM crdt_merge('source_a', 'source_b', key := 'id');

-- Per-field strategy via SQL syntax
SELECT * FROM crdt_merge(
    'source_a', 'source_b',
    key := 'id',
    strategies := {
        'score': 'max_wins',
        'tags': 'union_set',
        'name': 'lww'
    }
);

-- With provenance — every merge decision logged
SELECT merged.*, prov.strategy_used, prov.winner
FROM crdt_merge_with_provenance('source_a', 'source_b', key := 'id') 
    AS (merged, prov);

-- Works with any DuckDB data source
SELECT * FROM crdt_merge(
    read_parquet('s3://bucket/source_a/*.parquet'),
    read_parquet('s3://bucket/source_b/*.parquet'),
    key := 'id'
);
```

**Python API for DuckDB integration:**

```python
from crdt_merge.mergeql import register_functions

import duckdb
conn = duckdb.connect()
register_functions(conn)

result = conn.sql("""
    SELECT * FROM crdt_merge(
        'sales_eu', 'sales_us', 
        key := 'order_id',
        strategies := {'amount': 'max_wins', 'status': 'lww'}
    )
""").fetchdf()
```

**Why v0.7.0:** MergeQL is the ultimate integration — SQL is the universal data language. It also builds on Arrow-native merge from v0.6.0 (DuckDB uses Arrow internally).

**Architecture:**
- New module `crdt_merge.mergeql` (~300 lines Python wrapper)
- DuckDB UDF registration using `duckdb.create_function()`
- Leverages Arrow-native merge (v0.6.0) — DuckDB ↔ Arrow is zero-copy
- Optional: native DuckDB extension in C++ (~200 lines) for standalone usage

**Lines:** ~500
**Tests:** ~40 (SQL syntax, strategies, Parquet roundtrip, provenance in SQL)

### Existing v0.7.0 Features (Unchanged)

| Package | What It Does |
|---------|-------------|
| `crdt-merge-server` | HTTP/gRPC CRDT sync microservice |
| `crdt-merge-kafka` | Kafka Streams merge operator |
| `crdt-merge-flink` | Flink ProcessFunction |
| `crdt-merge-dbt` | dbt custom materialization |
| `crdt-merge-airflow` | Airflow/Dagster operator |
| `crdt-merge-langchain` | LangChain/LlamaIndex tool |

### Updated Totals for v0.7.0

| Metric | Original Plan | With Unicorns |
|--------|--------------|---------------|
| **New lines** | ~1,700 | **~2,200** |
| **Total lines** | ~6,500 | **~8,100** |
| **New tests** | ~300 | **~340** |
| **Total tests** | ~920 | **~1,078** |

---

## v0.8.0 — "The Polyglot Release" 🌍

**Codename:** Universal
**Theme:** Protocol engine + universal language access + AI model merging
**What's NEW from unicorn analysis:** ModelCRDT

### 🦄 Unicorn Feature #5: ModelCRDT — AI Model Merging as CRDT Operations

**The problem:** The AI community already does model merging (TIES, DARE, SLERP, Task Arithmetic). They do it with ad-hoc scripts. The algebra is already commutative and associative — it's already a CRDT, they just don't know it.

**The solution:** New `crdt_merge.model_crdt` module:

```python
from crdt_merge.model_crdt import (
    ModelCRDT, TIESMerge, DAREMerge, SLERPMerge, TaskArithmetic, FisherMerge,
)

base_model = ModelCRDT.from_safetensors("base-llama-7b/")
finetune_a = ModelCRDT.from_safetensors("finetune-medical/")
finetune_b = ModelCRDT.from_safetensors("finetune-legal/")

# TIES merge — trim redundant params, elect signs, merge
merged = ModelCRDT.merge(
    base_model, finetune_a, finetune_b,
    strategy=TIESMerge(density=0.5, majority_sign=True)
)
merged.save_safetensors("merged-model/")

# The CRDT guarantee: order doesn't matter
merged_abc = merge(merge(a, b), c)
merged_bca = merge(merge(b, c), a)
assert merged_abc == merged_bca  # Commutativity + Associativity

# Per-layer merge strategy
schema = MergeSchema(
    default=TIESMerge(),
    attention_layers=SLERPMerge(t=0.5),
    lm_head=TaskArithmetic(scaling=0.7)
)
result = ModelCRDT.merge(base, ft_a, ft_b, schema=schema)
```

**Why v0.8.0:** ModelCRDT makes crdt-merge speak the AI language. Model merging is already algebraic — formalizing it as CRDTs is inevitable.

**Architecture:**
- New module `crdt_merge.model_crdt` (~700 lines)
- Optional dependencies: `safetensors`, `torch` (lazy imports)
- CRDT operations on model weight tensors
- Integrates with verification: `verify_crdt(my_model_merge)` proves commutativity

**Lines:** ~700
**Tests:** ~50

### Existing v0.8.0 Features (Unchanged)

| Feature | What It Does |
|---------|-------------|
| Rust protocol engine | Wire format + merge semantics in ~1,000 lines |
| FFI wrappers (14 languages) | Go, C#, Swift, Ruby, PHP, Dart, etc. |
| WASM build | Browser, Node, Deno, Cloudflare Workers |

### Updated Totals for v0.8.0

| Metric | Original Plan | With Unicorns |
|--------|--------------|---------------|
| **New lines (Python)** | ~1,500 | **~2,200** |
| **Total lines (Python)** | ~8,000 | **~10,300** |
| **New tests** | ~800 | **~850** |
| **Total tests** | ~1,700 | **~1,928** |

---

## v0.9.0 — "The Enterprise Release" 🏢

**Codename:** Trust
**Theme:** Security, compliance, observability + reversible merge
**What's NEW from unicorn analysis:** UnmergeEngine

### 🦄 Unicorn Feature #4: UnmergeEngine — Reversible CRDT Merge

**The problem:** GDPR Article 17 says "right to erasure." CRDTs are designed to be merge-only — you can never un-merge. This is a mathematical paradox. Everyone just says "rebuild from scratch." That's O(n) over all history.

**The solution:** Reversible merge through cryptographic tombstoning:

```python
from crdt_merge.unmerge import UnmergeEngine, UnmergePolicy

engine = UnmergeEngine(
    storage="postgresql://localhost/crdt_audit",
    policy=UnmergePolicy(
        preserve_aggregate_stats=True,
        tombstone_strategy="crypto",
        cascade=True,
    )
)

# Normal merge — engine tracks lineage
result = engine.merge(df_a, df_b, key="id", schema=my_schema)

# GDPR erasure request
erasure = engine.unmerge(
    user_id="user_123",
    scope="all",
    reason="GDPR Article 17 request",
)

print(erasure.certificate)
# {
#   "user_id": "user_123",
#   "records_affected": 47,
#   "merges_recomputed": 12,
#   "cryptographic_proof": "sha256:a1b2c3...",
#   "compliant_with": ["GDPR Art.17", "CCPA §1798.105"]
# }

assert engine.verify_erasure("user_123")  # True
```

**Why v0.9.0:** UnmergeEngine IS the compliance story. Without it, CRDTs can never be GDPR-compliant.

**Architecture:**
- New module `crdt_merge.unmerge` (~400 lines)
- Integrates with provenance system — lineage tracking already exists
- Tombstone IS a valid CRDT state (the "zero element")

**Lines:** ~400
**Tests:** ~30

### Existing v0.9.0 Features (Unchanged)

| Module | What It Does |
|--------|-------------|
| `crdt_merge.encryption` | E2E encryption for wire format |
| `crdt_merge.rbac` | Role-based merge permissions |
| `crdt_merge.observability` | OpenTelemetry instrumentation |
| `crdt_merge.compliance` | GDPR/SOX/HIPAA audit toolkit |

### Updated Totals for v0.9.0

| Metric | Original Plan | With Unicorns |
|--------|--------------|---------------|
| **New lines** | ~1,000 | **~1,400** |
| **Total lines** | ~9,000 | **~11,700** |
| **Total tests** | ~2,000 | **~2,258** |

---

## v1.0.0 — "The Platform Release" 🚀

**No new unicorn features.** Stabilization: API freeze, security audit, formal spec, full docs.

---

## Updated Evolution Summary

| Version | Codename | Theme | 🦄 Unicorn Additions | Lines | Tests |
|---------|----------|-------|----------------------|-------|-------|
| **v0.5.1** | 🔧 Hotfix | **Fix** | **merge()+MergeSchema, critical bug fixes** | ~3,880 | ~438 |
| **v0.6.0** | 🌐 Distributed | **Scaling** | **Arrow-native merge, Schema evolution** | ~5,900 | ~738 |
| **v0.7.0** | 🔌 Integration | **Ecosystem** | **MergeQL (DuckDB SQL)** | ~8,100 | ~1,078 |
| **v0.8.0** | 🌍 Polyglot | **Universal** | **ModelCRDT (AI model merge)** | ~10,300 | ~1,928 |
| **v0.9.0** | 🏢 Enterprise | **Trust** | **UnmergeEngine (reversible merge)** | ~11,700 | ~2,258 |
| **v1.0.0** | 🚀 Platform | **Definitive** | — | ~12,000 | ~2,300 |

## The Unicorn Cascade (Build Order)

```
Week 0:     v0.5.1 — merge()+MergeSchema + critical fixes (ship in 3 days)
Weeks 1-3:  v0.6.0 — Arrow-native merge (the performance foundation)
Weeks 3-5:  v0.6.0 — Schema evolution (the compatibility foundation)
Weeks 5-8:  v0.6.0 — Gossip + vector clocks + Merkle (distributed)
Weeks 8-10: v0.7.0 — MergeQL (DuckDB SQL — uses Arrow internally)
Weeks 10-16:v0.7.0 — Integration packages (Kafka, Flink, dbt, etc.)
Weeks 16-22:v0.8.0 — Protocol engine + FFI wrappers
Weeks 22-25:v0.8.0 — ModelCRDT (AI model merging)
Weeks 25-30:v0.9.0 — Encryption + RBAC + UnmergeEngine
Weeks 30-36:v1.0.0 — API freeze, spec, security audit, docs
```

**Total new code from unicorn features: ~2,720 lines, ~235 tests**

---

*Copyright 2026 Ryan Gillespie — Optitransfer AG*
*Contact: rgillespie83@icloud.com, data@optitransfer.ch*
