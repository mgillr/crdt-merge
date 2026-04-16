"""
Module 3: Distributed Training State for Project Nord SNN
==========================================================
Uses CRDT primitives to track training metrics, sparsity stats,
STDP weight updates, and cross-lingual emergence — all mergeable
across distributed nodes without conflicts.
"""

import time
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from crdt_merge.core import GCounter, PNCounter, LWWRegister, LWWMap, ORSet
from crdt_merge.agentic import AgentState, SharedKnowledge, Fact
from crdt_merge.clocks import VectorClock


class NordTrainingState:
    """CRDT-based distributed training state for a single Nord node.

    Tracks all training metrics using conflict-free data types so that
    N nodes can independently train and merge their state at any time.

    CRDT mapping for Nord-specific metrics:
    - GCounter: spike counts, step counts (only increase)
    - PNCounter: STDP potentiation/depression (increase and decrease)
    - LWWRegister: loss value, learning rate (last update wins)
    - LWWMap: per-zone activation rates, per-layer sparsity
    - ORSet: emerged capabilities (cross-lingual, etc.)

    Usage::

        state = NordTrainingState(node_id="rtx5070_laptop")

        # After each training step
        state.record_step(
            step=27000,
            loss=4.4,
            sparsity=0.93,
            zone_activations={
                "sensory": 0.05,
                "association": 0.08,
                "memory_cortex": 0.39,
                "executive": 0.18,
            },
        )

        # Record STDP updates
        state.record_stdp_update(
            layer="association_zone.block_1",
            potentiation_count=1234,
            depression_count=567,
        )

        # Record emergent capabilities
        state.record_emergence("cross_lingual_russian", step=25000)

        # Merge with another node's state
        merged = state.merge(other_node_state)
    """

    def __init__(self, node_id: str):
        self.node_id = node_id

        # --- Monotonic counters (GCounter) ---
        self.total_steps = GCounter()
        self.total_spikes = GCounter()          # total spike events observed
        self.total_tokens_processed = GCounter()

        # --- Bidirectional counters (PNCounter) for STDP ---
        # STDP naturally maps to PNCounters:
        #   potentiation = increment (strengthen synapse)
        #   depression = decrement (weaken synapse)
        self.stdp_potentiation = PNCounter()    # net STDP changes
        self.stdp_updates: Dict[str, PNCounter] = {}  # per-layer STDP

        # --- Last-writer-wins registers ---
        self.current_loss = LWWRegister()
        self.current_lr = LWWRegister()
        self.current_sparsity = LWWRegister()
        self.best_loss = LWWRegister()

        # --- Per-zone activation tracking (LWWMap) ---
        self.zone_activations = LWWMap()        # zone -> activation rate
        self.layer_sparsity = LWWMap()          # layer -> sparsity fraction

        # --- Emergent capabilities (ORSet — add-wins) ---
        self.emerged_capabilities = ORSet()

        # --- AgentState for rich metadata ---
        self._agent = AgentState(agent_id=node_id)

        # --- Causal clock ---
        self.clock = VectorClock()

    def record_step(
        self,
        step: int,
        loss: float,
        sparsity: float = 0.93,
        lr: float = 0.0,
        zone_activations: Optional[Dict[str, float]] = None,
        tokens_in_batch: int = 0,
    ) -> None:
        """Record metrics from a training step."""
        ts = time.time()
        self.clock = self.clock.increment(self.node_id)

        self.total_steps.increment(self.node_id)
        if tokens_in_batch > 0:
            self.total_tokens_processed.increment(self.node_id, tokens_in_batch)

        self.current_loss.set(loss, timestamp=ts, node_id=self.node_id)
        self.current_sparsity.set(sparsity, timestamp=ts, node_id=self.node_id)
        if lr > 0:
            self.current_lr.set(lr, timestamp=ts, node_id=self.node_id)

        # Track best loss (using LWW — most recent "best" wins)
        current_best = self.best_loss.value
        if current_best is None or loss < current_best:
            self.best_loss.set(loss, timestamp=ts, node_id=self.node_id)

        # Zone activations
        if zone_activations:
            for zone, rate in zone_activations.items():
                self.zone_activations.set(
                    zone, rate, timestamp=ts, node_id=self.node_id
                )

        # Record as agent fact for rich provenance
        self._agent.add_fact(
            f"step_{step}",
            {"loss": loss, "sparsity": sparsity, "step": step},
            confidence=1.0,
            timestamp=ts,
        )

    def record_spikes(self, count: int) -> None:
        """Record spike events from a forward pass."""
        self.total_spikes.increment(self.node_id, count)

    def record_stdp_update(
        self,
        layer: str,
        potentiation_count: int = 0,
        depression_count: int = 0,
    ) -> None:
        """Record STDP weight updates for a layer.

        STDP (Spike-Timing Dependent Plasticity) is Nord's online
        learning mechanism. Potentiation strengthens synapses (pre
        fires before post), depression weakens them (post before pre).

        This maps perfectly to CRDT PNCounters:
        - Potentiation → increment (synapse strengthening)
        - Depression → decrement (synapse weakening)
        """
        if layer not in self.stdp_updates:
            self.stdp_updates[layer] = PNCounter()

        if potentiation_count > 0:
            self.stdp_updates[layer].increment(self.node_id, potentiation_count)
            self.stdp_potentiation.increment(self.node_id, potentiation_count)

        if depression_count > 0:
            self.stdp_updates[layer].decrement(self.node_id, depression_count)
            self.stdp_potentiation.decrement(self.node_id, depression_count)

    def record_emergence(self, capability: str, step: int = 0) -> None:
        """Record an emergent capability.

        Uses ORSet (add-wins semantics) so that once a capability is
        observed by any node, it persists across all merges.

        Example: "cross_lingual_russian" emerged at step 25000.
        """
        self.emerged_capabilities.add(f"{capability}@step_{step}")
        self._agent.add_fact(
            f"emergence_{capability}",
            {"capability": capability, "step": step},
            confidence=0.9,
        )
        self._agent.add_tag(f"emergence:{capability}")

    def record_layer_sparsity(
        self, layer_name: str, sparsity: float
    ) -> None:
        """Record per-layer sparsity measurement."""
        self.layer_sparsity.set(
            layer_name, sparsity,
            timestamp=time.time(), node_id=self.node_id,
        )

    def merge(self, other: "NordTrainingState") -> "NordTrainingState":
        """Merge two training states (CRDT — order independent).

        This is the core CRDT guarantee: merge(A,B) == merge(B,A).
        Any number of nodes can merge in any order and converge.
        """
        result = NordTrainingState(node_id=f"{self.node_id}+{other.node_id}")

        # GCounters: element-wise max per node
        result.total_steps = self.total_steps.merge(other.total_steps)
        result.total_spikes = self.total_spikes.merge(other.total_spikes)
        result.total_tokens_processed = self.total_tokens_processed.merge(
            other.total_tokens_processed
        )

        # PNCounters: merge positive and negative independently
        result.stdp_potentiation = self.stdp_potentiation.merge(
            other.stdp_potentiation
        )

        # Per-layer STDP counters
        all_layers = set(self.stdp_updates) | set(other.stdp_updates)
        for layer in all_layers:
            a = self.stdp_updates.get(layer, PNCounter())
            b = other.stdp_updates.get(layer, PNCounter())
            result.stdp_updates[layer] = a.merge(b)

        # LWW Registers: latest timestamp wins
        result.current_loss = self.current_loss.merge(other.current_loss)
        result.current_lr = self.current_lr.merge(other.current_lr)
        result.current_sparsity = self.current_sparsity.merge(
            other.current_sparsity
        )
        result.best_loss = self.best_loss.merge(other.best_loss)

        # LWW Maps: per-key LWW
        result.zone_activations = self.zone_activations.merge(
            other.zone_activations
        )
        result.layer_sparsity = self.layer_sparsity.merge(
            other.layer_sparsity
        )

        # ORSet: union (add-wins)
        result.emerged_capabilities = self.emerged_capabilities.merge(
            other.emerged_capabilities
        )

        # Vector clock: element-wise max
        result.clock = self.clock.merge(other.clock)

        return result

    @property
    def summary(self) -> dict:
        """Human-readable summary of the training state."""
        return {
            "node_id": self.node_id,
            "total_steps": self.total_steps.value,
            "total_spikes": self.total_spikes.value,
            "total_tokens": self.total_tokens_processed.value,
            "current_loss": self.current_loss.value,
            "current_sparsity": self.current_sparsity.value,
            "best_loss": self.best_loss.value,
            "net_stdp_updates": self.stdp_potentiation.value,
            "zone_activations": dict(self.zone_activations.value),
            "emerged_capabilities": sorted(self.emerged_capabilities.value),
            "causal_clock": dict(self.clock._clocks),
        }


class NordMemoryState:
    """CRDT state for Nord's Genesis Triple Memory module.

    Nord's memory cortex has 3 banks:
    - Structural (96 neurons): architectural patterns
    - Personal (96 neurons): contextual continuity
    - Auxiliary (64 neurons): overflow

    Plus an Archive Grid with 32 key-value RAG slots.

    This module replicates the memory state using CRDTs so that
    distributed nodes maintain consistent memory.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id

        # Each memory bank is a LWWMap (key → value, last writer wins)
        self.structural_bank = LWWMap()     # 96 neuron states
        self.personal_bank = LWWMap()       # 96 neuron states
        self.auxiliary_bank = LWWMap()       # 64 neuron states

        # Archive Grid: 32 RAG slots tracked as ORSet
        # (add-wins so knowledge is never lost)
        self.archive_keys = ORSet()
        self.archive_values = LWWMap()      # slot_id → value

        # Memory access counters
        self.read_count = GCounter()
        self.write_count = GCounter()

    def update_structural(self, neuron_id: int, state: float) -> None:
        ts = time.time()
        self.structural_bank.set(
            str(neuron_id), state, timestamp=ts, node_id=self.node_id
        )
        self.write_count.increment(self.node_id)

    def update_personal(self, neuron_id: int, state: float) -> None:
        ts = time.time()
        self.personal_bank.set(
            str(neuron_id), state, timestamp=ts, node_id=self.node_id
        )
        self.write_count.increment(self.node_id)

    def update_auxiliary(self, neuron_id: int, state: float) -> None:
        ts = time.time()
        self.auxiliary_bank.set(
            str(neuron_id), state, timestamp=ts, node_id=self.node_id
        )
        self.write_count.increment(self.node_id)

    def store_archive(self, slot_id: str, value: Any) -> None:
        """Store a key-value pair in the Archive Grid."""
        ts = time.time()
        self.archive_keys.add(slot_id)
        self.archive_values.set(slot_id, value, timestamp=ts, node_id=self.node_id)
        self.write_count.increment(self.node_id)

    def merge(self, other: "NordMemoryState") -> "NordMemoryState":
        result = NordMemoryState(f"{self.node_id}+{other.node_id}")
        result.structural_bank = self.structural_bank.merge(other.structural_bank)
        result.personal_bank = self.personal_bank.merge(other.personal_bank)
        result.auxiliary_bank = self.auxiliary_bank.merge(other.auxiliary_bank)
        result.archive_keys = self.archive_keys.merge(other.archive_keys)
        result.archive_values = self.archive_values.merge(other.archive_values)
        result.read_count = self.read_count.merge(other.read_count)
        result.write_count = self.write_count.merge(other.write_count)
        return result

    @property
    def summary(self) -> dict:
        return {
            "structural_neurons": len(self.structural_bank.value),
            "personal_neurons": len(self.personal_bank.value),
            "auxiliary_neurons": len(self.auxiliary_bank.value),
            "archive_slots_used": len(self.archive_keys.value),
            "total_reads": self.read_count.value,
            "total_writes": self.write_count.value,
        }
