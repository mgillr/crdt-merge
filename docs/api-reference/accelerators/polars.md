# Accelerator: polars

**Module**: `crdt_merge/accelerators/polars.py`
**Category**: Accelerator Integration

---

Native Polars plugin. Extends Polars with CRDT merge expressions.

```python
import polars as pl
from crdt_merge.accelerators.polars_plugin import register_plugin
register_plugin()
result = df_a.crdt_merge(df_b, on='id', strategy='LWW')
```
