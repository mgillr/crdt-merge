# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Delta integrity resilience — re-anchoring, composition, encoding.

Addresses four expert concerns:

  - Whitfield §11: Quantization error accumulation.  Repeated quantization
    (fp32→int8) introduces O(N×ε_q) error after N composed deltas.
    Solution: re-anchoring protocol that checkpoints full-precision state
    at configurable intervals.

  - Wei §21: Composition operator formalization.  delta(A→B) ∘ delta(B→C)
    = delta(A→C) requires formal spec for overlapping keys, conflicting
    updates, and tombstone handling.
    Solution: formal composition spec with edge case handling.

  - Chen §4: Model-aware delta semantics.  Different parameter types
    (attention QKV, layer norms, embeddings) have different statistical
    properties.  A single encoding scheme is suboptimal.
    Solution: parameter-type-aware encoding selection.

  - Chen §5: Non-commutative merge strategies (SLERP).  CRDT property
    requires commutativity, but some model merging strategies don't commute.
    Solution: commutativity adapter that wraps non-commutative operations
    with deterministic ordering.

Technical effect (UK patent): maintains numerical integrity across
long-running delta composition chains, enabling accurate distributed
model synchronization without precision degradation.
"""

from __future__ import annotations

import enum
import hashlib
import math
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)


# ===========================================================================
# Re-anchoring Protocol (Whitfield §11)
# ===========================================================================

@dataclass(frozen=True)
class AnchorCheckpoint:
    """Full-precision state checkpoint for re-anchoring.

    Attributes
    ----------
    version     : State version at checkpoint.
    state_hash  : SHA-256 of the full-precision state.
    chain_length: Number of deltas since last anchor.
    max_error   : Estimated maximum quantization error.
    """
    version: int
    state_hash: str
    chain_length: int
    max_error: float


class ReanchorPolicy:
    """Policy for triggering full-precision re-anchoring.

    After N composed quantized deltas, the accumulated quantization
    error can be significant.  The re-anchoring policy triggers a
    full-precision checkpoint when:
    1. Chain length exceeds max_chain_length, OR
    2. Estimated error exceeds max_error_bound.

    The re-anchoring replaces the accumulated delta chain with a single
    full-precision delta from the last anchor to the current state.

    Error model:
        After k compositions of int8-quantized deltas, the maximum
        error per parameter is: ε_total <= k × ε_quant
        where ε_quant = scale_factor / 254  (for symmetric int8).

        For fp16 intermediate: ε_quant ~= 3.05e-5
        For int8 intermediate: ε_quant ~= 3.92e-3

    Parameters
    ----------
    max_chain_length :
        Maximum compositions before forced re-anchor (default: 50).
    max_error_bound :
        Maximum allowed accumulated error (default: 0.01).
    quantization_error :
        Per-composition error estimate (default: 3.92e-3 for int8).
    """

    def __init__(
        self,
        *,
        max_chain_length: int = 50,
        max_error_bound: float = 0.01,
        quantization_error: float = 3.92e-3,
    ) -> None:
        self._max_chain = max_chain_length
        self._max_error = max_error_bound
        self._quant_error = quantization_error
        self._chain_length = 0
        self._checkpoints: List[AnchorCheckpoint] = []

    def record_composition(self) -> bool:
        """Record a delta composition.

        Returns True if re-anchoring is needed.
        """
        self._chain_length += 1
        return self.needs_reanchor()

    def needs_reanchor(self) -> bool:
        """Check if re-anchoring is needed."""
        if self._chain_length >= self._max_chain:
            return True
        if self.estimated_error >= self._max_error:
            return True
        return False

    @property
    def estimated_error(self) -> float:
        """Estimated accumulated quantization error."""
        return self._chain_length * self._quant_error

    @property
    def chain_length(self) -> int:
        return self._chain_length

    def checkpoint(self, version: int, state_hash: str) -> AnchorCheckpoint:
        """Record a re-anchoring checkpoint and reset the chain."""
        cp = AnchorCheckpoint(
            version=version,
            state_hash=state_hash,
            chain_length=self._chain_length,
            max_error=self.estimated_error,
        )
        self._checkpoints.append(cp)
        self._chain_length = 0
        return cp

    @property
    def last_checkpoint(self) -> Optional[AnchorCheckpoint]:
        return self._checkpoints[-1] if self._checkpoints else None

    @property
    def total_checkpoints(self) -> int:
        return len(self._checkpoints)

    def __repr__(self) -> str:
        return (
            f"ReanchorPolicy(chain={self._chain_length}/{self._max_chain}, "
            f"error={self.estimated_error:.4f}/{self._max_error})"
        )


# ===========================================================================
# Delta Composition Specification (Wei §21)
# ===========================================================================

class CompositionConflict(enum.Enum):
    """Types of conflicts during delta composition."""
    INSERT_DELETE = "insert_then_delete"  # A→B inserts, B→C deletes
    DELETE_INSERT = "delete_then_insert"  # A→B deletes, B→C inserts
    UPDATE_DELETE = "update_then_delete"  # A→B updates, B→C deletes
    DELETE_UPDATE = "delete_then_update"  # A→B deletes, B→C updates
    DOUBLE_UPDATE = "double_update"       # Both A→B and B→C update same key


@dataclass(frozen=True)
class CompositionResult:
    """Result of composing two deltas.

    Attributes
    ----------
    insertions     : Keys present in C but not in A.
    updates        : Keys present in both A and C with different values.
    deletions      : Keys present in A but not in C.
    conflicts      : Edge cases encountered during composition.
    tombstones     : Keys that were inserted then deleted (no net effect).
    """
    insertions: Dict[str, bytes]
    updates: Dict[str, Tuple[str, bytes]]
    deletions: FrozenSet[str]
    conflicts: List[Tuple[str, CompositionConflict]] = field(default_factory=list)
    tombstones: FrozenSet[str] = frozenset()


class DeltaCompositionSpec:
    """Formal specification for delta composition: δ(A→B) ∘ δ(B→C) = δ(A→C).

    Handles all edge cases:

    1. insert(k) in AB, delete(k) in BC → tombstone (no net effect)
    2. delete(k) in AB, insert(k) in BC → update(k) or insert(k)
    3. update(k) in AB, delete(k) in BC → delete(k) in AC
    4. delete(k) in AB, update(k) in BC → ERROR (key doesn't exist in B)
    5. update(k) in AB, update(k) in BC → update(k, a_old, c_new) in AC
    6. insert(k) in AB, update(k) in BC → insert(k, c_val) in AC
    """

    def compose(
        self,
        ab_insertions: Dict[str, bytes],
        ab_updates: Dict[str, Tuple[str, bytes]],
        ab_deletions: FrozenSet[str],
        bc_insertions: Dict[str, bytes],
        bc_updates: Dict[str, Tuple[str, bytes]],
        bc_deletions: FrozenSet[str],
    ) -> CompositionResult:
        """Compose two deltas into a single delta(A→C).

        Parameters follow the naming convention:
          ab_* = delta from state A to state B
          bc_* = delta from state B to state C
        """
        result_ins: Dict[str, bytes] = {}
        result_upd: Dict[str, Tuple[str, bytes]] = {}
        result_del: Set[str] = set()
        conflicts: List[Tuple[str, CompositionConflict]] = []
        tombstones: Set[str] = set()

        # All keys touched by either delta
        all_keys = (
            set(ab_insertions) | set(ab_updates) | ab_deletions
            | set(bc_insertions) | set(bc_updates) | bc_deletions
        )

        for key in all_keys:
            in_ab_ins = key in ab_insertions
            in_ab_upd = key in ab_updates
            in_ab_del = key in ab_deletions
            in_bc_ins = key in bc_insertions
            in_bc_upd = key in bc_updates
            in_bc_del = key in bc_deletions

            # Case 1: insert in AB, delete in BC → tombstone
            if in_ab_ins and in_bc_del:
                tombstones.add(key)
                conflicts.append((key, CompositionConflict.INSERT_DELETE))
                continue

            # Case 2: delete in AB, insert in BC → insert (key was gone, now back)
            if in_ab_del and in_bc_ins:
                result_ins[key] = bc_insertions[key]
                conflicts.append((key, CompositionConflict.DELETE_INSERT))
                continue

            # Case 3: update in AB, delete in BC → delete
            if in_ab_upd and in_bc_del:
                result_del.add(key)
                conflicts.append((key, CompositionConflict.UPDATE_DELETE))
                continue

            # Case 4: delete in AB, update in BC → conflict (shouldn't happen)
            if in_ab_del and in_bc_upd:
                # Treat as insert of the BC value
                _, bc_new = bc_updates[key]
                result_ins[key] = bc_new
                conflicts.append((key, CompositionConflict.DELETE_UPDATE))
                continue

            # Case 5: update in AB, update in BC → composed update
            if in_ab_upd and in_bc_upd:
                ab_old, _ = ab_updates[key]
                _, bc_new = bc_updates[key]
                result_upd[key] = (ab_old, bc_new)
                conflicts.append((key, CompositionConflict.DOUBLE_UPDATE))
                continue

            # Case 6: insert in AB, update in BC → insert with BC value
            if in_ab_ins and in_bc_upd:
                _, bc_new = bc_updates[key]
                result_ins[key] = bc_new
                continue

            # Simple cases: only in one delta
            if in_ab_ins and not in_bc_del and not in_bc_upd:
                result_ins[key] = ab_insertions[key]
            elif in_ab_upd and not in_bc_del and not in_bc_upd:
                result_upd[key] = ab_updates[key]
            elif in_ab_del and not in_bc_ins and not in_bc_upd:
                result_del.add(key)
            elif in_bc_ins and not in_ab_del and not in_ab_upd:
                result_ins[key] = bc_insertions[key]
            elif in_bc_upd and not in_ab_del and not in_ab_upd:
                result_upd[key] = bc_updates[key]
            elif in_bc_del and not in_ab_ins and not in_ab_upd:
                result_del.add(key)

        return CompositionResult(
            insertions=result_ins,
            updates=result_upd,
            deletions=frozenset(result_del),
            conflicts=conflicts,
            tombstones=frozenset(tombstones),
        )


# ===========================================================================
# Parameter-Type-Aware Encoding (Chen §4)
# ===========================================================================

class ParameterType(enum.Enum):
    """Neural network parameter types with distinct encoding strategies."""
    ATTENTION_QKV = "attention_qkv"       # Attention query/key/value matrices
    ATTENTION_OUTPUT = "attention_output"  # Attention output projection
    LAYER_NORM = "layer_norm"             # Layer normalization params
    EMBEDDING = "embedding"               # Token/position embeddings
    MLP_GATE = "mlp_gate"                 # MLP gate projections
    MLP_UP = "mlp_up"                     # MLP up projections
    MLP_DOWN = "mlp_down"                 # MLP down projections
    CLASSIFIER = "classifier"             # Classification head
    GENERIC = "generic"                   # Unknown/other parameters


@dataclass(frozen=True)
class EncodingRecommendation:
    """Recommended encoding for a parameter type.

    Attributes
    ----------
    encoding    : Encoding strategy ("sparse", "quantized", "raw").
    bits        : Quantization bits (8, 16, 32).
    threshold   : Sparsity threshold for sparse encoding.
    reason      : Why this encoding was chosen.
    """
    encoding: str
    bits: int = 8
    threshold: float = 1e-6
    reason: str = ""


class ParameterTypeEncoder:
    """Parameter-type-aware encoding selection.

    Different neural network parameter types have different statistical
    properties.  This encoder selects the optimal encoding strategy
    based on the parameter type:

    - Attention QKV: Sparse COO (typically 95%+ unchanged during fine-tune)
    - Layer Norm: Raw fp32 (small parameters, high sensitivity)
    - Embeddings: Top-K (sparse token-level changes)
    - MLP weights: Quantized int8 (dense, tolerant of quantization)
    - Classifier: Raw fp32 (critical, low parameter count)

    Parameters
    ----------
    type_patterns :
        Dict mapping key patterns to ParameterType.
        E.g., {"*.q_proj.*": ParameterType.ATTENTION_QKV}
    """

    # Default encoding recommendations per type
    DEFAULT_ENCODINGS: Dict[ParameterType, EncodingRecommendation] = {
        ParameterType.ATTENTION_QKV: EncodingRecommendation(
            encoding="sparse", threshold=1e-6,
            reason="95%+ unchanged during fine-tune; COO is optimal",
        ),
        ParameterType.ATTENTION_OUTPUT: EncodingRecommendation(
            encoding="sparse", threshold=1e-6,
            reason="Similar sparsity profile to QKV",
        ),
        ParameterType.LAYER_NORM: EncodingRecommendation(
            encoding="raw", bits=32,
            reason="Small param count, high sensitivity to quantization",
        ),
        ParameterType.EMBEDDING: EncodingRecommendation(
            encoding="sparse", threshold=1e-5,
            reason="Token-level sparsity; most embeddings unchanged",
        ),
        ParameterType.MLP_GATE: EncodingRecommendation(
            encoding="quantized", bits=8,
            reason="Dense changes, tolerant of int8 quantization",
        ),
        ParameterType.MLP_UP: EncodingRecommendation(
            encoding="quantized", bits=8,
            reason="Dense changes, tolerant of int8 quantization",
        ),
        ParameterType.MLP_DOWN: EncodingRecommendation(
            encoding="quantized", bits=8,
            reason="Dense changes, tolerant of int8 quantization",
        ),
        ParameterType.CLASSIFIER: EncodingRecommendation(
            encoding="raw", bits=32,
            reason="Critical layer, small param count, no quantization",
        ),
        ParameterType.GENERIC: EncodingRecommendation(
            encoding="quantized", bits=8,
            reason="Default: int8 quantization for unknown types",
        ),
    }

    # Default key pattern → type mappings
    DEFAULT_PATTERNS: Dict[str, ParameterType] = {
        "q_proj": ParameterType.ATTENTION_QKV,
        "k_proj": ParameterType.ATTENTION_QKV,
        "v_proj": ParameterType.ATTENTION_QKV,
        "o_proj": ParameterType.ATTENTION_OUTPUT,
        "out_proj": ParameterType.ATTENTION_OUTPUT,
        "layer_norm": ParameterType.LAYER_NORM,
        "layernorm": ParameterType.LAYER_NORM,
        "ln_": ParameterType.LAYER_NORM,
        "embed": ParameterType.EMBEDDING,
        "wte": ParameterType.EMBEDDING,
        "wpe": ParameterType.EMBEDDING,
        "gate_proj": ParameterType.MLP_GATE,
        "up_proj": ParameterType.MLP_UP,
        "down_proj": ParameterType.MLP_DOWN,
        "fc1": ParameterType.MLP_UP,
        "fc2": ParameterType.MLP_DOWN,
        "classifier": ParameterType.CLASSIFIER,
        "lm_head": ParameterType.CLASSIFIER,
    }

    def __init__(
        self,
        type_patterns: Optional[Dict[str, ParameterType]] = None,
        custom_encodings: Optional[Dict[ParameterType, EncodingRecommendation]] = None,
    ) -> None:
        self._patterns = dict(self.DEFAULT_PATTERNS)
        if type_patterns:
            self._patterns.update(type_patterns)
        self._encodings = dict(self.DEFAULT_ENCODINGS)
        if custom_encodings:
            self._encodings.update(custom_encodings)

    def classify(self, key: str) -> ParameterType:
        """Classify a parameter key into its type."""
        key_lower = key.lower()
        for pattern, ptype in self._patterns.items():
            if pattern.lower() in key_lower:
                return ptype
        return ParameterType.GENERIC

    def recommend(self, key: str) -> EncodingRecommendation:
        """Get the recommended encoding for a parameter key."""
        ptype = self.classify(key)
        return self._encodings.get(ptype, self.DEFAULT_ENCODINGS[ParameterType.GENERIC])

    def batch_recommend(
        self,
        keys: Sequence[str],
    ) -> Dict[str, EncodingRecommendation]:
        """Get encoding recommendations for a batch of keys."""
        return {key: self.recommend(key) for key in keys}

    def register_pattern(self, pattern: str, ptype: ParameterType) -> None:
        """Register a custom key pattern → type mapping."""
        self._patterns[pattern] = ptype

    def __repr__(self) -> str:
        return f"ParameterTypeEncoder(patterns={len(self._patterns)})"


# ===========================================================================
# Commutativity Adapter (Chen §5)
# ===========================================================================

class CommutativityAdapter:
    """Wrap non-commutative merge operations for CRDT compatibility.

    Some model merging strategies (SLERP, TIES) are order-dependent.
    The CRDT property requires commutativity: merge(A, B) = merge(B, A).

    This adapter wraps non-commutative operations with a deterministic
    ordering function: inputs are sorted by a canonical key (peer_id,
    then timestamp, then content hash) before merging.

    The result is commutative by construction: regardless of the order
    two replicas receive the operands, they produce the same sorted
    order and thus the same merge result.

    Parameters
    ----------
    ordering_key :
        Function that maps (peer_id, timestamp, value) to a sortable key.
        Default: lexicographic on (peer_id, timestamp).
    """

    def __init__(
        self,
        ordering_key: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._ordering = ordering_key or self._default_ordering

    @staticmethod
    def _default_ordering(
        peer_id: str,
        timestamp: float,
        value_hash: str,
    ) -> Tuple[str, float, str]:
        """Default deterministic ordering: peer_id, timestamp, value hash."""
        return (peer_id, timestamp, value_hash)

    def canonicalize(
        self,
        entries: Sequence[Tuple[str, float, Any]],
    ) -> List[Tuple[str, float, Any]]:
        """Sort entries into canonical order for deterministic merging.

        Parameters
        ----------
        entries :
            List of (peer_id, timestamp, value) tuples.

        Returns
        -------
        Sorted list in canonical order.
        """
        def sort_key(entry: Tuple[str, float, Any]) -> Any:
            peer_id, timestamp, value = entry
            # Hash the value for deterministic ordering
            if isinstance(value, bytes):
                vh = hashlib.sha256(value).hexdigest()
            else:
                vh = hashlib.sha256(str(value).encode()).hexdigest()
            return self._ordering(peer_id, timestamp, vh)

        return sorted(entries, key=sort_key)

    def commutative_merge(
        self,
        entries: Sequence[Tuple[str, float, Any]],
        merge_fn: Callable[[Sequence[Any]], Any],
    ) -> Any:
        """Apply a non-commutative merge function commutatively.

        Steps:
        1. Canonicalize the input order.
        2. Extract values in canonical order.
        3. Apply merge_fn to the ordered values.

        Because the ordering is deterministic, the result is the same
        regardless of which replica applies the merge first.
        """
        canonical = self.canonicalize(entries)
        values = [entry[2] for entry in canonical]
        return merge_fn(values)

    def is_commutative_safe(
        self,
        entries: Sequence[Tuple[str, float, Any]],
        merge_fn: Callable[[Sequence[Any]], Any],
    ) -> bool:
        """Test if a merge function produces the same result in any order.

        Checks forward and reverse order — if results match, the function
        is commutative for this input (or the canonicalization fixed it).
        """
        canonical = self.canonicalize(entries)
        values = [e[2] for e in canonical]

        result_forward = merge_fn(values)
        result_reverse = merge_fn(list(reversed(values)))

        return str(result_forward) == str(result_reverse)

    def __repr__(self) -> str:
        return "CommutativityAdapter()"
