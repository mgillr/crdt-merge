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

"""
Regulatory compliance auditing and reporting for crdt-merge.

Validates merge operations against major compliance frameworks — EU AI Act,
GDPR, HIPAA, and SOX — by inspecting recorded merge, unmerge, and access
events.  Generates structured reports with per-rule findings.

Classes:
    ComplianceFinding: Single rule evaluation result.
    ComplianceReport:  Full compliance report with findings list.
    ComplianceAuditor: Main auditor — records events and validates.
    EUAIActReport:     Specialised EU AI Act report generator.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import logging
import re
import time
import types
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional integration imports — compliance.py works standalone
# ---------------------------------------------------------------------------
# Issue #83: These type: ignore[assignment,misc] comments are intentional.
# Each try/except block imports an optional dependency module. When the import
# fails (e.g., circular import during bootstrapping or missing optional dep),
# the name is set to None so that downstream isinstance() / getattr() checks
# degrade gracefully. Mypy flags the None assignment because it conflicts with
# the class type from the successful import path — this is expected and
# unavoidable without TYPE_CHECKING guards, which would break the runtime
# fallback pattern used here.
# ---------------------------------------------------------------------------

try:
    from .audit import AuditLog, AuditEntry
except Exception:  # pragma: no cover
    AuditLog = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    AuditEntry = None  # type: ignore[assignment,misc]  # fallback: module unavailable

try:
    from .provenance import ProvenanceLog, MergeRecord, MergeDecision
except Exception:  # pragma: no cover
    ProvenanceLog = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    MergeRecord = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    MergeDecision = None  # type: ignore[assignment,misc]  # fallback: module unavailable

try:
    from .unmerge import UnmergeEngine, GDPRForget
except Exception:  # pragma: no cover
    UnmergeEngine = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    GDPRForget = None  # type: ignore[assignment,misc]  # fallback: module unavailable

try:
    from .rbac import RBACController, Permission, Role
except Exception:  # pragma: no cover
    RBACController = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    Permission = None  # type: ignore[assignment,misc]  # fallback: module unavailable
    Role = None  # type: ignore[assignment,misc]  # fallback: module unavailable


__all__ = [
    "CheckResult",
    "ComplianceFinding",
    "ComplianceReport",
    "ComplianceAuditor",
    "EUAIActReport",
    "register_compliance_rule",
]


# ---------------------------------------------------------------------------
# CheckResult — typed return structure for _check_* methods
# ---------------------------------------------------------------------------

class CheckResult(NamedTuple):
    """Typed result from internal compliance check methods.

    Backward-compatible with the previous bare ``(status, evidence)`` tuples.
    """

    passed: str  # "pass", "fail", or "not_applicable"
    message: str
    details: Dict[str, Any]

# ---------------------------------------------------------------------------
# Valid frameworks and severities
# ---------------------------------------------------------------------------

_VALID_FRAMEWORKS = frozenset({"eu_ai_act", "gdpr", "hipaa", "sox"})
_VALID_SEVERITIES = frozenset({"critical", "warning", "info"})
_VALID_STATUSES = frozenset({"pass", "fail", "not_applicable"})

# ---------------------------------------------------------------------------
# Custom compliance rule registry
# ---------------------------------------------------------------------------

from typing import Callable  # noqa: E402 — after type defs

_CUSTOM_RULES: Dict[str, List[Callable[..., "ComplianceFinding"]]] = {}


def register_compliance_rule(
    framework: str,
    rule_fn: Callable[..., "ComplianceFinding"],
) -> None:
    """Register a custom compliance rule for *framework*.

    The callable receives the :class:`ComplianceAuditor` instance as its only
    positional argument and must return a :class:`ComplianceFinding`.

    Parameters
    ----------
    framework : str
        One of ``"eu_ai_act"``, ``"gdpr"``, ``"hipaa"``, ``"sox"``, or any
        custom string for bespoke frameworks.
    rule_fn : callable
        ``(auditor: ComplianceAuditor) -> ComplianceFinding``

    Example
    -------
    .. code-block:: python

        from crdt_merge.compliance import register_compliance_rule, ComplianceFinding

        def my_rule(auditor):
            ok = len(auditor._merge_events) < 1000
            return ComplianceFinding(
                rule_id="CUSTOM_MERGE_LIMIT",
                severity="warning",
                status="pass" if ok else "fail",
                description="Merge event count must be under 1000",
            )

        register_compliance_rule("gdpr", my_rule)
    """
    if not callable(rule_fn):
        raise TypeError("rule_fn must be callable")
    _CUSTOM_RULES.setdefault(framework, []).append(rule_fn)


# ---------------------------------------------------------------------------
# PHI patterns for HIPAA Safe Harbor detection (issue #86)
# ---------------------------------------------------------------------------

_PHI_PATTERNS: Dict[str, re.Pattern] = {
    "name": re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),
    "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "phone": re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'),
    "email": re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
    "date": re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
    "zip": re.compile(r'\b\d{5}(-\d{4})?\b'),
    "mrn": re.compile(r'\bMRN[-:\s]?\d{4,10}\b', re.IGNORECASE),
    "ip": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
}

# ---------------------------------------------------------------------------
# ComplianceFinding
# ---------------------------------------------------------------------------

@dataclass
class ComplianceFinding:
    """Single compliance rule evaluation result.

    Attributes:
        rule_id:        Identifier such as ``"EU_AI_ACT_ART_10"`` or ``"GDPR_ART_17"``.
        severity:       ``"critical"`` | ``"warning"`` | ``"info"``.
        status:         ``"pass"`` | ``"fail"`` | ``"not_applicable"``.
        description:    Human-readable explanation of the rule.
        recommendation: Suggested remediation (empty string if passing).
        evidence:       Supporting data for the finding.
    """

    rule_id: str
    severity: str
    status: str
    description: str
    recommendation: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# ComplianceReport
# ---------------------------------------------------------------------------

@dataclass
class ComplianceReport:
    """Full compliance report for a specific framework.

    Attributes:
        framework:    One of ``'eu_ai_act'``, ``'gdpr'``, ``'hipaa'``, ``'sox'``.
        generated_at: Unix timestamp of report generation.
        status:       ``'compliant'`` | ``'non_compliant'`` | ``'partial'``.
        findings:     Individual rule evaluation results.
        metadata:     Extra contextual information.
    """

    framework: str
    generated_at: float
    status: str
    findings: List[ComplianceFinding]
    metadata: Dict[str, Any] = field(default_factory=dict)
    _signature: Optional[str] = field(default=None, init=False, repr=False, compare=False)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "framework": self.framework,
            "generated_at": self.generated_at,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "metadata": self.metadata,
        }
        if self._signature is not None:
            d["signature"] = self._signature
        return d

    def to_text(self) -> str:
        """Human-readable summary report."""
        lines: List[str] = [
            f"Compliance Report — {self.framework.upper().replace('_', ' ')}",
            "=" * 60,
            f"Status:       {self.status}",
            f"Generated at: {self.generated_at}",
            f"Findings:     {len(self.findings)}",
            "",
        ]

        for finding in self.findings:
            icon = {"pass": "", "fail": "", "not_applicable": "—"}.get(
                finding.status, "?"
            )
            lines.append(
                f"  [{icon}] {finding.rule_id} ({finding.severity}): "
                f"{finding.description}"
            )
            if finding.recommendation:
                lines.append(f"      → {finding.recommendation}")

        # Summary counts
        pass_count = sum(1 for f in self.findings if f.status == "pass")
        fail_count = sum(1 for f in self.findings if f.status == "fail")
        na_count = sum(1 for f in self.findings if f.status == "not_applicable")
        lines.append("")
        lines.append(f"Summary: {pass_count} passed, {fail_count} failed, {na_count} n/a")

        return "\n".join(lines)

    def summary(self) -> Dict[str, Any]:
        """Quick status overview."""
        pass_count = sum(1 for f in self.findings if f.status == "pass")
        fail_count = sum(1 for f in self.findings if f.status == "fail")
        na_count = sum(1 for f in self.findings if f.status == "not_applicable")
        critical_fails = sum(
            1
            for f in self.findings
            if f.status == "fail" and f.severity == "critical"
        )
        return {
            "framework": self.framework,
            "status": self.status,
            "total_findings": len(self.findings),
            "passed": pass_count,
            "failed": fail_count,
            "not_applicable": na_count,
            "critical_failures": critical_fails,
        }

    # -- signing -------------------------------------------------------------

    def sign(self, key: bytes) -> str:
        """Compute an HMAC-SHA256 signature over the report content.

        The signature is computed over ``json.dumps(self.to_dict(),
        sort_keys=True)`` *before* the signature field is included, providing
        a stable payload regardless of serialisation order.

        Parameters
        ----------
        key : bytes
            Secret key for the HMAC computation.

        Returns
        -------
        str
            Hexadecimal HMAC-SHA256 digest.  The digest is also stored on
            ``self._signature`` so that subsequent calls to :meth:`to_dict`
            include it.
        """
        # Temporarily clear any existing signature to get a canonical payload
        saved = self._signature
        object.__setattr__(self, "_signature", None)
        try:
            payload = json.dumps(self.to_dict(), sort_keys=True).encode()
        finally:
            object.__setattr__(self, "_signature", saved)
        sig = hmac.new(key, payload, hashlib.sha256).hexdigest()
        object.__setattr__(self, "_signature", sig)
        return sig

    def verify(self, key: bytes, signature: str) -> bool:
        """Verify a previously computed HMAC-SHA256 signature.

        Uses :func:`hmac.compare_digest` to prevent timing attacks.

        Parameters
        ----------
        key : bytes
            Secret key used when the signature was created.
        signature : str
            Hexadecimal digest to verify.

        Returns
        -------
        bool
            ``True`` if *signature* matches the recomputed digest.
        """
        expected = self.sign(key)
        return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Framework validation rules (internal)
# ---------------------------------------------------------------------------

_FRAMEWORK_RULES: types.MappingProxyType = types.MappingProxyType({
    "eu_ai_act": [
        {
            "rule_id": "EU_AI_ACT_ART_10",
            "severity": "critical",
            "description": "Data governance — provenance and quality documentation for training/merge data.",
            "check": "has_merge_provenance",
            "recommendation": "Record provenance metadata for all merge operations.",
        },
        {
            "rule_id": "EU_AI_ACT_ART_12",
            "severity": "critical",
            "description": "Record-keeping — automatic logging of system operations.",
            "check": "has_audit_trail",
            "recommendation": "Enable audit logging for all merge and data operations.",
        },
        {
            "rule_id": "EU_AI_ACT_ART_13",
            "severity": "warning",
            "description": "Transparency — system outputs must be interpretable and documented.",
            "check": "has_transparency_metadata",
            "recommendation": "Include descriptive metadata with merge operations.",
        },
        {
            "rule_id": "EU_AI_ACT_ART_14",
            "severity": "warning",
            "description": "Human oversight — documentation of human review processes.",
            "check": "has_human_oversight",
            "recommendation": "Document human oversight procedures for high-risk operations.",
        },
        {
            "rule_id": "EU_AI_ACT_ART_9",
            "severity": "info",
            "description": "Risk management — system risk classification documentation.",
            "check": "has_risk_classification",
            "recommendation": "Classify the system per Art. 6 risk categories.",
        },
    ],
    "gdpr": [
        {
            "rule_id": "GDPR_ART_17",
            "severity": "critical",
            "description": "Right to erasure — ability to remove personal data on request.",
            "check": "has_unmerge_capability",
            "recommendation": "Implement unmerge/forget operations for data subject requests.",
        },
        {
            "rule_id": "GDPR_ART_30",
            "severity": "critical",
            "description": "Records of processing activities — documented data processing log.",
            "check": "has_processing_records",
            "recommendation": "Maintain records of all data processing (merge) activities.",
        },
        {
            "rule_id": "GDPR_ART_7",
            "severity": "warning",
            "description": "Consent tracking — evidence of lawful basis for processing.",
            "check": "has_consent_tracking",
            "recommendation": "Record consent or lawful basis for each data processing operation.",
        },
        {
            "rule_id": "GDPR_ART_25",
            "severity": "info",
            "description": "Data protection by design — privacy safeguards in system architecture.",
            "check": "has_data_protection_design",
            "recommendation": "Document data protection measures in system design.",
        },
    ],
    "hipaa": [
        {
            "rule_id": "HIPAA_ACCESS_CONTROL",
            "severity": "critical",
            "description": "Access controls — role-based access to protected health information.",
            "check": "has_access_controls",
            "recommendation": "Implement RBAC for all data access operations.",
        },
        {
            "rule_id": "HIPAA_AUDIT_TRAIL",
            "severity": "critical",
            "description": "Audit trail — immutable log of all access and modifications.",
            "check": "has_audit_trail",
            "recommendation": "Enable tamper-evident audit logging.",
        },
        {
            "rule_id": "HIPAA_ENCRYPTION",
            "severity": "critical",
            "description": "Encryption — data at rest and in transit must be encrypted.",
            "check": "has_encryption",
            "recommendation": "Enable encryption for data storage and transmission.",
        },
        {
            "rule_id": "HIPAA_INTEGRITY",
            "severity": "warning",
            "description": "Data integrity — mechanisms to ensure data is not improperly altered.",
            "check": "has_data_integrity",
            "recommendation": "Use hash-chained audit logs to verify data integrity.",
        },
    ],
    "sox": [
        {
            "rule_id": "SOX_DATA_INTEGRITY",
            "severity": "critical",
            "description": "Data integrity verification — cryptographic proof of data consistency.",
            "check": "has_data_integrity",
            "recommendation": "Use hash-chained audit logs for data integrity verification.",
        },
        {
            "rule_id": "SOX_CHANGE_MGMT",
            "severity": "critical",
            "description": "Change management audit trail — all changes logged with attribution.",
            "check": "has_change_management",
            "recommendation": "Log all data changes with user/node attribution.",
        },
        {
            "rule_id": "SOX_ACCESS_CONTROL",
            "severity": "critical",
            "description": "Access controls — segregation of duties and role-based access.",
            "check": "has_access_controls",
            "recommendation": "Implement RBAC with segregation of duties.",
        },
        {
            "rule_id": "SOX_RETENTION",
            "severity": "warning",
            "description": "Data retention — audit logs retained for required period.",
            "check": "has_retention_policy",
            "recommendation": "Define and enforce audit log retention policies.",
        },
    ],
})


# ---------------------------------------------------------------------------
# Built-in compliance rules — GDPR Art. 5, HIPAA PHI, SOX controls
# ---------------------------------------------------------------------------
# These rules are registered at module import time via register_compliance_rule().
# They supplement the structural checks in _FRAMEWORK_RULES with data-level
# and control-flow checks.  They are intentionally not exhaustive — see the
# individual rule docstrings for the specific clause addressed.
# ---------------------------------------------------------------------------


def _gdpr_data_minimisation_rule(auditor: "ComplianceAuditor") -> "ComplianceFinding":
    """GDPR Art. 5(1)(c) — Data minimisation built-in check.

    Addresses: GDPR Article 5(1)(c) — personal data shall be adequate, relevant
    and limited to what is necessary in relation to the purposes for which they
    are processed.

    Note: This check is not exhaustive.  It flags fields present in the merge
    output that were absent from all input schemas, which may indicate that
    extra data was introduced during the merge.  A full data-minimisation
    assessment requires legal and contextual review beyond automated checks.
    """
    output = auditor._merge_output_data
    schemas = auditor._input_schemas

    if output is None:
        return ComplianceFinding(
            rule_id="GDPR_ART_5_1_C_DATA_MINIMISATION",
            severity="warning",
            status="not_applicable",
            description=(
                "GDPR Art. 5(1)(c) — Data minimisation: no merge output data "
                "registered for inspection. Call record_merge_data() before validate()."
            ),
        )

    # Build union of all field names present in any input schema
    input_fields: set = set()
    for schema in schemas:
        if isinstance(schema, dict):
            input_fields.update(schema.keys())

    extra_fields = [f for f in output.keys() if f not in input_fields] if input_fields else []

    findings_list: List[str] = []
    for field_name in extra_fields:
        findings_list.append(field_name)

    if findings_list:
        # Return one finding per extra field — represented as a single finding
        # with evidence listing all offending fields, to keep the API simple.
        return ComplianceFinding(
            rule_id="GDPR_ART_5_1_C_DATA_MINIMISATION",
            severity="warning",
            status="fail",
            description=(
                "GDPR Art. 5(1)(c) — Data minimisation: one or more fields in the "
                "merge output were not present in any input schema. "
                "May indicate data minimisation violation (GDPR Art. 5(1)(c)). "
                "Fields: " + ", ".join(
                    f"'{f}'" for f in findings_list
                )
            ),
            recommendation=(
                "Review extra fields and remove any that are not necessary for "
                "the stated processing purpose."
            ),
            evidence={"extra_fields": findings_list},
        )

    return ComplianceFinding(
        rule_id="GDPR_ART_5_1_C_DATA_MINIMISATION",
        severity="warning",
        status="pass",
        description=(
            "GDPR Art. 5(1)(c) — Data minimisation: all output fields were "
            "present in at least one input schema."
        ),
        evidence={"output_field_count": len(output)},
    )


def _gdpr_storage_limitation_rule(auditor: "ComplianceAuditor") -> "ComplianceFinding":
    """GDPR Art. 5(1)(e) — Storage limitation built-in check.

    Addresses: GDPR Article 5(1)(e) — personal data shall be kept in a form
    which permits identification of data subjects for no longer than is necessary
    for the purposes for which the personal data are processed.

    Note: This check is not exhaustive.  The presence of a TTL/expiry field is
    a necessary but not sufficient condition for compliance.  Legal review of
    retention periods is required.
    """
    output = auditor._merge_output_data

    if output is None:
        return ComplianceFinding(
            rule_id="GDPR_ART_5_1_E_STORAGE_LIMITATION",
            severity="warning",
            status="not_applicable",
            description=(
                "GDPR Art. 5(1)(e) — Storage limitation: no merge output data "
                "registered for inspection. Call record_merge_data() before validate()."
            ),
        )

    _TTL_FIELD_NAMES = frozenset({
        "ttl", "expiry", "expires_at", "expire_at", "expiration",
        "expiration_date", "expires", "valid_until", "delete_after",
        "retention_days", "retention_until",
    })

    has_ttl = any(k.lower() in _TTL_FIELD_NAMES for k in output.keys())

    if not has_ttl:
        return ComplianceFinding(
            rule_id="GDPR_ART_5_1_E_STORAGE_LIMITATION",
            severity="warning",
            status="fail",
            description=(
                "No expiry/TTL field found in merged records. "
                "May indicate storage limitation concern (GDPR Art. 5(1)(e))."
            ),
            recommendation=(
                "Add a TTL or expiry field to merged records and enforce "
                "automated deletion when the retention period elapses."
            ),
            evidence={"output_fields": list(output.keys())},
        )

    return ComplianceFinding(
        rule_id="GDPR_ART_5_1_E_STORAGE_LIMITATION",
        severity="warning",
        status="pass",
        description=(
            "GDPR Art. 5(1)(e) — Storage limitation: merged record contains "
            "a TTL/expiry field."
        ),
        evidence={
            "ttl_fields": [k for k in output.keys() if k.lower() in _TTL_FIELD_NAMES]
        },
    )


def _hipaa_phi_detection_rule(auditor: "ComplianceAuditor") -> "ComplianceFinding":
    """HIPAA Safe Harbor PHI detection built-in check.

    Addresses: HIPAA Privacy Rule Safe Harbor method (45 CFR §164.514(b)) —
    detection of the 18 categories of identifiers that must be removed for
    de-identification.

    Note: This check is not exhaustive.  It samples up to 100 values per field
    and applies regex heuristics.  It may produce false positives (e.g., zip
    codes matching non-PHI numeric strings).  A full HIPAA de-identification
    assessment requires expert review under the Expert Determination or Safe
    Harbor method.

    PHI values are NEVER logged — only field names and identifier types are
    included in findings.
    """
    output = auditor._merge_output_data

    if output is None:
        return ComplianceFinding(
            rule_id="HIPAA_PHI_DETECTION",
            severity="critical",
            status="not_applicable",
            description=(
                "HIPAA PHI detection: no merge output data registered for "
                "inspection. Call record_merge_data() before validate()."
            ),
        )

    detected: Dict[str, List[str]] = {}  # field_name -> [phi_type, ...]

    for field_name, value in output.items():
        field_lower = field_name.lower()
        # Collect up to 100 string values to sample
        if isinstance(value, list):
            samples = [str(v) for v in value[:100] if v is not None]
        else:
            samples = [str(value)] if value is not None else []

        phi_types_found: List[str] = []

        # Check field name against PHI pattern keys
        for phi_type in _PHI_PATTERNS:
            if phi_type in field_lower:
                phi_types_found.append(phi_type)

        # Check sampled values against all patterns
        for sample in samples:
            for phi_type, pattern in _PHI_PATTERNS.items():
                if phi_type not in phi_types_found and pattern.search(sample):
                    phi_types_found.append(phi_type)

        if phi_types_found:
            detected[field_name] = phi_types_found

    if detected:
        return ComplianceFinding(
            rule_id="HIPAA_PHI_DETECTION",
            severity="critical",
            status="fail",
            description=(
                "Potential PHI detected in merged output. "
                "Sampled detection (up to 100 values per field) — not exhaustive. "
                "Fields with potential PHI: "
                + ", ".join(
                    f"'{f}' ({', '.join(types)})"
                    for f, types in detected.items()
                )
            ),
            recommendation=(
                "Review flagged fields and apply HIPAA Safe Harbor de-identification "
                "before storing or transmitting this data."
            ),
            # Only field names and PHI types — no actual values are included
            evidence={
                "phi_fields": {f: types for f, types in detected.items()},
                "note": "Sampled detection (up to 100 values per field) — not exhaustive.",
            },
        )

    return ComplianceFinding(
        rule_id="HIPAA_PHI_DETECTION",
        severity="critical",
        status="pass",
        description=(
            "HIPAA PHI detection: no obvious PHI identifiers detected in sampled "
            "merge output fields. "
            "Sampled detection (up to 100 values per field) — not exhaustive."
        ),
        evidence={"fields_scanned": list(output.keys())},
    )


def _sox_audit_trail_integrity_rule(auditor: "ComplianceAuditor") -> "ComplianceFinding":
    """SOX IT General Control — Change Management: audit trail integrity check.

    Addresses: SOX Section 404 IT General Control — Change Management.
    Calls AuditLog.verify_chain() to confirm the immutable hash-chain has not
    been tampered with.  Flags if the chain is broken or if no AuditLog is
    provided.

    Note: This check is not exhaustive.  Audit trail integrity is one component
    of SOX IT General Controls; a full assessment requires additional review.
    """
    audit_log = auditor._audit_log

    if audit_log is None:
        return ComplianceFinding(
            rule_id="SOX_AUDIT_TRAIL_INTEGRITY",
            severity="critical",
            status="fail",
            description=(
                "No AuditLog provided. SOX IT General Control — Change Management "
                "requires audit log for all merge operations."
            ),
            recommendation=(
                "Pass an AuditLog instance to ComplianceAuditor(audit_log=...) "
                "or ComplianceAuditor.from_audit_log()."
            ),
            evidence={"audit_log_present": False},
        )

    chain_ok: bool
    try:
        chain_ok = bool(audit_log.verify_chain())
    except Exception as exc:
        chain_ok = False
        logger.warning("AuditLog.verify_chain() raised an exception: %s", exc)

    if not chain_ok:
        return ComplianceFinding(
            rule_id="SOX_AUDIT_TRAIL_INTEGRITY",
            severity="critical",
            status="fail",
            description=(
                "AuditLog chain integrity failure. SOX IT General Control — "
                "Change Management requires complete audit trail."
            ),
            recommendation=(
                "Investigate and repair the audit log hash chain. "
                "Do not rely on this log for compliance evidence until repaired."
            ),
            evidence={"chain_valid": False},
        )

    return ComplianceFinding(
        rule_id="SOX_AUDIT_TRAIL_INTEGRITY",
        severity="critical",
        status="pass",
        description=(
            "SOX IT General Control — Change Management: AuditLog chain "
            "integrity verified."
        ),
        evidence={"chain_valid": True},
    )


def _sox_merge_authorization_rule(auditor: "ComplianceAuditor") -> "ComplianceFinding":
    """SOX IT General Control — Separation of Duties: merge authorisation check.

    Addresses: SOX Section 404 IT General Control — Separation of Duties.
    Checks that an RBAC policy exists for the merging node, ensuring that merge
    operations are performed only by authorised principals.

    Note: This check is not exhaustive.  The existence of an RBAC policy entry
    is a necessary but not sufficient condition for separation of duties.
    """
    rbac = auditor._rbac
    node = auditor.node_id

    if rbac is None:
        return ComplianceFinding(
            rule_id="SOX_MERGE_AUTHORIZATION",
            severity="critical",
            status="fail",
            description=(
                f"No RBAC policy found for node '{node}'. "
                "SOX IT General Control — Separation of Duties requires "
                "documented authorization."
            ),
            recommendation=(
                "Pass an RBACController instance to ComplianceAuditor(rbac=...) "
                "and define a policy for this node."
            ),
            evidence={"rbac_present": False, "node": node},
        )

    policy = None
    try:
        policy = rbac.get_policy(node)
    except Exception as exc:
        logger.warning("RBACController.get_policy() raised an exception: %s", exc)

    if policy is None:
        return ComplianceFinding(
            rule_id="SOX_MERGE_AUTHORIZATION",
            severity="critical",
            status="fail",
            description=(
                f"No RBAC policy found for node '{node}'. "
                "SOX IT General Control — Separation of Duties requires "
                "documented authorization."
            ),
            recommendation=(
                f"Define an RBAC policy for node '{node}' in the RBACController."
            ),
            evidence={"rbac_present": True, "node": node, "policy_found": False},
        )

    return ComplianceFinding(
        rule_id="SOX_MERGE_AUTHORIZATION",
        severity="critical",
        status="pass",
        description=(
            f"SOX IT General Control — Separation of Duties: RBAC policy "
            f"found for node '{node}'."
        ),
        evidence={"node": node, "policy_found": True},
    )


# Register built-in rules at module import time.
# GDPR Art. 5 — data minimisation and storage limitation
register_compliance_rule("gdpr", _gdpr_data_minimisation_rule)
register_compliance_rule("gdpr", _gdpr_storage_limitation_rule)
# HIPAA PHI detection (Safe Harbor identifiers)
register_compliance_rule("hipaa", _hipaa_phi_detection_rule)
# SOX IT General Controls — Change Management and Separation of Duties
register_compliance_rule("sox", _sox_audit_trail_integrity_rule)
register_compliance_rule("sox", _sox_merge_authorization_rule)


# ---------------------------------------------------------------------------
# ComplianceAuditor
# ---------------------------------------------------------------------------

class ComplianceAuditor:
    """Main compliance auditor — records events and validates against frameworks.

    Parameters:
        framework:  Target compliance framework (default ``'eu_ai_act'``).
        node_id:    Identifier of the node being audited.
        audit_log:  Optional :class:`AuditLog` instance for SOX chain-integrity
                    checks and subject lineage queries.  Not stored as PII —
                    only used for structural integrity checks.
        rbac:       Optional :class:`RBACController` for SOX separation-of-duties
                    checks.
    """

    def __init__(
        self,
        framework: str = "eu_ai_act",
        node_id: str = "default",
        audit_log: Any = None,
        rbac: Any = None,
    ) -> None:
        if framework not in _VALID_FRAMEWORKS:
            raise ValueError(
                f"Unknown framework '{framework}'. "
                f"Supported: {sorted(_VALID_FRAMEWORKS)}"
            )
        self.framework = framework
        self.node_id = node_id

        # Optional integrations for SOX checks (no logic duplicated)
        self._audit_log: Any = audit_log
        self._rbac: Any = rbac

        # Event stores
        self._merge_events: List[Dict[str, Any]] = []
        self._unmerge_events: List[Dict[str, Any]] = []
        self._access_events: List[Dict[str, Any]] = []

        # Optional merge-output data for GDPR/HIPAA data-level checks.
        # Set via record_merge_data(); never persisted beyond the auditor lifetime.
        self._merge_output_data: Optional[Dict[str, Any]] = None
        self._input_schemas: List[Dict[str, Any]] = []

    # -- recording -----------------------------------------------------------

    def record_merge(
        self,
        operation: str,
        input_hash: str = "",
        output_hash: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a merge event."""
        self._merge_events.append({
            "operation": operation,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })

    def record_unmerge(
        self,
        subject_id: str,
        fields_removed: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an unmerge / forget event."""
        self._unmerge_events.append({
            "subject_id": subject_id,
            "fields_removed": fields_removed or [],
            "metadata": metadata or {},
            "timestamp": time.time(),
        })

    def record_merge_data(
        self,
        output: Dict[str, Any],
        input_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Record the raw output and input schemas for data-level compliance checks.

        Used by GDPR data-minimisation (Art. 5(1)(c)) and HIPAA PHI-detection
        rules.  The data is held only in memory for the lifetime of this auditor
        instance and is never written to disk or any external log.

        Parameters
        ----------
        output : dict
            The merged output record to inspect.
        input_schemas : list of dict, optional
            Field-name sets (or full schema dicts) from each input record.
            Used to detect fields in the output that were absent from all inputs.
        """
        self._merge_output_data = output
        self._input_schemas = list(input_schemas or [])

    def record_access(
        self,
        user_id: str,
        operation: str,
        resource: str,
        granted: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an access control event."""
        self._access_events.append({
            "user_id": user_id,
            "operation": operation,
            "resource": resource,
            "granted": granted,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })

    # -- validation ----------------------------------------------------------

    def validate(self) -> ComplianceReport:
        """Validate all recorded events against the framework rules.

        Returns a :class:`ComplianceReport` with per-rule findings.
        """
        rules = _FRAMEWORK_RULES.get(self.framework, [])
        findings: List[ComplianceFinding] = []

        for rule in rules:
            check_name = rule["check"]
            checker = getattr(self, f"_check_{check_name}", None)
            if checker is not None:
                result = checker()
                status = result.passed
                evidence = result.details
            else:
                status = "not_applicable"
                evidence = {"reason": f"No checker implemented for '{check_name}'"}

            recommendation = rule.get("recommendation", "") if status == "fail" else ""

            findings.append(ComplianceFinding(
                rule_id=rule["rule_id"],
                severity=rule["severity"],
                status=status,
                description=rule["description"],
                recommendation=recommendation,
                evidence=evidence,
            ))

        # Run custom rules registered for this framework
        for custom_fn in _CUSTOM_RULES.get(self.framework, []):
            try:
                finding = custom_fn(self)
                if isinstance(finding, ComplianceFinding):
                    findings.append(finding)
            except Exception as exc:  # pragma: no cover
                logger.warning("Custom compliance rule raised an error: %s", exc)

        # Derive overall status
        has_critical_fail = any(
            f.status == "fail" and f.severity == "critical" for f in findings
        )
        has_any_fail = any(f.status == "fail" for f in findings)

        if has_critical_fail:
            overall_status = "non_compliant"
        elif has_any_fail:
            overall_status = "partial"
        else:
            overall_status = "compliant"

        return ComplianceReport(
            framework=self.framework,
            generated_at=time.time(),
            status=overall_status,
            findings=findings,
            metadata={
                "node_id": self.node_id,
                "merge_events": len(self._merge_events),
                "unmerge_events": len(self._unmerge_events),
                "access_events": len(self._access_events),
            },
        )

    def generate_report(self) -> ComplianceReport:
        """Alias for :meth:`validate`."""
        return self.validate()

    # -- class methods -------------------------------------------------------

    @classmethod
    def from_audit_log(
        cls, audit_log: Any, framework: str = "eu_ai_act"
    ) -> ComplianceAuditor:
        """Create a :class:`ComplianceAuditor` pre-populated from an :class:`AuditLog`.

        Iterates over the audit log's entries and records them as merge events.
        """
        node_id = getattr(audit_log, "node_id", "default")
        auditor = cls(framework=framework, node_id=node_id)

        entries = []
        if hasattr(audit_log, "entries"):
            entries = audit_log.entries
        elif hasattr(audit_log, "__iter__"):
            entries = list(audit_log)

        _expected_fields = {
            "operation": "unknown",
            "input_hash": "",
            "output_hash": "",
            "metadata": {},
        }

        for entry in entries:
            missing_fields: List[str] = []
            values: Dict[str, Any] = {}
            for field_name, default in _expected_fields.items():
                value = getattr(entry, field_name, None)
                if value is None:
                    missing_fields.append(field_name)
                    value = default
                values[field_name] = value

            if missing_fields:
                warnings.warn(
                    f"Audit log entry missing fields: {missing_fields!r}; "
                    f"defaults applied.",
                    stacklevel=2,
                )
                logger.warning(
                    "Audit log entry missing fields: %r — defaults applied",
                    missing_fields,
                )

            metadata = values["metadata"]
            auditor.record_merge(
                operation=values["operation"],
                input_hash=values["input_hash"],
                output_hash=values["output_hash"],
                metadata=metadata if isinstance(metadata, dict) else {},
            )

        return auditor

    @classmethod
    def from_provenance_log(
        cls, provenance_log: Any, framework: str = "eu_ai_act"
    ) -> ComplianceAuditor:
        """Create a :class:`ComplianceAuditor` pre-populated from a :class:`ProvenanceLog`.

        Iterates over the provenance log's records and records them as merge
        events with provenance metadata.
        """
        auditor = cls(framework=framework, node_id="default")

        records: List[Any] = []
        if hasattr(provenance_log, "records"):
            records = provenance_log.records
        elif hasattr(provenance_log, "__iter__"):
            records = list(provenance_log)

        for record in records:
            key = getattr(record, "key", None)
            origin = getattr(record, "origin", "unknown")
            conflict_count = getattr(record, "conflict_count", 0)
            auditor.record_merge(
                operation="merge",
                input_hash="",
                output_hash="",
                metadata={
                    "key": str(key) if key is not None else "",
                    "origin": origin,
                    "conflict_count": conflict_count,
                    "has_provenance": True,
                },
            )

        return auditor

    # -- reset ---------------------------------------------------------------

    def clear(self) -> None:
        """Reset all recorded events."""
        self._merge_events.clear()
        self._unmerge_events.clear()
        self._access_events.clear()

    # -- data lineage --------------------------------------------------------

    def trace_subject(self, subject_id: str, audit_log: Any) -> List[Any]:
        """Query the AuditLog for all merge operations referencing *subject_id*.

        Searches :attr:`AuditLog.entries` for entries whose ``metadata``
        contains a reference to a hash of *subject_id*.  Only hash-based
        references are inspected — raw PII values are never stored or compared.

        Pre-condition: Callers must use ``AuditLog.log_merge()`` with
        subject-tagged input hashes so that the hash of *subject_id* appears in
        ``entry.metadata``.  Without subject-tagged hashes in the log this
        method will return an empty list.

        Parameters
        ----------
        subject_id : str
            Data-subject identifier to trace.  Only its SHA-256 hash is used
            during comparison — the value itself is never logged or stored.
        audit_log : AuditLog
            The audit log to search.

        Returns
        -------
        List[AuditEntry]
            Audit entries whose metadata references the subject's hash.
        """
        subject_hash = hashlib.sha256(subject_id.encode()).hexdigest()
        results: List[Any] = []

        entries: List[Any] = []
        if hasattr(audit_log, "entries"):
            entries = audit_log.entries
        elif hasattr(audit_log, "__iter__"):
            entries = list(audit_log)

        for entry in entries:
            meta = getattr(entry, "metadata", {}) or {}
            # Search all metadata values for the subject hash
            if any(
                subject_hash in str(v)
                for v in meta.values()
            ):
                results.append(entry)

        return results

    # -- internal checks -----------------------------------------------------

    def _check_has_merge_provenance(self) -> CheckResult:
        """Check if merge events contain provenance metadata."""
        if not self._merge_events:
            return CheckResult(passed="fail", message="No merge events recorded.", details={"reason": "No merge events recorded."})

        with_provenance = sum(
            1
            for e in self._merge_events
            if e.get("metadata", {}).get("has_provenance")
            or e.get("input_hash")
            or e.get("output_hash")
        )
        total = len(self._merge_events)

        if with_provenance == total:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_provenance": with_provenance, "total": total})
        elif with_provenance > 0:
            return CheckResult(passed="fail", message="Not all merge events have provenance.", details={
                "events_with_provenance": with_provenance,
                "total": total,
                "reason": "Not all merge events have provenance.",
            })
        else:
            return CheckResult(passed="fail", message="No merge events have provenance data.", details={"reason": "No merge events have provenance data."})

    def _check_has_audit_trail(self) -> CheckResult:
        """Check if there is an audit trail (merge events with hashes)."""
        if not self._merge_events:
            return CheckResult(passed="fail", message="No merge events recorded.", details={"reason": "No merge events recorded."})

        with_hashes = sum(
            1
            for e in self._merge_events
            if e.get("input_hash") or e.get("output_hash")
        )
        total = len(self._merge_events)

        if with_hashes == total:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_hashes": with_hashes, "total": total})
        elif with_hashes > 0:
            return CheckResult(passed="fail", message="Not all events have audit hashes.", details={
                "events_with_hashes": with_hashes,
                "total": total,
                "reason": "Not all events have audit hashes.",
            })
        else:
            # Even without hashes, having events logged counts as partial
            return CheckResult(passed="fail", message="Merge events recorded but lack cryptographic hashes.", details={
                "total": total,
                "reason": "Merge events recorded but lack cryptographic hashes.",
            })

    def _check_has_transparency_metadata(self) -> CheckResult:
        """Check if merge events contain descriptive metadata."""
        if not self._merge_events:
            return CheckResult(passed="fail", message="No merge events recorded.", details={"reason": "No merge events recorded."})

        with_metadata = sum(
            1
            for e in self._merge_events
            if e.get("metadata") and len(e["metadata"]) > 0
        )
        total = len(self._merge_events)

        if with_metadata >= total * 0.5:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_metadata": with_metadata, "total": total})
        return CheckResult(passed="fail", message="Insufficient metadata for transparency requirements.", details={
            "events_with_metadata": with_metadata,
            "total": total,
            "reason": "Insufficient metadata for transparency requirements.",
        })

    def _check_has_human_oversight(self) -> CheckResult:
        """Check for evidence of human oversight in metadata."""
        oversight_keywords = {"reviewed", "approved", "human_oversight", "reviewer"}
        found = 0
        for event in self._merge_events:
            meta = event.get("metadata", {})
            if any(k in meta for k in oversight_keywords):
                found += 1

        if found > 0:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_oversight": found})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No merge events to check.", details={"reason": "No merge events to check."})
        return CheckResult(passed="fail", message="No evidence of human oversight in merge metadata.", details={"reason": "No evidence of human oversight in merge metadata."})

    def _check_has_risk_classification(self) -> CheckResult:
        """Check for risk classification metadata."""
        for event in self._merge_events:
            meta = event.get("metadata", {})
            if "risk_level" in meta or "risk_classification" in meta:
                return CheckResult(passed="pass", message="Check passed", details={"risk_documented": True})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No merge events to check.", details={"reason": "No merge events to check."})
        return CheckResult(passed="fail", message="No risk classification documented.", details={"reason": "No risk classification documented."})

    def _check_has_unmerge_capability(self) -> CheckResult:
        """Check if unmerge / erasure capability has been exercised or recorded."""
        if self._unmerge_events:
            return CheckResult(passed="pass", message="Check passed", details={
                "unmerge_events": len(self._unmerge_events),
                "subjects": [e["subject_id"] for e in self._unmerge_events],
            })
        # Even without exercised events, check if merge events reference provenance
        has_provenance = any(
            e.get("metadata", {}).get("has_provenance")
            for e in self._merge_events
        )
        if has_provenance:
            return CheckResult(passed="pass", message="Provenance-tracked merges enable unmerge capability.", details={
                "reason": "Provenance-tracked merges enable unmerge capability."
            })
        return CheckResult(passed="fail", message="No unmerge events recorded and no provenance tracking.", details={"reason": "No unmerge events recorded and no provenance tracking."})

    def _check_has_processing_records(self) -> CheckResult:
        """Check if data processing (merge) activities are recorded."""
        if self._merge_events:
            return CheckResult(passed="pass", message="Check passed", details={"merge_events": len(self._merge_events)})
        return CheckResult(passed="fail", message="No data processing records found.", details={"reason": "No data processing records found."})

    def _check_has_consent_tracking(self) -> CheckResult:
        """Check for consent / lawful basis metadata."""
        consent_keywords = {"consent", "lawful_basis", "legal_basis", "consent_id"}
        found = 0
        for event in self._merge_events:
            meta = event.get("metadata", {})
            if any(k in meta for k in consent_keywords):
                found += 1

        if found > 0:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_consent": found})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No merge events to check.", details={"reason": "No merge events to check."})
        return CheckResult(passed="fail", message="No consent or lawful basis recorded.", details={"reason": "No consent or lawful basis recorded."})

    def _check_has_data_protection_design(self) -> CheckResult:
        """Check for data protection by design evidence."""
        # Pass if encryption events or access controls exist
        if self._access_events:
            return CheckResult(passed="pass", message="Check passed", details={"access_controls_present": True})
        encryption_events = sum(
            1
            for e in self._merge_events
            if e.get("operation") in ("encrypt", "decrypt")
            or e.get("metadata", {}).get("encrypted")
        )
        if encryption_events > 0:
            return CheckResult(passed="pass", message="Check passed", details={"encryption_events": encryption_events})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No events to check.", details={"reason": "No events to check."})
        return CheckResult(passed="fail", message="No data protection measures documented.", details={"reason": "No data protection measures documented."})

    def _check_has_access_controls(self) -> CheckResult:
        """Check if access control events have been recorded."""
        if self._access_events:
            granted = sum(1 for e in self._access_events if e["granted"])
            denied = sum(1 for e in self._access_events if not e["granted"])
            return CheckResult(passed="pass", message="Check passed", details={
                "total_access_events": len(self._access_events),
                "granted": granted,
                "denied": denied,
            })
        return CheckResult(passed="fail", message="No access control events recorded.", details={"reason": "No access control events recorded."})

    def _check_has_encryption(self) -> CheckResult:
        """Check for encryption usage evidence."""
        encryption_events = sum(
            1
            for e in self._merge_events
            if e.get("operation") in ("encrypt", "decrypt")
            or e.get("metadata", {}).get("encrypted")
        )
        if encryption_events > 0:
            return CheckResult(passed="pass", message="Check passed", details={"encryption_events": encryption_events})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No events to check.", details={"reason": "No events to check."})
        return CheckResult(passed="fail", message="No encryption usage evidence found.", details={"reason": "No encryption usage evidence found."})

    def _check_has_data_integrity(self) -> CheckResult:
        """Check for cryptographic integrity verification."""
        with_hashes = sum(
            1
            for e in self._merge_events
            if e.get("input_hash") and e.get("output_hash")
        )
        if with_hashes > 0:
            return CheckResult(passed="pass", message="Check passed", details={"events_with_integrity_hashes": with_hashes})
        if self._merge_events:
            return CheckResult(passed="fail", message="Merge events lack integrity hashes.", details={"reason": "Merge events lack integrity hashes."})
        return CheckResult(passed="fail", message="No merge events recorded.", details={"reason": "No merge events recorded."})

    def _check_has_change_management(self) -> CheckResult:
        """Check for change management audit trail."""
        if not self._merge_events:
            return CheckResult(passed="fail", message="No change events recorded.", details={"reason": "No change events recorded."})

        with_attribution = sum(
            1
            for e in self._merge_events
            if e.get("metadata", {}).get("user_id")
            or e.get("metadata", {}).get("node_id")
            or e.get("input_hash")
        )
        total = len(self._merge_events)

        if with_attribution > 0:
            return CheckResult(passed="pass", message="Check passed", details={
                "events_with_attribution": with_attribution,
                "total": total,
            })
        return CheckResult(passed="fail", message="Change events lack user/node attribution.", details={"reason": "Change events lack user/node attribution."})

    def _check_has_retention_policy(self) -> CheckResult:
        """Check for retention policy metadata."""
        for event in self._merge_events:
            meta = event.get("metadata", {})
            if "retention_days" in meta or "retention_policy" in meta:
                return CheckResult(passed="pass", message="Check passed", details={"retention_documented": True})
        if not self._merge_events:
            return CheckResult(passed="not_applicable", message="No events to check.", details={"reason": "No events to check."})
        return CheckResult(passed="fail", message="No retention policy documented.", details={"reason": "No retention policy documented."})


# ---------------------------------------------------------------------------
# EUAIActReport — specialised EU AI Act report generator
# ---------------------------------------------------------------------------

class EUAIActReport:
    """Specialised EU AI Act compliance report generator.

    Provides methods for Art. 6 risk classification, Art. 13 transparency,
    and Art. 10 data governance documentation.

    Parameters:
        auditor: A :class:`ComplianceAuditor` (any framework — will be used
                 for event data regardless of its configured framework).
    """

    def __init__(self, auditor: ComplianceAuditor) -> None:
        self._auditor = auditor

    def risk_classification(
        self, system_description: str = "", is_high_risk: bool = False
    ) -> Dict[str, Any]:
        """Classify the system per EU AI Act Art. 6 risk categories.

        Parameters:
            system_description: Free-text description of the AI system.
            is_high_risk:       Override flag — if ``True`` the system is
                                classified as high-risk regardless of heuristics.

        Returns:
            Dict with ``risk_level``, ``classification``, and ``obligations``.
        """
        if is_high_risk:
            risk_level = "high"
            classification = "Annex III high-risk AI system"
            obligations = [
                "Art. 9 — Risk management system",
                "Art. 10 — Data governance",
                "Art. 11 — Technical documentation",
                "Art. 12 — Record-keeping",
                "Art. 13 — Transparency",
                "Art. 14 — Human oversight",
                "Art. 15 — Accuracy, robustness, cybersecurity",
            ]
        else:
            merge_count = len(self._auditor._merge_events)
            has_access_controls = len(self._auditor._access_events) > 0
            has_unmerge = len(self._auditor._unmerge_events) > 0

            if merge_count > 100 or has_access_controls:
                risk_level = "limited"
                classification = "Limited-risk AI system — transparency obligations apply"
                obligations = [
                    "Art. 13 — Transparency obligations",
                    "Art. 52 — Disclosure requirements",
                ]
            elif merge_count > 0:
                risk_level = "minimal"
                classification = "Minimal-risk AI system — voluntary codes of conduct"
                obligations = [
                    "Voluntary codes of conduct (Art. 69)",
                ]
            else:
                risk_level = "unclassified"
                classification = "Insufficient data to classify"
                obligations = [
                    "Record merge operations to enable classification.",
                ]

        return {
            "risk_level": risk_level,
            "classification": classification,
            "system_description": system_description,
            "obligations": obligations,
            "merge_events_analysed": len(self._auditor._merge_events),
            "timestamp": time.time(),
        }

    def transparency_report(self) -> Dict[str, Any]:
        """Generate Art. 13 transparency report.

        Documents what data was used, how it was processed, and what
        metadata is available for interpretability.
        """
        merge_events = self._auditor._merge_events
        total = len(merge_events)
        with_metadata = sum(
            1
            for e in merge_events
            if e.get("metadata") and len(e["metadata"]) > 0
        )
        with_hashes = sum(
            1
            for e in merge_events
            if e.get("input_hash") or e.get("output_hash")
        )

        operations = {}
        for e in merge_events:
            op = e.get("operation", "unknown")
            operations[op] = operations.get(op, 0) + 1

        return {
            "article": "Art. 13 — Transparency",
            "total_operations": total,
            "operations_with_metadata": with_metadata,
            "operations_with_hashes": with_hashes,
            "operation_types": operations,
            "transparency_score": (
                with_metadata / total if total > 0 else 0.0
            ),
            "timestamp": time.time(),
        }

    def data_governance(self) -> Dict[str, Any]:
        """Generate Art. 10 data governance documentation.

        Documents data quality and provenance tracking measures.
        """
        merge_events = self._auditor._merge_events
        unmerge_events = self._auditor._unmerge_events

        provenance_tracked = sum(
            1
            for e in merge_events
            if e.get("metadata", {}).get("has_provenance")
            or (e.get("input_hash") and e.get("output_hash"))
        )

        return {
            "article": "Art. 10 — Data and data governance",
            "total_merge_operations": len(merge_events),
            "provenance_tracked": provenance_tracked,
            "erasure_operations": len(unmerge_events),
            "data_quality_score": (
                provenance_tracked / len(merge_events)
                if merge_events
                else 0.0
            ),
            "timestamp": time.time(),
        }

    def generate(self) -> ComplianceReport:
        """Generate a full structured EU AI Act compliance report.

        Combines risk classification, transparency, and data governance
        checks into a single :class:`ComplianceReport`.
        """
        # Use a shallow copy of the auditor to avoid mutating the original's
        # framework attribute — the original approach was NOT thread-safe.
        temp_auditor = copy.copy(self._auditor)
        temp_auditor.framework = "eu_ai_act"
        report = temp_auditor.validate()

        # Enrich metadata
        report.metadata["risk_classification"] = self.risk_classification()
        report.metadata["transparency"] = self.transparency_report()
        report.metadata["data_governance"] = self.data_governance()

        return report
