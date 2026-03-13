# crdt_merge.json_merge — JSON/Dict Merge

**Module**: `crdt_merge/json_merge.py`
**Layer**: 2 — Merge Engines
**LOC**: 105 *(corrected 2026-03-31 — was 145 from inventory; AST-verified actual: 105)*
**Dependencies**: `crdt_merge.strategies`

---

## Functions

### merge_dicts()
```python
def merge_dicts(
    dict_a: dict,
    dict_b: dict,
    schema: Optional[MergeSchema] = None
) -> dict
```
Merge two dictionaries using CRDT strategies.

### merge_json_lines()
```python
def merge_json_lines(
    file_a: str,
    file_b: str,
    key: str,
    schema: Optional[MergeSchema] = None,
    output: Optional[str] = None
) -> List[dict]
```
Merge two JSON Lines files. Optionally write output to file.
