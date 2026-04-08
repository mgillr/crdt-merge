# Compliance Guide: GDPR, HIPAA, SOX, EU AI Act

crdt-merge ships a built-in compliance layer (`crdt_merge.compliance`) that integrates directly with the audit chain, RBAC, and model-unmerge subsystems. Every merge operation can be validated against regulatory frameworks with one method call, and reports can be cryptographically signed for regulators.

```
┌──────────────────────────────────────────────────────────────────┐
│  ComplianceAuditor                                                │
│                                                                   │
│  record_merge()         ← log a merge event                      │
│  record_merge_data()    ← raw output for PHI / field checks      │
│  record_unmerge()       ← GDPR Art.17 erasure events             │
│  record_access(granted) ← SOX / HIPAA access logs                │
│                                                                 │
│  validate() ──────────────────────ComplianceReport             │
│                                     .to_text()                    │
│                                     .sign(key) / .verify(key,sig) │
└──────────────────────────────────────────────────────────────────┘
```

**Supported frameworks:** `"gdpr"` · `"hipaa"` · `"sox"` · `"eu_ai_act"`

---

## Quick Start

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog
from crdt_merge import merge
import hashlib, json

audit   = AuditLog(node_id="prod-pipeline")
auditor = ComplianceAuditor(framework="gdpr", node_id="prod-pipeline", audit_log=audit)

records_a = [{"id": "U1", "email": "alice@example.com", "score": 80}]
records_b = [{"id": "U1", "email": "alice@example.com", "score": 95}]
result = merge(records_a, records_b, key="id")

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

auditor.record_merge(
    operation="customer-score-merge",
    input_hash=sha(records_a)[:16],
    output_hash=sha(result)[:16],
    metadata={"source": "customer-pipeline", "records": len(result)},
)

report = auditor.validate()
print(report.to_text())
```

---

## GDPR (EU General Data Protection Regulation)

| Article | Principle | crdt-merge feature |
|---|---|---|
| Art.5(1)(c) | Data minimisation | Output field checks via `record_merge_data()` |
| Art.5(1)(e) | Storage limitation | TTL/expiry field detection |
| Art.17 | Right to erasure | `GDPRForget.forget_data()` + audit entry |
| Art.30 | Records of processing | `AuditLog` append-only chain |

### Setup

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog

audit   = AuditLog(node_id="eu-data-pipeline")
auditor = ComplianceAuditor(framework="gdpr", node_id="eu-data-pipeline", audit_log=audit)
```

### Recording a Merge

```python
import hashlib, json
from crdt_merge import merge

records_a = [{"id": "U1", "name": "Alice", "email": "alice@acme.com", "age": 32}]
records_b = [{"id": "U1", "name": "Alice", "email": "alice@acme.com", "age": 33}]
merged    = merge(records_a, records_b, key="id")

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

auditor.record_merge(
    operation="user-profile-merge",
    input_hash=sha(records_a),
    output_hash=sha(merged),
    metadata={"purpose": "profile-sync", "lawful_basis": "legitimate_interest"},
)

# Supply raw output for Art.5(1)(c) data-minimisation checks
# The auditor flags fields in the output absent from all inputs
auditor.record_merge_data(
    output=merged[0],
    input_schemas=[set(records_a[0].keys()), set(records_b[0].keys())],
)

report = auditor.validate()
print(report.to_text())
```

### Art.17 Right to Erasure — Records

```python
from crdt_merge.unmerge import GDPRForget
from crdt_merge.provenance import ProvenanceLog

prov = ProvenanceLog()
data_a = [{"id": "U1", "name": "Alice", "purchases": 12}]
data_b = [{"id": "U2", "name": "Bob",   "purchases":  7}]
merged = merge(data_a, data_b, key="id", provenance_log=prov)

# Bob requests erasure
forget = GDPRForget()
result = forget.forget_data(
    merged_data=merged,
    provenance=prov,
    contributor="b",
    key_field="id",
    audit_log=audit,               # writes gdpr_forget entry to chain
)
print(f"Records removed: {result.data_records_removed}")
print(f"Success: {result.success}")

gdpr_report = forget.compliance_report()
print(f"Requests processed: {len(gdpr_report.requests_processed)}")
print(f"Total removed: {gdpr_report.total_records_removed}")
```

### Art.17 Right to Erasure — ML Models

```python
import numpy as np
from crdt_merge.model import CRDTMergeState
from crdt_merge.unmerge import GDPRForget

state = CRDTMergeState("weight_average")
state.add(np.random.randn(64, 64).astype(np.float32), model_id="hospital-A", weight=0.4)
state.add(np.random.randn(64, 64).astype(np.float32), model_id="hospital-B", weight=0.35)
state.add(np.random.randn(64, 64).astype(np.float32), model_id="hospital-C", weight=0.25)

# Hospital B withdraws consent — remove from CRDT state
forget = GDPRForget()
result = forget.forget_training_data(
    model_state=state,
    provenance={"contributors": ["hospital-A", "hospital-B", "hospital-C"]},
    data_to_forget="hospital-B",
    method="negmerge",
    audit_log=audit,
)
print(f"Model influence removed: {result.model_influence_removed}")
# state now has hospital-B tombstoned; resolve() excludes it
```

### Subject Tracing (Forensics)

```python
import hashlib
# Locate all merge events involving a specific data subject
subject_hash = hashlib.sha256("alice@acme.com".encode()).hexdigest()
entries = auditor.trace_subject(subject_hash, audit)
for entry in entries:
    print(f"  {entry.operation} at {entry.timestamp}")
```

---

## HIPAA (Health Insurance Portability and Accountability Act)

| Rule | Requirement | crdt-merge feature |
|---|---|---|
| Security §164.312(a) | Access controls | `RBACController` + `Policy(denied_fields=PHI_FIELDS)` |
| Security §164.312(e) | Transmission security | `EncryptedMerge` with AES-256-GCM |
| Privacy §164.514 | PHI de-identification | HIPAA PHI detection rule |
| Audit §164.312(b) | Access logs | `AuditLog` + `record_access()` |

### Setup

```python
import secrets
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, Policy, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge

PHI_FIELDS = {"patient_id", "dob", "ssn", "diagnosis_code", "medication", "mrn"}

key_provider = StaticKeyProvider(secrets.token_bytes(32))
em = EncryptedMerge(key_provider=key_provider, backend="aes-256-gcm")

rbac = RBACController()
rbac.add_policy(Policy(
    role=MERGER,
    denied_fields=PHI_FIELDS,
    allowed_strategies={"LWW", "MaxWins"},
))

audit = AuditLog(node_id="hipaa-ehr")
am    = AuditedMerge(audit_log=audit)

auditor = ComplianceAuditor(
    framework="hipaa",
    node_id="hipaa-ehr",
    audit_log=audit,
    rbac=rbac,
)
```

### PHI-Safe Merge

```python
records_a = [{"encounter_id": "E001", "patient_id": "P9912", "diagnosis_code": "J18.9", "temp_f": 101.3}]
records_b = [{"encounter_id": "E001", "patient_id": "P9912", "diagnosis_code": "J18.9", "temp_f": 102.1}]

phi_present = list(PHI_FIELDS & set(records_a[0].keys()))

# Encrypt PHI before it reaches the merge engine
enc_a = em.encrypt_records(records_a, fields=phi_present, key="encounter_id")
enc_b = em.encrypt_records(records_b, fields=phi_present, key="encounter_id")

merged_enc, entry = am.merge(enc_a, enc_b, key="encounter_id")

auditor.record_merge(
    operation="ehr-encounter-merge",
    input_hash=entry.input_hash,
    output_hash=entry.output_hash,
    metadata={"encounter_count": len(merged_enc), "phi_encrypted": True},
)
auditor.record_access(
    user_id="nurse-station-7",
    operation="read",
    resource="encounter:E001",
    granted=True,
)

# Supply decrypted output for PHI field detection
decrypted = em.decrypt_records(merged_enc)
auditor.record_merge_data(
    output=decrypted[0],
    input_schemas=[set(records_a[0].keys()), set(records_b[0].keys())],
)

report = auditor.validate()
print(report.to_text())
```

---

## SOX (Sarbanes-Oxley Act)

| Section | Requirement | crdt-merge feature |
|---|---|---|
| §302 | Management certification | Signed `ComplianceReport` |
| §404 | Internal controls | `RBACController` merge authorisation |
| §802 | Audit trail integrity | `AuditLog.verify_chain()` |

### Setup

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.rbac import RBACController, Policy, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge

audit = AuditLog(node_id="sox-finance")
am    = AuditedMerge(audit_log=audit)

rbac = RBACController()
rbac.add_policy(Policy(
    role=MERGER,
    allowed_strategies={"LWW", "MaxWins"},
    max_record_count=500_000,
))

auditor = ComplianceAuditor(
    framework="sox",
    node_id="sox-finance",
    audit_log=audit,
    rbac=rbac,
)
```

### Authorised Financial Merge

```python
from crdt_merge import merge
import secrets, json

ledger_a = [{"account_id": "GL-1001", "balance": 145_200.00, "period": "2026-Q1"}]
ledger_b = [{"account_id": "GL-1001", "balance": 147_850.00, "period": "2026-Q1"}]

result, entry = am.merge(ledger_a, ledger_b, key="account_id")

auditor.record_merge(
    operation="gl-consolidation",
    input_hash=entry.input_hash,
    output_hash=entry.output_hash,
    metadata={"period": "2026-Q1", "accounts": len(result), "authorised_by": "cfo-system"},
)
# Record the authorisation event itself
auditor.record_access(
    user_id="cfo-system",
    operation="merge_authorise",
    resource="gl-consolidation-2026-Q1",
    granted=True,
)

# Verify chain integrity before signing
assert audit.verify_chain(), "CRITICAL: audit chain integrity failure"

report        = auditor.validate()
signing_key   = secrets.token_bytes(32)   # load from HSM in production
signature     = report.sign(signing_key)
assert report.verify(signing_key, signature)

# Export signed package for external auditors
with open("sox-report-2026-Q1.json", "w") as f:
    json.dump({**report.to_dict(), "signature": signature}, f, indent=2)

print(report.to_text())
```

---

## EU AI Act

| Article | Obligation | crdt-merge feature |
|---|---|---|
| Art.9 | Risk management | `EUAIActReport.risk_classification()` |
| Art.10 | Data governance | `record_merge_data()` + `data_governance()` |
| Art.13 | Transparency | `transparency_report()` |
| Art.14 | Human oversight | `record_access()` events |
| Art.17 | Quality management | Signed `ComplianceReport` |

### Setup

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport
from crdt_merge.audit import AuditLog

audit   = AuditLog(node_id="eu-ai-hiring")
auditor = ComplianceAuditor(framework="eu_ai_act", node_id="eu-ai-hiring", audit_log=audit)
```

### Risk Classification

```python
report_obj = EUAIActReport(auditor)

classification = report_obj.risk_classification(
    system_description="Automated candidate scoring and shortlisting system",
    is_high_risk=True,    # employment systems are Annex III high-risk
)
print(f"Risk level:   {classification['risk_level']}")        # "high"
print(f"Obligations:  {classification['obligations']}")
```

### Full Compliance Workflow

```python
from crdt_merge import merge

candidates_a = [{"id": "C001", "score": 0.82, "source": "assessment"}]
candidates_b = [{"id": "C001", "score": 0.79, "source": "interview"}]
merged        = merge(candidates_a, candidates_b, key="id")

auditor.record_merge(
    operation="candidate-score-fusion",
    metadata={
        "model_version": "hiring-v3.1",
        "transparency_metadata": True,
        "human_review_required": True,
    },
)
auditor.record_merge_data(
    output=merged[0],
    input_schemas=[set(candidates_a[0].keys()), set(candidates_b[0].keys())],
)
# Human oversight event (Art.14)
auditor.record_access(
    user_id="hr-reviewer-42",
    operation="human_oversight_review",
    resource="candidate:C001",
    granted=True,
)

transparency = report_obj.transparency_report()
print(f"Transparency score: {transparency['transparency_score']:.0%}")

governance = report_obj.data_governance()
print(f"Data quality score: {governance['data_quality_score']:.0%}")

full_report = report_obj.generate()
print(full_report.to_text())

import secrets
key = secrets.token_bytes(32)
sig = full_report.sign(key)
print(f"Signed. Signature: {sig[:32]}...")
```

---

## Custom Compliance Rules

Register domain-specific rules alongside the built-ins:

```python
import time
from crdt_merge.compliance import (
    register_compliance_rule, ComplianceFinding, CheckResult,
)

def check_no_future_timestamps(auditor) -> ComplianceFinding:
    """Reject merge events with timestamps more than 60s in the future."""
    now = time.time()
    future = [e for e in auditor._merge_events if e.get("timestamp", 0) > now + 60]
    passed = len(future) == 0
    return ComplianceFinding(
        rule_id="custom-no-future-ts",
        status="PASS" if passed else "FAIL",
        severity="medium",
        framework="gdpr",
        description="Merge event timestamps must not be in the future",
        evidence={"future_event_count": len(future)},
        recommendation="Check system clock synchronisation" if not passed else "",
    )

register_compliance_rule("gdpr", check_no_future_timestamps)

# Runs automatically in the next validate()
auditor = ComplianceAuditor(framework="gdpr")
auditor.record_merge("test")
report = auditor.validate()
```

---

## Signed Reports for Regulators

```python
import secrets, json
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="sox")
auditor.record_merge("quarterly-close")
report = auditor.validate()

signing_key = secrets.token_bytes(32)   # load from HSM in production
signature   = report.sign(signing_key)

package = {**report.to_dict(), "signature": signature, "signer": "compliance-v2"}
with open("sox-compliance.json", "w") as f:
    json.dump(package, f, indent=2)

# Verify in another process
loaded = json.load(open("sox-compliance.json"))
sig    = loaded.pop("signature")
loaded.pop("signer", None)
new_report = ComplianceAuditor(framework="sox").validate()  # re-validate or reconstruct
assert report.verify(signing_key, signature), "Tamper detected"
print("Report authenticity verified")
```

---

## Multi-Framework: One Audit Log

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog

audit = AuditLog(node_id="global-system")
gdpr_aud  = ComplianceAuditor(framework="gdpr",      audit_log=audit)
hipaa_aud = ComplianceAuditor(framework="hipaa",     audit_log=audit)
eu_ai_aud = ComplianceAuditor(framework="eu_ai_act", audit_log=audit)

for aud in (gdpr_aud, hipaa_aud, eu_ai_aud):
    aud.record_merge("cross-border-merge", metadata={"regions": ["EU", "US"]})

gdpr_report  = gdpr_aud.validate()
hipaa_report = hipaa_aud.validate()
ai_report    = eu_ai_aud.validate()
```

---

## Decision Matrix

| Regulation | Use when | Key class |
|---|---|---|
| GDPR | EU personal data, consent, erasure | `ComplianceAuditor(framework="gdpr")`, `GDPRForget` |
| HIPAA | US health records, EHR, clinical | `ComplianceAuditor(framework="hipaa")`, `EncryptedMerge` |
| SOX | US public company financial data | `ComplianceAuditor(framework="sox")`, `AuditedMerge` |
| EU AI Act | High-risk AI systems (EU) | `ComplianceAuditor(framework="eu_ai_act")`, `EUAIActReport` |

### E4 Trust Layer

E4 provides a cryptographic audit trail via proof-carrying operations. Every merge decision is traceable to its originator with signed evidence, strengthening compliance posture for GDPR Art.30, HIPAA audit requirements, SOX controls, and EU AI Act traceability mandates. PCOs bind originator identity and trust state to each operation. See [E4 Architecture](../e4/E4-MASTER-ARCHITECTURE.md) for details.

---

## See Also

- [Security Guide](security-guide.md) — encryption backends, key management
- [Privacy-Preserving Merge](privacy-preserving-merge.md) — field-level encryption cookbook
- [Provenance — Complete AI](provenance-complete-ai.md) — audit chains and lineage
- [Right to Forget in AI](right-to-forget-in-ai.md) — CRDT `remove()` and model unmerge
- [API Reference: Layer 6](../api-reference/layer6-compliance/compliance.md) — full class/method reference
