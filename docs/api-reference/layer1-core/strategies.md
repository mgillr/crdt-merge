# crdt_merge.strategies — Merge Strategies & Schema

**Module**: `crdt_merge/strategies.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 377
**Dependencies**: `crdt_merge.core`

---

## Overview

Provides composable per-field conflict resolution strategies. Every strategy satisfies CRDT properties (commutative, associative, idempotent).

---

## Quick Start

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority, Custom

# Build a schema with different strategies per column
schema = MergeSchema(
    default=LWW(),                                      # fallback for unlisted columns
    score=MaxWins(),                                     # higher score wins
    tags=UnionSet(separator=","),                         # set union of comma-separated values
    status=Priority(["draft", "review", "published"]),   # ranked priority
)

# Resolve a single-field conflict
print(MaxWins().resolve(80, 90))           # → 90
print(UnionSet().resolve("a,b", "b,c"))    # → "a,b,c"

# Merge two entire rows at once
row_a = {"id": 1, "name": "Alice", "score": 80, "tags": "a,b", "status": "draft", "_ts": 1000.0}
row_b = {"id": 1, "name": "Bob",   "score": 90, "tags": "b,c", "status": "published", "_ts": 2000.0}

merged = schema.resolve_row(row_a, row_b, timestamp_col="_ts")
# → {"id": 1, "name": "Bob", "score": 90, "tags": "a,b,c", "status": "published", "_ts": 2000.0}

# Custom strategy with your own function
avg = Custom(lambda a, b: (a + b) / 2)
print(avg.resolve(80, 90))  # → 85.0
```

---

## Abstract Base

### MergeStrategy (Abstract)

```python
class MergeStrategy:
    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any
    def name(self) -> str  # Returns class name
```

---

## Strategy Classes

### LWW
Last-Writer-Wins. Latest timestamp wins; tie-break via `str()` comparison.

```python
class LWW(MergeStrategy):
    def resolve(self, val_a, val_b, ts_a=0.0, ts_b=0.0, node_a="a", node_b="b") -> Any
```
**Logic**: `ts_b > ts_a` → `val_b`; equal timestamps → `str(val_a) >= str(val_b)` → `val_a`

### MaxWins
Higher value wins. `None` always loses.

```python
class MaxWins(MergeStrategy):
    def resolve(self, val_a, val_b, ...) -> Any
```
**Logic**: `max(val_a, val_b)`; if comparison fails, falls back to string comparison.

### MinWins
Lower value wins. Same logic as MaxWins but with `min()`.

```python
class MinWins(MergeStrategy):
    def resolve(self, val_a, val_b, ...) -> Any
```

### UnionSet
Merge comma-separated values as set union, sorted for determinism.

```python
class UnionSet(MergeStrategy):
    def __init__(self, separator: str = ",")
    def resolve(self, val_a, val_b, ...) -> str
```
**Example**: `resolve("a,b", "b,c")` → `"a,b,c"`

### Priority
Ranked priority — higher index wins.

```python
class Priority(MergeStrategy):
    def __init__(self, levels: List[str])
    def resolve(self, val_a, val_b, ...) -> str
```
**Example**: `Priority(["draft", "review", "published"]).resolve("draft", "published")` → `"published"`

### Concat
Concatenate values with optional deduplication.

```python
class Concat(MergeStrategy):
    def __init__(self, separator: str = " | ", dedup: bool = True)
    def resolve(self, val_a, val_b, ...) -> str
```

### LongestWins
Longer string wins. Tie-break delegates to LWW.

```python
class LongestWins(MergeStrategy):
    def resolve(self, val_a, val_b, ...) -> Any
```

### Custom
User-provided merge function.

```python
class Custom(MergeStrategy):
    def __init__(self, fn: Callable)
    def resolve(self, val_a, val_b, ...) -> Any
```
**Signatures supported**: `fn(val_a, val_b)` or `fn(val_a, val_b, ts_a, ts_b, node_a, node_b)`

> **Known Issue (LAY1-003)**: Custom strategies cannot be serialized. `to_dict()` emits UserWarning; `from_dict()` deserializes as LWW.

---

## Helper Functions

### _safe_parse_ts()
```python
def _safe_parse_ts(value: Any) -> float
```
Robustly parse timestamps. Handles: int, float, numeric strings, ISO-8601 strings, objects with `.timestamp()`. Returns `0.0` for unparseable values.

> **Known Issue (LAY1-005)**: Silent fallback to 0.0 — invalid timestamps never raise.

---

## MergeSchema

Declarative per-field strategy mapping.

```python
class MergeSchema:
    def __init__(self, default: Optional[MergeStrategy] = None, **field_strategies: MergeStrategy)
```

**Parameters**:
- `default`: Strategy for unspecified fields. Default: `LWW()`.
- `**field_strategies`: Keyword args mapping field name → strategy.

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `strategy_for()` | `strategy_for(field: str) -> MergeStrategy` | Get strategy for field (or default) |
| `set_strategy()` | `set_strategy(field: str, strategy: MergeStrategy) -> None` | Set/update strategy |
| `resolve_row()` | `resolve_row(row_a: dict, row_b: dict, timestamp_col: Optional[str] = None, node_a: str = "a", node_b: str = "b") -> dict` | Merge two row dicts |
| `to_dict()` | `to_dict() -> dict` | Serialize (Custom strategies emit warning) |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> MergeSchema` | Deserialize |

### Properties
- `default` → `MergeStrategy`
- `fields` → `Dict[str, MergeStrategy]` (copy)

> **Known Issue (LAY1-006)**: `resolve_row()` doesn't handle nested dicts.

**Example**:
```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority

schema = MergeSchema(
    default=LWW(),
    name=LWW(),
    score=MaxWins(),
    tags=UnionSet(),
    status=Priority(["draft", "review", "published"])
)

row_a = {"id": 1, "name": "Alice", "score": 80, "tags": "a,b", "_ts": 1000.0}
row_b = {"id": 1, "name": "Bob", "score": 90, "tags": "b,c", "_ts": 2000.0}

merged = schema.resolve_row(row_a, row_b, timestamp_col="_ts")
# → {"id": 1, "name": "Bob", "score": 90, "tags": "a,b,c", "_ts": 2000.0}
```


---

## Internal/Private API


### `UnionSet._to_set(self, val: Any) -> set`

Converts a value to a set for union operations. Handles comma-separated strings, lists, sets, and single values.

**Parameters:**
- `val` (`Any`): Value to convert. Strings are split by `separator`.

**Returns:** `set`


---

## automatic Methods (Missing from initial docs)

### `MergeSchema.__repr__(self) -> str`

Returns string representation of the schema showing default strategy and field count.

---


## Chokepoint Analysis

### MergeStrategy — #1 Entropy Chokepoint in Layer 1


| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Combined Entropy (H)** | **0.722** | Highest in Layer 1 — maximum information flow convergence |
| **Shannon Entropy** | **0.4446** | Static import-graph entropy |
| **Ping Entropy** | **0.9994** | Near-maximum runtime reachability entropy |
| **Convergence Endpoints** | **9** | 9 public API entry points converge through this abstract class |
| **Node Type** | SPECIALIZED | Abstract base with high fan-in and fan-out |

### Why This Matters

`MergeStrategy` sits at the intersection of the **entire per-field conflict resolution system**:

**Fan-out — 8 subclasses inherit from it:**

| Subclass | Strategy |
|----------|----------|
| `LWW` | Last-Writer-Wins (timestamp) |
| `MaxWins` | Larger value wins |
| `MinWins` | Smaller value wins |
| `UnionSet` | Set union of separated values |
| `Concat` | Concatenation with dedup |
| `Priority` | Ranked priority levels |
| `LongestWins` | Longer string wins |
| `Custom` | User-provided function |

**Fan-in — 9 public endpoints converge through `MergeStrategy.resolve()`:**

1. `MergeSchema.resolve_row()` — dispatches all field resolution through `strategy_for(field).resolve()`
2. `merge()` (dataframe) — uses `MergeSchema` internally
3. `merge_stream()` — streaming merge delegates to strategy resolution
4. `merge_sorted_stream()` — sorted streaming merge
5. `parallel_merge()` — parallel merge delegates per-field resolution
6. `ArrowMerge.merge()` — Arrow engine strategy dispatch
7. `MergeQL.execute()` — SQL-like interface builds and uses `MergeSchema`
8. `MergeSchema.to_dict()` / `from_dict()` — serialization round-trip
9. `_STRATEGY_REGISTRY` — global registry maps string names to strategy classes

### Impact Assessment

Any change to `MergeStrategy`'s interface propagates through:
- All 8 subclasses (must implement `.resolve()` with the same signature)
- All callers of `MergeSchema.strategy_for().resolve()` — which includes every merge code path
- The `_STRATEGY_REGISTRY` and serialization system
- All user-defined `Custom(fn)` strategies that conform to the resolve signature

### Stability Guarantee

`MergeStrategy` is a **frozen abstract interface**. The `resolve()` method signature is guaranteed stable:

```python
def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
            node_a: str = "a", node_b: str = "b") -> Any
```

New optional parameters may be added with defaults, but existing parameters will not be removed or reordered. The `name()` method is also frozen.

---

## Inherited Methods — 132 Inherited Dunder Methods

*Catalogued 2026-04-01 — resolves issue #44.*

### Overview

`MergeStrategy` is a standard Python class (not using `__slots__`). Each of its 8 direct subclasses inherits the full set of Python object dunder methods. With the `MergeSchema` class (which also inherits standard dunders), the strategies module contains **132+ inherited dunder methods** across 14+ classes (8 strategy subclasses + `MergeSchema` + internal/dynamic subclass variants).

### Inherited Dunder Methods per Subclass

Every `MergeStrategy` subclass inherits these standard Python dunders from `object` (via `MergeStrategy`):

| Dunder Method | Behavior | Override needed? |
|--------------|----------|-----------------|
| `__eq__(self, other)` | Identity comparison (`is` semantics) | Only if strategies should compare by configuration |
| `__hash__(self)` | Identity-based hash | Only if `__eq__` is overridden |
| `__repr__(self)` | Default `<ClassName object at 0x...>` | Recommended for debugging |
| `__str__(self)` | Delegates to `__repr__` | Optional — `name()` method preferred for display |
| `__init_subclass__(**kwargs)` | No-op hook | Override to register subclasses in `_STRATEGY_REGISTRY` |
| `__class__` | Returns the type | Never override |
| `__new__(cls)` | Standard allocation | Never override |
| `__delattr__(self, name)` | Standard attribute deletion | Never override |
| `__setattr__(self, name, value)` | Standard attribute setting | Never override |

### Subclass × Dunder Matrix

| Subclass | `__eq__` | `__hash__` | `__repr__` | `__str__` | `__init_subclass__` | Custom state? |
|----------|----------|-----------|-----------|----------|-------------------|--------------|
| `LWW` | inherited | inherited | inherited | inherited | inherited | No |
| `MaxWins` | inherited | inherited | inherited | inherited | inherited | No |
| `MinWins` | inherited | inherited | inherited | inherited | inherited | No |
| `UnionSet` | inherited | inherited | inherited | inherited | inherited | Yes (`separator`) |
| `Concat` | inherited | inherited | inherited | inherited | inherited | Yes (`separator`, `dedup`) |
| `Priority` | inherited | inherited | inherited | inherited | inherited | Yes (`levels`) |
| `LongestWins` | inherited | inherited | inherited | inherited | inherited | No |
| `Custom` | inherited | inherited | inherited | inherited | inherited | Yes (`_fn`) |

> **Note:** Stateful subclasses (`UnionSet`, `Concat`, `Priority`, `Custom`) inherit identity-based `__eq__`/`__hash__`, meaning two instances with identical configuration are **not** considered equal. This is by design — strategies are typically singletons within a `MergeSchema`.

### Subclassing Guide

When creating a custom `MergeStrategy` subclass, these are the methods to consider:

#### Required

```python
class MyStrategy(MergeStrategy):
    def resolve(self, val_a, val_b, ts_a=0.0, ts_b=0.0,
                node_a="a", node_b="b"):
        """MUST satisfy: commutative, associative, idempotent."""
        ...
```

#### Recommended Overrides

```python
    def __repr__(self):
        """Readable representation for debugging and logging."""
        return f"MyStrategy(param={self.param!r})"

    def __eq__(self, other):
        """Enable equality comparison for schema diffing."""
        return isinstance(other, MyStrategy) and self.param == other.param

    def __hash__(self):
        """Required if __eq__ is overridden."""
        return hash((type(self), self.param))
```

#### Optional: Auto-Registration

To make your strategy available via `MergeSchema.from_dict()` deserialization:

```python
from crdt_merge.strategies import _STRATEGY_REGISTRY

_STRATEGY_REGISTRY["MyStrategy"] = MyStrategy
```

Or use `__init_subclass__` for automatic registration:

```python
class AutoRegisterStrategy(MergeStrategy):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _STRATEGY_REGISTRY[cls.__name__] = cls
```

---

### Inherited By

| Subclass | `strategy.name` returns |
|----------|------------------------|
| `Concat` | `"Concat"` |
| `Custom` | `"Custom"` |
| `LWW` | `"LWW"` |
| `LongestWins` | `"LongestWins"` |
| `MaxWins` | `"MaxWins"` |
| `MinWins` | `"MinWins"` |
| `Priority` | `"Priority"` |
| `UnionSet` | `"UnionSet"` |

### Usage

```python
from crdt_merge.strategies import LWW, MaxWins, MergeSchema

schema = MergeSchema(default=LWW(), score=MaxWins())
print(schema.default.name)  # "LWW"
for field, strategy in schema.fields.items():
    print(f"{field}: {strategy.name}")
```

> **Note:** The `.name` property is defined on `MergeStrategy` (base class) and inherited by all subclasses. It is NOT overridden by any subclass. AST analysis only sees it on `MergeStrategy`; runtime introspection confirms availability on all 8 subclasses.
