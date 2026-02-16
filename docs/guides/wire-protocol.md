# Wire Protocol Deep Dive

## Format Overview

crdt-merge uses a compact binary wire format for transmitting CRDT state:

```
┌──────────────┬──────────┬──────────┬─────────────────────┐
│ Magic (4B)   │ Ver (2B) │ Type (2B)│ Payload (variable)  │
│ 0x43524454   │ 0x0001   │ enum     │ msgpack or binary   │
└──────────────┴──────────┴──────────┴─────────────────────┘
```

### Magic Number
`0x43524454` = ASCII "CRDT". Used for format detection.

### Version
Protocol version. Current: `0x0001`.

### Type Enum
Identifies the CRDT type:
- 0x01: GCounter
- 0x02: PNCounter
- 0x03: LWWRegister
- 0x04: ORSet
- 0x05: LWWMap
- 0x06: VectorClock
- 0x10: MergeSchema
- 0x20: DataFrame state

### Payload Formats
- **msgpack** (default): Compact, fast, cross-language
- **json**: Human-readable, larger
- **binary**: Custom compact binary for high-throughput

## Batch Protocol

For transmitting multiple CRDT objects:

```
┌──────────┬───────────┬──────────────┬──────────────────────┐
│ Magic(4) │ Count(4)  │ Sizes(4×N)   │ Payloads(concat)     │
└──────────┴───────────┴──────────────┴──────────────────────┘
```

## Usage

```python
from crdt_merge import serialize, deserialize, peek_type, wire_size

# Serialize any CRDT or dict to compact binary
data = serialize(my_counter)
info = peek_type(data)          # Returns type string, e.g. "generic"
size = wire_size(data)          # Returns dict: {"total_bytes": ..., "header_bytes": ..., ...}
restored = deserialize(data)    # Reconstruct the original object
```
