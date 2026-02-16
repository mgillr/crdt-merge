# CRDT-Mapping_Docs — crdt-merge v0.9.3

> **Architecture docs, API reference, and developer guides for the crdt-merge library** — a production-grade framework for conflict-free replicated data type (CRDT) based merging across data, ML models, and distributed systems.

| | |
|---|---|
| **Version** | 0.9.3 |
| **Architecture** | 6-layer + Accelerators + CLI |
| **Codebase** | 32,787 LOC · 78 modules · 201 classes · 289 functions |
| **License** | BUSL-1.1 |

---

## 🗺️ Learning Path

New to crdt-merge? Follow this guided path from zero to production.

### Step 1: Getting Started (15 min)

→ [Installation Guide](docs/getting-started/INSTALLATION.md) — Install crdt-merge and optional extras  
→ [Quickstart](docs/getting-started/QUICKSTART.md) — Your first merge in 5 minutes  
→ [Core Concepts](docs/getting-started/CONCEPTS.md) — CRDTs, strategies, schemas

### Step 2: Practical Recipes (30 min)

→ [Merge Cookbook](docs/cookbook/) — Ready-to-use patterns  
→ [Model Merging](docs/cookbook/model-merging.md) — All 26 ML merge strategies  
→ [Accelerators](docs/cookbook/accelerators.md) — DuckDB, dbt, Polars, Airbyte, and more

### Step 3: Production Deployment (1 hr)

→ [Security Guide](docs/guides/security-guide.md) — Encryption, RBAC, audit trails  
→ [Schema Evolution](docs/guides/schema-evolution.md) — Handle schema changes safely  
→ [Observability](docs/guides/observability-guide.md) — Metrics, tracing, health checks

### Step 4: Advanced Topics

→ [API Reference](api-reference/) — Complete API docs for all 6 layers  
→ [Architecture](architecture/OVERVIEW.md) — System design and decisions  
→ [Contributing](docs/development/CONTRIBUTING.md) — Join development

---

## 🔍 Quick Reference

| I want to... | Go here |
|---|---|
| Merge two DataFrames | [Quickstart](docs/getting-started/QUICKSTART.md) |
| Merge ML model weights | [Model Merging Cookbook](docs/cookbook/model-merging.md) |
| Add encryption to merges | [Security Guide](docs/guides/security-guide.md) |
| Set up audit trails | [Security Guide](docs/guides/security-guide.md#audit-trails) |
| Use with DuckDB/dbt/Polars | [Accelerators Cookbook](docs/cookbook/accelerators.md) |
| Handle GDPR compliance | [Compliance API](api-reference/layer6-compliance/compliance.md) |
| Understand the architecture | [Architecture Overview](architecture/OVERVIEW.md) |

---

## ⚡ 30-Second Demo

```python
import pandas as pd
from crdt_merge import merge, MergeSchema, LWW, MaxWins

df_a = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Charlie"], "score": [80, 70], "_ts": [1000.0, 1000.0]})
df_b = pd.DataFrame({"id": [1, 3], "name": ["Bob", "Diana"],    "score": [90, 85], "_ts": [2000.0, 1000.0]})

schema = MergeSchema(name=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="_ts")
print(result)
#    id   name  score      _ts
# 0   1    Bob     90   2000.0  ← Bob (newer), 90 (higher)
# 1   2  Charlie   70   1000.0  ← Only in df_a
# 2   3  Diana     85   1000.0  ← Only in df_b
```

---

## 📂 Repository Layout

```
CRDT-Mapping_Docs/
├── architecture/           ← System overview, layer map, data flow, design decisions
├── api-reference/          ← Complete API reference (layers 1–6, accelerators, CLI)
├── docs/
│   ├── getting-started/    ← Installation, quickstart, core concepts
│   ├── cookbook/            ← Practical recipes and patterns
│   ├── guides/             ← Security, schema evolution, observability, and more
│   ├── explanations/       ← Theory and design rationale
│   └── development/        ← Contributing, testing, changelog
├── gap-analysis/           ← Inventory vs actual, missing docs, bugs, recommendations
├── variables-and-functions/← Exhaustive export/class/function/constant listings
├── status/                 ← Build progress, review log, sign-off tracker
└── .sop/                   ← Standard Operating Procedures
```

---

## ✅ Documentation Status

| Section | Status |
|---------|--------|
| Architecture Map | ✅ Complete |
| API Reference (Layers 1–6) | ✅ Complete |
| Cookbook & Guides | ✅ Complete |
| Gap Analysis | ✅ Complete |
| Variables & Functions | ✅ Complete |
| SOPs & Status Tracking | ✅ Complete |

---

## By Role

- **Developers** — Start with the [Learning Path](#️-learning-path) above
- **Architects** — Read [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md), then explore [architecture/](architecture/)
- **API Consumers** — Browse [api-reference/](api-reference/) organized by layer
- **Contributors** — See [Contributing](docs/development/CONTRIBUTING.md) and [gap-analysis/](gap-analysis/)

---

> **Note:** The original codebase inventory reports 38,157 LOC vs. our AST-measured 32,787 LOC. The ~5,370 LOC difference is documented in [gap-analysis/INVENTORY_VS_ACTUAL.md](gap-analysis/INVENTORY_VS_ACTUAL.md).

---

*Generated: March 2026 | crdt-merge v0.9.3 | Documentation Build v1.0*
