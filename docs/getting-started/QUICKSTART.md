# Quickstart — crdt-merge in 5 Minutes

From install to your first working merge in under 5 minutes.

---

## Install

```bash
pip install crdt-merge
```

---

## Step 1: Your First DataFrame Merge

```python
import pandas as pd
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority

# Two DataFrames with conflicting data — typical after network partition or
# multi-master replication
df_a = pd.DataFrame([
    {"id": 1, "name": "Alice",   "score": 80, "tags": "python,ml",  "status": "review",   "ts": 1000.0},
    {"id": 2, "name": "Charlie", "score": 70, "tags": "go",         "status": "draft",    "ts": 1000.0},
])

df_b = pd.DataFrame([
    {"id": 1, "name": "Bob",   "score": 90, "tags": "python,ai", "status": "approved", "ts": 2000.0},
    {"id": 3, "name": "Diana", "score": 85, "tags": "rust",      "status": "published","ts": 1000.0},
])

# Declare per-field conflict resolution
schema = MergeSchema(
    default=LWW(),                                              # catch-all: latest timestamp
    score=MaxWins(),                                            # always keep highest score
    tags=UnionSet(separator=","),                              # union tag sets
    status=Priority(["draft", "review", "approved", "published"]),  # workflow escalation
)

result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="ts")
print(result.to_string(index=False))
```

**Output**:
```
 id     name  score          tags    status       ts
  1      Bob     90  ai,ml,python  approved   2000.0
  2  Charlie     70            go     draft   1000.0
  3    Diana     85          rust published   1000.0
```

Row analysis:
- **id=1**: name="Bob" (LWW, ts=2000 > 1000), score=90 (MaxWins), tags="ai,ml,python" (UnionSet), status="approved" (Priority beats "review")
- **id=2**: Only in df_a — kept unchanged
- **id=3**: Only in df_b — kept unchanged

---

## Step 2: CRDT Primitives (No DataFrames)

For low-level distributed data structures:

```python
from crdt_merge.core import GCounter, ORSet, LWWRegister

# Grow-only counter — page views, download counts
counter_a = GCounter()
counter_b = GCounter()
counter_a.increment("node_a", 150)
counter_b.increment("node_b", 87)

merged = counter_a.merge(counter_b)
print(merged.value)   # 237 — sum of both nodes

# CRDT guarantee: merge order doesn't matter
assert counter_a.merge(counter_b).value == counter_b.merge(counter_a).value   # ✅

# Observed-Remove Set — membership lists, tags
roles = ORSet()
roles.add("admin")
roles.add("editor")
roles.remove("admin")
print(roles.value)   # {"editor"}

# LWW Register — single scalar value
from crdt_merge.core import LWWRegister
import time

email_a = LWWRegister(value="alice@old.com", timestamp=1000.0, node_id="node_a")
email_b = LWWRegister(value="alice@new.com", timestamp=1001.0, node_id="node_b")
merged_email = email_a.merge(email_b)
print(merged_email.value)   # "alice@new.com" — higher timestamp wins
```

---

## Step 3: Streaming Large Datasets

For datasets that don't fit in memory:

```python
from crdt_merge.streaming import merge_stream
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())

# Both streams must be iterables of dicts with a shared key
stream_a = ({"id": i, "val": f"a{i}", "ts": 1000} for i in range(1_000_000))
stream_b = ({"id": i, "val": f"b{i}", "ts": 2000} for i in range(500_000))

output_count = 0
for merged_record in merge_stream(stream_a, stream_b, key="id", schema=schema):
    output_count += 1
    # process merged_record without buffering all data

print(f"Processed {output_count} records")
```

---

## Step 4: Wire Protocol (Distributed Sync)

Serialize CRDT state to binary for transmission across nodes:

```python
from crdt_merge.wire import serialize, deserialize, peek_type
from crdt_merge.core import GCounter

counter = GCounter()
counter.increment("node_a", 42)

# Serialize to bytes — cross-language compatible (Python/TypeScript/Rust/Java)
data = serialize(counter)
print(f"Type: {peek_type(data)}")     # "g_counter"
print(f"Size: {len(data)} bytes")    # compact binary

# Deserialize on receiving node
restored = deserialize(data)
print(restored.value)   # 42
```

---

## Step 5: Enterprise Features

Add encryption, audit trail, and RBAC to any merge:

```python
import secrets
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

# Audit trail (tamper-evident SHA-256 chain)
audit = AuditLog(node_id="prod-node-1")
am = AuditedMerge(audit_log=audit)

result, entry = am.merge(df_a, df_b, key="id")
assert audit.verify_chain()   # cryptographic verification
print(f"Audit entries: {len(audit.get_entries())}")

# Field-level encryption
key_provider = StaticKeyProvider(secrets.token_bytes(32))
em = EncryptedMerge(key_provider=key_provider, backend="aes-256-gcm")
# em.merge(...) encrypts sensitive fields before merge and decrypts after
```

---

## Next Steps

| Goal | Guide |
|---|---|
| Understand the math | [CRDT Fundamentals](../guides/crdt-fundamentals.md) |
| All merge strategies | [Merge Strategies](../guides/merge-strategies.md) |
| Working with every primitive | [CRDT Primitives Reference](../guides/crdt-primitives-reference.md) |
| Scale to millions of rows | [Performance Tuning](../guides/performance-tuning.md) |
| ML model merging | [Federated Model Merging](../guides/federated-model-merging.md) |
| GDPR/HIPAA/SOX/EU AI Act | [Compliance Guide](../guides/compliance-guide.md) |
| Troubleshoot errors | [Troubleshooting](../guides/troubleshooting.md) |
| Architecture overview | [System Overview](../architecture/OVERVIEW.md) |
