# crdt_merge._polars_engine — Polars Engine (Internal)

**Module**: `crdt_merge/_polars_engine.py`
**Layer**: 2 — Merge Engines
**LOC**: 306 *(corrected 2026-03-31 — was 433 from inventory; AST-verified actual: 306)*
**Dependencies**: `crdt_merge.strategies`, `polars`

---

## Internal Module

This module is prefixed with `_` indicating it is a private implementation detail. It should not be imported directly.

The Polars engine is used internally by `dataframe.py` when the input DataFrames are Polars DataFrames. The public API is `crdt_merge.merge()`.

---

## Architecture

The Polars engine provides:
1. Native Polars expression-based merge operations
2. Lazy evaluation support for large datasets
3. Type-aware strategy resolution leveraging Polars' type system

---
