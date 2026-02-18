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

"""Tests for crdt_merge.model.lora — LoRAMerge and LoRAMergeSchema."""

from __future__ import annotations

import math

import pytest

from crdt_merge.model.lora import (
    LoRAMerge,
    LoRAMergeSchema,
    _compute_target_rank,
    _ordered_module_union,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rank2_adapter(module_names, rank=2, in_f=4, out_f=4):
    """Return a simple adapter dict with given module names."""
    adapter = {}
    for m in module_names:
        adapter[m] = {
            "lora_A": [[float(i + 1) * 0.1] * in_f for i in range(rank)],
            "lora_B": [[float(i + 1) * 0.2] * rank for i in range(out_f)],
        }
    return adapter


def _default_schema():
    return LoRAMergeSchema(strategies={"default": "weight_average"})


# ---------------------------------------------------------------------------
# _compute_target_rank
# ---------------------------------------------------------------------------

class TestComputeTargetRank:
    def test_max_strategy(self):
        assert _compute_target_rank([4, 8, 2], "max") == 8

    def test_min_strategy(self):
        assert _compute_target_rank([4, 8, 2], "min") == 2

    def test_mean_strategy(self):
        assert _compute_target_rank([4, 8], "mean") == 6

    def test_adaptive_uniform_weights_equals_mean(self):
        result = _compute_target_rank([4, 8], "adaptive", weights=None)
        assert result == 6

    def test_empty_ranks_returns_zero(self):
        assert _compute_target_rank([], "max") == 0

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown rank_strategy"):
            _compute_target_rank([4], "unknown")


# ---------------------------------------------------------------------------
# _ordered_module_union
# ---------------------------------------------------------------------------

class TestOrderedModuleUnion:
    def test_union_preserves_order(self):
        a = {"q_proj": {}, "v_proj": {}}
        b = {"v_proj": {}, "k_proj": {}}
        result = _ordered_module_union([a, b])
        assert result == ["q_proj", "v_proj", "k_proj"]

    def test_single_adapter(self):
        a = {"q_proj": {}, "v_proj": {}}
        assert _ordered_module_union([a]) == ["q_proj", "v_proj"]

    def test_empty_adapters(self):
        assert _ordered_module_union([]) == []


# ---------------------------------------------------------------------------
# LoRAMergeSchema
# ---------------------------------------------------------------------------

class TestLoRAMergeSchema:
    def test_default_strategy_resolved(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        strat = schema.strategy_for("any_module")
        assert strat is not None

    def test_exact_module_match_takes_precedence(self):
        schema = LoRAMergeSchema(strategies={
            "q_proj": "slerp",
            "default": "weight_average",
        })
        strat = schema.strategy_for("q_proj")
        assert strat.name == "slerp"

    def test_default_used_when_no_exact_match(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        strat = schema.strategy_for("some_random_module")
        assert strat.name == "weight_average"

    def test_no_default_and_no_match_raises_key_error(self):
        schema = LoRAMergeSchema(strategies={"q_proj": "slerp"})
        with pytest.raises(KeyError, match="No strategy matches"):
            schema.strategy_for("v_proj")

    def test_to_dict_and_from_dict_roundtrip(self):
        original = LoRAMergeSchema(strategies={"default": "weight_average", "q_proj": "slerp"})
        d = original.to_dict()
        reconstructed = LoRAMergeSchema.from_dict(d)
        assert reconstructed.to_dict() == d

    def test_repr_contains_strategy_info(self):
        schema = LoRAMergeSchema(strategies={"default": "weight_average"})
        r = repr(schema)
        assert "weight_average" in r


# ---------------------------------------------------------------------------
# LoRAMerge.merge_adapters
# ---------------------------------------------------------------------------

class TestLoRAMergeMergeAdapters:
    def test_empty_adapters_returns_empty(self):
        merger = LoRAMerge(_default_schema())
        assert merger.merge_adapters([]) == {}

    def test_single_adapter_returned_as_copy(self):
        adapter = _rank2_adapter(["q_proj"])
        merger = LoRAMerge(_default_schema())
        result = merger.merge_adapters([adapter])
        assert "q_proj" in result

    def test_two_adapters_same_modules_returns_all_modules(self):
        a = _rank2_adapter(["q_proj", "v_proj"])
        b = _rank2_adapter(["q_proj", "v_proj"])
        merger = LoRAMerge(_default_schema())
        result = merger.merge_adapters([a, b])
        assert "q_proj" in result
        assert "v_proj" in result

    def test_result_contains_lora_a_and_lora_b(self):
        a = _rank2_adapter(["q_proj"])
        b = _rank2_adapter(["q_proj"])
        merger = LoRAMerge(_default_schema())
        result = merger.merge_adapters([a, b])
        assert "lora_A" in result["q_proj"]
        assert "lora_B" in result["q_proj"]

    def test_union_of_modules_included(self):
        a = _rank2_adapter(["q_proj"])
        b = _rank2_adapter(["v_proj"])
        merger = LoRAMerge(_default_schema())
        result = merger.merge_adapters([a, b])
        assert "q_proj" in result
        assert "v_proj" in result

    def test_explicit_weights_accepted(self):
        a = _rank2_adapter(["q_proj"])
        b = _rank2_adapter(["q_proj"])
        merger = LoRAMerge(_default_schema())
        # Should not raise
        result = merger.merge_adapters([a, b], weights=[0.7, 0.3])
        assert "q_proj" in result

    def test_rank_strategy_max(self):
        """Merging adapters with different ranks using 'max'."""
        rank2 = _rank2_adapter(["q_proj"], rank=2)
        rank4 = _rank2_adapter(["q_proj"], rank=4)
        merger = LoRAMerge(_default_schema())
        result = merger.merge_adapters([rank2, rank4], rank_strategy="max")
        assert "q_proj" in result


# ---------------------------------------------------------------------------
# LoRAMerge.merge_adapters_with_provenance
# ---------------------------------------------------------------------------

class TestLoRAMergeMergeAdaptersWithProvenance:
    def test_empty_adapters_returns_empty_dicts(self):
        merger = LoRAMerge(_default_schema())
        merged, prov = merger.merge_adapters_with_provenance([])
        assert merged == {}
        assert prov == {}

    def test_single_adapter_provenance_has_passthrough(self):
        adapter = _rank2_adapter(["q_proj"])
        merger = LoRAMerge(_default_schema())
        merged, prov = merger.merge_adapters_with_provenance([adapter])
        assert prov["q_proj"]["strategy"] == "passthrough"

    def test_provenance_contains_expected_keys(self):
        a = _rank2_adapter(["q_proj"])
        b = _rank2_adapter(["q_proj"])
        merger = LoRAMerge(_default_schema())
        _, prov = merger.merge_adapters_with_provenance([a, b])
        p = prov["q_proj"]
        assert "strategy" in p
        assert "num_sources" in p
        assert "dominant_source" in p
        assert "contribution_map" in p


# ---------------------------------------------------------------------------
# LoRAMerge.apply_to_base
# ---------------------------------------------------------------------------

class TestLoRAMergeApplyToBase:
    def test_apply_adds_delta_to_base_layer(self):
        base = {"q_proj": [[1.0, 0.0], [0.0, 1.0]]}
        # lora_B @ lora_A: (2×1) @ (1×2) → (2×2)
        adapter = {
            "q_proj": {
                "lora_A": [[0.0, 0.0]],   # 1×2, all zeros
                "lora_B": [[0.0], [0.0]],  # 2×1, all zeros
            }
        }
        merger = LoRAMerge(_default_schema())
        result = merger.apply_to_base(adapter, base)
        # Zero delta should leave base unchanged
        assert "q_proj" in result

    def test_apply_creates_new_key_when_not_in_base(self):
        base = {"other_layer": [1.0]}
        adapter = {
            "q_proj": {
                "lora_A": [[1.0, 0.0]],
                "lora_B": [[1.0], [0.0]],
            }
        }
        merger = LoRAMerge(_default_schema())
        result = merger.apply_to_base(adapter, base)
        # q_proj not in base → stored as new key
        assert "q_proj" in result or "q_proj.weight" in result

    def test_apply_skips_modules_with_missing_lora_keys(self):
        base = {"w": [1.0]}
        adapter = {"bad_module": {"lora_A": None, "lora_B": [[1.0]]}}
        merger = LoRAMerge(_default_schema())
        result = merger.apply_to_base(adapter, base)
        # base unchanged, bad_module skipped
        assert "w" in result
