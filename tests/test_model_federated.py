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
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.model.federated — FederatedMerge and FederatedResult."""

from __future__ import annotations

import math

import pytest

from crdt_merge.model.federated import FederatedMerge, FederatedResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _close(a, b, tol=1e-6):
    """Scalar or list approximate equality."""
    if isinstance(a, (list, tuple)):
        return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))
    return math.isclose(a, b, abs_tol=tol)


# ---------------------------------------------------------------------------
# FederatedMerge -- initialization
# ---------------------------------------------------------------------------

class TestFederatedMergeInit:
    def test_default_strategy_is_fedavg(self):
        fed = FederatedMerge()
        assert fed._strategy == "fedavg"

    def test_explicit_fedavg(self):
        fed = FederatedMerge(strategy="fedavg")
        assert fed._strategy == "fedavg"

    def test_explicit_fedprox(self):
        fed = FederatedMerge(strategy="fedprox", mu=0.1)
        assert fed._strategy == "fedprox"
        assert math.isclose(fed._mu, 0.1)

    def test_strategy_case_insensitive(self):
        fed = FederatedMerge(strategy="FedAvg")
        assert fed._strategy == "fedavg"

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown federated strategy"):
            FederatedMerge(strategy="bogus")

    def test_initial_state_empty(self):
        fed = FederatedMerge()
        assert fed.clients == []
        assert fed.total_samples == 0


# ---------------------------------------------------------------------------
# FederatedMerge.submit
# ---------------------------------------------------------------------------

class TestFederatedMergeSubmit:
    def test_submit_registers_client(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0, 2.0]}, num_samples=10)
        assert "c1" in fed.clients

    def test_submit_multiple_clients(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=5)
        fed.submit("c2", {"w": [2.0]}, num_samples=15)
        assert set(fed.clients) == {"c1", "c2"}

    def test_total_samples_accumulates(self):
        fed = FederatedMerge()
        fed.submit("c1", {}, num_samples=100)
        fed.submit("c2", {}, num_samples=200)
        assert fed.total_samples == 300

    def test_submit_overwrites_same_client(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=10)
        fed.submit("c1", {"w": [9.0]}, num_samples=20)
        assert fed._submissions["c1"]["w"] == [9.0]
        assert fed._sample_counts["c1"] == 20


# ---------------------------------------------------------------------------
# FederatedMerge.aggregate -- FedAvg
# ---------------------------------------------------------------------------

class TestFederatedMergeFedAvg:
    def test_aggregate_no_submissions_raises(self):
        fed = FederatedMerge()
        with pytest.raises(ValueError, match="No client submissions"):
            fed.aggregate()

    def test_single_client_returns_copy(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0, 2.0]}, num_samples=10)
        result = fed.aggregate()
        assert _close(result.model["w"], [1.0, 2.0])

    def test_equal_samples_produces_simple_average(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [0.0, 0.0]}, num_samples=50)
        fed.submit("c2", {"w": [2.0, 4.0]}, num_samples=50)
        result = fed.aggregate()
        assert _close(result.model["w"], [1.0, 2.0])

    def test_weighted_average_by_sample_count(self):
        fed = FederatedMerge()
        # c1 has 100 samples, c2 has 300 samples → weights 0.25, 0.75
        fed.submit("c1", {"w": [0.0]}, num_samples=100)
        fed.submit("c2", {"w": [4.0]}, num_samples=300)
        result = fed.aggregate()
        expected = 0.25 * 0.0 + 0.75 * 4.0  # 3.0
        assert _close(result.model["w"][0], expected)

    def test_result_metadata(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=10)
        fed.submit("c2", {"w": [3.0]}, num_samples=10)
        result = fed.aggregate()
        assert result.num_clients == 2
        assert result.total_samples == 20
        assert result.strategy_used == "fedavg"
        assert set(result.client_contributions.keys()) == {"c1", "c2"}

    def test_contributions_sum_to_one(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=30)
        fed.submit("c2", {"w": [2.0]}, num_samples=70)
        result = fed.aggregate()
        total = sum(result.client_contributions.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9)

    def test_aggregate_scalar_values(self):
        fed = FederatedMerge()
        fed.submit("c1", {"bias": 0.0}, num_samples=1)
        fed.submit("c2", {"bias": 2.0}, num_samples=1)
        result = fed.aggregate()
        assert math.isclose(result.model["bias"], 1.0, abs_tol=1e-6)

    def test_missing_layer_handled_gracefully(self):
        """Layers present in some but not all clients are still aggregated."""
        fed = FederatedMerge()
        fed.submit("c1", {"a": [1.0], "b": [2.0]}, num_samples=10)
        fed.submit("c2", {"a": [3.0]}, num_samples=10)
        result = fed.aggregate()
        assert "a" in result.model
        assert "b" in result.model  # from c1 only


# ---------------------------------------------------------------------------
# FederatedMerge.aggregate -- FedProx
# ---------------------------------------------------------------------------

class TestFederatedMergeFedProx:
    def test_fedprox_requires_global_model(self):
        fed = FederatedMerge(strategy="fedprox")
        fed.submit("c1", {"w": [1.0]}, num_samples=10)
        with pytest.raises(ValueError, match="FedProx requires a global_model"):
            fed.aggregate()

    def test_fedprox_with_global_model(self):
        fed = FederatedMerge(strategy="fedprox", mu=0.0)
        global_model = {"w": [0.0]}
        fed.submit("c1", {"w": [2.0]}, num_samples=50)
        fed.submit("c2", {"w": [4.0]}, num_samples=50)
        # mu=0.0 → no proximal correction → same as FedAvg
        result = fed.aggregate(global_model=global_model)
        assert _close(result.model["w"], [3.0])
        assert result.strategy_used == "fedprox"

    def test_fedprox_proximal_correction_reduces_drift(self):
        """With high mu the aggregated value should be closer to the global model."""
        global_model = {"w": [0.0]}
        fed_low = FederatedMerge(strategy="fedprox", mu=0.0)
        fed_high = FederatedMerge(strategy="fedprox", mu=0.9)
        for fed in (fed_low, fed_high):
            fed.submit("c1", {"w": [10.0]}, num_samples=50)
            fed.submit("c2", {"w": [10.0]}, num_samples=50)
        r_low = fed_low.aggregate(global_model=global_model)
        r_high = fed_high.aggregate(global_model=global_model)
        # High mu should push value closer to 0 (global) vs low mu
        assert r_high.model["w"][0] < r_low.model["w"][0]


# ---------------------------------------------------------------------------
# FederatedMerge.clear
# ---------------------------------------------------------------------------

class TestFederatedMergeClear:
    def test_clear_empties_state(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=10)
        fed.clear()
        assert fed.clients == []
        assert fed.total_samples == 0

    def test_clear_then_aggregate_raises(self):
        fed = FederatedMerge()
        fed.submit("c1", {"w": [1.0]}, num_samples=10)
        fed.clear()
        with pytest.raises(ValueError, match="No client submissions"):
            fed.aggregate()
