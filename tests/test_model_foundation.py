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

"""Foundation tests for crdt_merge.model — v0.8.0 Intelligence Release.

Coverage target: ≥120 tests across schema, registry, ModelCRDT, base ABC,
and integration scenarios.
"""

from __future__ import annotations

import math
import random
import re
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures -- a simple concrete strategy for testing
# ---------------------------------------------------------------------------

from crdt_merge.model.strategies.base import (
    MergeResult,
    ModelMergeStrategy,
    _approx_equal,
    _from_array,
    _get_np,
    _get_torch,
    _normalize_weights,
    _to_array,
)
from crdt_merge.model.strategies import (
    _REGISTRY,
    _reset_registry,
    get_strategy,
    list_strategies,
    list_strategies_by_category,
    register_strategy,
)
from crdt_merge.model.core import (
    ModelCRDT,
    ModelMergeSchema,
    _is_range_pattern,
    _is_regex_pattern,
    _range_matches,
    _ordered_union,
)
from crdt_merge.model import (
    ModelCRDT as PubModelCRDT,
    ModelMergeSchema as PubModelMergeSchema,
    MergeResult as PubMergeResult,
    ModelMergeStrategy as PubModelMergeStrategy,
    register_strategy as pub_register,
    get_strategy as pub_get,
    list_strategies as pub_list,
    list_strategies_by_category as pub_list_cat,
)

class _LinearMerge(ModelMergeStrategy):
    """Simple weighted linear interpolation for testing."""

    @property
    def name(self) -> str:
        return "test_linear"

    @property
    def category(self) -> str:
        return "interpolation"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": False, "idempotent": True}

    @property
    def paper_reference(self) -> str:
        return "N/A — simple linear average"

    def merge(self, tensors, weights=None, base=None, **kwargs):
        n = len(tensors)
        w = _normalize_weights(weights, n)
        arr = [_to_array(t) for t in tensors]

        if isinstance(arr[0], list):
            length = len(arr[0])
            result = [0.0] * length
            for a, wt in zip(arr, w):
                for i in range(length):
                    result[i] += a[i] * wt
            return _from_array(result, tensors[0])

        np = _get_np()
        if np is not None:
            import numpy as np_mod
            out = sum(a * wt for a, wt in zip(arr, w))
            return _from_array(out, tensors[0])

        raise TypeError("Cannot merge: no numpy and inputs are not lists")

class _MaxMerge(ModelMergeStrategy):
    """Element-wise max for testing."""

    @property
    def name(self) -> str:
        return "test_max"

    @property
    def category(self) -> str:
        return "selection"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": True, "idempotent": True}

    def merge(self, tensors, weights=None, base=None, **kwargs):
        arr = [_to_array(t) for t in tensors]
        if isinstance(arr[0], list):
            length = len(arr[0])
            return [max(a[i] for a in arr) for i in range(length)]
        np = _get_np()
        if np is not None:
            import numpy as np_mod
            return _from_array(
                np_mod.maximum.reduce(arr), tensors[0]
            )
        raise TypeError("Cannot merge")

class _TaskArithmetic(ModelMergeStrategy):
    """Task arithmetic: base + sum(w_i * (model_i - base))."""

    @property
    def name(self) -> str:
        return "test_task_arith"

    @property
    def category(self) -> str:
        return "arithmetic"

    @property
    def crdt_properties(self) -> Dict[str, Any]:
        return {"commutative": True, "associative": False, "idempotent": False}

    def merge(self, tensors, weights=None, base=None, **kwargs):
        n = len(tensors)
        w = _normalize_weights(weights, n)
        if base is None:
            base = tensors[0]
        b = _to_array(base)
        arr = [_to_array(t) for t in tensors]
        if isinstance(b, list):
            length = len(b)
            result = list(b)
            for a, wt in zip(arr, w):
                for i in range(length):
                    result[i] += wt * (a[i] - b[i])
            return _from_array(result, tensors[0])
        np = _get_np()
        if np is not None:
            deltas = sum(wt * (a - b) for a, wt in zip(arr, w))
            return _from_array(b + deltas, tensors[0])
        raise TypeError("Cannot merge")

# Fixture to register/unregister test strategies
@pytest.fixture(autouse=True)
def _clean_registry():
    """Save and restore registry around each test."""
    saved = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(saved)

def _register_test_strategies():
    """Register test strategies if not already present."""
    if "test_linear" not in _REGISTRY:
        _REGISTRY["test_linear"] = _LinearMerge
    if "test_max" not in _REGISTRY:
        _REGISTRY["test_max"] = _MaxMerge
    if "test_task_arith" not in _REGISTRY:
        _REGISTRY["test_task_arith"] = _TaskArithmetic

# ============================================================================
# 1. BASE CLASS TESTS (~20)
# ============================================================================

class TestModelMergeStrategyABC:
    """Test the abstract base class enforcement and helpers."""

    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ModelMergeStrategy()

    def test_abc_missing_merge(self):
        class Bad(ModelMergeStrategy):
            name = "x"
            category = "y"
            crdt_properties = {}
        with pytest.raises(TypeError):
            Bad()

    def test_abc_missing_name(self):
        class Bad(ModelMergeStrategy):
            category = "y"
            crdt_properties = {}
            def merge(self, tensors, **kw): pass
        with pytest.raises(TypeError):
            Bad()

    def test_abc_missing_category(self):
        class Bad(ModelMergeStrategy):
            name = "x"
            crdt_properties = {}
            def merge(self, tensors, **kw): pass
        with pytest.raises(TypeError):
            Bad()

    def test_abc_missing_crdt_properties(self):
        class Bad(ModelMergeStrategy):
            name = "x"
            category = "y"
            def merge(self, tensors, **kw): pass
        with pytest.raises(TypeError):
            Bad()

    def test_concrete_subclass_instantiates(self):
        s = _LinearMerge()
        assert s.name == "test_linear"
        assert s.category == "interpolation"
        assert s.paper_reference == "N/A — simple linear average"

    def test_crdt_properties_dict(self):
        s = _LinearMerge()
        props = s.crdt_properties
        assert "commutative" in props
        assert "associative" in props
        assert "idempotent" in props

    def test_default_paper_reference_empty(self):
        s = _MaxMerge()
        assert s.paper_reference == ""

    def test_verify_crdt_returns_dict(self):
        s = _LinearMerge()
        r = s.verify_crdt(trials=10)
        assert "commutative" in r
        assert "associative" in r
        assert "idempotent" in r
        assert "failures" in r

    def test_verify_crdt_with_gen_fn(self):
        s = _LinearMerge()
        def gen():
            return [random.random() for _ in range(5)]
        r = s.verify_crdt(gen_fn=gen, trials=20)
        assert isinstance(r, dict)

    def test_verify_crdt_idempotent_linear(self):
        s = _LinearMerge()
        r = s.verify_crdt(trials=50)
        assert r["idempotent"] is True  # linear avg of [a,a] == a

    def test_verify_crdt_commutative_linear(self):
        s = _LinearMerge()
        r = s.verify_crdt(trials=50)
        assert r["commutative"] is True

    def test_verify_crdt_associative_linear(self):
        # Weighted average is NOT associative when nesting changes effective
        # weights: merge(merge(a,b), c) ≠ merge(a, merge(b,c)) in general.
        s = _LinearMerge()
        r = s.verify_crdt(trials=50)
        assert r["associative"] is False

class TestMergeResult:
    """MergeResult dataclass tests."""

    def test_fields_present(self):
        r = MergeResult(tensor=[1, 2, 3])
        assert r.tensor == [1, 2, 3]
        assert r.provenance is None
        assert r.metadata == {}

    def test_with_provenance(self):
        r = MergeResult(tensor=[1], provenance={"src": "a"}, metadata={"k": "v"})
        assert r.provenance == {"src": "a"}
        assert r.metadata["k"] == "v"

    def test_metadata_default_is_mutable(self):
        r1 = MergeResult(tensor=1)
        r2 = MergeResult(tensor=2)
        r1.metadata["x"] = 1
        assert "x" not in r2.metadata

    def test_tensor_can_be_dict(self):
        r = MergeResult(tensor={"layer": [1, 2]})
        assert isinstance(r.tensor, dict)

class TestHelpers:
    """Tests for _to_array, _from_array, _normalize_weights."""

    def test_to_array_list(self):
        result = _to_array([1.0, 2.0, 3.0])
        # Should be numpy array or list
        np = _get_np()
        if np is not None:
            assert hasattr(result, 'shape') or isinstance(result, list)
        else:
            assert isinstance(result, list)

    def test_to_array_tuple(self):
        result = _to_array((1.0, 2.0))
        np = _get_np()
        if np is not None:
            import numpy
            assert isinstance(result, numpy.ndarray)
        else:
            assert isinstance(result, list)

    def test_to_array_numpy(self):
        np = _get_np()
        if np is None:
            pytest.skip("numpy not available")
        arr = np.array([1.0, 2.0])
        result = _to_array(arr)
        assert isinstance(result, np.ndarray)

    def test_from_array_list(self):
        np = _get_np()
        if np is None:
            result = _from_array([1.0, 2.0], [0.0, 0.0])
            assert isinstance(result, list)
        else:
            result = _from_array(np.array([1.0, 2.0]), [0.0, 0.0])
            assert isinstance(result, list)

    def test_from_array_tuple(self):
        np = _get_np()
        if np is None:
            result = _from_array([1.0, 2.0], (0.0, 0.0))
            assert isinstance(result, tuple)
        else:
            result = _from_array(np.array([1.0, 2.0]), (0.0, 0.0))
            assert isinstance(result, tuple)

    def test_normalize_weights_uniform(self):
        w = _normalize_weights(None, 3)
        assert len(w) == 3
        assert abs(sum(w) - 1.0) < 1e-9

    def test_normalize_weights_custom(self):
        w = _normalize_weights([2.0, 3.0], 2)
        assert abs(w[0] - 0.4) < 1e-9
        assert abs(w[1] - 0.6) < 1e-9

    def test_normalize_weights_already_normalized(self):
        w = _normalize_weights([0.5, 0.5], 2)
        assert abs(w[0] - 0.5) < 1e-9

    def test_normalize_weights_mismatch_raises(self):
        with pytest.raises(ValueError, match="weights length"):
            _normalize_weights([1.0], 3)

    def test_normalize_weights_zero_sum_raises(self):
        with pytest.raises(ValueError, match="must not be zero"):
            _normalize_weights([0.0, 0.0], 2)

    def test_normalize_weights_empty(self):
        w = _normalize_weights(None, 0)
        assert w == []

    def test_approx_equal_lists(self):
        assert _approx_equal([1.0, 2.0], [1.0, 2.0])
        assert not _approx_equal([1.0, 2.0], [1.0, 2.1])

    def test_approx_equal_scalars(self):
        assert _approx_equal(1.0, 1.0)
        assert not _approx_equal(1.0, 2.0)

    def test_approx_equal_different_lengths(self):
        assert not _approx_equal([1.0], [1.0, 2.0])

# ============================================================================
# 2. REGISTRY TESTS (~20)
# ============================================================================

class TestRegistry:
    """Strategy registry tests."""

    def test_register_strategy_decorator(self):
        @register_strategy("reg_test_1")
        class S(_LinearMerge):
            @property
            def name(self): return "reg_test_1"
        assert "reg_test_1" in _REGISTRY
        assert _REGISTRY["reg_test_1"] is S

    def test_get_strategy_returns_instance(self):
        _REGISTRY["test_linear"] = _LinearMerge
        s = get_strategy("test_linear")
        assert isinstance(s, _LinearMerge)

    def test_get_strategy_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            get_strategy("nonexistent_strategy_xyz")

    def test_list_strategies_sorted(self):
        _REGISTRY["bbb"] = _LinearMerge
        _REGISTRY["aaa"] = _MaxMerge
        names = list_strategies()
        assert names.index("aaa") < names.index("bbb")

    def test_list_strategies_empty(self):
        _REGISTRY.clear()
        assert list_strategies() == []

    def test_list_strategies_by_category(self):
        _REGISTRY["test_linear"] = _LinearMerge
        _REGISTRY["test_max"] = _MaxMerge
        cats = list_strategies_by_category()
        assert "interpolation" in cats
        assert "selection" in cats
        assert "test_linear" in cats["interpolation"]
        assert "test_max" in cats["selection"]

    def test_register_duplicate_raises(self):
        _REGISTRY["dup_test"] = _LinearMerge
        with pytest.raises(ValueError, match="already registered"):
            register_strategy("dup_test")(_MaxMerge)

    def test_register_non_strategy_raises(self):
        with pytest.raises(TypeError, match="ModelMergeStrategy subclass"):
            register_strategy("bad_reg")(str)

    def test_register_plain_class_raises(self):
        class NotAStrategy:
            pass
        with pytest.raises(TypeError):
            register_strategy("not_a_strat")(NotAStrategy)

    def test_get_strategy_with_kwargs(self):
        """get_strategy forwards kwargs to constructor."""
        class StratWithInit(_LinearMerge):
            def __init__(self, alpha=0.5, **kw):
                self.alpha = alpha
        _REGISTRY["kwarg_test"] = StratWithInit
        s = get_strategy("kwarg_test", alpha=0.9)
        assert s.alpha == 0.9

    def test_reset_registry(self):
        _REGISTRY["temp"] = _LinearMerge
        _reset_registry()
        assert "temp" not in _REGISTRY

    def test_multiple_registrations(self):
        @register_strategy("multi_a")
        class A(_LinearMerge):
            @property
            def name(self): return "multi_a"

        @register_strategy("multi_b")
        class B(_MaxMerge):
            @property
            def name(self): return "multi_b"

        assert "multi_a" in _REGISTRY
        assert "multi_b" in _REGISTRY

    def test_registered_class_is_preserved(self):
        @register_strategy("preserve_test")
        class P(_LinearMerge):
            custom_attr = 42
            @property
            def name(self): return "preserve_test"
        assert _REGISTRY["preserve_test"].custom_attr == 42

    def test_list_strategies_after_register(self):
        @register_strategy("listed_test")
        class L(_LinearMerge):
            @property
            def name(self): return "listed_test"
        assert "listed_test" in list_strategies()

    def test_get_strategy_error_message_includes_available(self):
        _REGISTRY["avail_1"] = _LinearMerge
        try:
            get_strategy("missing_xyz")
        except KeyError as e:
            assert "avail_1" in str(e)

    def test_category_grouping_single_category(self):
        _REGISTRY.clear()
        _REGISTRY["s1"] = _LinearMerge
        _REGISTRY["s2"] = _LinearMerge
        cats = list_strategies_by_category()
        assert len(cats) == 1
        assert "interpolation" in cats
        assert len(cats["interpolation"]) == 2

    def test_register_returns_class(self):
        @register_strategy("return_check")
        class R(_LinearMerge):
            @property
            def name(self): return "return_check"
        assert R is _REGISTRY["return_check"]

    def test_register_strategy_preserves_inheritance(self):
        @register_strategy("inherit_check")
        class I(_LinearMerge):
            @property
            def name(self): return "inherit_check"
        assert issubclass(I, ModelMergeStrategy)
        assert issubclass(I, _LinearMerge)

# ============================================================================
# 3. SCHEMA TESTS (~30)
# ============================================================================

class TestModelMergeSchema:
    """ModelMergeSchema pattern matching and serialization."""

    def setup_method(self):
        _register_test_strategies()

    # --- Exact matching ---

    def test_exact_match(self):
        s = ModelMergeSchema({"layers.0.weight": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.0.weight")
        assert strat.name == "test_linear"

    def test_exact_match_priority_over_glob(self):
        s = ModelMergeSchema({
            "layers.0.weight": "test_linear",
            "layers.*.weight": "test_max",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.0.weight")
        assert strat.name == "test_linear"

    def test_exact_match_priority_over_range(self):
        s = ModelMergeSchema({
            "layers.5.weight": "test_linear",
            "layers.0-10.weight": "test_max",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.5.weight")
        assert strat.name == "test_linear"

    # --- Glob matching ---

    def test_glob_star(self):
        s = ModelMergeSchema({"layers.*.weight": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.3.weight")
        assert strat.name == "test_linear"

    def test_glob_double_star_not_recursive(self):
        """fnmatch * matches anything except path separators only in OS paths."""
        s = ModelMergeSchema({"layers.*": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.anything")
        assert strat.name == "test_linear"

    def test_glob_question_mark(self):
        s = ModelMergeSchema({"layers.?.weight": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.5.weight")
        assert strat.name == "test_linear"

    def test_glob_no_match_falls_to_default(self):
        s = ModelMergeSchema({"layers.*.weight": "test_linear", "default": "test_max"})
        strat = s.strategy_for("embed.weight")
        assert strat.name == "test_max"

    def test_glob_bracket(self):
        s = ModelMergeSchema({"layers.[0-3].weight": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.2.weight")
        assert strat.name == "test_linear"

    def test_glob_priority_over_range(self):
        s = ModelMergeSchema({
            "layers.*.mlp": "test_linear",
            "layers.0-10.mlp": "test_max",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.5.mlp")
        assert strat.name == "test_linear"

    # --- Range matching ---

    def test_range_basic(self):
        s = ModelMergeSchema({"layers.0-15.self_attn": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.10.self_attn")
        assert strat.name == "test_linear"

    def test_range_boundary_start(self):
        s = ModelMergeSchema({"layers.0-15.self_attn": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.0.self_attn")
        assert strat.name == "test_linear"

    def test_range_boundary_end(self):
        s = ModelMergeSchema({"layers.0-15.self_attn": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.15.self_attn")
        assert strat.name == "test_linear"

    def test_range_out_of_range(self):
        s = ModelMergeSchema({"layers.0-15.self_attn": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.16.self_attn")
        assert strat.name == "test_max"

    def test_range_different_suffix(self):
        s = ModelMergeSchema({"layers.0-15.self_attn": "test_linear", "default": "test_max"})
        strat = s.strategy_for("layers.5.mlp")
        assert strat.name == "test_max"

    # --- Regex matching ---

    def test_regex_basic(self):
        s = ModelMergeSchema({
            r"layers\.\d+\.self_attn$": "test_linear",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.7.self_attn")
        assert strat.name == "test_linear"

    def test_regex_no_match(self):
        s = ModelMergeSchema({
            r"layers\.\d+\.self_attn$": "test_linear",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.7.mlp")
        assert strat.name == "test_max"

    def test_regex_with_groups(self):
        s = ModelMergeSchema({
            r"(embed|lm_head)\.weight": "test_linear",
            "default": "test_max",
        })
        strat = s.strategy_for("embed.weight")
        assert strat.name == "test_linear"

    def test_regex_priority_below_range(self):
        s = ModelMergeSchema({
            "layers.0-10.weight": "test_linear",
            r"layers\.\d+\.weight": "test_max",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.5.weight")
        assert strat.name == "test_linear"

    # --- Default fallback ---

    def test_default_fallback(self):
        s = ModelMergeSchema({"default": "test_linear"})
        strat = s.strategy_for("any.layer.name")
        assert strat.name == "test_linear"

    def test_no_default_raises(self):
        s = ModelMergeSchema({"layers.0.weight": "test_linear"})
        with pytest.raises(KeyError, match="No strategy matches"):
            s.strategy_for("nonexistent.layer")

    # --- Serialization ---

    def test_to_dict_strings(self):
        s = ModelMergeSchema({"default": "test_linear", "layers.0.w": "test_max"})
        d = s.to_dict()
        assert d["default"] == "test_linear"
        assert d["layers.0.w"] == "test_max"

    def test_to_dict_instances(self):
        s = ModelMergeSchema({"default": _LinearMerge()})
        d = s.to_dict()
        assert d["default"] == "test_linear"

    def test_from_dict(self):
        d = {"default": "test_linear", "layers.0.w": "test_max"}
        s = ModelMergeSchema.from_dict(d)
        strat = s.strategy_for("layers.0.w")
        assert strat.name == "test_max"

    def test_roundtrip_serialization(self):
        orig = {"default": "test_linear", "layers.0.w": "test_max"}
        s = ModelMergeSchema.from_dict(orig)
        d = s.to_dict()
        assert d == orig

    def test_repr(self):
        s = ModelMergeSchema({"default": "test_linear"})
        r = repr(s)
        assert "ModelMergeSchema" in r
        assert "test_linear" in r

    # --- Strategy instances in schema ---

    def test_strategy_instance_in_schema(self):
        inst = _LinearMerge()
        s = ModelMergeSchema({"default": inst})
        strat = s.strategy_for("any.layer")
        assert strat is inst

    def test_mixed_instances_and_strings(self):
        inst = _MaxMerge()
        s = ModelMergeSchema({"layers.0.w": inst, "default": "test_linear"})
        assert s.strategy_for("layers.0.w").name == "test_max"
        assert s.strategy_for("other").name == "test_linear"

    # --- Edge cases ---

    def test_empty_schema_no_default_raises(self):
        s = ModelMergeSchema({})
        with pytest.raises(KeyError):
            s.strategy_for("anything")

    def test_multiple_globs_first_wins(self):
        s = ModelMergeSchema({
            "layers.*.weight": "test_linear",
            "*.weight": "test_max",
            "default": "test_max",
        })
        strat = s.strategy_for("layers.0.weight")
        assert strat.name == "test_linear"

# ============================================================================
# 4. MODEL CRDT TESTS (~40)
# ============================================================================

class TestModelCRDT:
    """ModelCRDT merge, provenance, and verification tests."""

    def setup_method(self):
        _register_test_strategies()

    def _make_model(self, n_layers=3, val=1.0, layer_len=5):
        """Helper to create a simple model state dict."""
        return {
            f"layers.{i}.weight": [val + i * 0.1 + j * 0.01 for j in range(layer_len)]
            for i in range(n_layers)
        }

    # --- Basic merge ---

    def test_merge_uniform_weights(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"layer.w": [1.0, 2.0]}
        m2 = {"layer.w": [3.0, 4.0]}
        result = crdt.merge([m1, m2])
        assert isinstance(result, MergeResult)
        merged = result.tensor["layer.w"]
        assert abs(merged[0] - 2.0) < 1e-9
        assert abs(merged[1] - 3.0) < 1e-9

    def test_merge_custom_weights(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"layer.w": [0.0, 0.0]}
        m2 = {"layer.w": [10.0, 10.0]}
        result = crdt.merge([m1, m2], weights=[0.2, 0.8])
        merged = result.tensor["layer.w"]
        assert abs(merged[0] - 8.0) < 1e-9

    def test_merge_three_models(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"w": [3.0]}
        m2 = {"w": [6.0]}
        m3 = {"w": [9.0]}
        result = crdt.merge([m1, m2, m3])
        assert abs(result.tensor["w"][0] - 6.0) < 1e-9

    def test_merge_with_base_model(self):
        schema = ModelMergeSchema({"default": "test_task_arith"})
        crdt = ModelCRDT(schema)
        base = {"w": [0.0, 0.0]}
        m1 = {"w": [1.0, 2.0]}
        m2 = {"w": [3.0, 4.0]}
        result = crdt.merge([m1, m2], base_model=base)
        # task arith: base + 0.5*(m1-base) + 0.5*(m2-base) = 0 + 0.5*1 + 0.5*3 = 2.0
        merged = result.tensor["w"]
        assert abs(merged[0] - 2.0) < 1e-9

    def test_merge_empty_models_list(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge([])
        assert result.tensor == {}
        assert result.metadata["layers"] == 0

    def test_merge_single_model_passthrough(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m = {"w": [1.0, 2.0, 3.0]}
        result = crdt.merge([m])
        assert result.tensor["w"] == [1.0, 2.0, 3.0]
        assert result.metadata.get("single_passthrough") is True

    def test_merge_returns_merge_result(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge([{"w": [1.0]}, {"w": [2.0]}])
        assert isinstance(result, MergeResult)
        assert "layers" in result.metadata

    def test_merge_metadata_strategies_used(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge([{"w": [1.0]}, {"w": [2.0]}])
        assert "strategies_used" in result.metadata
        assert result.metadata["strategies_used"]["w"] == "test_linear"

    # --- Per-layer strategies ---

    def test_per_layer_strategy(self):
        schema = ModelMergeSchema({
            "layers.0.weight": "test_linear",
            "layers.1.weight": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        m1 = {"layers.0.weight": [1.0, 2.0], "layers.1.weight": [1.0, 2.0]}
        m2 = {"layers.0.weight": [3.0, 4.0], "layers.1.weight": [3.0, 4.0]}
        result = crdt.merge([m1, m2])
        # layer 0: linear avg → [2, 3]
        assert abs(result.tensor["layers.0.weight"][0] - 2.0) < 1e-9
        # layer 1: max → [3, 4]
        assert abs(result.tensor["layers.1.weight"][0] - 3.0) < 1e-9

    def test_per_layer_glob_strategy(self):
        schema = ModelMergeSchema({
            "layers.*.mlp": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        m1 = {"layers.0.mlp": [1.0], "layers.0.attn": [1.0]}
        m2 = {"layers.0.mlp": [5.0], "layers.0.attn": [5.0]}
        result = crdt.merge([m1, m2])
        assert abs(result.tensor["layers.0.mlp"][0] - 5.0) < 1e-9  # max
        assert abs(result.tensor["layers.0.attn"][0] - 3.0) < 1e-9  # linear

    def test_per_layer_range_strategy(self):
        schema = ModelMergeSchema({
            "layers.0-1.weight": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        m1 = {"layers.0.weight": [1.0], "layers.1.weight": [1.0], "layers.2.weight": [1.0]}
        m2 = {"layers.0.weight": [5.0], "layers.1.weight": [5.0], "layers.2.weight": [5.0]}
        result = crdt.merge([m1, m2])
        assert abs(result.tensor["layers.0.weight"][0] - 5.0) < 1e-9
        assert abs(result.tensor["layers.1.weight"][0] - 5.0) < 1e-9
        assert abs(result.tensor["layers.2.weight"][0] - 3.0) < 1e-9

    # --- Union behavior ---

    def test_mismatched_layers_union(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"w1": [1.0], "w2": [2.0]}
        m2 = {"w2": [4.0], "w3": [6.0]}
        result = crdt.merge([m1, m2])
        assert "w1" in result.tensor  # only in m1
        assert "w2" in result.tensor  # in both
        assert "w3" in result.tensor  # only in m2

    def test_union_single_model_layer_passthrough(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"unique": [42.0]}
        m2 = {"common": [1.0]}
        result = crdt.merge([m1, m2])
        assert result.tensor["unique"] == [42.0]

    # --- Provenance ---

    def test_merge_with_provenance(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"w": [1.0, 2.0]}
        m2 = {"w": [3.0, 4.0]}
        result = crdt.merge_with_provenance([m1, m2])
        assert result.provenance is not None
        assert "w" in result.provenance
        assert result.provenance["w"]["strategy"] == "test_linear"
        assert result.provenance["w"]["num_sources"] == 2

    def test_provenance_weights(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"w": [1.0]}
        m2 = {"w": [2.0]}
        result = crdt.merge_with_provenance([m1, m2], weights=[0.3, 0.7])
        assert abs(result.provenance["w"]["weights"][0] - 0.3) < 1e-9
        assert abs(result.provenance["w"]["weights"][1] - 0.7) < 1e-9

    def test_provenance_empty_models(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge_with_provenance([])
        assert result.provenance == {}

    def test_provenance_single_model(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge_with_provenance([{"w": [1.0]}])
        # single model has special provenance
        assert result.provenance is not None

    def test_provenance_multiple_layers(self):
        schema = ModelMergeSchema({
            "a": "test_linear",
            "b": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        m1 = {"a": [1.0], "b": [1.0]}
        m2 = {"a": [3.0], "b": [3.0]}
        result = crdt.merge_with_provenance([m1, m2])
        assert result.provenance["a"]["strategy"] == "test_linear"
        assert result.provenance["b"]["strategy"] == "test_max"

    # --- Verify ---

    def test_verify_all_strategies(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        results = crdt.verify()
        assert "test_linear" in results
        assert results["test_linear"]["commutative"] is True

    def test_verify_specific_strategy(self):
        _register_test_strategies()
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        results = crdt.verify(strategy="test_linear")
        assert "test_linear" in results

    def test_verify_multiple_strategies(self):
        schema = ModelMergeSchema({
            "a": "test_linear",
            "b": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        results = crdt.verify(trials=10)
        assert "test_linear" in results
        assert "test_max" in results

    # --- Error handling ---

    def test_unsupported_model_type_raises(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        with pytest.raises(TypeError, match="Unsupported model type"):
            crdt.merge(["not_a_dict"])

    def test_none_base_model_is_fine(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        result = crdt.merge([{"w": [1.0]}, {"w": [2.0]}], base_model=None)
        assert result.tensor is not None

    # --- Load model ---

    def test_load_model_dict(self):
        d = {"w": [1.0]}
        assert ModelCRDT._load_model(d) is d

    def test_load_model_none(self):
        assert ModelCRDT._load_model(None) == {}

    def test_load_model_invalid_type(self):
        with pytest.raises(TypeError):
            ModelCRDT._load_model(42)

    # --- Schema stored on instance ---

    def test_schema_accessible(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        assert crdt.schema is schema

    # --- Weights adjustment for missing layers ---

    def test_weights_adjusted_for_missing_layers(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"shared": [2.0], "only_m1": [10.0]}
        m2 = {"shared": [4.0]}
        result = crdt.merge([m1, m2], weights=[0.3, 0.7])
        # shared: 0.3*2 + 0.7*4 = 3.4 (after normalization of [0.3,0.7])
        assert abs(result.tensor["shared"][0] - 3.4) < 1e-9
        # only_m1: single model passthrough
        assert result.tensor["only_m1"] == [10.0]

    # --- Multi-layer models ---

    def test_many_layers(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {f"layer.{i}": [float(i)] for i in range(20)}
        m2 = {f"layer.{i}": [float(i) + 1] for i in range(20)}
        result = crdt.merge([m1, m2])
        assert len(result.tensor) == 20
        for i in range(20):
            expected = float(i) + 0.5
            assert abs(result.tensor[f"layer.{i}"][0] - expected) < 1e-9

    def test_large_tensors(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        n = 10000
        m1 = {"big": [1.0] * n}
        m2 = {"big": [3.0] * n}
        result = crdt.merge([m1, m2])
        assert len(result.tensor["big"]) == n
        assert abs(result.tensor["big"][0] - 2.0) < 1e-9
        assert abs(result.tensor["big"][-1] - 2.0) < 1e-9

    # --- ModelCRDT with strategy instances ---

    def test_schema_with_instances(self):
        inst = _MaxMerge()
        schema = ModelMergeSchema({"default": inst})
        crdt = ModelCRDT(schema)
        m1 = {"w": [1.0, 5.0]}
        m2 = {"w": [3.0, 2.0]}
        result = crdt.merge([m1, m2])
        assert result.tensor["w"][0] == 3.0
        assert result.tensor["w"][1] == 5.0

    # --- Four models ---

    def test_four_model_merge(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        models = [{"w": [float(i)]} for i in range(4)]
        result = crdt.merge(models)
        # average of 0, 1, 2, 3 = 1.5
        assert abs(result.tensor["w"][0] - 1.5) < 1e-9

    def test_five_models_with_weights(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        models = [{"w": [10.0]}, {"w": [20.0]}, {"w": [30.0]}, {"w": [40.0]}, {"w": [50.0]}]
        result = crdt.merge(models, weights=[1, 1, 1, 1, 1])
        assert abs(result.tensor["w"][0] - 30.0) < 1e-9

# ============================================================================
# 5. PATTERN HELPER TESTS
# ============================================================================

class TestPatternHelpers:
    """Test internal pattern matching helpers."""

    def test_is_range_pattern_true(self):
        assert _is_range_pattern("layers.0-15.self_attn")

    def test_is_range_pattern_false(self):
        assert not _is_range_pattern("layers.*.weight")

    def test_is_range_pattern_just_numbers(self):
        assert _is_range_pattern("0-9")

    def test_is_regex_pattern_dollar(self):
        assert _is_regex_pattern(r"layers\.\d+$")

    def test_is_regex_pattern_pipe(self):
        assert _is_regex_pattern("(a|b)")

    def test_is_regex_pattern_plain(self):
        assert not _is_regex_pattern("layers.0.weight")

    def test_range_matches_in_range(self):
        assert _range_matches("layers.0-15.weight", "layers.7.weight")

    def test_range_matches_out_of_range(self):
        assert not _range_matches("layers.0-15.weight", "layers.16.weight")

    def test_range_matches_different_suffix(self):
        assert not _range_matches("layers.0-15.weight", "layers.5.bias")

    def test_ordered_union(self):
        result = _ordered_union([["a", "b", "c"], ["b", "c", "d"]])
        assert result == ["a", "b", "c", "d"]

    def test_ordered_union_preserves_order(self):
        result = _ordered_union([["z", "a"], ["m", "a", "b"]])
        assert result == ["z", "a", "m", "b"]

    def test_ordered_union_empty(self):
        result = _ordered_union([])
        assert result == []

# ============================================================================
# 6. INTEGRATION TESTS (~10)
# ============================================================================

class TestIntegration:
    """Full flow integration tests."""

    def setup_method(self):
        _register_test_strategies()

    def test_full_flow_schema_merge_verify_provenance(self):
        schema = ModelMergeSchema({
            "layers.0.w": "test_linear",
            "layers.1.w": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)

        m1 = {"layers.0.w": [1.0, 2.0], "layers.1.w": [1.0, 2.0]}
        m2 = {"layers.0.w": [3.0, 4.0], "layers.1.w": [5.0, 6.0]}

        # Merge
        result = crdt.merge([m1, m2])
        assert len(result.tensor) == 2

        # Provenance
        prov_result = crdt.merge_with_provenance([m1, m2])
        assert prov_result.provenance is not None
        assert prov_result.provenance["layers.0.w"]["strategy"] == "test_linear"
        assert prov_result.provenance["layers.1.w"]["strategy"] == "test_max"

        # Verify
        vr = crdt.verify(trials=10)
        assert "test_linear" in vr
        assert "test_max" in vr

    def test_multiple_strategies_single_schema(self):
        schema = ModelMergeSchema({
            "embed": "test_linear",
            "layers.*.attn": "test_max",
            "layers.0-5.mlp": "test_task_arith",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)

        m1 = {
            "embed": [1.0],
            "layers.0.attn": [1.0],
            "layers.0.mlp": [1.0],
            "layers.10.attn": [1.0],
        }
        m2 = {
            "embed": [3.0],
            "layers.0.attn": [5.0],
            "layers.0.mlp": [3.0],
            "layers.10.attn": [5.0],
        }

        result = crdt.merge([m1, m2])
        assert abs(result.tensor["embed"][0] - 2.0) < 1e-9  # linear
        assert abs(result.tensor["layers.0.attn"][0] - 5.0) < 1e-9  # max
        assert abs(result.tensor["layers.10.attn"][0] - 5.0) < 1e-9  # max

    def test_schema_roundtrip_with_merge(self):
        orig = {"default": "test_linear", "head.w": "test_max"}
        schema = ModelMergeSchema.from_dict(orig)
        crdt = ModelCRDT(schema)

        m1 = {"head.w": [1.0], "body.w": [1.0]}
        m2 = {"head.w": [5.0], "body.w": [5.0]}

        result = crdt.merge([m1, m2])
        assert abs(result.tensor["head.w"][0] - 5.0) < 1e-9
        assert abs(result.tensor["body.w"][0] - 3.0) < 1e-9

        # Roundtrip
        d = schema.to_dict()
        assert d == orig

    def test_large_tensor_merge(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        n = 10000
        m1 = {"big": list(range(n))}
        m2 = {"big": list(range(n, 2 * n))}
        result = crdt.merge([m1, m2])
        # avg of (0, 10000) = 5000, avg of (1, 10001) = 5001, etc.
        assert abs(result.tensor["big"][0] - 5000.0) < 1e-9
        assert abs(result.tensor["big"][1] - 5001.0) < 1e-9

    def test_integration_with_numpy_if_available(self):
        np = _get_np()
        if np is None:
            pytest.skip("numpy not available")

        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        m1 = {"w": np.array([1.0, 2.0, 3.0])}
        m2 = {"w": np.array([5.0, 6.0, 7.0])}
        result = crdt.merge([m1, m2])
        merged = result.tensor["w"]
        assert abs(merged[0] - 3.0) < 1e-9
        assert abs(merged[1] - 4.0) < 1e-9

    def test_register_and_use_in_schema(self):
        @register_strategy("integ_custom")
        class CustomStrat(_LinearMerge):
            @property
            def name(self):
                return "integ_custom"

        schema = ModelMergeSchema({"default": "integ_custom"})
        crdt = ModelCRDT(schema)
        result = crdt.merge([{"w": [1.0]}, {"w": [3.0]}])
        assert abs(result.tensor["w"][0] - 2.0) < 1e-9

    def test_verify_with_custom_gen_fn(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        def gen():
            return [random.random() for _ in range(3)]
        results = crdt.verify(gen_fn=gen, trials=20)
        assert results["test_linear"]["commutative"] is True

    def test_provenance_full_flow(self):
        schema = ModelMergeSchema({
            "a": "test_linear",
            "b": "test_max",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        m1 = {"a": [1.0], "b": [1.0], "c": [1.0]}
        m2 = {"a": [3.0], "b": [3.0], "c": [3.0]}
        result = crdt.merge_with_provenance([m1, m2])
        assert result.provenance["a"]["strategy"] == "test_linear"
        assert result.provenance["b"]["strategy"] == "test_max"
        assert result.provenance["c"]["strategy"] == "test_linear"
        assert result.provenance["a"]["num_sources"] == 2

    def test_merge_preserves_layer_order(self):
        schema = ModelMergeSchema({"default": "test_linear"})
        crdt = ModelCRDT(schema)
        layers = [f"layer_{i}" for i in range(10)]
        m1 = {l: [1.0] for l in layers}
        m2 = {l: [3.0] for l in layers}
        result = crdt.merge([m1, m2])
        assert list(result.tensor.keys()) == layers

    def test_three_strategies_full_verify(self):
        schema = ModelMergeSchema({
            "a": "test_linear",
            "b": "test_max",
            "c": "test_task_arith",
            "default": "test_linear",
        })
        crdt = ModelCRDT(schema)
        results = crdt.verify(trials=10)
        assert "test_linear" in results
        assert "test_max" in results
        assert "test_task_arith" in results

# ============================================================================
# 7. PUBLIC API SURFACE TESTS
# ============================================================================

class TestPublicAPI:
    """Ensure public API re-exports work correctly."""

    def test_model_crdt_reexport(self):
        assert PubModelCRDT is ModelCRDT

    def test_model_merge_schema_reexport(self):
        assert PubModelMergeSchema is ModelMergeSchema

    def test_merge_result_reexport(self):
        assert PubMergeResult is MergeResult

    def test_model_merge_strategy_reexport(self):
        assert PubModelMergeStrategy is ModelMergeStrategy

    def test_register_strategy_reexport(self):
        assert pub_register is register_strategy

    def test_get_strategy_reexport(self):
        assert pub_get is get_strategy

    def test_list_strategies_reexport(self):
        assert pub_list is list_strategies

    def test_list_strategies_by_category_reexport(self):
        assert pub_list_cat is list_strategies_by_category

    def test_all_in_model_init(self):
        import crdt_merge.model as mod
        for name in [
            "ModelCRDT", "ModelMergeSchema", "MergeResult",
            "ModelMergeStrategy", "register_strategy", "get_strategy",
            "list_strategies", "list_strategies_by_category",
        ]:
            assert name in mod.__all__
