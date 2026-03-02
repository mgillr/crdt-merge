# Complete Merge Strategy Guide

Full reference for every built-in strategy with working code, edge cases, and CRDT property proofs. Every strategy is commutative, associative, and idempotent.

---

## Quick Reference

| Strategy | Best for | Tie-break |
|---|---|---|
| `LWW()` | Any scalar — most recent wins | Lexicographic `str(value)` |
| `MaxWins()` | Numeric or comparable values | `None` loses to non-`None` |
| `MinWins()` | Numeric or comparable values | `None` loses to non-`None` |
| `UnionSet()` | Comma-separated tag lists | N/A — always union |
| `Concat()` | Notes, comments — keep both | Sorted + deduplicated |
| `Priority()` | Workflow states with ordering | Lexicographic fallback |
| `LongestWins()` | More detailed text wins | Falls back to LWW |
| `Custom()` | None of the above | User-defined |

Import all strategies from:
```python
from crdt_merge.strategies import (
    MergeSchema, LWW, MaxWins, MinWins,
    UnionSet, Concat, Priority, LongestWins, Custom
)
```

---

## MergeSchema — Per-Field Strategy Map

The primary entry point. Attach one strategy per DataFrame column:

```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Concat, Priority

schema = MergeSchema(
    default=LWW(),                                      # catch-all
    name=LWW(),
    score=MaxWins(),
    tags=UnionSet(separator=","),
    notes=Concat(separator=" | "),
    status=Priority(["draft", "review", "approved", "published"]),
)

result = merge(df_a, df_b, key="id", schema=schema)
```

**Field lookup**:
```python
strat = schema.strategy_for("score")      # → MaxWins instance
strat = schema.strategy_for("unknown")    # → LWW (default)
schema.set_strategy("rating", MaxWins())  # Add/replace a field
print(schema.fields)                      # Dict[str, MergeStrategy]
```

**Row-level merge** (dict-to-dict, without DataFrames):
```python
row_a = {"id": 1, "score": 90, "tags": "python,ml", "updated_at": 1000.0}
row_b = {"id": 1, "score": 95, "tags": "python,ai", "updated_at": 999.0}

merged_row = schema.resolve_row(row_a, row_b, timestamp_col="updated_at")
print(merged_row["score"])   # 95 — MaxWins picks higher regardless of timestamp
print(merged_row["tags"])    # "ai,ml,python" — UnionSet: sorted union
```

**Schema serialization**:
```python
d = schema.to_dict()
# Store d as JSON, then restore
schema2 = MergeSchema.from_dict(d)
# Note: Custom strategies fall back to LWW after round-trip — re-attach manually
```

---

## LWW — Last-Writer-Wins

**Resolution**: Higher timestamp wins. Equal timestamps: `max(str(val_a), str(val_b))`.

```python
from crdt_merge.strategies import LWW

s = LWW()

# Normal case: later timestamp wins
print(s.resolve("old", "new", ts_a=1000, ts_b=1001))  # → "new"
print(s.resolve("new", "old", ts_a=1001, ts_b=1000))  # → "new" (commutative ✅)

# Tie: deterministic value comparison
print(s.resolve("alpha", "beta", ts_a=1000, ts_b=1000))  # → "beta" (b > a)
print(s.resolve("beta", "alpha", ts_a=1000, ts_b=1000))  # → "beta" (commutative ✅)

# Numeric ordering
print(s.resolve(100, 200, ts_a=1000, ts_b=1000))   # → "200" (str comparison)
```

**CRDT properties**:
```python
# Idempotent: merging same value with itself returns same value
assert s.resolve("x", "x", ts_a=5, ts_b=5) == "x"

# Commutative: swap arguments, get same result
assert s.resolve("a", "b", ts_a=1, ts_b=2) == s.resolve("b", "a", ts_a=2, ts_b=1)
```

**Timestamp format**: Any of `int`, `float`, `"1704067200.0"`, `"2024-01-01T12:00:00"`. Invalid values silently become `0.0` (with a `UserWarning`).

**Node_id tie-break** (via `node_a`/`node_b` params):
```python
# When both timestamp AND str(value) are equal, node_id is NOT used by LWW strategy
# Node_id tie-breaking is internal to LWWRegister and LWWMap primitives
# MergeSchema.resolve_row passes node_a/node_b but LWW ignores them
```

---

## MaxWins — Numeric Maximum

**Resolution**: Higher value wins. `None` always loses to any non-`None` value.

```python
from crdt_merge.strategies import MaxWins

s = MaxWins()

print(s.resolve(90, 95))      # 95
print(s.resolve(95, 90))      # 95 (commutative ✅)
print(s.resolve(None, 80))    # 80 (None loses)
print(s.resolve(80, None))    # 80 (commutative ✅)
print(s.resolve(None, None))  # None

# Works with any comparable type
print(s.resolve("2024-01-01", "2024-06-01"))  # "2024-06-01" (string compare)
print(s.resolve(3.14, 2.71))                  # 3.14
```

**Edge case — incomparable types**: Falls back to `repr` comparison:
```python
# Mixed types: deterministic but possibly surprising
print(s.resolve("text", 42))   # "text" (repr("text") > repr(42) = "'text'" vs "42")
```

**Schema example**:
```python
schema = MergeSchema(score=MaxWins(), version=MaxWins())
# Always keep the highest score, regardless of which record is newer
```

---

## MinWins — Numeric Minimum

Mirror of `MaxWins` — lower value wins.

```python
from crdt_merge.strategies import MinWins

s = MinWins()

print(s.resolve(100, 50))    # 50
print(s.resolve(50, 100))    # 50 (commutative ✅)
print(s.resolve(None, 50))   # 50 (None loses)
```

**Use cases**: expiry dates (earliest expiry wins), minimum bid price, minimum latency SLA.

```python
schema = MergeSchema(
    price=MinWins(),       # Lowest observed price wins (price oracle)
    expires_at=MinWins(),  # Earliest expiry is binding
)
```

---

## UnionSet — Set Union of Delimited Values

**Resolution**: Split both values by separator, take set union, sort, rejoin.

```python
from crdt_merge.strategies import UnionSet

s = UnionSet(separator=",")   # default separator

print(s.resolve("python,ml", "python,ai"))   # "ai,ml,python" (sorted union)
print(s.resolve("a,b,c", "b,c,d"))           # "a,b,c,d"
print(s.resolve("", "x,y"))                   # "x,y" (empty string → empty set)
print(s.resolve(None, "x"))                   # "x" (None → empty set)

# Commutativity: order doesn't matter
assert s.resolve("x,y", "y,z") == s.resolve("y,z", "x,y")   # ✅
# Idempotency: merge with self gives same result
assert s.resolve("x,y", "x,y") == "x,y"                      # ✅
```

**Custom separator**:
```python
pipe_union = UnionSet(separator="|")
print(pipe_union.resolve("red|green", "green|blue"))  # "blue|green|red"

space_union = UnionSet(separator=" ")
print(space_union.resolve("foo bar", "bar baz"))      # "bar baz foo"
```

**In DataFrame merge**:
```python
schema = MergeSchema(
    categories=UnionSet(separator=","),
    permissions=UnionSet(separator=";"),
)
result = merge(df_a, df_b, key="id", schema=schema)
```

---

## Concat — Preserve Both Values

**Resolution**: Append both values with separator, sort for commutativity, deduplicate.

```python
from crdt_merge.strategies import Concat

s = Concat(separator=" | ", dedup=True)   # defaults

print(s.resolve("First note", "Second note"))    # "First note | Second note"
print(s.resolve("Second note", "First note"))    # "First note | Second note" (sorted ✅)

# Deduplication (exact match only)
print(s.resolve("Note A", "Note A"))             # "Note A" (deduped)

# No dedup
s_nodup = Concat(separator=" | ", dedup=False)
print(s_nodup.resolve("Note A", "Note A"))       # "Note A | Note A"
```

**Custom separator**:
```python
newline_concat = Concat(separator="\n", dedup=True)
history = newline_concat.resolve("Line 1", "Line 2")
print(history)
# "Line 1\nLine 2"
```

**Idempotency**: Sorted + dedup ensures `resolve(A, A) == A`:
```python
s = Concat()
val = "note text"
assert s.resolve(val, val) == val   # ✅
```

---

## Priority — Workflow State Ordering

**Resolution**: Higher index in priority list wins. Unknown values get index -1 (always lose).

```python
from crdt_merge.strategies import Priority

s = Priority(["draft", "review", "approved", "published"])

print(s.resolve("draft", "published"))   # "published" (index 3 > 0)
print(s.resolve("published", "draft"))   # "published" (commutative ✅)
print(s.resolve("review", "approved"))   # "approved"
print(s.resolve("unknown", "draft"))     # "draft" (unknown gets -1)
print(s.resolve("unknown1", "unknown2")) # "unknown2" (lexicographic tiebreak)
```

**Case sensitivity**: Priority matching is exact-case. Normalise before merge:

```python
import pandas as pd
df["status"] = df["status"].str.lower()
schema = MergeSchema(status=Priority(["draft", "review", "approved", "published"]))
```

**Progressive escalation**: States can only advance, never retreat:
```python
# After merge: once a record is "published", it stays "published"
# even if one replica still has it as "draft"
row_a = {"id": 1, "status": "published", "updated_at": 1000}
row_b = {"id": 1, "status": "draft",     "updated_at": 2000}   # newer but lower priority

schema = MergeSchema(status=Priority(["draft", "review", "approved", "published"]))
merged = schema.resolve_row(row_a, row_b, timestamp_col="updated_at")
print(merged["status"])   # "published" — Priority overrides timestamp
```

---

## LongestWins — More Detailed Text

**Resolution**: Longer string wins. Equal lengths fall back to `LWW`.

```python
from crdt_merge.strategies import LongestWins

s = LongestWins()

print(s.resolve("hi", "hello"))              # "hello" (5 > 2)
print(s.resolve("hello", "hi"))              # "hello" (commutative ✅)
print(s.resolve("ab", "cd", ts_a=1, ts_b=2)) # "cd" (equal length → LWW, ts_b wins)
print(s.resolve(None, "text"))               # "text" (None length = 0)
```

**Use case**: Profile descriptions — keep whichever user provided more detail:
```python
schema = MergeSchema(
    bio=LongestWins(),
    description=LongestWins(),
)
```

---

## Custom — User-Defined Strategy

**Resolution**: Your function. Can accept 2 args `(val_a, val_b)` or all 6 `(val_a, val_b, ts_a, ts_b, node_a, node_b)`.

```python
from crdt_merge.strategies import Custom, MergeSchema

# Simple 2-arg function
prefer_longer = Custom(fn=lambda a, b: a if len(str(a)) >= len(str(b)) else b)

# Full 6-arg function with timestamp access
def semantic_merge(val_a, val_b, ts_a, ts_b, node_a, node_b):
    """Prefer non-None, then newer, then higher value."""
    if val_a is None:
        return val_b
    if val_b is None:
        return val_a
    if ts_a != ts_b:
        return val_a if ts_a > ts_b else val_b
    return val_a if val_a >= val_b else val_b

smart_strategy = Custom(fn=semantic_merge)

schema = MergeSchema(
    description=prefer_longer,
    score=smart_strategy,
)

row_a = {"description": "Short", "score": 90, "ts": 1000}
row_b = {"description": "Much longer description", "score": 85, "ts": 1001}
merged = schema.resolve_row(row_a, row_b, timestamp_col="ts")
print(merged["description"])  # "Much longer description"
print(merged["score"])        # 90 (ts_a=1000 < ts_b=1001 → val_b... wait, ts_b wins → 85)
```

**Warning**: Custom strategies cannot be serialized. After `schema.to_dict()` / `MergeSchema.from_dict()`, the field falls back to `LWW`. Re-attach manually:

```python
schema_dict = schema.to_dict()
restored = MergeSchema.from_dict(schema_dict)
restored.set_strategy("description", prefer_longer)   # Re-attach
```

**Verify CRDT properties** of your custom function:
```python
from crdt_merge.verify import verify_crdt
from crdt_merge.core import LWWRegister

result = verify_crdt(LWWRegister, strategy=smart_strategy)
print(result.commutativity.passed)    # Must be True
print(result.associativity.passed)    # Must be True
print(result.idempotency.passed)      # Must be True
```

---

## Nested Dict and List Handling

`resolve_row()` handles nested structures automatically:

```python
schema = MergeSchema(default=LWW(), score=MaxWins())

row_a = {"id": 1, "meta": {"score": 80, "label": "A"}, "tags": ["x", "y"]}
row_b = {"id": 1, "meta": {"score": 95, "label": "B"}, "tags": ["y", "z"]}

merged = schema.resolve_row(row_a, row_b)
# Nested dict → recursive resolve_row (unless "meta" has a registered strategy)
print(merged["meta"]["score"])   # 95 — MaxWins applies to nested "score" key
# List → element-wise merge
print(merged["tags"])            # ["x|y", "y|z"] — element 0: LWW("x","y"), element 1: LWW("y","z")
```

**Override nested dict with a strategy**: Register the parent field to bypass recursion:

```python
schema = MergeSchema(
    meta=LWW(),       # treat "meta" as opaque LWW — no recursion
)
```

---

## Strategy Selection Guide

```
Is the field a counter?
  → Grow-only: use GCounter primitive directly
  → Bidirectional: use PNCounter primitive directly

Is the field a single scalar?
  → Always take newer: LWW()
  → Always take higher number: MaxWins()
  → Always take lower number: MinWins()
  → More text detail wins: LongestWins()

Is the field a set or list of tags?
  → Comma-separated string: UnionSet(separator=",")
  → Preserve history of all values: Concat()

Is the field a state machine value?
  → Fixed progression: Priority(["state1", "state2", ...])

None of the above?
  → Custom(fn=your_function)
```

See [CRDT Verification Toolkit](crdt-verification-toolkit.md) to verify your custom strategies satisfy CRDT properties.
