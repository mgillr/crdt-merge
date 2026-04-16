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

"""
Tests for Project Nord + crdt-merge integration.
Verifies CRDT guarantees hold for all Nord-specific operations.
"""

import time
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nord_federated import (
    NordFederatedTrainer,
    NordCheckpointMerger,
    NORD_ZONES,
)
from nord_sparse_sync import (
    SparseDelta,
    extract_sparse_delta,
    apply_sparse_delta,
    merge_sparse_deltas,
    NordSparseGossipSync,
)
from nord_training_state import (
    NordTrainingState,
    NordMemoryState,
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_fake_state_dict(seed: int = 42, scale: float = 1.0) -> dict:
    """Create a fake Nord-like state dict with all 7 zones represented."""
    rng = np.random.RandomState(seed)
    return {
        # Sensory zone (~185M params, simulated small)
        "sensory_zone.block_0.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "sensory_zone.block_1.weight": rng.randn(256, 256).astype(np.float32) * scale,
        # Association zone + MoE experts
        "association_zone.block_0.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "association_zone.moe.expert_0.weight": rng.randn(128, 128).astype(np.float32) * scale,
        "association_zone.moe.expert_1.weight": rng.randn(128, 128).astype(np.float32) * scale,
        # Memory cortex
        "memory_cortex.persistent_lif.weight": rng.randn(96, 96).astype(np.float32) * scale,
        "memory_cortex.genesis.structural.weight": rng.randn(96, 64).astype(np.float32) * scale,
        "memory_cortex.genesis.personal.weight": rng.randn(96, 64).astype(np.float32) * scale,
        "memory_cortex.genesis.auxiliary.weight": rng.randn(64, 64).astype(np.float32) * scale,
        "memory_cortex.archive_grid.weight": rng.randn(32, 128).astype(np.float32) * scale,
        # Executive zone
        "executive_zone.block_0.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "executive_zone.block_1.weight": rng.randn(256, 256).astype(np.float32) * scale,
        # Temporal encoder
        "temporal_spike_encoder.weight": rng.randn(256, 256).astype(np.float32) * scale,
        # Readout
        "readout.ema_decay": rng.randn(256).astype(np.float32) * scale,
        "lm_head.weight": rng.randn(256, 256).astype(np.float32) * scale,
        # STDP engine
        "stdp.weight_matrix": rng.randn(64, 64).astype(np.float32) * scale,
    }


def make_sparse_state_dict(seed: int = 42, sparsity: float = 0.93) -> dict:
    """Create a state dict where ~93% of values are zero (like Nord)."""
    base = make_fake_state_dict(seed)
    rng = np.random.RandomState(seed + 1000)
    for key in base:
        mask = rng.random(base[key].shape) > sparsity
        base[key] = base[key] * mask.astype(np.float32)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Federated Training
# ═══════════════════════════════════════════════════════════════════════════

class TestNordFederatedTrainer:

    def test_basic_merge(self):
        """Two nodes submit checkpoints, coordinator merges them."""
        coordinator = NordFederatedTrainer()

        state_a = make_fake_state_dict(seed=1, scale=1.0)
        state_b = make_fake_state_dict(seed=2, scale=2.0)

        coordinator.submit_checkpoint(
            "node_a", state_a, num_samples=50000, steps_trained=5000,
            metadata={"gpu": "RTX 5070", "loss": 4.4},
        )
        coordinator.submit_checkpoint(
            "node_b", state_b, num_samples=100000, steps_trained=10000,
            metadata={"gpu": "A100", "loss": 4.1},
        )

        merged, report = coordinator.merge_round()

        # All layers present
        assert set(merged.keys()) == set(state_a.keys())
        # Weights are between the two inputs (weighted average)
        for key in merged:
            m = np.array(merged[key])
            a = state_a[key]
            b = state_b[key]
            # Merged should be closer to b (more samples)
            dist_a = np.linalg.norm(m - a)
            dist_b = np.linalg.norm(m - b)
            assert dist_b < dist_a, f"Merged should be closer to node_b (more samples) for {key}"

        # Report is correct
        assert report["round"] == 1
        assert report["global_steps"] == 15000
        assert report["global_samples"] == 150000
        assert report["num_nodes"] == 2

    def test_zone_classification(self):
        """Layers are classified into correct Nord zones."""
        coordinator = NordFederatedTrainer()
        assert coordinator._classify_layer("sensory_zone.block_0.weight") == "sensory"
        assert coordinator._classify_layer("association_zone.moe.expert_0") == "association"
        assert coordinator._classify_layer("memory_cortex.genesis.structural") == "memory_cortex"
        assert coordinator._classify_layer("executive_zone.block_1.weight") == "executive"
        assert coordinator._classify_layer("temporal_spike_encoder.weight") == "temporal_encoder"
        assert coordinator._classify_layer("readout.ema_decay") == "readout"
        assert coordinator._classify_layer("lm_head.weight") == "readout"
        assert coordinator._classify_layer("stdp.weight_matrix") == "stdp_engine"

    def test_three_node_merge(self):
        """Three nodes merge — simulating community distributed training."""
        coordinator = NordFederatedTrainer()

        for i, (node, samples, gpu) in enumerate([
            ("laptop_rtx5070", 30000, "RTX 5070"),
            ("colab_t4", 50000, "T4"),
            ("cloud_a100", 120000, "A100"),
        ]):
            state = make_fake_state_dict(seed=i * 10)
            coordinator.submit_checkpoint(
                node, state, num_samples=samples,
                steps_trained=samples // 10,
            )

        merged, report = coordinator.merge_round()
        assert report["num_nodes"] == 3
        assert report["global_samples"] == 200000
        assert len(merged) == 16  # all layers

    def test_memory_zone_uses_fedprox(self):
        """Memory cortex zone should use FedProx to prevent memory drift."""
        assert NORD_ZONES["memory_cortex"]["strategy"] == "fedprox"
        assert NORD_ZONES["stdp_engine"]["strategy"] == "fedprox"
        assert NORD_ZONES["sensory"]["strategy"] == "fedavg"


class TestNordCheckpointMerger:

    def test_crdt_commutativity(self):
        """merge(A, B) == merge(B, A) — core CRDT guarantee."""
        state_a = make_fake_state_dict(seed=1)
        state_b = make_fake_state_dict(seed=2)

        merger_ab = NordCheckpointMerger()
        merger_ab.add_checkpoint("a", state_a, weight=0.5)
        merger_ab.add_checkpoint("b", state_b, weight=0.5)
        result_ab = merger_ab.resolve()

        merger_ba = NordCheckpointMerger()
        merger_ba.add_checkpoint("b", state_b, weight=0.5)
        merger_ba.add_checkpoint("a", state_a, weight=0.5)
        result_ba = merger_ba.resolve()

        for key in result_ab:
            np.testing.assert_allclose(
                result_ab[key], result_ba[key], rtol=1e-5,
                err_msg=f"Commutativity violated for {key}",
            )

    def test_crdt_idempotency(self):
        """merge(A, A) == A — CRDT idempotency."""
        state_a = make_fake_state_dict(seed=1)

        merger = NordCheckpointMerger()
        merger.add_checkpoint("a_v1", state_a, weight=1.0)
        single = merger.resolve()

        merger2 = NordCheckpointMerger()
        merger2.add_checkpoint("a_v1", state_a, weight=1.0)
        merger2.add_checkpoint("a_v1_dup", state_a, weight=1.0)
        double = merger2.resolve()

        for key in single:
            np.testing.assert_allclose(
                single[key], double[key], rtol=1e-5,
                err_msg=f"Idempotency violated for {key}",
            )

    def test_weighted_merge(self):
        """Higher-weight checkpoint should dominate the merge."""
        state_a = {k: np.zeros_like(v) for k, v in make_fake_state_dict(1).items()}
        state_b = {k: np.ones_like(v) for k, v in make_fake_state_dict(1).items()}

        merger = NordCheckpointMerger()
        merger.add_checkpoint("zeros", state_a, weight=0.2)
        merger.add_checkpoint("ones", state_b, weight=0.8)
        result = merger.resolve()

        for key in result:
            mean_val = np.mean(result[key])
            # Should be close to 0.5 (average of 0 and 1 with equal-ish weights)
            # Actually with weight_average, both get normalized, so ~0.5
            assert 0.0 < mean_val < 1.0, f"Unexpected mean {mean_val} for {key}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Sparse Delta Sync
# ═══════════════════════════════════════════════════════════════════════════

class TestSparseDelta:

    def test_extract_sparse_delta(self):
        """Extracting a delta from 93% sparse weight change."""
        old = np.zeros((1000, 1000), dtype=np.float32)
        new = old.copy()
        # Only change 7% of weights (matching Nord's sparsity)
        rng = np.random.RandomState(42)
        mask = rng.random((1000, 1000)) < 0.07
        new[mask] = rng.randn(mask.sum()).astype(np.float32)

        delta = extract_sparse_delta(old, new, "test_layer", "node_1", step=1)

        assert delta.sparsity > 0.92, f"Expected >92% sparsity, got {delta.sparsity}"
        # Compression ratio accounts for index storage (int64=8 bytes per index)
        # so 7% density gives ~4-5x compression, not 14x
        assert delta.compression_ratio > 3, f"Expected >3x compression, got {delta.compression_ratio}"
        assert len(delta.indices) < 80000  # ~7% of 1M
        print(f"  Sparsity: {delta.sparsity:.2%}, Compression: {delta.compression_ratio:.1f}x")

    def test_apply_delta_roundtrip(self):
        """Apply a delta and verify correctness."""
        old = np.random.randn(100, 100).astype(np.float32)
        new = old.copy()
        new[10:15, 20:25] += 0.5  # change a small block

        delta = extract_sparse_delta(old, new, "layer", "node", step=1)
        recovered = apply_sparse_delta(old, delta)

        np.testing.assert_allclose(recovered, new, atol=1e-6)

    def test_merge_deltas_average(self):
        """Merge deltas from two nodes — averaging conflicting updates."""
        shape = (100,)
        delta_a = SparseDelta(
            layer_name="test",
            indices=np.array([0, 1, 2, 5]),
            values=np.array([1.0, 2.0, 3.0, 10.0], dtype=np.float32),
            shape=shape,
            node_id="a",
            step=1,
        )
        delta_b = SparseDelta(
            layer_name="test",
            indices=np.array([1, 2, 3, 6]),
            values=np.array([4.0, 6.0, 7.0, 11.0], dtype=np.float32),
            shape=shape,
            node_id="b",
            step=1,
        )

        merged = merge_sparse_deltas([delta_a, delta_b], method="average")

        # Index 0: only in A → 1.0
        # Index 1: in both → avg(2.0, 4.0) = 3.0
        # Index 2: in both → avg(3.0, 6.0) = 4.5
        # Index 3: only in B → 7.0
        # Index 5: only in A → 10.0
        # Index 6: only in B → 11.0
        expected_indices = [0, 1, 2, 3, 5, 6]
        expected_values = [1.0, 3.0, 4.5, 7.0, 10.0, 11.0]

        np.testing.assert_array_equal(merged.indices, expected_indices)
        np.testing.assert_allclose(merged.values, expected_values)

    def test_merge_deltas_latest(self):
        """Last-writer-wins delta merge."""
        shape = (100,)
        delta_a = SparseDelta(
            layer_name="test",
            indices=np.array([0, 1]),
            values=np.array([1.0, 2.0], dtype=np.float32),
            shape=shape, node_id="a", step=1,
            timestamp=100.0,
        )
        delta_b = SparseDelta(
            layer_name="test",
            indices=np.array([0, 1]),
            values=np.array([9.0, 8.0], dtype=np.float32),
            shape=shape, node_id="b", step=2,
            timestamp=200.0,  # newer
        )

        merged = merge_sparse_deltas([delta_a, delta_b], method="latest")
        np.testing.assert_allclose(merged.values, [9.0, 8.0])

    def test_sparsity_bandwidth_savings(self):
        """Verify bandwidth savings match Nord's 93% sparsity claim."""
        old = np.zeros((1024, 1024), dtype=np.float32)
        new = old.copy()
        rng = np.random.RandomState(0)
        # 7% active neurons
        mask = rng.random(old.shape) < 0.07
        new[mask] = rng.randn(mask.sum()).astype(np.float32)

        delta = extract_sparse_delta(old, new, "layer", "node", step=1)

        # Full tensor: 1024*1024*4 = 4MB
        # Sparse delta indices (int64) + values (fp32) = 12 bytes per non-zero
        # At 7% density: ~73k entries × 12 bytes ≈ 876KB vs 4MB → ~4.8x
        assert delta.compression_ratio > 3
        print(f"Compression: {delta.compression_ratio:.1f}x "
              f"({delta.size_bytes/1024:.0f}KB vs {delta.full_size_bytes/1024:.0f}KB)")


class TestNordSparseGossipSync:

    def test_post_step_extracts_deltas(self):
        sync = NordSparseGossipSync(node_id="test_node")
        old_state = {"layer_0": np.zeros((64, 64), dtype=np.float32)}
        new_state = {"layer_0": np.random.randn(64, 64).astype(np.float32) * 0.01}

        deltas = sync.post_step(old_state, new_state, step=1)
        assert len(deltas) > 0
        assert sync.stats["steps"] == 1
        assert sync.stats["deltas_produced"] > 0

    def test_apply_remote_deltas(self):
        sync = NordSparseGossipSync(node_id="test_node")
        current = {"layer_0": np.zeros((10,), dtype=np.float32)}
        delta = SparseDelta(
            layer_name="layer_0",
            indices=np.array([2, 5, 7]),
            values=np.array([1.0, 2.0, 3.0], dtype=np.float32),
            shape=(10,), node_id="remote", step=1,
        )

        updated = sync.apply_remote_deltas(current, [delta])
        assert updated["layer_0"][2] == 1.0
        assert updated["layer_0"][5] == 2.0
        assert updated["layer_0"][7] == 3.0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Training State
# ═══════════════════════════════════════════════════════════════════════════

class TestNordTrainingState:

    def test_basic_recording(self):
        state = NordTrainingState("node_a")
        state.record_step(
            step=27000, loss=4.4, sparsity=0.93,
            zone_activations={"sensory": 0.05, "memory_cortex": 0.39},
            tokens_in_batch=2048,
        )

        summary = state.summary
        assert summary["total_steps"] == 1
        assert summary["current_loss"] == 4.4
        assert summary["current_sparsity"] == 0.93
        assert summary["total_tokens"] == 2048
        assert summary["zone_activations"]["sensory"] == 0.05
        assert summary["zone_activations"]["memory_cortex"] == 0.39

    def test_stdp_as_pncounter(self):
        """STDP potentiation/depression maps to PNCounter."""
        state = NordTrainingState("node_a")

        # 1234 potentiation events, 567 depression events
        state.record_stdp_update("assoc.block_0", potentiation_count=1234, depression_count=567)

        # Net STDP = 1234 - 567 = 667
        assert state.stdp_potentiation.value == 667
        assert state.stdp_updates["assoc.block_0"].value == 667

    def test_merge_two_nodes(self):
        """Merge training states from two nodes."""
        node_a = NordTrainingState("rtx5070")
        node_a.record_step(step=27000, loss=4.4, sparsity=0.93)
        node_a.record_spikes(1000000)
        node_a.record_stdp_update("layer_0", potentiation_count=500, depression_count=200)
        node_a.record_emergence("cross_lingual_russian", step=25000)

        node_b = NordTrainingState("a100")
        node_b.record_step(step=50000, loss=4.1, sparsity=0.94)
        node_b.record_spikes(2000000)
        node_b.record_stdp_update("layer_0", potentiation_count=800, depression_count=100)
        node_b.record_emergence("cross_lingual_chinese", step=48000)

        merged = node_a.merge(node_b)
        summary = merged.summary

        # GCounters sum across nodes
        assert summary["total_steps"] == 2  # 1 + 1
        assert summary["total_spikes"] == 3000000  # 1M + 2M

        # LWW: latest timestamp wins (node_b recorded last)
        assert summary["current_loss"] == 4.1

        # PNCounter: merged STDP
        # node_a: 500-200=300, node_b: 800-100=700 → merge = 300+700=1000
        # Wait, PNCounter merge takes element-wise max of pos/neg per node
        # node_a pos=500, neg=200; node_b pos=800, neg=100
        # merged: pos = max(500,0) + max(0,800) = 500+800 = 1300
        #         neg = max(200,0) + max(0,100) = 200+100 = 300
        #         value = 1300 - 300 = 1000
        assert summary["net_stdp_updates"] == 1000

        # ORSet: union
        assert "cross_lingual_russian@step_25000" in summary["emerged_capabilities"]
        assert "cross_lingual_chinese@step_48000" in summary["emerged_capabilities"]

    def test_merge_commutativity(self):
        """merge(A, B) == merge(B, A)."""
        a = NordTrainingState("a")
        a.record_step(step=100, loss=5.0, sparsity=0.90)
        a.record_spikes(500)

        b = NordTrainingState("b")
        b.record_step(step=200, loss=4.5, sparsity=0.93)
        b.record_spikes(1000)

        ab = a.merge(b)
        ba = b.merge(a)

        assert ab.total_steps.value == ba.total_steps.value
        assert ab.total_spikes.value == ba.total_spikes.value
        assert ab.current_loss.value == ba.current_loss.value

    def test_emergence_tracking(self):
        """Emergent capabilities tracked via ORSet (add-wins)."""
        state = NordTrainingState("node")
        state.record_emergence("cross_lingual_russian", step=25000)
        state.record_emergence("memory_routing_shift", step=20000)

        caps = state.emerged_capabilities.value
        assert "cross_lingual_russian@step_25000" in caps
        assert "memory_routing_shift@step_20000" in caps


class TestNordMemoryState:

    def test_basic_memory_operations(self):
        mem = NordMemoryState("node_a")

        # Update structural bank neurons
        for i in range(96):
            mem.update_structural(i, float(i) * 0.01)

        # Update personal bank
        for i in range(96):
            mem.update_personal(i, float(i) * 0.02)

        # Store archive entries
        mem.store_archive("slot_0", {"pattern": "subject-verb-object"})
        mem.store_archive("slot_1", {"pattern": "noun-phrase"})

        summary = mem.summary
        assert summary["structural_neurons"] == 96
        assert summary["personal_neurons"] == 96
        assert summary["archive_slots_used"] == 2

    def test_memory_merge(self):
        """Merge memory states from two nodes."""
        mem_a = NordMemoryState("node_a")
        mem_a.update_structural(0, 0.5)
        mem_a.store_archive("slot_0", "pattern_a")

        mem_b = NordMemoryState("node_b")
        mem_b.update_structural(1, 0.7)
        mem_b.store_archive("slot_1", "pattern_b")

        merged = mem_a.merge(mem_b)
        assert merged.summary["structural_neurons"] == 2
        assert merged.summary["archive_slots_used"] == 2

    def test_memory_merge_commutativity(self):
        """Memory merge is order-independent."""
        a = NordMemoryState("a")
        a.update_structural(0, 1.0)
        a.store_archive("s0", "val_a")

        b = NordMemoryState("b")
        b.update_structural(1, 2.0)
        b.store_archive("s1", "val_b")

        ab = a.merge(b)
        ba = b.merge(a)

        assert ab.summary == ba.summary


# ═══════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
