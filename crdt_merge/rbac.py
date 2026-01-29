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
        return any(perm in p for p in self.permissions)


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
# RBACController
# ---------------------------------------------------------------------------


class RBACController:
    """Central policy store and enforcement engine.

    Thread-safe — all mutations are guarded by an internal lock.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, Policy] = {}
        self._lock = threading.Lock()

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

    def check_permission(self, context: AccessContext, permission: Permission) -> bool:
        """Return *True* if *context* grants *permission*."""
        policy = self.get_policy(context.node_id)
        if policy is None:
            return False
        return context.role.has_permission(permission)

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
    """

    def __init__(self, rbac: RBACController) -> None:
        self._rbac = rbac

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

        # 1. Permission gate
        if not self._rbac.check_permission(context, Permission.MERGE):
            raise PermissionError(
                f"Node '{context.node_id}' lacks MERGE permission"
            )

        # 2. Record-count gate
        policy = self._rbac.get_policy(context.node_id)
        if policy is not None and policy.max_record_count is not None:
            total = (len(left) if isinstance(left, list) else 0) + (
                len(right) if isinstance(right, list) else 0
            )
            if total > policy.max_record_count:
                raise PermissionError(
                    f"Record count {total} exceeds limit "
                    f"{policy.max_record_count} for node '{context.node_id}'"
                )

        # 3. Strategy gate
        if schema is not None and policy is not None and policy.allowed_strategies is not None:
            # Check per-field strategies stored in _strategies dict
            field_strats = getattr(schema, "_strategies", None) or {}
            for _fname, strat in field_strats.items():
                sname = type(strat).__name__
                if sname not in policy.allowed_strategies:
                    raise PermissionError(
                        f"Strategy '{sname}' not allowed for node '{context.node_id}'"
                    )
            # Check the default strategy
            default_strat = getattr(schema, "default", None)
            if default_strat is not None:
                dname = type(default_strat).__name__
                if dname not in policy.allowed_strategies:
                    raise PermissionError(
                        f"Default strategy '{dname}' not allowed for node '{context.node_id}'"
                    )

        # 4. Perform the real merge
        result = _crdt_merge(left, right, key=key, schema=schema, **kwargs)

        # 5. Filter output fields based on READ permissions
        if isinstance(result, list):
            result = self._rbac._filter_fields(context, result)

        return result
