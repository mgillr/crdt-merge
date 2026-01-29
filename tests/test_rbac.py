# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.rbac — Role-Based Access Control for merge operations."""

import copy

import pytest

from crdt_merge.rbac import (
    ADMIN,
    MERGER,
    READER,
    WRITER,
    AccessContext,
    Permission,
    Policy,
    RBACController,
    Role,
    SecureMerge,
)
from crdt_merge.strategies import LWW, MaxWins, MergeSchema


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rbac():
    return RBACController()


@pytest.fixture
def sample_left():
    return [
        {"id": 1, "name": "Alice", "age": 30, "secret": "s3cr3t"},
        {"id": 2, "name": "Bob", "age": 25, "secret": "hidden"},
    ]


@pytest.fixture
def sample_right():
    return [
        {"id": 1, "name": "Alicia", "age": 31, "secret": "new-secret"},
        {"id": 3, "name": "Charlie", "age": 40, "secret": "c-secret"},
    ]


# ---------------------------------------------------------------------------
# Permission / Role basics
# ---------------------------------------------------------------------------


class TestPermissionsAndRoles:
    def test_reader_has_read(self):
        assert READER.has_permission(Permission.READ)

    def test_reader_lacks_merge(self):
        assert not READER.has_permission(Permission.MERGE)

    def test_writer_has_write(self):
        assert WRITER.has_permission(Permission.WRITE)

    def test_writer_lacks_merge(self):
        assert not WRITER.has_permission(Permission.MERGE)

    def test_merger_has_merge(self):
        assert MERGER.has_permission(Permission.MERGE)

    def test_admin_has_all(self):
        for perm in Permission:
            assert ADMIN.has_permission(perm), f"ADMIN missing {perm}"

    def test_custom_role(self):
        role = Role(name="custom", permissions=frozenset({Permission.MERGE, Permission.ENCRYPT}))
        assert role.has_permission(Permission.MERGE)
        assert role.has_permission(Permission.ENCRYPT)
        assert not role.has_permission(Permission.ADMIN)

    def test_role_is_frozen(self):
        """Roles are immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            READER.name = "hacked"


# ---------------------------------------------------------------------------
# Policy management
# ---------------------------------------------------------------------------


class TestPolicyManagement:
    def test_add_and_get(self, rbac):
        policy = Policy(role=MERGER)
        rbac.add_policy("node-1", policy)
        assert rbac.get_policy("node-1") is policy

    def test_remove(self, rbac):
        rbac.add_policy("node-1", Policy(role=MERGER))
        rbac.remove_policy("node-1")
        assert rbac.get_policy("node-1") is None

    def test_remove_absent_is_noop(self, rbac):
        rbac.remove_policy("nonexistent")  # should not raise

    def test_replace(self, rbac):
        rbac.add_policy("n", Policy(role=READER))
        rbac.add_policy("n", Policy(role=ADMIN))
        assert rbac.get_policy("n").role is ADMIN

    def test_get_missing_returns_none(self, rbac):
        assert rbac.get_policy("missing") is None


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------


class TestPermissionChecks:
    def test_no_policy_denied(self, rbac):
        ctx = AccessContext(node_id="unknown", role=MERGER)
        assert not rbac.check_permission(ctx, Permission.MERGE)

    def test_reader_cannot_merge(self, rbac):
        rbac.add_policy("n", Policy(role=READER))
        ctx = AccessContext(node_id="n", role=READER)
        assert not rbac.check_permission(ctx, Permission.MERGE)

    def test_merger_can_merge(self, rbac):
        rbac.add_policy("n", Policy(role=MERGER))
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_permission(ctx, Permission.MERGE)

    def test_admin_can_unmerge(self, rbac):
        rbac.add_policy("n", Policy(role=ADMIN))
        ctx = AccessContext(node_id="n", role=ADMIN)
        assert rbac.check_permission(ctx, Permission.UNMERGE)


# ---------------------------------------------------------------------------
# Field access
# ---------------------------------------------------------------------------


class TestFieldAccess:
    def test_denied_fields_override_allowed(self, rbac):
        policy = Policy(
            role=MERGER,
            allowed_fields={"id", "name", "secret"},
            denied_fields={"secret"},
        )
        rbac.add_policy("n", policy)
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_field_access(ctx, "name", Permission.READ)
        assert not rbac.check_field_access(ctx, "secret", Permission.READ)

    def test_allowed_fields_whitelist(self, rbac):
        policy = Policy(role=MERGER, allowed_fields={"id", "name"})
        rbac.add_policy("n", policy)
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_field_access(ctx, "id", Permission.READ)
        assert not rbac.check_field_access(ctx, "age", Permission.READ)

    def test_none_allowed_means_all(self, rbac):
        policy = Policy(role=MERGER, allowed_fields=None)
        rbac.add_policy("n", policy)
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_field_access(ctx, "anything", Permission.READ)

    def test_no_policy_denies_field(self, rbac):
        ctx = AccessContext(node_id="ghost", role=MERGER)
        assert not rbac.check_field_access(ctx, "id", Permission.READ)


# ---------------------------------------------------------------------------
# Strategy access
# ---------------------------------------------------------------------------


class TestStrategyAccess:
    def test_restricted_strategies(self, rbac):
        policy = Policy(role=MERGER, allowed_strategies={"LWW"})
        rbac.add_policy("n", policy)
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_strategy_access(ctx, "LWW")
        assert not rbac.check_strategy_access(ctx, "MaxWins")

    def test_none_strategies_allows_all(self, rbac):
        policy = Policy(role=MERGER, allowed_strategies=None)
        rbac.add_policy("n", policy)
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.check_strategy_access(ctx, "anything")

    def test_no_policy_denies_strategy(self, rbac):
        ctx = AccessContext(node_id="ghost", role=MERGER)
        assert not rbac.check_strategy_access(ctx, "LWW")


# ---------------------------------------------------------------------------
# enforce_merge
# ---------------------------------------------------------------------------


class TestEnforceMerge:
    def test_no_merge_permission_raises(self, rbac, sample_left):
        rbac.add_policy("n", Policy(role=READER))
        ctx = AccessContext(node_id="n", role=READER)
        with pytest.raises(PermissionError, match="MERGE"):
            rbac.enforce_merge(ctx, sample_left)

    def test_record_count_limit(self, rbac, sample_left):
        rbac.add_policy("n", Policy(role=MERGER, max_record_count=1))
        ctx = AccessContext(node_id="n", role=MERGER)
        with pytest.raises(PermissionError, match="exceeds limit"):
            rbac.enforce_merge(ctx, sample_left)

    def test_fields_filtered(self, rbac, sample_left):
        rbac.add_policy("n", Policy(role=MERGER, denied_fields={"secret"}))
        ctx = AccessContext(node_id="n", role=MERGER)
        result = rbac.enforce_merge(ctx, sample_left)
        for rec in result:
            assert "secret" not in rec
            assert "id" in rec

    def test_empty_records(self, rbac):
        rbac.add_policy("n", Policy(role=MERGER))
        ctx = AccessContext(node_id="n", role=MERGER)
        assert rbac.enforce_merge(ctx, []) == []


# ---------------------------------------------------------------------------
# SecureMerge — integration with real merge API
# ---------------------------------------------------------------------------


class TestSecureMerge:
    def test_merge_without_context(self, rbac, sample_left, sample_right):
        """No context = pass-through (backwards compatible)."""
        sm = SecureMerge(rbac)
        result = sm.merge(sample_left, sample_right, key="id")
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_merge_with_schema(self, rbac, sample_left, sample_right):
        rbac.add_policy("n", Policy(role=MERGER))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=MERGER)
        schema = MergeSchema(default=LWW())
        result = sm.merge(sample_left, sample_right, key="id", schema=schema, context=ctx)
        assert isinstance(result, list)

    def test_reader_cannot_merge(self, rbac, sample_left, sample_right):
        rbac.add_policy("n", Policy(role=READER))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=READER)
        with pytest.raises(PermissionError):
            sm.merge(sample_left, sample_right, key="id", context=ctx)

    def test_denied_fields_stripped(self, rbac, sample_left, sample_right):
        rbac.add_policy("n", Policy(role=MERGER, denied_fields={"secret"}))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=MERGER)
        result = sm.merge(sample_left, sample_right, key="id", context=ctx)
        for rec in result:
            assert "secret" not in rec

    def test_allowed_fields_whitelist(self, rbac, sample_left, sample_right):
        rbac.add_policy(
            "n",
            Policy(role=MERGER, allowed_fields={"id", "name"}),
        )
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=MERGER)
        result = sm.merge(sample_left, sample_right, key="id", context=ctx)
        for rec in result:
            assert "age" not in rec
            assert "secret" not in rec

    def test_record_count_limit(self, rbac, sample_left, sample_right):
        rbac.add_policy("n", Policy(role=MERGER, max_record_count=2))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=MERGER)
        with pytest.raises(PermissionError, match="exceeds limit"):
            sm.merge(sample_left, sample_right, key="id", context=ctx)

    def test_strategy_restriction(self, rbac, sample_left, sample_right):
        rbac.add_policy("n", Policy(role=MERGER, allowed_strategies={"LWW"}))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="n", role=MERGER)
        schema = MergeSchema(default=MaxWins())
        with pytest.raises(PermissionError, match="not allowed"):
            sm.merge(sample_left, sample_right, key="id", schema=schema, context=ctx)

    def test_admin_passes_all_checks(self, rbac, sample_left, sample_right):
        rbac.add_policy("a", Policy(role=ADMIN))
        sm = SecureMerge(rbac)
        ctx = AccessContext(node_id="a", role=ADMIN)
        result = sm.merge(sample_left, sample_right, key="id", context=ctx)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_access_context_metadata(self):
        ctx = AccessContext(node_id="n", role=READER, metadata={"tenant": "acme"})
        assert ctx.metadata["tenant"] == "acme"

    def test_policy_defaults(self):
        p = Policy(role=READER)
        assert p.allowed_fields is None
        assert p.allowed_strategies is None
        assert p.denied_fields == set()
        assert p.max_record_count is None

    def test_empty_denied_fields(self, rbac, sample_left):
        rbac.add_policy("n", Policy(role=MERGER, denied_fields=set()))
        ctx = AccessContext(node_id="n", role=MERGER)
        result = rbac.enforce_merge(ctx, sample_left)
        assert result == sample_left
