# JSON/Dict Merge

Deep dict merge with LWW semantics and JSONL support.

## Quick Example

```python
from crdt_merge.json_merge import merge_dicts, merge_json_lines
result = merge_dicts(config_a, config_b)
```

---

## API Reference

## `crdt_merge.json_merge`

> Deep conflict-free JSON/dict merge using CRDT semantics.

**Module:** `crdt_merge.json_merge`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `merge_dicts(a: 'dict', b: 'dict', timestamps_a: 'Optional[Dict[str, float]]' = None, timestamps_b: 'Optional[Dict[str, float]]' = None, path: 'str' = '') -> 'dict'`

Deep merge two dicts with CRDT LWW semantics.

#### `merge_json_lines(lines_a: 'List[dict]', lines_b: 'List[dict]', key: 'Optional[str]' = None) -> 'List[dict]'`

Merge two JSONL datasets.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
