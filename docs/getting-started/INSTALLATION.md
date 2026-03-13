# Installation Guide

## Basic Install

```bash
pip install crdt-merge
```
Includes: Core CRDTs, strategies, DataFrame merge, JSON merge. No heavy dependencies.

## With Extras

```bash
# Arrow/Parquet support
pip install crdt-merge[arrow]

# Polars support
pip install crdt-merge[polars]

# ML model merging (requires PyTorch)
pip install crdt-merge[model]

# HuggingFace Hub integration
pip install crdt-merge[hub]

# Enterprise features (encryption, audit)
pip install crdt-merge[enterprise]

# All accelerators
pip install crdt-merge[accelerators]

# Everything
pip install crdt-merge[all]
```

## Verify Installation

```python
import crdt_merge
print(crdt_merge.__version__)  # 0.9.2
```

## Optional Dependencies

| Extra | Packages | For |
|-------|----------|-----|
| `arrow` | pyarrow | Arrow tables, Parquet files |
| `polars` | polars | Polars DataFrames |
| `model` | torch, transformers | ML model merging |
| `hub` | huggingface_hub | HF Hub integration |
| `enterprise` | cryptography | Encryption backends |
| `accelerators` | duckdb, streamlit | Database integrations |
| `flower` | flwr | Federated learning |
