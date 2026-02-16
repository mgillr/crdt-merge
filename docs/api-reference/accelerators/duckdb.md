# Accelerator: duckdb

**Module**: `crdt_merge/accelerators/duckdb.py`
**Category**: Accelerator Integration

---

DuckDB UDF integration. Register CRDT merge operations as DuckDB user-defined functions for SQL-based merging.

```sql
SELECT crdt_merge(a.*, b.*, 'LWW') FROM table_a a JOIN table_b b ON a.id = b.id;
```
