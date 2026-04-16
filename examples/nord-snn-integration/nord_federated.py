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

"""
Module 1: Federated Training for Project Nord SNN
==================================================
Allows multiple GPU nodes to train Nord independently and merge
checkpoints using CRDT guarantees — no central parameter server needed.

The developer ran out of budget at $670. With this module, N people
can each train on their own hardware and merge results deterministically.
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple

from crdt_merge.model.federated import FederatedMerge, FederatedResult
from crdt_merge.model.crdt_state import CRDTMergeState, MergeContribution
from crdt_merge.core import GCounter, PNCounter, LWWRegister, LWWMap
from crdt_merge.gossip import GossipState
from crdt_merge.clocks import VectorClock


# ---------------------------------------------------------------------------
# 1. Zone-aware federated merge for Nord's 4-zone architecture
# ---------------------------------------------------------------------------

# Nord's architecture has 4 zones with different learning dynamics:
#   - Sensory Zone (3 blocks, 3-7% activation)
#   - Association Zone (3 blocks, Spike-Driven MoE, 4-12% activation)
#   - Memory Cortex (tau=0.99, 39% activation, persistent LIF)
#   - Executive Zone (4 blocks, 4-33% activation)
#
# Each zone needs a different merge strategy because:
#   - Sensory/Executive: standard weight averaging works (low spike variance)
#   - Association MoE: experts must be aligned before averaging
#   - Memory Cortex: persistent state must use LWW (last-writer-wins) semantics

NORD_ZONES = {
    "sensory": {
        "pattern": "sensory_zone.*",
        "strategy": "fedavg",
        "description": "Feature extraction — stable, low activation",
    },
    "association": {
        "pattern": "association_zone.*",
        "strategy": "fedavg",
        "description": "Spike-driven MoE — expert routing from spike dynamics",
    },
    "memory_cortex": {
        "pattern": "memory_cortex.*",
        "strategy": "fedprox",  # Proximal to prevent memory drift
        "description": "Persistent LIF neurons, tau=0.99, 39% activation",
    },
    "executive": {
        "pattern": "executive_zone.*",
        "strategy": "fedavg",
        "description": "Decision making and output generation",
    },
    "temporal_encoder": {
        "pattern": "temporal_spike_encoder.*",
        "strategy": "fedavg",
        "description": "Spike temporal encoding (263M params)",
    },
    "readout": {
        "pattern": "readout.*|lm_head.*",
        "strategy": "fedavg",
        "description": "EMA temporal readout + LM head (263M params)",
    },
    "stdp_engine": {
        "pattern": "stdp.*",
        "strategy": "fedprox",  # STDP weights must stay close to global
        "description": "Reward-modulated STDP (3M params)",
    },
}


class NordFederatedTrainer:
    """Federated training coordinator for Project Nord SNN.

    Each participant trains locally, then submits their state_dict.
    The coordinator merges all contributions zone-by-zone using
    the appropriate strategy for each architectural zone.

    Usage::

        coordinator = NordFederatedTrainer()

        # Each participant trains locally and submits
        coordinator.submit_checkpoint(
            node_id="rtx5070_laptop",
            state_dict=model.state_dict(),
            num_samples=50000,
            steps_trained=5000,
            metadata={"gpu": "RTX 5070", "loss": 4.4}
        )

        coordinator.submit_checkpoint(
            node_id="colab_a100",
            state_dict=other_model.state_dict(),
            num_samples=100000,
            steps_trained=10000,
            metadata={"gpu": "A100", "loss": 4.1}
        )

        # Merge all contributions
        merged_state_dict, report = coordinator.merge_round()
    """

    def __init__(self, mu: float = 0.01):
        self._mu = mu
        # One FederatedMerge per zone
        self._zone_mergers: Dict[str, FederatedMerge] = {}
        # Track metadata per node
        self._node_metadata: Dict[str, dict] = {}
        # CRDT counters for tracking global training progress
        self._total_steps = GCounter()
        self._total_samples = GCounter()
        # Vector clock for causal ordering of merge rounds
        self._clock = VectorClock()
        # Round counter
        self._round = 0

    def _classify_layer(self, layer_name: str) -> str:
        """Classify a layer name into its Nord zone."""
        ln = layer_name.lower()
        if "sensory" in ln:
            return "sensory"
        elif "association" in ln or "moe" in ln or "expert" in ln:
            return "association"
        elif "memory" in ln or "genesis" in ln or "archive" in ln:
            return "memory_cortex"
        elif "executive" in ln:
            return "executive"
        elif "temporal" in ln or "spike_encoder" in ln:
            return "temporal_encoder"
        elif "readout" in ln or "lm_head" in ln:
            return "readout"
        elif "stdp" in ln:
            return "stdp_engine"
        else:
            return "sensory"  # default fallback

    def submit_checkpoint(
        self,
        node_id: str,
        state_dict: Dict[str, np.ndarray],
        num_samples: int,
        steps_trained: int = 0,
        metadata: Optional[dict] = None,
    ) -> None:
        """Submit a training checkpoint from a participant node.

        Parameters
        ----------
        node_id : str
            Unique identifier for this training node.
        state_dict : dict
            Model state dict mapping layer names to numpy arrays.
        num_samples : int
            Number of training samples this node processed.
        steps_trained : int
            Number of gradient steps completed.
        metadata : dict, optional
            Extra info (gpu type, loss value, etc.)
        """
        # Track global progress with CRDT counters
        self._total_steps.increment(node_id, steps_trained)
        self._total_samples.increment(node_id, num_samples)
        self._node_metadata[node_id] = metadata or {}

        # Split state_dict by zone and submit to zone-specific mergers
        zone_dicts: Dict[str, Dict[str, np.ndarray]] = {}
        for layer_name, tensor in state_dict.items():
            zone = self._classify_layer(layer_name)
            if zone not in zone_dicts:
                zone_dicts[zone] = {}
            zone_dicts[zone][layer_name] = tensor

        for zone_name, zone_dict in zone_dicts.items():
            if zone_name not in self._zone_mergers:
                zone_info = NORD_ZONES.get(zone_name, NORD_ZONES["sensory"])
                self._zone_mergers[zone_name] = FederatedMerge(
                    strategy=zone_info["strategy"],
                    mu=self._mu,
                )
            self._zone_mergers[zone_name].submit(
                client_id=node_id,
                model_update=zone_dict,
                num_samples=num_samples,
            )

    def merge_round(
        self,
        global_model: Optional[Dict[str, np.ndarray]] = None,
    ) -> Tuple[Dict[str, np.ndarray], dict]:
        """Execute one federated merge round.

        Returns
        -------
        merged_state_dict : dict
            The merged model weights.
        report : dict
            Merge report with per-zone stats and global counters.
        """
        self._round += 1
        merged_state_dict = {}
        zone_reports = {}

        for zone_name, merger in self._zone_mergers.items():
            zone_info = NORD_ZONES.get(zone_name, NORD_ZONES["sensory"])

            # For FedProx zones, pass global model for proximal term
            # On the first round (no global model), fall back to fedavg
            zone_global = None
            if zone_info["strategy"] == "fedprox" and global_model:
                zone_global = {
                    k: v for k, v in global_model.items()
                    if self._classify_layer(k) == zone_name
                }
            elif zone_info["strategy"] == "fedprox" and global_model is None:
                # First round: no global model yet, use fedavg semantics
                # by creating a temporary FedAvg merger
                temp_merger = FederatedMerge(strategy="fedavg")
                for cid in merger.clients:
                    temp_merger.submit(
                        cid,
                        merger._submissions[cid],
                        merger._sample_counts[cid],
                    )
                result = temp_merger.aggregate()
                merged_state_dict.update(result.model)
                zone_reports[zone_name] = {
                    "strategy": "fedavg (first round, no global model)",
                    "num_clients": result.num_clients,
                    "total_samples": result.total_samples,
                    "client_contributions": result.client_contributions,
                }
                merger.clear()
                continue

            result: FederatedResult = merger.aggregate(
                global_model=zone_global
            )
            merged_state_dict.update(result.model)
            zone_reports[zone_name] = {
                "strategy": result.strategy_used,
                "num_clients": result.num_clients,
                "total_samples": result.total_samples,
                "client_contributions": result.client_contributions,
            }
            merger.clear()

        report = {
            "round": self._round,
            "global_steps": self._total_steps.value,
            "global_samples": self._total_samples.value,
            "num_nodes": len(self._node_metadata),
            "zones": zone_reports,
            "node_metadata": dict(self._node_metadata),
        }

        return merged_state_dict, report


# ---------------------------------------------------------------------------
# 2. CRDT-based checkpoint merging for async contributions
# ---------------------------------------------------------------------------

class NordCheckpointMerger:
    """Merge Nord checkpoints from multiple training runs using CRDT state.

    Unlike FederatedMerge which does weighted averaging, this uses
    CRDTMergeState to guarantee merge order independence. Two nodes
    merging A+B or B+A always get the exact same result.

    This is ideal for the community training scenario: many people
    train independently and upload checkpoints. Any merge order
    produces identical output.

    Usage::

        merger = NordCheckpointMerger(strategy="weight_average")

        merger.add_checkpoint(
            "rtx5070_27k_steps",
            state_dict_a,
            weight=0.4,  # trained less
        )
        merger.add_checkpoint(
            "a100_50k_steps",
            state_dict_b,
            weight=0.6,  # trained more
        )

        merged = merger.resolve()
    """

    def __init__(self, strategy: str = "weight_average"):
        self._strategy = strategy
        self._layer_states: Dict[str, CRDTMergeState] = {}

    def add_checkpoint(
        self,
        checkpoint_id: str,
        state_dict: Dict[str, np.ndarray],
        weight: float = 1.0,
    ) -> None:
        """Add a checkpoint contribution."""
        for layer_name, tensor in state_dict.items():
            if layer_name not in self._layer_states:
                self._layer_states[layer_name] = CRDTMergeState(
                    self._strategy
                )
            self._layer_states[layer_name].add(
                tensor=tensor,
                model_id=checkpoint_id,
                weight=weight,
            )

    def resolve(self) -> Dict[str, np.ndarray]:
        """Resolve all layers to get the merged state dict."""
        merged = {}
        for layer_name, state in self._layer_states.items():
            result = state.resolve()
            # resolve() returns numpy.ndarray directly (not MergeResult)
            merged[layer_name] = np.asarray(result)
        return merged

    def merge_with(self, other: "NordCheckpointMerger") -> "NordCheckpointMerger":
        """Merge two checkpoint mergers (CRDT merge — order independent)."""
        result = NordCheckpointMerger(strategy=self._strategy)
        all_layers = set(self._layer_states) | set(other._layer_states)
        for layer in all_layers:
            if layer in self._layer_states and layer in other._layer_states:
                result._layer_states[layer] = self._layer_states[layer].merge(
                    other._layer_states[layer]
                )
            elif layer in self._layer_states:
                result._layer_states[layer] = self._layer_states[layer]
            else:
                result._layer_states[layer] = other._layer_states[layer]
        return result
