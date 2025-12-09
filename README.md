# crdt-merge

**Conflict-free merge for structured data.** Define strategies. Merge datasets. Prove correctness. Audit every field. Stream at any scale. Zero dependencies.

[![PyPI](https://img.shields.io/badge/pypi-v0.5.0-orange)](https://pypi.org/project/crdt-merge/0.5.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-425%20passed-brightgreen)](TEST_RESULTS.md)

---

## What is crdt-merge?

**crdt-merge** is a Python library for merging datasets with conflict resolution. Instead of "last write wins" or manual dedup scripts, you declare per-field merge strategies — and the library guarantees deterministic, order-independent results with full audit trails.

```python
pip install crdt-merge
```

### What it does

- **Merges datasets** with configurable per-field strategies (max wins, min wins, union, priority, custom)
- **Streams merges** at any scale — O(1) memory for sorted sources, tested to 100M rows
- **Proves correctness** — `@verified_merge` decorator verifies commutativity, associativity, idempotency
- **Audits everything** — per-field provenance trails show exactly which source won each field and why
- **Serializes for the wire** — compact binary format for cross-language CRDT exchange
- **Zero dependencies** — pure Python, embeds anywhere

### What it is NOT

- **Not a real-time collaboration tool.** For collaborative text editing, see [Yjs](https://github.com/yjs/yjs) or [Loro](https://github.com/loro-dev/loro).
- **Not a database.** No persistence, no queries, no networking. It's a library.
- **Not a distributed system.** No gossip protocols, no consensus. It provides the merge primitives that distributed systems can use.

### Who is it for?

Anyone merging structured data from multiple sources: data pipelines, ETL, multi-node sync, offline-first apps, federated datasets. Your real alternative today is `pandas.merge()` (no conflict resolution) or hand-written dedup scripts.

---

## Quick Start

### 1. Basic Merge

```python
from crdt_merge import merge

# Two datasets with conflicting scores for the same person
dataset_a = [{"id": 1, "name": "Alice", "score": 100}]
dataset_b = [{"id": 1, "name": "Alice", "score": 150}]

result = merge(dataset_a, dataset_b, key="id")
# → [{"id": 1, "name": "Alice", "score": 150}]
```

By default, when two rows share the same key, the second dataset wins ties. You can control this with `prefer="a"`, `prefer="b"`, or `prefer="latest"` (uses timestamps).

### 2. Per-Field Strategies with MergeSchema

The real power is declaring **different strategies for different fields**:

```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, MaxWins, LWW, UnionSet

schema = MergeSchema(
    default=LWW(),           # Most fields: last-writer-wins
    score=MaxWins(),          # Scores: highest value wins
    tags=UnionSet()           # Tags: merge as set union
)

a = [{"id": 1, "score": 80, "tags": "python;data", "status": "draft"}]
b = [{"id": 1, "score": 95, "tags": "python;ml",   "status": "published"}]

result = merge(a, b, key="id", schema=schema)
# score: 95 (MaxWins), tags: "data;ml;python" (UnionSet), status: "published" (LWW)
```

**8 built-in strategies:** `LWW`, `MaxWins`, `MinWins`, `UnionSet`, `Priority`, `Concat`, `LongestWins`, `Custom(fn)`

### 3. Streaming Merge at Scale

```python
from crdt_merge import merge_sorted_stream

# Merge two sorted sources with O(1) memory — works with generators from disk/network
def source_a():
    for i in range(10_000_000):
        yield {"id": i, "value": f"a_{i}"}

def source_b():
    for i in range(0, 10_000_000, 2):
        yield {"id": i, "value": f"b_{i}"}

for batch in merge_sorted_stream(source_a(), source_b(), key="id", batch_size=10000):
    process(batch)  # Memory never exceeds batch_size
```

### 4. CRDT Primitives

```python
from crdt_merge import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

# Grow-only counter — nodes increment independently, merge via max-per-node
a = GCounter("node_a")
a.increment("node_a", 10)
b = GCounter("node_b")
b.increment("node_b", 5)
merged = a.merge(b)
print(merged.value)  # 15 — guaranteed correct regardless of merge order
```

All primitives satisfy CRDT properties: **commutative** (a ⊔ b = b ⊔ a), **associative** ((a ⊔ b) ⊔ c = a ⊔ (b ⊔ c)), **idempotent** (a ⊔ a = a).

---

## Feature Matrix

| Module | Feature | Since | Description |
|--------|---------|-------|-------------|
| `core` | GCounter, PNCounter, LWWRegister, ORSet, LWWMap | v0.1.0 | CRDT primitives with merge, serialize, deserialize |
| `dataframe` | `merge()`, `diff()` | v0.1.0 | Dataset merge with key matching, conflict resolution, schema support |
| `dedup` | `dedup_list()`, `dedup_records()`, MinHashDedup | v0.1.0 | Exact, fuzzy (bigram), and MinHash deduplication |
| `json_merge` | `merge_dicts()`, `merge_json_lines()` | v0.1.0 | Deep dict merge with LWW, None-as-missing semantics |
| `strategies` | MergeSchema + 8 strategies | v0.3.0 | Per-field strategy DSL: LWW, MaxWins, MinWins, UnionSet, Priority, Concat, LongestWins, Custom |
| `streaming` | `merge_stream()`, `merge_sorted_stream()` | v0.3.0 | O(batch_size) and O(1) memory streaming merge |
| `delta` | Delta, DeltaStore, `compute_delta()`, `compose_deltas()` | v0.3.0 | Delta-state CRDT sync — compute, apply, compose deltas |
| `provenance` | `merge_with_provenance()`, ProvenanceLog | v0.4.0 | Per-field audit trail: which source won, which strategy, why |
| `verify` | `@verified_merge` decorator | v0.4.0 | Property-based testing of commutativity, associativity, idempotency |
| `wire` | `serialize()`, `deserialize()`, `serialize_batch()` | v0.5.0 | Compact binary wire format for all CRDT types |
| `probabilistic` | MergeableHLL, MergeableBloom, MergeableCMS | v0.5.0 | Probabilistic data structures with CRDT merge semantics |
| `datasets_ext` | `merge_datasets()`, `dedup_dataset()` | v0.1.0 | HuggingFace Datasets integration (optional) |

**13 modules, 4,028 lines of source, zero required dependencies.**

---

## API Reference

### `merge()` — The Main Entry Point

```python
from crdt_merge import merge

result = merge(
    df_a,                    # First dataset (list of dicts, pandas DataFrame, or Polars DataFrame)
    df_b,                    # Second dataset
    key="id",                # Column to match rows on (raises KeyError if not found)
    prefer="latest",         # "a", "b", or "latest" — conflict resolution (raises ValueError if invalid)
    schema=None,             # Optional MergeSchema for per-field strategies (overrides prefer)
    timestamp_col=None,      # Column with timestamps for LWW resolution
    dedup=True,              # Remove exact duplicates in output
    fuzzy_dedup=False,       # Also remove near-duplicates
    fuzzy_threshold=0.85,    # Similarity threshold for fuzzy dedup
)
```

- When `key` is provided: rows with matching keys are merged, unique rows from both sides are preserved.
- When `key` is `None`: datasets are appended and deduplication is applied.
- When `schema` is provided: per-field strategies override the `prefer` parameter for matched rows.
- Input/output format matches: pass pandas in → get pandas out. Pass list of dicts → get list of dicts.

### `merge_with_provenance()` — Merge + Full Audit Trail

```python
from crdt_merge import merge_with_provenance

merged, log = merge_with_provenance(
    df_a, df_b,
    key="id",
    schema=my_schema,          # Optional MergeSchema
    timestamp_col=None,        # Optional timestamp column
    as_dataframe=False,        # Set True to get pandas DataFrame output
)

# Inspect the audit trail
print(log.summary())           # Human-readable summary
print(log.total_conflicts)     # Number of field-level conflicts resolved
for entry in log.entries:
    print(entry.field, entry.winner, entry.strategy)

# Export
from crdt_merge import export_provenance
json_str = export_provenance(log, format="json")  # Returns string
csv_str = export_provenance(log, format="csv")     # Returns string
log_dict = log.to_dict()                           # Returns dict
```

### `merge_stream()` — Streaming Merge

```python
from crdt_merge import merge_stream, StreamStats

stats = StreamStats()
for batch in merge_stream(
    source_a,                # Iterable of dicts (streamed)
    source_b,                # Iterable of dicts (loaded into memory)
    key="id",
    batch_size=5000,
    schema=my_schema,        # Optional MergeSchema
    prefer="b",              # Optional prefer shorthand
    timestamp_col=None,
    stats=stats,
):
    process(batch)

print(f"{stats.rows_per_second:.0f} rows/s, {stats.batch_count} batches")
```

**Memory:** O(|source_b| + batch_size). Loads source_b fully for key lookup, streams source_a in batches.

### `merge_sorted_stream()` — True O(1) Memory Merge

```python
from crdt_merge import merge_sorted_stream

for batch in merge_sorted_stream(
    sorted_source_a,          # MUST be sorted by key ascending
    sorted_source_b,          # MUST be sorted by key ascending
    key="id",
    batch_size=5000,
    schema=my_schema,
    verify_order=True,        # Raises ValueError if sources aren't sorted
):
    process(batch)
```

**Memory:** O(batch_size). Never loads more than 1 row from each source at a time. Tested to 100M rows at 10.8 MB.

### Composable Strategies

```python
from crdt_merge.strategies import (
    MergeSchema, LWW, MaxWins, MinWins, UnionSet,
    Priority, Concat, LongestWins, Custom
)

# Declare per-field strategies
schema = MergeSchema(
    default=LWW(),                                    # Fallback for unspecified fields
    score=MaxWins(),                                   # Highest value wins
    rating=MinWins(),                                  # Lowest value wins
    tags=UnionSet(delimiter=";"),                       # Set union of delimited values
    status=Priority(order=["draft", "review", "live"]), # Priority ranking
    notes=Concat(delimiter="\n"),                       # Concatenate with dedup
    title=LongestWins(),                               # Longer string wins
    custom_field=Custom(fn=my_merge_fn),               # Your own function
)

# Apply to any merge function
result = merge(df_a, df_b, key="id", schema=schema)
merged, log = merge_with_provenance(df_a, df_b, key="id", schema=schema)
for batch in merge_stream(src_a, src_b, key="id", schema=schema):
    ...

# Serialize for storage/transmission
d = schema.to_dict()    # → {"__default__": {"strategy": "LWW"}, "score": {"strategy": "MaxWins"}, ...}
restored = MergeSchema.from_dict(d)
```

**Note:** `Custom(fn)` strategies cannot be serialized — `to_dict()` stores `{"strategy": "Custom"}` and `from_dict()` raises `ValueError` to prevent silent behavior change.

### Delta Sync

```python
from crdt_merge.delta import compute_delta, apply_delta, compose_deltas, DeltaStore

# Compute what changed between two versions
delta = compute_delta(old_records, new_records, key="id")
print(delta.size)  # Number of changes

# Apply delta to bring a remote node up to date
updated = apply_delta(remote_records, delta, key="id")

# Compose multiple deltas: delta(v1→v2) ⊔ delta(v2→v3) = delta(v1→v3)
combined = compose_deltas(delta_1, delta_2, key="id")

# DeltaStore tracks versions automatically
store = DeltaStore(key="id", node_id="node_a")
delta = store.ingest(new_records)  # Returns delta from previous state
print(store.version, store.size)
```

**Note:** DeltaStore is in-memory. Use `Delta.to_dict()` / `Delta.from_dict()` to persist deltas externally.

### Binary Wire Format

```python
from crdt_merge import serialize, deserialize, peek_type, wire_size, serialize_batch, deserialize_batch

# Serialize any CRDT type to compact binary
gc = GCounter("node1")
gc.increment("node1", 100)
wire_bytes = serialize(gc, compress=True)   # zlib compression
restored = deserialize(wire_bytes)          # → GCounter with value 100

# Inspect without deserializing
type_name = peek_type(wire_bytes)           # → "g_counter"
info = wire_size(wire_bytes)                # → {total_bytes, header_bytes, payload_bytes, ...}

# Batch serialize/deserialize
batch_bytes = serialize_batch([gc, pn, lww])
objects = deserialize_batch(batch_bytes)    # → [GCounter, PNCounter, LWWRegister]
```

**Supported types:** GCounter, PNCounter, LWWRegister, ORSet, LWWMap, MergeableHLL, MergeableBloom, MergeableCMS, Delta.

**Wire format specification:** Deterministic byte layout with 12-byte header (magic, version, type, flags, length). Any language implementation that speaks this format can interoperate.

### Probabilistic CRDTs

```python
from crdt_merge import MergeableHLL, MergeableBloom, MergeableCMS

# HyperLogLog — estimate unique counts across distributed nodes
hll_a = MergeableHLL(precision=14)
hll_a.add_all(user_ids_node_a)
hll_b = MergeableHLL(precision=14)
hll_b.add_all(user_ids_node_b)
merged = hll_a.merge(hll_b)       # register-max merge
print(f"~{merged.cardinality():.0f} unique users (±0.81%)")

# Bloom filter — distributed membership testing
bloom = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom.add("blocked_ip")
merged = bloom_a.merge(bloom_b)    # bitwise-OR merge

# Count-Min Sketch — distributed frequency estimation
cms = MergeableCMS(width=1000, depth=5)
cms.add("event_type", count=3)
merged = cms_a.merge(cms_b)       # element-wise max merge
```

All three structures satisfy CRDT merge properties and can be serialized via the wire format.

### Verified Merge

```python
from crdt_merge import verified_merge

@verified_merge(samples=100, key="id")
def my_merge(a, b, key="id"):
    return merge(a, b, key=key)

# Calling my_merge() automatically verifies:
# - Commutativity: my_merge(a, b) == my_merge(b, a)
# - Associativity: my_merge(my_merge(a, b), c) == my_merge(a, my_merge(b, c))
# - Idempotency: my_merge(a, a) == a
# Raises CRDTVerificationError if any property fails.
```

### JSON Deep Merge

```python
from crdt_merge import merge_dicts, merge_json_lines

# Deep merge two dicts with LWW semantics
merged = merge_dicts(
    {"user": {"name": "Alice", "score": 80}},
    {"user": {"name": "Alice", "score": 95, "level": 5}},
)
# → {"user": {"name": "Alice", "score": 95, "level": 5}}

# None values in B are treated as missing (A's value preserved)
merged = merge_dicts({"x": 10}, {"x": None})
# → {"x": 10}

# Merge JSONL files line by line
merged_lines = merge_json_lines(jsonl_a, jsonl_b, key="id")
```

### Deduplication

```python
from crdt_merge import dedup, dedup_records, DedupIndex, MinHashDedup

# Exact dedup on strings
unique = dedup(["hello", "world", "hello"])

# Fuzzy dedup on records
unique_records = dedup_records(records, key="title", threshold=0.85)

# MinHash for large-scale approximate dedup
mh = MinHashDedup(num_hashes=128, threshold=0.5)
unique = mh.dedup(items, text_fn=lambda x: x["description"])

# DedupIndex — CRDT-mergeable dedup state
idx_a = DedupIndex("node_a")
idx_a.add_exact("item1")
idx_b = DedupIndex("node_b")
idx_b.add_exact("item2")
merged_idx = idx_a.merge(idx_b)
```

---

## Benchmarks — A100 Stress Tests

All benchmarks run on Google Colab A100 (83.5 GB RAM). Full results in [`docs/benchmarks/`](docs/benchmarks/).

### v0.3.0 — Core Performance (173 measurements)

| Operation | Scale | Throughput | Memory | Scaling |
|-----------|-------|-----------|--------|---------|
| `merge()` | 100K → 10M rows | 39–42K rows/s | O(n) — 0.3 MB/1K rows | 7% degradation over 100× scale |
| `resolve_row()` (strategies) | 100K → 5M rows | 42–44K rows/s | Zero overhead | Flat — O(1) per row |
| `merge_stream()` (batched) | 100K → 5M rows | 9.7–21K rows/s | O(\|source_b\|) | ⚠️ 54% degradation at 5M |
| `merge_sorted_stream()` | 100K → **100M rows** | **1.05–1.17M rows/s** | **10.8 MB constant** | ✅ 10.5% degradation over 1000× |

**Key findings:**
- **`merge_sorted_stream()` is the star:** 1.2M rows/s with truly constant 10.8 MB memory at 100M rows. O(1) memory proven at scale.
- **Core merge is honest O(n):** No hidden quadratics. Stable throughput to 10M rows.
- **Strategies have zero overhead:** 42–44K rows/s vs 39–42K for raw merge. The DSL is free.
- **`merge_stream()` caveat:** Loads source_b into memory. Use `merge_sorted_stream()` for truly large-scale work.

### v0.4.0 — Provenance & Verification (55 measurements)

All provenance and verification features tested. Schema-aware merge with 50-row datasets: 1.62ms. Export to JSON/CSV verified.

### v0.5.0 — Wire Format & Probabilistic (50 measurements)

All wire format roundtrips verified (GCounter, PNCounter, LWWRegister, ORSet, LWWMap + probabilistic types). Batch serialize/deserialize, compression, and peek_type all verified.

**Notebooks:** Available in [`notebooks/`](notebooks/) for independent reproduction on Google Colab.

---

## Cross-Language Ports

crdt-merge follows a **reference + protocol** architecture:

| Language | Package | Version | Status |
|----------|---------|---------|--------|
| **Python** (reference) | [crdt-merge](https://pypi.org/project/crdt-merge/) | v0.5.0 | ✅ Full feature set |
| TypeScript | [crdt-merge](https://www.npmjs.com/package/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| Rust | [crdt-merge](https://crates.io/crates/crdt-merge) | v0.2.0 | Core CRDTs + merge |
| Java | [crdt-merge](https://github.com/mgillr/crdt-merge-java) | v0.2.0 | Source complete |

**Architecture:** Python is the reference implementation where all innovation starts. The Rust crate will become a thin protocol engine (~1,000 lines) implementing wire format + merge semantics. FFI wrappers (Go, C#, Swift) will wrap the protocol engine. The golden rule: `Python serialize → Rust deserialize → merge → serialize → Python deserialize` must roundtrip perfectly.

---

## Roadmap

### Released

| Version | Name | Highlights |
|---------|------|-----------|
| v0.1.0 | Initial Release | Core CRDTs, merge, diff, dedup, JSON merge, HuggingFace integration |
| v0.2.0 | License Update | Apache-2.0 + patent protection |
| v0.3.0 | The Schema Release | MergeSchema DSL, 8 strategies, streaming merge, delta sync |
| v0.4.0 | The Audit Release | Provenance tracking, @verified_merge, streaming optimizations |
| v0.5.0 | The Protocol Release | Binary wire format, probabilistic CRDTs (HLL, Bloom, CMS) |

### Upcoming

| Version | Name | Key Features |
|---------|------|-------------|
| **v0.5.1** | Hotfix | 24 bug fixes (on main). Key validation, MergeSchema in merge(), None handling, __all__ exports. |
| **v0.6.0** | The Performance Release | Arrow-native merge (10-50× speedup), schema evolution (column mapping + type coercion), async merge, multi-key support |
| **v0.7.0** | The SQL Release | MergeQL — CRDT merge as DuckDB SQL UDF, self-merging Parquet files |
| **v0.8.0** | The AI Release | ModelCRDT — AI model merging (TIES/DARE/SLERP as strategies), conflict topology visualization |
| **v0.9.0** | The Compliance Release | UnmergeEngine — reversible CRDT merge for GDPR erasure, parallel merge |
| **v1.0.0** | The Platform Release | API freeze, cross-language port sync, full documentation, production certification |

**Full roadmap:** [`docs/roadmap/v051_v100_unicorn_roadmap.md`](docs/roadmap/v051_v100_unicorn_roadmap.md)

---

## Known Limitations

These are honest constraints of the current version:

| Limitation | Details | Planned Fix |
|-----------|---------|------------|
| **Python dict merge path** | `merge()` converts DataFrames to list-of-dicts internally. Slow for >1M rows. | Arrow-native engine in v0.6.0 |
| **No type system** | Strategies operate on `Any`. No type checking during merge. | Schema evolution + type coercion in v0.6.0 |
| **Single-threaded** | All operations are synchronous, single-threaded Python. | Async wrappers in v0.6.0, parallel merge in v0.9.0 |
| **Single key column** | `merge()` supports one key column only. Composite keys require manual concatenation. | Multi-key support in v0.6.0 |
| **No persistence** | DeltaStore is in-memory. State lost on process exit. Use `to_dict()`/`from_dict()` to serialize externally. | By design — persistence belongs in the application layer |
| **No networking** | No built-in sync, gossip, or transport. Wire format enables interop but doesn't implement it. | By design — networking belongs in the application layer |
| **O(n²) fuzzy dedup** | `_fuzzy_dedup_records` compares every record against all existing records. Unusable above ~10K records. | Algorithmic improvement in v0.6.0 |
| **Wire format doesn't include MergeSchema** | You can serialize CRDTs and Deltas, but not MergeSchema over the wire. | Planned for v0.6.0 |

---

## Installation

```bash
# Core — zero dependencies
pip install crdt-merge

# With optional accelerators for heavy workloads
pip install crdt-merge[fast]       # orjson + xxhash
pip install crdt-merge[pandas]     # pandas DataFrame support
pip install crdt-merge[polars]     # Polars DataFrame support
pip install crdt-merge[datasets]   # HuggingFace Datasets
pip install crdt-merge[all]        # Everything
pip install crdt-merge[dev]        # pytest + hypothesis for development
```

**Requirements:** Python 3.9+. No required dependencies. Works on Linux, macOS, Windows.

---

## Test Results

**425 tests across 14 test files. 422 passed, 2 skipped (pandas optional), 0 failures.**

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_core.py | 30 | ✅ |
| test_dataframe.py | 14 | ✅ |
| test_dedup.py | 15 | ✅ |
| test_json_merge.py | 10 | ✅ |
| test_strategies.py | 39 | ✅ |
| test_streaming.py | 19 | ✅ |
| test_provenance.py | 24 | ✅ (2 skipped) |
| test_verified_merge.py | 10 | ✅ |
| test_wire.py | 40 | ✅ |
| test_probabilistic.py | 42 | ✅ |
| test_v050_integration.py | 157 | ✅ |
| test_longest_wins.py | 11 | ✅ |
| test_stress_v030.py | 8 | ✅ |
| test_benchmark.py | 6 | ✅ |

**Version history:**

| Version | Tests | Growth |
|---------|------:|--------|
| v0.1.0 | 45 | — |
| v0.2.0 | 88 | +43 |
| v0.3.0 | 133 | +45 |
| v0.4.0 | 277 | +144 |
| v0.5.0 | 425 | +148 |

Full details: [TEST_RESULTS.md](TEST_RESULTS.md)

---

## Project Stats

| Metric | Value |
|--------|-------|
| Modules | 13 |
| Source lines | 4,028 |
| Test lines | ~3,950 |
| Test:source ratio | ~1:1 |
| Dependencies | 0 (required) |
| Python versions | 3.9, 3.10, 3.11, 3.12 |
| License | Apache-2.0 |

---

## Contributing

We welcome contributions. Please see [CLA.md](CLA.md) before submitting pull requests.

**Commercial licensing & inquiries:**
- rgillespie83@icloud.com
- data@optitransfer.ch

---

## License

Copyright 2026 Ryan Gillespie

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full text.

Patent grant included — see [PATENTS](PATENTS).
