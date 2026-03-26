# wire

> Layer 3 — Sync & Transport
> Source: `crdt_merge/wire.py`  
> LOC: 601 (AST-verified)

## Overview
Cross-Language Wire Format for crdt-merge.

Binary interchange format that all 4 language implementations (Python, TypeScript,
Rust, Java) can read and write. Enables polyglot distributed systems where nodes
run different language implementations but share CRDT state.

Format specification:
    [automatic:4][VERSION:2][TYPE:1][FLAGS:1][LENGTH:4][PAYLOAD:N]

    automatic:   b'CRDT' (4 bytes)
    VERSION: Protocol version as uint16 big-endian (currently 1)
    TYPE:    Type tag identifying the CRDT type (uint8)
    FLAGS:   Bit flags — bit 0: zlib compressed (uint8)
    LENGTH:  Payload length as uint32 big-endian
    PAYLOAD: Binary-encoded data (custom compact encoding)

Type tags:
    0x01: GCounter
    0x02: PNCounter
    0x03: LWWRegister
    0x04: ORSet
    0x05: LWWMap
    0x10: Delta
    0x20: Generic (any JSON-serializable dict/list)

The payload uses a compact binary encoding for primitives:
    0x00: None
    0x01: True
    0x02: False
    0x03: int (int64 big-endian)
    0x04: float (float64 big-endian)
    0x05: str (uint32 length + UTF-8 bytes)
    0x06: bytes (uint32 length + raw bytes)
    0x07: list (uint32 count + encoded elements)
    0x08: dict (uint32 count + encoded key-value pairs)
    0x09: small int (int8, for values -128..127)
    0x0A: set (uint32 count + encoded elements)

New in v0.5.0.

## Quick Start

```python
from crdt_merge.core import GCounter, LWWRegister
from crdt_merge.wire import serialize, deserialize, peek_type, wire_size

# Serialize a CRDT object to binary wire format
counter = GCounter("node1", 10)
data = serialize(counter)
print(len(data))  # compact binary — typically ~30-50 bytes

# Peek at the type without full deserialization (useful for routing)
print(peek_type(data))  # "g_counter"

# Get size info
info = wire_size(data)
print(info)  # {'total_bytes': ..., 'compressed': False, 'type_name': 'g_counter', ...}

# Deserialize back to a Python CRDT object
restored = deserialize(data)
assert restored.value == 10

# Works with compression for large payloads
reg = LWWRegister("hello world", 1000.0, "node1")
compressed = serialize(reg, compress=True)
assert deserialize(compressed).value == "hello world"

# Batch serialize/deserialize multiple objects
from crdt_merge.wire import serialize_batch, deserialize_batch
objects = [GCounter("a", 1), GCounter("b", 2), LWWRegister("x", 1.0)]
batch_data = serialize_batch(objects)
restored_list = deserialize_batch(batch_data)
```

## Classes

### `WireError(Exception)`

Raised on serialization/deserialization errors.

---

## Functions

### `_get_delta_module()`

Lazily imports and caches the `crdt_merge.delta` module to avoid circular imports between `wire.py` and `delta.py`. Returns the cached module reference on subsequent calls. This is the highest-entropy chokepoint (H=0.97) in the wire serialization pipeline — all Delta serialization/deserialization flows through it.

### `_is_delta(obj)`

Check if obj is a Delta without circular import.

| Parameter | Type | Default |
|-----------|------|---------|
| `obj` | `—` | `—` |

### `_encode_value(val: Any) -> bytes`

Encode a Python value to compact binary.

| Parameter | Type | Default |
|-----------|------|---------|
| `val` | `Any` | `—` |

### `_decode_value(data: bytes, offset: int) -> tuple`

Decode a value from binary data at the given offset. Returns (value, new_offset).

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `bytes` | `—` |
| `offset` | `int` | `—` |

### `_encode_json_payload(data: dict) -> bytes`

DEF-023: Encode payload using msgpack if available, else JSON.

msgpack produces smaller payloads and is faster to encode/decode.
Falls back to JSON transparently for backwards compatibility.

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `dict` | `—` |

### `_decode_json_payload(payload: bytes) -> dict`

DEF-023: Decode payload — tries msgpack first, falls back to JSON.

This ensures backward compatibility: payloads encoded with JSON
can still be read even when msgpack is available, and vice versa.

| Parameter | Type | Default |
|-----------|------|---------|
| `payload` | `bytes` | `—` |

### `_build_wire_frame(type_tag: int, payload: bytes, compress: bool = False) -> bytes`

Build a wire-format frame for v0.6.0+ encoded types.

Args:
    type_tag: The type tag byte.
    payload: Encoded payload bytes (msgpack or JSON).
    compress: If True, apply zlib compression.

Returns:
    bytes: Complete wire-format frame.

| Parameter | Type | Default |
|-----------|------|---------|
| `type_tag` | `int` | `—` |
| `payload` | `bytes` | `—` |
| `compress` | `bool` | `False` |

### `serialize(obj: Any, *, compress: bool = False) -> bytes`

Serialize a CRDT object to the wire format.

Supports: GCounter, PNCounter, LWWRegister, ORSet, LWWMap, Delta,
and any dict/list (as generic).

Args:
    obj: The object to serialize.
    compress: If True, apply zlib compression to the payload.

Returns:
    bytes: The wire-format encoded data.

Raises:
    WireError: If the object type is not supported.

Examples:
    >>> from crdt_merge import GCounter
    >>> from crdt_merge.wire import serialize, deserialize
    >>> gc = GCounter("node1")
    >>> gc.increment("node1", 5)
    >>> data = serialize(gc)
    >>> gc2 = deserialize(data)
    >>> gc2.value == gc.value
    True

| Parameter | Type | Default |
|-----------|------|---------|
| `obj` | `Any` | `—` |
| `compress` | `bool` | `False` |

### `deserialize(data: bytes) -> Any`

Deserialize a CRDT object from wire format bytes.

Returns the appropriate Python CRDT type (GCounter, PNCounter, etc.)
or a plain dict/list for generic data.

Args:
    data: Wire-format bytes to deserialize.

Returns:
    The deserialized CRDT object.

Raises:
    WireError: If the data is invalid or corrupted.

Examples:
    >>> from crdt_merge import GCounter
    >>> from crdt_merge.wire import serialize, deserialize
    >>> gc = GCounter("node1")
    >>> gc.increment("node1", 10)
    >>> data = serialize(gc)
    >>> restored = deserialize(data)
    >>> isinstance(restored, GCounter)
    True
    >>> restored.value
    10

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `bytes` | `—` |

### `peek_type(data: bytes) -> str`

Read the type tag from wire format bytes without deserializing.

Useful for routing messages to the correct handler without
paying the full deserialization cost.

Args:
    data: Wire-format bytes.

Returns:
    str: The CRDT type name (e.g., 'g_counter', 'lww_register', 'generic').

Raises:
    WireError: If the data is invalid.

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `bytes` | `—` |

### `wire_size(data: bytes) -> dict`

Get size information about wire-format data without deserializing.

Args:
    data: Wire-format bytes.

Returns:
    dict with keys: total_bytes, header_bytes, payload_bytes,
    compressed, protocol_version, type_name.

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `bytes` | `—` |

### `serialize_batch(objects: list, *, compress: bool = False) -> bytes`

Serialize multiple CRDT objects into a single byte stream.

Format: [COUNT:4][SIZE1:4][OBJ1][SIZE2:4][OBJ2]...

Args:
    objects: List of CRDT objects to serialize.
    compress: If True, compress each object's payload.

Returns:
    bytes: The concatenated wire-format data.

| Parameter | Type | Default |
|-----------|------|---------|
| `objects` | `list` | `—` |
| `compress` | `bool` | `False` |

### `deserialize_batch(data: bytes) -> list`

Deserialize multiple CRDT objects from a batch byte stream.

Args:
    data: Batch wire-format bytes.

Returns:
    list: The deserialized objects.

| Parameter | Type | Default |
|-----------|------|---------|
| `data` | `bytes` | `—` |

## Constants

| Name | Type | Value |
|------|------|-------|
| `automatic` | `—` | `b'CRDT'` |
| `PROTOCOL_VERSION` | `—` | `1` |
| `TAG_GCOUNTER` | `—` | `1` |
| `TAG_PNCOUNTER` | `—` | `2` |
| `TAG_LWWREGISTER` | `—` | `3` |
| `TAG_ORSET` | `—` | `4` |
| `TAG_LWWMAP` | `—` | `5` |
| `TAG_DELTA` | `—` | `16` |
| `TAG_GENERIC` | `—` | `32` |
| `TAG_HLL` | `—` | `48` |
| `TAG_BLOOM` | `—` | `49` |
| `TAG_CMS` | `—` | `50` |
| `TAG_VECTOR_CLOCK` | `—` | `64` |
| `TAG_DOTTED_VERSION_VECTOR` | `—` | `65` |
| `TAG_MERKLE_TREE` | `—` | `66` |
| `TAG_GOSSIP_STATE` | `—` | `67` |
| `TAG_GOSSIP_ENTRY` | `—` | `68` |
| `TAG_SCHEMA_EVOLUTION_RESULT` | `—` | `69` |
| `TAG_SCHEMA_CHANGE` | `—` | `70` |
| `TAG_MERKLE_DIFF` | `—` | `71` |
| `TAG_MERGEQL_QUERY` | `—` | `80` |
| `TAG_MERGE_PLAN` | `—` | `81` |
| `TAG_MERGEQL_RESULT` | `—` | `82` |
| `TAG_PARQUET_MERGE_META` | `—` | `83` |
| `TAG_CONFLICT_RECORD` | `—` | `84` |
| `TAG_CONFLICT_TOPOLOGY` | `—` | `85` |
| `_NONE` | `—` | `0` |
| `_TRUE` | `—` | `1` |
| `_FALSE` | `—` | `2` |
| `_INT64` | `—` | `3` |
| `_FLOAT64` | `—` | `4` |
| `_STR` | `—` | `5` |
| `_BYTES` | `—` | `6` |
| `_LIST` | `—` | `7` |
| `_DICT` | `—` | `8` |
| `_SMALLINT` | `—` | `9` |
| `_SET` | `—` | `10` |
| `FLAG_COMPRESSED` | `—` | `1` |
| `_TYPE_TO_TAG` | `—` | `{'g_counter': TAG_GCOUNTER, 'pn_counter': TAG_PNCOUNTER, 'lww_register': TAG_...` |
| `_TAG_TO_TYPE` | `—` | `{v: k for k, v in _TYPE_TO_TAG.items()}` |
| `_HEADER_FMT` | `—` | `'>4sHBBI'` |
| `_HEADER_SIZE` | `—` | `struct.calcsize(_HEADER_FMT)` |

## Critical Chokepoints

### `_get_delta_module()`

| Metric | Value |
|--------|-------|
| Ping Entropy (H) | **0.97** (near-maximum) |
| Combined Entropy | 0.6076 |
| Endpoints | 4 |

`_get_delta_module` is the highest-entropy chokepoint in the wire serialization pipeline. Nearly all wire paths that involve delta objects flow through this single function, making it a critical convergence point.

**What it does:** Lazily resolves and caches the `crdt_merge.delta` module to break a circular import between `wire.py` and `delta.py`. On first call it performs `from . import delta as dm` and stores the result in the module-level `_delta_module` global. Subsequent calls return the cached reference.

**Role in the wire format pipeline:**

```
serialize(obj)
  ├── _is_delta(obj) ──→ _get_delta_module() ──→ isinstance check against dm.Delta
  └── (if delta) obj.to_dict() → _encode_value(d) → frame

deserialize(data)
  └── TAG_DELTA branch ──→ _get_delta_module() ──→ dm.Delta.from_dict(d)
```

All Delta serialization and deserialization passes through `_get_delta_module`. The function is also invoked by `_is_delta()`, which is itself called during the type-dispatch phase of `serialize()`.

**Why H=0.97 matters:** A ping entropy of 0.97 (out of a maximum 1.0) means information flow through this function is almost maximally uncertain — it sits at the junction of many independent code paths. Any failure here (import error, module state corruption) would cascade to every wire operation involving deltas.

**Callers:**
1. `_is_delta(obj)` — type checking during serialization
2. `serialize()` — resolves delta module for `TAG_DELTA` encoding
3. `deserialize()` — resolves `Delta.from_dict` for `TAG_DELTA` decoding
4. Any external code that imports and calls `_get_delta_module()` directly

---

## Error Reachability

### `WireError`

| Metric | Value |
|--------|-------|
| Ping Entropy (H) | 0.6628 |
| Combined Entropy | 0.5019 |
| Reachable Endpoints | **7** |

`WireError` is the sole exception class in the wire module. It is raised on any serialization or deserialization error and can propagate from 7 distinct endpoints in the public and internal API.

#### Endpoint Propagation Map

| # | Endpoint | Raise Conditions |
|---|----------|-----------------|
| 1 | `serialize()` | Unsupported object type (`Cannot serialize type: {name}`) |
| 2 | `deserialize()` | Invalid automatic bytes, unsupported protocol version, payload truncation, decompression failure, unknown type tag |
| 3 | `peek_type()` | Data too short, invalid automatic bytes |
| 4 | `wire_size()` | Data too short |
| 5 | `serialize_batch()` | Propagates `WireError` from `serialize()` for each object in the batch |
| 6 | `deserialize_batch()` | Batch header too short, batch data truncated, plus propagated errors from `deserialize()` |
| 7 | `_decode_value()` | Unknown encoding tag during binary payload decoding (propagates through `deserialize()`) |

#### Error Propagation Chain

```
serialize_batch()
  └── serialize() ──→ WireError("Cannot serialize type: ...")

deserialize_batch()
  └── deserialize()
        ├── WireError("Data too short: ...")
        ├── WireError("Invalid automatic bytes: ...")
        ├── WireError("Unsupported protocol version: ...")
        ├── WireError("Payload truncated: ...")
        ├── WireError("Decompression failed: ...")
        ├── WireError("Unknown type tag: 0x...")
        └── _decode_value() ──→ WireError("Unknown encoding tag: 0x...")

peek_type()
  ├── WireError("Data too short: ...")
  └── WireError("Invalid automatic bytes: ...")

wire_size()
  └── WireError("Data too short: ...")
```

#### Handling Guidance

All public wire functions can raise `WireError`. Callers should wrap wire operations in try/except:

```python
from crdt_merge.wire import serialize, deserialize, WireError

try:
    data = serialize(obj)
    restored = deserialize(data)
except WireError as e:
    logger.error(f"Wire format error: {e}")
    # Handle gracefully — e.g., request retransmission
```

For batch operations, a single malformed object will abort the entire batch. Consider validating with `peek_type()` before full deserialization when processing untrusted input.

---

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: `WireError.add_note` (from `BaseException`), `WireError.with_traceback` (from `BaseException`)
- No circular dependencies
- Import graph edges (full package): 289

### RREA Findings
- Entropy profile: zero (first pass); heightened sensitivity found 4 genuine chokepoints
- `_get_delta_module`: combined H=0.6076, ping H=0.9722, 4 endpoints — **critical chokepoint** in delta serialization pipeline
- `WireError`: combined H=0.5019, ping H=0.6628, 7 endpoints — high-reachability error class
- `serialize`: combined H=0.3597, ping H=0.598, 2 endpoints
- `deserialize`: combined H=0.3312, ping H=0.541, 2 endpoints
- Dead code: None
- Shadow dependencies: None (wire-specific)
- Chokepoint status: 4 genuine chokepoints surfaced by heightened sensitivity second pass

### Code Quality (Team 2)
- Docstring coverage: 92.9%
- `__all__` defined: yes (`serialize`, `deserialize`, `peek_type`, `wire_size`, `serialize_batch`, `deserialize_batch`, `WireError`)
- Code smells: `_TAG_TO_TYPE` (L175) is a mutable global dict — consider `types.MappingProxyType`
- Conditional import: `try: import msgpack` (L67) — graceful fallback to JSON

---
Approved by: Auditor (Team 1), Cross-validated by Teams 2–4  
Last reviewed: 2026-03-31
