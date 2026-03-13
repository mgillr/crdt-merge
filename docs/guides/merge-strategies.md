# Complete Merge Strategy Guide

## Strategy Overview

Every strategy in crdt-merge satisfies CRDT properties: commutative, associative, idempotent.

## LWW (Last-Writer-Wins)

**Use when**: You want the most recent update to win.

**Resolution logic**:
1. Compare timestamps: higher wins
2. If equal: compare `str(value)` lexicographically

**Gotcha**: `_safe_parse_ts()` silently converts invalid timestamps to 0.0. This means corrupted timestamps don't raise errors — they just lose to any valid timestamp.

## MaxWins / MinWins

**Use when**: Numeric values where higher/lower should always win.

**Resolution logic**:
1. If either is None: non-None wins
2. Try `max()`/`min()` comparison
3. If TypeError: fall back to string comparison

## UnionSet

**Use when**: Comma-separated values that should be combined.

**Configuration**: `separator` parameter (default: `,`)

**Output**: Sorted, deduplicated union of both value sets.

## Priority

**Use when**: Values have a natural ordering (e.g., workflow states).

**Configuration**: `levels` list, lowest priority first.

**Unknown values**: Get priority -1 (always lose).

## Concat

**Use when**: Both values should be preserved (e.g., notes, comments).

**Configuration**:
- `separator`: Join string (default: `" | "`)
- `dedup`: Remove duplicates (default: `True`)

## LongestWins

**Use when**: Longer/more detailed text should win.

**Tie-break**: Delegates to LWW when lengths are equal.

## Custom

**Use when**: None of the built-in strategies fit.

```python
from crdt_merge.strategies import Custom

# Simple 2-arg function
my_strategy = Custom(fn=lambda a, b: a if len(str(a)) > len(str(b)) else b)

# Full 6-arg function for timestamp access
def my_resolver(val_a, val_b, ts_a, ts_b, node_a, node_b):
    return val_a if ts_a > ts_b else val_b

my_strategy = Custom(fn=my_resolver)
```

⚠️ **Warning**: Custom strategies cannot be serialized. They will be replaced by LWW on round-trip through `to_dict()`/`from_dict()`.
