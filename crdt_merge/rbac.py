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

"""Role-Based Access Control (RBAC) for crdt-merge operations.

Provides policy-based access control that governs which nodes can perform
merge, encrypt, unmerge, and audit operations on specific fields using
specific strategies.

Example::

    from crdt_merge.rbac import RBACController, Role, Policy, Permission, AccessContext, MERGER

    rbac = RBACController()
    policy = Policy(role=MERGER, denied_fields={"secret"})
    rbac.add_policy("node-1", policy)

    ctx = AccessContext(node_id="node-1", role=MERGER)
    assert rbac.check_permission(ctx, Permission.MERGE)
"""

from __future__ import annotations

import copy
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Any, Dict, List, Optional, Set

from crdt_merge import merge as _crdt_merge

__all__ = [
    "logger",
    "Permission",
    "Role",
    "READER",
    "WRITER",
    "MERGER",
    "ADMIN",
    "Policy",
    "AccessContext",
    "RBACController",
    "SecureMerge",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class Permission(Flag):
    """Fine-grained permissions for merge operations."""

    READ = auto()
    WRITE = auto()
    MERGE = auto()
    ADMIN = auto()
    UNMERGE = auto()
    ENCRYPT = auto()
    AUDIT_READ = auto()


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Role:
    """Named collection of permissions."""

    name: str
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def has_permission(self, perm: Permission) -> bool:
        """Return *True* if this role includes *perm*."""
        return perm in self.permissions


# Pre-defined roles --------------------------------------------------------

READER = Role(
    name="reader",
    permissions=frozenset({Permission.READ, Permission.AUDIT_READ}),
)

WRITER = Role(
    name="writer",
    permissions=frozenset({Permission.READ, Permission.WRITE}),
)

MERGER = Role(
    name="merger",
    permissions=frozenset({Permission.READ, Permission.WRITE, Permission.MERGE}),
)

ADMIN = Role(
    name="admin",
    permissions=frozenset(
        {
            Permission.READ,
            Permission.WRITE,
            Permission.MERGE,
            Permission.ADMIN,
            Permission.UNMERGE,
            Permission.ENCRYPT,
            Permission.AUDIT_READ,
        }
    ),
)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass
class Policy:
    """Access-control policy bound to a node via :class:`RBACController`.

    Parameters
    ----------
    role:
        The :class:`Role` that dictates base permissions.
    allowed_fields:
        Whitelist of field names the node may access.  ``None`` means *all*.
    allowed_strategies:
        Whitelist of strategy class names (e.g. ``"LWW"``, ``"MaxWins"``).
        ``None`` means *all*.
    denied_fields:
        Explicit deny list — takes priority over *allowed_fields*.
    max_record_count:
        Optional ceiling on the number of input records per merge.
    """

    role: Role
    allowed_fields: Optional[Set[str]] = None
    allowed_strategies: Optional[Set[str]] = None
    denied_fields: Set[str] = field(default_factory=set)
    max_record_count: Optional[int] = None


# ---------------------------------------------------------------------------
# AccessContext
# ---------------------------------------------------------------------------


@dataclass
class AccessContext:
    """Runtime context passed to every RBAC check."""

    node_id: str
    role: Role
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY: Dict[Role, Set[Role]] = {
    ADMIN: {ADMIN, MERGER, WRITER, READER},
    MERGER: {MERGER, WRITER, READER},
    WRITER: {WRITER, READER},
    READER: {READER},
}


# ---------------------------------------------------------------------------
# RBACController
# ---------------------------------------------------------------------------


class RBACController:
    """Central policy store and enforcement engine.

    Thread-safe — all mutations are guarded by an internal lock.

    Parameters
    ----------
    allow_unknown_nodes:
        When ``False`` (default) unregistered nodes are denied all
        permissions.  When ``True`` the legacy behaviour is preserved
        (full access for unregistered nodes).
    """

    def __init__(self, allow_unknown_nodes: bool = False) -> None:
        self._policies: Dict[str, Policy] = {}
        self._lock = threading.Lock()
        self._allow_unknown_nodes = allow_unknown_nodes

    # -- policy management ---------------------------------------------------

    def add_policy(self, node_id: str, policy: Policy) -> None:
        """Register *policy* for *node_id*, replacing any existing one."""
        with self._lock:
            self._policies[node_id] = policy
            logger.debug("policy added for node %s (role=%s)", node_id, policy.role.name)

    def remove_policy(self, node_id: str) -> None:
        """Remove the policy for *node_id*.  No-op if absent."""
        with self._lock:
            self._policies.pop(node_id, None)

    def get_policy(self, node_id: str) -> Optional[Policy]:
        """Return the policy for *node_id*, or ``None``."""
        with self._lock:
            return self._policies.get(node_id)

    # -- permission checks ---------------------------------------------------

    def _effective_permissions(self, role: Role) -> frozenset:
        """Return the union of permissions granted by *role* and all roles
        that *role* subsumes in the hierarchy."""
        effective_roles = _ROLE_HIERARCHY.get(role, {role})
        perms: Set[Permission] = set()
        for r in effective_roles:
            perms |= set(r.permissions)
        return frozenset(perms)

    def check_permission(self, context: AccessContext, permission: Permission) -> bool:
        """Return *True* if *context* grants *permission*.

        Applies role hierarchy so ADMIN subsumes MERGER ⊃ WRITER ⊃ READER.
        Unregistered nodes are denied when ``allow_unknown_nodes=False``.
        """
        policy = self.get_policy(context.node_id)
        if policy is None:
            if not self._allow_unknown_nodes:
                logger.warning(
                    "RBAC: unknown node '%s' denied (default-deny)", context.node_id
                )
                return False
            # Legacy: allow full access
            return context.role.has_permission(permission)
        effective = self._effective_permissions(context.role)
        return permission in effective

    def check_field_access(
        self, context: AccessContext, field_name: str, permission: Permission
    ) -> bool:
        """Return *True* if the node may apply *permission* to *field_name*."""
        if not self.check_permission(context, permission):
            return False
        policy = self.get_policy(context.node_id)
        if policy is None:
            return False
        # Explicit deny always wins
        if field_name in policy.denied_fields:
            return False
        # If an allow-list is set, field must be in it
        if policy.allowed_fields is not None and field_name not in policy.allowed_fields:
            return False
        return True

    def check_strategy_access(self, context: AccessContext, strategy: str) -> bool:
        """Return *True* if the node may use *strategy*."""
        policy = self.get_policy(context.node_id)
        if policy is None:
            return False
        if policy.allowed_strategies is not None and strategy not in policy.allowed_strategies:
            return False
        return True

    # -- high-level enforcement ---------------------------------------------

    def enforce_merge(
        self,
        context: AccessContext,
        records: List[Dict[str, Any]],
        schema: Any = None,
    ) -> List[Dict[str, Any]]:
        """Filter *records* according to the node's READ policy.

        Raises :class:`PermissionError` if the node lacks ``MERGE`` permission.
        Raises :class:`PermissionError` if *records* exceeds *max_record_count*.
        """
        if not self.check_permission(context, Permission.MERGE):
            raise PermissionError(
                f"Node '{context.node_id}' lacks MERGE permission"
            )
        policy = self.get_policy(context.node_id)
        if policy is not None and policy.max_record_count is not None:
            if len(records) > policy.max_record_count:
                raise PermissionError(
                    f"Record count {len(records)} exceeds limit "
                    f"{policy.max_record_count} for node '{context.node_id}'"
                )
        return self._filter_fields(context, records)

    # -- internal helpers ----------------------------------------------------

    def _filter_fields(
        self, context: AccessContext, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Strip fields the node is not allowed to READ."""
        policy = self.get_policy(context.node_id)
        if policy is None:
            return records
        filtered: List[Dict[str, Any]] = []
        for rec in records:
            out: Dict[str, Any] = {}
            for k, v in rec.items():
                if k in policy.denied_fields:
                    continue
                if policy.allowed_fields is not None and k not in policy.allowed_fields:
                    continue
                out[k] = v
            filtered.append(out)
        return filtered


# ---------------------------------------------------------------------------
# SecureMerge — RBAC-enforced merge wrapper
# ---------------------------------------------------------------------------


class SecureMerge:
    """Wraps :func:`crdt_merge.merge` with RBAC policy enforcement.

    Parameters
    ----------
    rbac:
        The :class:`RBACController` that holds all active policies.
    audit_log:
        Optional :class:`~crdt_merge.audit.AuditLog` instance.  When
        provided, every RBAC decision is recorded as an ``rbac_decision``
        entry linked to the corresponding merge entry via ``merge_id``.
    """

    def __init__(self, rbac: RBACController, audit_log: Any = None) -> None:
        self._rbac = rbac
        self._audit_log = audit_log

    def _log_decision(
        self,
        node_id: str,
        role: Role,
        operation: str,
        decision: str,
        merge_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write an RBAC decision to the audit log if one is configured."""
        if self._audit_log is None:
            return
        meta: Dict[str, Any] = {
            "node_id": node_id,
            "role": role.name,
            "operation": operation,
            "decision": decision,
        }
        if merge_id is not None:
            meta["merge_id"] = merge_id
        if extra:
            meta.update(extra)
        self._audit_log.log_operation(
            "rbac_decision",
            input_data={"node_id": node_id, "role": role.name, "operation": operation},
            output_data={"decision": decision},
            **meta,
        )

    def merge(
        self,
        left: Any,
        right: Any,
        key: Any,
        schema: Any = None,
        context: Optional[AccessContext] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Perform a merge with RBAC enforcement.

        If no *context* is provided the merge proceeds without access checks
        (backwards-compatible behaviour).

        Raises
        ------
        PermissionError
            When the calling node lacks required permissions.
        """
        if context is None:
            return _crdt_merge(left, right, key=key, schema=schema, **kwargs)

        node_id = context.node_id
        role = context.role

        # 1. Permission gate
        if not self._rbac.check_permission(context, Permission.MERGE):
            self._log_decision(node_id, role, "merge", "denied",
                               extra={"reason": "lacks MERGE permission"})
            raise PermissionError(
                f"Node '{node_id}' lacks MERGE permission"
            )

        # 2. Record-count gate
        policy = self._rbac.get_policy(node_id)
        if policy is not None and policy.max_record_count is not None:
            total = (len(left) if isinstance(left, list) else 0) + (
                len(right) if isinstance(right, list) else 0
            )
            if total > policy.max_record_count:
                self._log_decision(node_id, role, "merge", "denied",
                                   extra={"reason": "record count exceeded"})
                raise PermissionError(
                    f"Record count {total} exceeds limit "
                    f"{policy.max_record_count} for node '{node_id}'"
                )

        # 3. Field whitelist gate (issue #77)
        if policy is not None and policy.allowed_fields is not None:
            all_records = (
                (left if isinstance(left, list) else [])
                + (right if isinstance(right, list) else [])
            )
            for rec in all_records:
                if not isinstance(rec, dict):
                    continue
                for fname in rec:
                    if fname not in policy.allowed_fields:
                        self._log_decision(
                            node_id, role, "merge", "denied",
                            extra={"reason": "field not permitted", "field": fname},
                        )
                        raise PermissionError(
                            f"Field '{fname}' not permitted for role {role.name}"
                        )

        # 4. Strategy gate
        if schema is not None and policy is not None and policy.allowed_strategies is not None:
            # Check per-field strategies stored in _strategies dict
            field_strats = getattr(schema, "_strategies", None) or {}
            for _fname, strat in field_strats.items():
                sname = type(strat).__name__
                if sname not in policy.allowed_strategies:
                    self._log_decision(node_id, role, "merge", "denied",
                                       extra={"reason": "strategy not allowed",
                                              "strategy": sname})
                    raise PermissionError(
                        f"Strategy '{sname}' not allowed for node '{node_id}'"
                    )
            # Check the default strategy
            default_strat = getattr(schema, "default", None)
            if default_strat is not None:
                dname = type(default_strat).__name__
                if dname not in policy.allowed_strategies:
                    self._log_decision(node_id, role, "merge", "denied",
                                       extra={"reason": "default strategy not allowed",
                                              "strategy": dname})
                    raise PermissionError(
                        f"Default strategy '{dname}' not allowed for node '{node_id}'"
                    )

        # 5. Perform the real merge
        result = _crdt_merge(left, right, key=key, schema=schema, **kwargs)

        # 6. Log the merge to the audit log and capture the merge_id
        merge_id: Optional[str] = None
        if self._audit_log is not None:
            merge_entry = self._audit_log.log_merge(
                left_records=left,
                right_records=right,
                result_records=result,
                schema=schema,
                key=key if isinstance(key, str) else str(key),
            )
            merge_id = merge_entry.entry_id

        # 7. Log RBAC grant decision linked to the merge entry
        self._log_decision(node_id, role, "merge", "granted", merge_id=merge_id)

        # 8. Filter output fields based on READ permissions
        if isinstance(result, list):
            result = self._rbac._filter_fields(context, result)

        return result
