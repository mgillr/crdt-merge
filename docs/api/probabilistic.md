# Probabilistic CRDTs

HyperLogLog, Bloom filter, Count-Min Sketch with CRDT merge semantics.

## Quick Example

```python
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS
hll = MergeableHLL(precision=14)
hll.add("user_123")
```

---

## API Reference

## `crdt_merge.probabilistic`

> Probabilistic CRDTs — approximate data structures with conflict-free merge semantics.

**Module:** `crdt_merge.probabilistic`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `MergeableBloom(capacity: int = 10000, fp_rate: float = 0.01, *, _size: Optional[int] = None, _num_hashes: Optional[int] = None)`

Bloom filter with CRDT merge semantics.

**Methods:**

- `add(self, item: Any) -> None` — Add an item to the filter.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items.
- `contains(self, item: Any) -> bool` — Check if an item might be in the set.
- `estimated_fp_rate(self) -> float` — Estimate current false positive rate based on fill ratio.
- `from_dict(d: dict) -> 'MergeableBloom'` — Deserialize from dict.
- `merge(self, other: 'MergeableBloom') -> 'MergeableBloom'` — Merge two Bloom filters via bitwise OR.
- `size_bytes(self) -> int` — Return memory usage in bytes.
- `to_dict(self) -> dict` — Serialize to dict for wire format.

#### `MergeableCMS(width: int = 2000, depth: int = 7)`

Count-Min Sketch with CRDT merge semantics.

**Properties:**

- `total` — Total count of all items added.

**Methods:**

- `add(self, item: Any, count: int = 1) -> None` — Add an item with the given count.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items (count 1 each).
- `estimate(self, item: Any) -> int` — Estimate the count of an item.
- `from_dict(d: dict) -> 'MergeableCMS'` — Deserialize from dict.
- `merge(self, other: 'MergeableCMS') -> 'MergeableCMS'` — Merge two Count-Min Sketches via per-cell max.
- `size_bytes(self) -> int` — Approximate memory usage in bytes.
- `to_dict(self) -> dict` — Serialize to dict for wire format.

#### `MergeableHLL(precision: int = 14)`

HyperLogLog cardinality estimator with CRDT merge semantics.

**Methods:**

- `add(self, item: Any) -> None` — Add an item to the HLL.
- `add_all(self, items: Iterable[Any]) -> None` — Add multiple items.
- `cardinality(self) -> float` — Estimate the number of distinct elements.
- `from_dict(d: dict) -> 'MergeableHLL'` — Deserialize from dict.
- `merge(self, other: 'MergeableHLL') -> 'MergeableHLL'` — Merge two HLLs by taking register-max.
- `size_bytes(self) -> int` — Return the memory usage in bytes.
- `standard_error(self) -> float` — Return the standard error rate for this precision.
- `to_dict(self) -> dict` — Serialize to dict for wire format.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
