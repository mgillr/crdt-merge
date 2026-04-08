# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Tests for crdt_merge.compliance module."""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock

from crdt_merge.compliance import (
    ComplianceAuditor,
    ComplianceFinding,
    ComplianceReport,
    EUAIActReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auditor_with_merges(framework: str = "eu_ai_act", count: int = 3) -> ComplianceAuditor:
    """Create an auditor with some merge events pre-recorded."""
    auditor = ComplianceAuditor(framework=framework, node_id="test-node")
    for i in range(count):
        auditor.record_merge(
            operation="merge",
            input_hash=f"in_hash_{i}",
            output_hash=f"out_hash_{i}",
            metadata={"batch": i, "has_provenance": True},
        )
    return auditor


def _make_mock_audit_log(n_entries: int = 3) -> MagicMock:
    """Build a mock AuditLog with the expected interface."""
    log = MagicMock()
    log.node_id = "mock-node"

    entries = []
    for i in range(n_entries):
        entry = MagicMock()
        entry.operation = "merge"
        entry.input_hash = f"ih_{i}"
        entry.output_hash = f"oh_{i}"
        entry.metadata = {"row_count": i * 10}
        entries.append(entry)

    log.entries = entries
    return log


def _make_mock_provenance_log(n_records: int = 3) -> MagicMock:
    """Build a mock ProvenanceLog with the expected interface."""
    log = MagicMock()

    records = []
    for i in range(n_records):
        record = MagicMock()
        record.key = f"key_{i}"
        record.origin = "merged"
        record.conflict_count = i
        records.append(record)

    log.records = records
    return log


# ===========================================================================
# 1. ComplianceAuditor basic record / validate cycle
# ===========================================================================

class TestComplianceAuditorBasic:

    def test_empty_auditor_validates(self):
        auditor = ComplianceAuditor(framework="eu_ai_act")
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)
        assert report.framework == "eu_ai_act"
        assert report.status in ("compliant", "non_compliant", "partial")

    def test_record_merge_and_validate(self):
        auditor = _make_auditor_with_merges()
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)
        assert len(report.findings) > 0

    def test_record_unmerge(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_merge(operation="merge", input_hash="a", output_hash="b")
        auditor.record_unmerge(subject_id="user-42", fields_removed=["email", "phone"])
        report = auditor.validate()
        # GDPR Art. 17 should pass because unmerge events exist
        art17 = next((f for f in report.findings if f.rule_id == "GDPR_ART_17"), None)
        assert art17 is not None
        assert art17.status == "pass"

    def test_record_access(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(
            operation="merge", input_hash="x", output_hash="y",
        )
        auditor.record_access(
            user_id="nurse-1", operation="read", resource="patient-data",
            granted=True,
        )
        report = auditor.validate()
        access_finding = next(
            (f for f in report.findings if f.rule_id == "HIPAA_ACCESS_CONTROL"), None
        )
        assert access_finding is not None
        assert access_finding.status == "pass"

    def test_clear_resets_events(self):
        auditor = _make_auditor_with_merges()
        auditor.record_unmerge(subject_id="x")
        auditor.record_access(user_id="u", operation="r", resource="res", granted=True)
        auditor.clear()
        assert len(auditor._merge_events) == 0
        assert len(auditor._unmerge_events) == 0
        assert len(auditor._access_events) == 0

    def test_generate_report_is_alias(self):
        auditor = _make_auditor_with_merges()
        r1 = auditor.validate()
        r2 = auditor.generate_report()
        # Both should produce the same structure
        assert r1.framework == r2.framework
        assert len(r1.findings) == len(r2.findings)

    def test_invalid_framework_raises(self):
        with pytest.raises(ValueError, match="Unknown framework"):
            ComplianceAuditor(framework="pci_dss")


# ===========================================================================
# 2. EU AI Act report generation
# ===========================================================================

class TestEUAIActReport:

    def test_basic_generation(self):
        auditor = _make_auditor_with_merges(framework="eu_ai_act", count=5)
        eu = EUAIActReport(auditor)
        report = eu.generate()
        assert isinstance(report, ComplianceReport)
        assert report.framework == "eu_ai_act"
        assert "risk_classification" in report.metadata
        assert "transparency" in report.metadata
        assert "data_governance" in report.metadata

    def test_risk_classification_default(self):
        auditor = _make_auditor_with_merges(count=5)
        eu = EUAIActReport(auditor)
        rc = eu.risk_classification()
        assert rc["risk_level"] in ("minimal", "limited", "high", "unclassified")
        assert "obligations" in rc

    def test_risk_classification_high_risk(self):
        auditor = _make_auditor_with_merges(count=1)
        eu = EUAIActReport(auditor)
        rc = eu.risk_classification(
            system_description="Medical diagnosis AI",
            is_high_risk=True,
        )
        assert rc["risk_level"] == "high"
        assert rc["system_description"] == "Medical diagnosis AI"
        assert len(rc["obligations"]) > 3

    def test_transparency_report(self):
        auditor = _make_auditor_with_merges(count=3)
        eu = EUAIActReport(auditor)
        tr = eu.transparency_report()
        assert tr["total_operations"] == 3
        assert tr["article"] == "Art. 13 — Transparency"
        assert 0 <= tr["transparency_score"] <= 1.0

    def test_data_governance(self):
        auditor = _make_auditor_with_merges(count=4)
        auditor.record_unmerge(subject_id="s1")
        eu = EUAIActReport(auditor)
        dg = eu.data_governance()
        assert dg["total_merge_operations"] == 4
        assert dg["erasure_operations"] == 1
        assert dg["article"] == "Art. 10 — Data and data governance"

    def test_empty_auditor_risk(self):
        auditor = ComplianceAuditor(framework="eu_ai_act")
        eu = EUAIActReport(auditor)
        rc = eu.risk_classification()
        assert rc["risk_level"] == "unclassified"

    def test_limited_risk_with_access_controls(self):
        auditor = _make_auditor_with_merges(count=5)
        auditor.record_access(
            user_id="u1", operation="read", resource="r", granted=True,
        )
        eu = EUAIActReport(auditor)
        rc = eu.risk_classification()
        assert rc["risk_level"] == "limited"


# ===========================================================================
# 3. GDPR report with unmerge records
# ===========================================================================

class TestGDPRCompliance:

    def test_gdpr_with_unmerge(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_merge(operation="merge", input_hash="a", output_hash="b")
        auditor.record_unmerge(subject_id="user-123", fields_removed=["name", "email"])
        report = auditor.validate()
        assert report.framework == "gdpr"
        art17 = next(f for f in report.findings if f.rule_id == "GDPR_ART_17")
        assert art17.status == "pass"

    def test_gdpr_without_unmerge_fails_art17(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_merge(operation="merge", input_hash="", output_hash="")
        report = auditor.validate()
        art17 = next(f for f in report.findings if f.rule_id == "GDPR_ART_17")
        assert art17.status == "fail"

    def test_gdpr_processing_records(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_merge(operation="merge", input_hash="a", output_hash="b")
        report = auditor.validate()
        art30 = next(f for f in report.findings if f.rule_id == "GDPR_ART_30")
        assert art30.status == "pass"

    def test_gdpr_consent_tracking(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_merge(
            operation="merge", input_hash="a", output_hash="b",
            metadata={"consent": "opt_in_20260101"},
        )
        report = auditor.validate()
        art7 = next(f for f in report.findings if f.rule_id == "GDPR_ART_7")
        assert art7.status == "pass"

    def test_gdpr_non_compliant_status(self):
        """Empty GDPR auditor should be non_compliant (critical rules fail)."""
        auditor = ComplianceAuditor(framework="gdpr")
        report = auditor.validate()
        assert report.status == "non_compliant"


# ===========================================================================
# 4. HIPAA report with access control records
# ===========================================================================

class TestHIPAACompliance:

    def test_hipaa_with_access_controls(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(
            operation="merge", input_hash="h1", output_hash="h2",
        )
        auditor.record_access(
            user_id="doc-1", operation="read", resource="patient-123",
            granted=True,
        )
        report = auditor.validate()
        ac = next(f for f in report.findings if f.rule_id == "HIPAA_ACCESS_CONTROL")
        assert ac.status == "pass"

    def test_hipaa_without_access_controls_fails(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(operation="merge", input_hash="h1", output_hash="h2")
        report = auditor.validate()
        ac = next(f for f in report.findings if f.rule_id == "HIPAA_ACCESS_CONTROL")
        assert ac.status == "fail"

    def test_hipaa_audit_trail(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(operation="merge", input_hash="a", output_hash="b")
        report = auditor.validate()
        at = next(f for f in report.findings if f.rule_id == "HIPAA_AUDIT_TRAIL")
        assert at.status == "pass"

    def test_hipaa_encryption(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(
            operation="encrypt", input_hash="a", output_hash="b",
        )
        report = auditor.validate()
        enc = next(f for f in report.findings if f.rule_id == "HIPAA_ENCRYPTION")
        assert enc.status == "pass"

    def test_hipaa_encryption_via_metadata(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_merge(
            operation="merge", input_hash="a", output_hash="b",
            metadata={"encrypted": True},
        )
        report = auditor.validate()
        enc = next(f for f in report.findings if f.rule_id == "HIPAA_ENCRYPTION")
        assert enc.status == "pass"


# ===========================================================================
# 5. SOX report with audit trail
# ===========================================================================

class TestSOXCompliance:

    def test_sox_data_integrity(self):
        auditor = ComplianceAuditor(framework="sox")
        auditor.record_merge(operation="merge", input_hash="h1", output_hash="h2")
        report = auditor.validate()
        di = next(f for f in report.findings if f.rule_id == "SOX_DATA_INTEGRITY")
        assert di.status == "pass"

    def test_sox_change_management(self):
        auditor = ComplianceAuditor(framework="sox")
        auditor.record_merge(
            operation="merge", input_hash="h1", output_hash="h2",
            metadata={"user_id": "admin-1"},
        )
        report = auditor.validate()
        cm = next(f for f in report.findings if f.rule_id == "SOX_CHANGE_MGMT")
        assert cm.status == "pass"

    def test_sox_access_controls(self):
        auditor = ComplianceAuditor(framework="sox")
        auditor.record_access(
            user_id="u1", operation="write", resource="ledger",
            granted=True,
        )
        report = auditor.validate()
        ac = next(f for f in report.findings if f.rule_id == "SOX_ACCESS_CONTROL")
        assert ac.status == "pass"

    def test_sox_retention_policy(self):
        auditor = ComplianceAuditor(framework="sox")
        auditor.record_merge(
            operation="merge", input_hash="h1", output_hash="h2",
            metadata={"retention_days": 2555},
        )
        report = auditor.validate()
        rp = next(f for f in report.findings if f.rule_id == "SOX_RETENTION")
        assert rp.status == "pass"

    def test_sox_no_retention_fails(self):
        auditor = ComplianceAuditor(framework="sox")
        auditor.record_merge(operation="merge", input_hash="h1", output_hash="h2")
        report = auditor.validate()
        rp = next(f for f in report.findings if f.rule_id == "SOX_RETENTION")
        assert rp.status == "fail"


# ===========================================================================
# 6. from_audit_log integration
# ===========================================================================

class TestFromAuditLog:

    def test_from_mock_audit_log(self):
        mock_log = _make_mock_audit_log(n_entries=5)
        auditor = ComplianceAuditor.from_audit_log(mock_log, framework="eu_ai_act")
        assert auditor.node_id == "mock-node"
        assert len(auditor._merge_events) == 5
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)

    def test_from_audit_log_preserves_hashes(self):
        mock_log = _make_mock_audit_log(n_entries=2)
        auditor = ComplianceAuditor.from_audit_log(mock_log)
        assert auditor._merge_events[0]["input_hash"] == "ih_0"
        assert auditor._merge_events[0]["output_hash"] == "oh_0"

    def test_from_audit_log_empty(self):
        mock_log = _make_mock_audit_log(n_entries=0)
        auditor = ComplianceAuditor.from_audit_log(mock_log)
        assert len(auditor._merge_events) == 0

    def test_from_audit_log_different_framework(self):
        mock_log = _make_mock_audit_log(n_entries=3)
        auditor = ComplianceAuditor.from_audit_log(mock_log, framework="gdpr")
        assert auditor.framework == "gdpr"


# ===========================================================================
# 6b. from_provenance_log integration
# ===========================================================================

class TestFromProvenanceLog:

    def test_from_mock_provenance_log(self):
        mock_log = _make_mock_provenance_log(n_records=4)
        auditor = ComplianceAuditor.from_provenance_log(mock_log, framework="eu_ai_act")
        assert len(auditor._merge_events) == 4
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)

    def test_provenance_events_have_metadata(self):
        mock_log = _make_mock_provenance_log(n_records=2)
        auditor = ComplianceAuditor.from_provenance_log(mock_log)
        for event in auditor._merge_events:
            assert event["metadata"]["has_provenance"] is True


# ===========================================================================
# 7. ComplianceReport to_dict / to_text roundtrip
# ===========================================================================

class TestComplianceReportSerialization:

    def test_to_dict(self):
        auditor = _make_auditor_with_merges()
        report = auditor.validate()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["framework"] == "eu_ai_act"
        assert isinstance(d["findings"], list)
        assert len(d["findings"]) > 0
        # Each finding should be a dict
        for f in d["findings"]:
            assert "rule_id" in f
            assert "status" in f

    def test_to_text(self):
        auditor = _make_auditor_with_merges()
        report = auditor.validate()
        text = report.to_text()
        assert isinstance(text, str)
        assert "EU AI ACT" in text
        assert "Summary:" in text

    def test_to_text_contains_findings(self):
        auditor = _make_auditor_with_merges()
        report = auditor.validate()
        text = report.to_text()
        for finding in report.findings:
            assert finding.rule_id in text

    def test_summary(self):
        auditor = _make_auditor_with_merges()
        report = auditor.validate()
        s = report.summary()
        assert s["framework"] == "eu_ai_act"
        assert "passed" in s
        assert "failed" in s
        assert "total_findings" in s
        assert s["total_findings"] == len(report.findings)

    def test_finding_to_dict(self):
        finding = ComplianceFinding(
            rule_id="TEST_001",
            severity="warning",
            status="pass",
            description="Test finding",
            recommendation="Do something",
            evidence={"key": "value"},
        )
        d = finding.to_dict()
        assert d["rule_id"] == "TEST_001"
        assert d["evidence"] == {"key": "value"}


# ===========================================================================
# 8. Empty auditor produces valid report
# ===========================================================================

class TestEmptyAuditor:

    @pytest.mark.parametrize("framework", ["eu_ai_act", "gdpr", "hipaa", "sox"])
    def test_empty_auditor_produces_report(self, framework):
        auditor = ComplianceAuditor(framework=framework)
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)
        assert report.framework == framework
        assert len(report.findings) > 0
        # All findings should have valid statuses
        for f in report.findings:
            assert f.status in ("pass", "fail", "not_applicable")
            assert f.severity in ("critical", "warning", "info")

    @pytest.mark.parametrize("framework", ["eu_ai_act", "gdpr", "hipaa", "sox"])
    def test_empty_auditor_metadata(self, framework):
        auditor = ComplianceAuditor(framework=framework)
        report = auditor.validate()
        assert report.metadata["merge_events"] == 0
        assert report.metadata["unmerge_events"] == 0
        assert report.metadata["access_events"] == 0


# ===========================================================================
# 9. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_none_metadata_in_record_merge(self):
        auditor = ComplianceAuditor(framework="eu_ai_act")
        auditor.record_merge(operation="merge", metadata=None)
        assert auditor._merge_events[0]["metadata"] == {}

    def test_none_metadata_in_record_unmerge(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_unmerge(subject_id="s1", metadata=None)
        assert auditor._unmerge_events[0]["metadata"] == {}

    def test_none_metadata_in_record_access(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_access(
            user_id="u1", operation="read", resource="res",
            granted=False, metadata=None,
        )
        assert auditor._access_events[0]["metadata"] == {}

    def test_none_fields_removed(self):
        auditor = ComplianceAuditor(framework="gdpr")
        auditor.record_unmerge(subject_id="s1", fields_removed=None)
        assert auditor._unmerge_events[0]["fields_removed"] == []

    def test_empty_input_hash(self):
        auditor = ComplianceAuditor(framework="eu_ai_act")
        auditor.record_merge(operation="merge", input_hash="", output_hash="")
        # Should still work — findings may flag missing hashes
        report = auditor.validate()
        assert isinstance(report, ComplianceReport)

    def test_multiple_frameworks_sequential(self):
        """Ensure each framework produces distinct rules."""
        frameworks = ["eu_ai_act", "gdpr", "hipaa", "sox"]
        rule_ids_per_fw: dict = {}
        for fw in frameworks:
            auditor = ComplianceAuditor(framework=fw)
            report = auditor.validate()
            rule_ids_per_fw[fw] = {f.rule_id for f in report.findings}

        # EU AI Act and GDPR should have different rule IDs
        assert rule_ids_per_fw["eu_ai_act"] != rule_ids_per_fw["gdpr"]
        assert rule_ids_per_fw["hipaa"] != rule_ids_per_fw["sox"]

    def test_compliance_report_with_no_findings(self):
        """Manually construct a report with no findings."""
        report = ComplianceReport(
            framework="eu_ai_act",
            generated_at=time.time(),
            status="compliant",
            findings=[],
            metadata={},
        )
        assert report.to_dict()["findings"] == []
        assert "Summary:" in report.to_text()
        s = report.summary()
        assert s["total_findings"] == 0
        assert s["passed"] == 0

    def test_access_denied_events_counted(self):
        auditor = ComplianceAuditor(framework="hipaa")
        auditor.record_access(
            user_id="hacker", operation="write", resource="data",
            granted=False,
        )
        auditor.record_access(
            user_id="nurse", operation="read", resource="data",
            granted=True,
        )
        report = auditor.validate()
        ac = next(f for f in report.findings if f.rule_id == "HIPAA_ACCESS_CONTROL")
        assert ac.status == "pass"
        assert ac.evidence["granted"] == 1
        assert ac.evidence["denied"] == 1

    def test_eu_ai_act_report_preserves_framework(self):
        """EUAIActReport.generate() should restore original framework."""
        auditor = _make_auditor_with_merges(framework="gdpr", count=2)
        eu = EUAIActReport(auditor)
        report = eu.generate()
        # Report is EU AI Act
        assert report.framework == "eu_ai_act"
        # But auditor's framework should be restored
        assert auditor.framework == "gdpr"
