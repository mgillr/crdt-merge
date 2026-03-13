# Quickstart — crdt-merge in 5 Minutes

## Install

```bash
pip install crdt-merge
```

## Your First Merge

```python
import pandas as pd
from crdt_merge import merge, MergeSchema, LWW, MaxWins

# Two DataFrames with conflicting data
df_a = pd.DataFrame({
    "id": [1, 2],
    "name": ["Alice", "Charlie"],
    "score": [80, 70],
    "_ts": [1000.0, 1000.0]
})

df_b = pd.DataFrame({
    "id": [1, 3],
    "name": ["Bob", "Diana"],
    "score": [90, 85],
    "_ts": [2000.0, 1000.0]
})

# Define per-field strategies
schema = MergeSchema(
    name=LWW(),           # Latest timestamp wins for name
    score=MaxWins(),      # Higher score always wins
)

# Merge!
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="_ts")
print(result)
#    id   name  score      _ts
# 0   1    Bob     90   2000.0  ← Bob (newer), 90 (higher)
# 1   2  Charlie   70   1000.0  ← Only in df_a
# 2   3  Diana     85   1000.0  ← Only in df_b
```

## Key Concepts

1. **Key column**: How rows are matched across DataFrames
2. **MergeSchema**: Declares per-field conflict resolution
3. **Strategies**: LWW, MaxWins, MinWins, UnionSet, Priority, Concat, LongestWins, Custom
4. **CRDT guarantee**: `merge(A, B) == merge(B, A)` — order doesn't matter

## Next Steps

- [Installation Guide](INSTALLATION.md) — All extras and optional dependencies
- [First Merge Tutorial](FIRST_MERGE.md) — Detailed walkthrough
- [Core Concepts](CONCEPTS.md) — Understand CRDTs, strategies, and schemas
