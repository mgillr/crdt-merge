# Dependency Graph

Import-level dependencies between modules, verified by AST analysis (2026-03-31).

---

## High-Level Layer Dependencies

```
Layer 6 (Compliance)   ── Layer 5 (Enterprise)
                       ── Layer 4 (AI/Model)  [for model unmerge]
                       ── Layer 1 (Core)       [for audit chain]

Layer 5 (Enterprise)   ── Layer 4 (AI/Model)  [for model unmerge]
                       ── Layer 2 (Engines)    [wraps merge()]
                       ── Layer 1 (Core)       [for CRDT primitives]

Layer 4 (AI/Model)     ── Layer 3 (Transport)  [wire, gossip]
                       ── Layer 2 (Engines)    [for data merge]
                       ── Layer 1 (Core)       [for CRDT primitives]

Layer 3 (Transport)    ── Layer 2 (Engines)
                       ── Layer 1 (Core)

Layer 2 (Engines)      ── Layer 1 (Core)       [strategies, schema_evolution]

Layer 1 (Core)         ── Python stdlib only
```


---

## Facade Note: `crdt_merge/__init__.py`

`crdt_merge/__init__.py` imports from **all 6 layers** to provide a flat public namespace. This is the **package facade pattern** — expected behavior, not layer violations.

```python
# These all work from the top-level import
from crdt_merge import (
    merge,               # Layer 2: dataframe.py
    GCounter,            # Layer 1: core.py
    AuditLog,            # Layer 5: audit.py
    ComplianceAuditor,   # Layer 6: compliance.py
    CRDTMergeState,      # Layer 4: model/crdt_state.py
    serialize,           # Layer 3: wire.py
)
```


---

## Layer 1 — Module-Level Dependencies

```
core.py          →  stdlib: copy, time, uuid
strategies.py    →  core.py (for timestamp handling)
                 →  stdlib: copy, time, warnings
clocks.py        →  stdlib only
probabilistic.py →  stdlib: hashlib, struct, math
dedup.py         →  core.py, strategies.py
provenance.py    →  core.py, strategies.py
verify.py        →  core.py, strategies.py, clocks.py
```

**Key finding**: Layer 2 does NOT import `core.py` directly. It imports `strategies.py` which transitively depends on `core.py`. The dependency chain is:

```
Layer 2  →  strategies.py  →  core.py
```

---

## Layer 2 — Module-Level Dependencies

```
dataframe.py      →  strategies.py         [MergeSchema, LWW, etc.]
                  →  schema_evolution.py   [schema drift handling]
                  →  pandas (optional)
                  →  polars (optional)

streaming.py      →  strategies.py
arrow.py          →  strategies.py
                  →  schema_evolution.py
                  →  pyarrow (required)
parquet.py        →  arrow.py
                  →  pyarrow (required)
parallel.py       →  dataframe.py
                  →  strategies.py
                  →  concurrent.futures (stdlib)
async_merge.py    →  dataframe.py
                  →  asyncio (stdlib)
json_merge.py     →  strategies.py
_polars_engine.py →  strategies.py
                  →  polars (required — internal only)
schema_evolution.py → strategies.py, core.py
```

---

## Layer 3 — Module-Level Dependencies

```
wire.py              →  core.py           [GCounter, PNCounter, etc.]
                     →  probabilistic.py  [HLL, Bloom, CMS serialization]
                     →  struct, zlib      (stdlib)
merkle.py            →  core.py
                     →  hashlib           (stdlib)
gossip.py            →  merkle.py
                     →  wire.py
                     →  core.py
delta.py             →  core.py
                     →  wire.py
```

---

## Layer 4 — Module-Level Dependencies (key modules)

```
model/crdt_state.py  →  core.py           [ORSet for contribution tracking]
                     →  wire.py           [state serialization]
                     →  hashlib           (stdlib)
model/core.py        →  model/strategies/ [all strategy modules]
                     →  model/safety.py
                     →  dataframe.py      [weight tensor operations]
model/federated.py   →  model/crdt_state.py
                     →  model/core.py
                     →  gossip.py
agentic.py           →  core.py           [ORSet for agent state]
                     →  strategies.py
mergeql.py           →  strategies.py
                     →  dataframe.py
context/merge.py     →  strategies.py
                     →  core.py
context/bloom.py     →  probabilistic.py  [MergeableBloom]
```

---

## Layer 5 — Module-Level Dependencies

```
encryption.py    →  strategies.py      [field-level strategy hooks]
                 →  cryptography       (required for aes/chacha backends)
rbac.py          →  strategies.py
                 →  core.py
audit.py         →  core.py
                 →  dataframe.py       [merge() calls inside AuditedMerge]
                 →  hashlib            (stdlib)
observability.py →  dataframe.py
                 →  time, threading    (stdlib)
                 →  prometheus_client  (optional)
                 →  opentelemetry      (optional)
unmerge.py       →  audit.py           [audit chain for lineage]
                 →  model/crdt_state.py [model contribution retraction]
```

---

## Layer 6 — Module-Level Dependencies

```
compliance.py    →  audit.py           [verify_chain(), get_entries()]
                 →  rbac.py            [permission checks]
                 →  encryption.py      [backend presence check]
                 →  unmerge.py         [GDPRForget, ModelUnmerge]
                 →  hashlib, secrets   (stdlib)
```

---

## External Dependencies Summary

| Package | Layer(s) | Install extra |
|---|---|---|
| `pandas` | L2 | `pip install crdt-merge` (default) |
| `polars` | L2 | `pip install crdt-merge[polars]` |
| `pyarrow` | L2-L3 | `pip install crdt-merge[arrow]` |
| `torch` | L4 | `pip install crdt-merge[model]` |
| `transformers` | L4 | `pip install crdt-merge[model]` |
| `cryptography` | L5 | `pip install crdt-merge[enterprise]` |
| `prometheus_client` | L5 | `pip install crdt-merge[enterprise]` |
| `opentelemetry-sdk` | L5 | `pip install crdt-merge[enterprise]` |
| `duckdb` | accelerators | `pip install crdt-merge[duckdb]` |
| `streamlit` | accelerators | `pip install crdt-merge[streamlit]` |
| `flwr` (Flower) | L4 | `pip install crdt-merge[federated]` |

Install everything:
```bash
pip install crdt-merge[all]
```

---


The most critical classes — highest information flow through a single abstraction:

| Rank | Class | Layer | H (combined) | Why |
|---|---|---|---|---|
| 1 | `MergeStrategy` | L1 | 0.722 | 9 public endpoints, all 8 strategies + MergeSchema depend on it |
| 2 | `MergeRecord` | L1 | 0.159 | Core record type |
| 3 | `AuditLog` | L5 | — | L6 compliance depends entirely on this chain |
| 4 | `CRDTMergeState` | L4 | — | Federation convergence point |

Understanding `MergeStrategy.resolve()` is the single highest-leverage point for understanding the entire merge pipeline.

---

*Dependency Graph v1.1 — AST-verified 2026-03-31, updated for v0.9.4*
