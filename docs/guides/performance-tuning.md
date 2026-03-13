# Performance Tuning Guide

## Engine Selection

| Data Size | Engine | Why |
|-----------|--------|-----|
| < 100K rows | `merge()` (pandas) | Simple, fast enough |
| 100K - 1M rows | `merge()` (polars) | 2-5x faster than pandas |
| > 1M rows | `arrow_merge()` | Vectorized, columnar |
| > 10M rows | `parallel_merge()` | Multi-core |
| Unbounded | `merge_stream()` | O(1) memory |
| Pre-sorted | `merge_sorted_stream()` | Optimal O(n+m) |

## Key Optimizations

### 1. Use Polars Instead of Pandas
```python
import polars as pl
# crdt_merge auto-detects Polars DataFrames
df_a = pl.read_csv("data_a.csv")
result = merge(df_a, df_b, key="id")  # Uses Polars engine
```

### 2. Use Arrow for Large Data
```python
from crdt_merge.arrow import arrow_merge
result = arrow_merge(table_a, table_b, key="id", schema=schema)
```

### 3. Parallel Merge
```python
from crdt_merge.parallel import parallel_merge
result = parallel_merge(df_a, df_b, key="id", schema=schema, num_workers=8)
```

### 4. Self-Merging Parquet
```python
from crdt_merge.parquet import SelfMergingParquet
store = SelfMergingParquet("data/", key="id", schema=schema)
store.write(new_data)
store.compact()  # Periodic compaction
```

## Model Merge Performance

### GPU Acceleration
```python
from crdt_merge.model.gpu import GPUMerge
gpu = GPUMerge(device="cuda", dtype="float16")
merged = gpu.merge([model_a, model_b], strategy="linear")
```

### Memory Estimation
```python
mem_needed = gpu.estimate_memory([model_a_size, model_b_size])
```
