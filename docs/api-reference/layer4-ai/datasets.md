# crdt_merge.datasets_ext — HuggingFace Datasets Integration

**Module**: `crdt_merge/datasets_ext.py`
**Layer**: 4 — AI / Model / Agent
**LOC**: 106

---

## Functions

### merge_datasets()
```python
def merge_datasets(
    dataset_a,  # HuggingFace Dataset
    dataset_b,
    key: str,
    schema: Optional[MergeSchema] = None
) -> Dataset
```
Merge two HuggingFace Datasets using CRDT strategies.


## Analysis Notes
