# crdt_merge.mergeql — MergeQL DSL

**Module**: `crdt_merge/mergeql.py`
**Layer**: 4 — AI / Model / Agent
**LOC**: 743
**Dependencies**: `crdt_merge.core`, `crdt_merge.strategies`, `crdt_merge.dataframe`

---

## Overview

SQL-like Domain Specific Language for declarative merge operations.

---

## Classes

### MergeQL

```python
class MergeQL:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `register()` | `register(name: str, data: DataFrame) -> None` | Register a data source |
| `execute()` | `execute(query: str) -> DataFrame` | Execute a MergeQL query |
| `explain()` | `explain(query: str) -> str` | Explain query execution plan |

### MergeQL Syntax

```sql
MERGE source_a, source_b
ON key_column
USING LWW FOR name, MaxWins FOR score, UnionSet FOR tags
```


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class MergeQLError(Exception)`

Base exception for MergeQL errors.


### `class MergeQLSyntaxError(MergeQLError)`

Raised when MergeQL query has syntax errors.


### `class MergeQLValidationError(MergeQLError)`

Raised when MergeQL query references invalid sources or strategies.


### `class MergeAST`

Abstract syntax tree for a MergeQL statement.

**Attributes:**
- `sources`: `List[str]`
- `on_key`: `str`
- `strategies`: `Dict[str, str]`
- `where_clause`: `Optional[str]`
- `explain`: `bool`
- `schema_mapping`: `Optional[Dict[str, str]]`
- `limit`: `Optional[int]`


### `class MergePlan`

Execution plan for a MergeQL query.

**Attributes:**
- `sources`: `List[str]`
- `source_sizes`: `Dict[str, int]`
- `merge_key`: `str`
- `strategies`: `Dict[str, str]`
- `estimated_output_rows`: `int`
- `schema_evolution_needed`: `bool`
- `arrow_backend`: `bool`
- `steps`: `List[str]`


### `class MergeQLResult`

Result of a MergeQL execution.

**Attributes:**
- `data`: `List[dict]`
- `plan`: `MergePlan`
- `conflicts`: `int`
- `provenance`: `Optional[List[dict]]`
- `merge_time_ms`: `float`
- `sources_merged`: `int`


### `class MergeQLParser`

Parse MergeQL SQL-like syntax into AST nodes.

    Supported syntax:
        MERGE source1, source2 [, sourceN...]
        ON key_column
        [STRATEGY field1='strategy1', field2='strategy2']
        [WHERE condition]
        [LIMIT n]
        [MAP old_col -> new_col]

        EXPLAIN MERGE ...  (returns MergePlan without executing)
    

**Attributes:**
- `KEYWORDS`


### `MergeQLParser.parse(self, query: str) → MergeAST`

Parse a MergeQL query string into an AST.

        Args:
            query: SQL-like merge statement

        Returns:
            MergeAST node

        Raises:
            MergeQLSyntaxError: If query is malformed
            MergeQLValidationError: If query references unknown sources
        

**Parameters:**
- `query` (`str`)

**Returns:** `MergeAST`

**Raises:** `MergeQLSyntaxError('Empty query')`


### `MergeQL.unregister(self, name: str) → None`

Remove a registered data source.

**Parameters:**
- `name` (`str`)

**Returns:** `None`


### `MergeQL.list_sources(self) → List[str]`

List all registered source names.

**Returns:** `List[str]`


### `MergeQL.source_info(self, name: str) → Dict[str, Any]`

Get info about a registered source (row count, columns, etc).

**Parameters:**
- `name` (`str`)

**Returns:** `Dict[str, Any]`

**Raises:** `MergeQLValidationError(f"Source '{name}' not registered")`


### `MergeQL.register_strategy(self, name: str, func: Callable) → None`

Register a custom merge strategy for use in STRATEGY clauses.

        Args:
            name: Strategy name (used as STRATEGY field='custom:name')
            func: Strategy function with signature (val_a, val_b, ...) -> resolved
        

**Parameters:**
- `name` (`str`)
- `func` (`Callable`)

**Returns:** `None`

**Raises:** `ValueError('Strategy name must be non-empty')`


## Critical Chokepoints

### `MergeQLError` — Ping H = 0.997

`MergeQLError` is the **sole error hierarchy** for the entire MergeQL query engine. Every failure path in query parsing, validation, and execution surfaces through this base class or one of its two subclasses.

#### Error Hierarchy

| Exception | Raised By | Trigger |
|-----------|-----------|---------|
| `MergeQLSyntaxError` | `MergeQLParser.parse()` | Malformed query (missing `MERGE`/`ON`, bad `LIMIT`, invalid tokens) |
| `MergeQLValidationError` | `MergeQL._validate_ast()` | Unregistered source name, unknown strategy name, unregistered custom strategy |
| `MergeQLError` (base) | — | Catch-all for any MergeQL operation failure |

#### Error Propagation Through the Query Pipeline

The MergeQL execution pipeline has three stages, each with distinct failure modes:

1. **Parsing** (`MergeQLParser.parse()`)  
   Tokenizes the SQL-like query string and builds a `MergeAST`. Raises `MergeQLSyntaxError` for:
   - Empty or `None` queries
   - Missing `MERGE` or `ON` keywords
   - Malformed `STRATEGY field=value` clauses (missing `=` or value)
   - Invalid `LIMIT` (non-integer)
   - Malformed `MAP old -> new` clauses (missing `->`)
   - Unexpected tokens outside of known clause keywords

2. **Planning / Validation** (`MergeQL._validate_ast()`, `MergeQL._build_plan()`)  
   Validates AST against registered sources and strategies. Raises `MergeQLValidationError` for:
   - References to unregistered data sources
   - Unknown built-in strategy names (not in `_BUILTIN_STRATEGIES`)
   - References to unregistered custom strategies (`custom:name` prefix)

3. **Execution** (`MergeQL._execute_merge()`)  
   Performs the actual merge: key-based join, per-field strategy resolution, WHERE filtering, column mapping, and LIMIT. Errors at this stage propagate from the underlying `MergeSchema.resolve_row()` calls or data conversion (`_to_records`), and surface as `ValueError` or `MergeQLError` subclasses.

#### `EXPLAIN` Short-Circuit

`EXPLAIN MERGE ...` queries skip stage 3 entirely — they parse, validate, build the plan, and return the `MergePlan` without executing the merge. This makes `EXPLAIN` useful for validating queries without side effects.

#### Implications

Because `MergeQLError` is the single error base class, any consumer that catches `MergeQLError` will capture all query-layer failures. Downstream systems should distinguish between `MergeQLSyntaxError` (user input errors) and `MergeQLValidationError` (configuration/registration errors) for proper error handling.

---

## Analysis Notes
