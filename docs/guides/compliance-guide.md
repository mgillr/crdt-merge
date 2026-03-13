# Compliance Guide

## GDPR (General Data Protection Regulation)

### Right to Erasure (Article 17)

```python
from crdt_merge.unmerge import GDPRForget

forget = GDPRForget(audit_log=log)
cleaned = forget.forget(data=df, subject_id="user-123", key_col="user_id")
cert = forget.generate_certificate("user-123")
```

### Audit Trail Requirements
- All merges must be logged
- Logs must be immutable
- Retention period: as required by jurisdiction

## HIPAA (Health Insurance Portability and Accountability Act)

### Protected Health Information (PHI)
- Always use `EncryptedMerge` for PHI data
- Use RBAC to restrict access to authorized personnel
- Maintain complete audit trail

## SOX (Sarbanes-Oxley)

### Financial Data Integrity
- Use audit trails to demonstrate data lineage
- Verify chain integrity for compliance evidence
- Export audit reports for external auditors

## EU AI Act

### Model Merge Compliance

```python
from crdt_merge.compliance import EUAIActReport

report = EUAIActReport(risk_level="high")
assessment = report.assess(model_info=model_metadata, merge_info=merge_log)
obligations = report.transparency_obligations()
```

### Risk Levels
- **Minimal**: No specific obligations
- **Limited**: Transparency obligations
- **High**: Conformity assessment, documentation, human oversight
- **Unacceptable**: Prohibited
