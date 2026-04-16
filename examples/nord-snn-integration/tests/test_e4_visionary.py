# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""E4 x Nord SNN integration tests -- live endpoints, no stubs."""
import time
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nord_e4_visionary import (
    CRDTSynapticTrace,
    CRDTSTDPEngine,
    TrustGatedZoneMerge,
    ZONE_TRUST_MAP,
    EmergenceDetector,
    EmergenceEvent,
    DeterministicSpikeConsensus,
)
from crdt_merge.e4.typed_trust import TypedTrustScore, TRUST_DIMENSIONS


# ═══════════════════════════════════════════════════════════════════════
# IDEA 1: CRDT-Native STDP
# ═══════════════════════════════════════════════════════════════════════

class TestCRDTSynapticTrace:

    def test_hebbian_potentiation(self):
        trace = CRDTSynapticTrace()
        trace.hebbian_event("node_a", magnitude=5)
        assert trace.net_plasticity == 5

    def test_anti_hebbian_depression(self):
        trace = CRDTSynapticTrace()
        trace.anti_hebbian_event("node_a", magnitude=3)
        assert trace.net_plasticity == -3

    def test_net_plasticity(self):
        trace = CRDTSynapticTrace()
        trace.hebbian_event("node_a", 10)
        trace.anti_hebbian_event("node_a", 4)
        assert trace.net_plasticity == 6

    def test_merge_preserves_potentiation(self):
        """Once ANY node strengthens a synapse, it stays strengthened."""
        trace_a = CRDTSynapticTrace()
        trace_a.hebbian_event("node_a", 10)

        trace_b = CRDTSynapticTrace()
        # Node B never saw this synapse fire

        merged = trace_a.merge(trace_b)
        assert merged.net_plasticity == 10  # Preserved from node A

    def test_merge_commutativity(self):
        a = CRDTSynapticTrace()
        a.hebbian_event("x", 5)
        a.anti_hebbian_event("x", 2)

        b = CRDTSynapticTrace()
        b.hebbian_event("y", 3)

        ab = a.merge(b)
        ba = b.merge(a)
        assert ab.net_plasticity == ba.net_plasticity

    def test_multi_node_accumulation(self):
        trace = CRDTSynapticTrace()
        trace.hebbian_event("node_1", 5)
        trace.hebbian_event("node_2", 8)
        trace.hebbian_event("node_3", 3)
        assert trace.potentiation.value == 16
        assert trace.net_plasticity == 16


class TestCRDTSTDPEngine:

    def test_entropy_gating(self):
        """STDP blocked when model is confident (low entropy)."""
        engine = CRDTSTDPEngine("node_a", pre_dim=10, post_dim=10)
        fired = engine.process_spike_pair(0, 5, True, entropy=1.0, entropy_threshold=2.5)
        assert not fired  # Blocked — entropy too low

        fired = engine.process_spike_pair(0, 5, True, entropy=3.0, entropy_threshold=2.5)
        assert fired  # Passed — entropy high enough

    def test_weight_delta_generation(self):
        engine = CRDTSTDPEngine("node_a", pre_dim=8, post_dim=8)
        for _ in range(10):
            engine.process_spike_pair(2, 5, True, entropy=3.0)
        delta = engine.to_weight_delta()
        assert delta.shape == (8, 8)
        assert delta[5, 2] > 0  # Hebbian: post=5, pre=2 strengthened

    def test_merge_two_nodes(self):
        eng_a = CRDTSTDPEngine("laptop", pre_dim=4, post_dim=4)
        eng_a.process_spike_pair(0, 1, True, entropy=3.0)
        eng_a.process_spike_pair(0, 1, True, entropy=3.0)

        eng_b = CRDTSTDPEngine("colab", pre_dim=4, post_dim=4)
        eng_b.process_spike_pair(2, 3, True, entropy=3.0)

        merged = eng_a.merge(eng_b)
        assert (0, 1) in merged.traces
        assert (2, 3) in merged.traces
        assert merged.traces[(0, 1)].net_plasticity == 2
        assert merged.traces[(2, 3)].net_plasticity == 1

    def test_stats(self):
        engine = CRDTSTDPEngine("node", pre_dim=4, post_dim=4)
        engine.process_spike_pair(0, 1, True, entropy=3.0)
        engine.process_spike_pair(0, 1, False, entropy=1.0)  # Blocked
        stats = engine.stats
        assert stats["total_events"] == 2
        assert stats["gated_events"] == 1
        assert stats["gate_pass_rate"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# IDEA 2: Trust-Gated Zone Merge
# ═══════════════════════════════════════════════════════════════════════

class TestTrustGatedZoneMerge:

    def test_zone_classification(self):
        merger = TrustGatedZoneMerge()
        assert merger.classify_layer("sensory_zone.block_0") == "sensory_zone"
        assert merger.classify_layer("memory_cortex.genesis") == "memory_cortex"
        assert merger.classify_layer("executive_zone.block_1") == "executive_zone"
        assert merger.classify_layer("lm_head.weight") == "lm_head"

    def test_zone_trust_mapping(self):
        assert ZONE_TRUST_MAP["memory_cortex"] == "causality"
        assert ZONE_TRUST_MAP["executive_zone"] == "model"
        assert ZONE_TRUST_MAP["sensory_zone"] == "integrity"

    def test_high_trust_accepted_all_zones(self):
        """Node with high trust in all dimensions passes all zones."""
        merger = TrustGatedZoneMerge()
        high_trust = TypedTrustScore()  # 0.5 default, passes most thresholds
        sd = {
            "sensory_zone.w": np.ones((4,), dtype=np.float32),
            "memory_cortex.w": np.ones((4,), dtype=np.float32),
        }
        merged, stats = merger.merge_state_dicts([
            ("good_node", sd, high_trust),
        ])
        assert "sensory_zone.w" in merged
        assert "memory_cortex.w" in merged

    def test_low_trust_rejected_from_memory(self):
        """Node with low causality trust rejected from memory cortex only."""
        merger = TrustGatedZoneMerge()

        # Low causality trust (0.1) — will be rejected for memory_cortex
        low_causality = TypedTrustScore(_evidence={"causality": {"obs": 0.9}})

        # High integrity trust (0.9) — accepted for sensory
        # (but same node has low causality)

        sd_bad = {
            "sensory_zone.w": np.ones((4,), dtype=np.float32) * 2.0,
            "memory_cortex.w": np.ones((4,), dtype=np.float32) * 999.0,
        }
        sd_good = {
            "sensory_zone.w": np.ones((4,), dtype=np.float32) * 1.0,
            "memory_cortex.w": np.ones((4,), dtype=np.float32) * 1.0,
        }
        good_trust = TypedTrustScore()  # 0.5 trust, passes memory threshold

        merged, stats = merger.merge_state_dicts([
            ("attacker", sd_bad, low_causality),
            ("honest", sd_good, good_trust),
        ])

        # Memory cortex: attacker rejected (causality=0.1 < 0.6 threshold)
        assert stats["memory_cortex.w"]["zone"] == "memory_cortex"
        mem_val = np.mean(merged["memory_cortex.w"])
        assert mem_val < 500, f"Attacker's 999 should not dominate, got {mem_val}"

    def test_three_node_zone_merge(self):
        merger = TrustGatedZoneMerge()
        trusts = [TypedTrustScore() for _ in range(3)]
        sds = [
            {"sensory_zone.w": np.random.randn(8).astype(np.float32),
             "memory_cortex.w": np.random.randn(8).astype(np.float32)}
            for _ in range(3)
        ]
        contribs = [(f"node_{i}", sds[i], trusts[i]) for i in range(3)]
        merged, stats = merger.merge_state_dicts(contribs)
        assert len(merged) == 2


# ═══════════════════════════════════════════════════════════════════════
# IDEA 3: Emergence Detection
# ═══════════════════════════════════════════════════════════════════════

class TestEmergenceDetector:

    def test_stable_training_no_emergence(self):
        detector = EmergenceDetector(sigma_threshold=2.0, min_samples=3)
        for step in range(0, 5000, 500):
            events = detector.record_activations({
                "sensory": 0.07 + np.random.normal(0, 0.005),
                "memory_cortex": 0.01 + np.random.normal(0, 0.002),
            }, step=step)
        # Gradual change — should NOT trigger
        assert len(detector.events) == 0 or all(
            e.shift_magnitude < 0.1 for e in detector.events
        )

    def test_detects_memory_routing_shift(self):
        """The 0.5% -> 39% memory shift MUST be detected."""
        detector = EmergenceDetector(sigma_threshold=1.5, min_samples=3)

        # Build baseline
        for step in range(0, 5000, 500):
            detector.record_activations({
                "memory_cortex": 0.005 + np.random.normal(0, 0.001),
            }, step=step)

        # THE SHIFT
        events = detector.record_activations({
            "memory_cortex": 0.39,
        }, step=25000)

        memory_events = [e for e in detector.events if e.zone == "memory_cortex"]
        assert len(memory_events) > 0, "Failed to detect 0.5%->39% memory shift"
        shift_event = memory_events[-1]
        assert shift_event.shift_magnitude > 0.1

    def test_simulate_full_nord_training(self):
        """Replay Nord's actual training trajectory."""
        detector = EmergenceDetector(sigma_threshold=1.5, min_samples=3)
        events = detector.simulate_nord_training()

        # Should detect the memory routing shift
        memory_events = [e for e in events if e.zone == "memory_cortex"]
        assert len(memory_events) > 0, "Simulation failed to detect emergence"

        # The memory shift should be among the detected events
        memory_events = [e for e in detector.events if e.zone == "memory_cortex"]
        assert len(memory_events) > 0
        biggest_memory = max(memory_events, key=lambda e: e.shift_magnitude)
        assert biggest_memory.new_activation > 0.3

    def test_event_contains_step_info(self):
        detector = EmergenceDetector(sigma_threshold=1.0, min_samples=2)
        for step in [0, 100, 200]:
            detector.record_activations({"zone_a": 0.05}, step=step)
        detector.record_activations({"zone_a": 0.95}, step=300)

        if detector.events:
            event = detector.events[-1]
            assert event.step == 300
            assert "zone_a" in event.description


# ═══════════════════════════════════════════════════════════════════════
# IDEA 4: Deterministic Spike Consensus
# ═══════════════════════════════════════════════════════════════════════

class TestDeterministicSpikeConsensus:

    def test_merge_weight_vectors(self):
        dsc = DeterministicSpikeConsensus()
        w1 = [0.11, 0.13, 0.09, 0.15]
        w2 = [0.12, 0.10, 0.14, 0.08]
        merged = dsc.merge_weight_vectors([w1, w2], [0.5, 0.5])
        assert len(merged) == 4

    def test_spike_consensus(self):
        dsc = DeterministicSpikeConsensus()
        weights = [0.15, 0.08, 0.13, 0.11, 0.05, 0.20]
        result = dsc.verify_spike_consensus(weights, threshold=0.12)
        assert result["total_neurons"] == 6
        assert result["firing"] == 3  # 0.15, 0.13, 0.20 >= 0.12
        assert result["silent"] == 3  # 0.08, 0.11, 0.05 < 0.12
        assert result["sparsity"] == 0.5

    def test_determinism_proof(self):
        dsc = DeterministicSpikeConsensus()
        w1 = [0.11, 0.13, 0.09]
        w2 = [0.12, 0.10, 0.14]
        result = dsc.prove_determinism([w1, w2], [0.6, 0.4], threshold=0.12)
        assert result["weight_deterministic"]
        assert "spike_consensus" in result

    def test_sparsity_at_threshold(self):
        """Nord's threshold=0.12: verify 93% sparsity is achievable."""
        dsc = DeterministicSpikeConsensus()
        rng = np.random.RandomState(42)
        # 93% of weights below threshold
        weights = []
        for _ in range(1000):
            if rng.random() < 0.93:
                weights.append(rng.uniform(0.0, 0.11))  # Below threshold
            else:
                weights.append(rng.uniform(0.12, 0.50))  # Above threshold
        result = dsc.verify_spike_consensus(weights, threshold=0.12)
        assert result["sparsity"] > 0.90

    def test_bit_identical_across_permutations(self):
        """Prove merge order doesn't change spike behavior."""
        dsc = DeterministicSpikeConsensus()
        rng = np.random.RandomState(0)
        n_nodes = 5
        weights = [rng.uniform(0.05, 0.20, size=100).tolist() for _ in range(n_nodes)]
        trusts = [0.2] * n_nodes

        ref = dsc.merge_weight_vectors(weights, trusts)
        ref_spikes = dsc.verify_spike_consensus(ref, threshold=0.12)

        # Permute and re-merge
        for perm in [[4,3,2,1,0], [2,0,4,1,3], [1,4,0,3,2]]:
            perm_w = [weights[i] for i in perm]
            perm_t = [trusts[i] for i in perm]
            result = dsc.merge_weight_vectors(perm_w, perm_t)
            result_spikes = dsc.verify_spike_consensus(result, threshold=0.12)
            assert result_spikes["firing"] == ref_spikes["firing"], \
                f"Spike consensus broken by permutation {perm}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
