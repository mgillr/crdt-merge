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
Tests for the shard training workflow — the key use case for the Nord developer.
Verifies: sparse-aware merge, shard splitting, gradient tracking, resume warmup.
"""

import time
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nord_shard_workflow import (
    sparse_aware_merge,
    NordShardTrainer,
    SurrogateGradientTracker,
    NordResumeCoordinator,
)


def make_fake_state_dict(seed=42, scale=1.0):
    rng = np.random.RandomState(seed)
    return {
        "sensory_zone.block_0.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "sensory_zone.block_1.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "association_zone.moe.expert_0": rng.randn(128, 128).astype(np.float32) * scale,
        "association_zone.moe.expert_1": rng.randn(128, 128).astype(np.float32) * scale,
        "memory_cortex.genesis.structural": rng.randn(96, 96).astype(np.float32) * scale,
        "memory_cortex.genesis.personal": rng.randn(96, 64).astype(np.float32) * scale,
        "executive_zone.block_0.weight": rng.randn(256, 256).astype(np.float32) * scale,
        "lm_head.weight": rng.randn(256, 256).astype(np.float32) * scale,
    }


def make_sparse_weights(shape, sparsity=0.93, seed=42):
    """Create weights where ~93% are zero (like Nord's firing pattern)."""
    rng = np.random.RandomState(seed)
    w = rng.randn(*shape).astype(np.float32)
    mask = rng.random(shape) > sparsity  # only ~7% are non-zero
    return w * mask.astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Sparse-Aware Merge (the critical piece)
# ═══════════════════════════════════════════════════════════════════════════

class TestSparseAwareMerge:

    def test_nonzero_wins_over_zero(self):
        """THE key property: firing neurons should not be killed by silent ones.

        Node A: neuron fires (0.8)
        Node B: neuron silent (0.0)
        Naive average: 0.4 — spike signal DESTROYED
        Sparse union: 0.8 — spike signal PRESERVED
        """
        state_a = {"layer": np.array([0.8, 0.0, 0.0, 0.5], dtype=np.float32)}
        state_b = {"layer": np.array([0.0, 0.7, 0.0, 0.0], dtype=np.float32)}

        merged = sparse_aware_merge([state_a, state_b], method="sparse_union")

        # Non-zero values should be preserved, not averaged with zeros
        np.testing.assert_allclose(merged["layer"], [0.8, 0.7, 0.0, 0.5])

    def test_naive_average_destroys_sparsity(self):
        """Demonstrate why naive averaging is wrong for SNNs."""
        firing = np.array([0.8, 0.0, 0.6], dtype=np.float32)
        silent = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        # Naive average: kills the signal
        naive = (firing + silent) / 2
        assert naive[0] == pytest.approx(0.4)  # signal halved!

        # Sparse-aware: preserves signal
        merged = sparse_aware_merge(
            [{"l": firing}, {"l": silent}], method="sparse_union"
        )
        assert merged["l"][0] == pytest.approx(0.8)  # signal preserved!

    def test_multiple_nonzero_averaged(self):
        """When both nodes fire, average only the firing values."""
        state_a = {"layer": np.array([0.8, 0.0], dtype=np.float32)}
        state_b = {"layer": np.array([0.6, 0.0], dtype=np.float32)}

        merged = sparse_aware_merge([state_a, state_b], method="sparse_union")

        # Both fire → average of non-zero values only
        np.testing.assert_allclose(merged["layer"], [0.7, 0.0])

    def test_preserves_93_percent_sparsity(self):
        """Merge two 93% sparse tensors — result should stay sparse."""
        w1 = make_sparse_weights((1000, 1000), sparsity=0.93, seed=1)
        w2 = make_sparse_weights((1000, 1000), sparsity=0.93, seed=2)

        merged = sparse_aware_merge(
            [{"layer": w1}, {"layer": w2}], method="sparse_union"
        )

        result = merged["layer"]
        result_sparsity = (np.abs(result) < 0.01).sum() / result.size

        # Sparsity should be preserved (not destroyed by averaging)
        # With two 93% sparse tensors, union gives ~86% sparsity
        # (some positions fire in both, some in only one)
        assert result_sparsity > 0.80, f"Sparsity dropped to {result_sparsity:.1%}"
        print(f"Input sparsity: 93%, Merged sparsity: {result_sparsity:.1%}")

    def test_three_node_sparse_merge(self):
        """Three nodes with different firing patterns."""
        w1 = make_sparse_weights((100,), sparsity=0.93, seed=1)
        w2 = make_sparse_weights((100,), sparsity=0.93, seed=2)
        w3 = make_sparse_weights((100,), sparsity=0.93, seed=3)

        merged = sparse_aware_merge(
            [{"l": w1}, {"l": w2}, {"l": w3}], method="sparse_union"
        )

        # Every non-zero value from any input should be represented
        any_nonzero = (np.abs(w1) > 0.01) | (np.abs(w2) > 0.01) | (np.abs(w3) > 0.01)
        merged_nonzero = np.abs(merged["l"]) > 0.001
        assert np.all(merged_nonzero[any_nonzero]), "Lost non-zero values during merge"

    def test_magnitude_weighted_method(self):
        """Magnitude-weighted merge favors stronger signals."""
        state_a = {"layer": np.array([0.9, 0.1], dtype=np.float32)}
        state_b = {"layer": np.array([0.1, 0.9], dtype=np.float32)}

        merged = sparse_aware_merge(
            [state_a, state_b], method="magnitude_weighted"
        )

        # Each position should be weighted by magnitude
        # Position 0: 0.9*(0.9/1.0) + 0.1*(0.1/1.0) = 0.81+0.01 = 0.82
        assert merged["layer"][0] > 0.5  # Larger magnitude dominates

    def test_firing_rate_method(self):
        """Firing-rate weighted merge favors more active networks."""
        # Node A: 50% active
        state_a = {"layer": np.array([1.0, 1.0, 0.0, 0.0], dtype=np.float32)}
        # Node B: 25% active
        state_b = {"layer": np.array([0.5, 0.0, 0.0, 0.0], dtype=np.float32)}

        merged = sparse_aware_merge(
            [state_a, state_b], method="firing_rate"
        )

        # Node A has higher firing rate, should have more influence
        assert merged["layer"][0] > 0.75  # Closer to node A's value


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Shard Training
# ═══════════════════════════════════════════════════════════════════════════

class TestNordShardTrainer:

    def test_create_shards(self):
        """Split a model into N shards."""
        state = make_fake_state_dict(seed=1)
        trainer = NordShardTrainer()
        shards = trainer.create_shards(state, num_shards=4)

        assert len(shards) == 4
        # All layers should be covered
        all_shard_keys = set()
        for sd in shards.values():
            all_shard_keys.update(sd.keys())
        assert all_shard_keys == set(state.keys())

    def test_submit_and_merge(self):
        """Full workflow: split, train (simulated), merge."""
        state = make_fake_state_dict(seed=1)
        trainer = NordShardTrainer()
        shards = trainer.create_shards(state, num_shards=2)

        # Simulate training: add small perturbations
        for shard_id, shard_dict in shards.items():
            trained = {}
            for k, v in shard_dict.items():
                trained[k] = v + np.random.randn(*v.shape).astype(np.float32) * 0.01
            trainer.submit_shard(shard_id, trained, metrics={
                "node_id": shard_id, "steps": 5000, "loss": 4.2, "cost_usd": 0.0,
            })

        merged = trainer.merge_all()
        assert set(merged.keys()) == set(state.keys())
        report = trainer.report
        assert report["submitted"] == 2
        assert report["total_steps"] == 10000

    def test_free_tier_workflow(self):
        """Simulate the exact workflow: 4 shards on free platforms."""
        state = make_fake_state_dict(seed=1)
        trainer = NordShardTrainer()
        shards = trainer.create_shards(state, num_shards=4)

        platforms = ["colab_free", "kaggle_free", "local_rtx5070", "colab_free_2"]
        for i, (shard_id, shard_dict) in enumerate(shards.items()):
            trained = {k: v + np.random.randn(*v.shape).astype(np.float32) * 0.01
                       for k, v in shard_dict.items()}
            trainer.submit_shard(shard_id, trained, metrics={
                "node_id": platforms[i],
                "steps": 5000,
                "cost_usd": 0.0,  # All free!
                "platform": platforms[i],
            })

        merged = trainer.merge_all(method="sparse_union")
        report = trainer.report
        assert report["total_cost_usd"] == 0.0  # Free!
        assert report["total_steps"] == 20000
        assert len(merged) == len(state)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Surrogate Gradient Tracking
# ═══════════════════════════════════════════════════════════════════════════

class TestSurrogateGradientTracker:

    def test_basic_tracking(self):
        tracker = SurrogateGradientTracker("node_a")
        tracker.record_gradients("sensory.block_0", grad_norm=0.05, grad_variance=0.001)
        tracker.record_gradients("association.moe", grad_norm=0.02, grad_variance=0.0005)

        summary = tracker.summary
        assert summary["total_grad_steps"] == 2
        assert summary["grad_norms"]["sensory.block_0"] == pytest.approx(0.05)
        assert tracker.health == "healthy"

    def test_vanishing_gradient_detection(self):
        """Detect vanishing gradients — the #1 SNN training failure mode."""
        tracker = SurrogateGradientTracker("node_a")

        # Record mostly vanishing gradients
        for i in range(10):
            tracker.record_gradients(f"layer_{i}", grad_norm=1e-9, grad_variance=1e-12)

        assert tracker.vanishing_events.value == 10
        assert "vanishing" in tracker.health.lower()

    def test_exploding_gradient_detection(self):
        tracker = SurrogateGradientTracker("node_a")
        tracker.record_gradients("layer_0", grad_norm=500.0, grad_variance=100.0)

        assert tracker.exploding_events.value == 1
        assert "exploding" in tracker.health.lower()

    def test_merge_gradient_stats(self):
        """Merge gradient stats from two nodes."""
        node_a = SurrogateGradientTracker("rtx5070")
        node_a.record_gradients("layer_0", grad_norm=0.05, grad_variance=0.001)
        node_a.record_gradients("layer_1", grad_norm=1e-9, grad_variance=1e-12)

        node_b = SurrogateGradientTracker("a100")
        node_b.record_gradients("layer_0", grad_norm=0.03, grad_variance=0.002)
        node_b.record_gradients("layer_2", grad_norm=200.0, grad_variance=50.0)

        merged = node_a.merge(node_b)
        assert merged.total_grad_steps.value == 4
        assert merged.vanishing_events.value == 1
        assert merged.exploding_events.value == 1

    def test_gradient_commutativity(self):
        a = SurrogateGradientTracker("a")
        a.record_gradients("l0", grad_norm=0.1, grad_variance=0.01)

        b = SurrogateGradientTracker("b")
        b.record_gradients("l0", grad_norm=0.2, grad_variance=0.02)

        ab = a.merge(b)
        ba = b.merge(a)
        assert ab.total_grad_steps.value == ba.total_grad_steps.value
        assert ab.vanishing_events.value == ba.vanishing_events.value


# ═══════════════════════════════════════════════════════════════════════════
# TEST: Resume Coordinator
# ═══════════════════════════════════════════════════════════════════════════

class TestNordResumeCoordinator:

    def test_warmup_lr_schedule(self):
        state = make_fake_state_dict()
        resume = NordResumeCoordinator(state, base_lr=1e-4, warmup_steps=100)

        # Step 0: 1/100 of base_lr
        assert resume.get_warmup_lr(0) == pytest.approx(1e-6)
        # Step 50: 51/100 of base_lr
        assert resume.get_warmup_lr(50) == pytest.approx(51e-6)
        # Step 99: 100/100 of base_lr
        assert resume.get_warmup_lr(99) == pytest.approx(1e-4)
        # Step 200: full base_lr
        assert resume.get_warmup_lr(200) == pytest.approx(1e-4)

    def test_stable_merge(self):
        """Simulate a successful merge warmup — loss decreases."""
        state = make_fake_state_dict()
        resume = NordResumeCoordinator(state, base_lr=1e-4, warmup_steps=10)

        # Simulate decreasing loss during warmup
        for step in range(10):
            loss = 4.4 - step * 0.02
            resume.record_step(step, loss, sparsity=0.93)

        report = resume.merge_stability_report
        assert report["status"] == "stable"
        assert report["loss_improved"] is True
        assert report["sparsity_preserved"] is True
        assert report["loss_spike_detected"] is False

    def test_unstable_merge_detection(self):
        """Detect when a merge produces an unstable checkpoint."""
        state = make_fake_state_dict()
        resume = NordResumeCoordinator(state, base_lr=1e-4, warmup_steps=10)

        # Simulate loss spike (merge instability)
        resume.record_step(0, loss=4.4, sparsity=0.93)
        resume.record_step(1, loss=8.0, sparsity=0.93)  # spike!
        resume.record_step(2, loss=5.0, sparsity=0.93)

        report = resume.merge_stability_report
        assert report["loss_spike_detected"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
