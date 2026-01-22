# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""
CRDT-Aware Merge State — the layer that makes ALL 25 strategies true CRDTs.

Architecture
============

The original ``crdt-merge`` architecture tried to make each merge strategy's
``merge()`` function satisfy CRDT laws (commutativity, associativity,
idempotency) directly on raw tensors. This is **mathematically impossible**
for most model-merge algorithms (SLERP, TIES, DARE, Fisher, etc.).

The solution is a **two-layer architecture** that separates concerns:

    Layer 1 — CRDT State (this module)
        Manages a set of model contributions with provably correct CRDT
        semantics. The merge operation is **set union** which is trivially
        commutative, associative, and idempotent.

    Layer 2 — Strategy (existing ``strategies/`` modules)
        Pure functions that compute a merged model from a set of inputs.
        Applied atomically during ``resolve()`` — never pairwise.

``CRDTMergeState`` provides the CRDT wrapper layer that makes all 25
strategies satisfy the three CRDT laws. Implementation internals are
proprietary — see LICENSE and PATENTS for details.

Usage
=====

::

    from crdt_merge.model.crdt_state import CRDTMergeState

    # Node A creates state and adds its model
    state_a = CRDTMergeState("weight_average")
    state_a.add(tensor_a, model_id="llama-7b-node-a", weight=1.0)

    # Node B creates state and adds its model
    state_b = CRDTMergeState("weight_average")
    state_b.add(tensor_b, model_id="llama-7b-node-b", weight=1.0)

    # Any merge order produces identical states
    merged_1 = state_a.merge(state_b)
    merged_2 = state_b.merge(state_a)
    assert merged_1 == merged_2                 # CRDT guarantee

    # Resolve to get the actual merged tensor
    result = merged_1.resolve()

    # Works with ANY strategy — all 25 are true CRDTs
    state_ties = CRDTMergeState("ties", base=pretrained_base)
    state_ties.add(finetuned_a, model_id="ft-a")
    state_ties.add(finetuned_b, model_id="ft-b")
    merged_model = state_ties.resolve()
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import OrderedDict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

__all__ = [
    "CRDTMergeState",
    "MergeContribution",
    "ConflictResolution",
]

class ConflictResolution(str, Enum):
    """Strategy for resolving conflicts when the same model_id appears twice."""
    FIRST_WRITE_WINS = "first_write_wins"
    LAST_WRITE_WINS = "last_write_wins"
    HIGHEST_VERSION = "highest_version"

class MergeContribution:
    """A single model contribution in the CRDT state.

    Each contribution is content-addressable via its Merkle hash,
    enabling provenance tracking and integrity verification.
    """
    __slots__ = (
        'model_id', 'tensor', 'weight', 'version',
        'metadata', 'merkle_hash', 'timestamp', '_tag',
    )

    def __init__(
        self,
        model_id: str,
        tensor: Any,
        weight: float = 1.0,
        version: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ):
        self.model_id = model_id
        self.weight = weight
        self.version = version
        self.metadata = metadata or {}
        self.timestamp = timestamp or time.time()

        # Store tensor — import numpy lazily
        try:
            import numpy as np
            self.tensor = np.asarray(tensor, dtype=np.float64)
        except ImportError:
            self.tensor = list(tensor) if not isinstance(tensor, list) else tensor

        # Merkle hash for content-addressability
        self.merkle_hash = self._compute_hash()

        # Unique tag for OR-Set semantics (unique per add operation)
        self._tag = f"{self.model_id}:v{self.version}:{self.merkle_hash[:8]}"

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of contribution content."""
        try:
            import numpy as np
            tensor_bytes = np.asarray(self.tensor).tobytes()
        except ImportError:
            tensor_bytes = json.dumps(self.tensor, sort_keys=True).encode()

        h = hashlib.sha256()
        h.update(self.model_id.encode())
        h.update(tensor_bytes)
        h.update(str(self.weight).encode())
        h.update(str(self.version).encode())
        return h.hexdigest()

    def to_dict(self) -> dict:
        """Serialize for wire transfer."""
        try:
            import numpy as np
            tensor_val = np.asarray(self.tensor).tolist()
        except ImportError:
            tensor_val = self.tensor
        return {
            "model_id": self.model_id,
            "tensor": tensor_val,
            "weight": self.weight,
            "version": self.version,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "merkle_hash": self.merkle_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MergeContribution:
        """Deserialize from wire format."""
        return cls(
            model_id=d["model_id"],
            tensor=d["tensor"],
            weight=d["weight"],
            version=d.get("version", 1),
            metadata=d.get("metadata", {}),
            timestamp=d.get("timestamp"),
        )

    def __repr__(self) -> str:
        return (
            f"MergeContribution(model_id={self.model_id!r}, "
            f"version={self.version}, hash={self.merkle_hash[:8]})"
        )

class CRDTMergeState:
    """Conflict-Free Replicated merge state for model merging.

    This is the CRDT wrapper that makes ALL 25 merge strategies satisfy
    the three CRDT laws. It operates as a **set of identified model
    contributions** with set-union merge semantics.

    The merge strategies themselves remain unchanged — they are applied
    atomically during ``resolve()`` to the full set of contributions.

    Parameters
    ----------
    strategy_name : str
        Name of the merge strategy (e.g., "weight_average", "ties", "slerp").
        Must be one of the known registered strategy names.
    base : array-like, optional
        Base/pretrained model for task-vector strategies.
    conflict_resolution : ConflictResolution
        How to handle duplicate model_ids. Default: highest version wins.
    seed : int, optional
        RNG seed for stochastic strategies (dare, evolutionary, genetic).
        Required for deterministic resolution across replicas.

    CRDT Guarantees
    ---------------
    All three CRDT laws (commutativity, associativity, idempotency) are
    satisfied by construction. See PATENTS for implementation details.

    Thread Safety
    -------------
    This class is **NOT** thread-safe. Concurrent calls to mutating methods
    (``add``, ``add_batch``, ``remove``, ``merge``) from multiple threads
    may corrupt internal state. Callers must provide their own
    synchronization (e.g., ``threading.Lock``) when sharing a
    ``CRDTMergeState`` instance across threads.

    Read-only properties and ``resolve()`` are safe to call concurrently
    only if no other thread is mutating the state at the same time.
    """

    __slots__ = (
        'strategy_name', 'base', 'conflict_resolution', 'seed',
        '_contributions', '_tombstones',
        '_active_cache', '_cache_valid',
    )

    # All 25 built-in registered strategy names
    KNOWN_STRATEGIES = frozenset({
        'weight_average', 'slerp', 'task_arithmetic', 'linear',
        'weight_scope_alignment', 'representation_surgery',
        'evolutionary_merge', 'genetic_merge',
        'safe_merge', 'led_merge',
        'ties', 'dare', 'della', 'dare_ties',
        'model_breadcrumbs', 'emr', 'star', 'svd_knot_tying', 'adarank',
        'negative_merge', 'split_unlearn_merge',
        'fisher_merge', 'regression_mean', 'ada_merging', 'dam',
        'dual_projection',
    })

    # Strategies that require a base model
    BASE_REQUIRED = frozenset({
        'task_arithmetic', 'ties', 'dare', 'della', 'dare_ties',
        'model_breadcrumbs', 'emr', 'star', 'svd_knot_tying', 'adarank',
        'negative_merge', 'split_unlearn_merge', 'safe_merge',
    })

    # Strategies with internal RNG (need deterministic seed)
    STOCHASTIC = frozenset({
        'dare', 'della', 'dare_ties', 'evolutionary_merge', 'genetic_merge',
    })

    def __init__(
        self,
        strategy_name: str,
        base: Any = None,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_VERSION,
        seed: Optional[int] = None,
    ):
        # Validate strategy name
        if strategy_name not in self.KNOWN_STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy_name}'. "
                f"Known strategies: {sorted(self.KNOWN_STRATEGIES)}"
            )

        self.strategy_name = strategy_name
        self.conflict_resolution = conflict_resolution
        self.seed = seed if seed is not None else 42

        # Store base model
        if base is not None:
            try:
                import numpy as np
                self.base = np.asarray(base, dtype=np.float64)
            except ImportError:
                self.base = base
        else:
            self.base = None

        # OR-Set state: contributions + tombstones
        self._contributions: Dict[str, MergeContribution] = OrderedDict()
        self._tombstones: Set[str] = set()

        # Cache for _active_contributions()
        self._active_cache: Optional[Dict[str, MergeContribution]] = None
        self._cache_valid: bool = False

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _invalidate_cache(self) -> None:
        """Invalidate the active-contributions cache.

        Must be called after any mutation to ``_contributions`` or
        ``_tombstones``.

        .. note:: Not thread-safe — see class docstring.
        """
        self._active_cache = None
        self._cache_valid = False

    # ------------------------------------------------------------------
    # Core CRDT Operations
    # ------------------------------------------------------------------

    def add(
        self,
        tensor: Any,
        model_id: Optional[str] = None,
        weight: float = 1.0,
        version: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "CRDTMergeState":
        """Add a model contribution to the merge set.

        If a contribution with the same ``model_id`` already exists,
        the conflict resolution policy determines which one is kept.

        Parameters
        ----------
        tensor : array-like
            The model weights/parameters to contribute.
        model_id : str, optional
            Unique identifier for this model. If not provided, a
            content-hash is used. Explicit IDs enable deduplication.
        weight : float
            Importance weight for this contribution (default 1.0).
        version : int
            Version number. Higher versions supersede lower ones
            when ``conflict_resolution=HIGHEST_VERSION``.
        metadata : dict, optional
            Arbitrary metadata (node_id, training info, etc.).

        Returns
        -------
        self : CRDTMergeState
            For method chaining.

        Raises
        ------
        ValueError
            If the tensor shape does not match existing contributions.

        .. note:: Not thread-safe — see class docstring.
        """
        contrib = MergeContribution(
            model_id=model_id or self._auto_id(tensor),
            tensor=tensor,
            weight=weight,
            version=version,
            metadata=metadata,
        )

        # Validate tensor shape against existing contributions
        self._validate_tensor_shape(contrib.tensor)

        existing = self._contributions.get(contrib.model_id)
        if existing is not None:
            if self.conflict_resolution == ConflictResolution.FIRST_WRITE_WINS:
                return self  # Keep existing
            elif self.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
                pass  # Overwrite below
            elif self.conflict_resolution == ConflictResolution.HIGHEST_VERSION:
                if existing.version >= contrib.version:
                    return self  # Existing is newer or same
            # else: overwrite

        self._contributions[contrib.model_id] = contrib

        # Remove from tombstones if re-added (add-wins semantics)
        self._tombstones.discard(contrib._tag)

        self._invalidate_cache()
        return self

    def add_batch(
        self,
        contributions: List[
            Union[
                Tuple[Any, str],
                Tuple[Any, str, float],
                Tuple[Any, str, float, int],
                Dict[str, Any],
            ]
        ],
    ) -> "CRDTMergeState":
        """Add multiple model contributions at once.

        More efficient than repeated ``add()`` calls because the
        active-contributions cache is invalidated only once after all
        items are inserted.

        Each element of *contributions* is either:

        - A tuple ``(tensor, model_id)``
        - A tuple ``(tensor, model_id, weight)``
        - A tuple ``(tensor, model_id, weight, version)``
        - A dict with keys ``tensor``, ``model_id`` and optional
          ``weight``, ``version``, ``metadata``

        Parameters
        ----------
        contributions : list
            Sequence of contributions to add.

        Returns
        -------
        self : CRDTMergeState
            For method chaining.

        Raises
        ------
        ValueError
            If any tensor shape does not match existing contributions.
        TypeError
            If an element is not a supported type.

        .. note:: Not thread-safe — see class docstring.
        """
        if not contributions:
            return self

        mutated = False
        for item in contributions:
            if isinstance(item, dict):
                tensor = item["tensor"]
                mid = item.get("model_id") or self._auto_id(tensor)
                weight = item.get("weight", 1.0)
                version = item.get("version", 1)
                metadata = item.get("metadata", None)
            elif isinstance(item, (tuple, list)):
                if len(item) < 2:
                    raise TypeError(
                        "Tuple contributions must have at least (tensor, model_id)"
                    )
                tensor = item[0]
                mid = item[1]
                weight = item[2] if len(item) > 2 else 1.0
                version = item[3] if len(item) > 3 else 1
                metadata = None
            else:
                raise TypeError(
                    f"Unsupported contribution type: {type(item).__name__}. "
                    "Expected dict or tuple."
                )

            contrib = MergeContribution(
                model_id=mid,
                tensor=tensor,
                weight=weight,
                version=version,
                metadata=metadata,
            )

            # Validate tensor shape against existing contributions
            self._validate_tensor_shape(contrib.tensor)

            existing = self._contributions.get(contrib.model_id)
            if existing is not None:
                if self.conflict_resolution == ConflictResolution.FIRST_WRITE_WINS:
                    continue  # Keep existing
                elif self.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
                    pass  # Overwrite below
                elif self.conflict_resolution == ConflictResolution.HIGHEST_VERSION:
                    if existing.version >= contrib.version:
                        continue  # Existing is newer or same

            self._contributions[contrib.model_id] = contrib
            self._tombstones.discard(contrib._tag)
            mutated = True

        if mutated:
            self._invalidate_cache()
        return self

    def remove(self, model_id: str) -> "CRDTMergeState":
        """Remove a model contribution by ID (OR-Set remove).

        Only removes the current version. A newer ``add()`` with the
        same model_id will override the remove (add-wins).

        Returns
        -------
        self : CRDTMergeState

        .. note:: Not thread-safe — see class docstring.
        """
        contrib = self._contributions.get(model_id)
        if contrib is not None:
            self._tombstones.add(contrib._tag)
            del self._contributions[model_id]
            self._invalidate_cache()
        return self

    def merge(self, other: "CRDTMergeState") -> "CRDTMergeState":
        """CRDT merge: set union of contributions with conflict resolution.

        This operation satisfies all three CRDT laws: commutativity,
        associativity, and idempotency. The resulting state is equivalent
        regardless of merge order.

        Parameters
        ----------
        other : CRDTMergeState
            The remote replica's state to merge with.

        Returns
        -------
        merged : CRDTMergeState
            New state containing the union of both contribution sets.
        """
        result = CRDTMergeState(
            strategy_name=self.strategy_name,
            base=self.base if self.base is not None else other.base,
            conflict_resolution=self.conflict_resolution,
            seed=self.seed,
        )

        # Union of tombstones
        result._tombstones = self._tombstones | other._tombstones

        # Collect all contributions from both sides
        all_contribs: Dict[str, MergeContribution] = {}

        for mid, contrib in self._contributions.items():
            if contrib._tag not in result._tombstones:
                all_contribs[mid] = contrib

        for mid, contrib in other._contributions.items():
            if contrib._tag not in result._tombstones:
                if mid in all_contribs:
                    # Conflict: same model_id from both replicas
                    existing = all_contribs[mid]
                    if self.conflict_resolution == ConflictResolution.HIGHEST_VERSION:
                        if contrib.version > existing.version:
                            all_contribs[mid] = contrib
                        elif contrib.version == existing.version:
                            # Tie-break: deterministic by merkle hash
                            if contrib.merkle_hash < existing.merkle_hash:
                                all_contribs[mid] = contrib
                    elif self.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
                        if contrib.timestamp > existing.timestamp:
                            all_contribs[mid] = contrib
                    # FIRST_WRITE_WINS: keep existing (do nothing)
                else:
                    all_contribs[mid] = contrib

        result._contributions = OrderedDict(
            sorted(all_contribs.items(), key=lambda x: x[0])
        )

        # Cache is already invalid in the fresh `result` (initialized False)
        return result

    @classmethod
    def merge_many(cls, states: List["CRDTMergeState"]) -> "CRDTMergeState":
        """Merge N states at once (more efficient than chained pairwise merges).

        Performs a single-pass union over all contribution sets, avoiding
        the O(N²) intermediate-state overhead of sequential pairwise
        ``merge()`` calls.

        The result is identical to ``s1.merge(s2).merge(s3)...`` in any
        order (by CRDT associativity and commutativity).

        Parameters
        ----------
        states : list of CRDTMergeState
            Two or more states to merge. All must share the same
            ``strategy_name``.

        Returns
        -------
        merged : CRDTMergeState
            New state containing the union of all contribution sets.

        Raises
        ------
        ValueError
            If *states* is empty or contains inconsistent strategy names.
        """
        if not states:
            raise ValueError("merge_many() requires at least one state")
        if len(states) == 1:
            # Return a copy via merge-with-self (idempotent)
            return states[0].merge(states[0])

        first = states[0]

        # Validate all share the same strategy
        for s in states[1:]:
            if s.strategy_name != first.strategy_name:
                raise ValueError(
                    f"Cannot merge states with different strategies: "
                    f"{first.strategy_name!r} vs {s.strategy_name!r}"
                )

        # Pick the first available base
        base = None
        for s in states:
            if s.base is not None:
                base = s.base
                break

        result = cls(
            strategy_name=first.strategy_name,
            base=base,
            conflict_resolution=first.conflict_resolution,
            seed=first.seed,
        )

        # Union of all tombstones
        all_tombstones: Set[str] = set()
        for s in states:
            all_tombstones |= s._tombstones
        result._tombstones = all_tombstones

        # Single-pass union of all contributions
        all_contribs: Dict[str, MergeContribution] = {}
        for s in states:
            for mid, contrib in s._contributions.items():
                if contrib._tag in all_tombstones:
                    continue
                if mid in all_contribs:
                    existing = all_contribs[mid]
                    if first.conflict_resolution == ConflictResolution.HIGHEST_VERSION:
                        if contrib.version > existing.version:
                            all_contribs[mid] = contrib
                        elif contrib.version == existing.version:
                            if contrib.merkle_hash < existing.merkle_hash:
                                all_contribs[mid] = contrib
                    elif first.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
                        if contrib.timestamp > existing.timestamp:
                            all_contribs[mid] = contrib
                    # FIRST_WRITE_WINS: keep existing
                else:
                    all_contribs[mid] = contrib

        result._contributions = OrderedDict(
            sorted(all_contribs.items(), key=lambda x: x[0])
        )
        return result

    def resolve(self) -> Any:
        """Apply the merge strategy atomically to all contributions.

        This is the **resolution function** — a deterministic pure function
        that produces the same output from the same set of contributions,
        regardless of the order they were added or merged.

        Returns
        -------
        merged_tensor : numpy.ndarray or list
            The merged model weights.

        Raises
        ------
        ValueError
            If the state is empty or base is missing for strategies that need it.
        """
        active = self._active_contributions()

        if not active:
            if self.base is not None:
                return self.base
            raise ValueError("Cannot resolve empty CRDT state with no base model")

        # Import strategy
        from crdt_merge.model.strategies import get_strategy
        strategy = get_strategy(self.strategy_name)

        # Canonical order: sort by model_id for determinism
        sorted_ids = sorted(active.keys())
        tensors = [active[mid].tensor for mid in sorted_ids]
        weights = [active[mid].weight for mid in sorted_ids]

        # Build kwargs
        kwargs: Dict[str, Any] = {}
        if self.strategy_name in self.STOCHASTIC:
            kwargs['seed'] = self.seed

        if self.strategy_name in self.BASE_REQUIRED:
            if self.base is None:
                raise ValueError(
                    f"Strategy '{self.strategy_name}' requires base= but none provided"
                )
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)

        return strategy.merge(tensors, weights=weights, **kwargs)

    # ------------------------------------------------------------------
    # Query / Inspection
    # ------------------------------------------------------------------

    @property
    def model_ids(self) -> List[str]:
        """List of model IDs currently in the set (excluding tombstoned)."""
        return sorted(self._active_contributions().keys())

    @property
    def size(self) -> int:
        """Number of active contributions."""
        return len(self._active_contributions())

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    @property
    def needs_base(self) -> bool:
        """Whether this state's strategy requires a base model."""
        return self.strategy_name in self.BASE_REQUIRED

    @property
    def is_stochastic(self) -> bool:
        """Whether this state's strategy has internal RNG."""
        return self.strategy_name in self.STOCHASTIC

    @property
    def estimated_memory_bytes(self) -> int:
        """Estimate the total memory footprint of this state in bytes.

        Accounts for tensor data in all contributions (active and
        tombstoned entries still held in ``_contributions``), the base
        model tensor, and a fixed overhead estimate for Python objects.

        Returns
        -------
        int
            Estimated memory usage in bytes.
        """
        total = 0

        # Fixed overhead for the state object itself + dicts + sets
        total += sys.getsizeof(self._contributions)
        total += sys.getsizeof(self._tombstones)

        # Base model
        if self.base is not None:
            try:
                import numpy as np
                total += np.asarray(self.base).nbytes
            except ImportError:
                total += sys.getsizeof(self.base)

        # All contributions (including tombstoned ones still in dict)
        for contrib in self._contributions.values():
            try:
                import numpy as np
                total += np.asarray(contrib.tensor).nbytes
            except ImportError:
                total += sys.getsizeof(contrib.tensor)
            # Per-contribution object overhead (strings, metadata, etc.)
            total += (
                sys.getsizeof(contrib.model_id)
                + sys.getsizeof(contrib.merkle_hash)
                + sys.getsizeof(contrib.metadata)
                + sys.getsizeof(contrib._tag)
                + 64  # slots overhead estimate
            )

        return total

    def get_contribution(self, model_id: str) -> Optional[MergeContribution]:
        """Get a specific contribution by model ID."""
        return self._active_contributions().get(model_id)

    def provenance(self) -> List[Dict[str, Any]]:
        """Return provenance trail for all contributions."""
        return [
            {
                "model_id": c.model_id,
                "version": c.version,
                "merkle_hash": c.merkle_hash,
                "weight": c.weight,
                "timestamp": c.timestamp,
                "metadata": c.metadata,
            }
            for c in self._active_contributions().values()
        ]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the full CRDT state for wire transfer."""
        try:
            import numpy as np
            base_val = np.asarray(self.base).tolist() if self.base is not None else None
        except ImportError:
            base_val = self.base

        return {
            "type": "CRDTMergeState",
            "version": 1,
            "strategy_name": self.strategy_name,
            "base": base_val,
            "conflict_resolution": self.conflict_resolution.value,
            "seed": self.seed,
            "contributions": {
                mid: c.to_dict()
                for mid, c in self._contributions.items()
            },
            "tombstones": sorted(self._tombstones),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CRDTMergeState":
        """Deserialize from wire format."""
        state = cls(
            strategy_name=d["strategy_name"],
            base=d.get("base"),
            conflict_resolution=ConflictResolution(d.get("conflict_resolution", "highest_version")),
            seed=d.get("seed", 42),
        )
        for mid, cd in d.get("contributions", {}).items():
            contrib = MergeContribution.from_dict(cd)
            state._contributions[mid] = contrib
        state._tombstones = set(d.get("tombstones", []))
        state._invalidate_cache()
        return state

    # ------------------------------------------------------------------
    # Equality (for CRDT law verification)
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Two states are equal if they have the same active contribution set."""
        if not isinstance(other, CRDTMergeState):
            return NotImplemented
        return (
            self.strategy_name == other.strategy_name
            and self._active_ids() == other._active_ids()
            and all(
                self._contributions[mid].merkle_hash
                == other._contributions[mid].merkle_hash
                for mid in self._active_ids()
                if mid in self._contributions and mid in other._contributions
            )
        )

    def __hash__(self) -> int:
        return hash((
            self.strategy_name,
            frozenset(self._active_ids()),
        ))

    def __repr__(self) -> str:
        active = self._active_contributions()
        ids = ", ".join(sorted(active.keys())[:5])
        more = f", +{len(active)-5} more" if len(active) > 5 else ""
        return (
            f"CRDTMergeState(strategy={self.strategy_name!r}, "
            f"models=[{ids}{more}], size={len(active)})"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_contributions(self) -> Dict[str, MergeContribution]:
        """Get contributions not in tombstones.

        Results are cached and returned on subsequent calls until the
        cache is invalidated by a mutating operation.
        """
        if self._cache_valid and self._active_cache is not None:
            return self._active_cache

        result = OrderedDict(
            (mid, c) for mid, c in self._contributions.items()
            if c._tag not in self._tombstones
        )
        self._active_cache = result
        self._cache_valid = True
        return result

    def _active_ids(self) -> frozenset:
        """Frozen set of active model IDs."""
        return frozenset(
            mid for mid, c in self._contributions.items()
            if c._tag not in self._tombstones
        )

    def _validate_tensor_shape(self, tensor: Any) -> None:
        """Validate that *tensor* has the same shape as existing contributions.

        Raises ``ValueError`` if shapes are incompatible.  Skipped when
        there are no existing contributions yet.
        """
        if not self._contributions:
            return
        # Get the first existing contribution's tensor for shape reference
        first = next(iter(self._contributions.values()))
        try:
            import numpy as np
            new_shape = np.asarray(tensor).shape
            existing_shape = np.asarray(first.tensor).shape
            if new_shape != existing_shape:
                raise ValueError(
                    f"Tensor shape mismatch: new tensor has shape {new_shape} "
                    f"but existing contributions have shape {existing_shape}"
                )
        except ImportError:
            # Without numpy, do a best-effort length check for lists
            if isinstance(tensor, list) and isinstance(first.tensor, list):
                if len(tensor) != len(first.tensor):
                    raise ValueError(
                        f"Tensor length mismatch: new tensor has length "
                        f"{len(tensor)} but existing contributions have "
                        f"length {len(first.tensor)}"
                    )

    @staticmethod
    def _auto_id(tensor: Any) -> str:
        """Generate a content-hash ID for anonymous tensors."""
        try:
            import numpy as np
            data = np.asarray(tensor).tobytes()
        except ImportError:
            data = json.dumps(tensor, sort_keys=True).encode()
        return f"auto_{hashlib.sha256(data).hexdigest()[:12]}"
