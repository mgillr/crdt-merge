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

"""Property-based tests for RBAC security invariants and AuditLog behaviour.

Covers: permission grant/deny, role composition, field-access filtering,
audit log ordering, hash-chain integrity, and revocation semantics.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

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
)
from crdt_merge.audit import AuditEntry, AuditLog

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_node_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
)

_field_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=12,
)

_all_roles = st.sampled_from([READER, WRITER, MERGER, ADMIN])

_all_permissions = st.sampled_from(list(Permission))


# ---------------------------------------------------------------------------
# Permission model — basic grant/deny
# ---------------------------------------------------------------------------


@given(node=_node_id, role=_all_roles, perm=_all_permissions)
@settings(max_examples=50)
def test_policy_registered_node_uses_role_permissions(node, role, perm):
    """A node with a registered policy is granted exactly the role's permissions."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=role))
    ctx = AccessContext(node_id=node, role=role)
    expected = role.has_permission(perm)
    assert rbac.check_permission(ctx, perm) == expected


@given(node=_node_id)
@settings(max_examples=50)
def test_unregistered_node_always_denied(node):
    """A node with no registered policy is always denied for every permission."""
    rbac = RBACController()
    ctx = AccessContext(node_id=node, role=ADMIN)
    for perm in Permission:
        assert rbac.check_permission(ctx, perm) is False


@given(node=_node_id, perm=_all_permissions)
@settings(max_examples=50)
def test_admin_has_all_permissions(node, perm):
    """ADMIN role has every permission."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=ADMIN))
    ctx = AccessContext(node_id=node, role=ADMIN)
    assert rbac.check_permission(ctx, perm) is True


@given(node=_node_id)
@settings(max_examples=50)
def test_reader_lacks_merge_permission(node):
    """READER role must not have MERGE permission."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=READER))
    ctx = AccessContext(node_id=node, role=READER)
    assert rbac.check_permission(ctx, Permission.MERGE) is False


# ---------------------------------------------------------------------------
# Revocation — removing a policy is immediately effective
# ---------------------------------------------------------------------------


@given(node=_node_id)
@settings(max_examples=50)
def test_revoke_policy_denies_all_permissions(node):
    """After remove_policy, the node is denied all permissions."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=ADMIN))
    rbac.remove_policy(node)
    ctx = AccessContext(node_id=node, role=ADMIN)
    for perm in Permission:
        assert rbac.check_permission(ctx, perm) is False


# ---------------------------------------------------------------------------
# Field access — denied_fields and allowed_fields
# ---------------------------------------------------------------------------


@given(node=_node_id, secret=_field_name)
@settings(max_examples=50)
def test_denied_field_is_always_blocked(node, secret):
    """A field in denied_fields is always blocked regardless of role."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=ADMIN, denied_fields={secret}))
    ctx = AccessContext(node_id=node, role=ADMIN)
    assert rbac.check_field_access(ctx, secret, Permission.READ) is False


@given(node=_node_id, allowed=_field_name, other=_field_name)
@settings(max_examples=50)
def test_allowed_fields_restricts_access(node, allowed, other):
    """When allowed_fields is set, only listed fields pass check_field_access."""
    assume(allowed != other)
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=ADMIN, allowed_fields={allowed}))
    ctx = AccessContext(node_id=node, role=ADMIN)
    assert rbac.check_field_access(ctx, allowed, Permission.READ) is True
    assert rbac.check_field_access(ctx, other, Permission.READ) is False


@given(node=_node_id, field=_field_name)
@settings(max_examples=50)
def test_reader_without_denied_fields_can_read_all(node, field):
    """READER without denied_fields can read any field."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=READER))
    ctx = AccessContext(node_id=node, role=READER)
    assert rbac.check_field_access(ctx, field, Permission.READ) is True


# ---------------------------------------------------------------------------
# enforce_merge — raises on missing MERGE permission
# ---------------------------------------------------------------------------


@given(node=_node_id)
@settings(max_examples=50)
def test_enforce_merge_raises_for_reader(node):
    """enforce_merge raises PermissionError when the node lacks MERGE."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=READER))
    ctx = AccessContext(node_id=node, role=READER)
    with pytest.raises(PermissionError):
        rbac.enforce_merge(ctx, [{"id": 1}])


@given(node=_node_id)
@settings(max_examples=50)
def test_enforce_merge_succeeds_for_merger(node):
    """enforce_merge does not raise when the node has MERGE permission."""
    rbac = RBACController()
    rbac.add_policy(node, Policy(role=MERGER))
    ctx = AccessContext(node_id=node, role=MERGER)
    result = rbac.enforce_merge(ctx, [{"id": 1, "val": 42}])
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# AuditLog — ordering and chain integrity
# ---------------------------------------------------------------------------


@given(
    node=_node_id,
    num_ops=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50)
def test_audit_log_entries_are_in_order(node, num_ops):
    """Timestamps of audit entries are non-decreasing."""
    log = AuditLog(node_id=node)
    for i in range(num_ops):
        log.log_operation("merge", input_data={"i": i}, output_data={"i": i})
    entries = log.entries
    timestamps = [e.timestamp for e in entries]
    assert all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))


@given(node=_node_id, num_ops=st.integers(min_value=0, max_value=8))
@settings(max_examples=50)
def test_audit_log_chain_always_verifies(node, num_ops):
    """verify_chain() always returns True for a freshly appended log."""
    log = AuditLog(node_id=node)
    for i in range(num_ops):
        log.log_operation("merge", input_data=i, output_data=i * 2)
    assert log.verify_chain() is True


@given(node=_node_id)
@settings(max_examples=50)
def test_audit_log_empty_chain_verifies(node):
    """An empty audit log verifies cleanly."""
    log = AuditLog(node_id=node)
    assert log.verify_chain() is True


@given(
    node=_node_id,
    left=st.lists(st.integers(0, 10), min_size=1, max_size=4),
    right=st.lists(st.integers(0, 10), min_size=1, max_size=4),
)
@settings(max_examples=50)
def test_audit_log_merge_records_counts(node, left, right):
    """log_merge records correct left/right/result counts in metadata."""
    log = AuditLog(node_id=node)
    result = left + right
    entry = log.log_merge(left, right, result)
    assert entry.metadata["left_count"] == len(left)
    assert entry.metadata["right_count"] == len(right)
    assert entry.metadata["result_count"] == len(result)


@given(node=_node_id, num_ops=st.integers(min_value=2, max_value=8))
@settings(max_examples=50)
def test_audit_log_prev_hash_links_correctly(node, num_ops):
    """Each entry's prev_hash matches the preceding entry's entry_hash."""
    log = AuditLog(node_id=node)
    for i in range(num_ops):
        log.log_operation("custom", input_data=i, output_data=i)
    entries = log.entries
    for i in range(1, len(entries)):
        assert entries[i].prev_hash == entries[i - 1].entry_hash
