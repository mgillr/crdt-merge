<div align="center">

# 🔀 crdt-merge

**Conflict-free merge, dedup & sync for DataFrames, JSON and datasets — powered by CRDTs**

*Latest: v0.4.0 "The Trust Release" — merge provenance, verified merges, 16x streaming speedup*

[![PyPI](https://img.shields.io/pypi/v/crdt-merge.svg)](https://pypi.org/project/crdt-merge/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests: 175 passed](https://img.shields.io/badge/tests-175%20passed-brightgreen.svg)](https://github.com/mgillr/crdt-merge)

**Merge any two datasets in one function call. No conflicts. No coordination. No data loss.**

[Quick Start](#-quick-start) • [What's New in v0.4.0](#-whats-new-in-v040) • [Strategies](#-composable-merge-strategies) • [Streaming](#-streaming-merge) • [Provenance](#-merge-provenance--audit-trails) • [Benchmarks](#-benchmarks) • [API Reference](#-api-reference) • [All Languages](#-available-in-every-language)

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

## 🆕 What's New in v0.4.0

> **"The Trust Release"** — every merge decision is now auditable and verifiable

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| 🔍 **[Merge Provenance](#-merge-provenance--audit-trails)** | Full audit trail of every merge decision — which source won, what changed, why | Compliance, debugging, trust |
| ✅ **[@verified_merge Decorator](#-verified-merge-decorator)** | Wrap any merge with automatic CRDT property checks | Prove correctness, don't hope |
| ⚡ **[16x Streaming Speedup](#-streaming-merge)** | `merge_stream` flat at ~400K rows/s regardless of scale | Was degrading 110K → 23K in v0.3.0 |
| 🐛 **Convergence Fix** | `verify_convergence` no longer false-flags valid CRDTs | Accurate verification |

**100% backward compatible** — all existing APIs work exactly as before. 11 modules, 2,820 lines, 175 tests.

<details>
<summary>📋 What shipped in v0.3.0 "The Schema Release"</summary>

| Feature | What It Does | Why It Matters |
|---------|-------------|----------------|
| 🎯 **Composable Merge Strategies** | Define per-column merge rules (LWW, MaxWins, UnionSet, Priority…) | True CRDT commutativity — order never matters |
| 🌊 **Streaming Merge** | O(batch_size) memory instead of O(n) | Merge 1M+ rows in 3 MB of RAM |
| 📊 **Delta Sync** | Only sync what changed since last merge | 95%+ bandwidth savings |
| 🔬 **Verification Engine** | Prove CRDT guarantees hold on YOUR data | Foundation for v0.4.0 decorator |

</details>

<details>
<summary>📋 Version History</summary>

| Version | Codename | Highlights |
|---------|----------|------------|
| **v0.4.0** | The Trust Release | Merge provenance, @verified_merge decorator, 16x streaming speedup |
| **v0.3.0** | The Schema Release | Composable strategies, streaming merge, delta sync, 1M+ row scale |
| **v0.2.0** | IP Protection | Apache-2.0 license, patent protection, all 4 languages |
| **v0.1.0** | Launch | Core merge, dedup, diff, CRDT types, 5 modules |

</details>

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
pip install crdt-merge                     # zero dependencies (pure Python)
pip install crdt-merge[pandas]             # with pandas support
pip install crdt-merge[datasets]           # with HuggingFace Datasets support
pip install crdt-merge[fast]               # with orjson + xxhash for max speed
pip install crdt-merge[all]                # everything
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

---

## 🎯 Composable Merge Strategies

> **Since v0.3.0** — Define exactly how each column resolves conflicts

Instead of "B always wins", define per-column merge rules:

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority

schema = MergeSchema(
    default=LWW(),                                    # newest timestamp wins (default)
    score=MaxWins(),                                   # highest score always wins
    priority=MinWins(),                                # lowest priority number wins
    tags=UnionSet(separator=","),                       # merge comma-separated sets
    status=Priority(["draft", "review", "published"]), # defined progression
)

# Resolve a single row conflict
merged_row = schema.resolve_row(row_a, row_b, timestamp_col="_ts")

# Resolve entire datasets
merged = schema.resolve_all(dataset_a, dataset_b, key="_id", timestamp_col="_ts")
```

### 8 Built-in Strategies

| Strategy | What It Does | Example |
|----------|-------------|---------|
| `LWW()` | Latest timestamp wins | Name, email — last edit wins |
| `MaxWins()` | Highest value wins | Scores, ratings, counters |
| `MinWins()` | Lowest value wins | Priority numbers, prices |
| `UnionSet(sep)` | Merge delimited sets | `"a,b"` + `"b,c"` → `"a,b,c"` |
| `Priority(order)` | Defined progression | `draft` → `review` → `published` |
| `Concat(sep)` | Concatenate + dedup | Append notes, merge logs |
| `LongestWins()` | Longest string wins | Descriptions, bios |
| `Custom(fn)` | Your function | Any custom logic |

**Why this matters:** `LWW().resolve()` is **truly commutative** — `resolve(A, B) == resolve(B, A)` regardless of argument order. This is the mathematically correct CRDT merge path.

---

## 🔍 Merge Provenance & Audit Trails

> **New in v0.4.0** — Know exactly what happened in every merge

Every merge decision is now traceable. Track which source won each row, what fields changed, and why:

```python
from crdt_merge.provenance import merge_with_provenance

result, log = merge_with_provenance(base_df, incoming_df, key="id")

# Inspect every decision
for decision in log.decisions:
    print(f"Row {decision.key}: {decision.source} won — {decision.reason}")

# Export as DataFrame for analysis
audit_df = log.to_dataframe()

# Export as JSON for compliance logs
audit_json = log.to_json()
```

**Use cases:** regulatory compliance, debugging merge anomalies, building trust with stakeholders who need to know *why* a value changed.

---

## ✅ Verified Merge Decorator

> **New in v0.4.0** — Prove your merges are mathematically correct

Wrap any merge function with automatic CRDT property verification:

```python
from crdt_merge.verify import verified_merge
import crdt_merge

@verified_merge
def my_merge(a, b, **kwargs):
    return crdt_merge.merge(a, b, **kwargs)

# Automatically checks on every call:
# ✅ Idempotency:    merge(A, A) == A
# ✅ Commutativity:  merge(A, B) == merge(B, A)
# ✅ Associativity:  merge(merge(A, B), C) == merge(A, merge(B, C))
result = my_merge(df_a, df_b, key="id")
```

Use `@verified_merge` in your test suite or staging environment to mathematically prove your merge pipeline preserves CRDT guarantees.

---

## 🌊 Streaming Merge

> **Since v0.3.0** — Merge datasets larger than your RAM
> 
> **v0.4.0 upgrade:** `merge_stream` now delivers **16x faster throughput** at scale — flat ~400K rows/s regardless of dataset size (was degrading from 110K → 23K rows/s in v0.3.0)

```python
from crdt_merge.streaming import merge_stream, merge_sorted_stream

# Unsorted data — batched merge with O(batch_size) memory
for batch in merge_stream(large_a, large_b, key="_id", batch_size=5000):
    write_batch(batch)

# Pre-sorted data — true streaming, constant memory
def sorted_gen_a():
    for row in read_csv_streaming("a.csv"):
        yield row

for batch in merge_sorted_stream(sorted_gen_a(), sorted_gen_b(), key="_id"):
    write_batch(batch)  # each batch is batch_size rows, memory stays flat
```

### Memory & Throughput Model

| Approach | Memory | Throughput (v0.4.0) | Scale Limit |
|----------|--------|---------------------|-------------|
| `merge()` | O(n) — grows with data | ~55K rows/s | ~2M rows (8GB RAM) |
| `merge_stream()` | O(batch_size) — configurable | **~400K rows/s (flat)** ⚡ | Unlimited (disk-bound) |
| `merge_sorted_stream()` | O(batch_size) — **constant** | ~200K rows/s | Unlimited (disk-bound) |

> **v0.3.0 → v0.4.0 improvement:** `merge_stream` suffered from two hidden performance bugs (per-batch GC sweep + per-row column reallocation). v0.4.0 removed both — throughput is now scale-independent.

At 1M rows, `merge_sorted_stream` uses **3 MB** regardless of input size. The classic `merge()` would need **688 MB**.

---

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

> **Architectural note:** The core `merge()` function uses "B-wins" overlay semantics (like `git merge remote`). For true order-independent commutativity, use `MergeSchema` with `LWW()` — see [Composable Merge Strategies](#-composable-merge-strategies). Both approaches are valid for different use cases.

### Built-in CRDT Types

| Type | Use Case | Example |
|---|---|---|
| `GCounter` | Grow-only counters | Download counts, page views |
| `PNCounter` | Increment + decrement | Stock levels, balances |
| `LWWRegister` | Single value (latest wins) | Name, email, status fields |
| `ORSet` | Add/remove set | Tags, memberships, dedup sets |
| `LWWMap` | Key-value map | Row merges, config objects |

## 📊 Benchmarks

### Core Operations (v0.2.0 baseline)

Tested on real data (rotten_tomatoes dataset, 8,530 rows):

| Operation | Size | Time | Throughput |
|---|---|---|---|
| DataFrame merge | 1K + 1K → 1.5K | 3.6ms | 411K rows/sec |
| DataFrame merge | 10K + 10K → 15K | 42.6ms | 352K rows/sec |
| DataFrame merge | 50K + 50K → 75K | 234ms | 320K rows/sec |
| Exact dedup | 9K texts | 76ms | 118K texts/sec |
| GCounter ops | 100K increments | - | 8.6M ops/sec |
| OR-Set ops | 10K adds | - | 250K+ ops/sec |

### v0.3.0 Stress Results (224 measurements)

Tested in sandbox (1.9 GB RAM):

| Module | Scale | Throughput | Memory | Notes |
|--------|-------|-----------|--------|-------|
| **Core merge** | 500K + 500K | 57K rows/sec | 688 MB | Linear scaling, predictable |
| **Core merge** | 2M rows | 55K rows/sec | ~1.5 GB | Sandbox ceiling |
| **Strategies** | 1M rows | 58K rows/sec | Proportional | All 8 strategies verified |
| **merge_stream** | 1M rows | 115K rows/sec | O(batch) | 2× faster than core |
| **merge_sorted_stream** | 1M rows | 200K rows/sec | **3 MB flat** | ⭐ Memory constant at any scale |
| **Delta compute** | 500K rows | 953K rows/sec | Minimal | Near 1M/sec — sync is instant |
| **Delta apply** | 500K → 500K | 253K rows/sec | Proportional | Full round-trip |
| **CRDT verification** | 500 trials | All pass | - | Commutativity, associativity, idempotency ✅ |

### v0.4.0 Streaming Performance (16x improvement)

| Scale | v0.3.0 | v0.4.0 | Improvement |
|-------|--------|--------|-------------|
| 100K rows | 110K rows/s | 430K rows/s | +288% |
| 500K rows | 64K rows/s | 393K rows/s | +513% |
| 1M rows | 41K rows/s | 410K rows/s | +906% |
| 2M rows | 23K rows/s | 393K rows/s | **+1,572%** |

> v0.3.0 `merge_stream` degraded linearly as data grew. v0.4.0 holds flat — the throughput line is a ruler.

> **[📓 Run A100 Stress Tests →](notebooks/crdt_merge_stress_a100.ipynb)** Push past sandbox limits with 80GB GPU RAM

<details>
<summary>📋 Full stress reports</summary>

- [v0.3.0 Stress Report](docs/stress_report_v030.md) — 224 measurements across 8 suites
- [v0.2.0 Breaking Point Report](docs/breaking_point_report_v020.md) — Baseline measurements (109 tests)

</details>

**Zero dependencies.** Pure Python. Works offline. Works everywhere.

---

## 📖 API Reference

### Core (since v0.1.0)

#### `merge(df_a, df_b, key=None, timestamp_col=None, prefer="latest", dedup=True)`

Merge two DataFrames (pandas, polars, or list of dicts).

- **key**: Column to match rows. `None` = append + dedup.
- **timestamp_col**: Column with timestamps for conflict resolution.
- **prefer**: `"latest"` (B wins), `"a"`, or `"b"`.
- **dedup**: Remove exact duplicate rows.

#### `dedup(items, method="exact", threshold=0.85)`

Deduplicate a list of strings. Returns `(unique_items, duplicate_indices)`.

- **method**: `"exact"` or `"fuzzy"` (bigram similarity).
- **threshold**: Similarity threshold for fuzzy dedup (0.0-1.0).

#### `diff(df_a, df_b, key)`

Show what changed between two DataFrames. Returns added, removed, modified, unchanged counts.

#### `merge_dicts(a, b, timestamps_a=None, timestamps_b=None)`

Deep-merge two dicts with CRDT semantics. Nested dicts recurse, lists concatenate + dedup.

#### `merge_datasets(dataset_a, dataset_b, key=None, ...)`

Merge two HuggingFace Dataset objects or dataset names. Requires `pip install crdt-merge[datasets]`.

#### `dedup_dataset(dataset, columns=None, method="exact", threshold=0.85)`

Deduplicate a HuggingFace Dataset. Requires `pip install crdt-merge[datasets]`.

#### `DedupIndex(node_id)`

Distributed dedup index backed by CRDT OR-Set. Multiple workers build indices independently, then merge.

#### `MinHashDedup(num_hashes=128, threshold=0.5)`

Locality-sensitive hashing for O(n) near-duplicate detection at scale.

### Strategies (since v0.3.0)

#### `MergeSchema(default=LWW(), **column_strategies)`

Define per-column merge strategies. Apply to individual rows or entire datasets.

```python
schema = MergeSchema(default=LWW(), score=MaxWins(), tags=UnionSet(","))
merged_row = schema.resolve_row(row_a, row_b, timestamp_col="_ts")
merged_all = schema.resolve_all(dataset_a, dataset_b, key="_id", timestamp_col="_ts")
```

#### Strategy Classes

| Class | Constructor | Resolve Semantics |
|-------|-----------|-------------------|
| `LWW()` | No args | Newest timestamp wins |
| `MaxWins()` | No args | `max(a, b)` |
| `MinWins()` | No args | `min(a, b)` |
| `UnionSet(separator)` | `","` or any delimiter | Set union of delimited values |
| `Priority(order)` | `["draft", "published"]` | Later in list wins |
| `Concat(separator)` | `" "` or any delimiter | Concatenate + dedup tokens |
| `LongestWins()` | No args | Longest string wins |
| `Custom(fn)` | `fn(a, b, ts_a, ts_b) → value` | Your function |

### Provenance (since v0.4.0)

#### `merge_with_provenance(base, incoming, key, timestamp_col=None)`

Merge two datasets with full audit trail. Returns `(merged_df, ProvenanceLog)`.

- **ProvenanceLog.decisions**: List of `MergeDecision` objects — one per row
- **ProvenanceLog.to_dataframe()**: Export audit trail as DataFrame
- **ProvenanceLog.to_json()**: Export as JSON for compliance systems

#### `MergeDecision`

| Field | Type | Description |
|-------|------|-------------|
| `key` | any | Row key value |
| `source` | str | `"base"`, `"incoming"`, or `"both"` |
| `reason` | str | Human-readable explanation |
| `fields_changed` | list | Which columns were modified |

### Verification (since v0.3.0, enhanced v0.4.0)

#### `@verified_merge` (v0.4.0+)

Decorator that wraps a merge function with automatic CRDT property checks. Verifies idempotency, commutativity, and associativity on every call.

#### `verify_convergence(merge_fn, datasets, key)` 

Test convergence across multiple dataset permutations. Returns verification report.

#### `verify_crdt_properties(merge_fn, dataset_a, dataset_b, key)`

Check all three CRDT properties (commutative, associative, idempotent) on a pair of datasets.

### Streaming (since v0.3.0, optimized v0.4.0)

#### `merge_stream(a, b, key="_id", batch_size=5000)`

Batched merge for large datasets. Yields lists of merged rows. O(batch_size) memory. **v0.4.0: 16x faster at scale.**

#### `merge_sorted_stream(a_iter, b_iter, key="_id", batch_size=5000)`

True streaming merge for pre-sorted generators. Constant memory regardless of input size.

#### `StreamStats`

Attached to stream results via `.stats` — tracks `batches_emitted`, `rows_emitted`, `peak_memory_mb`, `elapsed_sec`.

### Delta Sync (since v0.3.0)

#### `Delta(added, removed, modified)`

Represents changes between two dataset versions. Compute with `compute_delta()`, apply with `apply_delta()`.

#### `compute_delta(old, new, key)`

Compute the delta between two versions. Returns a `Delta` object.

#### `apply_delta(base, delta, key)`

Apply a delta to a base dataset to reconstruct the new version.

---

## 🏗️ Use Cases

- **Dataset curation**: Multiple annotators edit simultaneously — merge without conflicts
- **Parallel crawlers**: Two crawlers produce overlapping data — merge + dedup automatically
- **Model training**: Merge training logs, configs, and metrics from distributed runs
- **Community datasets**: Accept contributions from multiple forks without merge conflicts
- **Data pipelines**: Incremental processing with automatic state reconciliation
- **Offline-first apps**: Sync data between devices that were offline for days
- **Edge computing**: Stream-merge sensor data from thousands of IoT nodes in constant memory
- **Multi-tenant SaaS**: Per-column merge strategies let different teams own different fields
- **Audit & compliance**: Full provenance trails for regulated industries (v0.4.0+)
- **CI/CD pipelines**: `@verified_merge` in tests to prove correctness before deploy (v0.4.0+)

## 🤝 Contributing

PRs welcome! Run tests with:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 📄 License

Licensed under the [Apache License, Version 2.0](LICENSE).

> **Contributing?** By opening a pull request, you agree to our [Contributor License Agreement](CLA.md).

Copyright 2024–2026 Ryan Gillespie / Optitransfer. See [NOTICE](NOTICE) for attribution requirements.

For commercial licensing inquiries: **rgillespie83@icloud.com**, **data@optitransfer.ch**

---

<div align="center">

Built with math, not hope. 🧬

**[⭐ Star on GitHub](https://github.com/mgillr/crdt-merge)** • **[🤗 Try on HuggingFace](https://huggingface.co/spaces/Optitransfer/crdt-merge)** • **[📦 PyPI](https://pypi.org/project/crdt-merge/)**

</div>
