# Accelerator: sqlite

**Module**: `crdt_merge/accelerators/sqlite.py`
**Category**: Accelerator Integration

---

SQLite extension adding CRDT merge functions.

```sql
SELECT crdt_lww(a.name, b.name, a.ts, b.ts) FROM ...
```
