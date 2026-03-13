# Accelerator: dbt

**Module**: `crdt_merge/accelerators/dbt.py`
**Category**: Accelerator Integration

---

dbt macro package. Use CRDT merge strategies in dbt models.

```sql
{{ crdt_merge(ref('source_a'), ref('source_b'), 'id', {'name': 'LWW', 'score': 'MaxWins'}) }}
```
