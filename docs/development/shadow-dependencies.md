# Shadow Dependencies

**RREA Classification:** SHADOW — private helpers with zero public visibility but critical to internal operation.

This document catalogues the 22 private helper functions and methods identified during RREA (Reachability, Risk, Entropy Analysis) as **shadow dependencies** — internal symbols that are never exported but sit on critical code paths. Changes to these helpers can silently break downstream behavior.

---

## Overview

| # | Module | Symbol | Purpose | Callers |
|---|--------|--------|---------|---------|
| 1 | `strategies.py` | `_safe_parse_ts()` | Timestamp parsing with silent fallback | `MergeSchema.resolve_row()` |
| 2 | `strategies.py` | `UnionSet._to_set()` | Value-to-set conversion | `UnionSet.resolve()` |
| 3 | `probabilistic.py` | `_hash128()` | 128-bit MD5 hash generation | `_hash64()`, all probabilistic types |
| 4 | `probabilistic.py` | `_hash64()` | 64-bit hash truncation | `MergeableHLL.add()`, `MergeableBloom._get_positions()`, `MergeableCMS._positions()` |
| 5 | `probabilistic.py` | `_leading_zeros()` | Leading-zero count for HLL rank | `MergeableHLL.add()` |
| 6 | `probabilistic.py` | `MergeableHLL._compute_alpha()` | HLL bias correction constant | `MergeableHLL.__init__()` |
| 7 | `probabilistic.py` | `MergeableBloom._optimal_size()` | Bloom filter bit-array sizing | `MergeableBloom.__init__()` |
| 8 | `probabilistic.py` | `MergeableBloom._optimal_hashes()` | Optimal hash-function count | `MergeableBloom.__init__()` |
| 9 | `probabilistic.py` | `MergeableBloom._get_positions()` | Double-hashing for bit positions | `MergeableBloom.add()`, `.contains()` |
| 10 | `probabilistic.py` | `MergeableBloom._set_bit()` | Set a single bit in the filter | `MergeableBloom.add()` |
| 11 | `probabilistic.py` | `MergeableBloom._get_bit()` | Read a single bit from the filter | `MergeableBloom.contains()` |
| 12 | `probabilistic.py` | `MergeableCMS._positions()` | CMS double-hashing for row positions | `MergeableCMS.add()`, `.estimate()` |
| 13 | `verify.py` | `_are_equal()` | Deep equality for CRDT objects, DataFrames, floats | `verify_commutative()`, `verify_associative()`, `verify_idempotent()`, `verify_convergence()` |
| 14 | `wire.py` | `_get_delta_module()` | Lazy import of `crdt_merge.delta` | `_is_delta()`, serialization path |
| 15 | `wire.py` | `_is_delta()` | Check if object is a delta type | `serialize()` |
| 16 | `wire.py` | `_encode_value()` | Encode a Python value to wire bytes | `serialize()`, `serialize_batch()` |
| 17 | `wire.py` | `_decode_value()` | Decode wire bytes to a Python value | `deserialize()`, `deserialize_batch()` |
| 18 | `wire.py` | `_encode_json_payload()` | JSON → compressed bytes for wire frames | `serialize()` |
| 19 | `wire.py` | `_decode_json_payload()` | Compressed bytes → JSON for deserialization | `deserialize()` |
| 20 | `wire.py` | `_build_wire_frame()` | Construct type-tagged wire frame with optional compression | `serialize()` |
| 21 | `dataframe.py` | `_parse_timestamp()` | Timestamp parsing for DataFrame merge paths | `merge()`, `_merge_rows()` |
| 22 | `dataframe.py` | `_to_records()` | Convert pandas/polars/dict DataFrames to list-of-dicts | `merge()`, `diff()` |

---

## Detailed Reference

### 1. `strategies._safe_parse_ts(value: Any) -> float`

**Purpose:** Robustly parse a timestamp value into a float. Handles `int`, `float`, numeric strings, ISO-8601 datetime strings, and objects with a `.timestamp()` method.

**Silent fallback:** Returns `0.0` for any unparseable value with a `UserWarning`. This means invalid timestamps silently lose all LWW comparisons.

**Caller chain:** `MergeSchema.resolve_row()` → `_safe_parse_ts(row.get(timestamp_col))`

**Stability:** STABLE — changing the fallback value or raising exceptions would be a breaking change for all downstream `MergeSchema` users.

---

### 2. `strategies.UnionSet._to_set(self, val: Any) -> set`

**Purpose:** Convert an arbitrary value to a `set` for union operations. Splits strings by `self.separator`, strips whitespace, and filters empty strings. Returns `set()` for `None`.

**Implementation:**
```python
def _to_set(self, val: Any) -> set:
    if val is None:
        return set()
    return {s.strip() for s in str(val).split(self.separator) if s.strip()}
```

**Caller chain:** `UnionSet.resolve()` → `_to_set(val_a)`, `_to_set(val_b)`

**Stability:** STABLE — the separator-based splitting behavior is a public contract of `UnionSet`.

---

### 3–4. `probabilistic._hash128()` / `_hash64()`

**Purpose:** Generate deterministic hash values from arbitrary Python objects. `_hash128` uses MD5 over `repr(item)` with an integer seed packed as big-endian 4 bytes. `_hash64` truncates the result to 64 bits.

**Implementation:**
```python
def _hash128(item: Any, seed: int = 0) -> int:
    data = repr(item).encode('utf-8') + struct.pack('>I', seed)
    return int(hashlib.md5(data).hexdigest(), 16)

def _hash64(item: Any, seed: int = 0) -> int:
    return _hash128(item, seed) & 0xFFFFFFFFFFFFFFFF
```

**Caller chain:** Every `add()`, `contains()`, `estimate()`, and `_get_positions()` / `_positions()` call in `MergeableHLL`, `MergeableBloom`, and `MergeableCMS` flows through `_hash64`.

**Stability:** FROZEN — changing the hash function would break all existing serialized probabilistic structures (register values, bit positions, and CMS cell assignments would shift).

---

### 5. `probabilistic._leading_zeros(value: int, bits: int = 64) -> int`

**Purpose:** Count leading zeros in the binary representation of a value. Used by `MergeableHLL.add()` to compute the "rank" (run of leading zeros) that determines which register is updated.

**Caller chain:** `MergeableHLL.add()` → `_leading_zeros(remaining, 64 - self.precision) + 1`

**Stability:** FROZEN — integral to HLL cardinality estimation accuracy.

---

### 6. `probabilistic.MergeableHLL._compute_alpha() -> float`

**Purpose:** Compute the bias correction constant α for HyperLogLog cardinality estimation. Uses hardcoded values for `m ∈ {16, 32, 64}` and the formula `0.7213 / (1.0 + 1.079 / m)` for larger register counts.

**Caller chain:** `MergeableHLL.__init__()` → `self._alpha = self._compute_alpha()`

**Stability:** FROZEN — α directly affects cardinality estimates.

---

### 7–8. `probabilistic.MergeableBloom._optimal_size()` / `._optimal_hashes()`

**Purpose:** Calculate optimal Bloom filter parameters from capacity and false-positive rate targets.

- `_optimal_size(n, p)` → `ceil(-n × ln(p) / ln(2)²)`, minimum 64 bits
- `_optimal_hashes(m, n)` → `ceil((m/n) × ln(2))`, minimum 1

**Caller chain:** `MergeableBloom.__init__()` — only when `_size` / `_num_hashes` override params are not provided.

**Stability:** STABLE — changing these formulas would change filter dimensions for the same inputs, breaking merge compatibility with existing filters.

---

### 9–11. `MergeableBloom._get_positions()` / `._set_bit()` / `._get_bit()`

**Purpose:** Low-level bit manipulation for the Bloom filter.

- `_get_positions(item)` uses double hashing: `(h1 + i × h2) % self.size` for `i ∈ [0, num_hashes)`
- `_set_bit(pos)` sets bit at position `pos` using byte-level OR
- `_get_bit(pos)` reads bit at position `pos` using byte-level AND

**Caller chain:** `add()` → `_get_positions()` → `_set_bit()`; `contains()` → `_get_positions()` → `_get_bit()`

**Stability:** FROZEN — bit layout determines merge compatibility.

---

### 12. `probabilistic.MergeableCMS._positions(item: Any) -> list`

**Purpose:** Compute per-row hash positions for the Count-Min Sketch using double hashing: `(h1 + i × h2) % self.width` for `i ∈ [0, depth)`.

**Caller chain:** `MergeableCMS.add()` → `_positions(item)`; `MergeableCMS.estimate()` → `_positions(item)`

**Stability:** FROZEN — position mapping determines cell assignment and merge compatibility.

---

### 13. `verify._are_equal(a: Any, b: Any) -> bool`

**Purpose:** Deep equality check that handles CRDT objects (via `.value` property), pandas/polars DataFrames (sorted record comparison), nested dicts/lists, sets, and floats with epsilon tolerance (`1e-10`). Also handles `NaN == NaN` as `True`.

**Caller chain:** All four verification functions (`verify_commutative`, `verify_associative`, `verify_idempotent`, `verify_convergence`) use `_are_equal` as the default `eq_fn`.

**Stability:** STABLE — this is the correctness oracle for the entire verification toolkit. False negatives here produce spurious verification failures; false positives allow broken merges to pass.

---

### 14–15. `wire._get_delta_module()` / `wire._is_delta()`

**Purpose:** Lazy-import pattern for the `crdt_merge.delta` module. `_get_delta_module()` uses `importlib.import_module` with caching. `_is_delta(obj)` checks whether an object is an instance of a delta type from the delta module.

**Caller chain:** `serialize()` → `_is_delta(obj)` → `_get_delta_module()` (on first call)

**Stability:** STABLE — the lazy-import pattern avoids circular imports between `wire` and `delta`.

---

### 16–17. `wire._encode_value()` / `wire._decode_value()`

**Purpose:** Low-level serialization of Python values to/from compact binary format for the wire protocol. Handles `None`, `bool`, `int`, `float`, `str`, `bytes`, `list`, `dict`, and CRDT objects (via `.to_dict()`).

**Caller chain:** `serialize()` → `_encode_value()` → wire bytes; `deserialize()` → `_decode_value()` → Python objects

**Stability:** FROZEN — changing the encoding format would break wire compatibility with all existing serialized data.

---

### 18–19. `wire._encode_json_payload()` / `wire._decode_json_payload()`

**Purpose:** Convert a dict to JSON bytes with optional zlib compression (used for payloads above a size threshold), and the reverse.

**Caller chain:** `serialize()` → `_encode_json_payload()` → `_build_wire_frame()`; `deserialize()` → `_decode_json_payload()`

**Stability:** FROZEN — compression format is part of the wire protocol.

---

### 20. `wire._build_wire_frame(type_tag: int, payload: bytes, compress: bool = False) -> bytes`

**Purpose:** Construct a wire frame with a type tag byte, length header, and payload (optionally zlib-compressed). This is the outermost framing layer of the wire protocol.

**Caller chain:** `serialize()` → `_build_wire_frame(tag, payload)` → final bytes

**Stability:** FROZEN — frame layout is the wire protocol.

---

### 21. `dataframe._parse_timestamp(value: Any) -> float`

**Purpose:** Parse a timestamp value for the DataFrame merge path. Similar to `strategies._safe_parse_ts()` but used in the `dataframe.merge()` / `_merge_rows()` code path rather than the `MergeSchema` path.

**Caller chain:** `merge()` → `_merge_rows()` → `_parse_timestamp(row[ts_col])`

**Stability:** STABLE — timestamp parsing consistency across the two code paths (`_parse_timestamp` vs `_safe_parse_ts`) is critical. They should produce identical results for identical inputs.

---

### 22. `dataframe._to_records(df: Any) -> Tuple[List[Dict], List[str], str]`

**Purpose:** Normalize any supported DataFrame input (pandas DataFrame, polars DataFrame, list of dicts) into a canonical `(records, columns, lib)` tuple. Detects the input library (`"pandas"`, `"polars"`, `"dict"`) and extracts column names.

**Caller chain:** `merge(df_a, df_b, ...)` → `_to_records(df_a)`, `_to_records(df_b)` — called at the top of every merge operation.

**Stability:** STABLE — adding new DataFrame library support (e.g., cuDF) would extend this function.

---

## Dependency Graph

```
Public API
    │
    ├── merge() ──────────────── _to_records() ── _parse_timestamp()
    │                                                  │
    ├── MergeSchema.resolve_row() ── _safe_parse_ts()  │
    │                                                  │
    ├── UnionSet.resolve() ──── UnionSet._to_set()     │
    │                                                  │
    ├── serialize() ──── _is_delta() ── _get_delta_module()
    │       │                │
    │       ├── _encode_value() ── _encode_json_payload()
    │       └── _build_wire_frame()
    │
    ├── deserialize() ── _decode_value() ── _decode_json_payload()
    │
    ├── verify_crdt() ── verify_commutative() ── _are_equal()
    │       │            verify_associative()  ── _are_equal()
    │       │            verify_idempotent()   ── _are_equal()
    │       │            verify_convergence()  ── _are_equal()
    │
    └── MergeableHLL / MergeableBloom / MergeableCMS
            │
            ├── _hash128() ── _hash64()
            ├── _leading_zeros()
            ├── _compute_alpha()
            ├── _optimal_size() / _optimal_hashes()
            ├── _get_positions() ── _set_bit() / _get_bit()
            └── _positions()
```

---

## Stability Classification

| Level | Meaning | Shadow Deps |
|-------|---------|-------------|
| **FROZEN** | Must never change — serialized format or hash function dependency | `_hash128`, `_hash64`, `_leading_zeros`, `_compute_alpha`, `_set_bit`, `_get_bit`, `_get_positions`, `_positions`, `_encode_value`, `_decode_value`, `_encode_json_payload`, `_decode_json_payload`, `_build_wire_frame` |
| **STABLE** | Change with extreme caution — altering behavior affects public API semantics | `_safe_parse_ts`, `_to_set`, `_are_equal`, `_get_delta_module`, `_is_delta`, `_parse_timestamp`, `_to_records`, `_optimal_size`, `_optimal_hashes` |
