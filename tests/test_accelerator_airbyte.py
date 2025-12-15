# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.accelerators.airbyte — Airbyte destination connector.

All Airbyte CDK interactions are mocked; airbyte_cdk is NOT required.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from crdt_merge.accelerators.airbyte import (
    AirbyteMergeDestination,
    AirbyteMessage,
    AirbyteRecordMessage,
    StreamConfig,
    WriteResult,
    _StreamStore,
    _resolve_field,
    _build_merge_schema,
)
from crdt_merge.accelerators import ACCELERATOR_REGISTRY


# ===================================================================
# TestAirbyteMergeDestination — 25 tests
# ===================================================================


class TestAirbyteMergeDestination:
    """Tests for the AirbyteMergeDestination accelerator."""

    # -- Construction & protocol -------------------------------------------

    def test_init_default(self):
        dest = AirbyteMergeDestination()
        assert dest._default_key == "id"
        assert dest._default_strategy == "lww"

    def test_init_custom_key(self):
        dest = AirbyteMergeDestination(default_key="user_id")
        assert dest._default_key == "user_id"

    def test_init_custom_strategy(self):
        dest = AirbyteMergeDestination(default_strategy="max")
        assert dest._default_strategy == "max"

    def test_registered_in_accelerator_registry(self):
        assert "airbyte_destination" in ACCELERATOR_REGISTRY

    def test_health_check(self):
        dest = AirbyteMergeDestination()
        hc = dest.health_check()
        assert hc["name"] == "airbyte_destination"
        assert hc["version"] == "0.7.0"
        assert hc["status"] == "ok"
        assert hc["connector"] == "destination-crdt-merge"

    def test_is_available(self):
        dest = AirbyteMergeDestination()
        assert dest.is_available() is True

    # -- Spec & connection check -------------------------------------------

    def test_get_spec(self):
        dest = AirbyteMergeDestination()
        spec = dest.get_spec()
        assert "connectionSpecification" in spec
        props = spec["connectionSpecification"]["properties"]
        assert "default_key" in props
        assert "default_strategy" in props
        assert spec["supportsIncremental"] is True

    def test_check_connection_valid(self):
        dest = AirbyteMergeDestination()
        ok, err = dest.check_connection({"default_key": "id"})
        assert ok is True
        assert err is None

    def test_check_connection_missing_key(self):
        dest = AirbyteMergeDestination()
        ok, err = dest.check_connection({})
        assert ok is False
        assert "default_key" in err

    def test_check_connection_bad_strategy(self):
        dest = AirbyteMergeDestination()
        ok, err = dest.check_connection(
            {"default_key": "id", "default_strategy": "nonexistent"}
        )
        assert ok is False
        assert "strategy" in err.lower()

    # -- Stream configuration ----------------------------------------------

    def test_configure_stream(self):
        dest = AirbyteMergeDestination()
        dest.configure_stream(
            "users",
            key_column="user_id",
            strategies={"name": "lww", "score": "max"},
        )
        cfg = dest._stream_configs["users"]
        assert cfg.key_column == "user_id"
        assert cfg.strategies["score"] == "max"

    def test_auto_configure_on_write(self):
        dest = AirbyteMergeDestination()
        dest.write("new_stream", [{"id": 1, "val": "a"}])
        assert "new_stream" in dest._stream_configs

    # -- Write (basic) -----------------------------------------------------

    def test_write_single_record(self):
        dest = AirbyteMergeDestination()
        result = dest.write("users", [{"id": 1, "name": "Alice"}])
        assert result.records_written == 1
        assert result.records_merged == 0

    def test_write_multiple_unique_records(self):
        dest = AirbyteMergeDestination()
        recs = [{"id": i, "val": f"v{i}"} for i in range(5)]
        result = dest.write("things", recs)
        assert result.records_written == 5
        assert result.records_merged == 0

    def test_write_conflicting_records_lww(self):
        dest = AirbyteMergeDestination()
        dest.write("users", [{"id": 1, "name": "Alice"}], timestamp=1.0)
        result = dest.write("users", [{"id": 1, "name": "Alicia"}], timestamp=2.0)
        assert result.records_merged == 1
        records = dest.read_stream("users")
        assert len(records) == 1
        # LWW with later timestamp should pick "Alicia"
        assert records[0]["name"] == "Alicia"

    def test_write_conflicting_records_max(self):
        dest = AirbyteMergeDestination()
        dest.configure_stream("scores", key_column="id", strategies={"score": "max"})
        dest.write("scores", [{"id": 1, "score": 100}])
        dest.write("scores", [{"id": 1, "score": 200}])
        records = dest.read_stream("scores")
        assert records[0]["score"] == 200

    def test_write_conflicting_records_min(self):
        dest = AirbyteMergeDestination()
        dest.configure_stream("prices", key_column="id", strategies={"price": "min"})
        dest.write("prices", [{"id": 1, "price": 100}])
        dest.write("prices", [{"id": 1, "price": 50}])
        records = dest.read_stream("prices")
        assert records[0]["price"] == 50

    def test_write_result_to_dict(self):
        dest = AirbyteMergeDestination()
        result = dest.write("test", [{"id": 1, "v": "x"}])
        d = result.to_dict()
        assert d["stream_name"] == "test"
        assert d["records_written"] == 1

    def test_write_result_has_timing(self):
        dest = AirbyteMergeDestination()
        result = dest.write("test", [{"id": 1, "v": "x"}])
        assert result.merge_time_ms >= 0

    # -- Read & query ------------------------------------------------------

    def test_read_stream_empty(self):
        dest = AirbyteMergeDestination()
        assert dest.read_stream("nonexistent") == []

    def test_read_stream_after_write(self):
        dest = AirbyteMergeDestination()
        dest.write("users", [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
        records = dest.read_stream("users")
        assert len(records) == 2

    def test_list_streams(self):
        dest = AirbyteMergeDestination()
        dest.write("a", [{"id": 1}])
        dest.write("b", [{"id": 1}])
        assert set(dest.list_streams()) == {"a", "b"}

    def test_clear_stream(self):
        dest = AirbyteMergeDestination()
        dest.write("users", [{"id": 1, "name": "Alice"}])
        dest.clear_stream("users")
        assert dest.read_stream("users") == []

    def test_get_write_results(self):
        dest = AirbyteMergeDestination()
        dest.write("a", [{"id": 1}])
        dest.write("b", [{"id": 2}])
        results = dest.get_write_results()
        assert len(results) == 2

    # -- write_messages (Airbyte protocol) ---------------------------------

    def test_write_messages_record_and_state(self):
        dest = AirbyteMergeDestination()
        msgs = [
            AirbyteMessage(
                type="RECORD",
                record={"stream": "users", "data": {"id": 1, "name": "Alice"}, "emitted_at": 1.0},
            ),
            AirbyteMessage(type="STATE", state={"cursor": "abc123"}),
        ]
        state_msgs = list(dest.write_messages(iter(msgs)))
        assert len(state_msgs) == 1
        assert state_msgs[0].state["cursor"] == "abc123"
        assert dest.read_stream("users")[0]["name"] == "Alice"


# ===================================================================
# TestStreamConfig — extra coverage
# ===================================================================


class TestStreamConfig:
    """Test StreamConfig helper."""

    def test_resolve_strategy_name_default(self):
        cfg = StreamConfig(key_column="id")
        assert cfg.resolve_strategy_name("unknown_col") == "LWW"

    def test_resolve_strategy_name_override(self):
        cfg = StreamConfig(key_column="id", strategies={"score": "max"})
        assert cfg.resolve_strategy_name("score") == "MaxWins"


# ===================================================================
# TestStreamStore — extra coverage
# ===================================================================


class TestStreamStore:
    """Test the _StreamStore internal class."""

    def test_upsert_new(self):
        store = _StreamStore("id")
        existing, is_update = store.upsert({"id": 1, "v": "a"}, 1.0)
        assert existing is None
        assert is_update is False

    def test_upsert_existing(self):
        store = _StreamStore("id")
        store.upsert({"id": 1, "v": "a"}, 1.0)
        existing, is_update = store.upsert({"id": 1, "v": "b"}, 2.0)
        assert existing is not None
        assert is_update is True

    def test_missing_key_raises(self):
        store = _StreamStore("id")
        with pytest.raises(ValueError, match="missing key column"):
            store.upsert({"no_id": 1}, 1.0)

    def test_count(self):
        store = _StreamStore("id")
        store.upsert({"id": 1}, 1.0)
        store.upsert({"id": 2}, 2.0)
        assert store.count == 2

    def test_clear(self):
        store = _StreamStore("id")
        store.upsert({"id": 1}, 1.0)
        store.clear()
        assert store.count == 0


# ===================================================================
# TestResolveField — strategy resolution
# ===================================================================


class TestResolveField:
    """Test the _resolve_field helper."""

    def test_equal_values_no_conflict(self):
        val, conflict = _resolve_field(42, 42, "MaxWins")
        assert val == 42
        assert conflict is False

    def test_max_wins(self):
        val, conflict = _resolve_field(10, 20, "MaxWins")
        assert val == 20
        assert conflict is True

    def test_min_wins(self):
        val, conflict = _resolve_field(10, 20, "MinWins")
        assert val == 10
        assert conflict is True
