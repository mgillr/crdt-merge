# Copyright 2026 Ryan Gillespie
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Commercial licensing: rgillespie83@icloud.com, data@optitransfer.ch

"""
Cross-Language Wire Format for crdt-merge.

Binary interchange format that all 4 language implementations (Python, TypeScript,
Rust, Java) can read and write. Enables polyglot distributed systems where nodes
run different language implementations but share CRDT state.

Format specification:
    [MAGIC:4][VERSION:2][TYPE:1][FLAGS:1][LENGTH:4][PAYLOAD:N]

    MAGIC:   b'CRDT' (4 bytes)
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
"""

import struct
import zlib
from typing import Any, Optional, Union

from .core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

# Lazy import to avoid circular
_delta_module = None


def _get_delta_module():
    global _delta_module
    if _delta_module is None:
        from . import delta as dm
        _delta_module = dm
    return _delta_module



def _is_delta(obj):
    """Check if obj is a Delta without circular import."""
    dm = _get_delta_module()
    return isinstance(obj, dm.Delta)

# ── Constants ──────────────────────────────────────────────────────────────

MAGIC = b'CRDT'
PROTOCOL_VERSION = 1

# Type tags
TAG_GCOUNTER    = 0x01
TAG_PNCOUNTER   = 0x02
TAG_LWWREGISTER = 0x03
TAG_ORSET       = 0x04
TAG_LWWMAP      = 0x05
TAG_DELTA       = 0x10
TAG_GENERIC     = 0x20

# Payload encoding tags
_NONE   = 0x00
_TRUE   = 0x01
_FALSE  = 0x02
_INT64  = 0x03
_FLOAT64 = 0x04
_STR    = 0x05
_BYTES  = 0x06
_LIST   = 0x07
_DICT   = 0x08
_SMALLINT = 0x09
_SET    = 0x0A

# Flags
FLAG_COMPRESSED = 0x01

# Type tag mapping
_TYPE_TO_TAG = {
    'g_counter': TAG_GCOUNTER,
    'pn_counter': TAG_PNCOUNTER,
    'lww_register': TAG_LWWREGISTER,
    'or_set': TAG_ORSET,
    'lww_map': TAG_LWWMAP,
    'delta': TAG_DELTA,
}

_TAG_TO_TYPE = {v: k for k, v in _TYPE_TO_TAG.items()}

# Header: MAGIC(4) + VERSION(2) + TYPE(1) + FLAGS(1) + LENGTH(4) = 12 bytes
_HEADER_FMT = '>4sHBBI'
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)


# ── Compact Binary Encoder ────────────────────────────────────────────────

class WireError(Exception):
    """Raised on serialization/deserialization errors."""
    pass


def _encode_value(val: Any) -> bytes:
    """Encode a Python value to compact binary."""
    if val is None:
        return struct.pack('B', _NONE)
    elif val is True:
        return struct.pack('B', _TRUE)
    elif val is False:
        return struct.pack('B', _FALSE)
    elif isinstance(val, int) and not isinstance(val, bool):
        if -128 <= val <= 127:
            return struct.pack('Bb', _SMALLINT, val)
        return struct.pack('>Bq', _INT64, val)
    elif isinstance(val, float):
        return struct.pack('>Bd', _FLOAT64, val)
    elif isinstance(val, str):
        encoded = val.encode('utf-8')
        return struct.pack('>BI', _STR, len(encoded)) + encoded
    elif isinstance(val, (bytes, bytearray)):
        return struct.pack('>BI', _BYTES, len(val)) + bytes(val)
    elif isinstance(val, set):
        parts = [struct.pack('>BI', _SET, len(val))]
        for item in sorted(val, key=str):
            parts.append(_encode_value(item))
        return b''.join(parts)
    elif isinstance(val, (list, tuple)):
        parts = [struct.pack('>BI', _LIST, len(val))]
        for item in val:
            parts.append(_encode_value(item))
        return b''.join(parts)
    elif isinstance(val, dict):
        parts = [struct.pack('>BI', _DICT, len(val))]
        for k, v in val.items():
            parts.append(_encode_value(k))
            parts.append(_encode_value(v))
        return b''.join(parts)
    else:
        # Fallback: convert to string
        return _encode_value(str(val))


def _decode_value(data: bytes, offset: int) -> tuple:
    """Decode a value from binary data at the given offset. Returns (value, new_offset)."""
    tag = data[offset]
    offset += 1

    if tag == _NONE:
        return None, offset
    elif tag == _TRUE:
        return True, offset
    elif tag == _FALSE:
        return False, offset
    elif tag == _SMALLINT:
        val, = struct.unpack_from('b', data, offset)
        return val, offset + 1
    elif tag == _INT64:
        val, = struct.unpack_from('>q', data, offset)
        return val, offset + 8
    elif tag == _FLOAT64:
        val, = struct.unpack_from('>d', data, offset)
        return val, offset + 8
    elif tag == _STR:
        length, = struct.unpack_from('>I', data, offset)
        offset += 4
        val = data[offset:offset + length].decode('utf-8')
        return val, offset + length
    elif tag == _BYTES:
        length, = struct.unpack_from('>I', data, offset)
        offset += 4
        val = data[offset:offset + length]
        return bytes(val), offset + length
    elif tag == _SET:
        count, = struct.unpack_from('>I', data, offset)
        offset += 4
        result = set()
        for _ in range(count):
            item, offset = _decode_value(data, offset)
            result.add(item)
        return result, offset
    elif tag == _LIST:
        count, = struct.unpack_from('>I', data, offset)
        offset += 4
        result = []
        for _ in range(count):
            item, offset = _decode_value(data, offset)
            result.append(item)
        return result, offset
    elif tag == _DICT:
        count, = struct.unpack_from('>I', data, offset)
        offset += 4
        result = {}
        for _ in range(count):
            k, offset = _decode_value(data, offset)
            v, offset = _decode_value(data, offset)
            result[k] = v
        return result, offset
    else:
        raise WireError(f"Unknown encoding tag: 0x{tag:02x} at offset {offset - 1}")


# ── Public API ─────────────────────────────────────────────────────────────

def serialize(obj: Any, *, compress: bool = False) -> bytes:
    """
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
    """
    # Determine type tag and get dict representation
    if isinstance(obj, (GCounter, PNCounter, LWWRegister, ORSet, LWWMap)):
        d = obj.to_dict()
        type_tag = _TYPE_TO_TAG[d['type']]
    elif _is_delta(obj):
        d = obj.to_dict()
        type_tag = TAG_DELTA
    elif hasattr(obj, 'to_dict') and callable(obj.to_dict):
        d = obj.to_dict()
        type_name = d.get('type', '')
        type_tag = _TYPE_TO_TAG.get(type_name, TAG_GENERIC)
    elif isinstance(obj, (dict, list)):
        d = obj
        type_tag = TAG_GENERIC
    else:
        raise WireError(f"Cannot serialize type: {type(obj).__name__}")

    # Encode payload
    payload = _encode_value(d)

    # Optional compression
    flags = 0
    if compress:
        compressed = zlib.compress(payload, level=6)
        if len(compressed) < len(payload):
            payload = compressed
            flags |= FLAG_COMPRESSED

    # Build header
    header = struct.pack(_HEADER_FMT, MAGIC, PROTOCOL_VERSION, type_tag, flags, len(payload))

    return header + payload


def deserialize(data: bytes) -> Any:
    """
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
    """
    if len(data) < _HEADER_SIZE:
        raise WireError(f"Data too short: {len(data)} bytes (minimum {_HEADER_SIZE})")

    # Parse header
    magic, version, type_tag, flags, payload_len = struct.unpack_from(_HEADER_FMT, data)

    if magic != MAGIC:
        raise WireError(f"Invalid magic bytes: {magic!r} (expected {MAGIC!r})")

    if version > PROTOCOL_VERSION:
        raise WireError(f"Unsupported protocol version: {version} (max supported: {PROTOCOL_VERSION})")

    # Extract payload
    payload = data[_HEADER_SIZE:_HEADER_SIZE + payload_len]

    if len(payload) != payload_len:
        raise WireError(f"Payload truncated: expected {payload_len} bytes, got {len(payload)}")

    # Decompress if needed
    if flags & FLAG_COMPRESSED:
        try:
            payload = zlib.decompress(payload)
        except zlib.error as e:
            raise WireError(f"Decompression failed: {e}")

    # Decode payload
    d, _ = _decode_value(payload, 0)

    # Reconstruct object based on type tag
    if type_tag == TAG_GCOUNTER:
        return GCounter.from_dict(d)
    elif type_tag == TAG_PNCOUNTER:
        return PNCounter.from_dict(d)
    elif type_tag == TAG_LWWREGISTER:
        return LWWRegister.from_dict(d)
    elif type_tag == TAG_ORSET:
        return ORSet.from_dict(d)
    elif type_tag == TAG_LWWMAP:
        return LWWMap.from_dict(d)
    elif type_tag == TAG_DELTA:
        dm = _get_delta_module()
        return dm.Delta.from_dict(d)
    elif type_tag == TAG_GENERIC:
        return d
    else:
        raise WireError(f"Unknown type tag: 0x{type_tag:02x}")


def peek_type(data: bytes) -> str:
    """
    Read the type tag from wire format bytes without deserializing.

    Useful for routing messages to the correct handler without
    paying the full deserialization cost.

    Args:
        data: Wire-format bytes.

    Returns:
        str: The CRDT type name (e.g., 'g_counter', 'lww_register', 'generic').

    Raises:
        WireError: If the data is invalid.
    """
    if len(data) < _HEADER_SIZE:
        raise WireError(f"Data too short: {len(data)} bytes")

    magic, version, type_tag, flags, payload_len = struct.unpack_from(_HEADER_FMT, data)

    if magic != MAGIC:
        raise WireError(f"Invalid magic bytes: {magic!r}")

    return _TAG_TO_TYPE.get(type_tag, 'generic')


def wire_size(data: bytes) -> dict:
    """
    Get size information about wire-format data without deserializing.

    Args:
        data: Wire-format bytes.

    Returns:
        dict with keys: total_bytes, header_bytes, payload_bytes,
        compressed, protocol_version, type_name.
    """
    if len(data) < _HEADER_SIZE:
        raise WireError(f"Data too short: {len(data)} bytes")

    magic, version, type_tag, flags, payload_len = struct.unpack_from(_HEADER_FMT, data)

    return {
        'total_bytes': len(data),
        'header_bytes': _HEADER_SIZE,
        'payload_bytes': payload_len,
        'compressed': bool(flags & FLAG_COMPRESSED),
        'protocol_version': version,
        'type_name': _TAG_TO_TYPE.get(type_tag, 'generic'),
    }


def serialize_batch(objects: list, *, compress: bool = False) -> bytes:
    """
    Serialize multiple CRDT objects into a single byte stream.

    Format: [COUNT:4][SIZE1:4][OBJ1][SIZE2:4][OBJ2]...

    Args:
        objects: List of CRDT objects to serialize.
        compress: If True, compress each object's payload.

    Returns:
        bytes: The concatenated wire-format data.
    """
    parts = [struct.pack('>I', len(objects))]
    for obj in objects:
        encoded = serialize(obj, compress=compress)
        parts.append(struct.pack('>I', len(encoded)))
        parts.append(encoded)
    return b''.join(parts)


def deserialize_batch(data: bytes) -> list:
    """
    Deserialize multiple CRDT objects from a batch byte stream.

    Args:
        data: Batch wire-format bytes.

    Returns:
        list: The deserialized objects.
    """
    if len(data) < 4:
        raise WireError("Batch data too short")

    count, = struct.unpack_from('>I', data, 0)
    offset = 4
    results = []

    for _ in range(count):
        if offset + 4 > len(data):
            raise WireError("Batch data truncated")
        size, = struct.unpack_from('>I', data, offset)
        offset += 4
        obj_data = data[offset:offset + size]
        results.append(deserialize(obj_data))
        offset += size

    return results
