# First Merge Tutorial

## Step 1: Create Sample Data

Imagine two database replicas that diverged:

```python
import pandas as pd

# Replica A (West Coast server)
west = pd.DataFrame({
    "user_id": [1, 2, 3],
    "name": ["Alice", "Bob", "Charlie"],
    "score": [85, 70, 90],
    "tags": ["python,ml", "java", "rust,go"],
    "status": ["active", "draft", "review"],
    "updated_at": [1000.0, 1000.0, 1500.0]
})

# Replica B (East Coast server)
east = pd.DataFrame({
    "user_id": [1, 2, 4],
    "name": ["Alicia", "Bobby", "Diana"],
    "score": [80, 75, 95],
    "tags": ["python,ai", "java,spring", "go"],
    "status": ["active", "review", "published"],
    "updated_at": [900.0, 1100.0, 1000.0]
})
```

## Step 2: Define Merge Schema

```python
from crdt_merge import MergeSchema, LWW, MaxWins, UnionSet, Priority

schema = MergeSchema(
    default=LWW(),  # Default: last-writer-wins
    name=LWW(),
    score=MaxWins(),  # Higher score always wins
    tags=UnionSet(separator=","),  # Union of all tags
    status=Priority(["draft", "review", "active", "published"]),  # Higher status wins
)
```

## Step 3: Merge

```python
from crdt_merge import merge

result = merge(west, east, key="user_id", schema=schema, timestamp_col="updated_at")
print(result)
```

**Result**:
| user_id | name | score | tags | status | updated_at |
|---------|------|-------|------|--------|------------|
| 1 | Alice | 85 | ai,ml,python | active | 1000.0 |
| 2 | Bobby | 75 | java,spring | review | 1100.0 |
| 3 | Charlie | 90 | rust,go | review | 1500.0 |
| 4 | Diana | 95 | go | published | 1000.0 |

**What happened**:
- **User 1**: name="Alice" (west, ts=1000 > 900), score=85 (MaxWins), tags merged, status="active" (higher priority)
- **User 2**: name="Bobby" (east, ts=1100 > 1000), score=75 (MaxWins), tags merged, status="review" (higher priority)
- **User 3**: Only in west → included as-is
- **User 4**: Only in east → included as-is

## Step 4: Verify CRDT Properties

```python
# Order doesn't matter!
result_1 = merge(west, east, key="user_id", schema=schema, timestamp_col="updated_at")
result_2 = merge(east, west, key="user_id", schema=schema, timestamp_col="updated_at")

# merge() doesn't guarantee row order, so sort by key before comparing
r1 = result_1.sort_values("user_id").reset_index(drop=True)
r2 = result_2.sort_values("user_id").reset_index(drop=True)
assert r1.equals(r2)  # Commutative!
```
