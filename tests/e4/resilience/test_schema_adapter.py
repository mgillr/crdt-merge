# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Tests for schema heterogeneity adapter."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "source"))

from crdt_merge.e4.resilience.schema_adapter import (
    SchemaDescriptor,
    FieldDescriptor,
    SchemaAligner,
    SchemaAlignment,
    SchemaRegistry,
    ResultNormaliser,
    NormalisationFactor,
)


class TestSchemaDescriptor:

    def test_create(self):
        sd = SchemaDescriptor(
            schema_id="model-v1",
            version=1,
            fields=[
                FieldDescriptor("weight", "float64", 0),
                FieldDescriptor("bias", "float64", 1),
            ],
        )
        assert sd.field_names() == {"weight", "bias"}

    def test_content_hash(self):
        sd = SchemaDescriptor("m1", 1, [FieldDescriptor("x", "float64", 0)])
        h = sd.content_hash()
        assert len(h) == 16

    def test_get_field(self):
        sd = SchemaDescriptor("m1", 1, [
            FieldDescriptor("weight", "float64", 0),
        ])
        assert sd.get_field("weight") is not None
        assert sd.get_field("nonexistent") is None


class TestFieldDescriptor:

    def test_compatible_same_type(self):
        f1 = FieldDescriptor("x", "float64", 0)
        f2 = FieldDescriptor("x", "float64", 0)
        assert f1.compatible_with(f2)

    def test_compatible_widening(self):
        f1 = FieldDescriptor("x", "float32", 0)
        f2 = FieldDescriptor("x", "float64", 0)
        assert f1.compatible_with(f2)

    def test_incompatible(self):
        f1 = FieldDescriptor("x", "string", 0)
        f2 = FieldDescriptor("x", "float64", 0)
        assert not f1.compatible_with(f2)

    def test_wider_type(self):
        f1 = FieldDescriptor("x", "float32", 0)
        f2 = FieldDescriptor("x", "float64", 0)
        assert f1.wider_type(f2) == "float64"


class TestSchemaAligner:

    def test_identical_schemas(self):
        fields = [
            FieldDescriptor("weight", "float64", 0),
            FieldDescriptor("bias", "float64", 1),
        ]
        s1 = SchemaDescriptor("m1", 1, list(fields))
        s2 = SchemaDescriptor("m2", 1, list(fields))
        alignment = SchemaAligner().align(s1, s2)
        assert alignment.alignment_ratio == 1.0
        assert len(alignment.local_only) == 0

    def test_partial_overlap(self):
        s1 = SchemaDescriptor("m1", 1, [
            FieldDescriptor("weight", "float64", 0),
            FieldDescriptor("bias", "float64", 1),
        ])
        s2 = SchemaDescriptor("m2", 1, [
            FieldDescriptor("weight", "float64", 0),
            FieldDescriptor("gamma", "float64", 1),
        ])
        alignment = SchemaAligner().align(s1, s2)
        assert len(alignment.aligned_fields) == 1
        assert "bias" in alignment.local_only
        assert "gamma" in alignment.remote_only

    def test_fuzzy_matching(self):
        s1 = SchemaDescriptor("m1", 1, [
            FieldDescriptor("learning_rate", "float64", 0),
        ])
        s2 = SchemaDescriptor("m2", 1, [
            FieldDescriptor("learningrate", "float64", 0),
        ])
        # Strict mode: no match
        strict = SchemaAligner(strict=True).align(s1, s2)
        assert len(strict.aligned_fields) == 0
        # Fuzzy mode: match
        fuzzy = SchemaAligner(strict=False).align(s1, s2)
        assert len(fuzzy.aligned_fields) == 1


class TestSchemaRegistry:

    def test_register_and_get(self):
        registry = SchemaRegistry()
        s = SchemaDescriptor("model", 1, [])
        registry.register(s)
        assert registry.get("model", 1) is not None
        assert registry.get("model", 2) is None

    def test_latest(self):
        registry = SchemaRegistry()
        registry.register(SchemaDescriptor("model", 1, []))
        registry.register(SchemaDescriptor("model", 2, []))
        latest = registry.latest("model")
        assert latest.version == 2

    def test_merge_union(self):
        r1 = SchemaRegistry()
        r1.register(SchemaDescriptor("a", 1, []))
        r2 = SchemaRegistry()
        r2.register(SchemaDescriptor("b", 1, []))
        r1.merge(r2)
        assert r1.schema_count == 2


class TestResultNormaliser:

    def test_register_and_normalise(self):
        norm = ResultNormaliser()
        norm.register_factor(NormalisationFactor(
            "v100:imagenet-val", "v100", "imagenet-val", 1.1, -0.02,
        ))
        result = norm.normalise(0.75, "v100", "imagenet-val")
        assert abs(result - (0.75 - 0.02) * 1.1) < 0.001

    def test_unknown_hardware_passthrough(self):
        norm = ResultNormaliser()
        assert norm.normalise(0.8, "tpu", "custom") == 0.8

    def test_calibration(self):
        norm = ResultNormaliser()
        norm.register_from_calibration("v100", "cifar10", 0.95, 0.90)
        assert norm.factor_count == 1
