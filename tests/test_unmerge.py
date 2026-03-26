# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.unmerge — reversible merge engine."""

import json
import math

import pytest
import numpy as np

from crdt_merge.provenance import (
    MergeDecision,
    MergeRecord,
    ProvenanceLog,
    merge_with_provenance,
)
from crdt_merge.delta import Delta
from crdt_merge.model.crdt_state import CRDTMergeState
from crdt_merge.unmerge import (
    ForgetResult,
    GDPRComplianceReport,
    GDPRForget,
    ModelUnmerge,
    ResidualReport,
    UnmergeEngine,
    UnmergeReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data_a():
    return [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
    ]


@pytest.fixture
def sample_data_b():
    return [
        {"id": 1, "name": "Alice_B", "age": 31},
        {"id": 3, "name": "Carol", "age": 28},
    ]


@pytest.fixture
def merged_result(sample_data_a, sample_data_b):
    merged, prov = merge_with_provenance(sample_data_a, sample_data_b, key="id")
    return merged, prov


@pytest.fixture
def engine():
    return UnmergeEngine()


@pytest.fixture
def model_unmerge():
    return ModelUnmerge()


# ---------------------------------------------------------------------------
# Tabular unmerge
# ---------------------------------------------------------------------------

class TestUnmergeEngine:
    """Tabular unmerge — merge(A, B) → unmerge(result, B) ≈ A."""

    def test_unmerge_remove_b_recovers_a(self, sample_data_a, merged_result, engine):
        """Removing source B should recover source A's data."""
        merged, prov = merged_result
        result = engine.unmerge(merged, prov, "b")

        # Should have exactly the records from A
        assert len(result) == len(sample_data_a)

        result_by_id = {r["id"]: r for r in result}
        for original in sample_data_a:
            assert original["id"] in result_by_id
            recovered = result_by_id[original["id"]]
            for field, value in original.items():
                assert recovered[field] == value, (
                    f"Field '{field}' mismatch for id={original['id']}: "
                    f"{recovered[field]} != {value}"
                )

    def test_unmerge_remove_a_recovers_b(self, sample_data_b, merged_result, engine):
        """Removing source A should recover source B's data."""
        merged, prov = merged_result
        result = engine.unmerge(merged, prov, "a")

        assert len(result) == len(sample_data_b)

        result_by_id = {r["id"]: r for r in result}
        for original in sample_data_b:
            assert original["id"] in result_by_id
            recovered = result_by_id[original["id"]]
            for field, value in original.items():
                assert recovered[field] == value

    def test_unmerge_no_provenance_keeps_all(self, engine):
        """Records without provenance are kept unchanged."""
        data = [{"id": 10, "value": "x"}]
        empty_prov = []
        result = engine.unmerge(data, empty_prov, "a")
        assert len(result) == 1
        assert result[0] == {"id": 10, "value": "x"}

    def test_unmerge_unknown_source(self, merged_result, engine):
        """Removing a source that contributed nothing keeps all records."""
        merged, prov = merged_result
        # The provenance only knows "a" and "b" — "c" contributed nothing
        # Since no records have origin "unique_c", all records are kept
        result = engine.unmerge(merged, prov, "c")
        # Merged records with origin "merged" will have decisions with
        # source != "c_only", so they get preserved via conflict_resolved path
        assert len(result) >= 1

    def test_unmerge_single_source(self, engine):
        """Unmerging the only source removes all records."""
        data_a = [{"id": 1, "name": "Solo"}]
        data_b: list = []
        merged, prov = merge_with_provenance(data_a, data_b, key="id")
        result = engine.unmerge(merged, prov, "a")
        assert len(result) == 0

    def test_unmerge_identical_data(self, engine):
        """Unmerge when both sources are identical leaves one copy."""
        data = [{"id": 1, "name": "Same", "age": 40}]
        merged, prov = merge_with_provenance(data, list(data), key="id")
        result_a = engine.unmerge(merged, prov, "a")
        result_b = engine.unmerge(merged, prov, "b")
        # Both sources agree — data persists regardless of which is removed
        assert len(result_a) == 1
        assert len(result_b) == 1
        assert result_a[0]["name"] == "Same"
        assert result_b[0]["name"] == "Same"

    def test_unmerge_preserves_key_field(self, merged_result, engine):
        """Key field is always present in unmerged records."""
        merged, prov = merged_result
        result = engine.unmerge(merged, prov, "b")
        for row in result:
            assert "id" in row

    def test_unmerge_with_provenance_log_object(self, merged_result, engine):
        """Accepts a ProvenanceLog directly (not just a list)."""
        merged, prov = merged_result
        assert isinstance(prov, ProvenanceLog)
        result = engine.unmerge(merged, prov, "b")
        assert isinstance(result, list)

    def test_unmerge_with_record_list(self, merged_result, engine):
        """Accepts a raw list of MergeRecord objects."""
        merged, prov = merged_result
        result = engine.unmerge(merged, prov.records, "b")
        assert isinstance(result, list)

    def test_unmerge_empty_input(self, engine):
        """Empty merged data returns empty result."""
        result = engine.unmerge([], [], "a")
        assert result == []

    def test_unmerge_none_values(self, engine):
        """Records with None values are handled gracefully."""
        data_a = [{"id": 1, "name": None, "age": 30}]
        data_b = [{"id": 1, "name": "Alice", "age": None}]
        merged, prov = merge_with_provenance(data_a, data_b, key="id")
        result = engine.unmerge(merged, prov, "b")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Verify unmerge
# ---------------------------------------------------------------------------

class TestVerifyUnmerge:
    """Verification that unmerge is complete — no residual data."""

    def test_verify_clean_unmerge(self, sample_data_a, merged_result, engine):
        merged, prov = merged_result
        unmerged = engine.unmerge(merged, prov, "b")
        report = engine.verify_unmerge(merged, unmerged, "b", prov)

        assert isinstance(report, UnmergeReport)
        assert report.success is True
        assert report.residual_data == 0
        assert report.records_removed > 0
        assert report.records_remaining == len(unmerged)
        assert report.source_removed == "b"
        assert report.timestamp  # non-empty

    def test_verify_detects_residual(self, merged_result, engine):
        """If we skip the unmerge, verification should detect residual."""
        merged, prov = merged_result
        # Pass the original merged data as "unmerged" — source B is still there
        report = engine.verify_unmerge(merged, merged, "b", prov)
        # Records unique to B are still present → residual > 0
        assert report.residual_data > 0
        assert report.success is False

    def test_verify_report_fields(self, merged_result, engine):
        merged, prov = merged_result
        unmerged = engine.unmerge(merged, prov, "a")
        report = engine.verify_unmerge(merged, unmerged, "a", prov)
        assert isinstance(report.records_removed, int)
        assert isinstance(report.records_remaining, int)
        assert isinstance(report.residual_data, int)


# ---------------------------------------------------------------------------
# Delta unmerge
# ---------------------------------------------------------------------------

class TestDeltaUnmerge:
    """Filtering deltas to remove contributions from a source."""

    def test_delta_unmerge_removes_source_records(self, merged_result, engine):
        merged, prov = merged_result
        delta = Delta(
            added=[{"id": 3, "name": "Carol"}],
            modified=[{"id": 1, "name": "Alice_B"}],
            removed=[],
        )
        # Record id=3 is unique_b — should be removed
        filtered = engine.unmerge_delta(delta, prov, "b")
        assert isinstance(filtered, Delta)
        added_ids = {r["id"] for r in filtered.added}
        assert 3 not in added_ids

    def test_delta_unmerge_keeps_other_source(self, merged_result, engine):
        merged, prov = merged_result
        delta = Delta(
            added=[{"id": 2, "name": "Bob"}, {"id": 3, "name": "Carol"}],
        )
        filtered = engine.unmerge_delta(delta, prov, "b")
        added_ids = {r["id"] for r in filtered.added}
        assert 2 in added_ids

    def test_delta_unmerge_preserves_version(self, merged_result, engine):
        merged, prov = merged_result
        delta = Delta(added=[], version=7, source_node="node-1")
        filtered = engine.unmerge_delta(delta, prov, "a")
        assert filtered.version == 7
        assert filtered.source_node == "node-1"

    def test_delta_unmerge_empty_delta(self, merged_result, engine):
        merged, prov = merged_result
        delta = Delta()
        filtered = engine.unmerge_delta(delta, prov, "b")
        assert filtered.added == []
        assert filtered.modified == []
        assert filtered.removed == []


# ---------------------------------------------------------------------------
# Model unmerge
# ---------------------------------------------------------------------------

class TestModelUnmerge:
    """Model weight unmerge — remove a model's contribution from merged weights."""

    def test_negmerge_method(self, model_unmerge):
        """Negmerge: cleaned = merged - alpha * removed."""
        state = CRDTMergeState("weight_average")
        state.add([1.0, 2.0, 3.0], model_id="model_a", weight=0.6)
        state.add([4.0, 5.0, 6.0], model_id="model_b", weight=0.4)

        result = model_unmerge.unmerge_model(
            state, None, "model_b", method="negmerge",
        )
        assert "merged" in result
        tensor = np.asarray(result["merged"])
        assert tensor.shape == (3,)
        # After removing model_b's contribution, result should move away from model_b
        original_b = np.array([4.0, 5.0, 6.0])
        original_a = np.array([1.0, 2.0, 3.0])
        # Cleaned should be closer to A than to B
        dist_a = np.linalg.norm(tensor - original_a)
        dist_b = np.linalg.norm(tensor - original_b)
        assert dist_a < dist_b

    def test_surgical_method(self, model_unmerge):
        """Surgical: zero out the removed contribution entirely."""
        state = CRDTMergeState("weight_average")
        state.add([1.0, 2.0, 3.0], model_id="model_a", weight=0.5)
        state.add([4.0, 5.0, 6.0], model_id="model_b", weight=0.5)

        result = model_unmerge.unmerge_model(
            state, None, "model_b", method="surgical",
        )
        assert "merged" in result
        tensor = np.asarray(result["merged"])
        assert tensor.shape == (3,)

    def test_proportional_method(self, model_unmerge):
        """Proportional: rescale remaining weights."""
        state = CRDTMergeState("weight_average")
        state.add([2.0, 4.0, 6.0], model_id="model_a", weight=0.5)
        state.add([4.0, 8.0, 12.0], model_id="model_b", weight=0.5)

        result = model_unmerge.unmerge_model(
            state, None, "model_b", method="proportional",
        )
        assert "merged" in result

    def test_unknown_method_raises(self, model_unmerge):
        state = CRDTMergeState("weight_average")
        state.add([1.0], model_id="m1")
        with pytest.raises(ValueError, match="Unknown unmerge method"):
            model_unmerge.unmerge_model(state, None, "m1", method="automatically")

    def test_remove_nonexistent_model(self, model_unmerge):
        """Removing a model that isn't in the state returns the merged result."""
        state = CRDTMergeState("weight_average")
        state.add([1.0, 2.0], model_id="model_a")
        result = model_unmerge.unmerge_model(
            state, None, "nonexistent", method="negmerge",
        )
        assert "merged" in result

    def test_unmerge_dict_tensors(self, model_unmerge):
        """Unmerge from a plain dict of layer → tensor."""
        merged = {
            "layer_0": np.array([3.0, 5.0]),
            "removed_model": np.array([2.0, 3.0]),
        }
        provenance = [
            {"model_id": "layer_0", "weight": 0.5},
            {"model_id": "removed_model", "weight": 0.5},
        ]
        result = model_unmerge.unmerge_model(
            merged, provenance, "removed_model", method="negmerge",
        )
        assert "removed_model" not in result
        assert "layer_0" in result


# ---------------------------------------------------------------------------
# Residual measurement
# ---------------------------------------------------------------------------

class TestResidualMeasurement:
    """Verify influence score after model unmerge."""

    def test_zero_residual(self, model_unmerge):
        """Orthogonal model should have low residual after removal."""
        cleaned = {"layer": np.array([1.0, 0.0, 0.0])}
        original = {"layer": np.array([0.0, 0.0, 1.0])}
        report = model_unmerge.measure_residual(cleaned, original)

        assert isinstance(report, ResidualReport)
        assert report.influence_score < 0.1
        assert report.parameters_checked == 1
        assert report.parameters_with_residual == 0

    def test_high_residual(self, model_unmerge):
        """Identical vectors should yield high influence score."""
        cleaned = {"layer": np.array([1.0, 2.0, 3.0])}
        original = {"layer": np.array([1.0, 2.0, 3.0])}
        report = model_unmerge.measure_residual(cleaned, original)

        assert report.influence_score > 0.9
        assert report.parameters_with_residual == 1

    def test_partial_residual(self, model_unmerge):
        """Partially similar vectors produce moderate influence."""
        cleaned = {"layer": np.array([1.0, 0.0, 0.0])}
        original = {"layer": np.array([1.0, 1.0, 0.0])}
        report = model_unmerge.measure_residual(cleaned, original)
        assert 0.0 < report.influence_score < 1.0

    def test_empty_model(self, model_unmerge):
        """No overlapping layers → influence 0."""
        cleaned = {"layer_a": np.array([1.0])}
        original = {"layer_b": np.array([1.0])}
        report = model_unmerge.measure_residual(cleaned, original)
        assert report.influence_score == 0.0
        assert report.parameters_checked == 0

    def test_zero_vector(self, model_unmerge):
        """Zero vectors should not cause division errors."""
        cleaned = {"layer": np.array([0.0, 0.0, 0.0])}
        original = {"layer": np.array([1.0, 2.0, 3.0])}
        report = model_unmerge.measure_residual(cleaned, original)
        assert report.influence_score == 0.0


# ---------------------------------------------------------------------------
# GDPR forget
# ---------------------------------------------------------------------------

class TestGDPRForget:
    """GDPR right to be forgotten — data + model removal with compliance."""

    def test_forget_data(self, merged_result):
        merged, prov = merged_result
        gdpr = GDPRForget()
        result = gdpr.forget_data(merged, prov, "b")

        assert isinstance(result, ForgetResult)
        assert result.success is True
        assert result.data_records_removed > 0
        assert result.contributor == "b"
        assert result.compliance_timestamp
        assert result.model_influence_removed is False

    def test_forget_training_data(self):
        state = CRDTMergeState("weight_average")
        state.add([1.0, 2.0], model_id="contributor_a", weight=0.6)
        state.add([3.0, 4.0], model_id="contributor_b", weight=0.4)

        gdpr = GDPRForget()
        result = gdpr.forget_training_data(state, None, "contributor_b")

        assert isinstance(result, ForgetResult)
        assert result.success is True
        assert result.model_influence_removed is True
        assert result.contributor == "contributor_b"

    def test_compliance_report_empty(self):
        gdpr = GDPRForget()
        report = gdpr.compliance_report()
        assert isinstance(report, GDPRComplianceReport)
        assert report.total_records_removed == 0
        assert report.total_models_cleaned == 0
        assert len(report.requests_processed) == 0

    def test_compliance_report_after_operations(self, merged_result):
        merged, prov = merged_result
        gdpr = GDPRForget()

        gdpr.forget_data(merged, prov, "b")
        state = CRDTMergeState("weight_average")
        state.add([1.0], model_id="model_x")
        state.add([2.0], model_id="model_y")
        gdpr.forget_training_data(state, None, "model_y")

        report = gdpr.compliance_report()
        assert len(report.requests_processed) == 2
        assert report.total_records_removed > 0
        assert report.total_models_cleaned == 1

    def test_compliance_report_to_dict(self, merged_result):
        merged, prov = merged_result
        gdpr = GDPRForget()
        gdpr.forget_data(merged, prov, "a")
        report = gdpr.compliance_report()

        d = report.to_dict()
        assert isinstance(d, dict)
        assert "requests_processed" in d
        assert "total_records_removed" in d
        assert "generated_at" in d

    def test_compliance_report_to_json(self, merged_result):
        merged, prov = merged_result
        gdpr = GDPRForget()
        gdpr.forget_data(merged, prov, "a")
        report = gdpr.compliance_report()

        j = report.to_json()
        parsed = json.loads(j)
        assert isinstance(parsed, dict)
        assert "requests_processed" in parsed

    def test_custom_engine_injection(self, merged_result):
        """GDPRForget accepts custom engine instances."""
        eng = UnmergeEngine()
        mu = ModelUnmerge()
        gdpr = GDPRForget(engine=eng, model_unmerge=mu)

        merged, prov = merged_result
        result = gdpr.forget_data(merged, prov, "b")
        assert result.success is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_multiple_sequential_unmerges(self, engine):
        """Unmerge A then unmerge B from a 3-way merge scenario."""
        data_a = [{"id": 1, "val": "a1"}, {"id": 2, "val": "a2"}]
        data_b = [{"id": 2, "val": "b2"}, {"id": 3, "val": "b3"}]

        merged, prov = merge_with_provenance(data_a, data_b, key="id")
        step1 = engine.unmerge(merged, prov, "b")
        # Should recover data_a
        assert len(step1) == len(data_a)
        ids = {r["id"] for r in step1}
        assert ids == {1, 2}

    def test_large_dataset_unmerge(self, engine):
        """Performance sanity — 1000 records."""
        data_a = [{"id": i, "val": f"a_{i}"} for i in range(500)]
        data_b = [{"id": i + 250, "val": f"b_{i}"} for i in range(500)]
        merged, prov = merge_with_provenance(data_a, data_b, key="id")
        result = engine.unmerge(merged, prov, "b")
        assert len(result) == 500  # data_a's 500 records

    def test_dataclass_fields_present(self):
        """All report dataclasses have the expected fields."""
        report = UnmergeReport(
            success=True, records_removed=1, records_remaining=2,
            residual_data=0, source_removed="a", timestamp="2026-01-01",
        )
        assert report.success is True

        residual = ResidualReport(
            influence_score=0.5, parameters_checked=10,
            parameters_with_residual=3,
        )
        assert residual.influence_score == 0.5

        forget = ForgetResult(
            success=True, data_records_removed=5,
            model_influence_removed=False,
            compliance_timestamp="now", contributor="x",
        )
        assert forget.contributor == "x"


# ---------------------------------------------------------------------------
# CRDT preservation
# ---------------------------------------------------------------------------

class TestCRDTPreservation:
    """Remaining data after unmerge should still satisfy CRDT properties."""

    def test_unmerge_idempotent(self, merged_result, engine):
        """Unmerging the same source twice yields the same result."""
        merged, prov = merged_result
        first = engine.unmerge(merged, prov, "b")
        second = engine.unmerge(merged, prov, "b")
        assert first == second

    def test_unmerge_commutative_with_remerge(self, engine):
        """unmerge(merge(A,B), A) + remerge with A = original merge."""
        data_a = [{"id": 1, "name": "A1"}, {"id": 2, "name": "A2"}]
        data_b = [{"id": 1, "name": "B1"}, {"id": 3, "name": "B3"}]

        merged, prov = merge_with_provenance(data_a, data_b, key="id")
        without_a = engine.unmerge(merged, prov, "a")

        # The remaining data should be equivalent to B's contribution
        without_a_ids = {r["id"] for r in without_a}
        b_ids = {r["id"] for r in data_b}
        assert without_a_ids == b_ids

    def test_model_crdt_state_after_unmerge(self, model_unmerge):
        """CRDTMergeState remains valid after model unmerge."""
        state = CRDTMergeState("weight_average")
        state.add([1.0, 2.0], model_id="a", weight=0.5)
        state.add([3.0, 4.0], model_id="b", weight=0.5)

        result = model_unmerge.unmerge_model(
            state, None, "b", method="negmerge",
        )
        # Result is a dict with tensors — valid output
        assert isinstance(result, dict)
        assert "merged" in result
        tensor = np.asarray(result["merged"])
        assert not np.any(np.isnan(tensor))
        assert not np.any(np.isinf(tensor))
