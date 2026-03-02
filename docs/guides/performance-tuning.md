# Performance Tuning Guide

Benchmarks, engine selection, chunking, profiling, and DuckDB acceleration. All APIs are verified against the live codebase.

---

## Engine Selection

Choose the engine based on data volume and format:

| Data Size | Engine | Import | Why |
|---|---|---|---|
| < 10K rows | `merge()` (pandas) | `from crdt_merge import merge` | Thread overhead exceeds benefit |
| 10K – 1M rows | `merge()` (polars) | auto-detected | 2-5× faster than pandas |
| 100K – 10M rows | `arrow_merge()` | `from crdt_merge.arrow import arrow_merge` | Vectorized columnar operations |
| > 1M rows (multi-core) | `parallel_merge()` | `from crdt_merge.parallel import parallel_merge` | Key-aligned chunking + thread pool |
| Unbounded / streaming | `merge_stream()` | `from crdt_merge.streaming import merge_stream` | O(1) memory |
| Pre-sorted streams | `merge_sorted_stream()` | `from crdt_merge.streaming import merge_sorted_stream` | Optimal O(n+m) |

---

## 1. Use Polars Instead of Pandas

crdt-merge auto-detects Polars DataFrames — no code change needed:

```python
import polars as pl
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

df_a = pl.read_parquet("data_a.parquet")
df_b = pl.read_parquet("data_b.parquet")

schema = MergeSchema(default=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema)
# Returns polars DataFrame — same engine as input
```

**When to prefer Polars**: CSV/Parquet ingestion pipelines, numeric-heavy schemas, single-node workloads up to ~5M rows.

---

## 2. Arrow Merge for Large Columnar Data

```python
import pyarrow.parquet as pq
from crdt_merge.arrow import arrow_merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

table_a = pq.read_table("data_a.parquet")
table_b = pq.read_table("data_b.parquet")

schema = MergeSchema(default=LWW(), score=MaxWins())
result = arrow_merge(table_a, table_b, key="id", schema=schema)
# Returns Arrow Table
```

**When to prefer Arrow**: Interoperability with Spark/DuckDB/Polars pipelines, datasets that don't fit in pandas memory, columnar analytics workflows.

---

## 3. Parallel Merge (Multi-Core)

```python
from crdt_merge.parallel import parallel_merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), score=MaxWins())

result = parallel_merge(
    df_a, df_b,
    key="id",
    schema=schema,
    timestamp_col="updated_at",
    max_workers=8,        # number of threads (None → executor default)
    chunk_size=50_000,    # unique keys per chunk (tune based on row size)
)
```

**How it works**:
1. All rows sharing a key are assigned to the same chunk (key-aligned partitioning)
2. Each chunk pair is merged independently by a thread
3. Results are concatenated

**Auto-fallback**: If total rows < 10,000, `parallel_merge` falls back to single-threaded `merge()` automatically. No performance penalty for small datasets.

**Arrow-backed parallel merge**:
```python
from crdt_merge.parallel import parallel_merge_arrow

result = parallel_merge_arrow(
    table_a, table_b,
    key="id",
    schema=schema,
    max_workers=8,
    chunk_size=100_000,
)
```

---

## 4. Streaming Merge (O(1) Memory)

```python
from crdt_merge.streaming import merge_stream
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())

# Produces merged records one at a time — never loads full dataset
for merged_record in merge_stream(stream_a, stream_b, key="id", schema=schema):
    output_sink.write(merged_record)
```

**Pre-sorted stream** (optimal O(n+m) — no sorting overhead):
```python
from crdt_merge.streaming import merge_sorted_stream

# Requires both streams to be sorted by key ascending
for merged_record in merge_sorted_stream(sorted_a, sorted_b, key="id", schema=schema):
    output_sink.write(merged_record)
```

**When to use**: Log ingestion, event streams, datasets too large for RAM, real-time pipeline sinks.

---

## 5. Self-Merging Parquet Store

```python
from crdt_merge.parquet import SelfMergingParquet
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), score=MaxWins())
store = SelfMergingParquet("data/", key="id", schema=schema)

# Write new data — auto-merges on next compact()
store.write(new_records)

# Compact all Parquet files into one merged file
store.compact()
```

**Use case**: Append-only ingestion with periodic compaction (e.g., Lambda, nightly jobs).

---

## 6. Async Merge

```python
import asyncio
from crdt_merge.async_merge import amerge
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())

async def process():
    result = await amerge(df_a, df_b, key="id", schema=schema)
    return result

result = asyncio.run(process())
```

```python
from crdt_merge.async_merge import amerge_stream

async def stream_process():
    async for merged_record in amerge_stream(stream_a, stream_b, key="id"):
        await sink.write(merged_record)
```

---

## 7. DuckDB Acceleration

Register crdt-merge functions as DuckDB UDFs for SQL-based pipelines:

```python
import duckdb
from crdt_merge.accelerators.duckdb_udf import register_duckdb_udfs

conn = duckdb.connect()
register_duckdb_udfs(conn)

# Use CRDT merge functions in SQL
result = conn.execute("""
    SELECT
        a.id,
        crdt_lww(a.name, b.name, a.ts, b.ts) AS name,
        crdt_max(a.score, b.score) AS score
    FROM table_a a
    JOIN table_b b USING (id)
""").fetchdf()
```

**DuckLake** (full merge pushed to DuckDB):
```python
from crdt_merge.accelerators.ducklake import DuckLakeMerge
from crdt_merge.strategies import MergeSchema, LWW

dl = DuckLakeMerge(conn=conn, schema=MergeSchema(default=LWW()))
dl.merge_tables("table_a", "table_b", key="id", output="merged")
```

---

## 8. Model Merge Performance (GPU)

```python
from crdt_merge.model.gpu import GPUMerge

gpu = GPUMerge(device="cuda", dtype="float16")

# Estimate GPU memory before merging
sizes = [model_a_param_count, model_b_param_count]
mem_needed = gpu.estimate_memory(sizes)
print(f"Required VRAM: {mem_needed / 1e9:.1f} GB")

# Merge on GPU
merged = gpu.merge([model_a, model_b], strategy="weight_average")
```

**MPS (Apple Silicon)**:
```python
gpu = GPUMerge(device="mps", dtype="float32")
merged = gpu.merge([model_a, model_b], strategy="weight_average")
```

---

## 9. Profiling Your Merge Pipeline

```python
import cProfile
import pstats
from crdt_merge import merge

with cProfile.Profile() as pr:
    result = merge(df_a, df_b, key="id", schema=schema)

stats = pstats.Stats(pr).sort_stats("cumulative")
stats.print_stats(20)   # Top 20 hotspots
```

**Built-in observability** (tracks merge duration, row counts, conflicts):
```python
from crdt_merge.observability import MetricsCollector, ObservedMerge

collector = MetricsCollector()
om = ObservedMerge(collector=collector)

result = om.merge(df_a, df_b, key="id", schema=schema)
summary = collector.get_summary()
print(f"Duration: {summary['total_duration_ms']:.1f}ms")
print(f"Rows merged: {summary['rows_merged']}")
print(f"Conflicts resolved: {summary['conflicts_resolved']}")
```

---

## 10. Chunking Strategy

`parallel_merge` uses **key-aligned chunking** — all rows for a given key end up in the same chunk, ensuring correctness.

```python
from crdt_merge.parallel import parallel_merge

# chunk_size = number of unique keys per chunk
# Tune based on: rows_per_key × chunk_size × avg_row_bytes < available_RAM_per_thread

# Example: 1M rows, 1 key per row, 8 threads, 1KB per row
# chunk_size = 1_000_000 / 8 = 125_000 unique keys per chunk
result = parallel_merge(df_a, df_b, key="id", max_workers=8, chunk_size=125_000)

# Wide rows (many columns): use smaller chunks
result = parallel_merge(df_a, df_b, key="id", max_workers=8, chunk_size=10_000)
```

---

## Performance Tips Summary

| Tip | Impact | When |
|---|---|---|
| Use Polars instead of pandas | 2-5× | Any workload |
| Use `arrow_merge` | 3-8× | Large Parquet/Arrow datasets |
| Use `parallel_merge` | N× (N=cores) | > 1M rows, multi-core available |
| Use `merge_sorted_stream` | Best O(n+m) | Pre-sorted data |
| Use `chunk_size` tuning | 20-50% | When chunks spill to disk |
| Use DuckDB UDFs | 5-20× | SQL-resident data |
| Use `GPUMerge` | 10-100× | Model weight tensors (CUDA) |
| Use `MetricsCollector` | — | Profiling, identifying bottlenecks |
