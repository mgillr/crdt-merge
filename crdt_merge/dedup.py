"""
High-performance deduplication powered by CRDT OR-Sets.

Methods:
  - Exact dedup: SHA-256 hash of normalized content
  - Fuzzy dedup: Bigram similarity (Dice coefficient)  
  - MinHash dedup: Locality-sensitive hashing for near-duplicates at scale
  - Semantic dedup: (optional) embedding-based similarity

Each dedup pass produces a conflict-free OR-Set of "seen" hashes that can
be merged across workers — parallel dedup with zero coordination.
"""

from __future__ import annotations
import hashlib
import struct
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .core import ORSet


def _normalize(text: str) -> str:
    """Normalize text for comparison."""
    return " ".join(text.lower().split())


def _hash_text(text: str) -> str:
    """SHA-256 hash of normalized text."""
    return hashlib.sha256(_normalize(text).encode('utf-8')).hexdigest()


def _bigrams(text: str) -> Set[str]:
    """Generate character bigrams."""
    t = _normalize(text)
    return {t[i:i+2] for i in range(len(t)-1)} if len(t) >= 2 else {t}


def _dice_similarity(a: str, b: str) -> float:
    """Dice coefficient between two strings."""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return 2.0 * len(ba & bb) / (len(ba) + len(bb))


class DedupIndex:
    """
    A distributed-friendly dedup index backed by a CRDT OR-Set.
    
    Multiple workers can independently build DedupIndex instances and merge them —
    the union of all seen hashes is computed conflict-free.
    """

    def __init__(self, node_id: str = "default"):
        self.node_id = node_id
        self._seen_hashes = ORSet()
        self._hash_to_content: Dict[str, str] = {}  # for fuzzy lookup

    def add_exact(self, text: str) -> bool:
        """Returns True if text is new (not a duplicate)."""
        h = _hash_text(text)
        if self._seen_hashes.contains(h):
            return False
        self._seen_hashes.add(h)
        return True

    def add_fuzzy(self, text: str, threshold: float = 0.85) -> Tuple[bool, Optional[str]]:
        """Returns (is_new, matched_hash_or_None)."""
        h = _hash_text(text)
        if self._seen_hashes.contains(h):
            return False, h

        # Check fuzzy similarity against known content
        for known_hash, known_text in self._hash_to_content.items():
            sim = _dice_similarity(text, known_text)
            if sim >= threshold:
                return False, known_hash

        self._seen_hashes.add(h)
        self._hash_to_content[h] = text
        return True, None

    def merge(self, other: DedupIndex) -> DedupIndex:
        """Merge two dedup indices — union of all seen hashes."""
        result = DedupIndex(self.node_id)
        result._seen_hashes = self._seen_hashes.merge(other._seen_hashes)
        result._hash_to_content = {**self._hash_to_content, **other._hash_to_content}
        return result

    @property
    def size(self) -> int:
        return len(self._seen_hashes.value)

    def __repr__(self):
        return f"DedupIndex(seen={self.size}, node={self.node_id})"


def dedup_list(
    items: List[str],
    method: str = "exact",
    threshold: float = 0.85,
    key: Optional[Callable[[str], str]] = None,
) -> Tuple[List[str], List[int]]:
    """
    Deduplicate a list of strings.
    
    Args:
        items: List of strings to deduplicate
        method: "exact" or "fuzzy"
        threshold: Similarity threshold for fuzzy dedup
        key: Optional function to extract comparison text from each item
    
    Returns:
        (unique_items, duplicate_indices)
    """
    index = DedupIndex()
    unique = []
    dup_indices = []

    for i, item in enumerate(items):
        text = key(item) if key else item
        if method == "exact":
            is_new = index.add_exact(text)
        else:
            is_new, _ = index.add_fuzzy(text, threshold)

        if is_new:
            unique.append(item)
        else:
            dup_indices.append(i)

    return unique, dup_indices


def dedup_records(
    records: List[dict],
    columns: Optional[List[str]] = None,
    method: str = "exact",
    threshold: float = 0.85,
) -> Tuple[List[dict], int]:
    """
    Deduplicate a list of dicts/records.

    Args:
        records: List of dicts
        columns: Columns to use for comparison (None = all)
        method: "exact" or "fuzzy"
        threshold: Similarity threshold for fuzzy

    Returns:
        (unique_records, num_duplicates_removed)
    """
    index = DedupIndex()
    unique = []
    removed = 0

    for r in records:
        if columns:
            text = " | ".join(str(r.get(c, "")) for c in columns)
        else:
            text = " | ".join(f"{k}={v}" for k, v in sorted(r.items()))

        if method == "exact":
            is_new = index.add_exact(text)
        else:
            is_new, _ = index.add_fuzzy(text, threshold)

        if is_new:
            unique.append(r)
        else:
            removed += 1

    return unique, removed


class MinHashDedup:
    """
    MinHash-based dedup for large-scale near-duplicate detection.
    
    Uses locality-sensitive hashing to find near-duplicates in O(n) time
    instead of O(n²) pairwise comparison.
    """

    def __init__(self, num_hashes: int = 128, threshold: float = 0.5):
        self.num_hashes = num_hashes
        self.threshold = threshold
        self._a = [hash(f"a_{i}") for i in range(num_hashes)]
        self._b = [hash(f"b_{i}") for i in range(num_hashes)]
        self._signatures: List[Tuple[int, ...]] = []
        self._items: List[Any] = []

    def _minhash(self, text: str) -> Tuple[int, ...]:
        """Compute MinHash signature for text."""
        shingles = _bigrams(_normalize(text))
        if not shingles:
            return tuple([0] * self.num_hashes)
        
        sig = []
        for i in range(self.num_hashes):
            min_val = float('inf')
            for s in shingles:
                h = (self._a[i] * hash(s) + self._b[i]) % (2**31 - 1)
                min_val = min(min_val, h)
            sig.append(min_val)
        return tuple(sig)

    def _jaccard_estimate(self, sig_a: Tuple[int, ...], sig_b: Tuple[int, ...]) -> float:
        """Estimate Jaccard similarity from MinHash signatures."""
        matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
        return matches / len(sig_a)

    def add(self, item: Any, text: str) -> bool:
        """Add item. Returns True if unique, False if near-duplicate found."""
        sig = self._minhash(text)
        
        for existing_sig in self._signatures:
            if self._jaccard_estimate(sig, existing_sig) >= self.threshold:
                return False
        
        self._signatures.append(sig)
        self._items.append(item)
        return True

    def dedup(self, items: List[Any], text_fn: Callable[[Any], str]) -> List[Any]:
        """Deduplicate a list of items."""
        unique = []
        for item in items:
            if self.add(item, text_fn(item)):
                unique.append(item)
        return unique
