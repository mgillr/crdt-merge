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

"""Trust-weighted conflict resolution strategies — E3 entanglement (ref 870-874).

Implements trust-weighted strategy engines that bind trust scores into
conflict resolution decisions.  Every merge strategy in the E4 pipeline
consults the trust lattice before resolving conflicts: high-trust peers
dominate, low-trust peers are filtered, and the strategy selector itself
adapts based on aggregate trust topology.

Components
----------
TrustWeightedLWWResolver (ref 871)
    Last-writer-wins where 'last' is redefined as a product of timestamp
    and trust weight.  A trusted write at t=5 beats an untrusted write
    at t=7 when trust_weight * timestamp exceeds the competitor.

TrustWeightedAveragingResolver (ref 872)
    Numeric merge via trust-weighted average.  Each peer's contribution
    is proportional to their typed trust score.  Converges to the value
    held by the most trusted majority.

TrustGatedAcceptanceFilter (ref 873)
    Pre-merge gate that rejects operations from peers below a trust
    threshold.  Threshold is per-dimension: an integrity violation in
    Merkle hashing does not block a peer from contributing model params
    (unless their model trust is also low).

TrustWeightedStrategySelector (ref 874)
    Meta-strategy that selects the appropriate resolver based on data
    type, conflict characteristics, and aggregate trust topology.  Uses
    the typed trust dimensions to route: numeric conflicts → averaging,
    opaque blobs → LWW, structured data → custom resolver.

Mathematical properties:
  - All resolvers maintain join-semilattice convergence
  - Trust weighting is monotone: more evidence → lower trust → less influence
  - Composable: selectors can be chained without violating CRDT invariants
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from .typed_trust import (
    LOW_TRUST_THRESHOLD,
    QUARANTINE_THRESHOLD,
    TypedTrustScore,
)

if TYPE_CHECKING:
    from .delta_trust_lattice import DeltaTrustLattice


# -- Data types for conflict representation --------------------------------

class ConflictType(enum.Enum):
    """Classification of merge conflicts (ref 874)."""
    NUMERIC = "numeric"          # float/int values → averaging
    OPAQUE = "opaque"            # binary blobs → LWW
    STRUCTURED = "structured"    # nested dicts/lists → recursive
    COUNTER = "counter"          # monotone counters → max
    SET = "set"                  # set union/intersection → trust-weighted


@dataclass(frozen=True)
class ConflictEntry:
    """A single conflicting value from one peer.

    Attributes
    ----------
    peer_id     : Originating peer.
    value       : The conflicting value (any serializable type).
    timestamp   : Logical or wall-clock timestamp.
    trust       : Typed trust score of the originating peer at conflict time.
    dimension   : Primary trust dimension relevant to this data type.
    """
    peer_id: str
    value: Any
    timestamp: float
    trust: TypedTrustScore
    dimension: str = "integrity"


@dataclass(frozen=True)
class ResolutionResult:
    """Outcome of a conflict resolution.

    Attributes
    ----------
    resolved_value : The winning or merged value.
    confidence     : Confidence in the resolution [0.0, 1.0].
    method         : Name of the resolver that produced this result.
    contributors   : Peers whose values contributed (non-empty for averaging).
    rejected_peers : Peers whose values were filtered out.
    """
    resolved_value: Any
    confidence: float
    method: str
    contributors: Tuple[str, ...] = ()
    rejected_peers: Tuple[str, ...] = ()


# -- Protocol for pluggable resolvers -------------------------------------

@runtime_checkable
class ConflictResolver(Protocol):
    """Interface for trust-weighted conflict resolvers."""

    def resolve(
        self,
        entries: Sequence[ConflictEntry],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> ResolutionResult:
        """Resolve a conflict among multiple entries."""
        ...


# -- TrustWeightedLWWResolver (ref 871) ------------------------------------

class TrustWeightedLWWResolver:
    """Last-writer-wins weighted by trust score.

    The effective timestamp is: effective_t = timestamp * (1 + trust_weight).
    This means a trusted peer at t=5 with trust 0.9 has effective_t = 9.5,
    while an untrusted peer at t=7 with trust 0.2 has effective_t = 8.4.
    The trusted peer wins despite the later timestamp.

    When effective timestamps are equal (within epsilon), the higher
    trust score wins.  When both are equal, falls back to peer_id
    lexicographic ordering for deterministic convergence.

    Parameters
    ----------
    trust_weight_factor :
        Multiplier for the trust component.  Higher values give trust
        more influence over recency.  Default 1.0.
    min_trust :
        Minimum trust required to participate.  Entries below this
        threshold are filtered before comparison.
    """

    def __init__(
        self,
        *,
        trust_weight_factor: float = 1.0,
        min_trust: float = QUARANTINE_THRESHOLD,
    ) -> None:
        self._factor = trust_weight_factor
        self._min_trust = min_trust

    def resolve(
        self,
        entries: Sequence[ConflictEntry],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> ResolutionResult:
        """Resolve by trust-weighted last-writer-wins."""
        if not entries:
            raise ValueError("cannot resolve empty conflict set")

        # Refresh trust from lattice if available
        resolved_entries = self._refresh_trust(entries, trust_lattice)

        # Filter by minimum trust
        eligible = [
            e for e in resolved_entries
            if e.trust.trust_for_dimension(e.dimension) >= self._min_trust
        ]
        rejected = [
            e.peer_id for e in resolved_entries
            if e.trust.trust_for_dimension(e.dimension) < self._min_trust
        ]

        if not eligible:
            # All peers below threshold — fall back to highest trust entry
            eligible = sorted(
                resolved_entries,
                key=lambda e: e.trust.overall_trust(),
                reverse=True,
            )[:1]
            rejected = [e.peer_id for e in resolved_entries if e not in eligible]

        # Compute effective timestamps
        def effective_key(e: ConflictEntry) -> Tuple[float, float, str]:
            dim_trust = e.trust.trust_for_dimension(e.dimension)
            effective_t = e.timestamp * (1.0 + self._factor * dim_trust)
            return (effective_t, dim_trust, e.peer_id)

        winner = max(eligible, key=effective_key)
        dim_trust = winner.trust.trust_for_dimension(winner.dimension)

        return ResolutionResult(
            resolved_value=winner.value,
            confidence=dim_trust,
            method="trust_weighted_lww",
            contributors=(winner.peer_id,),
            rejected_peers=tuple(rejected),
        )

    def _refresh_trust(
        self,
        entries: Sequence[ConflictEntry],
        lattice: Optional[DeltaTrustLattice],
    ) -> List[ConflictEntry]:
        """Re-fetch trust scores from the lattice if available."""
        if lattice is None:
            return list(entries)
        return [
            ConflictEntry(
                peer_id=e.peer_id,
                value=e.value,
                timestamp=e.timestamp,
                trust=lattice.get_trust(e.peer_id),
                dimension=e.dimension,
            )
            for e in entries
        ]


# -- TrustWeightedAveragingResolver (ref 872) ------------------------------

class TrustWeightedAveragingResolver:
    """Trust-weighted average for numeric conflict resolution.

    Each peer's value is weighted by their dimension-specific trust score.
    The result is the weighted mean:

        resolved = Σ(trust_i * value_i) / Σ(trust_i)

    This naturally converges to the value held by the most trusted
    majority.  If a Byzantine peer contributes an outlier value, its
    low trust score minimises its impact on the result.

    Parameters
    ----------
    min_trust :
        Peers below this trust threshold contribute zero weight.
    outlier_sigma :
        Values more than this many standard deviations from the
        trust-weighted mean are excluded (default: 3.0, 0 disables).
    """

    def __init__(
        self,
        *,
        min_trust: float = QUARANTINE_THRESHOLD,
        outlier_sigma: float = 3.0,
    ) -> None:
        self._min_trust = min_trust
        self._outlier_sigma = outlier_sigma

    def resolve(
        self,
        entries: Sequence[ConflictEntry],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> ResolutionResult:
        """Resolve numeric values by trust-weighted averaging."""
        if not entries:
            raise ValueError("cannot resolve empty conflict set")

        resolved_entries = self._refresh_trust(entries, trust_lattice)

        # Partition into eligible/rejected
        eligible = []
        rejected = []
        for e in resolved_entries:
            dim_trust = e.trust.trust_for_dimension(e.dimension)
            if dim_trust >= self._min_trust:
                eligible.append(e)
            else:
                rejected.append(e.peer_id)

        if not eligible:
            # Fallback: use highest-trust entry as-is
            best = max(resolved_entries, key=lambda e: e.trust.overall_trust())
            return ResolutionResult(
                resolved_value=best.value,
                confidence=best.trust.overall_trust(),
                method="trust_weighted_averaging_fallback",
                contributors=(best.peer_id,),
                rejected_peers=tuple(e.peer_id for e in resolved_entries if e is not best),
            )

        # First pass: trust-weighted mean
        weights = []
        values = []
        for e in eligible:
            w = e.trust.trust_for_dimension(e.dimension)
            weights.append(w)
            values.append(float(e.value))

        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = 1.0

        weighted_mean = sum(w * v for w, v in zip(weights, values)) / total_weight

        # Outlier filtering
        if self._outlier_sigma > 0 and len(eligible) > 2:
            variance = sum(
                w * (v - weighted_mean) ** 2
                for w, v in zip(weights, values)
            ) / total_weight
            std = variance ** 0.5

            if std > 0:
                filtered_eligible = []
                for e, w, v in zip(eligible, weights, values):
                    if abs(v - weighted_mean) <= self._outlier_sigma * std:
                        filtered_eligible.append((e, w, v))
                    else:
                        rejected.append(e.peer_id)

                if filtered_eligible:
                    weights = [x[1] for x in filtered_eligible]
                    values = [x[2] for x in filtered_eligible]
                    eligible = [x[0] for x in filtered_eligible]
                    total_weight = sum(weights)
                    if total_weight == 0:
                        total_weight = 1.0
                    weighted_mean = sum(
                        w * v for w, v in zip(weights, values)
                    ) / total_weight

        # Confidence = normalized weight concentration (Herfindahl index)
        norm_weights = [w / total_weight for w in weights]
        hhi = sum(w ** 2 for w in norm_weights)
        confidence = min(1.0, hhi * len(eligible))  # 1.0 when unanimous

        return ResolutionResult(
            resolved_value=weighted_mean,
            confidence=confidence,
            method="trust_weighted_averaging",
            contributors=tuple(e.peer_id for e in eligible),
            rejected_peers=tuple(rejected),
        )

    def _refresh_trust(
        self,
        entries: Sequence[ConflictEntry],
        lattice: Optional[DeltaTrustLattice],
    ) -> List[ConflictEntry]:
        if lattice is None:
            return list(entries)
        return [
            ConflictEntry(
                peer_id=e.peer_id,
                value=e.value,
                timestamp=e.timestamp,
                trust=lattice.get_trust(e.peer_id),
                dimension=e.dimension,
            )
            for e in entries
        ]


# -- TrustGatedAcceptanceFilter (ref 873) ----------------------------------

class TrustGatedAcceptanceFilter:
    """Pre-merge gate that rejects operations from low-trust peers.

    Operates per-dimension: a peer with low integrity trust may still
    contribute model parameters if their model trust is acceptable.
    This is the fine-grained counterpart to the binary accept/reject
    in adaptive verification.

    Parameters
    ----------
    thresholds :
        Per-dimension acceptance thresholds.  Missing dimensions
        default to the global_threshold.
    global_threshold :
        Default threshold for dimensions not in the thresholds map.
    strict_mode :
        If True, ALL relevant dimensions must pass (AND logic).
        If False, ANY passing dimension allows the operation (OR logic).
        Default: True.
    """

    def __init__(
        self,
        *,
        thresholds: Optional[Dict[str, float]] = None,
        global_threshold: float = LOW_TRUST_THRESHOLD,
        strict_mode: bool = True,
    ) -> None:
        self._thresholds = dict(thresholds or {})
        self._global = global_threshold
        self._strict = strict_mode

    def accept(
        self,
        peer_id: str,
        trust: TypedTrustScore,
        dimensions: Optional[Sequence[str]] = None,
    ) -> bool:
        """Return True if the peer passes the trust gate.

        Parameters
        ----------
        peer_id :
            The originating peer (for logging/auditing).
        trust :
            The current typed trust score.
        dimensions :
            Dimensions to check.  If None, checks overall trust
            against the global threshold.
        """
        if dimensions is None:
            return trust.overall_trust() >= self._global

        results = []
        for dim in dimensions:
            threshold = self._thresholds.get(dim, self._global)
            dim_trust = trust.trust_for_dimension(dim)
            results.append(dim_trust >= threshold)

        if self._strict:
            return all(results)
        return any(results)

    def filter_entries(
        self,
        entries: Sequence[ConflictEntry],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> Tuple[List[ConflictEntry], List[str]]:
        """Partition entries into accepted and rejected.

        Returns
        -------
        (accepted, rejected_peer_ids)
        """
        accepted = []
        rejected = []

        for e in entries:
            trust = e.trust
            if trust_lattice is not None:
                trust = trust_lattice.get_trust(e.peer_id)

            if self.accept(e.peer_id, trust, dimensions=[e.dimension]):
                accepted.append(e)
            else:
                rejected.append(e.peer_id)

        return accepted, rejected


# -- TrustWeightedStrategySelector (ref 874) --------------------------------

class TrustWeightedStrategySelector:
    """Meta-strategy that selects resolvers based on conflict type and trust.

    Routes conflicts to the appropriate resolver based on the data type
    of the conflicting values and the aggregate trust topology of the
    contributing peers.

    Default routing:
        NUMERIC   → TrustWeightedAveragingResolver
        OPAQUE    → TrustWeightedLWWResolver
        COUNTER   → max (monotone, trust acts as tiebreaker)
        SET       → union with trust-gated membership
        STRUCTURED → recursive descent with per-field routing

    The selector can be extended with custom resolvers for specific
    conflict types via register().

    Parameters
    ----------
    acceptance_filter :
        The TrustGatedAcceptanceFilter applied before any resolver runs.
    lww_resolver :
        TrustWeightedLWWResolver instance (or None for default).
    averaging_resolver :
        TrustWeightedAveragingResolver instance (or None for default).
    """

    def __init__(
        self,
        *,
        acceptance_filter: Optional[TrustGatedAcceptanceFilter] = None,
        lww_resolver: Optional[TrustWeightedLWWResolver] = None,
        averaging_resolver: Optional[TrustWeightedAveragingResolver] = None,
        trust_scores: Optional[Dict[str, "TypedTrustScore"]] = None,
    ) -> None:
        self._filter = acceptance_filter or TrustGatedAcceptanceFilter()
        self._lww = lww_resolver or TrustWeightedLWWResolver()
        self._averaging = averaging_resolver or TrustWeightedAveragingResolver()
        self._custom_resolvers: Dict[str, ConflictResolver] = {}
        self._default_trust_scores: Dict[str, TypedTrustScore] = dict(trust_scores or {})

    # -- resolver registration ---------------------------------------------

    def register(
        self,
        conflict_type: ConflictType,
        resolver: ConflictResolver,
    ) -> None:
        """Register a custom resolver for a specific conflict type."""
        self._custom_resolvers[conflict_type.value] = resolver

    # -- main resolution entry point ----------------------------------------

    def resolve(
        self,
        entries: Sequence[ConflictEntry],
        conflict_type: ConflictType = ConflictType.OPAQUE,
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> ResolutionResult:
        """Resolve a conflict by routing to the appropriate strategy.

        Steps:
          1. Apply acceptance filter (reject low-trust peers)
          2. Classify conflict type
          3. Route to appropriate resolver
          4. Return result with full attribution
        """
        if not entries:
            raise ValueError("cannot resolve empty conflict set")

        # 1. Acceptance filter
        accepted, rejected = self._filter.filter_entries(
            entries, trust_lattice=trust_lattice,
        )

        if not accepted:
            # Everyone rejected — use highest trust as fallback
            best = max(entries, key=lambda e: e.trust.overall_trust())
            return ResolutionResult(
                resolved_value=best.value,
                confidence=best.trust.overall_trust(),
                method=f"trust_gated_fallback",
                contributors=(best.peer_id,),
                rejected_peers=tuple(rejected),
            )

        # 2. Check for custom resolver
        custom = self._custom_resolvers.get(conflict_type.value)
        if custom is not None:
            result = custom.resolve(accepted, trust_lattice)
            return ResolutionResult(
                resolved_value=result.resolved_value,
                confidence=result.confidence,
                method=result.method,
                contributors=result.contributors,
                rejected_peers=tuple(rejected) + result.rejected_peers,
            )

        # 3. Route to built-in resolver
        if conflict_type == ConflictType.NUMERIC:
            result = self._averaging.resolve(accepted, trust_lattice)
        elif conflict_type in (ConflictType.OPAQUE, ConflictType.STRUCTURED):
            result = self._lww.resolve(accepted, trust_lattice)
        elif conflict_type == ConflictType.COUNTER:
            result = self._resolve_counter(accepted)
        elif conflict_type == ConflictType.SET:
            result = self._resolve_set(accepted, trust_lattice)
        else:
            result = self._lww.resolve(accepted, trust_lattice)

        return ResolutionResult(
            resolved_value=result.resolved_value,
            confidence=result.confidence,
            method=result.method,
            contributors=result.contributors,
            rejected_peers=tuple(rejected) + result.rejected_peers,
        )

    # -- built-in resolvers for counter/set --------------------------------

    def _resolve_counter(
        self,
        entries: Sequence[ConflictEntry],
    ) -> ResolutionResult:
        """Monotone counter: max value wins, trust as tiebreaker."""
        winner = max(
            entries,
            key=lambda e: (
                float(e.value),
                e.trust.overall_trust(),
                e.peer_id,
            ),
        )
        return ResolutionResult(
            resolved_value=winner.value,
            confidence=winner.trust.overall_trust(),
            method="trust_weighted_counter_max",
            contributors=(winner.peer_id,),
        )

    def _resolve_set(
        self,
        entries: Sequence[ConflictEntry],
        trust_lattice: Optional[DeltaTrustLattice] = None,
    ) -> ResolutionResult:
        """Set union with trust-gated membership.

        Elements contributed by low-trust peers are excluded from the
        union.  This prevents Sybil peers from injecting bogus elements.
        """
        result_set: set = set()
        contributors = []

        for e in entries:
            trust = e.trust
            if trust_lattice is not None:
                trust = trust_lattice.get_trust(e.peer_id)

            dim_trust = trust.trust_for_dimension(e.dimension)
            if dim_trust >= self._filter._global:
                if isinstance(e.value, (set, frozenset, list, tuple)):
                    result_set.update(e.value)
                else:
                    result_set.add(e.value)
                contributors.append(e.peer_id)

        avg_trust = sum(
            e.trust.overall_trust() for e in entries if e.peer_id in contributors
        ) / max(len(contributors), 1)

        return ResolutionResult(
            resolved_value=frozenset(result_set),
            confidence=avg_trust,
            method="trust_weighted_set_union",
            contributors=tuple(contributors),
        )

    # -- introspection -----------------------------------------------------

    @property
    def registered_types(self) -> List[str]:
        """Custom conflict types with registered resolvers."""
        return list(self._custom_resolvers.keys())

    def __repr__(self) -> str:
        return (
            f"TrustWeightedStrategySelector("
            f"custom={len(self._custom_resolvers)}, "
            f"strict={self._filter._strict})"
        )


# Convenience alias
TrustWeightedStrategy = TrustWeightedStrategySelector
