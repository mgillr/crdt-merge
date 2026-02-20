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

"""Tests for crdt_merge.model.safety — SafetyAnalyzer and SafetyReport."""

from __future__ import annotations

import math

import pytest

from crdt_merge.model.safety import SafetyAnalyzer, SafetyReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _analyzer():
    return SafetyAnalyzer()


# ---------------------------------------------------------------------------
# SafetyAnalyzer initialization
# ---------------------------------------------------------------------------

class TestSafetyAnalyzerInit:
    def test_instantiation(self):
        analyzer = SafetyAnalyzer()
        assert analyzer is not None


# ---------------------------------------------------------------------------
# SafetyAnalyzer._compute_layer_variances
# ---------------------------------------------------------------------------

class TestComputeLayerVariances:
    def test_identical_models_have_zero_variance(self):
        model = {"w": [1.0, 2.0, 3.0]}
        analyzer = _analyzer()
        variances = analyzer._compute_layer_variances([model, model])
        assert math.isclose(variances["w"], 0.0, abs_tol=1e-9)

    def test_variance_is_positive_for_different_models(self):
        m1 = {"w": [0.0]}
        m2 = {"w": [2.0]}
        analyzer = _analyzer()
        variances = analyzer._compute_layer_variances([m1, m2])
        assert variances["w"] > 0.0

    def test_single_model_has_zero_variance(self):
        model = {"w": [1.0, 2.0]}
        analyzer = _analyzer()
        variances = analyzer._compute_layer_variances([model])
        assert math.isclose(variances["w"], 0.0, abs_tol=1e-9)

    def test_all_layer_names_included(self):
        m1 = {"a": [1.0], "b": [2.0]}
        m2 = {"a": [3.0], "c": [4.0]}
        analyzer = _analyzer()
        variances = analyzer._compute_layer_variances([m1, m2])
        assert "a" in variances
        assert "b" in variances
        assert "c" in variances

    def test_missing_layer_in_one_model_has_zero_variance(self):
        m1 = {"a": [1.0], "b": [2.0]}
        m2 = {"a": [1.0]}
        analyzer = _analyzer()
        variances = analyzer._compute_layer_variances([m1, m2])
        # "b" only in m1 → single sample → 0.0
        assert math.isclose(variances["b"], 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# SafetyAnalyzer.detect_safety_layers
# ---------------------------------------------------------------------------

class TestDetectSafetyLayers:
    def test_no_safety_layers_when_identical(self):
        model = {"w": [1.0, 2.0]}
        analyzer = _analyzer()
        layers = analyzer.detect_safety_layers([model, model])
        assert layers == []

    def test_high_variance_layer_detected(self):
        m1 = {"w": [0.0]}
        m2 = {"w": [100.0]}
        analyzer = _analyzer()
        layers = analyzer.detect_safety_layers([m1, m2], threshold=0.1)
        assert "w" in layers

    def test_threshold_respected(self):
        m1 = {"safe": [1.0], "risky": [0.0]}
        m2 = {"safe": [1.01], "risky": [5.0]}
        analyzer = _analyzer()
        layers = analyzer.detect_safety_layers([m1, m2], threshold=0.5)
        # "risky" should be flagged, "safe" should not
        assert "risky" in layers
        assert "safe" not in layers

    def test_custom_low_threshold_flags_more_layers(self):
        m1 = {"w": [0.0]}
        m2 = {"w": [0.5]}
        analyzer = _analyzer()
        layers_high = analyzer.detect_safety_layers([m1, m2], threshold=1.0)
        layers_low = analyzer.detect_safety_layers([m1, m2], threshold=0.01)
        assert len(layers_low) >= len(layers_high)


# ---------------------------------------------------------------------------
# SafetyAnalyzer.safety_report
# ---------------------------------------------------------------------------

class TestSafetyReport:
    def test_returns_safety_report_instance(self):
        model = {"w": [1.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([model, model])
        assert isinstance(report, SafetyReport)

    def test_risk_score_between_zero_and_one(self):
        m1 = {"w": [0.0]}
        m2 = {"w": [10.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2])
        assert 0.0 <= report.risk_score <= 1.0

    def test_identical_models_have_zero_risk(self):
        model = {"w": [1.0, 2.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([model, model])
        assert math.isclose(report.risk_score, 0.0, abs_tol=1e-9)

    def test_very_different_models_have_high_risk(self):
        m1 = {"w": [0.0, 0.0, 0.0]}
        m2 = {"w": [100.0, 100.0, 100.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2])
        assert report.risk_score > 0.0

    def test_layer_variance_dict_populated(self):
        m1 = {"layer_a": [1.0], "layer_b": [0.0]}
        m2 = {"layer_a": [3.0], "layer_b": [0.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2])
        assert "layer_a" in report.layer_variance
        assert "layer_b" in report.layer_variance

    def test_recommendation_is_non_empty_string(self):
        model = {"w": [1.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([model, model])
        assert isinstance(report.recommendation, str)
        assert len(report.recommendation) > 0

    def test_safety_layers_listed_in_report(self):
        m1 = {"safe": [1.0], "risky": [0.0]}
        m2 = {"safe": [1.001], "risky": [50.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2])
        assert "risky" in report.safety_layers

    def test_empty_models_list_has_zero_risk(self):
        analyzer = _analyzer()
        report = analyzer.safety_report([])
        assert math.isclose(report.risk_score, 0.0, abs_tol=1e-9)

    def test_with_base_model_accepted(self):
        base = {"w": [0.0]}
        m1 = {"w": [1.0]}
        m2 = {"w": [2.0]}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2], base_model=base)
        assert isinstance(report, SafetyReport)

    def test_risk_score_capped_at_one(self):
        # Extremely different models
        m1 = {"a": [0.0] * 100}
        m2 = {"a": [1000.0] * 100}
        analyzer = _analyzer()
        report = analyzer.safety_report([m1, m2])
        assert report.risk_score <= 1.0
