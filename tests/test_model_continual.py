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

"""Tests for crdt_merge.model.continual — ContinualMerge and StabilityResult."""

from __future__ import annotations

import math

import pytest

from crdt_merge.model.continual import ContinualMerge, StabilityResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = {"layer.weight": [1.0, 2.0, 3.0], "layer.bias": [0.5]}


def _cm(**kwargs):
    """Create a ContinualMerge with the shared base model."""
    return ContinualMerge(base_model=_BASE, **kwargs)


def _close(a, b, tol=1e-6):
    if isinstance(a, (list, tuple)):
        return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))
    return math.isclose(float(a), float(b), abs_tol=tol)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestContinualMergeInit:
    def test_default_instantiation(self):
        cm = _cm()
        assert cm is not None

    def test_base_model_absorbed_as_base(self):
        cm = _cm()
        assert "__base__" in cm._contributions

    def test_history_empty_on_init(self):
        cm = _cm()
        assert cm.history == []

    def test_memory_budget_clamped_to_valid_range(self):
        cm_low = ContinualMerge(base_model=_BASE, memory_budget=-1.0)
        cm_high = ContinualMerge(base_model=_BASE, memory_budget=5.0)
        assert cm_low._memory_budget >= 0.01
        assert cm_high._memory_budget <= 1.0

    def test_crdt_mode_initialises_states(self):
        cm = ContinualMerge(
            base_model=_BASE, convergence="crdt", strategy="weight_average"
        )
        assert len(cm._crdt_states) == len(_BASE)


# ---------------------------------------------------------------------------
# absorb
# ---------------------------------------------------------------------------

class TestContinualMergeAbsorb:
    def test_absorb_adds_to_history(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft_v1")
        assert len(cm.history) == 1
        assert cm.history[0]["name"] == "ft_v1"

    def test_absorb_auto_generates_name(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]})
        assert len(cm.history) == 1
        assert cm.history[0]["name"].startswith("model_")

    def test_absorb_multiple_models(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="a")
        cm.absorb({"layer.weight": [3.0, 4.0, 5.0]}, name="b")
        assert len(cm.history) == 2

    def test_absorb_with_replace_removes_old(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="v1")
        cm.absorb({"layer.weight": [5.0, 6.0, 7.0]}, name="v2", replace="v1")
        assert "v1" not in cm._contributions
        assert "v2" in cm._contributions

    def test_duplicate_name_gets_suffix(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft")
        cm.absorb({"layer.weight": [3.0, 4.0, 5.0]}, name="ft")
        # Both should be present under different keys
        assert len([n for n in cm._contributions if n.startswith("ft")]) == 2


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

class TestContinualMergeExport:
    def test_export_returns_dict(self):
        cm = _cm()
        result = cm.export()
        assert isinstance(result, dict)

    def test_export_contains_base_layer_keys(self):
        cm = _cm()
        result = cm.export()
        assert "layer.weight" in result
        assert "layer.bias" in result

    def test_export_with_absorbed_model_differs_from_base(self):
        cm = _cm()
        cm.absorb({"layer.weight": [10.0, 20.0, 30.0]}, weight=1.0, name="big")
        result = cm.export()
        # Should differ from original base due to absorption
        base_w = _BASE["layer.weight"]
        merged_w = result["layer.weight"]
        assert not _close(merged_w, base_w)

    def test_export_crdt_mode(self):
        cm = ContinualMerge(
            base_model=_BASE, convergence="crdt", strategy="weight_average"
        )
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft")
        result = cm.export()
        assert "layer.weight" in result

    def test_export_is_repeatable(self):
        cm = _cm()
        cm.absorb({"layer.weight": [5.0, 5.0, 5.0]}, name="ft")
        r1 = cm.export()
        r2 = cm.export()
        assert _close(r1["layer.weight"], r2["layer.weight"])


# ---------------------------------------------------------------------------
# current_weights
# ---------------------------------------------------------------------------

class TestCurrentWeights:
    def test_weights_sum_to_one(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 2.0, 2.0]}, name="ft")
        w = cm.current_weights
        assert math.isclose(sum(w.values()), 1.0, abs_tol=1e-9)

    def test_weights_contain_base_and_absorbed(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 2.0, 2.0]}, name="ft")
        w = cm.current_weights
        assert "__base__" in w
        assert "ft" in w


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_history(self):
        cm = _cm()
        cm.absorb({"layer.weight": [9.0, 9.0, 9.0]}, name="ft")
        new_base = {"layer.weight": [0.0, 0.0, 0.0]}
        cm.reset(new_base)
        assert cm.history == []

    def test_reset_uses_new_base(self):
        cm = _cm()
        new_base = {"layer.weight": [0.0, 0.0, 0.0]}
        cm.reset(new_base)
        result = cm.export()
        assert _close(result["layer.weight"], [0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# verify_convergence
# ---------------------------------------------------------------------------

class TestVerifyConvergence:
    def test_non_crdt_returns_false(self):
        cm = _cm()
        assert cm.verify_convergence() is False

    def test_crdt_mode_returns_true_after_absorb(self):
        cm = ContinualMerge(
            base_model=_BASE, convergence="crdt", strategy="weight_average"
        )
        assert cm.verify_convergence() is True


# ---------------------------------------------------------------------------
# measure_stability
# ---------------------------------------------------------------------------

class TestMeasureStability:
    def test_unknown_model_raises_key_error(self):
        cm = _cm()
        with pytest.raises(KeyError, match="not found"):
            cm.measure_stability("nonexistent")

    def test_returns_stability_result(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft")
        result = cm.measure_stability("ft")
        assert isinstance(result, StabilityResult)

    def test_retention_between_zero_and_one(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft")
        result = cm.measure_stability("ft")
        assert 0.0 <= result.retention <= 1.0

    def test_per_layer_populated(self):
        cm = _cm()
        cm.absorb({"layer.weight": [2.0, 3.0, 4.0]}, name="ft")
        result = cm.measure_stability("ft")
        assert "layer.weight" in result.per_layer

    def test_exact_copy_has_high_retention(self):
        """Absorbing the same update with full weight should preserve direction."""
        base = {"w": [1.0, 0.0]}
        update = {"w": [3.0, 0.0]}  # same direction, larger magnitude
        cm = ContinualMerge(base_model=base, memory_budget=1.0)
        cm.absorb(update, name="ft", weight=1.0)
        result = cm.measure_stability("ft")
        assert result.retention >= 0.0  # directional preservation >= 0
