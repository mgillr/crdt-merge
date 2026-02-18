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

"""Tests for crdt_merge.accelerators.sqlite_ext — SQLiteCRDTMerge.

All tests use in-memory SQLite databases (no file I/O required).
Tests cover init, register/unregister, create/drop CRDT tables, merge_insert,
read_table, merge_tables, sync_from, execute_sql, get_clock, compact,
health_check, and is_available.
"""

import os
import sqlite3
import tempfile

import pytest

from crdt_merge.accelerators.sqlite_ext import SQLiteCRDTMerge
from crdt_merge.strategies import MergeSchema, MaxWins, MinWins, LWW
from crdt_merge.accelerators import ACCELERATOR_REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ext():
    """In-memory extension with a users CRDT table pre-created."""
    e = SQLiteCRDTMerge(db_path=":memory:")
    e.register()
    e.create_crdt_table(
        "users",
        columns={"name": "TEXT", "score": "REAL"},
        key="id",
        strategies={"score": "max"},
    )
    yield e
    e.close()


@pytest.fixture
def populated(ext):
    """Extension with two rows pre-inserted."""
    ext.merge_insert("users", [
        {"id": "1", "name": "Alice", "score": 100.0},
        {"id": "2", "name": "Bob", "score": 200.0},
    ])
    return ext


# ===================================================================
# TestInit
# ===================================================================

class TestInit:
    def test_name_attribute(self):
        e = SQLiteCRDTMerge()
        assert e.name == "sqlite_ext"
        e.close()

    def test_version_attribute(self):
        e = SQLiteCRDTMerge()
        assert e.version == "0.7.0"
        e.close()

    def test_default_db_path_is_memory(self):
        e = SQLiteCRDTMerge()
        assert e._db_path == ":memory:"
        e.close()

    def test_registered_false_at_init(self):
        e = SQLiteCRDTMerge()
        assert e._registered is False
        e.close()

    def test_conn_property(self):
        e = SQLiteCRDTMerge()
        assert e.conn is not None
        e.close()

    def test_registered_in_accelerator_registry(self):
        assert "sqlite_ext" in ACCELERATOR_REGISTRY


# ===================================================================
# TestRegisterUnregister
# ===================================================================

class TestRegisterUnregister:
    def test_register_sets_flag(self, ext):
        assert ext._registered is True

    def test_unregister_clears_flag(self, ext):
        ext.unregister()
        assert ext._registered is False

    def test_crdt_functions_available_after_register(self, ext):
        """crdt_max and crdt_min should be callable via SQL."""
        row = ext.execute_sql("SELECT crdt_max(10, 20)")
        assert row[0]["crdt_max(10, 20)"] == 20

    def test_crdt_min_function(self, ext):
        row = ext.execute_sql("SELECT crdt_min(10, 20)")
        assert row[0]["crdt_min(10, 20)"] == 10

    def test_crdt_merge_function_max(self, ext):
        row = ext.execute_sql("SELECT crdt_merge(5, 15, 'max')")
        assert row[0]["crdt_merge(5, 15, 'max')"] == 15


# ===================================================================
# TestCRDTTableManagement
# ===================================================================

class TestCRDTTableManagement:
    def test_list_crdt_tables_contains_users(self, ext):
        assert "users" in ext.list_crdt_tables()

    def test_create_second_table(self, ext):
        ext.create_crdt_table(
            "products",
            columns={"price": "REAL", "stock": "INTEGER"},
            key="sku",
        )
        assert "products" in ext.list_crdt_tables()

    def test_drop_removes_from_list(self, ext):
        ext.drop_crdt_table("users")
        assert "users" not in ext.list_crdt_tables()

    def test_table_info_returns_key_column(self, ext):
        info = ext.table_info("users")
        assert info["key_column"] == "id"

    def test_table_info_returns_strategies(self, ext):
        info = ext.table_info("users")
        assert "score" in info["strategies"]
        assert info["strategies"]["score"] == "max"

    def test_table_info_not_found_raises(self, ext):
        with pytest.raises(ValueError):
            ext.table_info("nonexistent")

    def test_table_info_row_count(self, populated):
        info = populated.table_info("users")
        assert info["row_count"] == 2


# ===================================================================
# TestMergeInsert
# ===================================================================

class TestMergeInsert:
    def test_insert_new_record(self, ext):
        result = ext.merge_insert("users", [{"id": "10", "name": "Zara", "score": 500.0}])
        assert result["inserted"] == 1
        assert result["merged"] == 0
        assert result["total"] == 1

    def test_merge_existing_max_strategy(self, populated):
        populated.merge_insert("users", [{"id": "1", "name": "Alice", "score": 150.0}])
        rows = populated.read_table("users")
        r1 = next(r for r in rows if r["id"] == "1")
        assert r1["score"] == 150.0  # max(100, 150) = 150

    def test_merge_existing_max_strategy_keeps_higher(self, populated):
        populated.merge_insert("users", [{"id": "1", "name": "Alice", "score": 50.0}])
        rows = populated.read_table("users")
        r1 = next(r for r in rows if r["id"] == "1")
        assert r1["score"] == 100.0  # max(100, 50) = 100

    def test_insert_and_merge_in_one_batch(self, ext):
        result = ext.merge_insert("users", [
            {"id": "1", "name": "Alice", "score": 100.0},
        ])
        assert result["inserted"] == 1
        result2 = ext.merge_insert("users", [
            {"id": "1", "name": "Alice2", "score": 120.0},
            {"id": "2", "name": "Bob", "score": 200.0},
        ])
        assert result2["merged"] == 1
        assert result2["inserted"] == 1

    def test_record_without_key_skipped(self, ext):
        result = ext.merge_insert("users", [{"name": "NoKey", "score": 99.0}])
        assert result["inserted"] == 0
        assert result["total"] == 1

    def test_merge_insert_unknown_table_raises(self, ext):
        with pytest.raises(ValueError):
            ext.merge_insert("nonexistent", [{"id": "1"}])


# ===================================================================
# TestReadTable
# ===================================================================

class TestReadTable:
    def test_read_empty_table(self, ext):
        rows = ext.read_table("users")
        assert rows == []

    def test_read_populated_table(self, populated):
        rows = populated.read_table("users")
        assert len(rows) == 2

    def test_meta_columns_excluded_by_default(self, populated):
        rows = populated.read_table("users")
        for r in rows:
            assert "_crdt_ts" not in r
            assert "_crdt_node" not in r

    def test_meta_columns_included_when_requested(self, populated):
        rows = populated.read_table("users", include_meta=True)
        assert "_crdt_ts" in rows[0]
        assert "_crdt_node" in rows[0]


# ===================================================================
# TestMergeTables
# ===================================================================

class TestMergeTables:
    def test_merge_two_raw_tables(self, ext):
        ext.conn.execute("CREATE TABLE ta (id TEXT PRIMARY KEY, val REAL)")
        ext.conn.execute("INSERT INTO ta VALUES ('a', 10.0)")
        ext.conn.execute("CREATE TABLE tb (id TEXT PRIMARY KEY, val REAL)")
        ext.conn.execute("INSERT INTO tb VALUES ('a', 25.0), ('b', 5.0)")
        ext.conn.commit()

        merged = ext.merge_tables("ta", "tb", key="id", strategies={"val": "max"})
        assert len(merged) == 2
        ra = next(r for r in merged if r["id"] == "a")
        assert ra["val"] == 25.0

    def test_merge_disjoint_tables(self, ext):
        ext.conn.execute("CREATE TABLE left_t (id TEXT PRIMARY KEY, v TEXT)")
        ext.conn.execute("INSERT INTO left_t VALUES ('x', 'hello')")
        ext.conn.execute("CREATE TABLE right_t (id TEXT PRIMARY KEY, v TEXT)")
        ext.conn.execute("INSERT INTO right_t VALUES ('y', 'world')")
        ext.conn.commit()

        merged = ext.merge_tables("left_t", "right_t", key="id")
        ids = {r["id"] for r in merged}
        assert ids == {"x", "y"}


# ===================================================================
# TestVectorClock
# ===================================================================

class TestVectorClock:
    def test_clock_created_on_insert(self, populated):
        clock = populated.get_clock("users", "1")
        assert "local" in clock
        assert clock["local"] >= 1

    def test_clock_increments_on_update(self, populated):
        before = populated.get_clock("users", "1").get("local", 0)
        populated.merge_insert("users", [{"id": "1", "name": "Updated", "score": 150.0}])
        after = populated.get_clock("users", "1").get("local", 0)
        assert after > before


# ===================================================================
# TestCompact
# ===================================================================

class TestCompact:
    def test_compact_returns_dict(self, populated):
        result = populated.compact("users")
        assert "clock_entries_removed" in result

    def test_compact_removes_orphaned_entries(self, populated):
        # Delete a user directly so clock entry becomes orphaned
        populated.conn.execute("DELETE FROM users WHERE id = '1'")
        populated.conn.commit()
        result = populated.compact("users")
        assert result["clock_entries_removed"] >= 1

    def test_compact_nonexistent_table_raises(self, ext):
        with pytest.raises(ValueError):
            ext.compact("nonexistent")


# ===================================================================
# TestExecuteSQL
# ===================================================================

class TestExecuteSQL:
    def test_execute_sql_select(self, populated):
        rows = populated.execute_sql(
            "SELECT * FROM users WHERE id = ?", ("1",)
        )
        assert len(rows) == 1

    def test_execute_sql_returns_empty_for_no_match(self, populated):
        rows = populated.execute_sql(
            "SELECT * FROM users WHERE id = ?", ("999",)
        )
        assert rows == []


# ===================================================================
# TestSyncFrom
# ===================================================================

class TestSyncFrom:
    def test_sync_inserts_remote_records(self, ext):
        tmppath = tempfile.mktemp(suffix=".db")
        try:
            remote = sqlite3.connect(tmppath)
            remote.execute(
                "CREATE TABLE users "
                "(id TEXT PRIMARY KEY, name TEXT, score REAL, _crdt_ts REAL, _crdt_node TEXT)"
            )
            remote.execute("INSERT INTO users VALUES ('99', 'Remote', 777.0, 0.0, 'remote')")
            remote.commit()
            remote.close()

            stats = ext.sync_from(tmppath, ["users"])
            assert stats["users"] == 1
            rows = ext.read_table("users")
            ids = [r["id"] for r in rows]
            assert "99" in ids
        finally:
            os.unlink(tmppath)


# ===================================================================
# TestHealthAndAvailability
# ===================================================================

class TestHealthAndAvailability:
    def test_health_check_sqlite_available(self, ext):
        hc = ext.health_check()
        assert hc["sqlite_available"] is True

    def test_health_check_status_ok(self, ext):
        hc = ext.health_check()
        assert hc["status"] == "ok"

    def test_health_check_lists_crdt_tables(self, ext):
        hc = ext.health_check()
        assert "users" in hc["crdt_tables"]

    def test_health_check_db_path(self, ext):
        hc = ext.health_check()
        assert hc["db_path"] == ":memory:"

    def test_is_available_true(self, ext):
        assert ext.is_available() is True

    def test_repr_contains_class_name(self, ext):
        assert "SQLiteCRDTMerge" in repr(ext)

    def test_repr_contains_db_path(self, ext):
        assert ":memory:" in repr(ext)
