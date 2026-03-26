# schema_evolution

> Layer 3 — Sync & Transport
> Source: `crdt_merge/schema_evolution.py`  
> LOC: 326 (AST-verified)

## Overview
Schema drift detection and resolution for evolving datasets.

Supports four policies (UNION, INTERSECTION, LEFT_PRIORITY, RIGHT_PRIORITY)
and integrates with Arrow-style type strings.  Pure standalone module — no
imports from crdt_merge.

## Classes

### `SchemaPolicy(Enum)`

Policy for resolving schema drift between two schemas.

---

### `SchemaChange`
`@dataclass`  


Describes a single schema change for one column.

#### Methods

##### `to_dict(self) -> dict`

Return a plain-dict representation.

##### `@classmethod from_dict(cls, d: dict) -> 'SchemaChange'`
Decorators: `@classmethod`

Reconstruct from a plain dict.

---

### `SchemaEvolutionResult`
`@dataclass`  


Full result of a schema evolution operation.

#### Methods

##### `to_dict(self) -> dict`

Return a plain-dict representation suitable for JSON.

##### `@classmethod from_dict(cls, d: dict) -> 'SchemaEvolutionResult'`
Decorators: `@classmethod`

Reconstruct a *SchemaEvolutionResult* from its dict form.

---

## Functions

### `widen_type(type_a: str, type_b: str) -> Optional[str]`

Return the widened type that covers both *type_a* and *type_b*.

Returns *None* when no safe widening is known (incompatible or opaque
type strings).

| Parameter | Type | Default |
|-----------|------|---------|
| `type_a` | `str` | `—` |
| `type_b` | `str` | `—` |

### `check_compatibility(schema_a: Dict[str, str], schema_b: Dict[str, str]) -> Tuple[bool, List[str]]`

Check whether *schema_a* and *schema_b* can be merged without evolution.

Two schemas are compatible when they share the same set of columns and
every shared column either has identical types or can be safely widened.

Returns ``(is_compatible, reasons)`` where *reasons* lists every
incompatibility found (empty list when compatible).

| Parameter | Type | Default |
|-----------|------|---------|
| `schema_a` | `Dict[str, str]` | `—` |
| `schema_b` | `Dict[str, str]` | `—` |

### `_resolve_type_conflict(column: str, old_type: str, new_type: str, allow_type_narrowing: bool, warnings: List[str]) -> Tuple[str, bool]`

Resolve a type conflict between *old_type* and *new_type*.

Returns ``(resolved_type, is_compatible_change)``.

| Parameter | Type | Default |
|-----------|------|---------|
| `column` | `str` | `—` |
| `old_type` | `str` | `—` |
| `new_type` | `str` | `—` |
| `allow_type_narrowing` | `bool` | `—` |
| `warnings` | `List[str]` | `—` |

### `evolve_schema(old: Dict[str, str], new: Dict[str, str], policy: SchemaPolicy = SchemaPolicy.UNION, defaults: Optional[Dict[str, Any]] = None, allow_type_narrowing: bool = False) -> SchemaEvolutionResult`

Detect and resolve schema drift between *old* and *new*.

Parameters
----------
old:
    The existing (left) schema mapping column names to type strings.
new:
    The incoming (right) schema.
policy:
    How to handle differing column sets. See :class:`SchemaPolicy`.
defaults:
    Default values for columns that appear in only one side.
allow_type_narrowing:
    When *False* (default), type narrowing (e.g. float64 → int32) makes
    the result incompatible and emits a warning.  When *True*, the new
    type is accepted.

Returns
-------
SchemaEvolutionResult

| Parameter | Type | Default |
|-----------|------|---------|
| `old` | `Dict[str, str]` | `—` |
| `new` | `Dict[str, str]` | `—` |
| `policy` | `SchemaPolicy` | `SchemaPolicy.UNION` |
| `defaults` | `Optional[Dict[str, Any]]` | `None` |
| `allow_type_narrowing` | `bool` | `False` |

## Constants

| Name | Type | Value |
|------|------|-------|
| `TYPE_WIDENING` | `Dict[Tuple[str, str], str]` | `{('int32', 'int64'): 'int64', ('int64', 'int32'): 'int64', ('float32', 'float...` |

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 1
- Inherited methods: None
- No circular dependencies
- Pure standalone module — no imports from crdt_merge

### RREA Findings
- Entropy profile: zero (not present in package reachability graph — standalone utility)
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: No chokepoints — standalone schema utility with no upstream dependents

### Code Quality (Team 2)
- Docstring coverage: 100% 
- `__all__` defined: no — **public API is ambiguous** (should export `SchemaPolicy`, `SchemaChange`, `SchemaEvolutionResult`, `evolve_schema`, `check_compatibility`, `widen_type`)
- Code smells: None

---
Approved by: Auditor (Team 1), Cross-validated by Teams 2–4  
Last reviewed: 2026-03-31
