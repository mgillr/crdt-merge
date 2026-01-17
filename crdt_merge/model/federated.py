# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Federated learning bridge — FedAvg and FedProx as CRDT operations.

Example::

    from crdt_merge.model.federated import FederatedMerge

    fed = FederatedMerge(strategy="fedavg")
    fed.submit("client_a", {"w": [1.0, 2.0]}, num_samples=100)
    fed.submit("client_b", {"w": [3.0, 4.0]}, num_samples=200)
    result = fed.aggregate()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crdt_merge.model.strategies.base import _get_np

__all__ = ["FederatedMerge", "FederatedResult"]

def _weighted_combine(tensors: list, weights: List[float]) -> Any:
    """Weighted combination of tensor-like objects."""
    np = _get_np()
    if np is not None:
        arrays = [np.asarray(t, dtype=float) for t in tensors]
        result = sum(w * a for w, a in zip(weights, arrays))
        return result.tolist()
    # Fallback: plain lists
    if isinstance(tensors[0], (list, tuple)):
        length = len(tensors[0])
        result = [0.0] * length
        for t, w in zip(tensors, weights):
            for i in range(length):
                result[i] += w * t[i]
        return result
    # Scalars
    return sum(w * t for w, t in zip(weights, tensors))

def _subtract(a: Any, b: Any) -> Any:
    """Element-wise subtraction a - b."""
    np = _get_np()
    if np is not None:
        return (np.asarray(a, dtype=float) - np.asarray(b, dtype=float)).tolist()
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return [x - y for x, y in zip(a, b)]
    return a - b

def _add(a: Any, b: Any) -> Any:
    """Element-wise addition."""
    np = _get_np()
    if np is not None:
        return (np.asarray(a, dtype=float) + np.asarray(b, dtype=float)).tolist()
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return [x + y for x, y in zip(a, b)]
    return a + b

def _scale(tensor: Any, s: float) -> Any:
    """Multiply tensor by scalar."""
    np = _get_np()
    if np is not None:
        return (np.asarray(tensor, dtype=float) * s).tolist()
    if isinstance(tensor, (list, tuple)):
        return [x * s for x in tensor]
    return tensor * s

@dataclass
class FederatedResult:
    """Result of a federated aggregation round.

    Attributes
    ----------
    model : dict
        Aggregated model state_dict.
    client_contributions : dict[str, float]
        Per-client weight used during aggregation.
    num_clients : int
        Number of participating clients.
    total_samples : int
        Total training samples across all clients.
    strategy_used : str
        The aggregation strategy used.
    """

    model: dict
    client_contributions: Dict[str, float]
    num_clients: int
    total_samples: int
    strategy_used: str

class FederatedMerge:
    """Federated learning bridge for FedAvg and FedProx aggregation.

    Parameters
    ----------
    strategy : str
        ``"fedavg"`` for sample-weighted averaging,
        ``"fedprox"`` for proximal regularization.
    mu : float
        Proximal term coefficient (FedProx only).
    """

    SUPPORTED_STRATEGIES = ("fedavg", "fedprox")

    def __init__(self, strategy: str = "fedavg", mu: float = 0.01) -> None:
        strategy = strategy.lower()
        if strategy not in self.SUPPORTED_STRATEGIES:
            raise ValueError(
                f"Unknown federated strategy '{strategy}'. "
                f"Supported: {self.SUPPORTED_STRATEGIES}"
            )
        self._strategy = strategy
        self._mu = mu
        self._submissions: Dict[str, dict] = {}
        self._sample_counts: Dict[str, int] = {}

    def submit(
        self,
        client_id: str,
        model_update: dict,
        num_samples: int = 1,
    ) -> None:
        """Register a client's model update.

        Parameters
        ----------
        client_id : str
            Unique identifier for the client.
        model_update : dict
            The client's updated model state_dict.
        num_samples : int
            Number of training samples used by this client.
        """
        self._submissions[client_id] = model_update
        self._sample_counts[client_id] = num_samples

    def aggregate(self, global_model: Optional[dict] = None) -> FederatedResult:
        """Aggregate all submitted client updates.

        Parameters
        ----------
        global_model : dict | None
            Required for FedProx; the current global model for proximal term.

        Returns
        -------
        FederatedResult
        """
        if not self._submissions:
            raise ValueError("No client submissions to aggregate")

        if self._strategy == "fedprox" and global_model is None:
            raise ValueError("FedProx requires a global_model for proximal term")

        total_samples = self.total_samples
        client_ids = list(self._submissions.keys())

        # Compute per-client weights (sample-proportional)
        contributions: Dict[str, float] = {}
        for cid in client_ids:
            contributions[cid] = self._sample_counts[cid] / total_samples

        # Collect all layer names
        all_layers: List[str] = []
        seen = set()
        for cid in client_ids:
            for layer in self._submissions[cid]:
                if layer not in seen:
                    seen.add(layer)
                    all_layers.append(layer)

        merged: dict = {}
        for layer in all_layers:
            tensors = []
            weights = []
            for cid in client_ids:
                if layer in self._submissions[cid]:
                    t = self._submissions[cid][layer]
                    if self._strategy == "fedprox" and global_model is not None:
                        # FedProx: θ_adjusted = θ_i - μ(θ_i - θ_global)
                        if layer in global_model:
                            drift = _subtract(t, global_model[layer])
                            correction = _scale(drift, self._mu)
                            t = _subtract(t, correction)
                    tensors.append(t)
                    weights.append(contributions[cid])

            if tensors:
                # Re-normalize weights for layers that might be missing from some clients
                w_sum = sum(weights)
                if w_sum > 0:
                    norm_weights = [w / w_sum for w in weights]
                else:
                    norm_weights = [1.0 / len(weights)] * len(weights)
                merged[layer] = _weighted_combine(tensors, norm_weights)

        return FederatedResult(
            model=merged,
            client_contributions=contributions,
            num_clients=len(client_ids),
            total_samples=total_samples,
            strategy_used=self._strategy,
        )

    def clear(self) -> None:
        """Clear all submissions for the next round."""
        self._submissions.clear()
        self._sample_counts.clear()

    @property
    def clients(self) -> List[str]:
        """List of submitted client IDs."""
        return list(self._submissions.keys())

    @property
    def total_samples(self) -> int:
        """Total training samples across all clients."""
        return sum(self._sample_counts.values())
