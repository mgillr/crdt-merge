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

"""Trust-validated streaming merge (ref 1155-1156).

Wraps a base streaming merge engine to add per-chunk PCO validation
and trust-gated stream acceptance.  Streams from quarantined peers are
rejected outright; streams from low-trust peers get full verification
on every chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from crdt_merge.e4.adaptive_verification import (
        AdaptiveVerificationController,
        VerificationResult,
    )
    from crdt_merge.e4.projection_delta import ProjectionDelta


# -- Stream chunk wrapper --------------------------------------------------

@dataclass
class StreamChunk:
    """Single chunk in a trust-validated stream.

    Attributes
    ----------
    delta        : The projection delta for this chunk.
    sequence     : Monotonic sequence number within the stream.
    stream_id    : Identifier tying chunks to a logical stream.
    """

    delta: ProjectionDelta
    sequence: int
    stream_id: str = ""


@dataclass(frozen=True)
class ChunkResult:
    """Outcome of validating a single stream chunk."""

    accepted: bool
    sequence: int
    reason: str = ""


# -- TrustStreamMerge ------------------------------------------------------

class TrustStreamMerge:
    """Streaming merge with per-chunk trust validation.

    Parameters
    ----------
    verifier :
        Adaptive verification controller.
    state :
        Local application state for verification.
    min_trust :
        Minimum overall trust to accept a stream at all.
    """

    def __init__(
        self,
        verifier: Optional[AdaptiveVerificationController] = None,
        state: Optional[object] = None,
        *,
        min_trust: float = 0.1,
    ) -> None:
        self._verifier = verifier
        self._state = state
        self._min_trust = min_trust
        self._active_streams: dict[str, List[ChunkResult]] = {}

    # -- dependency injection ----------------------------------------------

    def bind_verifier(self, verifier: AdaptiveVerificationController) -> None:
        self._verifier = verifier

    def bind_state(self, state: object) -> None:
        self._state = state

    # -- stream-level gate -------------------------------------------------

    def accept_stream(
        self,
        peer_id: str,
        stream_id: str,
        trust_lattice: object,
    ) -> bool:
        """Decide whether to accept a stream from *peer_id*.

        Returns False if the peer's overall trust is below the minimum
        threshold.
        """
        get_trust = getattr(trust_lattice, "get_trust", None)
        if get_trust is None:
            return True
        score = get_trust(peer_id)
        overall = score.overall_trust()
        if overall < self._min_trust:
            return False
        self._active_streams[stream_id] = []
        return True

    # -- per-chunk validation ----------------------------------------------

    def validate_chunk(
        self,
        chunk: StreamChunk,
        trust_lattice: Optional[object] = None,
    ) -> ChunkResult:
        """Validate a single stream chunk via adaptive verification.

        Each chunk's delta is independently verified.  Failures are
        recorded in the chunk result log for the stream.
        """
        if self._verifier is None:
            result = ChunkResult(accepted=True, sequence=chunk.sequence)
            self._record(chunk.stream_id, result)
            return result

        vr = self._verifier.verify(chunk.delta, self._state, trust_lattice)
        result = ChunkResult(
            accepted=vr.accepted,
            sequence=chunk.sequence,
            reason=vr.reason if not vr.accepted else "",
        )
        self._record(chunk.stream_id, result)
        return result

    def validate_stream(
        self,
        chunks: Sequence[StreamChunk],
        trust_lattice: Optional[object] = None,
    ) -> List[ChunkResult]:
        """Validate an entire stream of chunks in order.

        Stops early if a chunk fails (stream is considered corrupt
        from that point forward).
        """
        results: List[ChunkResult] = []
        for chunk in chunks:
            cr = self.validate_chunk(chunk, trust_lattice)
            results.append(cr)
            if not cr.accepted:
                break
        return results

    # -- introspection -----------------------------------------------------

    def stream_results(self, stream_id: str) -> List[ChunkResult]:
        return list(self._active_streams.get(stream_id, []))

    def active_stream_ids(self) -> List[str]:
        return list(self._active_streams)

    def close_stream(self, stream_id: str) -> None:
        self._active_streams.pop(stream_id, None)

    # -- internal ----------------------------------------------------------

    def _record(self, stream_id: str, result: ChunkResult) -> None:
        log = self._active_streams.setdefault(stream_id, [])
        log.append(result)
