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
# On 2028-03-29 the code license converts to Apache 2.0. Patent rights
# are separately held
# (UK Application No. GB 2607132.4, GB2608127.3) and are not granted by the
# license. Commercial use of patented methods requires a patent license.

"""Tests for 5 gap modules -- live crdt-merge endpoints."""
import time
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nord_gap1_frozen_specialist import (
    FrozenSpecialist, FrozenSpecialistRegistry, NordFreezeAfterEmergence,
)
from nord_gap2_phase_transition import PhaseTransitionMeasurer, PhaseTransitionFit
from nord_gap3_sheaf_merge import (
    STDPCoherenceScorer, sheaf_glue_merge, compute_k_effective, NordSheafMerge,
)
from nord_gap4_scip_memory import SCIPMemoryManager, MemoryEntry, MemoryType
from nord_gap5_immune_detection import NordImmuneSystem, AnomalyType


def make_weights(seed=42, dim=16):
    rng = np.random.RandomState(seed)
    return {f"layer_{i}.w": rng.randn(dim, dim).astype(np.float32) * 0.1 for i in range(4)}


# ================================================================
# GAP 1: Frozen Specialist
# ================================================================

class TestFrozenSpecialist:

    def test_freeze_creates_immutable_snapshot(self):
        reg = FrozenSpecialistRegistry()
        w = make_weights(seed=1)
        spec = reg.freeze_and_register("spec_1", w, step=25000, capability="cross_lingual_russian")
        assert spec.content_hash
        assert reg.count == 1
        assert "cross_lingual_russian" in reg.capabilities

    def test_frozen_weights_unchanged_after_merge(self):
        reg = FrozenSpecialistRegistry()
        w1 = make_weights(seed=1)
        w2 = make_weights(seed=2)
        reg.freeze_and_register("s1", w1, 100, "cap_a")
        reg.freeze_and_register("s2", w2, 200, "cap_b")

        merged = reg.merge_specialists(["s1", "s2"])
        # Original specialists unchanged
        s1 = reg.get("s1")
        for k in s1.weights:
            np.testing.assert_array_equal(s1.weights[k], w1[k])

    def test_registry_merge_commutativity(self):
        r1 = FrozenSpecialistRegistry()
        r2 = FrozenSpecialistRegistry()
        r1.freeze_and_register("a", make_weights(1), 10, "x")
        r2.freeze_and_register("b", make_weights(2), 20, "y")
        ab = r1.merge_registry(r2)
        ba = r2.merge_registry(r1)
        assert ab.count == ba.count == 2

    def test_freeze_after_emergence(self):
        freezer = NordFreezeAfterEmergence()
        weights = {
            "memory_cortex.genesis.w": np.ones((8, 8), dtype=np.float32),
            "sensory.block.w": np.ones((8, 8), dtype=np.float32) * 2,
        }
        freezer.freeze_zone("memory_cortex", weights, step=25000, capability="russian")
        assert freezer.is_frozen("memory_cortex")
        assert not freezer.is_frozen("sensory")

    def test_merge_new_with_frozen_preserves_emerged(self):
        freezer = NordFreezeAfterEmergence()
        frozen_w = {"memory_cortex.w": np.ones((4,), dtype=np.float32) * 10.0}
        freezer.freeze_zone("memory_cortex", frozen_w, 25000, "russian")

        new_w = {"memory_cortex.w": np.zeros((4,), dtype=np.float32)}
        merged = freezer.merge_new_with_frozen(new_w, frozen_weight=0.7)

        # Frozen gets 70% weight, new gets 30%
        # Result should be closer to 10.0 (frozen) than 0.0 (new)
        assert np.mean(merged["memory_cortex.w"]) > 5.0


# ================================================================
# GAP 2: Phase Transition
# ================================================================

class TestPhaseTransition:

    def test_simulate_nord_finds_memory_transition(self):
        measurer = PhaseTransitionMeasurer()
        results = measurer.simulate_nord_trajectory()
        assert "memory_cortex" in results
        fit = results["memory_cortex"]
        assert fit.critical_step == 25000
        assert fit.exponent_beta > 0
        assert fit.universality_class in ["2D_ising", "3D_ising_percolation", "mean_field", "non_standard"]

    def test_no_transition_in_stable_zone(self):
        measurer = PhaseTransitionMeasurer()
        for step in range(0, 10000, 500):
            measurer.record(step, {"stable_zone": 0.07 + np.random.normal(0, 0.002)})
        fit = measurer.fit_transition("stable_zone")
        # Either no fit or very small critical value
        assert fit is None or fit.critical_value < 0.05

    def test_critical_exponent_in_physical_range(self):
        measurer = PhaseTransitionMeasurer()
        results = measurer.simulate_nord_trajectory()
        if "memory_cortex" in results:
            beta = results["memory_cortex"].exponent_beta
            assert 0.01 <= beta <= 2.0

    def test_history_tracking(self):
        measurer = PhaseTransitionMeasurer()
        measurer.record(0, {"z": 0.1})
        measurer.record(100, {"z": 0.2})
        assert measurer.history_length == 2


# ================================================================
# GAP 3: Sheaf Merge
# ================================================================

class TestSheafMerge:

    def test_coherence_scorer(self):
        scorer = STDPCoherenceScorer(pre_dim=4, post_dim=4)
        # Neuron 0 (pre) always causes neuron 2 (post) to fire
        for _ in range(100):
            pre = np.array([1, 0, 0, 0])
            post = np.array([0, 0, 1, 0])
            scorer.record_spikes(pre, post)
        coh = scorer.coherence_matrix()
        assert coh[2, 0] > 0.9  # strong correlation

    def test_high_coherence_pairs(self):
        scorer = STDPCoherenceScorer(pre_dim=4, post_dim=4)
        for _ in range(50):
            scorer.record_spikes(np.array([1, 0, 0, 0]), np.array([0, 1, 0, 0]))
        pairs = scorer.high_coherence_pairs(threshold=0.3)
        assert any(p.pre_idx == 0 and p.post_idx == 1 for p in pairs)

    def test_sheaf_glue_preserves_correlated(self):
        """High-coherence synapse preserved, low-coherence averaged."""
        w1 = np.array([[0.8, 0.1], [0.1, 0.1]], dtype=np.float32)
        w2 = np.array([[0.2, 0.1], [0.1, 0.1]], dtype=np.float32)

        # Synapse (0,0) has high coherence in contributor 1, low in 2
        coh1 = np.array([[0.9, 0.1], [0.1, 0.1]])
        coh2 = np.array([[0.1, 0.1], [0.1, 0.1]])

        merged = sheaf_glue_merge([w1, w2], [coh1, coh2], coherence_threshold=0.3)

        # Synapse (0,0): contributor 1 has high coherence, should dominate
        assert merged[0, 0] > 0.5  # closer to w1's 0.8 than w2's 0.2

    def test_k_effective(self):
        # Equal coherence: k_eff = n (no information loss)
        scores = [0.5, 0.5, 0.5, 0.5]
        k_eff = compute_k_effective(scores)
        assert k_eff == pytest.approx(0.5)  # sum(0.25)/sum(0.5) = 0.5

        # One dominant: k_eff closer to 1 (one specialist matters)
        scores = [0.9, 0.1, 0.1, 0.1]
        k_eff = compute_k_effective(scores)
        assert k_eff > 0.5  # dominated by the 0.9

    def test_nord_sheaf_merge(self):
        merger = NordSheafMerge()
        merger.register_layer("layer_0.w", pre_dim=8, post_dim=8)
        for _ in range(50):
            pre = (np.random.random(8) > 0.5).astype(np.float32)
            post = (np.random.random(8) > 0.5).astype(np.float32)
            merger.record_spikes("layer_0.w", pre, post)

        sd1 = {"layer_0.w": np.random.randn(8, 8).astype(np.float32)}
        sd2 = {"layer_0.w": np.random.randn(8, 8).astype(np.float32)}
        merged = merger.merge_state_dicts([("a", sd1), ("b", sd2)])
        assert "layer_0.w" in merged
        assert merged["layer_0.w"].shape == (8, 8)


# ================================================================
# GAP 4: SCIP Memory
# ================================================================

class TestSCIPMemory:

    def test_experience_creates_entry(self):
        mgr = SCIPMemoryManager("node_a")
        entry = MemoryEntry(
            entry_id="pat_001", memory_type=MemoryType.PATTERN,
            content_hash="abc123", value={"spike_pattern": [1, 0, 1]},
            source_zone="sensory",
        )
        eid = mgr.experience(entry)
        assert eid == "pat_001"
        assert mgr.stats["experienced"] == 1
        assert mgr.stats["structural_entries"] == 1

    def test_contribute_promotes_to_personal(self):
        mgr = SCIPMemoryManager("node_a")
        entry = MemoryEntry("p1", MemoryType.SKILL, "hash1", {"skill": "language"})
        mgr.experience(entry)
        ok = mgr.contribute("p1")
        assert ok
        assert mgr.stats["contributed"] == 1
        assert mgr.stats["personal_entries"] == 1

    def test_absorb_merges_to_auxiliary(self):
        mgr = SCIPMemoryManager("node_a")
        for i in range(3):
            mgr.experience(MemoryEntry(f"e{i}", MemoryType.PATTERN, f"h{i}", i))
        mid = mgr.absorb(["e0", "e1", "e2"], "merged_0", "merged_hash")
        assert mid == "merged_0"
        assert mgr.stats["auxiliary_entries"] == 1

    def test_evict_removes_from_active(self):
        mgr = SCIPMemoryManager("node_a")
        entry = MemoryEntry("old", MemoryType.CONTEXT, "h", "data")
        mgr.experience(entry)
        assert mgr.stats["active_in_memory"] == 1
        mgr.evict("old")
        assert mgr.stats["active_in_memory"] == 0
        # But registry still has it (add-wins)
        assert "old" in mgr.entry_registry.value

    def test_regenerate_returns_full_state(self):
        mgr = SCIPMemoryManager("node_a")
        mgr.experience(MemoryEntry("e1", MemoryType.PATTERN, "h1", "v1"))
        mgr.contribute("e1")
        state = mgr.regenerate()
        assert "structural" in state
        assert "personal" in state
        assert state["registry_size"] >= 1

    def test_merge_commutativity(self):
        a = SCIPMemoryManager("a")
        b = SCIPMemoryManager("b")
        a.experience(MemoryEntry("e1", MemoryType.PATTERN, "h1", "v1"))
        b.experience(MemoryEntry("e2", MemoryType.SKILL, "h2", "v2"))
        ab = a.merge(b)
        ba = b.merge(a)
        assert ab.stats["experienced"] == ba.stats["experienced"]

    def test_full_lifecycle(self):
        mgr = SCIPMemoryManager("nord")
        # EXPERIENCE
        for i in range(5):
            mgr.experience(MemoryEntry(f"p{i}", MemoryType.PATTERN, f"h{i}", f"v{i}", source_zone="sensory"))
        # CONTRIBUTE top 2
        mgr.contribute("p0")
        mgr.contribute("p1")
        # ABSORB into auxiliary
        mgr.absorb(["p0", "p1"], "merged_01", "mhash")
        # EVICT old
        mgr.evict("p4")
        # REGENERATE
        state = mgr.regenerate()
        stats = mgr.stats
        assert stats["experienced"] == 5
        assert stats["contributed"] == 2
        assert stats["absorbed"] == 1
        assert stats["evicted"] == 1
        assert stats["regenerated"] == 1


# ================================================================
# GAP 5: Immune Detection
# ================================================================

class TestImmuneSystem:

    def test_healthy_zones_no_anomaly(self):
        immune = NordImmuneSystem()
        for step in range(0, 5000, 500):
            events = immune.check_health(
                {"sensory": 0.07, "memory": 0.01, "executive": 0.12},
                step=step,
            )
        assert len(immune.quarantined_zones) == 0

    def test_detect_firing_rate_explosion(self):
        immune = NordImmuneSystem()
        for step in range(0, 3000, 500):
            immune.check_health({"zone_a": 0.07}, step=step)
        events = immune.check_health({"zone_a": 0.60}, step=3000)
        explosions = [e for e in events if e.anomaly_type == AnomalyType.FIRING_RATE_EXPLOSION]
        assert len(explosions) > 0

    def test_detect_dead_zone(self):
        immune = NordImmuneSystem()
        for step in range(0, 5000, 500):
            immune.check_health({"dying_zone": 0.0001}, step=step)
        dead = [e for e in immune.events if e.anomaly_type == AnomalyType.FIRING_RATE_COLLAPSE]
        assert len(dead) > 0

    def test_quarantine_on_severe_anomaly(self):
        immune = NordImmuneSystem()
        for step in range(0, 3000, 500):
            immune.check_health({"bad_zone": 0.05}, step=step)
        # 0.80 firing rate is >0.50 threshold, severity > 0.7 triggers quarantine
        immune.check_health({"bad_zone": 0.80}, step=3000)
        assert "bad_zone" in immune.quarantined_zones

    def test_zone_contradiction_detection(self):
        immune = NordImmuneSystem()
        for step in range(0, 3000, 500):
            immune.check_health({"z1": 0.07, "z2": 0.08}, step=step)
        events = immune.check_health({"z1": 0.50, "z2": 0.001}, step=3000)
        contradictions = [e for e in events if e.anomaly_type == AnomalyType.ZONE_CONTRADICTION]
        assert len(contradictions) > 0

    def test_stdp_timing_violation(self):
        immune = NordImmuneSystem()
        pre = np.array([0.001, 0.002, 0.003, 0.004, 0.005])
        post = np.array([0.0011, 0.0021, 0.0031, 0.0041, 0.0051])  # <0.5ms gap
        event = immune.check_stdp_timing(pre, post, "executive", step=100)
        assert event is not None
        assert event.anomaly_type == AnomalyType.STDP_TIMING_VIOLATION

    def test_health_report(self):
        immune = NordImmuneSystem()
        immune.check_health({"sensory": 0.07, "memory": 0.39}, step=0)
        report = immune.health_report
        assert "zones" in report
        assert "total_events" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
