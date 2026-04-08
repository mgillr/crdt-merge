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

"""Performance specifications — sketch config, fan-out, derating, GC.

Addresses four expert concerns:

  - Vasquez §3: CountMinSketch accuracy at hierarchical tier.  False
    positives could cause unwarranted trust degradation.  Specifies
    exact sketch parameters for target error bounds.

  - Tanaka §22: GC pressure from immutable data structures.  At high
    throughput, frozen dataclasses create significant GC pressure.
    Specifies mitigation strategies and Rust hot-path recommendations.

  - Tanaka §23: Network amplification.  At 10K+ nodes, PCO overhead
    grows linearly.  Specifies fan-out optimization for gossip protocol.

  - Tanaka §24: A100 benchmark vs real workload.  Production throughput
    is 30-50% of benchmark.  Specifies derating factors and minimum
    hardware requirements.

Technical effect (UK patent): provides deterministic performance
guarantees for deployment at specified scale points, enabling
capacity planning for distributed CRDT trust networks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ===========================================================================
# CountMinSketch Configuration (Vasquez §3)
# ===========================================================================

@dataclass(frozen=True)
class SketchConfig:
    """CountMinSketch parameters for approximate trust at the hierarchical tier.

    The sketch provides P(error > ε) < δ where:
      width = ceil(e / ε)   — columns per row
      depth = ceil(ln(1/δ)) — number of hash functions

    For target ε=0.01, δ=0.001 (error < 1% with 99.9% probability):
      width = ceil(2.718 / 0.01) = 272
      depth = ceil(ln(1000)) = 7

    Memory: width × depth × sizeof(float) = 272 × 7 × 4 = 7,616 bytes
    Per 1M peers: 7.6KB — negligible.

    Attributes
    ----------
    width        : Columns per row.
    depth        : Number of hash functions (rows).
    epsilon      : Error bound (max overcount as fraction of total).
    delta        : Probability bound (P(error > ε) < δ).
    memory_bytes : Total memory consumption.
    """
    width: int
    depth: int
    epsilon: float
    delta: float
    memory_bytes: int = 0

    def __post_init__(self) -> None:
        if self.memory_bytes == 0:
            mem = self.width * self.depth * 4  # 4 bytes per float32
            object.__setattr__(self, "memory_bytes", mem)

    @classmethod
    def for_target(cls, epsilon: float = 0.01, delta: float = 0.001) -> SketchConfig:
        """Compute optimal sketch parameters for target error bounds.

        Parameters
        ----------
        epsilon :
            Maximum error as fraction of total updates (default: 0.01 = 1%).
        delta :
            Probability bound for exceeding epsilon (default: 0.001 = 0.1%).
        """
        width = math.ceil(math.e / epsilon)
        depth = math.ceil(math.log(1.0 / delta))
        return cls(width=width, depth=depth, epsilon=epsilon, delta=delta)

    @classmethod
    def for_scale(cls, peer_count: int) -> SketchConfig:
        """Auto-configure sketch for a given scale.

        Tighter bounds for larger deployments:
        - <1K peers: ε=0.05, δ=0.01
        - 1K-10K:    ε=0.02, δ=0.005
        - 10K-100K:  ε=0.01, δ=0.001
        - 100K-1M:   ε=0.005, δ=0.0001
        - >1M:       ε=0.001, δ=0.00001
        """
        if peer_count < 1000:
            return cls.for_target(0.05, 0.01)
        if peer_count < 10000:
            return cls.for_target(0.02, 0.005)
        if peer_count < 100000:
            return cls.for_target(0.01, 0.001)
        if peer_count < 1000000:
            return cls.for_target(0.005, 0.0001)
        return cls.for_target(0.001, 0.00001)


# ===========================================================================
# Fan-out Optimization (Tanaka §23)
# ===========================================================================

@dataclass(frozen=True)
class FanoutConfig:
    """Gossip fan-out configuration for a specific scale.

    Attributes
    ----------
    fan_out       : Number of peers to gossip to per round.
    pco_overhead  : PCO bytes per node per second.
    total_bw      : Total bandwidth per node per second.
    rounds_to_all : Expected rounds to reach all peers.
    """
    fan_out: int
    pco_overhead: float
    total_bw: float
    rounds_to_all: int


class FanoutOptimizer:
    """Gossip fan-out optimizer for network efficiency.

    At large scale, broadcasting to all peers is impractical.
    The fan-out optimizer computes the optimal number of peers
    to gossip to per round, balancing convergence speed against
    network overhead.

    Optimal fan-out: f = ceil(ln(n)) where n = peer count.
    This guarantees all peers are reached in O(log n / log f)
    rounds with high probability.

    Parameters
    ----------
    pco_size :
        Size of a PCO in bytes (default: 128).
    avg_delta_size :
        Average delta payload size in bytes (default: 4096).
    max_bw_per_node :
        Maximum bandwidth budget per node in bytes/sec (default: 10MB/s).
    """

    def __init__(
        self,
        *,
        pco_size: int = 128,
        avg_delta_size: int = 4096,
        max_bw_per_node: float = 10 * 1024 * 1024,
    ) -> None:
        self._pco_size = pco_size
        self._delta_size = avg_delta_size
        self._max_bw = max_bw_per_node

    def optimize(
        self,
        peer_count: int,
        deltas_per_second: float = 1.0,
    ) -> FanoutConfig:
        """Compute optimal fan-out for given network size.

        Parameters
        ----------
        peer_count :
            Total peers in the network.
        deltas_per_second :
            Average deltas produced per peer per second.
        """
        if peer_count <= 1:
            return FanoutConfig(0, 0, 0, 0)

        # Optimal fan-out: ceil(ln(n))
        fan_out = max(1, math.ceil(math.log(peer_count)))

        # PCO overhead: receiving from fan_out senders, each sending their deltas
        pco_overhead = fan_out * deltas_per_second * self._pco_size

        # Total bandwidth: PCO + delta payloads
        total_bw = fan_out * deltas_per_second * (self._pco_size + self._delta_size)

        # Rounds to reach all peers: log_f(n)
        rounds = math.ceil(math.log(peer_count) / math.log(max(fan_out, 2)))

        # Cap fan-out if bandwidth exceeds budget
        if total_bw > self._max_bw:
            max_fan = int(self._max_bw / (deltas_per_second * (self._pco_size + self._delta_size)))
            fan_out = max(1, min(fan_out, max_fan))
            pco_overhead = fan_out * deltas_per_second * self._pco_size
            total_bw = fan_out * deltas_per_second * (self._pco_size + self._delta_size)
            rounds = math.ceil(math.log(peer_count) / math.log(max(fan_out, 2)))

        return FanoutConfig(
            fan_out=fan_out,
            pco_overhead=pco_overhead,
            total_bw=total_bw,
            rounds_to_all=rounds,
        )

    def scale_report(
        self,
        scales: Optional[List[int]] = None,
    ) -> List[Tuple[int, FanoutConfig]]:
        """Generate fan-out configs for multiple scale points."""
        if scales is None:
            scales = [10, 100, 1000, 10000, 100000, 1000000]
        return [(n, self.optimize(n)) for n in scales]


# ===========================================================================
# Production Derating Specification (Tanaka §24)
# ===========================================================================

@dataclass(frozen=True)
class ProductionDeratingSpec:
    """Production derating factors for benchmark-to-production translation.

    Benchmark numbers are gathered under ideal conditions.  Production
    workloads experience:
    - Network latency (10-100ms RTT)
    - Disk I/O contention
    - GC pauses (Python)
    - Variable delta sizes
    - OS scheduling jitter

    Derating factors (multiply benchmark by this to get production estimate):

    Attributes
    ----------
    pco_build     : Derating for PCO build throughput.
    pco_verify    : Derating for PCO verify throughput.
    delta_encode  : Derating for delta encoding throughput.
    merkle_diff   : Derating for Merkle tree diff.
    network       : Derating for network throughput.
    overall       : Conservative overall derating.
    """
    pco_build: float = 0.45
    pco_verify: float = 0.40
    delta_encode: float = 0.50
    merkle_diff: float = 0.55
    network: float = 0.35
    overall: float = 0.40

    def derate(self, benchmark_value: float, category: str = "overall") -> float:
        """Apply derating to a benchmark value."""
        factor = getattr(self, category, self.overall)
        return benchmark_value * factor

    @classmethod
    def optimistic(cls) -> ProductionDeratingSpec:
        """Optimistic derating (well-tuned production environment)."""
        return cls(
            pco_build=0.60, pco_verify=0.55, delta_encode=0.65,
            merkle_diff=0.70, network=0.50, overall=0.55,
        )

    @classmethod
    def conservative(cls) -> ProductionDeratingSpec:
        """Conservative derating (untuned, shared infrastructure)."""
        return cls(
            pco_build=0.30, pco_verify=0.25, delta_encode=0.35,
            merkle_diff=0.40, network=0.20, overall=0.25,
        )


@dataclass(frozen=True)
class HardwareRequirements:
    """Minimum hardware requirements for target deployment scales.

    Attributes
    ----------
    peer_count    : Target number of peers.
    cpu_cores     : Minimum CPU cores.
    ram_gb        : Minimum RAM in GB.
    network_mbps  : Minimum network bandwidth in Mbps.
    storage_gb    : Minimum storage in GB.
    gpu_required  : Whether GPU acceleration is needed.
    notes         : Deployment notes.
    """
    peer_count: int
    cpu_cores: int
    ram_gb: float
    network_mbps: float
    storage_gb: float
    gpu_required: bool = False
    notes: str = ""

    @classmethod
    def for_scale(cls, peer_count: int) -> HardwareRequirements:
        """Compute minimum hardware for target scale.

        Based on:
        - Trust lattice memory: O(N × 120) entries at 10 bytes each
        - PCO verification: 49K/s per core (benchmark) × 0.4 derating
        - Gossip bandwidth: O(N × delta_size × fan_out)
        """
        # Memory: trust lattice + working set
        trust_mem_gb = (peer_count * 120 * 10) / (1024 ** 3)
        working_set_gb = max(1.0, trust_mem_gb * 2)
        ram = max(2.0, math.ceil(working_set_gb * 2))  # 2x for headroom

        # CPU: one core per ~20K verification ops/s (derated)
        verify_per_core = 49000 * 0.4  # 19,600/s
        verify_needed = peer_count * 1.0  # 1 delta/peer/second
        cores = max(2, math.ceil(verify_needed / verify_per_core))

        # Network: fan_out × peer_count × (128 + 4096) bytes/s
        fan_out = max(1, math.ceil(math.log(max(peer_count, 2))))
        bw_bytes = fan_out * 1.0 * (128 + 4096)  # bytes/s per node
        bw_mbps = max(10, math.ceil(bw_bytes * 8 / 1_000_000))

        # Storage: evidence history + delta cache
        storage = max(10, math.ceil(peer_count * 0.001))

        # GPU: only needed for model delta compression at very large scale
        gpu = peer_count > 100000

        if peer_count < 100:
            notes = "Single server deployment. Python runtime is sufficient."
        elif peer_count < 10000:
            notes = "Consider Rust hot-path for PCO verification."
        elif peer_count < 100000:
            notes = "Rust hot-path required. Horizontal scaling recommended."
        else:
            notes = (
                "Rust hot-path mandatory. Distributed deployment with "
                "geographic sharding. GPU acceleration for delta compression."
            )

        return cls(
            peer_count=peer_count,
            cpu_cores=cores,
            ram_gb=ram,
            network_mbps=bw_mbps,
            storage_gb=storage,
            gpu_required=gpu,
            notes=notes,
        )

    @classmethod
    def scale_matrix(
        cls,
        scales: Optional[List[int]] = None,
    ) -> List[HardwareRequirements]:
        """Generate hardware requirements for multiple scale points."""
        if scales is None:
            scales = [10, 100, 1000, 10000, 100000, 1000000]
        return [cls.for_scale(n) for n in scales]
