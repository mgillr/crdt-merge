# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for the cross-language wire format (v0.5.0)."""
import struct
import pytest
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.delta import Delta
from crdt_merge.wire import (
    serialize, deserialize, peek_type, wire_size,
    serialize_batch, deserialize_batch, WireError,
    MAGIC, PROTOCOL_VERSION, _HEADER_SIZE,
    _encode_value, _decode_value,
)

# ── Low-level encoder round-trips ──────────────────────────────────────

class TestBinaryEncoder:
    def test_none(self):
        enc = _encode_value(None)
        val, off = _decode_value(enc, 0)
        assert val is None

    def test_true(self):
        val, _ = _decode_value(_encode_value(True), 0)
        assert val is True

    def test_false(self):
        val, _ = _decode_value(_encode_value(False), 0)
        assert val is False

    def test_small_int(self):
        for v in [-128, -1, 0, 1, 42, 127]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_large_int(self):
        for v in [128, 1000, -129, 2**50, -(2**50)]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_float(self):
        for v in [0.0, 1.5, -3.14, float('inf'), float('-inf')]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_string(self):
        for v in ["", "hello", "unicode: 日本語 🎉", "a" * 10000]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_bytes(self):
        for v in [b"", b"\x00\x01\x02", b"hello" * 100]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_list(self):
        for v in [[], [1, 2, 3], [None, True, "hello", 3.14], [[1, 2], [3, 4]]]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_dict(self):
        for v in [{}, {"a": 1}, {"nested": {"x": [1, 2, 3]}}]:
            val, _ = _decode_value(_encode_value(v), 0)
            assert val == v

    def test_set(self):
        val, _ = _decode_value(_encode_value({1, 2, 3}), 0)
        assert val == {1, 2, 3}

    def test_nested_complex(self):
        v = {"key": [1, None, {"inner": True}], "b": 3.14}
        val, _ = _decode_value(_encode_value(v), 0)
        assert val == v

# ── GCounter round-trip ────────────────────────────────────────────────

class TestGCounterWire:
    def test_basic_roundtrip(self):
        gc = GCounter("node1")
        gc.increment("node1", 10)
        gc.increment("node2", 5)
        data = serialize(gc)
        restored = deserialize(data)
        assert isinstance(restored, GCounter)
        assert restored.value == 15

    def test_compressed(self):
        gc = GCounter("node1")
        for i in range(100):
            gc.increment(f"node_{i}", i)
        raw = serialize(gc)
        comp = serialize(gc, compress=True)
        assert len(comp) < len(raw)
        restored = deserialize(comp)
        assert restored.value == gc.value

    def test_empty_gcounter(self):
        gc = GCounter()
        data = serialize(gc)
        restored = deserialize(data)
        assert restored.value == 0

    def test_peek_type(self):
        gc = GCounter("a")
        data = serialize(gc)
        assert peek_type(data) == 'g_counter'

# ── PNCounter round-trip ───────────────────────────────────────────────

class TestPNCounterWire:
    def test_roundtrip(self):
        pn = PNCounter()
        pn.increment("a", 10)
        pn.decrement("b", 3)
        data = serialize(pn)
        restored = deserialize(data)
        assert isinstance(restored, PNCounter)
        assert restored.value == 7

    def test_negative_value(self):
        pn = PNCounter()
        pn.decrement("a", 50)
        data = serialize(pn)
        restored = deserialize(data)
        assert restored.value == -50

# ── LWWRegister round-trip ─────────────────────────────────────────────

class TestLWWRegisterWire:
    def test_roundtrip(self):
        reg = LWWRegister("hello", 1000.0, "node1")
        data = serialize(reg)
        restored = deserialize(data)
        assert isinstance(restored, LWWRegister)
        assert restored.value == "hello"
        assert restored.timestamp == 1000.0

    def test_none_value(self):
        reg = LWWRegister(None, 0.0)
        data = serialize(reg)
        restored = deserialize(data)
        assert restored.value is None

    def test_peek_type(self):
        reg = LWWRegister("x")
        assert peek_type(serialize(reg)) == 'lww_register'

# ── ORSet round-trip ───────────────────────────────────────────────────

class TestORSetWire:
    def test_roundtrip(self):
        s = ORSet()
        s.add("alice")
        s.add("bob")
        data = serialize(s)
        restored = deserialize(data)
        assert isinstance(restored, ORSet)
        assert "alice" in restored.value
        assert "bob" in restored.value

    def test_empty(self):
        s = ORSet()
        data = serialize(s)
        restored = deserialize(data)
        assert len(restored.value) == 0

# ── LWWMap round-trip ──────────────────────────────────────────────────

class TestLWWMapWire:
    def test_roundtrip(self):
        m = LWWMap()
        m.set("name", "Alice", 100.0)
        m.set("age", 30, 100.0)
        data = serialize(m)
        restored = deserialize(data)
        assert isinstance(restored, LWWMap)
        assert restored.get("name") == "Alice"
        assert restored.get("age") == 30

# ── Delta round-trip ───────────────────────────────────────────────────

class TestDeltaWire:
    def test_roundtrip(self):
        d = Delta(
            added=[{"id": 1, "name": "Alice"}],
            modified=[{"id": 2, "name": "Bob_v2"}],
            removed=[{"id": 3}],
            version=5,
            source_node="node_a"
        )
        data = serialize(d)
        restored = deserialize(data)
        assert isinstance(restored, Delta)
        assert len(restored.added) == 1
        assert len(restored.modified) == 1
        assert len(restored.removed) == 1
        assert restored.version == 5
        assert restored.source_node == "node_a"

    def test_empty_delta(self):
        d = Delta(version=0)
        data = serialize(d)
        restored = deserialize(data)
        assert isinstance(restored, Delta)
        assert restored.is_empty

# ── Generic round-trip ─────────────────────────────────────────────────

class TestGenericWire:
    def test_dict(self):
        d = {"key": "value", "nested": [1, 2, 3]}
        data = serialize(d)
        restored = deserialize(data)
        assert restored == d

    def test_list(self):
        l = [1, "two", None, True]
        data = serialize(l)
        restored = deserialize(data)
        assert restored == l

    def test_peek_generic(self):
        assert peek_type(serialize({"x": 1})) == 'generic'

# ── Batch serialize/deserialize ────────────────────────────────────────

class TestBatchWire:
    def test_batch_roundtrip(self):
        objects = [
            GCounter("a"),
            PNCounter(),
            LWWRegister("hello", 1.0),
            {"generic": True},
        ]
        objects[0].increment("a", 5)
        data = serialize_batch(objects)
        restored = deserialize_batch(data)
        assert len(restored) == 4
        assert isinstance(restored[0], GCounter)
        assert restored[0].value == 5

    def test_batch_empty(self):
        data = serialize_batch([])
        restored = deserialize_batch(data)
        assert restored == []

    def test_batch_compressed(self):
        objects = [GCounter(f"n{i}") for i in range(50)]
        raw = serialize_batch(objects)
        comp = serialize_batch(objects, compress=True)
        restored = deserialize_batch(comp)
        assert len(restored) == 50

# ── wire_size ──────────────────────────────────────────────────────────

class TestWireSize:
    def test_basic(self):
        gc = GCounter("a")
        gc.increment("a", 10)
        data = serialize(gc)
        info = wire_size(data)
        assert info['header_bytes'] == _HEADER_SIZE
        assert info['type_name'] == 'g_counter'
        assert info['compressed'] is False
        assert info['total_bytes'] == len(data)

    def test_compressed_flag(self):
        gc = GCounter()
        for i in range(100):
            gc.increment(f"node_{i}", i)
        data = serialize(gc, compress=True)
        info = wire_size(data)
        assert info['compressed'] is True

# ── Error handling ─────────────────────────────────────────────────────

class TestWireErrors:
    def test_too_short(self):
        with pytest.raises(WireError):
            deserialize(b"CR")

    def test_bad_magic(self):
        with pytest.raises(WireError, match="Invalid magic"):
            data = b"XXXX" + b"\x00" * 8
            deserialize(data)

    def test_truncated_payload(self):
        gc = GCounter("a")
        data = serialize(gc)
        with pytest.raises(WireError, match="truncated"):
            deserialize(data[:_HEADER_SIZE + 2])

    def test_unsupported_type(self):
        with pytest.raises(WireError):
            serialize(object())

# ── Cross-type merge after wire round-trip ─────────────────────────────

class TestWireMerge:
    def test_gcounter_merge_after_wire(self):
        a = GCounter("a")
        a.increment("a", 10)
        b = GCounter("b")
        b.increment("b", 20)

        a2 = deserialize(serialize(a))
        b2 = deserialize(serialize(b))
        merged = a2.merge(b2)
        assert merged.value == 30

    def test_lwwregister_merge_after_wire(self):
        a = LWWRegister("old", 1.0, "n1")
        b = LWWRegister("new", 2.0, "n2")

        a2 = deserialize(serialize(a))
        b2 = deserialize(serialize(b))
        merged = a2.merge(b2)
        assert merged.value == "new"
