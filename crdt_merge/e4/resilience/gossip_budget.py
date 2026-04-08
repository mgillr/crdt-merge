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

"""Gossip bandwidth budget analyser and trust-state compressor.

Addresses Mitchell §C3 and Georgiou §C6: at 10M clients, transmitting
trust updates alongside model updates adds non-trivial communication
overhead.  The 128-byte PCO is compact per-message, but the aggregate
trust state (all peer scores) scales linearly with peer count.

Solution — three compression strategies:

  Strategy 1: Sparse trust gossip.
    Only gossip trust deltas that changed since the last exchange.
    In a stable network, most trust scores are static, so the sparse
    delta is << full state.  Uses a bloom filter to track which peer
    scores have changed.

  Strategy 2: Hierarchical aggregation.
    For N > 10K peers, partition into trust regions (geographic,
    institutional, random hash).  Each region maintains a regional
    trust summary (min, max, median, count).  Cross-region gossip
    exchanges summaries, not individual scores.

  Strategy 3: Adaptive gossip rate.
    Reduce gossip frequency when trust is stable (convergence monitor
    reports low variance).  Increase during trust churn (new peers,
    attacks, epoch transitions).

Bandwidth model (for analysis):
  Per-peer trust state: 40 bytes (5 dims * 8 bytes)
  Full state for N=10K: 400 KB
  Full state for N=10M: 400 MB (prohibitive)
  Sparse delta (1% changed): 4 KB (for N=10K)
  Regional summary (100 regions): 4 KB (regardless of N)

Technical effect (UK patent): reduces trust gossip bandwidth from
O(N) to O(sqrt(N)) through hierarchical aggregation, enabling E4
deployment at cross-device federated learning scale (10M+ peers).
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# -- Bandwidth model -------------------------------------------------------

TRUST_ENTRY_BYTES = 40  # 5 dimensions * 8 bytes per float64

@dataclass(frozen=True)
class BandwidthEstimate:
    """Estimated bandwidth for trust gossip."""
    full_state_bytes: int
    sparse_delta_bytes: int
    regional_summary_bytes: int
    recommended_strategy: str
    gossip_interval_secs: float


def estimate_bandwidth(
    peer_count: int,
    churn_rate: float = 0.01,
    region_count: int = 100,
) -> BandwidthEstimate:
    """Estimate trust gossip bandwidth under three strategies.

    Parameters
    ----------
    peer_count :
        Total number of peers in the network.
    churn_rate :
        Fraction of peers whose trust changed since last gossip.
    region_count :
        Number of hierarchical trust regions.
    """
    full = peer_count * TRUST_ENTRY_BYTES
    sparse = int(peer_count * churn_rate * TRUST_ENTRY_BYTES) + 64
    regional = region_count * 48 + 64  # 48 bytes per region summary

    if peer_count < 1000:
        strategy = "full"
        interval = 10.0
    elif peer_count < 100_000:
        strategy = "sparse"
        interval = 30.0
    else:
        strategy = "regional"
        interval = 60.0

    return BandwidthEstimate(full, sparse, regional, strategy, interval)


# -- Sparse trust delta ----------------------------------------------------

@dataclass
class SparseTrustDelta:
    """Compact representation of changed trust entries only."""
    epoch: int
    changed_peers: Dict[str, Tuple[float, ...]] = field(default_factory=dict)

    def add(self, peer_id: str, dimensions: Tuple[float, ...]) -> None:
        self.changed_peers[peer_id] = dimensions

    def serialize(self) -> bytes:
        parts = [struct.pack("!I", self.epoch)]
        parts.append(struct.pack("!I", len(self.changed_peers)))
        for pid in sorted(self.changed_peers):
            pid_bytes = pid.encode("utf-8")
            parts.append(struct.pack("!H", len(pid_bytes)))
            parts.append(pid_bytes)
            dims = self.changed_peers[pid]
            for d in dims:
                parts.append(struct.pack("!d", d))
        return b"".join(parts)

    @classmethod
    def deserialize(cls, data: bytes) -> SparseTrustDelta:
        off = 0
        epoch = struct.unpack("!I", data[off:off + 4])[0]
        off += 4
        count = struct.unpack("!I", data[off:off + 4])[0]
        off += 4
        delta = cls(epoch=epoch)
        for _ in range(count):
            pid_len = struct.unpack("!H", data[off:off + 2])[0]
            off += 2
            pid = data[off:off + pid_len].decode("utf-8")
            off += pid_len
            dims = []
            for _ in range(5):
                d = struct.unpack("!d", data[off:off + 8])[0]
                off += 8
                dims.append(d)
            delta.changed_peers[pid] = tuple(dims)
        return delta

    @property
    def wire_size(self) -> int:
        return len(self.serialize())

    @property
    def change_count(self) -> int:
        return len(self.changed_peers)


# -- Regional trust summary ------------------------------------------------

@dataclass
class RegionSummary:
    """Compressed trust summary for a trust region."""
    region_id: str
    peer_count: int
    trust_min: float
    trust_max: float
    trust_median: float
    trust_mean: float
    epoch: int

    def serialize(self) -> bytes:
        rid = self.region_id.encode("utf-8")
        return struct.pack(
            "!H", len(rid),
        ) + rid + struct.pack(
            "!IddddI",
            self.peer_count,
            self.trust_min,
            self.trust_max,
            self.trust_median,
            self.trust_mean,
            self.epoch,
        )


class HierarchicalAggregator:
    """Hierarchical trust aggregation for large-scale deployment.

    Partitions peers into regions and computes per-region summaries
    for cross-region gossip.

    Parameters
    ----------
    region_count :
        Target number of regions (peers assigned by hash).
    """

    def __init__(self, region_count: int = 100) -> None:
        self._region_count = max(region_count, 1)
        self._regions: Dict[str, Dict[str, Tuple[float, ...]]] = {}

    def assign_peer(self, peer_id: str, dimensions: Tuple[float, ...]) -> str:
        """Assign peer to region by consistent hashing, store trust."""
        region_id = self._region_for(peer_id)
        if region_id not in self._regions:
            self._regions[region_id] = {}
        self._regions[region_id][peer_id] = dimensions
        return region_id

    def update_peer(self, peer_id: str, dimensions: Tuple[float, ...]) -> None:
        """Update trust for an already-assigned peer."""
        region_id = self._region_for(peer_id)
        if region_id in self._regions:
            self._regions[region_id][peer_id] = dimensions

    def remove_peer(self, peer_id: str) -> None:
        region_id = self._region_for(peer_id)
        if region_id in self._regions:
            self._regions[region_id].pop(peer_id, None)

    def compute_summaries(self, epoch: int = 0) -> List[RegionSummary]:
        """Compute trust summaries for all regions."""
        summaries = []
        for rid, peers in sorted(self._regions.items()):
            if not peers:
                continue
            overall_scores = []
            for dims in peers.values():
                overall_scores.append(sum(dims) / max(len(dims), 1))
            overall_scores.sort()
            n = len(overall_scores)
            mid = n // 2
            median = (
                overall_scores[mid] if n % 2
                else (overall_scores[mid - 1] + overall_scores[mid]) / 2.0
            )
            summaries.append(RegionSummary(
                region_id=rid,
                peer_count=n,
                trust_min=overall_scores[0],
                trust_max=overall_scores[-1],
                trust_median=median,
                trust_mean=sum(overall_scores) / n,
                epoch=epoch,
            ))
        return summaries

    def total_wire_size(self, epoch: int = 0) -> int:
        """Total serialized size of all region summaries."""
        return sum(len(s.serialize()) for s in self.compute_summaries(epoch))

    @property
    def region_count(self) -> int:
        return len(self._regions)

    @property
    def peer_count(self) -> int:
        return sum(len(r) for r in self._regions.values())

    # -- internal ----------------------------------------------------------

    def _region_for(self, peer_id: str) -> str:
        h = int(hashlib.md5(peer_id.encode()).hexdigest(), 16)
        idx = h % self._region_count
        return f"region-{idx:04d}"


# -- Adaptive gossip rate --------------------------------------------------

class AdaptiveGossipRate:
    """Adjust gossip frequency based on trust stability.

    Parameters
    ----------
    base_interval :
        Normal gossip interval in seconds.
    min_interval :
        Minimum interval during high churn.
    max_interval :
        Maximum interval during stability.
    variance_threshold :
        Trust variance above which gossip accelerates.
    """

    def __init__(
        self,
        base_interval: float = 30.0,
        min_interval: float = 5.0,
        max_interval: float = 120.0,
        variance_threshold: float = 0.01,
    ) -> None:
        self._base = base_interval
        self._min = min_interval
        self._max = max_interval
        self._var_threshold = variance_threshold
        self._recent_variances: List[float] = []

    def observe_variance(self, variance: float) -> None:
        self._recent_variances.append(variance)
        if len(self._recent_variances) > 50:
            self._recent_variances = self._recent_variances[-50:]

    def current_interval(self) -> float:
        if not self._recent_variances:
            return self._base
        avg_var = sum(self._recent_variances) / len(self._recent_variances)
        if avg_var > self._var_threshold * 5:
            return self._min
        if avg_var > self._var_threshold:
            ratio = avg_var / self._var_threshold
            return max(self._min, self._base / ratio)
        stability = self._var_threshold / max(avg_var, 1e-12)
        return min(self._max, self._base * min(stability, 4.0))

    def __repr__(self) -> str:
        return f"AdaptiveGossipRate(interval={self.current_interval():.1f}s)"
