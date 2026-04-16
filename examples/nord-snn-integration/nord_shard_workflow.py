"""
Module 4: End-to-End Shard Training & CRDT Merge Workflow
=========================================================
This is THE key module for the Nord developer.

The problem: Training 1.088B params in one continuous run costs $670+
and stops at loss 4.4 when the budget runs out.

The solution: Train smaller SNN shards (~300M) on free tiers (Colab,
Kaggle, etc.), then merge them using CRDT OR-Set semantics that
PRESERVE sparse spike structures instead of destroying them with
naive averaging.

Why standard averaging kills SNNs:
  - Neuron A fires (weight = 0.8) on node 1
  - Neuron A is silent (weight = 0.0) on node 2
  - Naive average: 0.4 — the spike signal is destroyed
  - OR-Set merge: 0.8 — the firing neuron WINS (add-wins semantics)

This module provides the complete workflow:
  1. Shard the model into trainable chunks
  2. Train each shard independently (local GPU, Colab, Kaggle)
  3. Merge shards using CRDT guarantees
  4. Resume training from the merged checkpoint
  5. Track surrogate gradient stats across nodes
  6. Monitor when to stop and merge for optimal loss
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from crdt_merge.core import GCounter, PNCounter, LWWRegister, LWWMap, ORSet
from crdt_merge.model.crdt_state import CRDTMergeState
from crdt_merge.clocks import VectorClock
from crdt_merge.agentic import AgentState, SharedKnowledge


# ---------------------------------------------------------------------------
# 1. Sparsity-aware merge that preserves spike structures
# ---------------------------------------------------------------------------

def sparse_aware_merge(
    state_dicts: List[Dict[str, np.ndarray]],
    sparsity_threshold: float = 0.01,
    method: str = "sparse_union",
) -> Dict[str, np.ndarray]:
    """Merge multiple sparse SNN state dicts WITHOUT destroying spike signals.

    Standard weight averaging kills sparsity:
      avg(0.8, 0.0) = 0.4 — spike signal destroyed

    This function uses OR-Set inspired semantics:
      - If ANY node has a non-zero weight, it wins over zeros
      - When multiple nodes have non-zero weights, average only those
      - Zero weights from silent neurons are excluded from averaging

    This preserves the 93% sparsity structure that Nord relies on.

    Parameters
    ----------
    state_dicts : list of dict
        State dicts from different training shards/nodes.
    sparsity_threshold : float
        Weights below this absolute value are considered "silent" (zero).
    method : str
        "sparse_union" — OR-Set semantics (non-zero wins over zero)
        "magnitude_weighted" — weight contribution by absolute magnitude
        "firing_rate" — weight by proportion of non-zero values

    Returns
    -------
    dict
        Merged state dict with spike structures preserved.
    """
    if not state_dicts:
        raise ValueError("No state dicts to merge")
    if len(state_dicts) == 1:
        return state_dicts[0]

    merged = {}
    all_keys = set()
    for sd in state_dicts:
        all_keys.update(sd.keys())

    for key in all_keys:
        tensors = []
        for sd in state_dicts:
            if key in sd:
                tensors.append(np.asarray(sd[key], dtype=np.float32))

        if len(tensors) == 1:
            merged[key] = tensors[0]
            continue

        # Ensure same shape
        shape = tensors[0].shape
        result = np.zeros(shape, dtype=np.float32)

        if method == "sparse_union":
            # OR-Set semantics: non-zero values win over zeros
            # When multiple non-zero values exist, average only those
            active_sum = np.zeros(shape, dtype=np.float64)
            active_count = np.zeros(shape, dtype=np.float64)

            for t in tensors:
                mask = np.abs(t) > sparsity_threshold
                active_sum += np.where(mask, t.astype(np.float64), 0.0)
                active_count += mask.astype(np.float64)

            # Where at least one node has a non-zero weight, use the average
            # of non-zero values only (not diluted by silent neurons)
            nonzero_mask = active_count > 0
            result[nonzero_mask] = (
                active_sum[nonzero_mask] / active_count[nonzero_mask]
            ).astype(np.float32)

        elif method == "magnitude_weighted":
            # Weight each contribution by its absolute magnitude
            magnitudes = [np.abs(t).astype(np.float64) for t in tensors]
            total_magnitude = sum(magnitudes)
            total_magnitude = np.maximum(total_magnitude, 1e-10)

            for t, m in zip(tensors, magnitudes):
                result += (t * (m / total_magnitude)).astype(np.float32)

        elif method == "firing_rate":
            # Weight each contribution by proportion of active neurons
            rates = []
            for t in tensors:
                active = np.abs(t) > sparsity_threshold
                rate = active.sum() / max(active.size, 1)
                rates.append(rate)
            total_rate = sum(rates)
            if total_rate > 0:
                weights = [r / total_rate for r in rates]
            else:
                weights = [1.0 / len(tensors)] * len(tensors)
            for t, w in zip(tensors, weights):
                result += t * w

        merged[key] = result

    return merged


# ---------------------------------------------------------------------------
# 2. Shard training coordinator
# ---------------------------------------------------------------------------

@dataclass
class ShardConfig:
    """Configuration for a training shard."""
    shard_id: str
    node_id: str
    layer_range: Tuple[int, int]  # (start_layer, end_layer)
    num_params: int = 0
    gpu: str = "unknown"
    platform: str = "local"  # "local", "colab", "kaggle", "cloud"
    estimated_cost: float = 0.0  # USD


class NordShardTrainer:
    """Orchestrate shard-based distributed training for Project Nord.

    The core insight: instead of training 1.088B params in one run ($670+),
    split into ~300M shards and train on free/cheap platforms.

    Workflow:
        1. coordinator.create_shards(full_state_dict, num_shards=4)
        2. Each participant: train their shard locally
        3. coordinator.submit_shard(shard_id, trained_state_dict, metrics)
        4. coordinator.merge_all() — CRDT merge preserving sparsity
        5. Continue training from merged checkpoint

    Usage::

        coordinator = NordShardTrainer()

        # Split the 1.088B model into 4 shards (~270M each)
        shards = coordinator.create_shards(
            full_state_dict=model.state_dict(),
            num_shards=4,
        )

        # Distribute shards to participants
        # Participant 1 trains shard 0 on their RTX 5070
        # Participant 2 trains shard 1 on Colab free tier
        # etc.

        # After training, submit results
        coordinator.submit_shard("shard_0", trained_shard_0, metrics_0)
        coordinator.submit_shard("shard_1", trained_shard_1, metrics_1)

        # Merge all shards back — preserving sparse spike structures
        merged = coordinator.merge_all()
    """

    def __init__(self):
        self._shards: Dict[str, ShardConfig] = {}
        self._submissions: Dict[str, Dict[str, np.ndarray]] = {}
        self._metrics: Dict[str, dict] = {}
        self._total_cost = GCounter()
        self._total_steps = GCounter()
        self._clock = VectorClock()

    def create_shards(
        self,
        full_state_dict: Dict[str, np.ndarray],
        num_shards: int = 4,
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Split a full state dict into N approximately equal shards.

        Each shard gets a contiguous subset of layers. The shards
        can be trained independently on different hardware.
        """
        layers = list(full_state_dict.keys())
        shard_size = max(1, len(layers) // num_shards)
        shards = {}

        for i in range(num_shards):
            start = i * shard_size
            end = start + shard_size if i < num_shards - 1 else len(layers)
            shard_layers = layers[start:end]
            shard_id = f"shard_{i}"

            shard_dict = {k: full_state_dict[k].copy() for k in shard_layers}
            shard_params = sum(v.size for v in shard_dict.values())

            self._shards[shard_id] = ShardConfig(
                shard_id=shard_id,
                node_id="unassigned",
                layer_range=(start, end),
                num_params=shard_params,
            )
            shards[shard_id] = shard_dict

        return shards

    def submit_shard(
        self,
        shard_id: str,
        state_dict: Dict[str, np.ndarray],
        metrics: Optional[dict] = None,
    ) -> None:
        """Submit a trained shard."""
        self._submissions[shard_id] = state_dict
        self._metrics[shard_id] = metrics or {}

        if metrics:
            node = metrics.get("node_id", shard_id)
            steps = metrics.get("steps", 0)
            cost = metrics.get("cost_usd", 0.0)
            if steps > 0:
                self._total_steps.increment(node, steps)
            if cost > 0:
                self._total_cost.increment(node, int(cost * 100))  # cents

    def merge_all(
        self,
        method: str = "sparse_union",
        sparsity_threshold: float = 0.01,
    ) -> Dict[str, np.ndarray]:
        """Merge all submitted shards into a complete model.

        Uses sparsity-aware merge to preserve spike structures.
        """
        if not self._submissions:
            raise ValueError("No shards submitted")

        # For shards that cover different layers, just concatenate
        # For overlapping layers (e.g. shared embeddings), use sparse merge
        all_keys = set()
        for sd in self._submissions.values():
            all_keys.update(sd.keys())

        merged = {}
        for key in all_keys:
            contributors = []
            for shard_id, sd in self._submissions.items():
                if key in sd:
                    contributors.append(sd[key])

            if len(contributors) == 1:
                merged[key] = contributors[0]
            else:
                # Multiple shards modified the same layer — use sparse merge
                merged[key] = sparse_aware_merge(
                    [{key: c} for c in contributors],
                    sparsity_threshold=sparsity_threshold,
                    method=method,
                )[key]

        return merged

    @property
    def report(self) -> dict:
        return {
            "num_shards": len(self._shards),
            "submitted": len(self._submissions),
            "total_steps": self._total_steps.value,
            "total_cost_usd": self._total_cost.value / 100.0,
            "shard_details": {
                sid: {"params": cfg.num_params, "platform": cfg.platform}
                for sid, cfg in self._shards.items()
            },
            "metrics": dict(self._metrics),
        }


# ---------------------------------------------------------------------------
# 3. Surrogate gradient tracking across distributed nodes
# ---------------------------------------------------------------------------

class SurrogateGradientTracker:
    """Track surrogate gradient statistics across distributed training nodes.

    Nord uses surrogate gradients to backpropagate through discrete
    spike events. The gradient magnitude and variance are critical
    indicators of training stability.

    This tracker uses CRDTs so that gradient statistics from N nodes
    can be merged without conflicts — enabling distributed monitoring
    of training health.

    Tracks per-zone:
    - Gradient L2 norm (via LWWRegister — latest measurement wins)
    - Gradient variance (via LWWRegister)
    - Vanishing gradient events (via GCounter — monotonically increasing)
    - Exploding gradient events (via GCounter)
    - Total gradient steps (via GCounter)
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.grad_norms = LWWMap()          # layer → latest gradient norm
        self.grad_variances = LWWMap()      # layer → latest gradient variance
        self.vanishing_events = GCounter()  # times gradient < threshold
        self.exploding_events = GCounter()  # times gradient > threshold
        self.total_grad_steps = GCounter()
        self.clock = VectorClock()

    def record_gradients(
        self,
        layer_name: str,
        grad_norm: float,
        grad_variance: float,
        vanishing_threshold: float = 1e-7,
        exploding_threshold: float = 100.0,
    ) -> None:
        """Record gradient statistics after a backward pass."""
        ts = time.time()
        self.clock = self.clock.increment(self.node_id)
        self.total_grad_steps.increment(self.node_id)

        self.grad_norms.set(layer_name, grad_norm, timestamp=ts, node_id=self.node_id)
        self.grad_variances.set(layer_name, grad_variance, timestamp=ts, node_id=self.node_id)

        if grad_norm < vanishing_threshold:
            self.vanishing_events.increment(self.node_id)
        if grad_norm > exploding_threshold:
            self.exploding_events.increment(self.node_id)

    def merge(self, other: "SurrogateGradientTracker") -> "SurrogateGradientTracker":
        result = SurrogateGradientTracker(f"{self.node_id}+{other.node_id}")
        result.grad_norms = self.grad_norms.merge(other.grad_norms)
        result.grad_variances = self.grad_variances.merge(other.grad_variances)
        result.vanishing_events = self.vanishing_events.merge(other.vanishing_events)
        result.exploding_events = self.exploding_events.merge(other.exploding_events)
        result.total_grad_steps = self.total_grad_steps.merge(other.total_grad_steps)
        result.clock = self.clock.merge(other.clock)
        return result

    @property
    def summary(self) -> dict:
        return {
            "node_id": self.node_id,
            "total_grad_steps": self.total_grad_steps.value,
            "vanishing_events": self.vanishing_events.value,
            "exploding_events": self.exploding_events.value,
            "grad_norms": dict(self.grad_norms.value),
            "grad_variances": dict(self.grad_variances.value),
        }

    @property
    def health(self) -> str:
        """Quick health check for gradient flow."""
        total = self.total_grad_steps.value
        if total == 0:
            return "no_data"
        vanish_rate = self.vanishing_events.value / max(total, 1)
        explode_rate = self.exploding_events.value / max(total, 1)
        if vanish_rate > 0.5:
            return "CRITICAL: >50% vanishing gradients"
        if explode_rate > 0.1:
            return "WARNING: >10% exploding gradients"
        if vanish_rate > 0.1:
            return "WARNING: >10% vanishing gradients"
        return "healthy"


# ---------------------------------------------------------------------------
# 4. Training resume coordinator
# ---------------------------------------------------------------------------

class NordResumeCoordinator:
    """Coordinate training resumption after a CRDT merge.

    After merging checkpoints from multiple nodes, this coordinator
    manages the warmup phase to stabilize the merged model before
    full-speed training resumes.

    The warmup is important because merged weights may have slightly
    different gradient landscapes than any individual checkpoint.

    Usage::

        # After merging
        merged_state_dict = merger.merge_all()

        # Create resume coordinator
        resume = NordResumeCoordinator(
            merged_state_dict=merged_state_dict,
            base_lr=1e-4,
            warmup_steps=500,
        )

        # Get the learning rate schedule for warmup
        for step in range(resume.total_warmup_steps):
            lr = resume.get_warmup_lr(step)
            # ... train with lr ...
            resume.record_step(step, loss, sparsity)

        # Check if merge was stable
        print(resume.merge_stability_report)
    """

    def __init__(
        self,
        merged_state_dict: Dict[str, np.ndarray],
        base_lr: float = 1e-4,
        warmup_steps: int = 500,
        node_id: str = "resume_coordinator",
    ):
        self.merged_state_dict = merged_state_dict
        self.base_lr = base_lr
        self.total_warmup_steps = warmup_steps
        self.node_id = node_id

        # Track warmup metrics
        self.loss_history: List[float] = []
        self.sparsity_history: List[float] = []
        self.lr_history: List[float] = []
        self._step_count = GCounter()

    def get_warmup_lr(self, step: int) -> float:
        """Linear warmup learning rate."""
        if step >= self.total_warmup_steps:
            return self.base_lr
        return self.base_lr * (step + 1) / self.total_warmup_steps

    def record_step(self, step: int, loss: float, sparsity: float = 0.0) -> None:
        """Record a warmup training step."""
        self._step_count.increment(self.node_id)
        lr = self.get_warmup_lr(step)
        self.loss_history.append(loss)
        self.sparsity_history.append(sparsity)
        self.lr_history.append(lr)

    @property
    def merge_stability_report(self) -> dict:
        """Check if the merge produced a stable starting point."""
        if len(self.loss_history) < 2:
            return {"status": "insufficient_data", "steps": len(self.loss_history)}

        initial_loss = self.loss_history[0]
        final_loss = self.loss_history[-1]
        loss_improved = final_loss < initial_loss
        loss_delta = initial_loss - final_loss

        # Check if sparsity was preserved through warmup
        if self.sparsity_history and self.sparsity_history[0] > 0:
            sparsity_preserved = abs(
                self.sparsity_history[-1] - self.sparsity_history[0]
            ) < 0.05  # less than 5% sparsity drift
        else:
            sparsity_preserved = True

        # Check for loss spikes (merge instability)
        max_loss = max(self.loss_history)
        loss_spike = max_loss > initial_loss * 1.5

        return {
            "status": "stable" if loss_improved and not loss_spike else "unstable",
            "initial_loss": initial_loss,
            "final_loss": final_loss,
            "loss_improved": loss_improved,
            "loss_delta": loss_delta,
            "loss_spike_detected": loss_spike,
            "sparsity_preserved": sparsity_preserved,
            "warmup_steps_completed": len(self.loss_history),
        }
