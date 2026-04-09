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

"""Property-based tests for crdt_merge.schema_evolution.

Covers: evolve_schema policies, widen_type idempotency and symmetry,
register_widening, rename_column, and SchemaEvolutionResult serialization.
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from crdt_merge.schema_evolution import (
    TYPE_WIDENING,
    SchemaPolicy,
    evolve_schema,
    register_widening,
    widen_type,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_col_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=12,
)

_known_types = st.sampled_from(
    ["int32", "int64", "float32", "float64", "str"]
)

_schema = st.dictionaries(
    keys=_col_name,
    values=_known_types,
    min_size=0,
    max_size=6,
)


# ---------------------------------------------------------------------------
# evolve_schema -- no-change when old == new
# ---------------------------------------------------------------------------


@given(schema=_schema)
@settings(max_examples=50)
def test_evolve_schema_same_input_all_unchanged(schema):
    """evolve_schema(a, a) reports all columns as 'unchanged' or adds none."""
    result = evolve_schema(schema, schema, policy=SchemaPolicy.UNION)
    for change in result.changes:
        assert change.change_type == "unchanged", (
            f"Column {change.column!r} should be unchanged when old == new"
        )


@given(schema=_schema)
@settings(max_examples=50)
def test_evolve_schema_same_input_resolved_equals_input(schema):
    """evolve_schema(a, a) resolved_schema equals the input schema."""
    result = evolve_schema(schema, schema)
    assert result.resolved_schema == schema


# ---------------------------------------------------------------------------
# evolve_schema -- UNION includes all keys from both sides
# ---------------------------------------------------------------------------


@given(a=_schema, b=_schema)
@settings(max_examples=50)
def test_evolve_schema_union_has_all_keys(a, b):
    """UNION policy: resolved_schema contains every key from both schemas."""
    result = evolve_schema(a, b, policy=SchemaPolicy.UNION)
    for k in a:
        assert k in result.resolved_schema
    for k in b:
        assert k in result.resolved_schema


# ---------------------------------------------------------------------------
# evolve_schema -- INTERSECTION keeps only common keys
# ---------------------------------------------------------------------------


@given(a=_schema, b=_schema)
@settings(max_examples=50)
def test_evolve_schema_intersection_has_only_common_keys(a, b):
    """INTERSECTION policy: resolved_schema contains only keys in both schemas."""
    result = evolve_schema(a, b, policy=SchemaPolicy.INTERSECTION)
    common = set(a) & set(b)
    assert set(result.resolved_schema.keys()) == common


@given(a=_schema, b=_schema)
@settings(max_examples=50)
def test_evolve_schema_intersection_no_extra_keys(a, b):
    """INTERSECTION resolved schema keys are a subset of each input's keys."""
    result = evolve_schema(a, b, policy=SchemaPolicy.INTERSECTION)
    for k in result.resolved_schema:
        assert k in a
        assert k in b


# ---------------------------------------------------------------------------
# evolve_schema -- LEFT_PRIORITY
# ---------------------------------------------------------------------------


@given(a=_schema, b=_schema)
@settings(max_examples=50)
def test_evolve_schema_left_priority_keeps_left_types_for_common(a, b):
    """LEFT_PRIORITY: shared columns retain the left schema's type."""
    result = evolve_schema(a, b, policy=SchemaPolicy.LEFT_PRIORITY)
    for k in set(a) & set(b):
        assert result.resolved_schema[k] == a[k]


# ---------------------------------------------------------------------------
# widen_type -- idempotency and known pairs
# ---------------------------------------------------------------------------


@given(t=_known_types)
@settings(max_examples=50)
def test_widen_type_same_type_returns_itself(t):
    """widen_type(t, t) returns t for any known type."""
    assert widen_type(t, t) == t


@given(
    pair=st.sampled_from(
        [
            ("int32", "int64"),
            ("float32", "float64"),
            ("int32", "float64"),
            ("int64", "float64"),
        ]
    )
)
@settings(max_examples=50)
def test_widen_type_known_pairs_return_non_none(pair):
    """Known widening pairs (int32→int64, etc.) always return a result."""
    t_a, t_b = pair
    assert widen_type(t_a, t_b) is not None


@given(
    pair=st.sampled_from(
        [
            ("int32", "int64"),
            ("float32", "float64"),
            ("int32", "float64"),
            ("int64", "float64"),
        ]
    )
)
@settings(max_examples=50)
def test_widen_type_symmetric(pair):
    """widen_type is symmetric: widen(a,b) == widen(b,a)."""
    a, b = pair
    assert widen_type(a, b) == widen_type(b, a)


# ---------------------------------------------------------------------------
# register_widening -- custom rule is queryable afterward
# ---------------------------------------------------------------------------


@given(
    result_type=st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz_"),
)
@settings(max_examples=50)
def test_register_widening_then_widen_returns_registered(result_type):
    """After register_widening(a, b, r), widen_type(a, b) returns r."""
    # Use unique unlikely names to avoid conflicts with built-in rules
    ta = f"__pbt_type_x_{result_type}"
    tb = f"__pbt_type_y_{result_type}"
    register_widening(ta, tb, result_type)
    assert widen_type(ta, tb) == result_type
    assert widen_type(tb, ta) == result_type


# ---------------------------------------------------------------------------
# SchemaEvolutionResult -- rename_column
# ---------------------------------------------------------------------------


@given(col=_col_name, new_col=_col_name, typ=_known_types)
@settings(max_examples=50)
def test_rename_column_changes_key_preserves_type(col, new_col, typ):
    """rename_column moves the key, keeps the type, and adds to renames list."""
    assume(col != new_col)
    schema = {col: typ}
    result = evolve_schema(schema, schema)
    result.rename_column(col, new_col)
    assert new_col in result.resolved_schema
    assert col not in result.resolved_schema
    assert result.resolved_schema[new_col] == typ
    assert any(r.old_name == col and r.new_name == new_col for r in result.renames)


@given(col=_col_name, typ=_known_types)
@settings(max_examples=50)
def test_rename_column_missing_key_raises(col, typ):
    """rename_column raises KeyError when the column doesn't exist."""
    schema = {col: typ}
    result = evolve_schema(schema, schema)
    # Remove the key so it is absent from resolved_schema
    result.resolved_schema.clear()
    with pytest.raises(KeyError):
        result.rename_column(col, col + "_new")


# ---------------------------------------------------------------------------
# SchemaEvolutionResult -- serialisation roundtrip
# ---------------------------------------------------------------------------


@given(a=_schema, b=_schema)
@settings(max_examples=50)
def test_schema_evolution_result_to_from_dict_roundtrip(a, b):
    """SchemaEvolutionResult.to_dict / from_dict roundtrip preserves state."""
    from crdt_merge.schema_evolution import SchemaEvolutionResult

    result = evolve_schema(a, b, policy=SchemaPolicy.UNION)
    d = result.to_dict()
    restored = SchemaEvolutionResult.from_dict(d)
    assert restored.resolved_schema == result.resolved_schema
    assert restored.policy_used == result.policy_used
    assert restored.is_compatible == result.is_compatible


# ---------------------------------------------------------------------------
# evolve_schema -- compatible flag
# ---------------------------------------------------------------------------


@given(schema=_schema)
@settings(max_examples=50)
def test_evolve_schema_identical_is_always_compatible(schema):
    """Identical schemas always produce is_compatible == True."""
    result = evolve_schema(schema, schema)
    assert result.is_compatible is True


@given(a=_schema)
@settings(max_examples=50)
def test_evolve_schema_changes_count_non_negative(a):
    """Number of schema changes is always >= 0."""
    b = {k: v for k, v in list(a.items())[:max(0, len(a) - 1)]}
    result = evolve_schema(a, b, policy=SchemaPolicy.UNION)
    assert len(result.changes) >= 0
