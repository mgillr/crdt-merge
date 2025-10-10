<div align="center">

# 🔀 crdt-merge

**Conflict-free merge, dedup & sync for DataFrames, JSON and datasets — powered by CRDTs**

[![PyPI](https://img.shields.io/pypi/v/crdt-merge.svg)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 1,083 passed](https://img.shields.io/badge/tests-1%2C083%20passed-brightgreen.svg)](https://github.com/mgillr/crdt-merge)

**Merge any two datasets in one function call. No conflicts. No coordination. No data loss.**

[Quick Start](#-quick-start) • [Why CRDTs](#-why-crdts) • [Benchmarks](#-benchmarks) • [API Reference](#-api-reference) • [All Languages](#-available-in-every-language)

</div>

---

## 🌐 Available in Every Language

| Language | Package | Install | Repo |
|---|---|---|---|
| **Python** 🐍 | `crdt-merge` | `pip install crdt-merge` | **You are here** |
| **TypeScript** | `crdt-merge` | `npm install crdt-merge` | [crdt-merge-ts](https://github.com/mgillr/crdt-merge-ts) |
| **Rust** 🦀 | `crdt-merge` | `cargo add crdt-merge` | [crdt-merge-rs](https://github.com/mgillr/crdt-merge-rs) |
| **Java** ☕ | `io.optitransfer:crdt-merge` | Maven / Gradle | [crdt-merge-java](https://github.com/mgillr/crdt-merge-java) |
| **CLI** 🖥️ | included in Rust | `cargo install crdt-merge` | [crdt-merge-rs](https://github.com/mgillr/crdt-merge-rs) |

> **[🤗 Try it in the browser →](https://huggingface.co/spaces/Optitransfer/crdt-merge)**

---

## 🎯 The Problem

You have two versions of a dataset. Maybe two crawlers ran in parallel. Maybe two annotators edited the same file. Maybe you're merging community contributions.

**Today:** Write custom merge scripts, lose data, or block on a coordinator.

**With crdt-merge:** One function call. Zero conflicts. Mathematically guaranteed.

```python
from crdt_merge import merge

merged = merge(df_a, df_b, key="id")  # done.
```

## ⚡ Quick Start

```bash
pip install crdt-merge                 # zero dependencies (pure Python)
pip install crdt-merge[pandas]         # with pandas support
pip install crdt-merge[datasets]       # with HuggingFace Datasets support
pip install crdt-merge[all]            # everything
```

### Merge Two DataFrames

```python
import pandas as pd
from crdt_merge import merge

# Two contributors edited the same dataset
df_a = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})
df_b = pd.DataFrame({"id": [2, 3, 4], "name": ["Robert", "Charlie", "Diana"]})

merged = merge(df_a, df_b, key="id")
# id=1: Alice (only in A)
# id=2: Robert (B wins — latest)
# id=3: Charlie (same in both)
# id=4: Diana (only in B)
```

### Merge Two HuggingFace Datasets

```python
from crdt_merge import merge_datasets

merged = merge_datasets("user/dataset-v1", "user/dataset-v2", key="id")
```

### Deduplicate Anything

```python
from crdt_merge import dedup

texts = ["Hello world", "hello  world", "HELLO WORLD", "Something else"]
unique, duplicate_indices = dedup(texts)
# unique = ["Hello world", "Something else"]  (case/whitespace normalized)
```

### Deep-Merge JSON/Configs

```python
from crdt_merge import merge_dicts

config_a = {"model": {"name": "bert", "layers": 12}, "tags": ["nlp"]}
config_b = {"model": {"name": "bert-large", "dropout": 0.1}, "tags": ["qa"]}

merged = merge_dicts(config_a, config_b)
# {"model": {"name": "bert-large", "layers": 12, "dropout": 0.1}, "tags": ["nlp", "qa"]}
```

### See What Changed

```python
from crdt_merge import diff

changes = diff(df_old, df_new, key="id")
print(changes["summary"])
# "+5 added, -2 removed, ~3 modified, =990 unchanged"
```

## 🧠 Why CRDTs

**CRDT** = Conflict-free Replicated Data Type. A data structure with one mathematical superpower:

> **Any two copies can merge — in any order, at any time — and the result is always identical and always correct.**

Three mathematical guarantees (proven, not hoped):

| Property | What it means |
|---|---|
| **Commutative** | `merge(A, B) == merge(B, A)` — order doesn't matter |
| **Associative** | `merge(merge(A, B), C) == merge(A, merge(B, C))` — grouping doesn't matter |
| **Idempotent** | `merge(A, A) == A` — re-merging is safe |

This means: **zero coordination, zero locks, zero conflicts.** Two workers can independently edit a dataset and merge later — the result is mathematically guaranteed correct.

### Built-in CRDT Types

| Type | Use Case | Example |
|---|---|---|
| `GCounter` | Grow-only counters | Download counts, page views |
| `PNCounter` | Increment + decrement | Stock levels, balances |
| `LWWRegister` | Single value (latest wins) | Name, email, status fields |
| `ORSet` | Add/remove set | Tags, memberships, dedup sets |
| `LWWMap` | Key-value map | Row merges, config objects |

## 📊 Benchmarks

Tested on real data (rotten_tomatoes dataset, 8,530 rows):

| Operation | Size | Time | Throughput |
|---|---|---|---|
| DataFrame merge | 1K + 1K → 1.5K | 3.6ms | 411K rows/sec |
| DataFrame merge | 10K + 10K → 15K | 42.6ms | 352K rows/sec |
| DataFrame merge | 50K + 50K → 75K | 234ms | 320K rows/sec |
| Exact dedup | 9K texts | 76ms | 118K texts/sec |
| GCounter ops | 100K increments | - | 8.6M ops/sec |
| OR-Set ops | 10K adds | - | 250K+ ops/sec |

**Zero dependencies.** Pure Python. Works offline. Works everywhere.

## 📖 API Reference

### `merge(df_a, df_b, key=None, timestamp_col=None, prefer="latest", dedup=True)`

Merge two DataFrames (pandas, polars, or list of dicts).

- **key**: Column to match rows. `None` = append + dedup.
- **timestamp_col**: Column with timestamps for conflict resolution.
- **prefer**: `"latest"` (B wins), `"a"`, or `"b"`.
- **dedup**: Remove exact duplicate rows.

### `dedup(items, method="exact", threshold=0.85)`

Deduplicate a list of strings. Returns `(unique_items, duplicate_indices)`.

- **method**: `"exact"` or `"fuzzy"` (bigram similarity).
- **threshold**: Similarity threshold for fuzzy dedup (0.0-1.0).

### `diff(df_a, df_b, key)`

Show what changed between two DataFrames. Returns added, removed, modified, unchanged counts.

### `merge_dicts(a, b, timestamps_a=None, timestamps_b=None)`

Deep-merge two dicts with CRDT semantics. Nested dicts recurse, lists concatenate + dedup.

### `merge_datasets(dataset_a, dataset_b, key=None, ...)`

Merge two HuggingFace Dataset objects or dataset names. Requires `pip install crdt-merge[datasets]`.

### `dedup_dataset(dataset, columns=None, method="exact", threshold=0.85)`

Deduplicate a HuggingFace Dataset. Requires `pip install crdt-merge[datasets]`.

### `DedupIndex(node_id)`

Distributed dedup index backed by CRDT OR-Set. Multiple workers build indices independently, then merge.

### `MinHashDedup(num_hashes=128, threshold=0.5)`

Locality-sensitive hashing for O(n) near-duplicate detection at scale.

## 🏗️ Use Cases

- **Dataset curation**: Multiple annotators edit simultaneously — merge without conflicts
- **Parallel crawlers**: Two crawlers produce overlapping data — merge + dedup automatically
- **Model training**: Merge training logs, configs, and metrics from distributed runs
- **Community datasets**: Accept contributions from multiple forks without merge conflicts
- **Data pipelines**: Incremental processing with automatic state reconciliation
- **Offline-first apps**: Sync data between devices that were offline for days

## 🤝 Contributing

PRs welcome! Run tests with:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 📄 License

MIT — use it for anything.

---

<div align="center">

Built with math, not hope. 🧬

**[⭐ Star on GitHub](https://github.com/mgillr/crdt-merge)** • **[🤗 Try on HuggingFace](https://huggingface.co/spaces/Optitransfer/crdt-merge)** • **[📦 PyPI](https://pypi.org/project/crdt-merge/)**

</div>
