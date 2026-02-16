# Dependency Graph

## High-Level Layer Dependencies

```
Layer 6 (Compliance) ──────► Layer 5 (Enterprise) + Layer 4 (AI)
Layer 5 (Enterprise) ──────► Layer 4 (AI) + Layer 2 (Engines) + Layer 1 (Core)
Layer 4 (AI/Model)   ──────► Layer 3 (Transport) + Layer 2 (Engines) + Layer 1 (Core)
Layer 3 (Transport)  ──────► Layer 2 (Engines) + Layer 1 (Core)
Layer 2 (Engines)    ──────► Layer 1 (Core)
Layer 1 (Core)       ──────► Python stdlib only

Accelerators         ──────► Layer 2 (Engines) + Layer 1 (Core)
CLI                  ──────► All layers (for migration)
```

## Facade Note: `__init__.py`

> `crdt_merge/__init__.py` imports from **all 6 layers** to provide a flat public API (e.g., `from crdt_merge import merge, ArrowMerge, AuditLog`). This is the **package facade pattern** — it is expected behavior, NOT a layer violation. The GDEPA analysis flagged 19 "violations" from `__init__` which are all facade imports.

## Module-Level Dependencies (Layer 1)

```
core.py          → stdlib (copy, time, uuid)
strategies.py    → core.py (LWW depends on timestamp handling)
clocks.py        → stdlib only
probabilistic.py → stdlib (hashlib, struct, math)
dedup.py         → core.py, strategies.py
provenance.py    → core.py, strategies.py
verify.py        → core.py, strategies.py, clocks.py
```

## Module-Level Dependencies (Layer 2)

```
dataframe.py      → strategies.py, schema_evolution.py, pandas (optional), polars (optional)
streaming.py      → strategies.py
arrow.py          → strategies.py, schema_evolution.py, pyarrow
parquet.py        → arrow.py, strategies.py, pyarrow
parallel.py       → dataframe.py, strategies.py, multiprocessing
async_merge.py    → dataframe.py, strategies.py, asyncio
json_merge.py     → strategies.py
_polars_engine.py → strategies.py, polars
```

### Layer 2 → Layer 1 Dependency Details (AST-verified 2026-03-31)

Layer 2 depends on exactly **2 Layer 1 modules**:
- **`crdt_merge.strategies`**: All 8 Layer 2 modules import `MergeStrategy`, `MergeSchema`, and individual strategies (LWW, MaxWins, etc.) for conflict resolution dispatch
- **`crdt_merge.schema_evolution`**: `dataframe.py` and `arrow.py` import schema evolution utilities for handling schema drift between merge inputs

> Note: Previous documentation listed `core.py` as a direct dependency for several Layer 2 modules. AST analysis shows they import strategies (which itself depends on core), not core directly. The dependency is transitive, not direct.

## Module-Level Dependencies (Layer 3)

```
wire.py              → core.py, strategies.py, struct, msgpack (optional)
merkle.py            → core.py, hashlib
gossip.py            → merkle.py, wire.py, core.py
delta.py             → core.py, wire.py
schema_evolution.py  → strategies.py, core.py
```

## External Dependencies

| Package | Required | Used By |
|---------|----------|---------|
| `pandas` | Optional | dataframe.py, parallel.py |
| `polars` | Optional | _polars_engine.py, dataframe.py |
| `pyarrow` | Optional | arrow.py, parquet.py |
| `torch` | Optional | model/ (all model merge modules) |
| `transformers` | Optional | model/, hub/ |
| `cryptography` | Optional | encryption.py |
| `prometheus_client` | Optional | observability.py |
| `duckdb` | Optional | accelerators/duckdb_udf.py |
| `streamlit` | Optional | accelerators/streamlit_ui.py |
| `flower` | Optional | flower_plugin.py |

---

*Dependency Graph v1.0*
