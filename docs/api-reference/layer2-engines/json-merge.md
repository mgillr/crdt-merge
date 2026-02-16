# `crdt_merge/json_merge.py`

> Deep conflict-free JSON/dict merge using CRDT semantics.

Handles nested dicts, lists, and mixed types. Each leaf is treated as an
LWW Register — if both sides set a value, the one with the later timestamp
(or side B by default) wins.

**Source:** `crdt_merge/json_merge.py` | **Lines:** 105 *(corrected 2026-03-31 — was 145; AST-verified actual: 105)*

---

**Exports (`__all__`):** `['merge_dicts', 'merge_json_lines']`

## Scope & Limitations

`json_merge.py` is an **intentionally compact utility** (105 AST lines) providing basic JSON-level CRDT merge for flat and nested JSON documents.

### What it handles
- **Flat dict merges** with LWW (Last Writer Wins) semantics per key
- **Nested dict merges** via recursive descent
- **List merges** via concatenation and deduplication
- **JSON Lines** batch merging (`merge_json_lines()`)

### Edge case boundaries
For the following scenarios, use the `dataframe.py` engine (via `crdt_merge.merge()`) instead:
- **Complex array merges** requiring positional or element-level conflict resolution
- **Deeply nested conflicts** with per-path strategy configuration (use `MergeSchema`)
- **Mixed-type edge cases** where the same key has different types across replicas
- **Timestamp-aware resolution** beyond basic LWW (e.g., MaxWins, MinWins, Priority)

The compact scope is by design — `json_merge.py` serves as a lightweight utility for simple JSON document merging without requiring pandas/pyarrow dependencies.

## Functions

### `merge_dicts(a: dict, b: dict, timestamps_a: Optional[Dict[str, float]] = None, timestamps_b: Optional[Dict[str, float]] = None, path: str = '') → dict`

Deep merge two dicts with CRDT LWW semantics.
    
    Keys unique to either side: preserved.
    Keys in both: recursively merged if dicts, LWW if scalars.
    Lists: concatenated and deduped.

### `_merge_lists(a: list, b: list) → list`

Merge two lists: concatenate and deduplicate while preserving order.

### `_list_item_key(item: Any) → Any`

Create a hashable key for a list item.

### `merge_json_lines(lines_a: List[dict], lines_b: List[dict], key: Optional[str] = None) → List[dict]`

Merge two JSONL datasets.
    
    If key is provided, matches records by key and merges per-record.
    If no key, concatenates and deduplicates.

---

## RREA Chokepoint Analysis (2026-03-31)

| Symbol | Entropy (H) | Role |
|--------|-------------|------|
| `_list_item_key` | 0.413 | Create hashable key for list dedup — convergence point for list merge |
| `merge_dicts` | 0.2593 | Public entry point — recursive dict merge with LWW semantics |

