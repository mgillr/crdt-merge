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

"""Tests for crdt_merge.accelerators.ducklake — DuckLake Semantic Conflict Layer.

All tests mock duckdb so they run without the duckdb dependency.
"""

import time
import pytest

from crdt_merge.strategies import LWW, MaxWins, MinWins, MergeSchema
from crdt_merge.accelerators.ducklake import (
    AuditEntry,
    Branch,
    DuckLakeConflictResolver,
    FieldChange,
    MergeResult,
    SnapshotDiff,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def schema():
    return MergeSchema(default=LWW(), salary=MaxWins(), score=MinWins())

@pytest.fixture
def resolver(schema):
    return DuckLakeConflictResolver(schema=schema)

@pytest.fixture
def snap_a():
    return [
        {"id": 1, "name": "Alice", "salary": 100, "score": 80},
        {"id": 2, "name": "Bob", "salary": 200, "score": 70},
    ]

@pytest.fixture
def snap_b():
    return [
        {"id": 1, "name": "Alicia", "salary": 150, "score": 90},
        {"id": 3, "name": "Charlie", "salary": 300, "score": 60},
    ]

# ═══════════════════════════════════════════════════════════════════════════
# TestMergeSnapshots — core merge
# ═══════════════════════════════════════════════════════════════════════════

class TestMergeSnapshots:
    """Core snapshot merge tests."""

    def test_basic_merge(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        assert isinstance(result, MergeResult)
        assert result.total_rows == 3
        assert result.rows_merged == 1
        assert result.rows_left_only == 1
        assert result.rows_right_only == 1

    def test_merge_max_wins(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        row_1 = [r for r in result.data if r["id"] == 1][0]
        assert row_1["salary"] == 150  # MaxWins: 150 > 100

    def test_merge_min_wins(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        row_1 = [r for r in result.data if r["id"] == 1][0]
        assert row_1["score"] == 80  # MinWins: 80 < 90

    def test_merge_preserves_unique_rows(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        ids = {r["id"] for r in result.data}
        assert ids == {1, 2, 3}

    def test_merge_identical_snapshots(self, resolver, snap_a):
        result = resolver.merge_snapshots(snap_a, list(snap_a), key="id")
        assert result.conflicts_resolved == 0
        assert result.rows_merged == 2

    def test_merge_empty_left(self, resolver, snap_b):
        result = resolver.merge_snapshots([], snap_b, key="id")
        assert result.rows_right_only == 2
        assert result.total_rows == 2

    def test_merge_empty_right(self, resolver, snap_a):
        result = resolver.merge_snapshots(snap_a, [], key="id")
        assert result.rows_left_only == 2
        assert result.total_rows == 2

    def test_merge_both_empty(self, resolver):
        result = resolver.merge_snapshots([], [], key="id")
        assert result.total_rows == 0

    def test_merge_result_to_dict(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        d = result.to_dict()
        assert "total_rows" in d
        assert "conflicts_resolved" in d
        assert d["total_rows"] == 3

    def test_merge_time_tracked(self, resolver, snap_a, snap_b):
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
        assert result.merge_time_ms >= 0

# ═══════════════════════════════════════════════════════════════════════════
# TestDetectChanges — change detection
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectChanges:
    """Merkle-based change detection."""

    def test_identical_snapshots(self, resolver, snap_a):
        diff = resolver.detect_changes(snap_a, list(snap_a), key="id")
        assert diff.is_identical

    def test_added_keys(self, resolver, snap_a, snap_b):
        diff = resolver.detect_changes(snap_a, snap_b, key="id")
        assert 3 in diff.added_keys

    def test_removed_keys(self, resolver, snap_a, snap_b):
        diff = resolver.detect_changes(snap_a, snap_b, key="id")
        assert 2 in diff.removed_keys

    def test_modified_fields(self, resolver, snap_a, snap_b):
        diff = resolver.detect_changes(snap_a, snap_b, key="id")
        modified_fields = {fc.field for fc in diff.modified_fields}
        assert "name" in modified_fields or "salary" in modified_fields

    def test_num_changes(self, resolver, snap_a, snap_b):
        diff = resolver.detect_changes(snap_a, snap_b, key="id")
        assert diff.num_changes > 0

    def test_diff_to_dict(self, resolver, snap_a, snap_b):
        diff = resolver.detect_changes(snap_a, snap_b, key="id")
        d = diff.to_dict()
        assert "added_keys" in d
        assert "removed_keys" in d
        assert "modified_fields" in d

# ═══════════════════════════════════════════════════════════════════════════
# TestAuditTrail
# ═══════════════════════════════════════════════════════════════════════════

class TestAuditTrail:
    """Audit trail after merge."""

    def test_audit_populated_after_merge(self, resolver, snap_a, snap_b):
        resolver.merge_snapshots(snap_a, snap_b, key="id")
        audit = resolver.audit_trail()
        assert len(audit) > 0

    def test_audit_filter_by_key(self, resolver, snap_a, snap_b):
        resolver.merge_snapshots(snap_a, snap_b, key="id")
        audit_1 = resolver.audit_trail(key=1)
        assert all(e["key"] == 1 for e in audit_1)

    def test_audit_clear(self, resolver, snap_a, snap_b):
        resolver.merge_snapshots(snap_a, snap_b, key="id")
        resolver.clear_audit()
        assert len(resolver.audit_trail()) == 0

    def test_audit_entry_has_strategy(self, resolver, snap_a, snap_b):
        resolver.merge_snapshots(snap_a, snap_b, key="id")
        conflicts = [
            e for e in resolver.audit_trail()
            if e["strategy"] != ""
        ]
        assert len(conflicts) > 0
        for c in conflicts:
            assert c["strategy"] in ("LWW", "MaxWins", "MinWins")

# ═══════════════════════════════════════════════════════════════════════════
# TestBranching
# ═══════════════════════════════════════════════════════════════════════════

class TestBranching:
    """Branch management."""

    def test_create_branch(self, resolver, snap_a):
        name = resolver.branch(snap_a, "feature_1")
        assert name == "feature_1"

    def test_list_branches(self, resolver, snap_a):
        resolver.branch(snap_a, "b1")
        resolver.branch(snap_a, "b2")
        branches = resolver.list_branches()
        names = [b["name"] for b in branches]
        assert "b1" in names
        assert "b2" in names

    def test_merge_branches(self, resolver, snap_a, snap_b):
        resolver.branch(snap_a, "br_a")
        resolver.branch(snap_b, "br_b")
        result = resolver.merge_branches("br_a", "br_b", key="id")
        assert result.total_rows == 3

    def test_branch_not_found(self, resolver):
        with pytest.raises(KeyError, match="not found"):
            resolver.merge_branches("nonexistent_a", "nonexistent_b", key="id")

    def test_get_branch_data(self, resolver, snap_a):
        resolver.branch(snap_a, "test_branch")
        data = resolver.get_branch_data("test_branch")
        assert len(data) == 2

    def test_update_branch(self, resolver, snap_a):
        resolver.branch(snap_a, "mutable")
        new_data = [{"id": 10, "name": "New"}]
        resolver.update_branch("mutable", new_data)
        data = resolver.get_branch_data("mutable")
        assert len(data) == 1
        assert data[0]["id"] == 10

# ═══════════════════════════════════════════════════════════════════════════
# TestSnapshots — snapshot registration
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshots:
    """Snapshot registration and listing."""

    def test_register_snapshot(self, resolver, snap_a):
        resolver.register_snapshot("v1", snap_a)
        assert "v1" in resolver.list_snapshots()

    def test_merge_registered_snapshots(self, resolver, snap_a, snap_b):
        resolver.register_snapshot("v1", snap_a)
        resolver.register_snapshot("v2", snap_b)
        result = resolver.merge_snapshots("v1", "v2", key="id")
        assert result.total_rows == 3

    def test_snapshot_not_found(self, resolver):
        with pytest.raises(KeyError, match="not found"):
            resolver.merge_snapshots("nonexistent", [], key="id")

# ═══════════════════════════════════════════════════════════════════════════
# TestHealthCheck
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    """Health check and availability."""

    def test_health_check(self, resolver):
        hc = resolver.health_check()
        assert hc["name"] == "ducklake"
        assert hc["version"] == "0.7.0"

    def test_is_available_without_duckdb(self, resolver):
        import crdt_merge.accelerators.ducklake as mod
        original = mod._duckdb
        mod._duckdb = None
        try:
            assert resolver.is_available() is False
        finally:
            mod._duckdb = original

    def test_repr(self, resolver):
        r = repr(resolver)
        assert "DuckLakeConflictResolver" in r
