# crdt_merge.probabilistic — Probabilistic Data Structures

**Module**: `crdt_merge/probabilistic.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 502
**Dependencies**: Python stdlib (`hashlib`, `struct`, `math`)

---

## Overview

Mergeable probabilistic data structures for approximate counting, membership testing, and frequency estimation at scale.

---

## Classes

### MergeableHLL

Mergeable HyperLogLog for approximate cardinality estimation.

```python
class MergeableHLL:
    def __init__(self, precision: int = 14) -> None
```

**Parameters**:
- `precision` (`int`): Number of register bits (4-18). Higher = more accurate, more memory. Default: 14 (16,384 registers).

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(item: Any) -> None` | Add item to the sketch |
| `count()` | `count() -> int` | Estimated cardinality |
| `merge()` | `merge(other: MergeableHLL) -> MergeableHLL` | Register-wise max. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> MergeableHLL` | Deserialize |

**Accuracy**: Standard error ~1.04/√(2^precision). At precision=14: ~0.81% error.

---

### MergeableBloom

Mergeable Bloom filter for approximate set membership.

```python
class MergeableBloom:
    def __init__(self, capacity: int = 10000, error_rate: float = 0.01) -> None
```

**Parameters**:
- `capacity` (`int`): Expected number of items.
- `error_rate` (`float`): Target false positive rate.

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(item: Any) -> None` | Add item |
| `contains()` | `contains(item: Any) -> bool` | Check membership (may have false positives) |
| `merge()` | `merge(other: MergeableBloom) -> MergeableBloom` | Bitwise OR. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> MergeableBloom` | Deserialize |

---

### MergeableCMS

Mergeable Count-Min Sketch for frequency estimation.

```python
class MergeableCMS:
    def __init__(self, width: int = 1000, depth: int = 5) -> None
```

**Parameters**:
- `width` (`int`): Number of counters per hash function.
- `depth` (`int`): Number of hash functions.

| Method | Signature | Description |
|--------|-----------|-------------|
| `add()` | `add(item: Any, count: int = 1) -> None` | Add item with count |
| `estimate()` | `estimate(item: Any) -> int` | Estimated frequency (never underestimates) |
| `merge()` | `merge(other: MergeableCMS) -> MergeableCMS` | Element-wise max. CRDT compliant. |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> MergeableCMS` | Deserialize |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `MergeableHLL.add_all(self, items: Iterable[Any]) → None`

Add multiple items.

**Parameters:**
- `items` (`Iterable[Any]`)

**Returns:** `None`


### `MergeableHLL.standard_error(self) → float`

Return the standard error rate for this precision.

**Returns:** `float`


### `MergeableHLL.size_bytes(self) → int`

Return the memory usage in bytes.

**Returns:** `int`


### `MergeableBloom.add_all(self, items: Iterable[Any]) → None`

Add multiple items.

**Parameters:**
- `items` (`Iterable[Any]`)

**Returns:** `None`


### `MergeableBloom.estimated_fp_rate(self) → float`

Estimate current false positive rate based on fill ratio.

**Returns:** `float`


### `MergeableBloom.size_bytes(self) → int`

Return memory usage in bytes.

**Returns:** `int`


### `MergeableCMS.add_all(self, items: Iterable[Any]) → None`

Add multiple items (count 1 each).

**Parameters:**
- `items` (`Iterable[Any]`)

**Returns:** `None`


### `MergeableCMS.total(self) → int`

Total count of all items added.
        
        Note: After merge, this reflects max(self.total, other.total) per CRDT
        semantics (register-max). For the combined total across distinct nodes,
        sum the totals before merging.
        

**Returns:** `int`


### `MergeableCMS.size_bytes(self) → int`

Approximate memory usage in bytes.

**Returns:** `int`


---

## Internal/Private API


### Module-Level Functions

#### `_hash128(item: Any, seed: int) -> int`

Generate a 128-bit hash from any item. Used internally by MergeableBloom for bit positions.

**Parameters:**
- `item` (`Any`): Item to hash (converted to string internally)
- `seed` (`int`): Hash seed for independent hash functions

**Returns:** `int` — 128-bit integer hash


#### `_hash64(item: Any, seed: int) -> int`

Generate a 64-bit hash from any item. Used internally by MergeableHLL and MergeableCMS.

**Parameters:**
- `item` (`Any`): Item to hash
- `seed` (`int`): Hash seed

**Returns:** `int` — 64-bit integer hash


#### `_leading_zeros(value: int, bits: int) -> int`

Count leading zeros in the binary representation. Core to HyperLogLog cardinality estimation.

**Parameters:**
- `value` (`int`): Integer value to analyze
- `bits` (`int`): Total bit width

**Returns:** `int` — count of leading zeros


### MergeableHLL Internal Methods

#### `MergeableHLL._compute_alpha(self) -> float`

Compute the bias correction constant for HLL cardinality estimation. Value depends on precision parameter.

**Returns:** `float`


### MergeableBloom Internal Methods

#### `MergeableBloom._optimal_size(n: int, p: float) -> int` (staticmethod)

Calculate optimal bit array size for given capacity and error rate. Formula: `-(n * ln(p)) / (ln(2)^2)`.

**Parameters:**
- `n` (`int`): Expected number of items
- `p` (`float`): Target false positive rate

**Returns:** `int`


#### `MergeableBloom._optimal_hashes(m: int, n: int) -> int` (staticmethod)

Calculate optimal number of hash functions. Formula: `(m/n) * ln(2)`.

**Parameters:**
- `m` (`int`): Bit array size
- `n` (`int`): Expected number of items

**Returns:** `int`


#### `MergeableBloom._get_positions(self, item: Any) -> list`

Get the bit positions for an item across all hash functions.

**Parameters:**
- `item` (`Any`): Item to hash

**Returns:** `list` — list of integer positions


#### `MergeableBloom._set_bit(self, pos: int) -> None`

Set a single bit in the bit array.

**Parameters:**
- `pos` (`int`): Bit position


#### `MergeableBloom._get_bit(self, pos: int) -> bool`

Check if a bit is set in the bit array.

**Parameters:**
- `pos` (`int`): Bit position

**Returns:** `bool`


### MergeableCMS Internal Methods

#### `MergeableCMS._positions(self, item: Any) -> list`

Get hash positions for each row in the count matrix.

**Parameters:**
- `item` (`Any`): Item to hash

**Returns:** `list` — list of (row, position) pairs


---

## automatic Methods (Missing from initial docs)

### `MergeableHLL.__repr__(self) -> str`

Returns `"MergeableHLL(precision=14, ~N items)"`.

### `MergeableHLL.__eq__(self, other: object) -> bool`

Equality based on precision and register array contents.

### `MergeableBloom.__repr__(self) -> str`

Returns `"MergeableBloom(capacity=N, fp_rate=P)"`.

### `MergeableBloom.__eq__(self, other: object) -> bool`

Equality based on bit array contents and parameters.

### `MergeableCMS.__repr__(self) -> str`

Returns `"MergeableCMS(width=W, depth=D)"`.

### `MergeableCMS.__eq__(self, other: object) -> bool`

Equality based on count matrix contents and dimensions.

---
