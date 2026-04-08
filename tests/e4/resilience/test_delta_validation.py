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

"""Tests for delta resilience (Whitfield §11, Wei §21, Chen §4-5)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.delta_validation import (
    ReanchorPolicy,
    DeltaCompositionSpec,
    CompositionConflict,
    ParameterTypeEncoder,
    ParameterType,
    CommutativityAdapter,
)


class TestReanchorPolicy:
    def test_no_reanchor_at_start(self):
        p = ReanchorPolicy(max_chain_length=10)
        assert not p.needs_reanchor()

    def test_reanchor_at_chain_limit(self):
        p = ReanchorPolicy(max_chain_length=5)
        for _ in range(5):
            p.record_composition()
        assert p.needs_reanchor()

    def test_reanchor_at_error_limit(self):
        p = ReanchorPolicy(max_chain_length=1000, max_error_bound=0.01, quantization_error=0.005)
        p.record_composition()
        p.record_composition()
        assert p.needs_reanchor()  # 2 * 0.005 = 0.01

    def test_checkpoint_resets_chain(self):
        p = ReanchorPolicy(max_chain_length=5)
        for _ in range(4):
            p.record_composition()
        cp = p.checkpoint(version=1, state_hash="abc123")
        assert p.chain_length == 0
        assert cp.chain_length == 4

    def test_error_estimation(self):
        p = ReanchorPolicy(quantization_error=0.001)
        for _ in range(10):
            p.record_composition()
        assert p.estimated_error == pytest.approx(0.01)


class TestDeltaCompositionSpec:
    def setup_method(self):
        self.spec = DeltaCompositionSpec()

    def test_simple_insertion(self):
        result = self.spec.compose(
            {b"k1": b"v1"}, {}, frozenset(),
            {}, {}, frozenset(),
        )
        assert b"k1" in result.insertions

    def test_insert_then_delete_tombstone(self):
        result = self.spec.compose(
            {b"k1": b"v1"}, {}, frozenset(),
            {}, {}, frozenset([b"k1"]),
        )
        assert b"k1" in result.tombstones
        assert b"k1" not in result.insertions

    def test_delete_then_insert(self):
        result = self.spec.compose(
            {}, {}, frozenset([b"k1"]),
            {b"k1": b"v2"}, {}, frozenset(),
        )
        assert b"k1" in result.insertions
        assert result.insertions[b"k1"] == b"v2"

    def test_double_update(self):
        result = self.spec.compose(
            {}, {b"k1": ("old", b"mid")}, frozenset(),
            {}, {b"k1": ("mid_h", b"new")}, frozenset(),
        )
        assert b"k1" in result.updates
        old, new = result.updates[b"k1"]
        assert old == "old"
        assert new == b"new"

    def test_update_then_delete(self):
        result = self.spec.compose(
            {}, {b"k1": ("old", b"mid")}, frozenset(),
            {}, {}, frozenset([b"k1"]),
        )
        assert b"k1" in result.deletions

    def test_empty_compose(self):
        result = self.spec.compose({}, {}, frozenset(), {}, {}, frozenset())
        assert not result.insertions
        assert not result.updates
        assert not result.deletions


class TestParameterTypeEncoder:
    def setup_method(self):
        self.enc = ParameterTypeEncoder()

    def test_classify_attention(self):
        assert self.enc.classify("model.layers.0.q_proj.weight") == ParameterType.ATTENTION_QKV

    def test_classify_layer_norm(self):
        assert self.enc.classify("model.layer_norm.weight") == ParameterType.LAYER_NORM

    def test_classify_embedding(self):
        assert self.enc.classify("model.embed_tokens.weight") == ParameterType.EMBEDDING

    def test_classify_unknown(self):
        assert self.enc.classify("some_random_param") == ParameterType.GENERIC

    def test_recommend_attention_is_sparse(self):
        rec = self.enc.recommend("model.layers.0.q_proj.weight")
        assert rec.encoding == "sparse"

    def test_recommend_layernorm_is_raw(self):
        rec = self.enc.recommend("model.layer_norm.weight")
        assert rec.encoding == "raw"
        assert rec.bits == 32

    def test_batch_recommend(self):
        keys = ["model.q_proj.w", "model.layer_norm.w", "model.fc1.w"]
        recs = self.enc.batch_recommend(keys)
        assert len(recs) == 3

    def test_register_custom_pattern(self):
        self.enc.register_pattern("my_custom", ParameterType.CLASSIFIER)
        assert self.enc.classify("my_custom.weight") == ParameterType.CLASSIFIER


class TestCommutativityAdapter:
    def setup_method(self):
        self.adapter = CommutativityAdapter()

    def test_canonicalize_is_deterministic(self):
        entries = [
            ("peer-b", 2.0, b"val2"),
            ("peer-a", 1.0, b"val1"),
        ]
        c1 = self.adapter.canonicalize(entries)
        c2 = self.adapter.canonicalize(list(reversed(entries)))
        assert [e[0] for e in c1] == [e[0] for e in c2]

    def test_commutative_merge(self):
        entries = [
            ("peer-b", 2.0, 10.0),
            ("peer-a", 1.0, 20.0),
        ]
        result1 = self.adapter.commutative_merge(entries, lambda vs: sum(vs))
        result2 = self.adapter.commutative_merge(
            list(reversed(entries)), lambda vs: sum(vs),
        )
        assert result1 == result2

    def test_is_commutative_safe_for_sum(self):
        entries = [
            ("peer-a", 1.0, 10.0),
            ("peer-b", 2.0, 20.0),
        ]
        assert self.adapter.is_commutative_safe(entries, lambda vs: sum(vs))
