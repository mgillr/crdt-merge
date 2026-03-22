# Layer 6 — Compliance

Layer 6 validates merge operations against regulatory frameworks. It integrates with the Layer 5 audit chain, RBAC, and model-unmerge subsystems — no duplication of logic.

| Document | What it covers |
|---|---|
| [compliance.md](compliance.md) | Full API reference: `ComplianceAuditor`, `EUAIActReport`, `ComplianceReport`, custom rules |

---

## Framework Decision Matrix

| Regulation | Use when | Key class | Framework string |
|---|---|---|---|
| **GDPR** | EU personal data, consent, erasure | `ComplianceAuditor`, `GDPRForget` | `"gdpr"` |
| **HIPAA** | US health records, EHR, clinical trials | `ComplianceAuditor`, `EncryptedMerge` | `"hipaa"` |
| **SOX** | US public company financial reporting | `ComplianceAuditor`, `AuditedMerge` | `"sox"` |
| **EU AI Act** | High-risk AI systems (Annex III) | `ComplianceAuditor`, `EUAIActReport` | `"eu_ai_act"` |

---

## Quick Start

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog

audit   = AuditLog(node_id="my-system")
auditor = ComplianceAuditor(framework="gdpr", audit_log=audit)

auditor.record_merge("user-profile-merge", input_hash="...", output_hash="...")
report = auditor.validate()
print(report.to_text())
```

---

## Built-in Rules by Framework

### GDPR
- **Data minimisation** (Art.5(1)(c)) — flags output fields not present in any input
- **Storage limitation** (Art.5(1)(e)) — checks for TTL/expiry metadata
- Processing records — verifies merge events are present in audit chain
- Access controls — checks RBAC is configured
- Encryption — verifies `EncryptedMerge` usage

### HIPAA
- **PHI detection** — scans output for patterns matching PHI field names (`patient_id`, `dob`, `ssn`, `diagnosis_code`, etc.)
- Data integrity — audit chain presence
- Encryption — `EncryptedMerge` presence check
- Access logs — `record_access()` events required

### SOX
- **Audit trail integrity** — `AuditLog.verify_chain()` must pass
- **Merge authorisation** — RBAC `MERGE` permission must be checked
- Change management — versioned records presence

### EU AI Act
- Merge provenance — complete lineage metadata
- Transparency metadata — operation descriptions
- Human oversight events — `record_access()` with oversight operations
- Risk classification — `is_high_risk` flag drives obligation set
- Unmerge capability — ability to retract contributions

---

## Adding Custom Rules

```python
from crdt_merge.compliance import register_compliance_rule, ComplianceFinding

def my_rule(auditor) -> ComplianceFinding:
    passed = len(auditor._merge_events) > 0
    return ComplianceFinding(
        rule_id="my-rule-001",
        status="PASS" if passed else "FAIL",
        severity="high",
        framework="gdpr",
        description="At least one merge must be recorded",
        evidence={"merge_count": len(auditor._merge_events)},
        recommendation="Call record_merge() before validate()" if not passed else "",
    )

register_compliance_rule("gdpr", my_rule)
```

---

## Signed Reports

```python
import secrets

report = auditor.validate()
key    = secrets.token_bytes(32)   # load from HSM in production
sig    = report.sign(key)
assert report.verify(key, sig)

import json
with open("compliance-report.json", "w") as f:
    json.dump({**report.to_dict(), "signature": sig}, f, indent=2)
```

---

## See Also

- [Compliance Guide](../../guides/compliance-guide.md) — full walkthroughs for each framework
- [Layer 5 Enterprise](../layer5-enterprise/README.md) — encryption, RBAC, audit, observability
- [Right to Forget in AI](../../guides/right-to-forget-in-ai.md) — CRDT erasure and model unmerge
- [Provenance — Complete AI](../../guides/provenance-complete-ai.md) — audit chain and lineage
