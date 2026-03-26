# Troubleshooting Guide

Common errors, diagnostic patterns, and fixes. Every symptom links to the underlying CRDT mechanism.

---

## Merge Correctness

### Q: Merge results are not deterministic

**Symptom**: Running the same merge twice gives different results.

**Cause**: Timestamp column is missing or not passed correctly.

```python
# Wrong — no timestamp column; LWW falls back to value comparison
result = merge(df_a, df_b, key="id")

# Correct — explicit timestamp column
result = merge(df_a, df_b, key="id", timestamp_col="updated_at")
```

**Also check**: `node_a`/`node_b` are consistent across runs. LWW tie-breaking uses node IDs lexicographically.

---

### Q: Old data is winning — recent updates ignored

**Symptom**: After a merge, stale values appear in the output.

**Cause A — Invalid timestamp format**: `_safe_parse_ts()` silently converts unparseable timestamps to `0.0`.

```python
# Silent failure — "2024-13-45" is an invalid ISO date → becomes 0.0
# Any valid timestamp will beat it
df["updated_at"] = "2024-13-45"
```

**Valid timestamp formats**:
- `int` or `float` (Unix epoch seconds)
- Numeric string: `"1704067200.0"`
- ISO-8601: `"2024-01-01T12:00:00"` or `"2024-01-01T12:00:00Z"`
- `datetime` objects with `.timestamp()` method

**Diagnostic**:
```python
import warnings
warnings.filterwarnings("error", category=UserWarning)
# Now _safe_parse_ts will raise on bad timestamps instead of silently returning 0.0
result = merge(df_a, df_b, key="id", timestamp_col="updated_at")
```

**Cause B — Wrong column name**: Timestamp column doesn't exist in one frame.

```python
# Verify column exists in both frames
assert "updated_at" in df_a.columns
assert "updated_at" in df_b.columns
```

---

### Q: "node9" beats "node10" in tie-breaking

**Symptom**: Unexpected winner when timestamps are identical.

**Cause**: Tie-breaking uses lexicographic string comparison. `"node9" > "node10"` because `"9" > "1"` character-by-character.

**Fix**: Zero-pad numeric suffixes:

```python
# Bad
node_ids = ["node1", "node2", ..., "node10"]

# Good
node_ids = [f"node{i:03d}" for i in range(1, 11)]
# → "node001", "node002", ..., "node010"
```

---

### Q: ORSet remove doesn't work after a concurrent add

**Symptom**: Removed element reappears after merge.

**Cause**: This is correct ORSet (Observed-Remove Set) behaviour — **add wins over concurrent remove**.

```python
from crdt_merge.core import ORSet

a = ORSet()
b = ORSet()

a.add("x")           # A adds x
b.remove("x")        # B removes x (but B never observed A's add)

# Merge — A's add-tag survives
merged = a.merge(b)
assert "x" in merged.elements()   # add-wins is by design
```

**To force a remove after merge**, remove from the merged state:

```python
merged = a.merge(b)
merged.remove("x")   # Remove all tags including A's tag
assert "x" not in merged.elements()
```

---

### Q: Custom strategy lost after serialization round-trip

**Symptom**: `CustomStrategy` function replaced by `LWW` after `schema.to_dict()` / `schema.from_dict()`.

**Cause**: Python functions cannot be serialized to JSON/binary. This is a known limitation (LAY1-003).

**Workaround**:
```python
from crdt_merge.strategies import MergeSchema, Custom, LWW

# Re-attach custom strategy after deserialization
schema_dict = schema.to_dict()
# ... store/transmit ...
schema = MergeSchema.from_dict(schema_dict)
schema.set_strategy("my_field", Custom(fn=my_resolver))  # Re-attach
```

---

## Strategy Mismatches

### Q: `Priority` strategy returns unexpected winner

**Symptom**: Wrong value wins despite correct priority list.

**Diagnostic**:
```python
from crdt_merge.strategies import Priority

s = Priority(["draft", "review", "approved", "published"])
print(s.resolve("draft", "published"))   # → "published" (index 3 > 0) 
print(s.resolve("draft", "unknown"))     # → "draft" (unknown gets index -1)
print(s.resolve("DRAFT", "published"))  # → "published" (case-sensitive!)
```

**Fix**: Normalise values before merge, or include all variants in the priority list:

```python
s = Priority(["draft", "DRAFT", "review", "approved", "published"])
```

---

### Q: `UnionSet` produces duplicates or wrong separator

**Symptom**: Union output has duplicates or wrong delimiter.

```python
from crdt_merge.strategies import UnionSet

# Default separator is ","
s = UnionSet(separator=",")
print(s.resolve("a,b", "b,c"))   # → "a,b,c" (sorted, deduped) 

# Wrong separator — entire string treated as single element
s_bad = UnionSet(separator=";")
print(s_bad.resolve("a,b", "b,c"))  # → "a,b,b,c" (no split on comma)
```

---

### Q: `Concat` output is not stable across multiple merges

**Symptom**: Repeated merges grow the concatenated string.

**Cause**: `dedup=True` (default) deduplicates, but only exact string matches. Check for whitespace:

```python
from crdt_merge.strategies import Concat

s = Concat(separator=" | ", dedup=True)
print(s.resolve("note A", "note A "))  # → "note A | note A " — trailing space prevents dedup!

# Fix: strip values before merge, or normalise in a Custom wrapper
```

---

## Schema Conflicts

### Q: `KeyError` or `AttributeError` when merging different schema versions

**Symptom**: Merge crashes on records that have different fields.

**Cause**: New field added in one replica but not the other.

```python
# df_a has "score" field, df_b does not
# result: df_b rows will have score=NaN → safe with MaxWins/MinWins
# but Priority on NaN → str(NaN)="nan" gets rank -1 (correct but unexpected)

from crdt_merge.strategies import MergeSchema, MaxWins, LWW

schema = MergeSchema(
    default=LWW(),
    score=MaxWins(),  # NaN handled: val_a is None → returns val_b
)
result = merge(df_a, df_b, key="id", schema=schema)
```

**For additive schema changes**, see [Schema Evolution](schema-evolution.md).

---

## Serialization Issues

### Q: `WireError: Invalid automatic bytes` on deserialization

**Symptom**: `deserialize()` raises `WireError`.

**Cause A**: Data was not serialized with `crdt_merge.wire.serialize()`.

**Cause B**: Data is compressed but not flagged (or vice versa).

```python
from crdt_merge.wire import serialize, deserialize, peek_type, WireError

data = serialize(my_counter)
info = peek_type(data)          # Check type string before deserializing
print(info)                     # e.g., "gcounter"

try:
    restored = deserialize(data)
except WireError as e:
    print(f"Wire format error: {e}")
    # Check: is data actually wire-encoded?
    print(f"First 4 bytes: {data[:4]}")  # Should be b'CRDT'
```

---

### Q: `deserialize()` returns a plain dict instead of a CRDT object

**Symptom**: Result of `deserialize()` is a `dict`, not a `GCounter`/`ORSet`/etc.

**Cause**: Object was serialized as `Generic` type (type tag `0x20`). Happens when serializing a `dict` directly.

```python
from crdt_merge.wire import serialize, deserialize
from crdt_merge.core import GCounter

# Serialize the CRDT object, not its dict representation
counter = GCounter()
counter.increment("node1", 5)

data = serialize(counter)          # type tag = 0x01 (GCounter)
data_bad = serialize(counter.to_dict())  #  type tag = 0x20 (Generic dict)

restored = deserialize(data)
print(type(restored))              # <class 'crdt_merge.core.GCounter'>
```

---

## Performance Issues

### Q: Merge is slow on large DataFrames

**Symptom**: `merge()` takes many seconds on 1M+ rows.

**Solutions** (in order of impact):

```python
# 1. Use Polars — 2-5x faster than pandas
import polars as pl
df_a = pl.read_parquet("data_a.parquet")
result = merge(df_a, df_b, key="id")   # auto-detects Polars

# 2. Use parallel merge for multi-core
from crdt_merge.parallel import parallel_merge
result = parallel_merge(df_a, df_b, key="id", schema=schema, max_workers=8)

# 3. Use Arrow for columnar data
from crdt_merge.arrow import arrow_merge
import pyarrow.parquet as pq
table_a = pq.read_table("data_a.parquet")
result = arrow_merge(table_a, table_b, key="id", schema=schema)

# 4. Stream for unbounded data
from crdt_merge.streaming import merge_stream
for merged_batch in merge_stream(stream_a, stream_b, key="id"):
    process(merged_batch)
```

**DuckDB acceleration** (for SQL-resident data):

```python
from crdt_merge.accelerators.duckdb_udf import register_duckdb_udfs
import duckdb

conn = duckdb.connect()
register_duckdb_udfs(conn)
result = conn.execute("""
    SELECT crdt_lww(a.value, b.value, a.ts, b.ts) AS value
    FROM table_a a JOIN table_b b USING (id)
""").fetchdf()
```

---

### Q: `parallel_merge()` is slower than regular `merge()`

**Cause**: Dataset is below the parallelism threshold (10,000 rows). Thread overhead exceeds benefit.

```python
from crdt_merge.parallel import parallel_merge

# parallel_merge auto-falls-back to sequential for small datasets
result = parallel_merge(small_df_a, small_df_b, key="id")
# ↑ This is fine — it detects small size and runs single-threaded
```

For datasets under 100K rows, plain `merge()` is typically fastest.

---

## Import and Dependency Errors

### Q: `ModuleNotFoundError: No module named 'pyarrow'`

```bash
pip install crdt-merge[arrow]
```

### Q: `ModuleNotFoundError: No module named 'torch'`

```bash
pip install crdt-merge[model]
```

### Q: `ModuleNotFoundError: No module named 'cryptography'`

```bash
pip install crdt-merge[enterprise]
```

### Q: Install everything at once

```bash
pip install crdt-merge[all]
```

---

## Verification Failures

### Q: `verify_crdt()` reports commutativity failure for my custom strategy

**Symptom**: `result.commutativity.passed = False`

**Cause**: Custom merge function is not symmetric — `fn(a, b) != fn(b, a)`.

```python
from crdt_merge.verify import verify_crdt
from crdt_merge.strategies import Custom

# Bad: not commutative
bad = Custom(fn=lambda a, b: a)   # Always picks left — not symmetric!

# Good: commutative
good = Custom(fn=lambda a, b: max(str(a), str(b)))

from crdt_merge.core import LWWRegister
result = verify_crdt(LWWRegister, strategy=good)
print(result.commutativity.passed)   # True
```

---

## Gossip and Sync

### Q: Gossip peers not converging

**Symptom**: Different peers have different state after many rounds.

**Diagnostic**:
```python
from crdt_merge.gossip import GossipState

state = GossipState(node_id="node1")
state.update("key", "value")

# Check vector clock
print(state.vector_clock)

# Merge with peer state
peer_state = ...  # received from peer
state.merge(peer_state)

# All nodes should have the same keys after enough rounds
print(state.keys())
```

**Common cause**: Peers using different `key` fields — the join key must match across all nodes.

---

## Getting More Help

- Run `crdt-merge doctor` from the CLI to check your installation
- Check the [CRDT Primitives Reference](crdt-primitives-reference.md) for correct API signatures
- See [Performance Tuning](performance-tuning.md) for detailed benchmarks
- File issues at [mgillr/crdt-merge](https://github.com/mgillr/crdt-merge/issues)
