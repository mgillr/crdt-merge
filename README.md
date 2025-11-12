# crdt-merge

**The Merge Algebra Toolkit** — composable, streaming, verified, auditable CRDT merge for datasets.

[![PyPI](https://img.shields.io/badge/pypi-v0.5.0-orange)](https://pypi.org/project/crdt-merge/0.5.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-423%20passed-brightgreen)](tests/)

> Define your schema. Compose your strategies. Merge your data. Prove it's correct. Audit where every value came from. Stream it at any scale. Serialize across languages. Zero dependencies.

---

**Navigation:** [What's New in v0.5.0](#-whats-new-in-v050) · [Quick Start](#-quick-start) · [Wire Format](#-cross-language-wire-format) · [Probabilistic CRDTs](#-probabilistic-crdts) · [Provenance](#-merge-provenance--audit-trails) · [Verified Merge](#-verified-merge-decorator) · [Strategies](#-composable-merge-strategies) · [Streaming](#-streaming-merge) · [Benchmarks](#-benchmarks) · [Test Results](TEST_RESULTS.md) · [API Reference](#-api-reference)

---

## 🆕 What's New in v0.5.0

**"The Protocol Release"** — Cross-language interop + probabilistic data structures with CRDT merge semantics.

| Feature | Description | Lines |
|---------|-------------|-------|
| 🔌 **Cross-Language Wire Format** | Binary serialize/deserialize all CRDT types — polyglot interop | 475 |
| 🎲 **Probabilistic CRDTs** | MergeableHLL, MergeableBloom, MergeableCMS — approximate at scale | 493 |

### New capabilities:

```python
# Wire Format — serialize any CRDT to bytes, deserialize in any language
from crdt_merge import serialize, deserialize, GCounter

gc = GCounter("node1")
gc.increment("node1", 100)
wire_bytes = serialize(gc, compress=True)  # compact binary
restored = deserialize(wire_bytes)         # → GCounter with value 100

# Probabilistic CRDTs — space-efficient merge across distributed nodes
from crdt_merge import MergeableHLL, MergeableBloom, MergeableCMS

# HyperLogLog: estimate unique counts across nodes
hll_a = MergeableHLL(precision=14)
hll_a.add_all(node_a_user_ids)
hll_b = MergeableHLL(precision=14)
hll_b.add_all(node_b_user_ids)
merged = hll_a.merge(hll_b)  # register-max → CRDT
print(f"~{merged.cardinality():.0f} unique users (±0.81%)")

# Bloom filter: distributed membership testing
bloom_a = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom_a.add_all(blocked_ips_node_a)
bloom_b = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom_b.add_all(blocked_ips_node_b)
merged = bloom_a.merge(bloom_b)  # bitwise OR → CRDT
print(merged.contains("192.168.1.1"))
```

### Complete feature matrix:

| Module | Feature | Version | CRDT Properties |
|--------|---------|---------|-----------------|
| `core` | GCounter, PNCounter, LWWRegister, ORSet, LWWMap | v0.1.0 | ✅ C/A/I |
| `dataframe` | `merge()`, `diff()` — list-of-dict merge | v0.1.0 | ✅ C/A/I |
| `dedup` | Exact, fuzzy, MinHash deduplication | v0.1.0 | — |
| `json_merge` | `merge_dicts()`, `merge_json_lines()` | v0.1.0 | ✅ C/A/I |
| `strategies` | 8 composable strategies + `MergeSchema` DSL | v0.3.0 | ✅ C/A/I |
| `streaming` | `merge_stream()`, `merge_sorted_stream()` | v0.3.0 | ✅ C/A/I |
| `delta` | Delta-state sync, `DeltaStore`, delta composition | v0.3.0 | ✅ C/A/I |
| `provenance` | `merge_with_provenance()`, audit trail, export JSON/CSV | v0.4.0 | — |
| `verify` | `@verified_merge` decorator, property-based testing | v0.4.0 | — |
| **`wire`** | **`serialize()`/`deserialize()` — binary wire format** | **v0.5.0** | **—** |
| **`probabilistic`** | **MergeableHLL, MergeableBloom, MergeableCMS** | **v0.5.0** | **✅ C/A/I** |

*C = Commutative, A = Associative, I = Idempotent*

---

## 🚀 Quick Start

```bash
pip install crdt-merge
```

```python
from crdt_merge import merge, GCounter

# Merge two datasets — second argument wins conflicts
merged = merge(
    [{"id": 1, "name": "Alice", "score": 100}],
    [{"id": 1, "name": "Alice", "score": 150}],
    key="id"
)
# → [{"id": 1, "name": "Alice", "score": 150}]

# Or use CRDT primitives
a = GCounter("node_a")
a.increment("node_a", 10)
b = GCounter("node_b")
b.increment("node_b", 5)
merged = a.merge(b)
print(merged.value)  # 15
```

---

## 🔌 Cross-Language Wire Format

*New in v0.5.0*

Binary interchange format for polyglot distributed systems. Serialize any CRDT type in Python, deserialize in TypeScript, Rust, or Java (and vice versa).

```python
from crdt_merge import serialize, deserialize, peek_type, wire_size
from crdt_merge import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

# Serialize any CRDT type
gc = GCounter("node1")
gc.increment("node1", 42)
data = serialize(gc)                    # 40 bytes
data_compressed = serialize(gc, compress=True)  # ~30 bytes with zlib

# Peek at type without deserializing (for routing)
peek_type(data)   # → 'g_counter'
wire_size(data)   # → {'total_bytes': 40, 'type_name': 'g_counter', ...}

# Deserialize back to the correct Python type
restored = deserialize(data)
assert isinstance(restored, GCounter)
assert restored.value == 42

# Batch serialize/deserialize multiple objects
from crdt_merge import serialize_batch, deserialize_batch

objects = [GCounter("a"), PNCounter(), LWWRegister("hello", 1.0)]
batch_data = serialize_batch(objects, compress=True)
restored_objects = deserialize_batch(batch_data)
```

### Wire Format Specification

```
[MAGIC:4][VERSION:2][TYPE:1][FLAGS:1][LENGTH:4][PAYLOAD:N]

MAGIC:   b'CRDT' (4 bytes)
VERSION: Protocol version (uint16 big-endian, currently 1)
TYPE:    CRDT type tag (uint8)
FLAGS:   bit 0 = zlib compressed
LENGTH:  Payload length (uint32 big-endian)
PAYLOAD: Compact binary-encoded data
```

**Supported types:** GCounter (0x01), PNCounter (0x02), LWWRegister (0x03), ORSet (0x04), LWWMap (0x05), Delta (0x10), Generic dict/list (0x20).

---

## 🎲 Probabilistic CRDTs

*New in v0.5.0*

Approximate data structures that trade exact precision for massive space savings — while maintaining **all CRDT properties** (commutativity, associativity, idempotency). Perfect for distributed analytics without central aggregation.

### MergeableHLL — Cardinality Estimation

```python
from crdt_merge import MergeableHLL

# Count unique users across distributed nodes
hll_a = MergeableHLL(precision=14)  # 16 KB, ±0.81% error
hll_a.add_all(range(100_000))

hll_b = MergeableHLL(precision=14)
hll_b.add_all(range(50_000, 150_000))

merged = hll_a.merge(hll_b)  # register-max: natural CRDT
print(f"Unique items: ~{merged.cardinality():.0f}")  # ~150,000

# CRDT properties hold
assert hll_a.merge(hll_b) == hll_b.merge(hll_a)          # commutative
assert hll_a.merge(hll_a) == hll_a                         # idempotent
```

### MergeableBloom — Membership Testing

```python
from crdt_merge import MergeableBloom

# Distributed blocklist across edge nodes
bloom_a = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom_a.add_all(blocked_ips_from_node_a)

bloom_b = MergeableBloom(capacity=1_000_000, fp_rate=0.01)
bloom_b.add_all(blocked_ips_from_node_b)

merged = bloom_a.merge(bloom_b)  # bitwise OR: natural CRDT
merged.contains("10.0.0.1")      # True if blocked on either node
```

### MergeableCMS — Frequency Estimation

```python
from crdt_merge import MergeableCMS

# Track request counts across nodes
cms_a = MergeableCMS(width=2000, depth=7)
cms_a.add("/api/users", count=1500)
cms_a.add("/api/orders", count=800)

cms_b = MergeableCMS(width=2000, depth=7)
cms_b.add("/api/users", count=2000)

merged = cms_a.merge(cms_b)  # per-cell max: natural CRDT
merged.estimate("/api/users")   # → 2000 (max of 1500, 2000)
```

### Why These Are CRDTs

| Structure | Merge Op | Commutative | Associative | Idempotent |
|-----------|----------|:-----------:|:-----------:|:----------:|
| HyperLogLog | register max | ✅ | ✅ | ✅ |
| Bloom Filter | bitwise OR | ✅ | ✅ | ✅ |
| Count-Min Sketch | cell max | ✅ | ✅ | ✅ |

---

## 🔍 Merge Provenance & Audit Trails

*New in v0.4.0*

Track every merge decision with a full audit trail — critical for compliance (GDPR, SOX), healthcare, and finance.

```python
from crdt_merge import merge_with_provenance, MergeSchema, strategies as s

schema = MergeSchema(score=s.MaxWins(), tags=s.UnionSet())

log = merge_with_provenance(
    [{"id": 1, "name": "Alice", "score": 100, "tags": "a,b"}],
    [{"id": 1, "name": "Bob",   "score": 200, "tags": "b,c"}],
    key="id", schema=schema
)

for record in log.records:
    print(f"Conflicts: {record.conflict_count}")
    for field, decision in record.decisions.items():
        print(f"  {field}: winner={decision.winner}, strategy={decision.strategy}")

# Export audit trail
from crdt_merge import export_provenance
export_provenance(log, "audit.json", format="json")
export_provenance(log, "audit.csv", format="csv")
```

---

## ✅ Verified Merge Decorator

*New in v0.4.0*

Prove your custom merge function satisfies CRDT properties at runtime — catch bugs before they reach production.

```python
from crdt_merge import verified_merge

@verified_merge(samples=1000)
def priority_merge(a, b):
    priority = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
    return a if priority.get(a, 0) >= priority.get(b, 0) else b
# ✅ Verified: commutative, associative, idempotent

@verified_merge(samples=1000)
def broken_merge(a, b):
    return a  # Always returns left — NOT commutative!
# ❌ CRDTVerificationError: Commutativity check failed
```

---

## 🎛 Composable Merge Strategies

*Since v0.3.0*

Define per-field conflict resolution with a declarative schema DSL.

```python
from crdt_merge import MergeSchema, strategies as s

schema = MergeSchema(
    name=s.LWW(),                              # Last writer wins
    tags=s.UnionSet(),                          # Merge as set union
    view_count=s.MaxWins(),                     # Higher value wins
    price=s.MinWins(),                          # Lower value wins
    description=s.LongestWins(),                # Longer string wins
    status=s.Priority(['active', 'pending', 'archived']),
    features=s.Custom(my_resolver),             # Your function
)

merged = schema.merge(record_a, record_b)
```

**8 built-in strategies:** LWW, MaxWins, MinWins, UnionSet, Concat, Priority, LongestWins, Custom.

---

## ⚡ Streaming Merge

*Since v0.3.0 — 16x faster in v0.4.0*

Merge datasets of any size with constant memory. No need to load everything into RAM.

```python
from crdt_merge import merge_stream

for batch in merge_stream(source_a, source_b, key="id", batch_size=5000):
    write_batch(batch)
    # Memory: O(batch_size), not O(n)
```

### v0.4.0 Streaming Performance

| Rows | v0.3.0 | v0.4.0 | Speedup |
|------|--------|--------|---------|
| 100K | 110K rows/s | 400K rows/s | 3.6x |
| 500K | 65K rows/s | 400K rows/s | 6.2x |
| 1M | 38K rows/s | 400K rows/s | 10.5x |
| 2M | 23K rows/s | 400K rows/s | **17.4x** |

Throughput is now **flat** regardless of dataset size — the v0.3.0 degradation curve is eliminated.

---

## 📊 Benchmarks

### Core Operations

| Operation | Throughput | Dataset |
|-----------|-----------|---------|
| GCounter merge | 1.2M ops/s | 100 nodes |
| Dict merge | 850K ops/s | 10 fields |
| Dedup (exact) | 500K items/s | 10K items |
| Streaming merge | 400K rows/s | Any size |
| ORSet operations | 200K ops/s | 10K elements |

### Version History

| Version | Codename | Modules | Lines | Tests | Key Innovation |
|---------|----------|---------|-------|-------|----------------|
| v0.1.0 | Launch | 5 | 791 | 55 | Core CRDTs + merge |
| v0.2.0 | IP Protection | 5 | 791 | 133 | Cross-language parity |
| v0.3.0 | The Schema Release | 8 | 1,578 | 133 | Strategies + Streaming + Delta |
| v0.4.0 | The Trust Release | 11 | 2,820 | 175 | Provenance + Verification + 16x streaming |
| **v0.5.0** | **The Protocol Release** | **13** | **3,790** | **412** | **Wire format + Probabilistic CRDTs** |

---

## 📚 API Reference

### Core CRDTs
| Type | Description |
|------|-------------|
| `GCounter(node_id)` | Grow-only counter, merge via max |
| `PNCounter()` | Positive-negative counter |
| `LWWRegister(value, timestamp)` | Last-writer-wins register |
| `ORSet()` | Observed-remove set (add wins) |
| `LWWMap()` | Last-writer-wins key-value map |

### Data Operations
| Function | Description |
|----------|-------------|
| `merge(a, b, key=)` | Merge two list-of-dict datasets |
| `diff(a, b, key=)` | Compute difference between datasets |
| `merge_dicts(a, b)` | Deep recursive dict merge |
| `merge_json_lines(a, b)` | Merge JSONL strings |
| `dedup(items)` | Deduplicate a list |
| `dedup_records(records, key=)` | Deduplicate records |

### Strategies
| Strategy | Behavior |
|----------|----------|
| `s.LWW()` | Last writer wins (default) |
| `s.MaxWins()` | Higher value wins |
| `s.MinWins()` | Lower value wins |
| `s.UnionSet()` | Set union of values |
| `s.Concat(sep)` | Concatenate values |
| `s.Priority(levels)` | Custom priority ordering |
| `s.LongestWins()` | Longer string wins |
| `s.Custom(fn)` | User-defined function |

### Wire Format (v0.5.0)
| Function | Description |
|----------|-------------|
| `serialize(obj, compress=)` | Serialize CRDT to bytes |
| `deserialize(data)` | Deserialize bytes to CRDT |
| `peek_type(data)` | Read type tag without deserializing |
| `wire_size(data)` | Get size info about wire data |
| `serialize_batch(objects)` | Batch serialize multiple objects |
| `deserialize_batch(data)` | Batch deserialize |

### Probabilistic CRDTs (v0.5.0)
| Class | Merge Op | Use Case |
|-------|----------|----------|
| `MergeableHLL(precision=14)` | register max | Unique counting (±0.81%) |
| `MergeableBloom(capacity, fp_rate)` | bitwise OR | Membership testing |
| `MergeableCMS(width, depth)` | cell max | Frequency estimation |

---

## 🛡 License

Apache 2.0 — see [LICENSE](LICENSE). Copyright 2026 Ryan Gillespie.

**Commercial licensing & CLA:** [rgillespie83@icloud.com](mailto:rgillespie83@icloud.com), [data@optitransfer.ch](mailto:data@optitransfer.ch)

<details>
<summary>Previous releases</summary>

### v0.4.0 — "The Trust Release"
- **Merge Provenance** — full audit trail of every merge decision
- **@verified_merge** — prove custom merge functions are valid CRDTs
- **16x streaming speedup** — flat at 400K rows/s regardless of size
- **Bug fix** — `verify_convergence` middle-out algorithm corrected

### v0.3.0 — "The Schema Release"
- **8 composable merge strategies** + `MergeSchema` DSL
- **Streaming merge pipeline** — O(batch_size) memory
- **Delta-state dataset sync** — O(changes) bandwidth
- **290% throughput improvement** (core merge: 310K → 850K ops/s)

### v0.2.0 — "IP Protection"
- Cross-language parity: Python, TypeScript, Rust, Java
- 133 tests across all implementations
- Apache 2.0 + CLA

</details>
