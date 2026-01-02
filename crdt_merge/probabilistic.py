# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Probabilistic CRDTs — approximate data structures with conflict-free merge semantics.

These data structures trade exact precision for massive space savings while
maintaining all CRDT properties (commutativity, associativity, idempotency).

Classes:
    MergeableHLL:    HyperLogLog for cardinality estimation. Merge via register-max.
    MergeableBloom:  Bloom filter for membership testing. Merge via bitwise OR.
    MergeableCMS:    Count-Min Sketch for frequency estimation. Merge via per-cell max.

All three are natural CRDTs — their merge operations inherently satisfy:
    - Commutativity:  A.merge(B) == B.merge(A)
    - Associativity:  A.merge(B).merge(C) == A.merge(B.merge(C))
    - Idempotency:    A.merge(A) == A

Use cases:
    - Distributed analytics without central aggregation
    - Federated unique counting across edge nodes
    - Mesh network membership tracking
    - Edge-aggregated metrics with eventual consistency

New in v0.5.0.
"""

import hashlib
import math
import struct
from typing import Any, Iterable, Optional


# ── Hash Utilities ─────────────────────────────────────────────────────────

def _hash128(item: Any, seed: int = 0) -> int:
    """Generate a 128-bit hash from any item."""
    data = repr(item).encode('utf-8') + struct.pack('>I', seed)
    return int(hashlib.md5(data).hexdigest(), 16)


def _hash64(item: Any, seed: int = 0) -> int:
    """Generate a 64-bit hash from any item."""
    return _hash128(item, seed) & 0xFFFFFFFFFFFFFFFF


def _leading_zeros(value: int, bits: int = 64) -> int:
    """Count leading zeros in the binary representation."""
    if value == 0:
        return bits
    count = 0
    for i in range(bits - 1, -1, -1):
        if value & (1 << i):
            break
        count += 1
    return count


# ── MergeableHLL ───────────────────────────────────────────────────────────

class MergeableHLL:
    """
    HyperLogLog cardinality estimator with CRDT merge semantics.

    Estimates the number of distinct elements in a set using O(m) space
    where m = 2^precision. Merge is register-max: take the maximum value
    in each register position across replicas.

    CRDT merge: register-max (commutative, associative, idempotent).

    Args:
        precision: Number of bits for register indexing (4-18).
            Higher precision = more accuracy, more memory.
            Default 14 gives ~0.81% standard error with 16KB of registers.

    Examples:
        >>> hll_a = MergeableHLL(precision=14)
        >>> hll_a.add_all(range(1000))
        >>> hll_b = MergeableHLL(precision=14)
        >>> hll_b.add_all(range(500, 1500))
        >>> merged = hll_a.merge(hll_b)
        >>> abs(merged.cardinality() - 1500) < 50  # ~0.81% error
        True
    """

    def __init__(self, precision: int = 14):
        if not 4 <= precision <= 18:
            raise ValueError(f"Precision must be 4-18, got {precision}")
        self.precision = precision
        self.m = 1 << precision  # number of registers
        self.registers = bytearray(self.m)
        self._alpha = self._compute_alpha()

    def _compute_alpha(self) -> float:
        """Compute the bias correction constant."""
        m = self.m
        if m == 16:
            return 0.673
        elif m == 32:
            return 0.697
        elif m == 64:
            return 0.709
        else:
            return 0.7213 / (1.0 + 1.079 / m)

    def add(self, item: Any) -> None:
        """Add an item to the HLL."""
        h = _hash64(item)
        # Use first `precision` bits as register index
        idx = h >> (64 - self.precision)
        # Count leading zeros in remaining bits
        remaining = (h << self.precision) & 0xFFFFFFFFFFFFFFFF
        rank = _leading_zeros(remaining, 64 - self.precision) + 1
        self.registers[idx] = max(self.registers[idx], rank)

    def add_all(self, items: Iterable[Any]) -> None:
        """Add multiple items."""
        for item in items:
            self.add(item)

    def cardinality(self) -> float:
        """
        Estimate the number of distinct elements.

        Returns:
            float: Estimated cardinality.
        """
        # Harmonic mean of 2^(-register)
        indicator = sum(2.0 ** (-r) for r in self.registers)
        estimate = self._alpha * self.m * self.m / indicator

        # Small range correction
        if estimate <= 2.5 * self.m:
            zeros = self.registers.count(0)
            if zeros > 0:
                estimate = self.m * math.log(self.m / zeros)

        # Large range correction (64-bit hash)
        if estimate > (1 << 32) / 30.0:
            estimate = -(1 << 64) * math.log(1.0 - estimate / (1 << 64))

        return estimate

    def merge(self, other: 'MergeableHLL') -> 'MergeableHLL':
        """
        Merge two HLLs by taking register-max.

        This is a natural CRDT operation:
        - Commutative: A.merge(B) == B.merge(A)
        - Associative: A.merge(B).merge(C) == A.merge(B.merge(C))
        - Idempotent: A.merge(A) == A

        Args:
            other: Another MergeableHLL with the same precision.

        Returns:
            MergeableHLL: New merged HLL.
        """
        if self.precision != other.precision:
            raise ValueError(
                f"Cannot merge HLLs with different precisions: {self.precision} vs {other.precision}"
            )
        result = MergeableHLL(self.precision)
        for i in range(self.m):
            result.registers[i] = max(self.registers[i], other.registers[i])
        return result

    def standard_error(self) -> float:
        """Return the standard error rate for this precision."""
        return 1.04 / math.sqrt(self.m)

    def size_bytes(self) -> int:
        """Return the memory usage in bytes."""
        return self.m  # 1 byte per register

    def to_dict(self) -> dict:
        """Serialize to dict for wire format."""
        return {
            'type': 'hll',
            'precision': self.precision,
            'registers': list(self.registers),
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'MergeableHLL':
        """Deserialize from dict."""
        hll = cls(d['precision'])
        hll.registers = bytearray(d['registers'])
        return hll

    def __repr__(self) -> str:
        return f"MergeableHLL(precision={self.precision}, est_cardinality={self.cardinality():.0f})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MergeableHLL):
            return NotImplemented
        return self.precision == other.precision and self.registers == other.registers


# ── MergeableBloom ─────────────────────────────────────────────────────────

class MergeableBloom:
    """
    Bloom filter with CRDT merge semantics.

    Probabilistic membership test: no false negatives, tunable false positive rate.
    Merge is bitwise OR: the union of two Bloom filters is the OR of their bit arrays.

    CRDT merge: bitwise OR (commutative, associative, idempotent).

    Args:
        capacity: Expected number of items.
        fp_rate: Target false positive rate (default 0.01 = 1%).

    Examples:
        >>> bloom_a = MergeableBloom(capacity=10000, fp_rate=0.01)
        >>> bloom_a.add("alice")
        >>> bloom_b = MergeableBloom(capacity=10000, fp_rate=0.01)
        >>> bloom_b.add("bob")
        >>> merged = bloom_a.merge(bloom_b)
        >>> merged.contains("alice") and merged.contains("bob")
        True
    """

    def __init__(self, capacity: int = 10000, fp_rate: float = 0.01,
                 *, _size: Optional[int] = None, _num_hashes: Optional[int] = None):
        self.capacity = capacity
        self.fp_rate = fp_rate

        # Calculate optimal size and hash count
        if _size is not None:
            self.size = _size
        else:
            self.size = self._optimal_size(capacity, fp_rate)
        if _num_hashes is not None:
            self.num_hashes = _num_hashes
        else:
            self.num_hashes = self._optimal_hashes(self.size, capacity)

        self.bits = bytearray((self.size + 7) // 8)
        self._count = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        """Calculate optimal bit array size."""
        m = -n * math.log(p) / (math.log(2) ** 2)
        return max(int(math.ceil(m)), 64)

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        """Calculate optimal number of hash functions."""
        k = (m / max(n, 1)) * math.log(2)
        return max(int(math.ceil(k)), 1)

    def _get_positions(self, item: Any) -> list:
        """Get the bit positions for an item."""
        h1 = _hash64(item, seed=0)
        h2 = _hash64(item, seed=42)
        return [(h1 + i * h2) % self.size for i in range(self.num_hashes)]

    def _set_bit(self, pos: int) -> None:
        self.bits[pos >> 3] |= (1 << (pos & 7))

    def _get_bit(self, pos: int) -> bool:
        return bool(self.bits[pos >> 3] & (1 << (pos & 7)))

    def add(self, item: Any) -> None:
        """Add an item to the filter."""
        for pos in self._get_positions(item):
            self._set_bit(pos)
        self._count += 1

    def add_all(self, items: Iterable[Any]) -> None:
        """Add multiple items."""
        for item in items:
            self.add(item)

    def contains(self, item: Any) -> bool:
        """
        Check if an item might be in the set.

        Returns True if possibly present, False if definitely absent.
        """
        return all(self._get_bit(pos) for pos in self._get_positions(item))

    def estimated_fp_rate(self) -> float:
        """Estimate current false positive rate based on fill ratio."""
        bits_set = sum(bin(b).count('1') for b in self.bits)
        fill = bits_set / max(self.size, 1)
        return fill ** self.num_hashes

    def merge(self, other: 'MergeableBloom') -> 'MergeableBloom':
        """
        Merge two Bloom filters via bitwise OR.

        This is a natural CRDT operation:
        - Commutative: A.merge(B) == B.merge(A)
        - Associative: A.merge(B).merge(C) == A.merge(B.merge(C))
        - Idempotent: A.merge(A) == A

        Args:
            other: Another MergeableBloom with the same size and hash count.

        Returns:
            MergeableBloom: New merged filter.
        """
        if self.size != other.size or self.num_hashes != other.num_hashes:
            raise ValueError(
                f"Cannot merge Bloom filters with different parameters: "
                f"({self.size}, {self.num_hashes}) vs ({other.size}, {other.num_hashes})"
            )
        result = MergeableBloom(
            self.capacity, self.fp_rate,
            _size=self.size, _num_hashes=self.num_hashes
        )
        for i in range(len(self.bits)):
            result.bits[i] = self.bits[i] | other.bits[i]
        # Estimate count from bit array popcount (more accurate than additive)
        bits_set = sum(bin(b).count('1') for b in result.bits)
        if bits_set < result.size:
            # Use inverse fill-ratio formula: n ≈ -m * ln(1 - k/m)
            fill = bits_set / result.size
            result._count = int(-result.size / max(result.num_hashes, 1) * math.log(max(1 - fill, 1e-10)))
        else:
            result._count = max(self._count, other._count)
        return result

    def size_bytes(self) -> int:
        """Return memory usage in bytes."""
        return len(self.bits)

    def to_dict(self) -> dict:
        """Serialize to dict for wire format."""
        return {
            'type': 'bloom',
            'capacity': self.capacity,
            'fp_rate': self.fp_rate,
            'size': self.size,
            'num_hashes': self.num_hashes,
            'bits': list(self.bits),
            'count': self._count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'MergeableBloom':
        """Deserialize from dict."""
        bloom = cls(d['capacity'], d['fp_rate'],
                    _size=d['size'], _num_hashes=d['num_hashes'])
        bloom.bits = bytearray(d['bits'])
        bloom._count = d.get('count', 0)
        return bloom

    def __repr__(self) -> str:
        return f"MergeableBloom(capacity={self.capacity}, fp_rate={self.fp_rate}, items≈{self._count})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MergeableBloom):
            return NotImplemented
        return (self.size == other.size and
                self.num_hashes == other.num_hashes and
                self.bits == other.bits)


# ── MergeableCMS ───────────────────────────────────────────────────────────

class MergeableCMS:
    """
    Count-Min Sketch with CRDT merge semantics.

    Estimates the frequency of items in a stream using O(width × depth) space.
    Merge is per-cell max: each cell takes the maximum count across replicas.

    CRDT merge: per-cell max (commutative, associative, idempotent).

    Args:
        width: Number of counters per row (default 2000).
        depth: Number of hash functions / rows (default 7).

    Examples:
        >>> cms_a = MergeableCMS(width=1000, depth=5)
        >>> for _ in range(100): cms_a.add("x")
        >>> cms_b = MergeableCMS(width=1000, depth=5)
        >>> for _ in range(50): cms_b.add("x")
        >>> merged = cms_a.merge(cms_b)
        >>> merged.estimate("x")  # max(100, 50) = 100
        100
    """

    def __init__(self, width: int = 2000, depth: int = 7):
        if width < 1 or depth < 1:
            raise ValueError(f"Width and depth must be >= 1, got ({width}, {depth})")
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]
        self._total = 0

    def _positions(self, item: Any) -> list:
        """Get hash positions for each row."""
        h1 = _hash64(item, seed=0)
        h2 = _hash64(item, seed=7)
        return [(h1 + i * h2) % self.width for i in range(self.depth)]

    def add(self, item: Any, count: int = 1) -> None:
        """Add an item with the given count."""
        for row, col in enumerate(self._positions(item)):
            self.table[row][col] += count
        self._total += count

    def add_all(self, items: Iterable[Any]) -> None:
        """Add multiple items (count 1 each)."""
        for item in items:
            self.add(item)

    def estimate(self, item: Any) -> int:
        """
        Estimate the count of an item.

        Returns the minimum across all rows (most accurate estimate).
        May overcount but never undercount.
        """
        positions = self._positions(item)
        return min(self.table[row][col] for row, col in enumerate(positions))

    @property
    def total(self) -> int:
        """Total count of all items added.
        
        Note: After merge, this reflects max(self.total, other.total) per CRDT
        semantics (register-max). For the combined total across distinct nodes,
        sum the totals before merging.
        """
        return self._total

    def merge(self, other: 'MergeableCMS') -> 'MergeableCMS':
        """
        Merge two Count-Min Sketches via per-cell max.

        This is a natural CRDT operation:
        - Commutative: A.merge(B) == B.merge(A)
        - Associative: A.merge(B).merge(C) == A.merge(B.merge(C))
        - Idempotent: A.merge(A) == A

        Args:
            other: Another MergeableCMS with the same dimensions.

        Returns:
            MergeableCMS: New merged sketch.
        """
        if self.width != other.width or self.depth != other.depth:
            raise ValueError(
                f"Cannot merge CMS with different dimensions: "
                f"({self.width}×{self.depth}) vs ({other.width}×{other.depth})"
            )
        result = MergeableCMS(self.width, self.depth)
        for row in range(self.depth):
            for col in range(self.width):
                result.table[row][col] = max(self.table[row][col], other.table[row][col])
        result._total = max(self._total, other._total)
        return result

    def size_bytes(self) -> int:
        """Approximate memory usage in bytes."""
        return self.width * self.depth * 8  # 8 bytes per int

    def to_dict(self) -> dict:
        """Serialize to dict for wire format."""
        return {
            'type': 'cms',
            'width': self.width,
            'depth': self.depth,
            'table': self.table,
            'total': self._total,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'MergeableCMS':
        """Deserialize from dict."""
        cms = cls(d['width'], d['depth'])
        cms.table = d['table']
        cms._total = d.get('total', 0)
        return cms

    def __repr__(self) -> str:
        return f"MergeableCMS(width={self.width}, depth={self.depth}, total={self._total})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MergeableCMS):
            return NotImplemented
        return (self.width == other.width and
                self.depth == other.depth and
                self.table == other.table)
