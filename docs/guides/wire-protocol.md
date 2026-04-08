# Wire Protocol Deep Dive

Binary interchange format used by all four language implementations (Python, TypeScript, Rust, Java). Cross-language compatible. All APIs verified against `crdt_merge/wire.py`.

---

## Format Specification

```
[automatic:4][VERSION:2][TYPE:1][FLAGS:1][LENGTH:4][PAYLOAD:N]

automatic:   b'CRDT' (4 bytes, ASCII)
VERSION: Protocol version, uint16 big-endian. Current: 1
TYPE:    Type tag identifying the CRDT type (uint8)
FLAGS:   Bit flags: bit 0 = zlib compressed (uint8)
LENGTH:  Payload length, uint32 big-endian (max 4 GB)
PAYLOAD: Binary-encoded data (custom compact format)
```

**Header size**: 12 bytes (always).

**Byte order**: Big-endian for all multi-byte fields.

---

## Type Tags

| Type Tag | Hex | CRDT Type |
|---|---|---|
| `g_counter` | `0x01` | `GCounter` |
| `pn_counter` | `0x02` | `PNCounter` |
| `lww_register` | `0x03` | `LWWRegister` |
| `or_set` | `0x04` | `ORSet` |
| `lww_map` | `0x05` | `LWWMap` |
| `delta` | `0x10` | Delta (sync optimization) |
| `hll` | `0x30` | `MergeableHLL` |
| `bloom` | `0x31` | `MergeableBloom` |
| `cms` | `0x32` | `MergeableCMS` |
| `vector_clock` | `0x40` | `VectorClock` |
| `dotted_version_vector` | `0x41` | `DottedVersionVector` |
| `merkle_tree` | `0x42` | `MerkleTree` |
| `gossip_state` | `0x43` | `GossipState` |
| `gossip_entry` | `0x44` | `GossipEntry` |
| `mergeql_query` | `0x50` | MergeQL query |
| `merge_plan` | `0x51` | Merge plan |
| `generic` | `0x20` | Any JSON-serializable dict/list |

---

## Payload Encoding

The payload uses a compact binary encoding for Python primitives:

| Tag | Hex | Python type | Size |
|---|---|---|---|
| `NONE` | `0x00` | `None` | 1 byte |
| `TRUE` | `0x01` | `True` | 1 byte |
| `FALSE` | `0x02` | `False` | 1 byte |
| `INT64` | `0x03` | `int` (large) | 9 bytes |
| `FLOAT64` | `0x04` | `float` | 9 bytes |
| `STR` | `0x05` | `str` | 5 + N bytes |
| `BYTES` | `0x06` | `bytes` | 5 + N bytes |
| `LIST` | `0x07` | `list`, `tuple` | 5 + elements |
| `DICT` | `0x08` | `dict` | 5 + pairs |
| `SMALLINT` | `0x09` | `int` (−128..127) | 2 bytes |
| `SET` | `0x0A` | `set` | 5 + elements |

---

## Basic Usage

```python
from crdt_merge.wire import serialize, deserialize, peek_type, wire_size, WireError

# Serialize any CRDT or serializable object
from crdt_merge.core import GCounter, ORSet, LWWRegister, PNCounter

counter = GCounter()
counter.increment("node_a", 10)
counter.increment("node_b", 7)

data = serialize(counter)
print(f"Type: {peek_type(data)}")      # "g_counter"

info = wire_size(data)
print(info)
# {"total_bytes": 28, "header_bytes": 12, "payload_bytes": 16, "compressed": False}

restored = deserialize(data)
print(type(restored))                   # <class 'crdt_merge.core.GCounter'>
print(restored.value)                   # 17
```

---

## Serializing All CRDT Types

```python
from crdt_merge.wire import serialize, deserialize
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
import time

# GCounter
gc = GCounter(); gc.increment("a", 5); gc.increment("b", 3)
assert deserialize(serialize(gc)).value == 8

# PNCounter
pn = PNCounter(); pn.increment("a", 10); pn.decrement("b", 3)
assert deserialize(serialize(pn)).value == 7

# LWWRegister
reg = LWWRegister(value="hello", timestamp=time.time(), node_id="node1")
restored_reg = deserialize(serialize(reg))
assert restored_reg.value == "hello"

# ORSet
s = ORSet(); s.add("x"); s.add("y"); s.remove("x")
restored_set = deserialize(serialize(s))
assert restored_set.value == {"y"}

# LWWMap
m = LWWMap(node_id="node1")
m.set("key", "value", timestamp=time.time())
restored_map = deserialize(serialize(m))
assert restored_map.get("key") == "value"
```

---

## Probabilistic Types

```python
from crdt_merge.wire import serialize, deserialize
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS

# HyperLogLog
hll = MergeableHLL()
for i in range(10000):
    hll.add(f"item_{i}")
data = serialize(hll)
restored = deserialize(data)
print(f"Cardinality estimate: {restored.cardinality()}")

# Bloom filter
bloom = MergeableBloom(capacity=10000, error_rate=0.01)
bloom.add("user:alice"); bloom.add("user:bob")
data = serialize(bloom)
restored = deserialize(data)
assert restored.contains("user:alice")

# Count-Min Sketch
cms = MergeableCMS()
cms.update("event_a", 5); cms.update("event_b", 3)
data = serialize(cms)
restored = deserialize(data)
print(f"event_a count: {restored.estimate('event_a')}")
```

---

## Compression

The wire format supports optional zlib compression (FLAGS bit 0):

```python
from crdt_merge.wire import serialize, deserialize, wire_size
from crdt_merge.core import ORSet

# Large ORSet — compression helps significantly
s = ORSet()
for i in range(1000):
    s.add(f"user:user_{i:05d}")

# Without compression (default)
data_plain = serialize(s)
info_plain = wire_size(data_plain)

# Note: compression is applied automatically when payload exceeds threshold
# Check if compressed:
print(f"Compressed: {info_plain['compressed']}")

# Manual inspection of header flags:
import struct
automatic, version, type_tag, flags, length = struct.unpack('>4sHBBI', data_plain[:12])
compressed = bool(flags & 0x01)
print(f"Flags byte: {flags:#04x}, compressed: {compressed}")
```

---

## Batch Protocol

Transmit multiple CRDT objects in a single packet:

```python
from crdt_merge.wire import serialize_batch, deserialize_batch
from crdt_merge.core import GCounter, LWWRegister
import time

objects = [
    GCounter(),
    LWWRegister(value="hello", timestamp=time.time(), node_id="n1"),
    GCounter(),
]
objects[0].increment("a", 5)
objects[2].increment("b", 3)

# Serialize all objects in one batch payload
batch_data = serialize_batch(objects)

# Deserialize — returns list of restored objects
restored = deserialize_batch(batch_data)
print(type(restored[0]))   # GCounter
print(type(restored[1]))   # LWWRegister
```

---

## Version Negotiation

```python
from crdt_merge.wire import supported_versions

# Query which protocol versions this implementation supports
versions = supported_versions()
print(versions)   # {1}  — currently only v1

# For cross-language handshakes: exchange versions before sending payloads
# Pick the highest mutually supported version
```

---

## Error Handling

```python
from crdt_merge.wire import deserialize, peek_type, WireError

# Bad automatic bytes
try:
    deserialize(b'\x00\x00\x00\x00rest')
except WireError as e:
    print(f"Error: {e}")   # "Invalid automatic bytes"

# Truncated header
try:
    deserialize(b'CRDT')
except WireError as e:
    print(f"Error: {e}")   # "Data too short to contain header"

# Unknown type tag
try:
    peek_type(b'CRDT\x00\x01\xFF\x00\x00\x00\x00\x05hello')
except WireError as e:
    print(f"Error: {e}")   # "Unknown type tag"

# Correct: check type before deserializing
data = serialize(my_counter)
type_str = peek_type(data)   # e.g., "g_counter"
if type_str == "g_counter":
    counter = deserialize(data)
```

---

## Cross-Language Interoperability

The wire format is identical across all four implementations:

| Language | Package |
|---|---|
| Python | `crdt-merge` (this library) |
| TypeScript | `crdt-merge-ts` |
| Rust | `crdt-merge-rs` |
| Java | `crdt-merge-jvm` |

**Interop example** (Python serializes, TypeScript deserializes):
```python
# Python: serialize GCounter to binary file
from crdt_merge.wire import serialize
from crdt_merge.core import GCounter

gc = GCounter()
gc.increment("python_node", 42)

with open("state.bin", "wb") as f:
    f.write(serialize(gc))
```

The TypeScript implementation reads `state.bin` using the same `automatic + VERSION + TYPE + FLAGS + LENGTH + PAYLOAD` format.

---

## Wire Size Limits

```python
from crdt_merge.wire import wire_size, WireError

MAX_PAYLOAD_BYTES = 4 * 1024**3   # 4 GB

# Check before serializing large objects
info = wire_size(my_large_data)
if info["payload_bytes"] > MAX_PAYLOAD_BYTES:
    raise ValueError("Object too large for wire format — split into chunks")
```

For objects near the size limit, use streaming serialization:
```python
from crdt_merge.streaming import merge_sorted_stream
# Stream results directly to a socket or file instead of accumulating in memory
```

### E4 Trust Layer

The proof-carrying operation (PCO) wire format is a fixed 128 bytes containing originator ID, signing function binding, Merkle root, clock snapshot, trust vector hash, and delta bounds. PCO build throughput is 167K ops/s; verification throughput is 101K ops/s. PCOs are appended to existing wire messages with no changes to the base serialisation format. See [E4 Architecture](../e4/E4-MASTER-ARCHITECTURE.md) for details.

---

## Integration with Gossip Protocol

The wire module is the serialization backend for gossip-based sync:

```python
from crdt_merge.gossip import GossipState
from crdt_merge.wire import serialize, deserialize

state = GossipState(node_id="node1")
state.update("key", {"value": 42})

# Serialize full state for transmission
raw = serialize(state)
print(f"Gossip state wire size: {len(raw)} bytes")

# Peer deserializes and merges
peer_state = GossipState(node_id="node2")
remote_state = deserialize(raw)
peer_state.merge_remote(raw)
```

See [Gossip & Serverless Sync](gossip-serverless-sync.md) for the full gossip protocol guide.
See [Delta Sync & Merkle Verification](delta-sync-merkle-verification.md) for bandwidth-efficient sync.
