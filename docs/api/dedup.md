# Deduplication

Exact, fuzzy (bigram), and MinHash deduplication.

## Quick Example

```python
from crdt_merge.dedup import dedup_list, dedup_records, MinHashDedup
unique = dedup_list(["hello", "world", "hello"])
```

---

## API Reference

## `crdt_merge.dedup`

> High-performance deduplication powered by CRDT OR-Sets.

**Module:** `crdt_merge.dedup`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `DedupIndex(node_id: 'str' = 'default')`

A distributed-friendly dedup index backed by a CRDT OR-Set.

**Properties:**

- `size` — 

**Methods:**

- `add_exact(self, text: 'str') -> 'bool'` — Returns True if text is new (not a duplicate).
- `add_fuzzy(self, text: 'str', threshold: 'float' = 0.85) -> 'Tuple[bool, Optional[str]]'` — Returns (is_new, matched_hash_or_None).
- `merge(self, other: 'DedupIndex') -> 'DedupIndex'` — Merge two dedup indices — union of all seen hashes.

#### `MinHashDedup(num_hashes: 'int' = 200, threshold: 'float' = 0.5)`

MinHash-based dedup for large-scale near-duplicate detection.

**Methods:**

- `add(self, item: 'Any', text: 'str') -> 'bool'` — Add item. Returns True if unique, False if near-duplicate found.
- `dedup(self, items: 'List[Any]', text_fn: 'Callable[[Any], str]') -> 'List[Any]'` — Deduplicate a list of items.

#### `ORSet()`

Observed-Remove Set — add and remove elements without conflicts.

**Properties:**

- `value` — 

**Methods:**

- `add(self, element: 'Hashable') -> 'str'` — 
- `contains(self, element: 'Hashable') -> 'bool'` — 
- `from_dict(d: 'dict') -> 'ORSet'` — 
- `merge(self, other: 'ORSet') -> 'ORSet'` — 
- `remove(self, element: 'Hashable') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

### Functions

#### `dedup_list(items: 'List[str]', method: 'str' = 'exact', threshold: 'float' = 0.85, key: 'Optional[Callable[[str], str]]' = None) -> 'Tuple[List[str], List[int]]'`

Deduplicate a list of strings.

#### `dedup_records(records: 'List[dict]', columns: 'Optional[List[str]]' = None, method: 'str' = 'exact', threshold: 'float' = 0.85) -> 'Tuple[List[dict], int]'`

Deduplicate a list of dicts/records.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
