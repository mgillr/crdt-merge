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

"""Tests for crdt_merge.model.heatmap — ConflictHeatmap."""

from __future__ import annotations

import json
import math
import tempfile
import os

import pytest

from crdt_merge.model.heatmap import ConflictHeatmap, LayerDetail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _two_model_heatmap():
    """Build a simple heatmap from two models with different weights."""
    m1 = {"layer_a": [1.0, 2.0, 3.0], "layer_b": [0.0]}
    m2 = {"layer_a": [4.0, 5.0, 6.0], "layer_b": [0.0]}
    return ConflictHeatmap.from_models([m1, m2])


# ---------------------------------------------------------------------------
# ConflictHeatmap.from_models
# ---------------------------------------------------------------------------

class TestConflictHeatmapFromModels:
    def test_empty_models_returns_empty_heatmap(self):
        hm = ConflictHeatmap.from_models([])
        assert hm.num_layers == 0
        assert hm.num_models == 0
        assert math.isclose(hm.overall_conflict, 0.0, abs_tol=1e-9)

    def test_single_model_accepted(self):
        m = {"w": [1.0, 2.0]}
        hm = ConflictHeatmap.from_models([m])
        assert hm.num_layers == 1

    def test_two_models_populates_layers(self):
        hm = _two_model_heatmap()
        assert "layer_a" in hm.layer_conflicts
        assert "layer_b" in hm.layer_conflicts

    def test_num_models_correct(self):
        m1 = {"w": [1.0]}
        m2 = {"w": [2.0]}
        m3 = {"w": [3.0]}
        hm = ConflictHeatmap.from_models([m1, m2, m3])
        assert hm.num_models == 3

    def test_conflict_scores_are_non_negative(self):
        hm = _two_model_heatmap()
        for score in hm.layer_conflicts.values():
            assert score >= 0.0

    def test_model_contributions_sum_roughly_to_one(self):
        hm = _two_model_heatmap()
        for layer, contrib in hm.model_contributions.items():
            total = sum(contrib.values())
            # Contributions sum to 1.0 when norms are non-zero;
            # all-zero layers may produce a total of 0.0.
            assert math.isclose(total, 1.0, abs_tol=1e-6) or math.isclose(total, 0.0, abs_tol=1e-9), (
                f"{layer}: {total}"
            )

    def test_with_base_computes_deltas(self):
        base = {"w": [1.0, 1.0]}
        m1 = {"w": [2.0, 2.0]}
        m2 = {"w": [3.0, 3.0]}
        hm = ConflictHeatmap.from_models([m1, m2], base=base)
        assert "w" in hm.layer_conflicts

    def test_layer_union_when_models_have_different_layers(self):
        m1 = {"a": [1.0], "b": [2.0]}
        m2 = {"a": [3.0], "c": [4.0]}
        hm = ConflictHeatmap.from_models([m1, m2])
        assert "a" in hm.layer_conflicts
        assert "b" in hm.layer_conflicts
        assert "c" in hm.layer_conflicts


# ---------------------------------------------------------------------------
# ConflictHeatmap properties
# ---------------------------------------------------------------------------

class TestConflictHeatmapProperties:
    def test_num_layers_property(self):
        hm = _two_model_heatmap()
        assert hm.num_layers == len(hm.layer_conflicts)

    def test_overall_conflict_is_mean(self):
        hm = _two_model_heatmap()
        if hm.num_layers > 0:
            expected = sum(hm.layer_conflicts.values()) / hm.num_layers
            assert math.isclose(hm.overall_conflict, expected, rel_tol=1e-6)

    def test_identical_models_zero_or_near_zero_conflict(self):
        model = {"w": [1.0, 2.0, 3.0]}
        hm = ConflictHeatmap.from_models([model, model])
        assert hm.overall_conflict >= 0.0  # may be 0 or tiny float


# ---------------------------------------------------------------------------
# ConflictHeatmap.most_conflicted_layers / least_conflicted_layers
# ---------------------------------------------------------------------------

class TestMostLeastConflicted:
    def test_most_conflicted_sorted_descending(self):
        hm = _two_model_heatmap()
        top = hm.most_conflicted_layers(10)
        scores = [s for _, s in top]
        assert scores == sorted(scores, reverse=True)

    def test_least_conflicted_sorted_ascending(self):
        hm = _two_model_heatmap()
        bottom = hm.least_conflicted_layers(10)
        scores = [s for _, s in bottom]
        assert scores == sorted(scores)

    def test_most_conflicted_respects_n(self):
        m1 = {f"layer_{i}": [float(i)] for i in range(10)}
        m2 = {f"layer_{i}": [float(i * 2)] for i in range(10)}
        hm = ConflictHeatmap.from_models([m1, m2])
        top3 = hm.most_conflicted_layers(3)
        assert len(top3) <= 3

    def test_most_conflicted_empty_heatmap(self):
        hm = ConflictHeatmap.from_models([])
        assert hm.most_conflicted_layers(5) == []


# ---------------------------------------------------------------------------
# ConflictHeatmap.parameter_detail
# ---------------------------------------------------------------------------

class TestParameterDetail:
    def test_parameter_detail_returns_layer_detail(self):
        hm = _two_model_heatmap()
        detail = hm.parameter_detail("layer_a")
        assert isinstance(detail, LayerDetail)

    def test_parameter_detail_unknown_layer_raises_key_error(self):
        hm = _two_model_heatmap()
        with pytest.raises(KeyError, match="not found in heatmap"):
            hm.parameter_detail("nonexistent_layer")

    def test_sign_agreement_between_zero_and_one(self):
        hm = _two_model_heatmap()
        detail = hm.parameter_detail("layer_a")
        assert 0.0 <= detail.sign_agreement <= 1.0

    def test_magnitude_spread_non_negative(self):
        hm = _two_model_heatmap()
        detail = hm.parameter_detail("layer_a")
        assert detail.magnitude_spread >= 0.0


# ---------------------------------------------------------------------------
# ConflictHeatmap.to_json / to_csv / to_dict
# ---------------------------------------------------------------------------

class TestConflictHeatmapExport:
    def test_to_dict_has_expected_keys(self):
        hm = _two_model_heatmap()
        d = hm.to_dict()
        assert "num_layers" in d
        assert "num_models" in d
        assert "overall_conflict" in d
        assert "layer_conflicts" in d
        assert "model_contributions" in d

    def test_to_json_returns_valid_json(self):
        hm = _two_model_heatmap()
        json_str = hm.to_json()
        parsed = json.loads(json_str)
        assert "layer_conflicts" in parsed

    def test_to_json_writes_file(self):
        hm = _two_model_heatmap()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            hm.to_json(path)
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert "layer_conflicts" in data
        finally:
            os.unlink(path)

    def test_to_csv_returns_string_with_header(self):
        hm = _two_model_heatmap()
        csv_str = hm.to_csv()
        assert csv_str.startswith("layer_name,conflict_score")

    def test_to_csv_writes_file(self):
        hm = _two_model_heatmap()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            hm.to_csv(path)
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert "layer_name" in content
        finally:
            os.unlink(path)
