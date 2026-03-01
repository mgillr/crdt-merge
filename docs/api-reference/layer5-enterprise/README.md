# Layer 5 — Enterprise

Layer 5 provides the production-hardening features that regulated-industry and enterprise deployments require: field-level encryption, role-based access control, tamper-evident audit trails, observability, and model-contribution retraction.

| Module | File | What it does |
|---|---|---|
| Encryption | [encryption.md](encryption.md) | Field-level AES-256-GCM / ChaCha20 encryption, key rotation, order-preserving tags |
| RBAC | [rbac.md](rbac.md) | Role/policy/permission enforcement; field and strategy access control |
| Audit | [audit.md](audit.md) | Append-only SHA-256 chain; `AuditedMerge` auto-logging |
| Observability | [observability.md](observability.md) | Metrics, OpenTelemetry tracing, drift detection, Prometheus/Grafana export |
| Unmerge | [unmerge.md](unmerge.md) | Model-contribution retraction, GDPR erasure, residual influence measurement |

---

## Quick Start

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, Policy, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.observability import MetricsCollector, ObservedMerge

# 1. Encryption
key_provider = StaticKeyProvider(secrets.token_bytes(32))
em = EncryptedMerge(key_provider=key_provider, backend="aes-256-gcm")

# 2. RBAC
rbac = RBACController()
rbac.add_policy(Policy(role=MERGER, denied_fields={"ssn", "dob"}))

# 3. Audit
audit = AuditLog(node_id="prod-node-1")
am    = AuditedMerge(audit_log=audit)
result, entry = am.merge(records_a, records_b, key="id")
assert audit.verify_chain()

# 4. Observability
collector = MetricsCollector()
om        = ObservedMerge(collector=collector)
result    = om.merge(df_a, df_b, key="id")
print(collector.get_summary())
```

---

## Encryption Backends

| Backend name | Algorithm | Notes |
|---|---|---|
| `"aes-256-gcm"` | AES-256-GCM | Requires `cryptography` package |
| `"chacha20-poly1305"` | ChaCha20-Poly1305 | Preferred for high-throughput; requires `cryptography` |
| `"xor-legacy"` | XOR + HMAC-SHA256 | Zero dependencies; not production-safe |
| `"auto"` | Best available | Selects `aes-256-gcm` if available, else `xor-legacy` |

Custom backends: `register_backend(name, cls)` where `cls` subclasses `CryptoBackend`.

---

## RBAC Roles

| Role | Permissions |
|---|---|
| `READER` | READ, AUDIT_READ |
| `WRITER` | READ, WRITE |
| `MERGER` | READ, WRITE, MERGE |
| `ADMIN` | All permissions |

Custom roles: `Role(name="analyst", permissions=Permission.READ | Permission.AUDIT_READ)`.

---

## See Also

- [Compliance Guide](../../guides/compliance-guide.md) — GDPR, HIPAA, SOX, EU AI Act integration
- [Security Guide](../../guides/security-guide.md) — encryption architecture and key providers
- [Privacy-Preserving Merge](../../guides/privacy-preserving-merge.md) — field-level encryption cookbook
- [Layer 6 Compliance](../layer6-compliance/README.md) — regulatory validation
