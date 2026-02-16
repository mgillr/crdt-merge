# Basic Merging Recipes

## Recipe 1: Simple DataFrame Merge

```python
import pandas as pd
from crdt_merge import merge

df_a = pd.DataFrame({"id": [1], "value": ["a"]})
df_b = pd.DataFrame({"id": [1], "value": ["b"]})

result = merge(df_a, df_b, key="id")  # Default: LWW for all fields
```

## Recipe 2: Multi-Strategy Merge

```python
from crdt_merge import merge, MergeSchema, LWW, MaxWins, UnionSet

schema = MergeSchema(
    name=LWW(),
    score=MaxWins(),
    tags=UnionSet(separator=",")
)

result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="_ts")
```

## Recipe 3: Merge with Provenance

```python
import pandas as pd
from crdt_merge import MergeSchema, LWW, MaxWins
from crdt_merge.provenance import merge_with_provenance

df_a = pd.DataFrame({"id": [1], "name": ["Alice"], "score": [80]})
df_b = pd.DataFrame({"id": [1], "name": ["Bob"], "score": [90]})

schema = MergeSchema(name=LWW(), score=MaxWins())

result, provenance = merge_with_provenance(
    df_a, df_b, key="id", schema=schema
)
# provenance is a ProvenanceLog that tells you where each value came from
print(provenance.summary())
```

## Recipe 4: JSON/Dict Merge

```python
from crdt_merge.json_merge import merge_dicts

dict_a = {"name": "Alice", "score": 80, "tags": ["python"]}
dict_b = {"name": "Bob", "score": 90, "tags": ["java"]}

# Without timestamps: scalar fields use LWW (b wins), lists are concat+dedup
result = merge_dicts(dict_a, dict_b)

# With timestamps: control which side wins per key
timestamps_a = {"name": 3.0, "score": 1.0, "tags": 1.0}
timestamps_b = {"name": 2.0, "score": 2.0, "tags": 2.0}

result = merge_dicts(dict_a, dict_b, timestamps_a=timestamps_a, timestamps_b=timestamps_b)
# result: {"name": "Alice", "score": 90, "tags": ["python", "java"]}
```

## Recipe 5: Merge Multiple DataFrames

```python
from functools import reduce
from crdt_merge import merge

dfs = [df_a, df_b, df_c, df_d]
result = reduce(lambda a, b: merge(a, b, key="id", schema=schema), dfs)
# CRDT associativity guarantees correctness regardless of reduce order
```
