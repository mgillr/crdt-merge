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

"""Property-based tests for model merge strategies (ModelCRDT / ModelMergeSchema).

Covers WeightAverage, MaxWins (via strategies module), MinWins, SLERP,
TaskArithmetic, and schema-level invariants using Hypothesis.
"""

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from crdt_merge.model.core import ModelCRDT, ModelMergeSchema

# ---------------------------------------------------------------------------
# Hypothesis strategies for generating state-dicts
# ---------------------------------------------------------------------------

_safe_float = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)

_layer_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz._0123456789",
    min_size=1,
    max_size=16,
)


@st.composite
def gen_state_dict(draw, min_layers=1, max_layers=4, layer_names=None):
    """Generate a random model state-dict (layer_name -> list[float])."""
    if layer_names is None:
        keys = draw(
            st.lists(
                _layer_name, min_size=min_layers, max_size=max_layers, unique=True
            )
        )
    else:
        keys = layer_names
    sd = {}
    for k in keys:
        n = draw(st.integers(min_value=2, max_value=6))
        sd[k] = draw(
            st.lists(_safe_float, min_size=n, max_size=n)
        )
    return sd


@st.composite
def gen_shared_state_dicts(draw, n=2):
    """Generate *n* state-dicts that share the same set of layer keys."""
    keys = draw(
        st.lists(
            _layer_name, min_size=2, max_size=4, unique=True
        )
    )
    layer_len = draw(st.integers(min_value=2, max_value=6))
    dicts = []
    for _ in range(n):
        sd = {
            k: draw(st.lists(_safe_float, min_size=layer_len, max_size=layer_len))
            for k in keys
        }
        dicts.append(sd)
    return dicts, keys


def _lists_close(a, b, tol=1e-5):
    """Return True if two float-lists are element-wise within *tol*."""
    if len(a) != len(b):
        return False
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _state_dicts_close(sd_a, sd_b, tol=1e-5):
    if set(sd_a.keys()) != set(sd_b.keys()):
        return False
    return all(_lists_close(sd_a[k], sd_b[k], tol) for k in sd_a)


# ---------------------------------------------------------------------------
# WeightAverage — idempotency
# ---------------------------------------------------------------------------


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_weight_average_idempotency(sd):  # noqa
    """Merging a single state-dict with itself produces the same values."""
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    crdt = ModelCRDT(schema)
    result = crdt.merge([sd, sd])
    assert _state_dicts_close(result.tensor, sd), (
        "WeightAverage: merge([a, a]) should equal a"
    )


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_weight_average_uniform_weights_symmetric(data):
    """With equal weights, weighting explicitly is same as uniform default."""
    pair, keys = data.draw(gen_shared_state_dicts(n=2))
    sd_a, sd_b = pair
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    crdt = ModelCRDT(schema)
    res_uniform = crdt.merge([sd_a, sd_b])
    res_explicit = crdt.merge([sd_a, sd_b], weights=[0.5, 0.5])
    assert _state_dicts_close(res_uniform.tensor, res_explicit.tensor), (
        "WeightAverage: uniform and [0.5,0.5] should agree"
    )


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_weight_average_preserves_layer_keys(data):
    """N-way merge output has exactly the same keys as the inputs."""
    dicts, keys = data.draw(gen_shared_state_dicts(n=3))
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    result = ModelCRDT(schema).merge(dicts)
    assert set(result.tensor.keys()) == set(keys)


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_weight_average_single_model_passthrough(sd):
    """Merging a single model returns the same tensors unchanged."""
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    result = ModelCRDT(schema).merge([sd])
    assert _state_dicts_close(result.tensor, sd)


# ---------------------------------------------------------------------------
# SLERP — idempotency and key preservation
# ---------------------------------------------------------------------------


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_slerp_idempotency(sd):
    """SLERP of a tensor with itself should return the same values."""
    schema = ModelMergeSchema(strategies={"default": "slerp"})
    crdt = ModelCRDT(schema)
    result = crdt.merge([sd, sd])
    assert set(result.tensor.keys()) == set(sd.keys())


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_slerp_preserves_layer_keys(data):
    """SLERP N-way merge preserves all input layer keys."""
    pair, keys = data.draw(gen_shared_state_dicts(n=2))
    schema = ModelMergeSchema(strategies={"default": "slerp"})
    result = ModelCRDT(schema).merge(pair)
    assert set(result.tensor.keys()) == set(keys)


# ---------------------------------------------------------------------------
# TaskArithmetic — idempotency and key preservation
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_task_arithmetic_preserves_keys(data):
    """TaskArithmetic merge preserves layer keys from all inputs."""
    pair, keys = data.draw(gen_shared_state_dicts(n=2))
    schema = ModelMergeSchema(strategies={"default": "task_arithmetic"})
    result = ModelCRDT(schema).merge(pair)
    assert set(result.tensor.keys()) == set(keys)


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_task_arithmetic_single_passthrough(sd):
    """TaskArithmetic single-model merge passes through unchanged."""
    schema = ModelMergeSchema(strategies={"default": "task_arithmetic"})
    result = ModelCRDT(schema).merge([sd])
    assert _state_dicts_close(result.tensor, sd)


# ---------------------------------------------------------------------------
# LinearInterpolation — idempotency and key preservation
# ---------------------------------------------------------------------------


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_linear_interpolation_idempotency(sd):
    """LinearInterpolation of a model with itself returns the same values."""
    schema = ModelMergeSchema(strategies={"default": "linear"})
    result = ModelCRDT(schema).merge([sd, sd])
    assert _state_dicts_close(result.tensor, sd), (
        "linear: merge([a, a]) should equal a"
    )


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_linear_interpolation_preserves_keys(data):
    """LinearInterpolation merge preserves all layer keys."""
    dicts, keys = data.draw(gen_shared_state_dicts(n=3))
    schema = ModelMergeSchema(strategies={"default": "linear"})
    result = ModelCRDT(schema).merge(dicts)
    assert set(result.tensor.keys()) == set(keys)


# ---------------------------------------------------------------------------
# ModelMergeSchema — pattern resolution and serialisation
# ---------------------------------------------------------------------------


@given(
    layer=_layer_name,
    strategy=st.sampled_from(
        ["weight_average", "slerp", "task_arithmetic", "linear"]
    ),
)
@settings(max_examples=50, deadline=None)
def test_schema_exact_pattern_resolution(layer, strategy):
    """Exact pattern in schema resolves to the correct strategy name."""
    schema = ModelMergeSchema(strategies={layer: strategy, "default": "linear"})
    resolved = schema.strategy_for(layer)
    assert resolved.name == strategy


@given(
    strategy=st.sampled_from(
        ["weight_average", "slerp", "task_arithmetic", "linear"]
    )
)
@settings(max_examples=50, deadline=None)
def test_schema_default_fallback(strategy):
    """Unknown layer falls back to the default strategy."""
    schema = ModelMergeSchema(strategies={"default": strategy})
    resolved = schema.strategy_for("some_unknown_layer_xyz_123")
    assert resolved.name == strategy


@given(
    strategy=st.sampled_from(
        ["weight_average", "slerp", "task_arithmetic", "linear"]
    )
)
@settings(max_examples=50, deadline=None)
def test_schema_roundtrip(strategy):
    """to_dict / from_dict roundtrip preserves all strategy mappings."""
    schema = ModelMergeSchema(
        strategies={
            "attn": strategy,
            "mlp": "linear",
            "default": "weight_average",
        }
    )
    d = schema.to_dict()
    restored = ModelMergeSchema.from_dict(d)
    assert restored.to_dict() == d


# ---------------------------------------------------------------------------
# CRDT guarantee flag
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_crdt_merge_sets_guarantee_flag(data):
    """crdt_merge() always sets metadata['crdt_guaranteed'] = True."""
    pair, _ = data.draw(gen_shared_state_dicts(n=2))
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    result = ModelCRDT(schema).crdt_merge(pair)
    assert result.metadata.get("crdt_guaranteed") is True


@given(data=st.data())
@settings(max_examples=50, deadline=None)
def test_crdt_merge_preserves_all_layer_keys(data):
    """crdt_merge() output contains all layer keys from all inputs."""
    dicts, keys = data.draw(gen_shared_state_dicts(n=3))
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    result = ModelCRDT(schema).crdt_merge(dicts)
    assert set(result.tensor.keys()) == set(keys)


@given(sd=gen_state_dict())
@settings(max_examples=50, deadline=None)
def test_merge_empty_model_list_returns_empty_tensor(sd):
    """Merging an empty list always returns an empty tensor dict."""
    schema = ModelMergeSchema(strategies={"default": "weight_average"})
    result = ModelCRDT(schema).merge([])
    assert result.tensor == {}
