# `crdt_merge/_polars_engine.py`

> **Internal Module** — This module is prefixed with `_`, indicating it is a **private implementation detail**. Do not import directly. The public API is exposed through `crdt_merge.dataframe` (Polars backend).

> Shared Polars merge kernel — zero-copy, Rust-compiled strategy resolution.

This module provides the fast path for crdt-merge: the full outer join AND
strategy resolution both happen inside Polars' Rust engine.  Five of eight
built-in strategies compile to pure Polars expressions (MaxWins, MinWins,


**Source:** `crdt_merge/_polars_engine.py` | **Lines:** 306 *(corrected 2026-03-31 — was 433; AST-verified actual: 306)*

---

**Exports (`__all__`):** `['HAS_POLARS', 'polars_merge_arrow', 'polars_merge_dicts', 'strategy_to_expr']`

## Functions

### `_is_strategy(strategy: Any, name: str) → bool`

Check strategy type by class name to avoid circular imports.

### `strategy_to_expr(col: str, strategy: Any, timestamp_col: Optional[str] = None, suffix: str = '_right', left_dtype: Optional['pl.DataType'] = None) → 'pl.Expr'`

Compile a MergeStrategy into a Polars expression.

    For vectorizable strategies (LWW, MaxWins, MinWins, Concat, LongestWins)
    the expression runs entirely in Rust.  For others (Custom, Priority,
    UnionSet) we fall back to ``map_elements`` which still benefits from the
    Rust join.

    Parameters
    ----------
    col : str
        Column name (left-side).
    strategy : MergeStrategy
        The strategy instance to compile.
    timestamp_col : str, optional
        Timestamp column for LWW resolution.
    suffix : str
        Suffix appended to right-side columns by the join (default "_right").

    Returns
    -------
    pl.Expr
        A Polars expression that resolves conflicts for *col*.

### `polars_merge_arrow(left: 'pa.Table', right: 'pa.Table', key: str, schema: Any, timestamp_col: Optional[str] = None) → Tuple['pa.Table', int]`

Merge two Arrow tables using the Polars engine.

    Parameters
    ----------
    left, right : pa.Table
        Input Arrow tables.
    key : str
        Join key column.
    schema : MergeSchema
        Per-field strategy configuration.
    timestamp_col : str, optional
        Column name for LWW timestamps.

    Returns
    -------
    tuple[pa.Table, int]
        (merged_table, conflict_count)

    Raises
    ------
    ImportError
        If polars is not installed.

### `polars_merge_dicts(left_rows: List[dict], right_rows: List[dict], key: str, schema: Any, timestamp_col: Optional[str] = None) → Tuple[List[dict], int]`

Merge two lists of dicts using the Polars engine.

    This is the entry point for accelerators that work with Python dicts.
    Converts to Polars, merges in Rust, converts back to dicts.

    Parameters
    ----------
    left_rows, right_rows : list[dict]
        Input rows as Python dictionaries.
    key : str
        Join key column.
    schema : MergeSchema
        Per-field strategy configuration.
    timestamp_col : str, optional
        Column name for LWW timestamps.

    Returns
    -------
    tuple[list[dict], int]
        (merged_rows, conflict_count)

### `_get_field_strategy(schema: Any, field: str) → Any`

Extract per-field strategy from a MergeSchema.

    Uses the official ``strategy_for()`` API which returns the per-field
    strategy if set, otherwise falls back to the schema default.

---

## Internal Chokepoints

### `_get_field_strategy` — Ping-Entropy-Dominant Chokepoint

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Combined Entropy (H)** | **0.5597** | Highest in `_polars_engine.py` |
| **Ping Entropy (H_ping)** | **0.9971** | Near-maximum — virtually ALL execution paths converge here |
| **Shannon Entropy** | 0.1223 | Low static entropy (single call site per merge kernel) |

**H_ping = 0.9971** means that at runtime, nearly every execution path through the Polars merge engine flows through `_get_field_strategy`. This makes it the single most traversed function in the module.

#### Role

`_get_field_strategy` is the **strategy dispatcher** for the Polars merge engine. It maps a field name to its `MergeStrategy` instance by:

1. Checking if `schema` has a `strategy_for(field)` method (the official `MergeSchema` API) — if so, delegates to it
2. Falling back to inspecting `schema._strategies` dict directly (for non-standard schema objects)
3. Falling back to `schema.default` property
4. Returns `None` if no strategy can be determined

#### Data Flow

```
polars_merge_arrow()  ─┐
                       ├──_get_field_strategy(schema, col)  ──strategy_to_expr(col, strategy, ...)
polars_merge_dicts() ──┘         │
                                                           MergeSchema.strategy_for(field)
                                 │
                                                           MergeStrategy instance (LWW, MaxWins, etc.)
```

Both `polars_merge_arrow()` and `polars_merge_dicts()` call `_get_field_strategy` in a loop over every non-key column. The returned strategy is then compiled into a Polars expression by `strategy_to_expr()`.

#### Why H_ping is Near-Maximum

The Polars engine has exactly two entry points (`polars_merge_arrow`, `polars_merge_dicts`), and both call `_get_field_strategy` for every data column in the merge. Since merge operations always have at least one data column, `_get_field_strategy` is reached by effectively 100% of runtime paths — hence H_ping ≈ 1.0.

#### Stability

This function is a critical internal interface. Its behavior must remain consistent with `MergeSchema.strategy_for()` semantics. The fallback chain (`strategy_for` → `_strategies` dict → `default` → `None`) is load-bearing for accelerator compatibility.

