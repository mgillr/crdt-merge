# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.audit — immutable audit log with hash chaining."""

import json
import time
import copy

import pytest

from crdt_merge.audit import AuditEntry, AuditLog, AuditedMerge, _hash_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_left():
    return [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
    ]


@pytest.fixture
def sample_right():
    return [
        {"id": 1, "name": "Alice", "age": 31},
        {"id": 3, "name": "Charlie", "age": 35},
    ]


@pytest.fixture
def audit_log():
    return AuditLog(node_id="test-node")


# ---------------------------------------------------------------------------
# 1. Basic logging -- log_merge creates correct entry with hashes
# ---------------------------------------------------------------------------

class TestBasicLogging:
    def test_log_merge_creates_entry(self, audit_log, sample_left, sample_right):
        result = [{"id": 1, "name": "Alice", "age": 31}, {"id": 2, "name": "Bob", "age": 25}]
        entry = audit_log.log_merge(sample_left, sample_right, result)

        assert isinstance(entry, AuditEntry)
        assert entry.operation == "merge"
        assert entry.node_id == "test-node"
        assert len(entry.entry_id) == 36  # UUID4 format
        assert len(entry.input_hash) == 64  # SHA-256 hex
        assert len(entry.output_hash) == 64
        assert len(entry.entry_hash) == 64

    def test_log_merge_metadata(self, audit_log, sample_left, sample_right):
        result = [{"id": 1, "name": "Alice", "age": 31}]
        entry = audit_log.log_merge(sample_left, sample_right, result)

        assert entry.metadata["left_count"] == 2
        assert entry.metadata["right_count"] == 2
        assert entry.metadata["result_count"] == 1

    def test_log_merge_hashes_are_deterministic(self, audit_log):
        left = [{"id": 1, "val": "a"}]
        right = [{"id": 1, "val": "b"}]
        result = [{"id": 1, "val": "b"}]

        h1 = _hash_data({"left": left, "right": right})
        h2 = _hash_data({"left": left, "right": right})
        assert h1 == h2

        entry = audit_log.log_merge(left, right, result)
        assert entry.input_hash == h1

    def test_log_operation_generic(self, audit_log):
        entry = audit_log.log_operation(
            "encrypt",
            input_data={"payload": "secret"},
            output_data={"payload": "encrypted"},
            algorithm="AES-256",
        )
        assert entry.operation == "encrypt"
        assert entry.metadata["algorithm"] == "AES-256"

    def test_entry_timestamp_is_recent(self, audit_log):
        before = time.time()
        entry = audit_log.log_operation("custom", input_data="x")
        after = time.time()
        assert before <= entry.timestamp <= after

    def test_log_length(self, audit_log):
        assert len(audit_log) == 0
        audit_log.log_operation("encrypt")
        assert len(audit_log) == 1
        audit_log.log_operation("decrypt")
        assert len(audit_log) == 2


# ---------------------------------------------------------------------------
# 2. Chain integrity -- verify_chain returns True for valid log
# ---------------------------------------------------------------------------

class TestChainIntegrity:
    def test_valid_chain(self, audit_log, sample_left, sample_right):
        audit_log.log_merge(sample_left, sample_right, sample_left)
        audit_log.log_operation("encrypt", input_data="data")
        audit_log.log_operation("decrypt", output_data="data")

        assert audit_log.verify_chain() is True

    def test_single_entry_chain(self, audit_log):
        audit_log.log_operation("merge")
        assert audit_log.verify_chain() is True

    def test_long_chain(self, audit_log):
        for i in range(50):
            audit_log.log_operation("merge", input_data={"iter": i})
        assert audit_log.verify_chain() is True


# ---------------------------------------------------------------------------
# 3. Tamper detection -- modifying any entry breaks chain verification
# ---------------------------------------------------------------------------

class TestTamperDetection:
    def test_modified_entry_hash_detected(self, audit_log):
        audit_log.log_operation("merge", input_data="data1")
        audit_log.log_operation("encrypt", input_data="data2")

        # Tamper with the first entry's entry_hash
        tampered = AuditEntry(
            entry_id=audit_log._entries[0].entry_id,
            timestamp=audit_log._entries[0].timestamp,
            operation=audit_log._entries[0].operation,
            node_id=audit_log._entries[0].node_id,
            input_hash=audit_log._entries[0].input_hash,
            output_hash=audit_log._entries[0].output_hash,
            metadata=audit_log._entries[0].metadata,
            prev_hash=audit_log._entries[0].prev_hash,
            entry_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )
        audit_log._entries[0] = tampered
        assert audit_log.verify_chain() is False

    def test_modified_operation_detected(self, audit_log):
        audit_log.log_operation("merge", input_data="data")

        original = audit_log._entries[0]
        tampered = AuditEntry(
            entry_id=original.entry_id,
            timestamp=original.timestamp,
            operation="TAMPERED",
            node_id=original.node_id,
            input_hash=original.input_hash,
            output_hash=original.output_hash,
            metadata=original.metadata,
            prev_hash=original.prev_hash,
            entry_hash=original.entry_hash,  # hash won't match
        )
        audit_log._entries[0] = tampered
        assert audit_log.verify_chain() is False

    def test_broken_chain_link(self, audit_log):
        audit_log.log_operation("merge", input_data="a")
        audit_log.log_operation("merge", input_data="b")
        audit_log.log_operation("merge", input_data="c")

        # Break the chain by swapping entries 1 and 2
        audit_log._entries[1], audit_log._entries[2] = (
            audit_log._entries[2],
            audit_log._entries[1],
        )
        assert audit_log.verify_chain() is False


# ---------------------------------------------------------------------------
# 4. AuditedMerge -- wraps real merge() with auto-logging
# ---------------------------------------------------------------------------

class TestAuditedMerge:
    def test_basic_merge(self, sample_left, sample_right):
        am = AuditedMerge(node_id="node-A")
        result, entry = am.merge(sample_left, sample_right, key="id")

        assert isinstance(result, list)
        assert len(result) >= 2  # at least the overlapping + unique records
        assert entry.operation == "merge"
        assert entry.node_id == "node-A"
        assert am.audit_log.verify_chain() is True

    def test_merge_with_schema(self, sample_left, sample_right):
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(default=MaxWins())
        am = AuditedMerge(node_id="node-B")
        result, entry = am.merge(sample_left, sample_right, key="id", schema=schema)

        assert isinstance(result, list)
        assert "schema" in entry.metadata
        assert am.audit_log.verify_chain() is True

    def test_multiple_merges(self):
        am = AuditedMerge(node_id="node-C")

        data_a = [{"id": 1, "v": "a"}]
        data_b = [{"id": 1, "v": "b"}]
        data_c = [{"id": 1, "v": "c"}]

        r1, e1 = am.merge(data_a, data_b, key="id")
        r2, e2 = am.merge(r1, data_c, key="id")

        assert len(am.audit_log) == 2
        assert e2.prev_hash == e1.entry_hash
        assert am.audit_log.verify_chain() is True

    def test_shared_audit_log(self):
        log = AuditLog(node_id="shared")
        am = AuditedMerge(audit_log=log)

        data = [{"id": 1, "x": 1}]
        am.merge(data, data, key="id")

        assert len(log) == 1
        assert am.audit_log is log

    def test_result_matches_direct_merge(self, sample_left, sample_right):
        import crdt_merge

        am = AuditedMerge(node_id="compare")
        audited_result, _ = am.merge(sample_left, sample_right, key="id")
        direct_result = crdt_merge.merge(sample_left, sample_right, key="id")

        assert audited_result == direct_result


# ---------------------------------------------------------------------------
# 5. Export / Import -- round-trip through JSON preserves data + chain
# ---------------------------------------------------------------------------

class TestExportImport:
    def test_round_trip(self, audit_log, sample_left, sample_right):
        result = [{"id": 1, "name": "Alice", "age": 31}]
        audit_log.log_merge(sample_left, sample_right, result)
        audit_log.log_operation("encrypt", input_data="secret", key_bits=256)

        exported = audit_log.export_log()
        imported = AuditLog.import_log(exported)

        assert len(imported) == len(audit_log)
        assert imported.verify_chain() is True

        for orig, restored in zip(audit_log, imported):
            assert orig.entry_id == restored.entry_id
            assert orig.entry_hash == restored.entry_hash
            assert orig.prev_hash == restored.prev_hash
            assert orig.metadata == restored.metadata

    def test_export_to_file(self, audit_log, tmp_path):
        audit_log.log_operation("merge", input_data="x")
        filepath = str(tmp_path / "audit.json")
        audit_log.export_log(filepath=filepath)

        with open(filepath, "r") as fh:
            data = json.load(fh)
        assert data["node_id"] == "test-node"
        assert len(data["entries"]) == 1

    def test_import_tampered_raises(self, audit_log):
        audit_log.log_operation("merge", input_data="x")
        exported = audit_log.export_log()

        payload = json.loads(exported)
        payload["entries"][0]["entry_hash"] = "bad_hash"
        tampered = json.dumps(payload)

        with pytest.raises(ValueError, match="chain verification"):
            AuditLog.import_log(tampered)

    def test_import_empty_log(self):
        log = AuditLog(node_id="empty")
        exported = log.export_log()
        imported = AuditLog.import_log(exported)
        assert len(imported) == 0
        assert imported.verify_chain() is True

    def test_export_preserves_node_id(self):
        log = AuditLog(node_id="my-node-123")
        log.log_operation("custom")
        exported = log.export_log()
        imported = AuditLog.import_log(exported)
        assert imported.node_id == "my-node-123"


# ---------------------------------------------------------------------------
# 6. Filtering -- get_entries by operation, since, until
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_operation(self, audit_log):
        audit_log.log_operation("merge", input_data="a")
        audit_log.log_operation("encrypt", input_data="b")
        audit_log.log_operation("merge", input_data="c")

        merges = audit_log.get_entries(operation="merge")
        assert len(merges) == 2
        assert all(e.operation == "merge" for e in merges)

        encrypts = audit_log.get_entries(operation="encrypt")
        assert len(encrypts) == 1

    def test_filter_by_time_range(self, audit_log):
        audit_log.log_operation("merge", input_data="early")
        t_mid = time.time()
        time.sleep(0.01)
        audit_log.log_operation("merge", input_data="late")

        since_entries = audit_log.get_entries(since=t_mid)
        assert len(since_entries) == 1

        until_entries = audit_log.get_entries(until=t_mid)
        assert len(until_entries) == 1

    def test_filter_combined(self, audit_log):
        audit_log.log_operation("merge", input_data="a")
        audit_log.log_operation("encrypt", input_data="b")
        t_mid = time.time()
        time.sleep(0.01)
        audit_log.log_operation("merge", input_data="c")

        results = audit_log.get_entries(operation="merge", since=t_mid)
        assert len(results) == 1
        assert results[0].operation == "merge"

    def test_filter_returns_empty(self, audit_log):
        audit_log.log_operation("merge")
        assert audit_log.get_entries(operation="nonexistent") == []

    def test_no_filter_returns_all(self, audit_log):
        for _ in range(5):
            audit_log.log_operation("merge")
        assert len(audit_log.get_entries()) == 5


# ---------------------------------------------------------------------------
# 7. Multiple operations -- log_merge, log_operation mixed
# ---------------------------------------------------------------------------

class TestMixedOperations:
    def test_mixed_chain(self, audit_log, sample_left, sample_right):
        result = [{"id": 1}]
        audit_log.log_merge(sample_left, sample_right, result)
        audit_log.log_operation("encrypt", input_data=result)
        audit_log.log_operation("key_rotate", input_data="old_key", output_data="new_key")
        audit_log.log_merge(result, sample_left, sample_right)
        audit_log.log_operation("decrypt", output_data=result)

        assert len(audit_log) == 5
        assert audit_log.verify_chain() is True

        ops = [e.operation for e in audit_log]
        assert ops == ["merge", "encrypt", "key_rotate", "merge", "decrypt"]


# ---------------------------------------------------------------------------
# 8. Genesis -- first entry has prev_hash = "genesis"
# ---------------------------------------------------------------------------

class TestGenesis:
    def test_first_entry_genesis(self, audit_log):
        audit_log.log_operation("merge")
        first = audit_log.entries[0]
        assert first.prev_hash == "genesis"

    def test_second_entry_links_to_first(self, audit_log):
        audit_log.log_operation("merge")
        audit_log.log_operation("encrypt")
        entries = audit_log.entries
        assert entries[1].prev_hash == entries[0].entry_hash


# ---------------------------------------------------------------------------
# 9. Empty log -- verify_chain on empty log returns True
# ---------------------------------------------------------------------------

class TestEmptyLog:
    def test_empty_verify(self):
        log = AuditLog()
        assert log.verify_chain() is True

    def test_empty_length(self):
        log = AuditLog()
        assert len(log) == 0

    def test_empty_iter(self):
        log = AuditLog()
        assert list(log) == []

    def test_empty_entries(self):
        log = AuditLog()
        assert log.entries == []

    def test_empty_export(self):
        log = AuditLog()
        exported = log.export_log()
        data = json.loads(exported)
        assert data["entries"] == []


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_records(self, audit_log):
        entry = audit_log.log_merge([], [], [])
        assert entry.metadata["left_count"] == 0
        assert entry.metadata["right_count"] == 0
        assert entry.metadata["result_count"] == 0
        assert audit_log.verify_chain() is True

    def test_large_metadata(self, audit_log):
        big_meta = {f"key_{i}": f"value_{i}" * 100 for i in range(50)}
        entry = audit_log.log_operation("custom", input_data="x", **big_meta)
        assert len(entry.metadata) >= 50
        assert audit_log.verify_chain() is True

    def test_special_characters_in_data(self, audit_log):
        left = [{"id": 1, "text": "Hello 'world' \"quotes\" & <tags> \n\t"}]
        right = [{"id": 1, "text": "Unicode: \u00e9\u00e0\u00fc\u00f1 \U0001f680"}]
        result = [{"id": 1, "text": "merged"}]
        entry = audit_log.log_merge(left, right, result)
        assert audit_log.verify_chain() is True

    def test_entry_immutability(self, audit_log):
        entry = audit_log.log_operation("merge")
        with pytest.raises(AttributeError):
            entry.operation = "tampered"

    def test_entry_to_dict_from_dict_roundtrip(self, audit_log):
        entry = audit_log.log_operation("encrypt", input_data="x", algorithm="AES")
        d = entry.to_dict()
        restored = AuditEntry.from_dict(d)
        assert restored == entry
        assert restored.verify() is True

    def test_repr(self, audit_log):
        r = repr(audit_log)
        assert "test-node" in r
        assert "0" in r

    def test_iter(self, audit_log):
        for _ in range(3):
            audit_log.log_operation("merge")
        entries = list(audit_log)
        assert len(entries) == 3

    def test_entries_returns_copy(self, audit_log):
        audit_log.log_operation("merge")
        entries = audit_log.entries
        entries.clear()
        assert len(audit_log) == 1  # internal list unchanged

    def test_log_operation_with_none_data(self, audit_log):
        entry = audit_log.log_operation("custom")
        assert entry.input_hash == _hash_data("")
        assert entry.output_hash == _hash_data("")
        assert audit_log.verify_chain() is True

    def test_schema_metadata_in_log_merge(self, audit_log):
        from crdt_merge.strategies import MergeSchema, LWW
        schema = MergeSchema(default=LWW())
        entry = audit_log.log_merge([{"id": 1}], [{"id": 1}], [{"id": 1}], schema=schema)
        assert "schema" in entry.metadata

    def test_entry_verify_standalone(self, audit_log):
        entry = audit_log.log_operation("merge", input_data="test")
        assert entry.verify() is True
