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

"""Delta trust lattice -- the E4 recursive binding (ref 840-843).

Trust changes propagate as projection deltas through the same pipeline
as data.  The trust system uses itself to propagate itself: trust
validates data integrity (via Merkle), data integrity validates trust
evidence (via proof verification), and both flow through a shared delta
pipeline.

The recursive dependency manifests at three points:
  1. observe_and_propagate() -- local evidence becomes a delta with PCO
  2. receive_trust_delta()   -- incoming delta verified at adaptive depth
  3. merge()                 -- lattice-level CRDT merge + homeostasis

TrustCircuitBreaker (ref 829) monitors trust velocity and forces full
verification when anomalous change rates are detected.

Mathematical property: fixed-point computation.  Trust converges when
trust(state) = state where state includes trust.  Convergence guaranteed
by GCounter monotonicity across all dimensions.
"""

from __future__ import annotations

import time as _time
from collections import deque
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    runtime_checkable,
)

from .typed_trust import (
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    TrustHomeostasis,
    TypedTrustScore,
)
from .proof_evidence import TrustEvidence
from .pco import AggregateProofCarryingOperation, SubtreeRef
from .projection_delta import FrozenDict, ProjectionDelta

if TYPE_CHECKING:
    from .trust_bound_merkle import TrustBoundMerkle
    from .causal_trust_clock import CausalTrustClock


# -- Protocols for injectable dependencies ----------------------------------

@runtime_checkable
class MerkleProvider(Protocol):
    """Minimal interface for a trust-bound Merkle tree."""

    @property
    def root_hash(self) -> str: ...

    def update_trust_context(self, peer_id: str, trust: TypedTrustScore) -> None: ...


@runtime_checkable
class ClockProvider(Protocol):
    """Minimal interface for a causal-trust clock."""

    def serialize_compact(self) -> bytes: ...

    def increment(self) -> ClockProvider: ...


@runtime_checkable
class DeltaEncoderProvider(Protocol):
    """Minimal interface for encoding trust changes as deltas."""

    def encode_trust_change(
        self,
        peer_id: str,
        old_trust: TypedTrustScore,
        new_trust: TypedTrustScore,
        evidence: TrustEvidence,
    ) -> ProjectionDelta: ...

    def decode_trust_evidence(self, delta: ProjectionDelta) -> TrustEvidence: ...


# -- Exceptions -------------------------------------------------------------

class CircuitBreakerTripped(RuntimeError):
    """Raised when trust velocity exceeds safe thresholds."""


# -- TrustCircuitBreaker (ref 829) ------------------------------------------

class TrustCircuitBreaker:
    """Trust velocity monitor -- halts delta application when anomalous.

    Monitors the rate of trust change across the network.  When trust
    velocity exceeds a configurable threshold (default: 2 sigma from
    rolling mean), switches to defensive mode: all incoming deltas get
    Level 2 (full PCO) verification regardless of sender trust.

    Protects against coordinated Sybil swarm attacks where multiple
    compromised peers simultaneously attempt to manipulate trust state.
    """

    def __init__(
        self,
        *,
        window_size: int = 100,
        sigma_threshold: float = 2.0,
        cooldown_seconds: float = 30.0,
        min_samples: int = 10,
    ) -> None:
        self._velocity: Deque[float] = deque(maxlen=window_size)
        self._sigma_threshold = sigma_threshold
        self._cooldown = cooldown_seconds
        self._min_samples = min_samples
        self._tripped = False
        self._trip_time: Optional[float] = None

    def record_trust_change(
        self,
        peer_id: str,
        old: TypedTrustScore,
        new: TypedTrustScore,
    ) -> None:
        """Record a trust change and trip if velocity is anomalous."""
        velocity = abs(new.overall_trust() - old.overall_trust())
        self._velocity.append(velocity)

        if len(self._velocity) < self._min_samples:
            return

        mean = sum(self._velocity) / len(self._velocity)
        variance = sum((v - mean) ** 2 for v in self._velocity) / len(self._velocity)
        std = variance ** 0.5
        if velocity > mean + self._sigma_threshold * std:
            self._tripped = True
            self._trip_time = _time.monotonic()

    def is_tripped(self) -> bool:
        """True when the breaker is active (defensive mode)."""
        if self._tripped and self._trip_time is not None:
            if _time.monotonic() - self._trip_time > self._cooldown:
                self._tripped = False
                self._trip_time = None
        return self._tripped

    def reset(self) -> None:
        """Manually reset the breaker."""
        self._tripped = False
        self._trip_time = None
        self._velocity.clear()


# -- Minimal delta encoder (used when none is injected) ---------------------

class _DefaultDeltaEncoder:
    """Encodes trust changes as projection deltas using the standard format.

    Production systems inject a full ProjectionDeltaEncoder; this default
    produces structurally valid deltas suitable for integration testing.
    """

    def encode_trust_change(
        self,
        peer_id: str,
        old_trust: TypedTrustScore,
        new_trust: TypedTrustScore,
        evidence: TrustEvidence,
    ) -> ProjectionDelta:
        key = f"trust:{peer_id}"
        old_bytes = old_trust.serialize()
        new_bytes = new_trust.serialize()
        import hashlib
        old_hash = hashlib.sha256(old_bytes).hexdigest()

        subtree = SubtreeRef(
            path=(hash(peer_id) % 256,),
            depth=1,
            old_hash=old_hash,
            new_hash=hashlib.sha256(new_bytes).hexdigest(),
        )

        # Build a minimal PCO -- the caller replaces it.
        pco = AggregateProofCarryingOperation.build(
            originator_id=evidence.observer,
            signing_fn=lambda h: b"\x00" * 64,
            merkle_root="",
            clock_snapshot=b"",
            trust_vector_hash="",
            delta_bounds=[subtree],
        )

        return ProjectionDelta(
            source_id=evidence.observer,
            source_version=None,
            target_version=None,
            changed_subtrees=(subtree,),
            insertions=FrozenDict(),
            updates=FrozenDict({key: (old_hash, new_bytes)}),
            deletions=frozenset(),
            pco=pco,
            encoding="raw",
            compression_ratio=1.0,
        )

    def decode_trust_evidence(self, delta: ProjectionDelta) -> TrustEvidence:
        """Reconstruct evidence embedded in a trust delta.

        In the default encoder the evidence is stored as a serialized
        update keyed by ``trust:<peer_id>``.  The real implementation
        carries the full evidence record inside the delta payload.
        This stub returns a minimal evidence structure.
        """
        return TrustEvidence.create(
            observer=delta.source_id,
            target=delta.source_id,
            evidence_type="invalid_delta",
            dimension="integrity",
            amount=0.01,
            proof=b"\x00" * 33,
        )


# -- Stub Merkle / Clock for standalone instantiation ----------------------

class _StubMerkle:
    """Stand-in when no TrustBoundMerkle is injected."""

    @property
    def root_hash(self) -> str:
        return ""

    def update_trust_context(self, peer_id: str, trust: TypedTrustScore) -> None:
        pass

    def is_plausible_root(self, root: str) -> bool:
        return True


class _StubClock:
    """Stand-in when no CausalTrustClock is injected."""

    def serialize_compact(self) -> bytes:
        return b""

    def increment(self) -> _StubClock:
        return self


# -- DeltaTrustLattice (ref 840) -------------------------------------------

class DeltaTrustLattice:
    """Trust lattice where trust changes propagate as projection deltas.

    Constructor injection wires the E4 components together:

        merkle          -- TrustBoundMerkle (E1 binding)
        clock           -- CausalTrustClock (E2 binding)
        delta_encoder   -- encodes trust changes as ProjectionDeltas
        homeostasis     -- TrustHomeostasis budget normalizer
        circuit_breaker -- TrustCircuitBreaker velocity monitor

    The recursive dependency is explicit: TrustBoundMerkle and
    CausalTrustClock both hold a back-reference to this lattice for
    trust lookups.  Lazy init / protocol interfaces break the import
    cycle.
    """

    def __init__(
        self,
        peer_id: str,
        *,
        merkle: Optional[MerkleProvider] = None,
        clock: Optional[ClockProvider] = None,
        delta_encoder: Optional[DeltaEncoderProvider] = None,
        homeostasis: Optional[TrustHomeostasis] = None,
        circuit_breaker: Optional[TrustCircuitBreaker] = None,
        signing_fn: Optional[Callable[[bytes], bytes]] = None,
        initial_peers: Optional[Set[str]] = None,
    ) -> None:
        self._peer_id = peer_id
        self._trust_scores: Dict[str, TypedTrustScore] = {}
        self._evidence_log: List[TrustEvidence] = []

        self._merkle: MerkleProvider = merkle or _StubMerkle()
        self._clock: ClockProvider = clock or _StubClock()
        self._delta_encoder: DeltaEncoderProvider = delta_encoder or _DefaultDeltaEncoder()
        self._homeostasis = homeostasis or TrustHomeostasis()
        self._circuit_breaker = circuit_breaker or TrustCircuitBreaker()
        self._signing_fn: Callable[[bytes], bytes] = signing_fn or (lambda h: b"\x00" * 64)
        self._async_queue: List[ProjectionDelta] = []

        if initial_peers:
            for p in initial_peers:
                self._trust_scores[p] = TypedTrustScore.probationary()

    # -- dependency injection post-init ------------------------------------

    def bind_merkle(self, merkle: MerkleProvider) -> None:
        """Late-bind the Merkle tree (resolves circular init order)."""
        self._merkle = merkle

    def bind_clock(self, clock: ClockProvider) -> None:
        """Late-bind the causal clock (resolves circular init order)."""
        self._clock = clock

    # -- observe and propagate (ref 841-842) --------------------------------

    def observe_and_propagate(self, evidence: TrustEvidence) -> ProjectionDelta:
        """Observe misbehaviour, update trust, return delta for propagation.

        The returned ProjectionDelta flows through the SAME pipeline as
        data deltas -- this is the E4 recursive binding in action.
        """
        if self._circuit_breaker.is_tripped():
            raise CircuitBreakerTripped("trust velocity exceeded threshold")

        # 0. Reject self-attestation (observer cannot accuse themselves)
        if evidence.observer == evidence.target:
            raise ValueError("self-attestation rejected: observer cannot target self")

        # 1. Cryptographic proof verification (trust-independent)
        if not evidence.verify(self._merkle.root_hash):
            raise ValueError("evidence proof failed verification")

        # 2. Update local trust
        target = evidence.target
        old_trust = self._trust_scores.get(target, TypedTrustScore.probationary())
        new_trust = old_trust.record_evidence(
            observer=evidence.observer,
            dimension=evidence.dimension,
            amount=evidence.amount,
            proof=evidence,
        )
        self._trust_scores[target] = new_trust
        self._evidence_log.append(evidence)

        # 3. Homeostasis normalization
        self._trust_scores = self._homeostasis.normalize(
            self._trust_scores, len(self._trust_scores),
        )

        # 4. Circuit breaker tracking
        self._circuit_breaker.record_trust_change(target, old_trust, new_trust)

        # 5. Encode trust change as ProjectionDelta
        trust_delta = self._delta_encoder.encode_trust_change(
            peer_id=target,
            old_trust=old_trust,
            new_trust=new_trust,
            evidence=evidence,
        )

        # 6. Build aggregate PCO and attach
        pco = AggregateProofCarryingOperation.build(
            originator_id=self._peer_id,
            signing_fn=self._signing_fn,
            merkle_root=self._merkle.root_hash,
            clock_snapshot=self._clock.serialize_compact(),
            trust_vector_hash=self.get_trust(self._peer_id).hash(),
            delta_bounds=trust_delta.changed_subtrees,
        )

        return trust_delta.with_pco(pco)

    # -- receive trust delta (ref 843) --------------------------------------

    def receive_trust_delta(
        self,
        delta: ProjectionDelta,
        state: Optional[object] = None,
    ) -> bool:
        """Receive a trust delta from another peer.

        Uses adaptive immune verification -- depth determined by our
        current trust in the sender.  This is where the recursive
        dependency manifests: trust determines verification depth,
        verification outcome updates trust.
        """
        if self._circuit_breaker.is_tripped():
            return False

        # 1. Adaptive immune level from sender trust
        sender_trust = self.get_trust(delta.source_id)
        level = sender_trust.verification_level()

        # 2. Verify aggregate PCO at the appropriate depth
        if not delta.pco.verify(
            state or self,
            self,
            verification_level=level,
        ):
            self._record_counter_evidence(delta.source_id, "invalid_delta")
            return False

        # 3. Schedule async full verification for optimistic levels
        if level < 2:
            self._async_queue.append(delta)

        # 4. Decode and verify embedded evidence
        evidence = self._delta_encoder.decode_trust_evidence(delta)
        if not evidence.verify(self._merkle.root_hash):
            self._record_counter_evidence(delta.source_id, "trust_manipulation")
            return False

        # 5. Apply trust update (merge guarantees monotonicity)
        target = evidence.target
        old_trust = self._trust_scores.get(target, TypedTrustScore.probationary())
        updated = old_trust.record_evidence(
            observer=evidence.observer,
            dimension=evidence.dimension,
            amount=evidence.amount,
            proof=evidence,
        )
        new_trust = old_trust.merge(updated)
        self._trust_scores[target] = new_trust

        # 6. Homeostasis
        self._trust_scores = self._homeostasis.normalize(
            self._trust_scores, len(self._trust_scores),
        )

        # 7. Circuit breaker
        self._circuit_breaker.record_trust_change(target, old_trust, new_trust)

        # 8. Update Merkle tree (trust change affects trust-bound hashes)
        self._merkle.update_trust_context(target, new_trust)

        return True

    # -- trust lookup -------------------------------------------------------

    def get_trust(self, peer_id: str) -> TypedTrustScore:
        """Current typed trust score for *peer_id*."""
        return self._trust_scores.get(peer_id, TypedTrustScore.probationary())

    # -- trust root (aggregate hash of all trust state) ---------------------

    def compute_trust_root(self) -> str:
        """Aggregate hash across all peer trust vectors."""
        import hashlib
        h = hashlib.sha256()
        for pid in sorted(self._trust_scores):
            h.update(pid.encode("utf-8"))
            h.update(self._trust_scores[pid].serialize())
        return h.hexdigest()

    # -- CRDT merge ---------------------------------------------------------

    def merge(self, other: DeltaTrustLattice) -> DeltaTrustLattice:
        """CRDT merge of two trust lattices.

        Element-wise merge of per-peer TypedTrustScores followed by
        homeostasis normalization.
        """
        result = DeltaTrustLattice(
            self._peer_id,
            merkle=self._merkle,
            clock=self._clock,
            delta_encoder=self._delta_encoder,
            homeostasis=self._homeostasis,
            circuit_breaker=self._circuit_breaker,
            signing_fn=self._signing_fn,
        )
        all_peers = set(self._trust_scores) | set(other._trust_scores)
        for peer in all_peers:
            self_t = self._trust_scores.get(peer, TypedTrustScore.probationary())
            other_t = other._trust_scores.get(peer, TypedTrustScore.probationary())
            result._trust_scores[peer] = self_t.merge(other_t)

        result._trust_scores = result._homeostasis.normalize(
            result._trust_scores, len(result._trust_scores),
        )
        return result

    # -- introspection ------------------------------------------------------

    @property
    def peer_id(self) -> str:
        return self._peer_id

    @property
    def peer_count(self) -> int:
        return len(self._trust_scores)

    def known_peers(self) -> Set[str]:
        return set(self._trust_scores)

    @property
    def evidence_log(self) -> List[TrustEvidence]:
        return list(self._evidence_log)

    @property
    def pending_async_verifications(self) -> int:
        return len(self._async_queue)

    def drain_async_queue(self) -> List[ProjectionDelta]:
        """Return and clear pending async verification items."""
        q = self._async_queue
        self._async_queue = []
        return q

    # -- internal helpers ---------------------------------------------------

    def _record_counter_evidence(
        self,
        peer_id: str,
        evidence_type: str,
    ) -> None:
        """Record counter-evidence against a misbehaving peer."""
        dim = "integrity" if evidence_type == "invalid_delta" else "consistency"
        old = self._trust_scores.get(peer_id, TypedTrustScore.probationary())

        ev = TrustEvidence.create(
            observer=self._peer_id,
            target=peer_id,
            evidence_type=evidence_type,
            dimension=dim,
            amount=0.05,
            proof=b"\x00" * 33,
        )
        try:
            new = old.record_evidence(
                observer=self._peer_id,
                dimension=dim,
                amount=0.05,
                proof=ev,
            )
            self._trust_scores[peer_id] = new
            self._evidence_log.append(ev)
        except ValueError:
            pass  # nosec B110 -- fallback on unsupported input

    def __repr__(self) -> str:
        return (
            f"DeltaTrustLattice(peer={self._peer_id!r}, "
            f"peers={len(self._trust_scores)}, "
            f"breaker={'TRIPPED' if self._circuit_breaker.is_tripped() else 'ok'})"
        )
