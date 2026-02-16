# Schema Evolution

> Schema drift detection and resolution for evolving datasets.

**Source:** `crdt_merge/schema_evolution.py`  
**Lines of Code:** 419

## Overview

Supports four policies (UNION, INTERSECTION, LEFT_PRIORITY, RIGHT_PRIORITY)
and integrates with Arrow-style type strings.  Pure standalone module — no
imports from crdt_merge.

## Classes

### `SchemaPolicy(Enum)`

Policy for resolving schema drift between two schemas.

**Class Attributes:**

- `UNION` — `'union'`
- `INTERSECTION` — `'intersection'`
- `LEFT_PRIORITY` — `'left_priority'`
- `RIGHT_PRIORITY` — `'right_priority'`

### `SchemaChange`

Describes a single schema change for one column.

**Class Attributes:**

- `column` — `str`
- `change_type` — `str`
- `old_type` — `Optional[str] = None`
- `new_type` — `Optional[str] = None`
- `resolved_type` — `Optional[str] = None`
- `default_value` — `Any = None`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_dict` | `to_dict() -> dict` | Return a plain-dict representation. |
| `from_dict` | `from_dict(d: dict) -> 'SchemaChange'` | Reconstruct from a plain dict. |

### `SchemaEvolutionResult`

Full result of a schema evolution operation.

**Class Attributes:**

- `resolved_schema` — `Dict[str, str]`
- `changes` — `List[SchemaChange]`
- `defaults` — `Dict[str, Any]`
- `policy_used` — `SchemaPolicy`
- `is_compatible` — `bool`
- `warnings` — `List[str] = field(default_factory=list)`

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_dict` | `to_dict() -> dict` | Return a plain-dict representation suitable for JSON. |
| `from_dict` | `from_dict(d: dict) -> 'SchemaEvolutionResult'` | Reconstruct a *SchemaEvolutionResult* from its dict form. |

## Functions

### `widen_type()`

```python
widen_type(type_a: str, type_b: str) -> Optional[str]
```

Return the widened type that covers both *type_a* and *type_b*.

### `check_compatibility()`

```python
check_compatibility(schema_a: Dict[str, str], schema_b: Dict[str, str]) -> Tuple[bool, List[str]]
```

Check whether *schema_a* and *schema_b* can be merged without evolution.

### `_resolve_type_conflict()`

```python
_resolve_type_conflict(column: str, old_type: str, new_type: str, allow_type_narrowing: bool, warnings: List[str]) -> Tuple[str, bool]
```

Resolve a type conflict between *old_type* and *new_type*.

### `evolve_schema()`

```python
evolve_schema(old: Dict[str, str], new: Dict[str, str], policy: SchemaPolicy = SchemaPolicy.UNION, defaults: Optional[Dict[str, Any]] = None, allow_type_narrowing: bool = False) -> SchemaEvolutionResult
```

Detect and resolve schema drift between *old* and *new*.

## Constants / Module Variables

- `TYPE_WIDENING` — `Dict[Tuple[str, str], str] = {('int32', 'int64'): 'int64', ('int64', 'int32'): 'int64', ('float32', 'float64'): 'float64', ('f...`
