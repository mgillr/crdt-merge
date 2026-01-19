# Schema Evolution

Automatic schema evolution for mismatched datasets.

## Quick Example

```python
from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy
result = evolve_schema(old_schema, new_schema, policy=SchemaPolicy.UNION)
```

---

## API Reference

## `crdt_merge.schema_evolution`

> Schema drift detection and resolution for evolving datasets.

**Module:** `crdt_merge.schema_evolution`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Enum(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)`

Create a collection of name/value pairs.

#### `SchemaChange(column: 'str', change_type: 'str', old_type: 'Optional[str]' = None, new_type: 'Optional[str]' = None, resolved_type: 'Optional[str]' = None, default_value: 'Any' = None) -> None`

Describes a single schema change for one column.

**Methods:**

- `from_dict(d: 'dict') -> "'SchemaChange'"` — Reconstruct from a plain dict.
- `to_dict(self) -> 'dict'` — Return a plain-dict representation.

#### `SchemaEvolutionResult(resolved_schema: 'Dict[str, str]', changes: 'List[SchemaChange]', defaults: 'Dict[str, Any]', policy_used: 'SchemaPolicy', is_compatible: 'bool', warnings: 'List[str]' = <factory>) -> None`

Full result of a schema evolution operation.

**Methods:**

- `from_dict(d: 'dict') -> "'SchemaEvolutionResult'"` — Reconstruct a *SchemaEvolutionResult* from its dict form.
- `to_dict(self) -> 'dict'` — Return a plain-dict representation suitable for JSON.

#### `SchemaPolicy(*values)`

Policy for resolving schema drift between two schemas.

### Functions

#### `check_compatibility(schema_a: 'Dict[str, str]', schema_b: 'Dict[str, str]') -> 'Tuple[bool, List[str]]'`

Check whether *schema_a* and *schema_b* can be merged without evolution.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `evolve_schema(old: 'Dict[str, str]', new: 'Dict[str, str]', policy: 'SchemaPolicy' = <SchemaPolicy.UNION: 'union'>, defaults: 'Optional[Dict[str, Any]]' = None, allow_type_narrowing: 'bool' = False) -> 'SchemaEvolutionResult'`

Detect and resolve schema drift between *old* and *new*.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `widen_type(type_a: 'str', type_b: 'str') -> 'Optional[str]'`

Return the widened type that covers both *type_a* and *type_b*.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
