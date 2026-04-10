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
Flower (flwr) integration plugin for crdt-merge.

Provides CRDT-based federated learning strategies, client wrappers,
and aggregators that work with or without the Flower framework installed.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional, Tuple

# Try importing FederatedMerge from .federated (optional internal dep)
try:
    from .federated import FederatedMerge as _FederatedMerge
except (ImportError, ModuleNotFoundError):
    _FederatedMerge = None

# Try importing Flower (optional external dep)
try:
    import flwr
    import flwr.server.strategy
    _HAS_FLWR = True
    _FlowerStrategyBase = flwr.server.strategy.Strategy
except (ImportError, ModuleNotFoundError):
    _HAS_FLWR = False
    _FlowerStrategyBase = object

__all__ = ["CRDTStrategy", "FlowerCRDTClient", "FlowerAggregator"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_values(a: Any, b: Any, resolution: str = "lww") -> Any:
    """Merge two values using the configured conflict resolution strategy.

    Supports dicts (recursive merge), lists/tuples (element-wise when
    lengths match, otherwise concatenation), and scalars (LWW / max / min).
    """
    if a is None:
        return copy.deepcopy(b)
    if b is None:
        return copy.deepcopy(a)

    # Both are dicts → recursive merge
    if isinstance(a, dict) and isinstance(b, dict):
        return _merge_dicts(a, b, resolution)

    # Both are lists or tuples → element-wise merge if same length
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) == len(b):
            merged = [_merge_values(va, vb, resolution) for va, vb in zip(a, b)]
            return type(a)(merged) if isinstance(a, tuple) else merged
        # Different lengths → last-writer-wins (take b)
        return copy.deepcopy(b)

    # Scalars
    if resolution == "lww":
        return copy.deepcopy(b)  # b is "later"
    elif resolution == "max":
        try:
            return max(a, b)
        except TypeError:
            return copy.deepcopy(b)
    elif resolution == "min":
        try:
            return min(a, b)
        except TypeError:
            return copy.deepcopy(b)
    elif resolution == "avg":
        try:
            return (a + b) / 2.0
        except TypeError:
            return copy.deepcopy(b)
    # fallback
    return copy.deepcopy(b)


def _merge_dicts(a: Dict, b: Dict, resolution: str = "lww") -> Dict:
    """Deep merge two dicts with configurable conflict resolution."""
    result: Dict[str, Any] = {}
    all_keys = set(a) | set(b)
    for key in all_keys:
        if key not in a:
            result[key] = copy.deepcopy(b[key])
        elif key not in b:
            result[key] = copy.deepcopy(a[key])
        else:
            result[key] = _merge_values(a[key], b[key], resolution)
    return result


# ---------------------------------------------------------------------------
# CRDTStrategy
# ---------------------------------------------------------------------------

class CRDTStrategy(_FlowerStrategyBase):
    """Flower-compatible federated learning strategy using CRDT merge.

    Wraps Flower's Strategy interface so model updates from FL clients
    are merged using CRDT semantics rather than FedAvg.

    Works standalone (returns dicts) or with Flower installed (implements Strategy protocol).

    Example::
        strategy = CRDTStrategy(merge_key="layer_name", conflict_resolution="lww")
        # Use with Flower server
        # fl.server.start_server(strategy=strategy, ...)
    """

    def __init__(
        self,
        merge_key: str = "layer_name",
        conflict_resolution: str = "lww",
        min_clients: int = 2,
        min_available: int = 2,
    ) -> None:
        self.merge_key = merge_key
        self.conflict_resolution = conflict_resolution
        self.min_clients = min_clients
        self.min_available = min_available

        # Statistics
        self._rounds_completed: int = 0
        self._total_merges: int = 0
        self._total_clients_seen: int = 0
        self._last_merge_ts: Optional[float] = None

    # -- Flower Strategy interface methods ---------------------------------

    def configure_fit(
        self,
        server_round: int,
        parameters: Any = None,
        client_manager: Any = None,
    ) -> List[Tuple]:
        """Configure the next round of training.

        Returns a list of (client_proxy, FitIns)-like tuples.  When running
        standalone (no Flower), returns an empty list.
        """
        if client_manager is not None and _HAS_FLWR:
            # Ask client_manager for clients when Flower is available
            try:
                sample = client_manager.sample(
                    num_clients=self.min_clients,
                    min_num_clients=self.min_available,
                )
                fit_ins = flwr.common.FitIns(parameters or flwr.common.Parameters(tensors=[], tensor_type=""), {})
                return [(client, fit_ins) for client in sample]
            except Exception:
                pass  # nosec B110 -- intentionally silent
        return []

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple],
        failures: List,
    ) -> Tuple:
        """Aggregate training results from clients using CRDT merge.

        *results* is a list of (client_proxy, FitRes)-like tuples.
        Each FitRes is expected to be a dict or an object with a
        ``parameters`` attribute that can be converted to a dict.

        Returns ``(merged_parameters, metrics_dict)``.
        """
        if not results:
            return {}, {"merged": 0}

        param_list: List[Dict] = []
        for item in results:
            params = item[1] if isinstance(item, (tuple, list)) else item
            if isinstance(params, dict):
                param_list.append(params)
            elif hasattr(params, "parameters"):
                p = params.parameters
                param_list.append(p if isinstance(p, dict) else {"raw": p})
            else:
                param_list.append({"raw": params})

        merged = self._crdt_merge_parameters(param_list)
        self._rounds_completed += 1
        self._total_clients_seen += len(results)
        self._last_merge_ts = time.time()

        metrics = {
            "merged_clients": len(results),
            "server_round": server_round,
            "failures": len(failures),
        }
        return merged, metrics

    def initialize_parameters(
        self,
        client_manager: Any = None,
    ) -> Any:
        """Return initial global parameters (None lets clients decide)."""
        return None

    def evaluate(
        self,
        server_round: int,
        parameters: Any = None,
    ) -> Any:
        """Server-side evaluation (optional). Returns None to skip."""
        return None

    def configure_evaluate(
        self,
        server_round: int,
        parameters: Any = None,
        client_manager: Any = None,
    ) -> List[Tuple]:
        """Configure the next round of evaluation.

        Returns a list of (client_proxy, EvaluateIns)-like tuples.
        """
        if client_manager is not None and _HAS_FLWR:
            try:
                sample = client_manager.sample(
                    num_clients=self.min_clients,
                    min_num_clients=self.min_available,
                )
                eval_ins = flwr.common.EvaluateIns(parameters or flwr.common.Parameters(tensors=[], tensor_type=""), {})
                return [(client, eval_ins) for client in sample]
            except Exception:
                pass  # nosec B110 -- intentionally silent
        return []

    def aggregate_evaluate(
        self,
        server_round: int,
        results: List[Tuple],
        failures: List,
    ) -> Tuple:
        """Aggregate evaluation results.

        Returns ``(loss, metrics_dict)``.
        """
        if not results:
            return 0.0, {"evaluated": 0}

        losses: List[float] = []
        for item in results:
            val = item[1] if isinstance(item, (tuple, list)) else item
            if isinstance(val, (int, float)):
                losses.append(float(val))
            elif isinstance(val, dict) and "loss" in val:
                losses.append(float(val["loss"]))
            elif hasattr(val, "loss"):
                losses.append(float(val.loss))

        avg_loss = sum(losses) / len(losses) if losses else 0.0
        metrics = {
            "evaluated_clients": len(results),
            "server_round": server_round,
            "failures": len(failures),
        }
        return avg_loss, metrics

    # -- CRDT merge core ---------------------------------------------------

    def _crdt_merge_parameters(self, parameter_list: List[Dict]) -> Dict:
        """Core CRDT merge logic for model parameters.

        Merges a list of parameter dicts pairwise using the configured
        conflict resolution strategy.  Each dict maps layer/key names
        to parameter values (scalars, lists, or nested dicts).
        """
        if not parameter_list:
            return {}
        if len(parameter_list) == 1:
            self._total_merges += 1
            return copy.deepcopy(parameter_list[0])

        merged = copy.deepcopy(parameter_list[0])
        for params in parameter_list[1:]:
            merged = _merge_dicts(merged, params, self.conflict_resolution)
            self._total_merges += 1
        return merged

    def get_merge_stats(self) -> Dict:
        """Return merge statistics."""
        return {
            "rounds_completed": self._rounds_completed,
            "total_merges": self._total_merges,
            "total_clients_seen": self._total_clients_seen,
            "last_merge_timestamp": self._last_merge_ts,
            "conflict_resolution": self.conflict_resolution,
            "merge_key": self.merge_key,
            "has_flower": _HAS_FLWR,
        }

    def to_dict(self) -> Dict:
        """Serialize strategy configuration and stats."""
        return {
            "type": "CRDTStrategy",
            "merge_key": self.merge_key,
            "conflict_resolution": self.conflict_resolution,
            "min_clients": self.min_clients,
            "min_available": self.min_available,
            "stats": self.get_merge_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"CRDTStrategy(merge_key={self.merge_key!r}, "
            f"conflict_resolution={self.conflict_resolution!r}, "
            f"min_clients={self.min_clients}, min_available={self.min_available})"
        )


# ---------------------------------------------------------------------------
# FlowerCRDTClient
# ---------------------------------------------------------------------------

class FlowerCRDTClient:
    """Flower client wrapper that applies CRDT merge to local model updates.

    Example::
        client = FlowerCRDTClient(node_id="client_1")
        merged = client.merge_update(local_params, global_params)
    """

    def __init__(
        self,
        node_id: str = "client_0",
        merge_key: str = "layer_name",
        conflict_resolution: str = "lww",
    ) -> None:
        self.node_id = node_id
        self.merge_key = merge_key
        self.conflict_resolution = conflict_resolution

        self._merge_count: int = 0
        self._last_merge_ts: Optional[float] = None

    def merge_update(self, local_params: Dict, global_params: Dict) -> Dict:
        """CRDT merge local parameters with global parameters.

        Returns a new dict containing the merged result.
        """
        merged = _merge_dicts(
            global_params or {},
            local_params or {},
            self.conflict_resolution,
        )
        self._merge_count += 1
        self._last_merge_ts = time.time()
        return merged

    def get_properties(self) -> Dict:
        """Node properties including merge stats."""
        return {
            "node_id": self.node_id,
            "merge_key": self.merge_key,
            "conflict_resolution": self.conflict_resolution,
            "merge_count": self._merge_count,
            "last_merge_timestamp": self._last_merge_ts,
            "has_flower": _HAS_FLWR,
        }

    def to_dict(self) -> Dict:
        """Serialize client configuration and stats."""
        return {
            "type": "FlowerCRDTClient",
            "node_id": self.node_id,
            "merge_key": self.merge_key,
            "conflict_resolution": self.conflict_resolution,
            "properties": self.get_properties(),
        }

    def __repr__(self) -> str:
        return (
            f"FlowerCRDTClient(node_id={self.node_id!r}, "
            f"merge_key={self.merge_key!r})"
        )


# ---------------------------------------------------------------------------
# FlowerAggregator
# ---------------------------------------------------------------------------

class FlowerAggregator:
    """Aggregates multiple Flower client results using CRDT merge.

    Example::
        agg = FlowerAggregator(conflict_resolution="lww")
        agg.add_result("client_1", {"layer1": [0.1, 0.2]})
        agg.add_result("client_2", {"layer1": [0.3, 0.4]})
        merged = agg.aggregate()
    """

    def __init__(
        self,
        conflict_resolution: str = "lww",
        merge_key: str = "layer_name",
    ) -> None:
        self.conflict_resolution = conflict_resolution
        self.merge_key = merge_key

        self._results: List[Dict] = []
        self._client_ids: List[str] = []
        self._num_examples: List[int] = []
        self._metadata: List[Dict] = []
        self._aggregate_count: int = 0
        self._last_aggregate_ts: Optional[float] = None

    def add_result(
        self,
        client_id: str,
        parameters: Dict,
        num_examples: int = 0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add a client result for later aggregation."""
        self._results.append(copy.deepcopy(parameters))
        self._client_ids.append(client_id)
        self._num_examples.append(num_examples)
        self._metadata.append(metadata or {})

    def aggregate(self) -> Dict:
        """CRDT merge all client results.

        Returns a dict containing the merged parameters.
        """
        if not self._results:
            return {}

        if len(self._results) == 1:
            merged = copy.deepcopy(self._results[0])
        else:
            merged = copy.deepcopy(self._results[0])
            for params in self._results[1:]:
                merged = _merge_dicts(merged, params, self.conflict_resolution)

        self._aggregate_count += 1
        self._last_aggregate_ts = time.time()
        return merged

    def reset(self) -> None:
        """Clear all buffered results."""
        self._results.clear()
        self._client_ids.clear()
        self._num_examples.clear()
        self._metadata.clear()

    def get_stats(self) -> Dict:
        """Return aggregation statistics."""
        return {
            "pending_results": len(self._results),
            "client_ids": list(self._client_ids),
            "total_examples": sum(self._num_examples),
            "aggregate_count": self._aggregate_count,
            "last_aggregate_timestamp": self._last_aggregate_ts,
            "conflict_resolution": self.conflict_resolution,
            "merge_key": self.merge_key,
        }

    def to_dict(self) -> Dict:
        """Serialize aggregator state."""
        return {
            "type": "FlowerAggregator",
            "conflict_resolution": self.conflict_resolution,
            "merge_key": self.merge_key,
            "pending_results": len(self._results),
            "client_ids": list(self._client_ids),
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"FlowerAggregator(conflict_resolution={self.conflict_resolution!r}, "
            f"pending={len(self._results)})"
        )
