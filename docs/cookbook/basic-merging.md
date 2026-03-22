# Basic Merging Recipes

Verified copy-paste recipes for the most common merge patterns.

---

## Recipe 1: Simple DataFrame Merge (Default LWW)

```python
import pandas as pd
from crdt_merge import merge

df_a = pd.DataFrame([
    {"id": 1, "name": "Alice", "score": 80, "ts": 1000.0},
    {"id": 2, "name": "Bob",   "score": 70, "ts": 1000.0},
])
df_b = pd.DataFrame([
    {"id": 1, "name": "Alice", "score": 95, "ts": 2000.0},  # newer
    {"id": 3, "name": "Carol", "score": 88, "ts": 1000.0},  # new row
])

# Default: LWW for all fields (highest timestamp wins)
result = merge(df_a, df_b, key="id", timestamp_col="ts")
print(result)
# id=1: score=95 (ts=2000 > 1000), id=2: unchanged, id=3: from df_b
```

---

## Recipe 2: Multi-Strategy Merge

```python
import pandas as pd
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority, Concat

schema = MergeSchema(
    default=LWW(),
    score=MaxWins(),                                         # highest score always wins
    price=MinWins(),                                         # lowest price wins
    tags=UnionSet(separator=","),                           # union tag sets
    status=Priority(["draft", "review", "approved", "published"]),
    notes=Concat(separator=" | "),
)

result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="ts")
```

---

## Recipe 3: Merge Without a Timestamp Column

When you don't have a timestamp column, LWW falls back to lexicographic value comparison:

```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, MaxWins

schema = MergeSchema(
    default=MaxWins(),   # Always pick higher value — no timestamp needed
)

result = merge(df_a, df_b, key="id", schema=schema)
```

For fields where you always want a specific side to win:
```python
# Always prefer df_b values when there's a conflict
from crdt_merge.strategies import Custom

prefer_b = Custom(fn=lambda a, b: b if b is not None else a)
schema = MergeSchema(default=prefer_b)
result = merge(df_a, df_b, key="id", schema=schema)
```

---

## Recipe 4: Composite Key

```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())

# Merge on multiple columns that together form the unique identifier
result = merge(df_a, df_b, key=["org_id", "user_id"], schema=schema, timestamp_col="ts")
```

---

## Recipe 5: Merge Multiple DataFrames

```python
from functools import reduce
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), score=MaxWins())

dfs = [df_a, df_b, df_c, df_d, df_e]

# CRDT associativity guarantees the same result regardless of reduce order
result = reduce(lambda a, b: merge(a, b, key="id", schema=schema, timestamp_col="ts"), dfs)
```

---

## Recipe 6: JSON / Dict Merge

```python
from crdt_merge.json_merge import merge_dicts

dict_a = {"name": "Alice", "score": 80, "tags": ["python", "ml"]}
dict_b = {"name": "Bob",   "score": 90, "tags": ["python", "ai"]}

# Without timestamps: b wins for scalar fields (LWW tie = lex comparison)
result = merge_dicts(dict_a, dict_b)
print(result)
# {"name": "Bob", "score": 90, "tags": ["ai", "ml", "python"]}  — lists union

# With timestamps: control which side wins per key
result = merge_dicts(
    dict_a, dict_b,
    timestamps_a={"name": 3.0, "score": 1.0},
    timestamps_b={"name": 2.0, "score": 2.0},
)
print(result["name"])    # "Alice" (ts_a=3.0 > ts_b=2.0)
print(result["score"])   # 90     (ts_b=2.0 > ts_a=1.0)
```

---

## Recipe 7: Merge with Provenance (Audit Trail)

```python
import pandas as pd
from crdt_merge.provenance import merge_with_provenance, export_provenance
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

df_a = pd.DataFrame([{"id": 1, "name": "Alice", "score": 80}])
df_b = pd.DataFrame([{"id": 1, "name": "Bob",   "score": 90}])

schema = MergeSchema(default=LWW(), score=MaxWins())

result, log = merge_with_provenance(df_a, df_b, key="id", schema=schema)

# Inspect per-field decisions
for record in log:
    for decision in record.conflicts:
        if decision.was_conflict():
            print(
                f"Row {record.key}, field '{decision.field}': "
                f"chose {decision.value!r} over {decision.alternative!r} "
                f"via {decision.strategy}"
            )

# Export as JSON for compliance
json_report = export_provenance(log, format="json")
csv_report  = export_provenance(log, format="csv")
```

---

## Recipe 8: Polars DataFrame Merge

crdt-merge auto-detects Polars DataFrames — no code change needed:

```python
import polars as pl
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

df_a = pl.read_parquet("data_a.parquet")
df_b = pl.read_parquet("data_b.parquet")

schema = MergeSchema(default=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="ts")
# result is a Polars DataFrame
print(type(result))   # <class 'polars.dataframe.frame.DataFrame'>
```

---

## Recipe 9: Apache Arrow Merge

```python
import pyarrow.parquet as pq
from crdt_merge.arrow import arrow_merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

table_a = pq.read_table("data_a.parquet")
table_b = pq.read_table("data_b.parquet")

schema = MergeSchema(default=LWW(), score=MaxWins())
result = arrow_merge(table_a, table_b, key="id", schema=schema)
print(type(result))   # pyarrow.Table
```

---

## Recipe 10: Async Merge

```python
import asyncio
import pandas as pd
from crdt_merge.async_merge import amerge
from crdt_merge.strategies import MergeSchema, LWW

async def merge_and_store(df_a, df_b):
    schema = MergeSchema(default=LWW())
    result = await amerge(df_a, df_b, key="id", schema=schema)
    return result

result = asyncio.run(merge_and_store(df_a, df_b))
```

---

## Recipe 11: Self-Merging Parquet Store

```python
from crdt_merge.parquet import SelfMergingParquet
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), score=MaxWins())
store = SelfMergingParquet("./data/", key="id", schema=schema)

# Append new data — stored as separate files
store.write([{"id": 1, "score": 90, "ts": 1000}])
store.write([{"id": 1, "score": 95, "ts": 2000}])

# Compact: merge all Parquet files into one
store.compact()

# Read merged result
result = store.read()
print(result)   # id=1, score=95 (MaxWins over all compacted files)
```

---

## Recipe 12: Streaming Merge (Large Datasets)

```python
from crdt_merge.streaming import merge_stream
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())

def read_stream(path):
    """Read records from a file as an iterator."""
    import json
    with open(path) as f:
        for line in f:
            yield json.loads(line)

output = []
for record in merge_stream(
    read_stream("data_a.jsonl"),
    read_stream("data_b.jsonl"),
    key="id",
    schema=schema,
):
    output.append(record)

print(f"Merged {len(output)} records")
```

---

## Recipe 13: MergeQL — SQL-Like Interface

```python
import pandas as pd
from crdt_merge.mergeql import MergeQL

nyc_data = pd.DataFrame([{"id": 1, "salary": 90000, "tags": "python,ml"}])
london_data = pd.DataFrame([{"id": 1, "salary": 85000, "tags": "python,ai"}])

ql = MergeQL()
ql.register("nyc", nyc_data)
ql.register("london", london_data)

result = ql.execute("""
    MERGE nyc, london
    ON id
    STRATEGY salary='max', tags='union'
""")
print(result.data)
# id=1, salary=90000 (max), tags="ai,ml,python" (union)
```

---

## Recipe 14: Row-Level Merge (No DataFrames)

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet

schema = MergeSchema(
    default=LWW(),
    score=MaxWins(),
    tags=UnionSet(","),
)

row_a = {"id": 1, "score": 80, "tags": "python,ml", "ts": 1000}
row_b = {"id": 1, "score": 95, "tags": "python,ai", "ts": 999}

merged = schema.resolve_row(row_a, row_b, timestamp_col="ts")
print(merged["score"])   # 95 — MaxWins ignores timestamp
print(merged["tags"])    # "ai,ml,python" — UnionSet
print(merged["id"])      # 1 — equal values, no conflict
```

---

## Recipe 15: Verify CRDT Properties

```python
from crdt_merge.verify import verify_crdt
from crdt_merge.core import GCounter, LWWRegister, ORSet, PNCounter

for cls in [GCounter, PNCounter, LWWRegister, ORSet]:
    result = verify_crdt(cls, trials=100)
    passed = (result.commutativity.passed and
              result.associativity.passed and
              result.idempotency.passed)
    print(f"{cls.__name__}: {'✅ PASS' if passed else '❌ FAIL'}")
```
