# Installation Guide

crdt-merge uses a modular extras system — install only what you need.

---

## Basic Install

```bash
pip install crdt-merge
```

Includes:
- Layer 1: CRDT primitives (GCounter, PNCounter, LWWRegister, ORSet, LWWMap)
- Layer 1: All merge strategies (LWW, MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins, Custom)
- Layer 1: Vector clocks, probabilistic structures, CRDT verification
- Layer 2: DataFrame merge (`merge()`, `diff()`) — pandas
- Layer 2: JSON/dict merge (`merge_dicts()`, `merge_json_lines()`)
- Layer 2: Streaming merge (`merge_stream()`, `merge_sorted_stream()`)
- Layer 2: Parallel merge (`parallel_merge()`)
- Layer 2: Schema evolution
- Layer 3: Wire protocol, Merkle tree, gossip, delta sync

No heavy dependencies (torch, pyarrow, cryptography) are installed.

---

## With Extras

```bash
# Apache Arrow / Parquet support
pip install crdt-merge[arrow]
# → Installs: pyarrow
# → Enables: arrow_merge(), ArrowMerge, SelfMergingParquet

# Polars support
pip install crdt-merge[polars]
# → Installs: polars
# → Enables: auto-detected Polars engine in merge()

# ML model merging (requires PyTorch)
pip install crdt-merge[model]
# → Installs: torch, transformers, numpy
# → Enables: CRDTMergeState, ModelMerge, LoRAMerge, GPUMerge, FederatedMerge
#            26+ strategies (weight_average, slerp, ties, dare, dare_ties, ...)

# HuggingFace Hub integration
pip install crdt-merge[hub]
# → Installs: huggingface_hub
# → Enables: push_to_hub(), HFModelTarget

# Enterprise features (encryption, audit, RBAC, observability, compliance)
pip install crdt-merge[enterprise]
# → Installs: cryptography, prometheus_client, opentelemetry-sdk
# → Enables: EncryptedMerge, RBACController, AuditLog, MetricsCollector,
#            DriftDetector, MergeTracer, ComplianceAuditor, EUAIActReport

# DuckDB and Streamlit accelerators
pip install crdt-merge[accelerators]
# → Installs: duckdb, streamlit
# → Enables: register_duckdb_udfs(), DuckLakeMerge, Streamlit UI

# Federated learning (Flower framework)
pip install crdt-merge[federated]
# → Installs: flwr
# → Enables: CRDTFlowerStrategy

# Everything
pip install crdt-merge[all]
```

---

## Verify Installation

```python
import crdt_merge
print(crdt_merge.__version__)   # "0.9.4"

# Verify core works
from crdt_merge.core import GCounter
c = GCounter()
c.increment("node1", 5)
print(c.value)   # 5

# Verify DataFrame merge works
import pandas as pd
from crdt_merge import merge
df_a = pd.DataFrame([{"id": 1, "val": "a"}])
df_b = pd.DataFrame([{"id": 2, "val": "b"}])
result = merge(df_a, df_b, key="id")
print(len(result))   # 2
```

**Check what's installed**:
```bash
crdt-merge doctor
```

This runs a diagnostic and shows which optional features are available:
```
crdt-merge doctor
✅ Core (Layer 1) — OK
✅ Engines (Layer 2) — pandas 2.1.0
✅ Transport (Layer 3) — OK
❌ Model (Layer 4) — torch not installed (pip install crdt-merge[model])
❌ Enterprise (Layer 5) — cryptography not installed (pip install crdt-merge[enterprise])
```

---

## Optional Dependencies Reference

| Extra | Packages installed | Layer | What it enables |
|---|---|---|---|
| `arrow` | `pyarrow>=12.0` | L2 | Arrow tables, Parquet, `arrow_merge()`, `SelfMergingParquet` |
| `polars` | `polars>=0.19` | L2 | Polars engine auto-detected in `merge()` |
| `model` | `torch`, `transformers`, `numpy` | L4 | 26+ model merge strategies, LoRA, GPU, federated |
| `hub` | `huggingface_hub` | L4 | HF Hub push/pull |
| `enterprise` | `cryptography`, `prometheus_client`, `opentelemetry-sdk` | L5-L6 | Encryption, RBAC, audit, metrics, compliance |
| `accelerators` | `duckdb`, `streamlit` | Accel | DuckDB UDFs, Streamlit UI |
| `federated` | `flwr` | L4 | Flower federated learning plugin |
| `all` | Everything above | All | Complete installation |

---

## Python Version Requirements

- Python 3.8+
- Python 3.10+ recommended for model merging (type union syntax)
- Python 3.11+ for best performance with the async merge engine

---

## Development Install

```bash
git clone https://github.com/mgillr/crdt-merge.git
cd crdt-merge
pip install -e ".[all]"
pytest tests/ -q   # Run the full test suite (309 tests)
```

---

## Docker

```dockerfile
FROM python:3.11-slim

# Core only
RUN pip install crdt-merge

# With model merging
RUN pip install crdt-merge[model]

# Production (enterprise + compliance)
RUN pip install crdt-merge[enterprise]
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'pyarrow'`**
```bash
pip install crdt-merge[arrow]
```

**`ModuleNotFoundError: No module named 'torch'`**
```bash
pip install crdt-merge[model]
```

**`ModuleNotFoundError: No module named 'cryptography'`**
```bash
pip install crdt-merge[enterprise]
```

**Import works but merge() is slow**
- Check if Polars or Arrow engine is available: `pip install crdt-merge[polars]` or `[arrow]`
- For > 1M rows: `pip install crdt-merge` (parallel_merge is in the base package)

See [Troubleshooting Guide](../guides/troubleshooting.md) for more diagnostic patterns.
