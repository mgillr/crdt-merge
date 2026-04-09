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

"""Tests for crdt_merge.schema_evolution — ~25 tests."""

import pytest

from crdt_merge.schema_evolution import (
    SchemaChange,
    SchemaEvolutionResult,
    SchemaPolicy,
    check_compatibility,
    evolve_schema,
    widen_type,
)

# ===================================================================
# 1. SchemaPolicy values
# ===================================================================

class TestSchemaPolicyValues:
    def test_all_four_policies_exist(self):
        assert SchemaPolicy.UNION.value == "union"
        assert SchemaPolicy.INTERSECTION.value == "intersection"
        assert SchemaPolicy.LEFT_PRIORITY.value == "left_priority"
        assert SchemaPolicy.RIGHT_PRIORITY.value == "right_priority"
        assert len(SchemaPolicy) == 4

# ===================================================================
# 2. evolve_schema -- UNION policy (4 tests)
# ===================================================================

class TestEvolveSchemaUnion:
    def test_same_schema_no_changes(self):
        schema = {"id": "int64", "name": "str"}
        result = evolve_schema(schema, schema, SchemaPolicy.UNION)
        assert result.resolved_schema == schema
        assert result.is_compatible is True
        assert all(c.change_type == "unchanged" for c in result.changes)

    def test_added_columns(self):
        old = {"id": "int64"}
        new = {"id": "int64", "email": "str"}
        result = evolve_schema(old, new, SchemaPolicy.UNION)
        assert "email" in result.resolved_schema
        assert result.resolved_schema["email"] == "str"
        added = [c for c in result.changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].column == "email"

    def test_removed_columns(self):
        old = {"id": "int64", "age": "int32"}
        new = {"id": "int64"}
        result = evolve_schema(old, new, SchemaPolicy.UNION)
        # UNION keeps all columns
        assert "age" in result.resolved_schema
        removed = [c for c in result.changes if c.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].column == "age"

    def test_type_conflict_with_widening(self):
        old = {"val": "int32"}
        new = {"val": "int64"}
        result = evolve_schema(old, new, SchemaPolicy.UNION)
        assert result.resolved_schema["val"] == "int64"
        assert result.is_compatible is True
        changed = [c for c in result.changes if c.change_type == "type_changed"]
        assert len(changed) == 1
        assert changed[0].resolved_type == "int64"

# ===================================================================
# 3. evolve_schema -- INTERSECTION policy (3 tests)
# ===================================================================

class TestEvolveSchemaIntersection:
    def test_same_schema(self):
        schema = {"a": "str", "b": "int64"}
        result = evolve_schema(schema, schema, SchemaPolicy.INTERSECTION)
        assert result.resolved_schema == schema

    def test_disjoint_columns_empty_result(self):
        old = {"a": "int64"}
        new = {"b": "str"}
        result = evolve_schema(old, new, SchemaPolicy.INTERSECTION)
        assert result.resolved_schema == {}

    def test_partial_overlap(self):
        old = {"a": "int64", "b": "str"}
        new = {"b": "str", "c": "float64"}
        result = evolve_schema(old, new, SchemaPolicy.INTERSECTION)
        assert result.resolved_schema == {"b": "str"}

# ===================================================================
# 4. evolve_schema -- LEFT_PRIORITY (2 tests)
# ===================================================================

class TestEvolveSchemaLeftPriority:
    def test_new_columns_from_right_added(self):
        old = {"a": "int64"}
        new = {"a": "int64", "b": "str"}
        result = evolve_schema(old, new, SchemaPolicy.LEFT_PRIORITY)
        assert result.resolved_schema == {"a": "int64", "b": "str"}

    def test_type_from_left_kept(self):
        old = {"val": "int32"}
        new = {"val": "float64"}
        result = evolve_schema(old, new, SchemaPolicy.LEFT_PRIORITY)
        assert result.resolved_schema["val"] == "int32"

# ===================================================================
# 5. evolve_schema -- RIGHT_PRIORITY (2 tests)
# ===================================================================

class TestEvolveSchemaRightPriority:
    def test_old_columns_preserved(self):
        old = {"a": "int64", "b": "str"}
        new = {"a": "int64"}
        result = evolve_schema(old, new, SchemaPolicy.RIGHT_PRIORITY)
        assert "b" in result.resolved_schema  # old col kept

    def test_type_from_right_kept(self):
        old = {"val": "int32"}
        new = {"val": "float64"}
        result = evolve_schema(old, new, SchemaPolicy.RIGHT_PRIORITY)
        assert result.resolved_schema["val"] == "float64"

# ===================================================================
# 6. Type widening (3 tests)
# ===================================================================

class TestTypeWidening:
    def test_int_to_float(self):
        assert widen_type("int", "float") == "float"

    def test_int32_to_int64(self):
        assert widen_type("int32", "int64") == "int64"

    def test_incompatible_types_return_none(self):
        assert widen_type("str", "int64") is None

# ===================================================================
# 7. Type narrowing (2 tests)
# ===================================================================

class TestTypeNarrowing:
    def test_narrowing_rejected_by_default(self):
        old = {"val": "float64"}
        new = {"val": "str"}  # incompatible, no widening
        result = evolve_schema(old, new, SchemaPolicy.UNION)
        assert result.is_compatible is False
        assert len(result.warnings) > 0

    def test_narrowing_allowed_when_flag_set(self):
        old = {"val": "float64"}
        new = {"val": "str"}
        result = evolve_schema(
            old, new, SchemaPolicy.UNION, allow_type_narrowing=True
        )
        assert result.resolved_schema["val"] == "str"
        assert len(result.warnings) > 0  # still warns

# ===================================================================
# 8. check_compatibility (2 tests)
# ===================================================================

class TestCheckCompatibility:
    def test_compatible_pair(self):
        a = {"id": "int64", "name": "str"}
        b = {"id": "int64", "name": "str"}
        ok, reasons = check_compatibility(a, b)
        assert ok is True
        assert reasons == []

    def test_incompatible_pair(self):
        a = {"id": "int64", "name": "str"}
        b = {"id": "str", "age": "int32"}
        ok, reasons = check_compatibility(a, b)
        assert ok is False
        assert len(reasons) > 0

# ===================================================================
# 9. SchemaEvolutionResult serialization (1 test)
# ===================================================================

class TestSchemaEvolutionResultSerialization:
    def test_to_dict_from_dict_roundtrip(self):
        original = evolve_schema(
            {"a": "int32", "b": "str"},
            {"a": "int64", "c": "float64"},
            SchemaPolicy.UNION,
            defaults={"b": 0, "c": None},
        )
        d = original.to_dict()
        restored = SchemaEvolutionResult.from_dict(d)

        assert restored.resolved_schema == original.resolved_schema
        assert restored.policy_used == original.policy_used
        assert restored.is_compatible == original.is_compatible
        assert restored.warnings == original.warnings
        assert len(restored.changes) == len(original.changes)
        for orig_c, rest_c in zip(original.changes, restored.changes):
            assert orig_c.column == rest_c.column
            assert orig_c.change_type == rest_c.change_type
            assert orig_c.resolved_type == rest_c.resolved_type

# ===================================================================
# 10. Edge cases (5 tests)
# ===================================================================

class TestEdgeCases:
    def test_empty_old_schema(self):
        result = evolve_schema({}, {"a": "int64"}, SchemaPolicy.UNION)
        assert result.resolved_schema == {"a": "int64"}
        assert result.is_compatible is True

    def test_empty_new_schema(self):
        result = evolve_schema({"a": "int64"}, {}, SchemaPolicy.UNION)
        assert result.resolved_schema == {"a": "int64"}
        assert result.is_compatible is True

    def test_both_schemas_empty(self):
        result = evolve_schema({}, {}, SchemaPolicy.UNION)
        assert result.resolved_schema == {}
        assert result.is_compatible is True
        assert result.changes == []

    def test_none_defaults(self):
        result = evolve_schema(
            {"a": "int64"}, {"b": "str"}, SchemaPolicy.UNION, defaults=None
        )
        assert result.is_compatible is True
        # defaults should have entries (with None values) for added/removed
        assert "a" in result.defaults
        assert "b" in result.defaults

    def test_unknown_types_treated_as_opaque(self):
        old = {"x": "geometry"}
        new = {"x": "geography"}
        # No widening known for these
        assert widen_type("geometry", "geography") is None
        result = evolve_schema(old, new, SchemaPolicy.UNION)
        assert result.is_compatible is False
        assert len(result.warnings) > 0
