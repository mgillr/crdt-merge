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

"""Tests for crdt_merge.accelerators.sqlite_ext — SQLite CRDT extension.

Uses stdlib ``sqlite3`` (in-memory databases) — no external dependencies.
"""

import os
import tempfile

import pytest

from crdt_merge.accelerators.sqlite_ext import SQLiteCRDTMerge
from crdt_merge.strategies import MergeSchema, MaxWins, LWW

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ext():
    """Create an in-memory SQLiteCRDTMerge with a sample table."""
    e = SQLiteCRDTMerge(db_path=":memory:")
    e.register()
    e.create_crdt_table(
        "users",
        columns={"name": "TEXT", "salary": "REAL"},
        key="id",
        strategies={"salary": "max"},
    )
    return e

@pytest.fixture
def populated_ext(ext):
    """Extension with sample data inserted."""
    ext.merge_insert("users", [
        {"id": "1", "name": "Alice", "salary": 100},
        {"id": "2", "name": "Bob", "salary": 200},
    ])
    return ext

# ---------------------------------------------------------------------------
# Tests (25)
# ---------------------------------------------------------------------------

class TestSQLiteCRDTMerge:
    def test_create_default(self):
        ext = SQLiteCRDTMerge()
        assert ext.name == "sqlite_ext"
        assert ext.version == "0.7.0"
        ext.close()

    def test_register(self, ext):
        assert ext._registered is True

    def test_unregister(self, ext):
        ext.unregister()
        assert ext._registered is False

    def test_create_crdt_table(self, ext):
        tables = ext.list_crdt_tables()
        assert "users" in tables

    def test_drop_crdt_table(self, ext):
        ext.drop_crdt_table("users")
        assert "users" not in ext.list_crdt_tables()

    def test_list_crdt_tables(self, ext):
        ext.create_crdt_table("products", columns={"price": "REAL"}, key="sku")
        tables = ext.list_crdt_tables()
        assert "users" in tables
        assert "products" in tables

    def test_table_info(self, populated_ext):
        info = populated_ext.table_info("users")
        assert info["key_column"] == "id"
        assert info["row_count"] == 2
        assert "salary" in info["strategies"]

    def test_table_info_not_found(self, ext):
        with pytest.raises(ValueError):
            ext.table_info("nonexistent")

class TestMergeInsert:
    def test_insert_new_records(self, ext):
        result = ext.merge_insert("users", [
            {"id": "1", "name": "Alice", "salary": 100},
        ])
        assert result["inserted"] == 1
        assert result["merged"] == 0

    def test_merge_existing_lww(self, populated_ext):
        result = populated_ext.merge_insert("users", [
            {"id": "1", "name": "Alicia", "salary": 90},
        ])
        assert result["merged"] == 1
        rows = populated_ext.read_table("users")
        r1 = next(r for r in rows if r["id"] == "1")
        # salary: max(100, 90) = 100
        assert r1["salary"] == 100.0

    def test_merge_existing_max_strategy(self, populated_ext):
        populated_ext.merge_insert("users", [
            {"id": "1", "name": "Alice", "salary": 150},
        ])
        rows = populated_ext.read_table("users")
        r1 = next(r for r in rows if r["id"] == "1")
        assert r1["salary"] == 150.0

    def test_merge_insert_mixed(self, ext):
        result = ext.merge_insert("users", [
            {"id": "1", "name": "Alice", "salary": 100},
        ])
        assert result["inserted"] == 1
        result2 = ext.merge_insert("users", [
            {"id": "1", "name": "Alice2", "salary": 120},
            {"id": "3", "name": "Charlie", "salary": 300},
        ])
        assert result2["merged"] == 1
        assert result2["inserted"] == 1

    def test_merge_insert_skip_none_key(self, ext):
        result = ext.merge_insert("users", [
            {"name": "NoKey", "salary": 100},
        ])
        assert result["total"] == 1
        assert result["inserted"] == 0

    def test_merge_insert_not_crdt_table(self, ext):
        with pytest.raises(ValueError):
            ext.merge_insert("nonexistent", [{"id": "1"}])

class TestReadTable:
    def test_read_empty(self, ext):
        rows = ext.read_table("users")
        assert rows == []

    def test_read_populated(self, populated_ext):
        rows = populated_ext.read_table("users")
        assert len(rows) == 2
        # meta columns should be excluded
        for r in rows:
            assert "_crdt_ts" not in r

    def test_read_include_meta(self, populated_ext):
        rows = populated_ext.read_table("users", include_meta=True)
        assert "_crdt_ts" in rows[0]
        assert "_crdt_node" in rows[0]

class TestMergeTables:
    def test_merge_two_tables(self, ext):
        ext.conn.execute("CREATE TABLE t1 (id TEXT PRIMARY KEY, val REAL)")
        ext.conn.execute("INSERT INTO t1 VALUES ('a', 10)")
        ext.conn.execute("CREATE TABLE t2 (id TEXT PRIMARY KEY, val REAL)")
        ext.conn.execute("INSERT INTO t2 VALUES ('a', 20)")
        ext.conn.execute("INSERT INTO t2 VALUES ('b', 30)")
        ext.conn.commit()

        merged = ext.merge_tables("t1", "t2", key="id", strategies={"val": "max"})
        assert len(merged) == 2
        ra = next(r for r in merged if r["id"] == "a")
        assert ra["val"] == 20.0

class TestSync:
    def test_sync_from_remote(self, ext):
        """Sync from a separate in-memory db using a temp file."""
        import sqlite3
        tmppath = tempfile.mktemp(suffix=".db")
        try:
            # Create remote db
            remote = sqlite3.connect(tmppath)
            remote.execute("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT, salary REAL, _crdt_ts REAL, _crdt_node TEXT)")
            remote.execute("INSERT INTO users VALUES ('10', 'Zara', 500, 0, 'remote')")
            remote.commit()
            remote.close()

            stats = ext.sync_from(tmppath, ["users"], node_id="remote")
            assert stats["users"] == 1
            rows = ext.read_table("users")
            ids = [r["id"] for r in rows]
            assert "10" in ids
        finally:
            os.unlink(tmppath)

class TestUtility:
    def test_execute_sql(self, populated_ext):
        rows = populated_ext.execute_sql("SELECT * FROM users WHERE id = ?", ("1",))
        assert len(rows) == 1

    def test_get_clock(self, populated_ext):
        clock = populated_ext.get_clock("users", "1")
        assert "local" in clock
        assert clock["local"] >= 1

    def test_compact(self, populated_ext):
        result = populated_ext.compact("users")
        assert "clock_entries_removed" in result

    def test_health_check(self, ext):
        hc = ext.health_check()
        assert hc["sqlite_available"] is True
        assert hc["status"] == "ok"
        assert "users" in hc["crdt_tables"]

    def test_is_available(self, ext):
        assert ext.is_available() is True

    def test_repr(self, ext):
        r = repr(ext)
        assert "SQLiteCRDTMerge" in r
        assert ":memory:" in r

    def test_registered_in_registry(self):
        from crdt_merge.accelerators import ACCELERATOR_REGISTRY
        assert "sqlite_ext" in ACCELERATOR_REGISTRY
