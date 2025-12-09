# crdt-merge Roadmap: v0.5.1 → v1.0.0

**Author:** Optitransfer AG Strategy
**Date:** 2026-03-28
**Source:** Forensic Reality Check + Competitive Intelligence + Gap Reconciliation
**Constraint:** ALL changes ADDITIVE ONLY — zero breaking changes to existing API

---

## Design Principle

crdt-merge is a **library**, not a database. Every feature must be:
- **Algorithmic** — pure computation on data structures, no persistence backends
- **Zero required dependencies** — optional deps (pyarrow, numpy, duckdb) for extensions
- **Additive only** — existing tests must always pass, existing API never changes

Features that require persistence, networking, or database semantics belong in products built on top of crdt-merge.

---

## Quick Reference: Feature → Release

| # | Feature | Lines | Release | Category |
|---|---------|-------|---------|----------|
| 0 | Fix merge() + MergeSchema | ~20 | **v0.5.1** ✅ DONE | Bug fix |
| 0 | 24 defect fixes (Master Defect Register) | ~224 | **v0.5.1** ✅ DONE | Quality |
| 1 | Arrow-native merge engine | ~800 | **v0.6.0** | Performance |
| 2 | Schema evolution (column map + type coerce) | ~300 | **v0.6.0** | Usability |
| — | Async merge wrappers | ~200 | **v0.6.0** | Performance |
| — | Multi-key merge (composite keys) | ~50 | **v0.6.0** | Usability |
| — | JSON merge with MergeSchema | ~80 | **v0.6.0** | Consistency |
| 3 | MergeQL — CRDT merge as DuckDB SQL | ~500 | **v0.7.0** | Accessibility |
| — | Self-merging Parquet files | ~300 | **v0.7.0** | Integration |
| 4 | ModelCRDT — AI model merging | ~700 | **v0.8.0** | Innovation |
| — | Conflict topology visualization | ~300 | **v0.8.0** | DX |
| 5 | UnmergeEngine — reversible CRDT merge | ~400 | **v0.9.0** | Compliance |
| — | Parallel merge (multiprocessing) | ~300 | **v0.9.0** | Performance |

### Explicitly Out of Scope

| Feature | Rationale |
|---------|-----------|
| Persistent DeltaStore (SQLite/Redis/S3 backends) | Persistence = database. Use `to_dict()`/`from_dict()` to serialize externally. |
| Real-time sync / networking | Library provides wire format. Transport belongs in the application. |
| Full history / time travel | Provenance covers single-merge lineage. Version chains = database feature. |
| Rich text collaboration | Different niche (Loro, Automerge). We do batch structured data. |
| Tree/graph CRDTs | Document-level CRDTs for collaborative editing. Not our space. |

---

## v0.5.1 — "The Hotfix Release" ✅ COMPLETE

**Status:** All fixes on `main`. Ready for PyPI release.
**Changes:** 24 defect fixes, ~224 lines changed across 13 modules, 425 tests (422 pass, 2 skip).

### Ship-Blockers Fixed

| ID | Fix | Impact |
|----|-----|--------|
| DEF-001 | `merge()` raises `KeyError` when key column doesn't exist | Prevents silent empty results |
| DEF-002 | `merge()` raises `ValueError` for invalid `prefer` values | Prevents silent B-wins fallback |
| DEF-003 | `merge()` now accepts `schema=MergeSchema(...)` parameter | Flagship function uses flagship feature |
| DEF-004 | `merge_dicts()` treats `None` values as missing | Consistent None handling across all merge functions |
| DEF-005 | `__all__` defined in all 13 modules | Clean wildcard imports |

### API Consistency Fixed

| ID | Fix |
|----|-----|
| DEF-006 | `merge_with_provenance()` now accepts `as_dataframe=True` for DataFrame output |
| DEF-007 | `compose_deltas()` raises `TypeError` if passed a list instead of variadic args |
| DEF-008 | `merge_sorted_stream()` now accepts `verify_order=True` to validate sort order |
| DEF-009 | `merge_stream()` now accepts `prefer=` parameter as sugar for simple cases |
| DEF-010 | `MergeSchema.from_dict()` no longer mutates its input dictionary |
| DEF-011 | `Custom` strategy raises `ValueError` on deserialization instead of silently becoming LWW |

### Documentation & Edge Cases

DEF-012 through DEF-024: Type guards for `datasets_ext`, docstring corrections, CRDT property documentation, edge case documentation, wire format + MergeSchema docs.

---

## v0.6.0 — "The Performance Release"

**Theme:** Make crdt-merge production-ready for large-scale data pipelines.
**Estimated lines:** ~1,430

### Arrow-Native Merge Engine (~800 lines)

**The problem:** Currently, every merge converts DataFrames to Python dicts, iterates in Python, then converts back. For 1M rows, this creates 1M Python dicts.

**The solution:** New `crdt_merge.arrow` module that operates directly on Apache Arrow columnar memory:

```python
from crdt_merge.arrow import merge_arrow

import pyarrow as pa

table_a = pa.table({"id": [1, 2, 3], "score": [80, 90, 70]})
table_b = pa.table({"id": [1, 2, 4], "score": [85, 88, 95]})

# Zero-copy columnar merge — stays in Arrow memory
result = merge_arrow(table_a, table_b, key="id", schema=my_schema)

# Native Polars integration
import polars as pl
merged_polars = pl.from_arrow(result)
```

**Expected speedup:** 10-50× over dict-based path. pyarrow as optional dependency.

**Why nobody's done it:** CRDT libraries think in documents. Data libraries think in SQL joins. crdt-merge bridges the gap.

### Schema Evolution (~300 lines)

**The problem:** Real datasets almost never have identical schemas. Renamed columns, new columns, type changes — every merge tool either fails or silently produces garbage.

```python
schema = MergeSchema(
    default=LWW(),
    column_map={"name": "full_name"},       # Column aliases
    type_coerce={"price": float},            # Automatic type coercion
    ignore_extra=True,                       # Don't fail on unknown columns
)

result = merge(df_a, df_b, key="id", schema=schema)
```

### Additional Features

| Feature | Lines | Description |
|---------|-------|-------------|
| Async merge wrappers | ~200 | `async merge_stream()` for asyncio pipelines |
| Multi-key merge | ~50 | `key=("tenant_id", "record_id")` — composite key support |
| JSON merge + strategies | ~80 | `merge_dicts()` accepts MergeSchema for per-field resolution |

---

## v0.7.0 — "The SQL Release"

**Theme:** Make CRDT merge accessible to every SQL user.
**Estimated lines:** ~800

### MergeQL — CRDT Merge as SQL (~500 lines)

DuckDB UDF that exposes CRDT merge semantics via SQL:

```sql
SELECT * FROM crdt_merge(
    'table_a', 'table_b',
    key := 'id',
    strategies := '{"score": "MaxWins", "tags": "UnionSet"}'
);
```

**Why this matters:** SQL is the lingua franca. If crdt-merge is accessible via SQL, every data warehouse, BI tool, and pipeline can use it.

**Implementation:** Python UDF registered via DuckDB's `create_function()`. duckdb as optional dependency.

### Self-Merging Parquet Files (~300 lines)

Write MergeSchema as JSON into Parquet key-value metadata. Then:

```python
from crdt_merge.parquet import auto_merge

# Files contain their own merge instructions
result = auto_merge("dataset_a.parquet", "dataset_b.parquet")
```

Files become self-describing merge units. Drop two Parquet files into a folder → they merge themselves.

---

## v0.8.0 — "The AI Release"

**Theme:** Capture the model merging wave.
**Estimated lines:** ~1,000

### ModelCRDT — AI Model Merging (~700 lines)

Model merging techniques (TIES, DARE, SLERP, Task Arithmetic) ARE merge strategies applied to weight tensors. Nobody has unified them under CRDT algebra.

```python
from crdt_merge.models import ModelCRDT, TIES, DARE, SLERP

schema = MergeSchema(
    default=TIES(density=0.2),
    attention_layers=DARE(density=0.5),
    head=SLERP(t=0.5),
)

merged_weights = ModelCRDT.merge(model_a_weights, model_b_weights, schema=schema)
```

**Why CRDT people haven't done this:** They don't work on LLMs.
**Why LLM people haven't done this:** They don't know CRDTs exist.
**The intersection is empty. We fill it.**

numpy/torch as optional dependencies.

### Conflict Topology Visualization (~300 lines)

```python
from crdt_merge.analysis import conflict_map

# Analyze merge results visually
report = conflict_map(provenance_log)
report.heatmap()          # Conflict distribution by column
report.clusters()         # Conflict clusters by key range
report.strategy_stats()   # Strategy effectiveness metrics
```

Optional matplotlib/plotly dependency.

---

## v0.9.0 — "The Compliance Release"

**Theme:** GDPR compliance + production performance.
**Estimated lines:** ~700

### UnmergeEngine — Reversible CRDT Merge (~400 lines)

CRDT merges are assumed irreversible. But GDPR's right-to-erasure requires: "remove this person's data from every merged dataset."

```python
from crdt_merge.unmerge import unmerge

# Surgically remove one source's contribution using provenance
cleaned = unmerge(
    merged_result,
    source_to_remove=original_data_subject_records,
    provenance_log=log,
)
```

**Mathematically valid** for LWW, KeepBoth, UnionSet, MaxWins, MinWins. Raises for strategies where reversal is ambiguous.

**Impact:** GDPR compliance for merged datasets. Zero competitors offer this.

### Parallel Merge (~300 lines)

```python
from crdt_merge.parallel import parallel_merge

result = parallel_merge(
    chunks,
    workers=4,
    key="id",
    schema=my_schema,
)
```

multiprocessing.Pool for record-level parallelism. 4-8× speedup on multi-core machines.

---

## v1.0.0 — "The Platform Release"

**Theme:** API freeze, cross-language sync, production certification.

### What v1.0.0 means:
- **API freeze** — all public signatures locked, semver from here
- **Cross-language ports updated** — TypeScript, Rust, Java all at v1.0.0
- **Wire format v1** — frozen, backward-compatible forever
- **Full documentation** — user guide, API reference, tutorials
- **Production certification** — A100 stress test suite with published results
- **Rust protocol engine** — thin (~1,000 line) translator: wire format + merge semantics only

### The golden rule:
```
Python serialize → Rust deserialize → merge → serialize → Python deserialize
```
Must roundtrip perfectly. The Rust engine implements ONLY the protocol, not Python's features.

---

## Release Timeline

| Release | Status | Key Metric |
|---------|--------|-----------|
| v0.5.1 | ✅ On main | 24 defects fixed, 425 tests |
| v0.6.0 | Next | 10-50× performance, schema evolution |
| v0.7.0 | Planned | SQL accessibility |
| v0.8.0 | Planned | AI model merging |
| v0.9.0 | Planned | GDPR compliance |
| v1.0.0 | Target | API freeze + platform certification |

---

## Gap Reconciliation

For the full analysis of which features fit crdt-merge core vs. product territory, see [`docs/analysis/gap_reconciliation.md`](../analysis/gap_reconciliation.md).
