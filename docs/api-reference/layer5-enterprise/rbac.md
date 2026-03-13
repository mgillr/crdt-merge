# crdt_merge.rbac — Role-Based Access Control

> **Module**: `crdt_merge/rbac.py` | **Layer**: 5 — Enterprise | **Version**: 0.9.3

---

## Overview

Provides policy-based access control that governs which nodes can perform merge, encrypt, unmerge, and audit operations on specific fields using specific strategies. The module defines a `Permission` flag enum, `Role` and `Policy` dataclasses, and two main classes: `RBACController` (the central policy store and enforcement engine) and `SecureMerge` (a wrapper around `crdt_merge.merge()` with RBAC enforcement).

---

## Quick Start

```python
from crdt_merge.rbac import (
    RBACController, SecureMerge, Policy, Permission, AccessContext, MERGER
)

# Set up RBAC
rbac = RBACController()
policy = Policy(role=MERGER, denied_fields={"secret"})
rbac.add_policy("node-1", policy)

# Check permissions
ctx = AccessContext(node_id="node-1", role=MERGER)
assert rbac.check_permission(ctx, Permission.MERGE)
assert not rbac.check_field_access(ctx, "secret", Permission.READ)

# Perform a secure merge
secure = SecureMerge(rbac)
left = [{"id": 1, "name": "Alice", "secret": "xxx"}]
right = [{"id": 1, "name": "Alicia", "secret": "yyy"}]
result = secure.merge(left, right, key="id", context=ctx)
# "secret" field is filtered from output
```

---

## Module-Level Constants

### `logger`

`logging.Logger` — Module logger (`logging.getLogger(__name__)`).

---

## Enums

### `Permission` *(Flag)*

Fine-grained permissions for merge operations. As a `Flag` enum, permissions can be combined with bitwise operators.

```python
class Permission(Flag):
    READ = auto()
    WRITE = auto()
    MERGE = auto()
    ADMIN = auto()
    UNMERGE = auto()
    ENCRYPT = auto()
    AUDIT_READ = auto()
```

| Member | Description |
|--------|-------------|
| `READ` | Read access to data fields. |
| `WRITE` | Write access to data fields. |
| `MERGE` | Permission to execute merge operations. |
| `ADMIN` | Full administrative access. |
| `UNMERGE` | Permission to reverse merge operations. |
| `ENCRYPT` | Permission to encrypt/decrypt fields. |
| `AUDIT_READ` | Permission to read audit logs. |

---

## Classes

### `Role`

Named collection of permissions. This is a **frozen dataclass** — instances are immutable and hashable.

```python
@dataclass(frozen=True)
class Role:
    name: str
    permissions: frozenset[Permission] = field(default_factory=frozenset)
```

**Fields:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | *(required)* | Human-readable role name. |
| `permissions` | `frozenset[Permission]` | `frozenset()` | Set of granted permissions. |

**Methods:**

#### `has_permission(perm: Permission) → bool`

Return `True` if this role includes the given permission.

---

### Pre-defined Roles

Four module-level role constants are provided:

| Constant | Name | Permissions |
|----------|------|-------------|
| `READER` | `"reader"` | `READ`, `AUDIT_READ` |
| `WRITER` | `"writer"` | `READ`, `WRITE` |
| `MERGER` | `"merger"` | `READ`, `WRITE`, `MERGE` |
| `ADMIN` | `"admin"` | `READ`, `WRITE`, `MERGE`, `ADMIN`, `UNMERGE`, `ENCRYPT`, `AUDIT_READ` |

**Example:**
```python
from crdt_merge.rbac import ADMIN, Permission

assert ADMIN.has_permission(Permission.UNMERGE)
assert ADMIN.has_permission(Permission.ENCRYPT)
```

---

### `Policy`

Access-control policy bound to a node via `RBACController`.

```python
@dataclass
class Policy:
    role: Role
    allowed_fields: Optional[Set[str]] = None
    allowed_strategies: Optional[Set[str]] = None
    denied_fields: Set[str] = field(default_factory=set)
    max_record_count: Optional[int] = None
```

**Fields:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `role` | `Role` | *(required)* | The role that dictates base permissions. |
| `allowed_fields` | `Optional[Set[str]]` | `None` | Whitelist of field names the node may access. `None` means *all*. |
| `allowed_strategies` | `Optional[Set[str]]` | `None` | Whitelist of strategy class names (e.g. `"LWW"`, `"MaxWins"`). `None` means *all*. |
| `denied_fields` | `Set[str]` | `set()` | Explicit deny list — takes priority over `allowed_fields`. |
| `max_record_count` | `Optional[int]` | `None` | Optional ceiling on the number of input records per merge. |

**Example:**
```python
from crdt_merge.rbac import Policy, MERGER

# Allow merger role, deny access to "secret" field, limit to LWW strategy
policy = Policy(
    role=MERGER,
    denied_fields={"secret", "ssn"},
    allowed_strategies={"LWW"},
    max_record_count=10_000,
)
```

---

### `AccessContext`

Runtime context passed to every RBAC check.

```python
@dataclass
class AccessContext:
    node_id: str
    role: Role
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Fields:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `node_id` | `str` | *(required)* | Identifier of the node making the request. |
| `role` | `Role` | *(required)* | The role under which the node is operating. |
| `metadata` | `Dict[str, Any]` | `{}` | Arbitrary metadata for the access context. |

---

### `RBACController`

Central policy store and enforcement engine. Thread-safe — all mutations are guarded by an internal lock.

```python
class RBACController:
    def __init__(self) -> None
```

Takes no arguments.

**Methods:**

#### `add_policy(node_id: str, policy: Policy) → None`

Register a policy for the given node, replacing any existing one.

**Parameters:**
- `node_id` (`str`): Node identifier.
- `policy` (`Policy`): The policy to assign.

---

#### `remove_policy(node_id: str) → None`

Remove the policy for a node. No-op if the node has no policy.

**Parameters:**
- `node_id` (`str`): Node identifier.

---

#### `get_policy(node_id: str) → Optional[Policy]`

Return the policy for a node, or `None` if none is registered.

**Parameters:**
- `node_id` (`str`): Node identifier.

**Returns:** `Optional[Policy]`

---

#### `check_permission(context: AccessContext, permission: Permission) → bool`

Return `True` if the given context grants the specified permission. Returns `False` if no policy exists for the node.

**Parameters:**
- `context` (`AccessContext`): The access context.
- `permission` (`Permission`): The permission to check.

**Returns:** `bool`

---

#### `check_field_access(context: AccessContext, field_name: str, permission: Permission) → bool`

Return `True` if the node may apply the given permission to the specified field. Checks: permission granted → field not in `denied_fields` → field in `allowed_fields` (if set).

**Parameters:**
- `context` (`AccessContext`): The access context.
- `field_name` (`str`): The field to check.
- `permission` (`Permission`): The permission to verify.

**Returns:** `bool`

---

#### `check_strategy_access(context: AccessContext, strategy: str) → bool`

Return `True` if the node may use the given strategy name.

**Parameters:**
- `context` (`AccessContext`): The access context.
- `strategy` (`str`): Strategy class name (e.g. `"LWW"`).

**Returns:** `bool`

---

#### `enforce_merge(context: AccessContext, records: List[Dict[str, Any]], schema=None) → List[Dict[str, Any]]`

Filter records according to the node's READ policy. Raises `PermissionError` if the node lacks `MERGE` permission or if the record count exceeds `max_record_count`.

**Parameters:**
- `context` (`AccessContext`): The access context.
- `records` (`List[Dict[str, Any]]`): Records to filter.
- `schema` (`Any`, optional): Merge schema (currently unused).

**Returns:** `List[Dict[str, Any]]` — Filtered records with denied fields removed.

**Raises:** `PermissionError`

**Example:**
```python
rbac = RBACController()
rbac.add_policy("node-1", Policy(role=MERGER, denied_fields={"secret"}))

ctx = AccessContext(node_id="node-1", role=MERGER)
records = [{"id": 1, "name": "Alice", "secret": "hidden"}]
filtered = rbac.enforce_merge(ctx, records)
# filtered == [{"id": 1, "name": "Alice"}]
```

---

### `SecureMerge`

Wraps `crdt_merge.merge()` with RBAC policy enforcement.

```python
class SecureMerge:
    def __init__(self, rbac: RBACController) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `rbac` | `RBACController` | *(required)* | The controller that holds all active policies. |

**Methods:**

#### `merge(left, right, key, schema=None, context=None, **kwargs) → List[Dict[str, Any]]`

Perform a merge with RBAC enforcement. If no `context` is provided, the merge proceeds without access checks (backwards-compatible behaviour).

When a context is provided, the following enforcement steps apply:
1. **Permission gate** — node must have `MERGE` permission.
2. **Record-count gate** — total input records must not exceed `max_record_count`.
3. **Strategy gate** — each strategy used in the schema must be in `allowed_strategies`.
4. **Merge execution** — calls `crdt_merge.merge()`.
5. **Field filtering** — output fields are filtered by the node's READ policy.

**Parameters:**
- `left` (`Any`): Left dataset.
- `right` (`Any`): Right dataset.
- `key` (`Any`): Key column(s).
- `schema` (`Any`, optional): Merge schema.
- `context` (`Optional[AccessContext]`): RBAC context. `None` skips enforcement.
- `**kwargs` (`Any`): Forwarded to `crdt_merge.merge()`.

**Returns:** `List[Dict[str, Any]]` — Merged and filtered records.

**Raises:** `PermissionError` — When the node lacks required permissions, exceeds record limits, or uses a disallowed strategy.

**Example:**
```python
from crdt_merge.rbac import (
    RBACController, SecureMerge, Policy, AccessContext, MERGER, READER
)

rbac = RBACController()
rbac.add_policy("edge-1", Policy(role=MERGER, denied_fields={"salary"}))
rbac.add_policy("viewer-1", Policy(role=READER))

secure = SecureMerge(rbac)

left = [{"id": 1, "name": "Alice", "salary": 100000}]
right = [{"id": 1, "name": "Alicia", "salary": 120000}]

# Merger can merge but won't see "salary"
ctx = AccessContext(node_id="edge-1", role=MERGER)
result = secure.merge(left, right, key="id", context=ctx)
# result == [{"id": 1, "name": ...}]  (salary filtered)

# Reader cannot merge
try:
    viewer_ctx = AccessContext(node_id="viewer-1", role=READER)
    secure.merge(left, right, key="id", context=viewer_ctx)
except PermissionError as e:
    print(e)  # "Node 'viewer-1' lacks MERGE permission"
```
