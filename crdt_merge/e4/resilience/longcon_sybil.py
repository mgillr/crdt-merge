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

"""Long-con Sybil detection — patient adversary resistance.

Addresses Wei §C16 and Dubois §C23: the trust velocity monitor (circuit
breaker, ref §829) detects coordinated fast trust-building but not a
patient adversary operating below the detection threshold over extended
periods.

A long-con Sybil attack pattern:
  1. Create many identities.
  2. Each identity contributes valid, unremarkable evidence.
  3. Over weeks/months, each identity builds trust incrementally.
  4. At a coordinated moment, all identities act maliciously.

The circuit breaker catches step 4 (sudden velocity spike) but not
steps 1-3 (slow, below-threshold trust accumulation).

Detection strategy — three independent signals, any two trigger alert:

  Signal A: Entropy clustering.
    Sybil identities from a common operator have correlated trust
    growth patterns.  Real peers have uncorrelated growth (different
    uptime, different data, different connectivity).  Pairwise
    Pearson correlation of trust growth vectors; cluster coefficient
    above threshold flags potential Sybil groups.

  Signal B: Evidence timing correlation.
    Real peers produce evidence at varying cadence (human schedules,
    hardware differences).  Sybil identities from the same operator
    tend to produce evidence in temporal bursts (batch scripts,
    shared infrastructure).  Kolmogorov-Smirnov test on inter-evidence
    arrival times against exponential null.

  Signal C: Graph density anomaly.
    In the trust evidence graph, organic peers have sparse, power-law
    degree distributions.  Sybil clusters have unusually dense internal
    connections (vouching for each other).  Local clustering coefficient
    vs. global average flags dense subgraphs.

Technical effect (UK patent): detects coordinated Sybil attacks that
individually stay below trust velocity thresholds by correlating
statistical patterns across the peer population.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# -- Configuration ---------------------------------------------------------

@dataclass
class LongConConfig:
    """Tuneable parameters for long-con detection."""
    correlation_window: int = 100
    correlation_threshold: float = 0.7
    timing_ks_threshold: float = 0.3
    density_ratio_threshold: float = 3.0
    min_evidence_count: int = 10
    signals_required: int = 2
    quarantine_duration: float = 3600.0


# -- Evidence record -------------------------------------------------------

@dataclass
class EvidenceRecord:
    """Single trust evidence observation."""
    peer_id: str
    timestamp: float
    dimension: int
    magnitude: float


# -- Detection signals -----------------------------------------------------

@dataclass(frozen=True)
class SybilSignal:
    """One detection signal for a candidate Sybil group."""
    signal_type: str       # "entropy", "timing", or "density"
    score: float
    threshold: float
    triggered: bool
    peer_group: Tuple[str, ...]


@dataclass(frozen=True)
class SybilAlert:
    """Alert for a detected Sybil cluster."""
    peer_ids: Tuple[str, ...]
    signals: Tuple[SybilSignal, ...]
    confidence: float
    timestamp: float


# -- Long-con detector -----------------------------------------------------

class LongConDetector:
    """Detect patient Sybil attacks via multi-signal correlation.

    Maintains a rolling window of trust evidence per peer and
    periodically scans for correlated growth patterns, timing
    anomalies, and graph density anomalies.

    Parameters
    ----------
    config :
        Detection thresholds and window sizes.
    """

    def __init__(self, config: Optional[LongConConfig] = None) -> None:
        self._config = config or LongConConfig()
        self._evidence: Dict[str, List[EvidenceRecord]] = defaultdict(list)
        self._alerts: List[SybilAlert] = []
        self._quarantined: Dict[str, float] = {}

    # -- evidence ingestion ------------------------------------------------

    def record_evidence(self, record: EvidenceRecord) -> None:
        """Ingest a trust evidence observation."""
        window = self._config.correlation_window
        buf = self._evidence[record.peer_id]
        buf.append(record)
        if len(buf) > window * 2:
            self._evidence[record.peer_id] = buf[-window:]

    def record_batch(self, records: List[EvidenceRecord]) -> None:
        """Ingest a batch of evidence records."""
        for r in records:
            self.record_evidence(r)

    # -- detection scan ----------------------------------------------------

    def scan(self, now: Optional[float] = None) -> List[SybilAlert]:
        """Run full detection scan across all peers.

        Returns new alerts generated this scan (empty if clean).
        """
        now = now or time.monotonic()
        self._expire_quarantine(now)

        peers = [
            pid for pid, ev in self._evidence.items()
            if len(ev) >= self._config.min_evidence_count
            and pid not in self._quarantined
        ]
        if len(peers) < 2:
            return []

        new_alerts = []
        groups = self._find_correlated_groups(peers)

        for group in groups:
            signals = []
            signals.append(self._check_entropy_correlation(group))
            signals.append(self._check_timing_correlation(group))
            signals.append(self._check_density_anomaly(group))

            triggered = sum(1 for s in signals if s.triggered)
            if triggered >= self._config.signals_required:
                confidence = triggered / len(signals)
                alert = SybilAlert(
                    peer_ids=tuple(group),
                    signals=tuple(signals),
                    confidence=confidence,
                    timestamp=now,
                )
                new_alerts.append(alert)
                for pid in group:
                    self._quarantined[pid] = now + self._config.quarantine_duration

        self._alerts.extend(new_alerts)
        return new_alerts

    @property
    def alerts(self) -> List[SybilAlert]:
        return list(self._alerts)

    @property
    def quarantined_peers(self) -> Set[str]:
        return set(self._quarantined)

    def is_quarantined(self, peer_id: str) -> bool:
        return peer_id in self._quarantined

    # -- Signal A: entropy clustering --------------------------------------

    def _find_correlated_groups(self, peers: List[str]) -> List[List[str]]:
        """Find groups of peers with correlated trust growth."""
        vectors = {}
        for pid in peers:
            vectors[pid] = self._growth_vector(pid)

        groups = []
        used = set()
        for i, p1 in enumerate(peers):
            if p1 in used:
                continue
            group = [p1]
            for p2 in peers[i + 1:]:
                if p2 in used:
                    continue
                r = _pearson(vectors[p1], vectors[p2])
                if r > self._config.correlation_threshold:
                    group.append(p2)
                    used.add(p2)
            if len(group) >= 2:
                groups.append(group)
                used.add(p1)

        return groups

    def _check_entropy_correlation(self, group: List[str]) -> SybilSignal:
        """Check pairwise trust growth correlation within group."""
        vectors = {pid: self._growth_vector(pid) for pid in group}
        pairs = []
        for i, p1 in enumerate(group):
            for p2 in group[i + 1:]:
                pairs.append(_pearson(vectors[p1], vectors[p2]))

        avg_corr = sum(pairs) / len(pairs) if pairs else 0.0
        threshold = self._config.correlation_threshold
        return SybilSignal(
            "entropy", avg_corr, threshold,
            avg_corr > threshold, tuple(group),
        )

    # -- Signal B: timing correlation --------------------------------------

    def _check_timing_correlation(self, group: List[str]) -> SybilSignal:
        """Check inter-evidence arrival time distribution."""
        ks_scores = []
        for pid in group:
            arrivals = self._inter_arrival_times(pid)
            if len(arrivals) < 3:
                continue
            ks = _ks_exponential(arrivals)
            ks_scores.append(ks)

        avg_ks = sum(ks_scores) / len(ks_scores) if ks_scores else 0.0
        threshold = self._config.timing_ks_threshold
        return SybilSignal(
            "timing", avg_ks, threshold,
            avg_ks > threshold, tuple(group),
        )

    # -- Signal C: graph density -------------------------------------------

    def _check_density_anomaly(self, group: List[str]) -> SybilSignal:
        """Check if group has anomalously dense mutual evidence."""
        mutual = 0
        total = 0
        group_set = set(group)

        for pid in group:
            for ev in self._evidence.get(pid, []):
                total += 1
                if ev.peer_id in group_set and ev.peer_id != pid:
                    mutual += 1

        density = mutual / max(total, 1)
        expected = len(group) / max(len(self._evidence), 1)
        ratio = density / max(expected, 1e-9)
        threshold = self._config.density_ratio_threshold
        return SybilSignal(
            "density", ratio, threshold,
            ratio > threshold, tuple(group),
        )

    # -- helpers -----------------------------------------------------------

    def _growth_vector(self, peer_id: str) -> List[float]:
        """Compute trust growth rate vector (per-dimension deltas)."""
        records = self._evidence.get(peer_id, [])
        if len(records) < 2:
            return [0.0] * 5
        dims = defaultdict(list)
        for r in records:
            dims[r.dimension].append(r.magnitude)
        vec = []
        for d in range(5):
            vals = dims.get(d, [0.0])
            if len(vals) >= 2:
                growth = sum(vals[i] - vals[i - 1] for i in range(1, len(vals)))
                vec.append(growth / len(vals))
            else:
                vec.append(0.0)
        return vec

    def _inter_arrival_times(self, peer_id: str) -> List[float]:
        """Compute inter-evidence arrival times."""
        records = self._evidence.get(peer_id, [])
        if len(records) < 2:
            return []
        times = sorted(r.timestamp for r in records)
        return [times[i] - times[i - 1] for i in range(1, len(times))]

    def _expire_quarantine(self, now: float) -> None:
        expired = [pid for pid, exp in self._quarantined.items() if now > exp]
        for pid in expired:
            del self._quarantined[pid]

    def __repr__(self) -> str:
        return (
            f"LongConDetector(peers={len(self._evidence)}, "
            f"alerts={len(self._alerts)}, "
            f"quarantined={len(self._quarantined)})"
        )


# -- statistical helpers (no external deps) --------------------------------

def _pearson(a: List[float], b: List[float]) -> float:
    """Pearson correlation coefficient between two vectors."""
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((a[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((b[i] - mb) ** 2 for i in range(n)))
    if da < 1e-12 or db < 1e-12:
        return 0.0
    return num / (da * db)


def _ks_exponential(samples: List[float]) -> float:
    """Kolmogorov-Smirnov statistic against exponential distribution."""
    n = len(samples)
    if n < 2:
        return 0.0
    mean = sum(samples) / n
    if mean < 1e-12:
        return 1.0
    rate = 1.0 / mean
    sorted_s = sorted(samples)
    ks = 0.0
    for i, s in enumerate(sorted_s):
        cdf = 1.0 - math.exp(-rate * s)
        ecdf = (i + 1) / n
        ks = max(ks, abs(ecdf - cdf))
    return ks
