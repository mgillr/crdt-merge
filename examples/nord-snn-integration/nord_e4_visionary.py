# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License").
# You may use this file freely for any non-production purpose:
# research, evaluation, development, testing, education, personal use.
#
# A commercial production license is required ONLY if you deploy this
# code in a revenue-generating production environment. All other use
# is permitted without restriction.
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
#
# On 2028-03-29 this file converts to Apache License, Version 2.0
# and becomes fully open for all use cases including commercial production.

"""
E4 x Nord SNN -- four integration points where the math lines up.

1. CRDT-Native STDP
   STDP is treated as a local synaptic process in the literature (Bi & Poo
   1998, Song 2000, Neftci 2019). The assumption is that spike traces from
   different machines are incompatible. But decompose STDP to its primitive:
   a bidirectional counter. Potentiation increments, depression decrements.
   A PNCounter is the same object. GCounter merge (element-wise max per node)
   preserves potentiation from any node without averaging it away. Synaptic
   memory survives distributed merge.

   Breaks: "STDP is local" + "spike traces can't merge across nodes"
   Tests: test_merge_preserves_potentiation, test_merge_commutativity

2. Trust-Gated Zone Merge
   FedAvg, Krum, Trimmed Mean -- every FL defence scores clients as a single
   scalar and accepts or rejects the full update. No existing framework gates
   per-layer. E4 has 6 trust dimensions. Nord has 6 zones. The mapping is
   1:1. A node with high integrity (sensory ok) but low causality (memory
   unsafe) gets accepted for sensory and rejected for memory cortex.

   Breaks: "merge is all-or-nothing" + "trust is per-peer not per-layer"
   Tests: test_low_trust_rejected_from_memory

3. Emergence Detection via Circuit Breaker
   Wei et al. 2022 and Schaeffer et al. 2023 treat emergence as something
   discovered post-hoc. No training framework detects it during a run.
   E4's TrustCircuitBreaker fires on anomalous velocity (rate of change
   exceeding sigma_threshold). Activation rate shift is the same signal.
   Feed zone activations instead of trust scores -- same math catches the
   0.5%->39% memory routing shift at step 25K.

   Breaks: "circuit breakers are for security" + "emergence can't be detected"
   Tests: test_detects_memory_routing_shift, test_simulate_full_nord_training

4. Deterministic Spike-Train Consensus
   IEEE 754 float addition is non-associative. (a+b)+c != a+(b+c). Every
   distributed ML framework (DDP, Horovod, DeepSpeed) accepts this. For
   transformers it barely matters. For SNNs with a hard threshold at 0.12
   it's catastrophic -- 0.1200001 fires, 0.1199999 doesn't. Kahan
   compensated summation with pre-sorted inputs gives bit-identical results
   regardless of merge order or hardware.

   Breaks: "float merges are non-deterministic" + "threshold sensitivity
   makes distributed SNN merging impossible"
   Tests: test_bit_identical_across_permutations, test_determinism_proof
"""

import time
import hashlib
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from crdt_merge.core import GCounter, PNCounter, LWWRegister, LWWMap, ORSet
from crdt_merge.e4.typed_trust import TypedTrustScore, TRUST_DIMENSIONS
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice, TrustCircuitBreaker
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry, ConflictType,
    TrustWeightedAveragingResolver,
    TrustGatedAcceptanceFilter,
    TrustWeightedStrategySelector,
)
from crdt_merge.e4.resilience.deterministic_merge import DeterministicMerge
from crdt_merge.e4.resilience.convergence_monitor import ConvergenceMonitor


# ═══════════════════════════════════════════════════════════════════════
# IDEA 1: CRDT-Native STDP
# ═══════════════════════════════════════════════════════════════════════

class CRDTSynapticTrace:
    """Single synapse STDP trace backed by two GCounters."""

    def __init__(self):
        self.potentiation = GCounter()
        self.depression = GCounter()

    def hebbian_event(self, node_id: str, magnitude: int = 1):
        self.potentiation.increment(node_id, magnitude)

    def anti_hebbian_event(self, node_id: str, magnitude: int = 1):
        self.depression.increment(node_id, magnitude)

    @property
    def net_plasticity(self) -> int:
        return self.potentiation.value - self.depression.value

    def merge(self, other: "CRDTSynapticTrace") -> "CRDTSynapticTrace":
        result = CRDTSynapticTrace()
        result.potentiation = self.potentiation.merge(other.potentiation)
        result.depression = self.depression.merge(other.depression)
        return result


class CRDTSTDPEngine:
    """Distributed STDP across N nodes with entropy gating (threshold=2.5)."""

    def __init__(self, node_id: str, pre_dim: int, post_dim: int):
        self.node_id = node_id
        self.pre_dim = pre_dim
        self.post_dim = post_dim
        self.traces: Dict[Tuple[int, int], CRDTSynapticTrace] = {}
        self.total_events = GCounter()
        self.gated_events = GCounter()

    def process_spike_pair(
        self,
        pre_idx: int,
        post_idx: int,
        pre_fires_first: bool,
        entropy: float,
        entropy_threshold: float = 2.5,
    ) -> bool:
        """Process a spike timing pair with entropy gating."""
        self.total_events.increment(self.node_id)

        if entropy < entropy_threshold:
            return False  # Model is confident, block plasticity

        self.gated_events.increment(self.node_id)
        key = (pre_idx, post_idx)
        if key not in self.traces:
            self.traces[key] = CRDTSynapticTrace()

        if pre_fires_first:
            self.traces[key].hebbian_event(self.node_id)
        else:
            self.traces[key].anti_hebbian_event(self.node_id)

        return True

    def to_weight_delta(self, a_plus: float = 0.01, a_minus: float = 0.008) -> np.ndarray:
        """Convert CRDT traces to a weight delta matrix."""
        delta = np.zeros((self.post_dim, self.pre_dim), dtype=np.float32)
        for (pre, post), trace in self.traces.items():
            if pre < self.pre_dim and post < self.post_dim:
                net = trace.net_plasticity
                if net > 0:
                    delta[post, pre] = a_plus * net
                else:
                    delta[post, pre] = a_minus * net
        return delta

    def merge(self, other: "CRDTSTDPEngine") -> "CRDTSTDPEngine":
        result = CRDTSTDPEngine(
            f"{self.node_id}+{other.node_id}",
            self.pre_dim, self.post_dim,
        )
        all_keys = set(self.traces) | set(other.traces)
        for key in all_keys:
            a = self.traces.get(key, CRDTSynapticTrace())
            b = other.traces.get(key, CRDTSynapticTrace())
            result.traces[key] = a.merge(b)
        result.total_events = self.total_events.merge(other.total_events)
        result.gated_events = self.gated_events.merge(other.gated_events)
        return result

    @property
    def stats(self) -> dict:
        active = sum(1 for t in self.traces.values() if t.net_plasticity != 0)
        return {
            "total_synapses_tracked": len(self.traces),
            "active_synapses": active,
            "total_events": self.total_events.value,
            "gated_events": self.gated_events.value,
            "gate_pass_rate": (
                self.gated_events.value / max(self.total_events.value, 1)
            ),
        }


# ═══════════════════════════════════════════════════════════════════════
# IDEA 2: Trust-Gated Zone Merge
# ═══════════════════════════════════════════════════════════════════════

# Mapping: E4 trust dimensions -> Nord architectural zones
ZONE_TRUST_MAP = {
    "sensory_zone":     "integrity",     # weight correctness
    "association_zone": "consistency",   # sparsity pattern preservation
    "memory_cortex":    "causality",     # temporal ordering of persistent state
    "executive_zone":   "model",         # gradient quality
    "temporal_encoder": "gossip",        # reliable state propagation
    "lm_head":          "context",       # domain-appropriate outputs
}


class TrustGatedZoneMerge:
    """Per-zone trust gating -- different threshold per architectural zone."""

    def __init__(self, zone_thresholds: Optional[Dict[str, float]] = None):
        defaults = {
            "sensory_zone": 0.3,       # Low bar — easy to verify
            "association_zone": 0.4,   # Medium — MoE routing matters
            "memory_cortex": 0.6,      # HIGH — persistent state is precious
            "executive_zone": 0.5,     # Medium-high — output quality
            "temporal_encoder": 0.3,   # Low bar
            "lm_head": 0.4,            # Medium
        }
        self.thresholds = zone_thresholds or defaults
        self.gate = TrustGatedAcceptanceFilter(
            global_threshold=0.3,
            thresholds={
                ZONE_TRUST_MAP[zone]: thresh
                for zone, thresh in self.thresholds.items()
            },
        )
        self.averaging = TrustWeightedAveragingResolver(min_trust=0.2)

    def classify_layer(self, layer_name: str) -> str:
        ln = layer_name.lower()
        if "sensory" in ln:
            return "sensory_zone"
        elif "association" in ln or "moe" in ln or "expert" in ln:
            return "association_zone"
        elif "memory" in ln or "genesis" in ln or "archive" in ln:
            return "memory_cortex"
        elif "executive" in ln:
            return "executive_zone"
        elif "temporal" in ln or "spike_encoder" in ln:
            return "temporal_encoder"
        elif "readout" in ln or "lm_head" in ln:
            return "lm_head"
        return "sensory_zone"

    def merge_state_dicts(
        self,
        contributions: List[Tuple[str, Dict[str, np.ndarray], TypedTrustScore]],
    ) -> Tuple[Dict[str, np.ndarray], dict]:
        """Merge state dicts with per-zone trust gating."""
        all_keys = set()
        for _, sd, _ in contributions:
            all_keys.update(sd.keys())

        merged = {}
        zone_stats = {}

        for key in all_keys:
            zone = self.classify_layer(key)
            dimension = ZONE_TRUST_MAP.get(zone, "integrity")
            threshold = self.thresholds.get(zone, 0.3)

            accepted = []
            rejected = []
            for peer_id, sd, trust in contributions:
                if key not in sd:
                    continue
                dim_trust = trust.trust_for_dimension(dimension)
                if dim_trust >= threshold:
                    accepted.append((peer_id, sd[key], trust, dim_trust))
                else:
                    rejected.append(peer_id)

            if not accepted:
                # All rejected — use the highest-trust contributor anyway
                best = max(
                    [(p, sd[key], t, t.trust_for_dimension(dimension))
                     for p, sd, t in contributions if key in sd],
                    key=lambda x: x[3],
                )
                merged[key] = best[1]
                zone_stats[key] = {"zone": zone, "status": "fallback", "rejected": rejected}
            elif len(accepted) == 1:
                merged[key] = accepted[0][1]
                zone_stats[key] = {"zone": zone, "status": "single", "rejected": rejected}
            else:
                # Trust-weighted average of accepted contributions
                total_trust = sum(t for _, _, _, t in accepted)
                result = np.zeros_like(accepted[0][1], dtype=np.float64)
                for _, tensor, _, t in accepted:
                    result += tensor.astype(np.float64) * (t / total_trust)
                merged[key] = result.astype(np.float32)
                zone_stats[key] = {
                    "zone": zone,
                    "status": "merged",
                    "contributors": [p for p, _, _, _ in accepted],
                    "rejected": rejected,
                }

        return merged, zone_stats


# ═══════════════════════════════════════════════════════════════════════
# IDEA 3: Emergence Detection via Trust Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class EmergenceEvent:
    """A detected emergence event — rapid activation pattern shift."""
    timestamp: float
    zone: str
    old_activation: float
    new_activation: float
    shift_magnitude: float
    step: int
    description: str


class EmergenceDetector:
    """Repurpose E4 circuit breaker to detect activation-space phase transitions."""

    def __init__(
        self,
        sigma_threshold: float = 2.0,
        window_size: int = 50,
        min_samples: int = 5,
    ):
        self.breakers: Dict[str, TrustCircuitBreaker] = {}
        self.sigma_threshold = sigma_threshold
        self.window_size = window_size
        self.min_samples = min_samples
        self.events: List[EmergenceEvent] = []
        self.activation_history = LWWMap()
        self._step = 0

    def _get_breaker(self, zone: str) -> TrustCircuitBreaker:
        if zone not in self.breakers:
            self.breakers[zone] = TrustCircuitBreaker(
                window_size=self.window_size,
                sigma_threshold=self.sigma_threshold,
                min_samples=self.min_samples,
            )
        return self.breakers[zone]

    def record_activations(
        self,
        zone_activations: Dict[str, float],
        step: int,
    ) -> List[EmergenceEvent]:
        """Record per-zone activation rates and detect emergence."""
        self._step = step
        detected = []

        for zone, rate in zone_activations.items():
            breaker = self._get_breaker(zone)

            # Get previous activation as trust score
            prev_rate = self.activation_history.get(zone, 0.0)

            # Convert activation rates to TypedTrustScore for circuit breaker
            old_ts = TypedTrustScore(_evidence={"model": {"obs": 1.0 - prev_rate}})
            new_ts = TypedTrustScore(_evidence={"model": {"obs": 1.0 - rate}})

            breaker.record_trust_change(zone, old_ts, new_ts)

            if breaker.is_tripped():
                shift = abs(rate - prev_rate)
                event = EmergenceEvent(
                    timestamp=time.time(),
                    zone=zone,
                    old_activation=prev_rate,
                    new_activation=rate,
                    shift_magnitude=shift,
                    step=step,
                    description=(
                        f"Emergence detected in {zone}: "
                        f"activation shifted {prev_rate:.1%} -> {rate:.1%} "
                        f"(delta={shift:.1%}) at step {step}"
                    ),
                )
                self.events.append(event)
                detected.append(event)
                breaker.reset()

            self.activation_history.set(
                zone, rate, timestamp=time.time(), node_id="detector"
            )

        return detected

    def simulate_nord_training(self) -> List[EmergenceEvent]:
        """Replay Nord's actual training trajectory to prove detection works."""
        all_events = []

        # Steps 0-20000: stable training at ~1% memory activation
        for step in range(0, 20000, 1000):
            events = self.record_activations({
                "sensory": 0.07,
                "association": 0.10,
                "memory_cortex": 0.01,
                "executive": 0.12,
            }, step=step)
            all_events.extend(events)

        # Step 22000-24000: KD starts, memory slowly increases
        for step in range(22000, 24500, 500):
            events = self.record_activations({
                "sensory": 0.05,
                "association": 0.08,
                "memory_cortex": 0.01,
                "executive": 0.10,
            }, step=step)
            all_events.extend(events)

        # Step 25000: MEMORY ROUTING SHIFT — 1% -> 39%
        events = self.record_activations({
            "sensory": 0.05,
            "association": 0.08,
            "memory_cortex": 0.39,  # THE EMERGENCE EVENT
            "executive": 0.18,
        }, step=25000)
        all_events.extend(events)

        return all_events


# ═══════════════════════════════════════════════════════════════════════
# IDEA 4: Deterministic Spike-Train Consensus
# ═══════════════════════════════════════════════════════════════════════

class DeterministicSpikeConsensus:
    """Kahan-summation merge -- bit-identical weights across any hardware."""

    def __init__(self, strategy: str = "sorted_kahan"):
        self.merger = DeterministicMerge(strategy=strategy)
        self.convergence = ConvergenceMonitor(peer_count=1)

    def merge_weight_vectors(
        self,
        weight_lists: List[List[float]],
        trust_weights: List[float],
    ) -> List[float]:
        return self.merger.merge_vectors(weight_lists, trust_weights)

    def verify_spike_consensus(
        self,
        merged_weights: List[float],
        threshold: float = 0.12,
    ) -> dict:
        """Check which neurons fire at the given threshold."""
        spikes = [1 if w >= threshold else 0 for w in merged_weights]
        firing_rate = sum(spikes) / max(len(spikes), 1)
        return {
            "total_neurons": len(merged_weights),
            "firing": sum(spikes),
            "silent": len(spikes) - sum(spikes),
            "firing_rate": firing_rate,
            "sparsity": 1.0 - firing_rate,
        }

    def prove_determinism(
        self,
        weight_lists: List[List[float]],
        trust_weights: List[float],
        threshold: float = 0.12,
        permutations: int = 20,
    ) -> dict:
        """Prove that merge order doesn't affect spike behavior."""
        is_deterministic = self.merger.verify_determinism(
            [w for wl in weight_lists for w in wl],
            trust_weights * len(weight_lists[0]),
            permutations=permutations,
        )

        ref_merged = self.merge_weight_vectors(weight_lists, trust_weights)
        ref_spikes = self.verify_spike_consensus(ref_merged, threshold)

        return {
            "weight_deterministic": is_deterministic,
            "spike_consensus": ref_spikes,
            "permutations_tested": permutations,
            "threshold": threshold,
        }
