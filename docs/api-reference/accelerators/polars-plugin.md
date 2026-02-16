# `crdt_merge/accelerators/polars_plugin.py`

> Polars Expression Plugin — native Polars DataFrame CRDT merge.

Provides :class:`PolarsCRDTMerge` for merging two Polars DataFrames with
per-field CRDT strategies (LWW, MaxWins, MinWins, etc.) and optional
Arrow-native zero-copy interop.

External dependency: ``polars`` — **lazy-imported**.  The mod

**Source:** `crdt_merge/accelerators/polars_plugin.py` | **Lines:** 517

---

**Exports (`__all__`):** `['PolarsCRDTMerge', 'PolarsMergeResult', 'CRDTMergeExpression', 'crdt_merge_expr']`

## Constants

- `_POLARS_INSTALL_MSG` = `'Polars is required for this accelerator. Install it with: pip install polars'`

## Classes

### `class CRDTMergeExpression`

Wrapper representing a CRDT merge expression for a single field.

    Used with ``PolarsCRDTMerge.as_expression()`` to build composable merge
    expressions for use in ``df.with_columns(...)``.

    This is a *description* of the merge operation; it does not execute
    until applied to actual data via :meth:`apply`.


**Methods:**

#### `CRDTMergeExpression.__init__(self, field: str, strategy: MergeStrategy) → None`

*No docstring*

#### `CRDTMergeExpression.field(self) → str`

The field name this expression targets.

#### `CRDTMergeExpression.strategy_name(self) → str`

Name of the merge strategy.

#### `CRDTMergeExpression.apply(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0, node_a: str = 'a', node_b: str = 'b') → Any`

Resolve a single conflict using the embedded strategy.

#### `CRDTMergeExpression.__repr__(self) → str`

*No docstring*


### `class PolarsMergeResult`

Result of a Polars CRDT merge operation.

    Attributes:
        data: Merged Polars DataFrame.
        conflicts: Number of field-level conflicts resolved.
        merge_time_ms: Execution time in milliseconds.
        rows_merged: Number of rows where both sources had matching keys.
        rows_left_only: Number of rows unique to left DataFrame.
        rows_right_only: Number of rows unique to right DataFrame.


**Methods:**

#### `PolarsMergeResult.__init__(self, data: Any, conflicts: int = 0, merge_time_ms: float = 0.0, rows_merged: int = 0, rows_left_only: int = 0, rows_right_only: int = 0) → None`

*No docstring*

#### `PolarsMergeResult.to_dict(self) → Dict[str, Any]`

Summary stats as dict.

#### `PolarsMergeResult.__repr__(self) → str`

*No docstring*


### `class PolarsCRDTMerge`

Polars expression plugin for CRDT merge operations.

    Provides native Polars DataFrame merge with CRDT strategies.  Converts
    DataFrames to list-of-dicts internally, applies per-field strategies, and
    returns a new Polars DataFrame.

    When Polars is not installed, :meth:`is_available` returns ``False`` and
    merge operations raise ``ImportError``.

    Args:
        schema: Optional MergeSchema for per-field strategies.
        timestamp_col: Column name for LWW timestamps (optional).

    Example::

        merger = PolarsCRDTMerge(schema=MergeSchema(default=LWW(), salary=MaxWins()))
        result = merger.merge(df_left, df_right, key="id")
        print(result.data)   # merged Polars DataFrame

- `name`: `str`
- `version`: `str`

**Methods:**

#### `PolarsCRDTMerge.__init__(self, schema: Optional[MergeSchema] = None, timestamp_col: Optional[str] = None) → None`

*No docstring*

#### `PolarsCRDTMerge.merge(self, left: Any, right: Any, key: str = 'id', strategies: Optional[Dict[str, str]] = None, timestamp_col: Optional[str] = None) → PolarsMergeResult`

Merge two Polars DataFrames with CRDT strategies.

        Args:
            left: Left Polars DataFrame (or list of dicts).
            right: Right Polars DataFrame (or list of dicts).
            key: Column to match rows on.
            strategies: Optional per-field strategy overrides (name → strategy name).
            timestamp_col: Column with timestamps for LWW resolution.

        Returns:
            PolarsMergeResult with merged DataFrame and statistics.

#### `PolarsCRDTMerge.merge_lazy(self, left: Any, right: Any, key: str = 'id', strategies: Optional[Dict[str, str]] = None, timestamp_col: Optional[str] = None) → PolarsMergeResult`

Lazy merge — collects LazyFrames before merging.

        For very large datasets, converts LazyFrames to DataFrames in a
        streaming-compatible way then delegates to :meth:`merge`.

        Args:
            left: Left Polars LazyFrame or DataFrame.
            right: Right Polars LazyFrame or DataFrame.
            key: Column to match rows on.
            strategies: Optional per-field strategy overrides.
            timestamp_col: Column with timestamps for LWW resolution.

        Returns:
            PolarsMergeResult with merged DataFrame.

#### `PolarsCRDTMerge.as_expression(self, field: str, strategy: str = 'lww') → CRDTMergeExpression`

Return a CRDTMergeExpression for use in composable merge pipelines.

        Args:
            field: The field name to apply the strategy to.
            strategy: Strategy name (e.g. "lww", "max", "min", "union", "concat").

        Returns:
            CRDTMergeExpression that can be applied to values.

#### `PolarsCRDTMerge.register_namespace(self) → None`

Register ``crdt`` namespace on Polars DataFrames.

        After calling this, you can use ``df.crdt.merge(...)`` syntax.
        Requires Polars ≥ 0.19 with namespace extension support.

#### `PolarsCRDTMerge.health_check(self) → Dict[str, Any]`

Return health / readiness status.

        Returns:
            Dict with status, polars availability, and version info.

#### `PolarsCRDTMerge.is_available(self) → bool`

Check whether Polars is available.

#### `PolarsCRDTMerge._resolve_schema(self, overrides: Optional[Dict[str, str]] = None) → MergeSchema`

Build effective schema from base + overrides.

#### `PolarsCRDTMerge._merge_row(self, row_a: dict, row_b: dict, schema: MergeSchema, timestamp_col: Optional[str]) → Tuple[dict, int]`

Merge two rows using per-field strategies. Returns (merged, conflict_count).

#### `PolarsCRDTMerge.__repr__(self) → str`

*No docstring*


## Functions

### `_safe_parse_ts(value)`

Parse timestamp to float — handles numeric, ISO-8601, None.

### `_require_polars() → Any`

Return the ``polars`` module or raise ImportError.

### `_to_dicts(df: Any) → List[dict]`

Convert a Polars DataFrame to list of dicts.

### `_from_dicts(records: List[dict], pl: Any) → Any`

Create a Polars DataFrame from list of dicts.

### `crdt_merge_expr(field: str, strategy: str = 'lww') → CRDTMergeExpression`

Create a standalone CRDT merge expression.

    Convenience function for quick one-off expressions::

        expr = crdt_merge_expr("salary", "max")
        resolved = expr.apply(100, 200)  # → 200

