# Schema Evolution Guide

## Introduction

In distributed systems, different nodes often evolve their data schemas
independently. One node adds an `email` column while another renames `score`
from `int32` to `float64`. When these nodes merge their CRDT state, the
system must reconcile two schemas that have drifted apart — without losing
data and, ideally, without human intervention.

The `crdt_merge.schema_evolution` module solves this problem. It detects
drift between two schemas, classifies every column change, widens types when
safe, and returns a unified resolved schema that both sides can adopt.

### Key concepts

| Term | Meaning |
|---|---|
| **Schema** | A `dict[str, str]` mapping column names to type strings (e.g. `{"id": "int64", "name": "str"}`). |
| **Type widening** | Promoting a narrower type to a wider one without data loss (e.g. `int32` → `float64`). |
| **Policy** | The strategy used to decide which columns survive a merge. |
| **Compatibility** | Two schemas are *compatible* when every shared column can be safely widened (or is already identical). |

---

## Schema Policies

`SchemaPolicy` is an enum with **four** policies that control how differing
column sets are resolved.

```python
from crdt_merge.schema_evolution import SchemaPolicy
```

### UNION

Keep **all** columns from both schemas. Columns that exist on only one side
are retained in the resolved schema and receive a default value for records
from the other side.

```python
old = {"id": "int64", "name": "str"}
new = {"id": "int64", "email": "str"}

result = evolve_schema(old, new, policy=SchemaPolicy.UNION)
print(result.resolved_schema)
# {"email": "str", "id": "int64", "name": "str"}
```

This is the **default** policy and the safest choice — no columns are
discarded.

### INTERSECTION

Keep **only** columns that appear in **both** schemas. Columns unique to
either side are dropped from the resolved schema.

```python
result = evolve_schema(old, new, policy=SchemaPolicy.INTERSECTION)
print(result.resolved_schema)
# {"id": "int64"}  — only the common column survives
```

Use this when you want a minimal, guaranteed-present column set.

### LEFT_PRIORITY

The **old** (left) schema is authoritative. All columns from both sides are
included, but type conflicts on shared columns are resolved in favour of the
old type.

```python
old = {"id": "int64", "score": "int32"}
new = {"id": "int64", "score": "float64", "email": "str"}

result = evolve_schema(old, new, policy=SchemaPolicy.LEFT_PRIORITY)
print(result.resolved_schema)
# {"email": "str", "id": "int64", "score": "int32"}
```

### RIGHT_PRIORITY

The **new** (right) schema is authoritative. Same as LEFT_PRIORITY but type
conflicts are resolved in favour of the new type.

```python
result = evolve_schema(old, new, policy=SchemaPolicy.RIGHT_PRIORITY)
print(result.resolved_schema)
# {"email": "str", "id": "int64", "score": "float64"}
```

---

## Type Compatibility and Widening

Before diving into the main `evolve_schema()` function, it helps to
understand how the module decides whether a type change is safe.

### The `TYPE_WIDENING` Map

`TYPE_WIDENING` is a dictionary of `(type_a, type_b) → widened_type` entries
defining every safe promotion path. The built-in map covers:

| From | To | Widened |
|---|---|---|
| `int32` | `int64` | `int64` |
| `int32` | `float32` | `float32` |
| `int32` | `float64` | `float64` |
| `int64` | `float64` | `float64` |
| `float32` | `float64` | `float64` |
| `int` | `float` | `float` |

All entries are symmetric — `(int32, float64)` and `(float64, int32)` both
resolve to `float64`.

### `widen_type(type_a, type_b)`

Returns the widened type that covers both inputs, or `None` when no safe
widening is known.

```python
from crdt_merge.schema_evolution import widen_type

widen_type("int32", "float64")  # "float64" — safe promotion
widen_type("int", "float")      # "float"
widen_type("str", "str")        # "str"   — identity, same type
widen_type("str", "int64")      # None    — incompatible
widen_type("float64", "int32")  # "float64" — symmetric
```

**Incompatible narrowing** (e.g. `float64` → `int32`) has no entry in the
map, so `widen_type` returns `None`. The library never silently narrows a
type.

### `check_compatibility(schema_a, schema_b)`

A quick pre-flight check that compares two **full schemas** (not individual
types). Returns a tuple `(is_compatible, reasons)`.

```python
from crdt_merge.schema_evolution import check_compatibility

v1 = {"id": "int64", "name": "str", "score": "int32"}
v2 = {"id": "int64", "name": "str", "score": "float64"}

ok, reasons = check_compatibility(v1, v2)
print(ok)       # True — int32→float64 is a safe widening
print(reasons)  # []

# Incompatible example
v3 = {"id": "int64", "name": "str", "score": "int32", "data": "bytes"}
v4 = {"id": "int64", "data": "json"}

ok, reasons = check_compatibility(v3, v4)
print(ok)
# False
for r in reasons:
    print(r)
# "Columns only in schema_a: ['name', 'score']"
# "Column 'data': incompatible types 'bytes' vs 'json'"
```

Compatibility means:

1. Both schemas have the **same set of columns**, AND
2. Every shared column either has an identical type or a known widening path.

If either condition fails, `is_compatible` is `False` and `reasons` lists
every problem found.

---

## `evolve_schema()` Walkthrough

`evolve_schema` is the core function. It detects drift, resolves it
according to a policy, and returns a full `SchemaEvolutionResult`.

### Signature

```python
def evolve_schema(
    old: dict[str, str],
    new: dict[str, str],
    policy: SchemaPolicy = SchemaPolicy.UNION,
    defaults: dict[str, Any] | None = None,
    allow_type_narrowing: bool = False,
) -> SchemaEvolutionResult:
```

| Parameter | Description |
|---|---|
| `old` | The existing (left-side) schema. |
| `new` | The incoming (right-side) schema. |
| `policy` | How to resolve differing column sets (default: `UNION`). |
| `defaults` | Default values for columns that only appear on one side. |
| `allow_type_narrowing` | Accept narrowing changes (e.g. `float64` → `int32`) instead of flagging them incompatible. Default `False`. |

### Basic example — UNION with type widening

```python
from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

v1 = {"id": "int64", "name": "str", "score": "int32"}
v2 = {"id": "int64", "name": "str", "score": "float64", "email": "str"}

result = evolve_schema(v1, v2, policy=SchemaPolicy.UNION)

print(result.resolved_schema)
# {"email": "str", "id": "int64", "name": "str", "score": "float64"}

print(result.is_compatible)
# True — int32→float64 is a safe widening

print(result.policy_used)
# SchemaPolicy.UNION

for ch in result.changes:
    print(f"  {ch.column}: {ch.change_type}"
          f"  {ch.old_type} → {ch.new_type}"
          f"  (resolved: {ch.resolved_type})")
# email: added  None → str  (resolved: str)
# id: unchanged  int64 → int64  (resolved: int64)
# name: unchanged  str → str  (resolved: str)
# score: type_changed  int32 → float64  (resolved: float64)
```

### Supplying defaults for missing columns

When UNION keeps a column that only one side has, records from the other side
need a default value. Pass `defaults` to specify them:

```python
result = evolve_schema(
    old={"id": "int64", "name": "str"},
    new={"id": "int64", "email": "str"},
    policy=SchemaPolicy.UNION,
    defaults={"name": "unknown", "email": ""},
)

print(result.defaults)
# {"email": "", "name": "unknown"}
```

The `defaults` dict on the result only contains columns that are missing
from one side.

### Allowing type narrowing

By default, narrowing (e.g. `float64` → `int32` where data loss is possible)
is flagged as incompatible. If you know what you are doing, opt in:

```python
result = evolve_schema(
    old={"score": "float64"},
    new={"score": "int32"},
    allow_type_narrowing=True,
)

print(result.is_compatible)   # True — narrowing was explicitly allowed
print(result.warnings)
# ["Column 'score': type narrowing 'float64' -> 'int32' (allowed by flag)"]
```

Without `allow_type_narrowing`, the result would have `is_compatible=False`
and the old type would be kept.

---

## The Result Object — `SchemaEvolutionResult`

| Field | Type | Description |
|---|---|---|
| `resolved_schema` | `dict[str, str]` | Final column→type mapping after resolution. |
| `changes` | `list[SchemaChange]` | One entry per column describing what happened. |
| `defaults` | `dict[str, Any]` | Default values for columns missing from one side. |
| `policy_used` | `SchemaPolicy` | The policy that was applied. |
| `is_compatible` | `bool` | `True` when no lossy/incompatible changes were detected. |
| `warnings` | `list[str]` | Human-readable warnings (e.g. about narrowing or incompatible types). |

Both `SchemaEvolutionResult` and `SchemaChange` have `.to_dict()` /
`.from_dict()` methods for JSON serialisation, making them easy to persist or
transmit over the wire.

### `SchemaChange` fields

| Field | Type | Description |
|---|---|---|
| `column` | `str` | Column name. |
| `change_type` | `str` | One of `"added"`, `"removed"`, `"type_changed"`, `"unchanged"`. |
| `old_type` | `str \| None` | Type in the old schema (`None` for added columns). |
| `new_type` | `str \| None` | Type in the new schema (`None` for removed columns). |
| `resolved_type` | `str \| None` | Final type after resolution (`None` if column was dropped). |
| `default_value` | `Any` | Default value assigned (if any). |

---

## Edge Cases

### Handling `None` schemas

Both `evolve_schema` and `check_compatibility` gracefully accept `None` as
either schema, treating it as an empty dict:

```python
result = evolve_schema(None, {"id": "int64"})
print(result.resolved_schema)  # {"id": "int64"}
```

### Removed fields under INTERSECTION

With `INTERSECTION`, columns unique to either side are **not** included in
`resolved_schema`. The corresponding `SchemaChange` will have
`resolved_type=None`:

```python
result = evolve_schema(
    {"id": "int64", "legacy_flag": "int32"},
    {"id": "int64", "email": "str"},
    policy=SchemaPolicy.INTERSECTION,
)
print(result.resolved_schema)  # {"id": "int64"}
# "legacy_flag" and "email" changes have resolved_type=None
```

### Incompatible types with no widening path

When two shared columns have types that cannot be widened (e.g. `"bytes"` vs
`"json"`), the behaviour depends on the policy:

- **LEFT_PRIORITY / RIGHT_PRIORITY** — the prioritised side's type wins.
- **UNION / INTERSECTION** — the old type is kept, `is_compatible` is set to
  `False`, and a warning is emitted.

```python
result = evolve_schema(
    {"data": "bytes"},
    {"data": "json"},
    policy=SchemaPolicy.UNION,
)
print(result.is_compatible)  # False
print(result.warnings)
# ["Column 'data': incompatible types 'bytes' vs 'json', keeping old type 'bytes'"]
```

### Concurrent schema changes from multiple nodes

When three or more nodes evolve schemas independently, resolve pairwise:

```python
# Node A, B, C each have their own schema
merged_ab = evolve_schema(schema_a, schema_b, policy=SchemaPolicy.UNION)
final = evolve_schema(merged_ab.resolved_schema, schema_c, policy=SchemaPolicy.UNION)
```

Because UNION is associative for column sets and type widening is
commutative, the order does not affect the final resolved schema for
compatible changes.

---

## Cross-Version Merging

A common real-world pattern: your application ships v2 of its schema while
some nodes still hold v1 data. Use `evolve_schema` to bridge the gap before
merging CRDT payloads.

```python
from crdt_merge.schema_evolution import evolve_schema, check_compatibility, SchemaPolicy

v1_schema = {"id": "int64", "name": "str", "score": "int32"}
v2_schema = {"id": "int64", "name": "str", "score": "float64", "email": "str"}

# Step 1 — check up-front
ok, reasons = check_compatibility(v1_schema, v2_schema)
if not ok:
    print("Schemas diverged:", reasons)

# Step 2 — evolve
evo = evolve_schema(
    v1_schema, v2_schema,
    policy=SchemaPolicy.UNION,
    defaults={"email": ""},
)

# Step 3 — use the resolved schema for your merge
unified_schema = evo.resolved_schema
# Pass unified_schema to your CRDT merge layer so both sides
# produce records with the same column set and types.
```

---

## Testing Schema Migrations

### 1. Pre-deploy compatibility checks

Run `check_compatibility` in CI to catch breaking changes early:

```python
def test_schema_backward_compatible():
    ok, reasons = check_compatibility(CURRENT_SCHEMA, NEW_SCHEMA)
    assert ok, f"Schema migration is breaking: {reasons}"
```

### 2. Version your schemas

Include a version number alongside the column map so nodes can detect drift
quickly:

```python
SCHEMA_REGISTRY = {
    1: {"id": "int64", "name": "str"},
    2: {"id": "int64", "name": "str", "email": "str"},
    3: {"id": "int64", "name": "str", "email": "str", "score": "float64"},
}
```

### 3. Test cross-version merges explicitly

```python
import itertools

def test_all_version_pairs():
    for va, vb in itertools.combinations(SCHEMA_REGISTRY, 2):
        result = evolve_schema(
            SCHEMA_REGISTRY[va],
            SCHEMA_REGISTRY[vb],
            policy=SchemaPolicy.UNION,
        )
        assert result.is_compatible, (
            f"v{va}→v{vb} incompatible: {result.warnings}"
        )
```

### 4. Serialise evolution results for audit trails

```python
import json

result = evolve_schema(old_schema, new_schema)
with open("migration_audit.json", "w") as f:
    json.dump(result.to_dict(), f, indent=2)
```

---

## Cross-References

- **API Reference** — full function signatures, parameter docs, and return
  types: [`api-reference/layer3-transport/schema-evolution.md`](../api-reference/layer3-transport/schema-evolution.md)
- **Merge Strategies** — how the resolved schema feeds into the merge layer:
  [`guides/merge-strategies.md`](merge-strategies.md)
