# Polars Engine

Rust-compiled merge kernel via Polars for 38.8× speedup.

## Quick Example

```python
# Polars engine is auto-selected when available:
# pip install crdt-merge[fast]
from crdt_merge.arrow import ArrowMerge
merger = ArrowMerge(schema=my_schema, engine="polars")
```

---

## API Reference

## `crdt_merge._polars_engine`

> Shared Polars merge kernel — zero-copy, Rust-compiled strategy resolution.

**Module:** `crdt_merge._polars_engine`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `polars_merge_arrow(left: "'pa.Table'", right: "'pa.Table'", key: 'str', schema: 'Any', timestamp_col: 'Optional[str]' = None) -> "Tuple['pa.Table', int]"`

Merge two Arrow tables using the Polars engine.

#### `polars_merge_dicts(left_rows: 'List[dict]', right_rows: 'List[dict]', key: 'str', schema: 'Any', timestamp_col: 'Optional[str]' = None) -> 'Tuple[List[dict], int]'`

Merge two lists of dicts using the Polars engine.

#### `strategy_to_expr(col: 'str', strategy: 'Any', timestamp_col: 'Optional[str]' = None, suffix: 'str' = '_right', left_dtype: "Optional['pl.DataType']" = None) -> "'pl.Expr'"`

Compile a MergeStrategy into a Polars expression.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
