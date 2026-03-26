# crdt_merge.dedup — Deduplication

**Module**: `crdt_merge/dedup.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 260
**Dependencies**: `crdt_merge.core`, `crdt_merge.strategies`

---

## Overview

Deduplication utilities for identifying and removing duplicate records, including fuzzy/approximate matching via MinHash.

---

## Functions

### dedup()
```python
def dedup(records: List[dict], key: str, strategy: Optional[MergeStrategy] = None) -> List[dict]
```
Deduplicate records by key, merging duplicates using the provided strategy (default: LWW).

**Parameters**:
- `records` (`List[dict]`): Input records
- `key` (`str`): Field to deduplicate on
- `strategy` (`MergeStrategy | None`): How to merge duplicate records. Default: `LWW()`

**Returns**: Deduplicated list of records.

### dedup_records()
```python
def dedup_records(records: List[dict], keys: List[str], schema: Optional[MergeSchema] = None) -> List[dict]
```
Multi-key deduplication with per-field merge strategies.

---

## Classes

### DedupIndex

Hash-based deduplication index for fast lookup.

```python
class DedupIndex:
    def __init__(self, key: str) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(record: dict) -> bool` | Add record; returns `True` if new, `False` if duplicate |
| `get()` | `get(key_value: Any) -> Optional[dict]` | Get record by key value |
| `merge_add()` | `merge_add(record: dict, strategy: MergeStrategy) -> dict` | Add or merge with existing |

---

### MinHashDedup

Approximate deduplication using MinHash locality-sensitive hashing.

```python
class MinHashDedup:
    def __init__(self, num_perm: int = 128, threshold: float = 0.5) -> None
```

**Parameters**:
- `num_perm` (`int`): Number of permutations (higher = more accurate). Default: 128.
- `threshold` (`float`): Jaccard similarity threshold for dedup. Default: 0.5.

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(record: dict, text_fields: List[str]) -> bool` | Add record; returns True if sufficiently unique |
| `find_duplicates()` | `find_duplicates(records: List[dict], text_fields: List[str]) -> List[Tuple[int, int]]` | Find approximate duplicate pairs |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `DedupIndex.add_exact(self, text: str) → bool`

Returns True if text is new (not a duplicate).
        
        Uses case-insensitive comparison but preserves all whitespace
        (tabs, newlines, etc.) — "hello	world" and "hello
world" are distinct.
        

**Parameters:**
- `text` (`str`)

**Returns:** `bool`



### `DedupIndex.add_fuzzy(self, text: str, threshold: float = 0.85) → Tuple[bool, Optional[str]]`

Returns (is_new, matched_hash_or_None).

**Parameters:**
- `text` (`str`)
- `threshold` (`float`)

**Returns:** `Tuple[bool, Optional[str]]`



### `DedupIndex.size(self) → int`

Returns the number of unique hashes currently tracked in the dedup index. This is the count of live elements in the underlying OR-Set.

**Returns:** `int`



---

## Internal/Private API

*Discovered during Team 4 RREA re-analysis.*

### Module-Level Helper Functions

#### `_normalize(text: str) -> str`

Normalize text for comparison. Strips whitespace, lowercases, removes punctuation.

**Parameters:**
- `text` (`str`): Raw text to normalize

**Returns:** `str` — normalized text

**RREA Classification:** SHADOW

#### `_hash_text(text: str) -> str`

SHA-256 hash of normalized text. Used by DedupIndex for exact matching.

**Parameters:**
- `text` (`str`): Text to hash

**Returns:** `str` — hex digest

**RREA Classification:** SHADOW

#### `_bigrams(text: str) -> Set[str]`

Generate character bigrams from text. Used for Dice similarity coefficient.

**Parameters:**
- `text` (`str`): Input text

**Returns:** `Set[str]` — set of 2-character substrings

**RREA Classification:** SHADOW

#### `_dice_similarity(a: str, b: str) -> float`

Dice coefficient between two strings. `2 * |bigrams(a) ∩ bigrams(b)| / (|bigrams(a)| + |bigrams(b)|)`.

**Parameters:**
- `a` (`str`): First string
- `b` (`str`): Second string

**Returns:** `float` — similarity score in [0, 1]

**RREA Classification:** SHADOW

### Public Functions (Missing from initial docs)

#### `dedup_list(items: List[str], method: str = "exact", threshold: float = 0.85, key: Optional[Callable[[str], str]] = None) -> Tuple[List[str], List[int]]`

Deduplicate a list of strings.

**Parameters:**
- `items` (`List[str]`): List of strings to deduplicate
- `method` (`str`): `"exact"` or `"fuzzy"`. Default: `"exact"`
- `threshold` (`float`): Similarity threshold for fuzzy dedup. Default: `0.85`
- `key` (`Optional[Callable]`): Optional function to extract comparison text from each item

**Returns:** `Tuple[List[str], List[int]]` — (unique items, indices of duplicates)

**RREA Classification:** SPECIALIZED — public API, exported in `__all__`

### MinHashDedup Internal Methods

#### `MinHashDedup._minhash(self, text: str) -> Tuple[int, ...]`

Compute MinHash signature for text. Generates `num_perm` independent hash values.

**Parameters:**
- `text` (`str`): Input text

**Returns:** `Tuple[int, ...]` — MinHash signature vector

**RREA Classification:** SHADOW

#### `MinHashDedup._jaccard_estimate(self, sig_a: Tuple[int, ...], sig_b: Tuple[int, ...]) -> float`

Estimate Jaccard similarity from MinHash signatures. `|matching positions| / num_perm`.

**Parameters:**
- `sig_a` (`Tuple[int, ...]`): First MinHash signature
- `sig_b` (`Tuple[int, ...]`): Second MinHash signature

**Returns:** `float` — estimated Jaccard similarity

**RREA Classification:** SHADOW

---

## automatic Methods (Missing from initial docs)

### `DedupIndex.__repr__(self)`

Returns string representation showing key name and index size.

---

## RREA Priority Analysis

| Symbol | Classification | Entropy | Reachability Score |
|--------|---------------|---------|-------------------|
| `DedupIndex` | SPECIALIZED | 0.3651 | 7.0 — **#2 entropy chokepoint** |
| `DedupIndex.add_exact` | DEAD (static) | 0.2714 | 4.7 — dynamic dispatch FP |
| `DedupIndex.add_fuzzy` | DEAD (static) | 0.2714 | 4.7 — dynamic dispatch FP |
| `dedup_list` | SPECIALIZED | — | Public function, exported |
| `dedup_records` | SPECIALIZED | — | Public function |
| `MinHashDedup` | SPECIALIZED | — | Public class |
| `MinHashDedup.dedup` | SPECIALIZED | — | Public entry point |
| `_normalize` | SHADOW | — | Critical text normalization |
| `_hash_text` | SHADOW | — | Exact dedup core |
| `_bigrams` | SHADOW | — | Fuzzy dedup core |
| `_dice_similarity` | SHADOW | — | Fuzzy dedup core |

> **DedupIndex** is the **#2 entropy chokepoint** in Layer 1 (entropy=0.3651, reachability=7.0).
