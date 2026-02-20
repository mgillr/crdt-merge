# SPDX-License-Identifier: BUSL-1.1

# Security Hardening Guide

This guide complements the [Security Guide](security-guide.md), which covers
the crdt-merge encryption, RBAC, and audit APIs in detail. The present guide
focuses on **production hardening**: what to configure, verify, and monitor
before deploying crdt-merge in regulated or high-security environments.

Read the [Security Guide](security-guide.md) first for the foundational API.

---

## Production Hardening Checklist

The following checklist covers the minimum controls required for a
production deployment. Each item links to the relevant section below.

### Encryption

- [ ] Deploy with `backend="aes-256-gcm-siv"` or `backend="aes-256-gcm"`. Never use `xor-legacy` in production.
- [ ] Generate master keys with `secrets.token_bytes(32)`. Never derive keys from passwords without a KDF (Argon2id, scrypt, or PBKDF2-HMAC-SHA256 with ≥ 600 000 iterations).
- [ ] Store master keys in a secrets manager (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault). Never store keys in environment variables, source code, or config files.
- [ ] Implement a key rotation schedule (monthly at minimum) using `EncryptedMerge.rotate_key()`.
- [ ] After rotation, re-encrypt all at-rest data encrypted with the old key.
- [ ] Use per-field key derivation via `StaticKeyProvider` so that compromising one field's ciphertext cannot be leveraged against others.
- [ ] Prefer `aes-256-gcm-siv` for distributed CRDT deployments where nonce coordination is difficult. See [AES-GCM-SIV vs AES-GCM](#aes-gcm-siv-vs-aes-gcm-when-to-use-each) below.

### Audit Log Integrity

- [ ] Use `AuditedMerge` for every merge operation in production; never call bare `crdt_merge.merge()` directly.
- [ ] Store exported audit log JSON in append-only storage (object store with object lock, write-ahead log, or immutable ledger).
- [ ] Call `log.verify_chain()` on a scheduled basis (hourly minimum). Alert on `False` return.
- [ ] Export and archive the audit log at least once per day using `log.export_log(filepath=...)`.
- [ ] Restrict `AUDIT_READ` permission to dedicated audit principals; do not grant it to operational roles.

### RBAC

- [ ] Define explicit `denied_fields` for all sensitive columns (PII, PHI, financial secrets). Explicit deny always wins over allow.
- [ ] Grant the `MERGER` role to operational nodes; reserve `ADMIN` for human operators only.
- [ ] Set `max_record_count` on every `Policy` to prevent resource-exhaustion via oversized merge payloads.
- [ ] Use `SecureMerge` instead of bare `crdt_merge.merge()` in any multi-tenant or networked environment.
- [ ] Treat RBAC policies as code: version them in git, review changes in pull requests, test them with `rbac.check_permission()` assertions.

### Network

- [ ] Enable TLS 1.3 (minimum TLS 1.2) on the Arrow Flight server. See [Network Security](#network-security-for-arrow-flight-and-gossip).
- [ ] Restrict gossip protocol ports to trusted network segments or VPN.
- [ ] Enable mutual TLS (mTLS) for Arrow Flight in zero-trust environments.
- [ ] Rate-limit the gossip `sync` endpoint to prevent amplification attacks.

---

## AES-GCM-SIV vs AES-GCM: When to Use Each

Both AES-GCM and AES-GCM-SIV are authenticated encryption with associated data
(AEAD) schemes. The practical difference is **nonce misuse resistance**.

### AES-GCM

AES-GCM requires a unique, unpredictable 96-bit nonce per encryption operation.
If the same (key, nonce) pair is ever reused, the confidentiality of **both**
messages is catastrophically broken: an attacker can XOR the two ciphertexts
to cancel the keystream and derive the relationship between the plaintexts.
GHASH authentication also breaks under nonce reuse.

Use AES-GCM when:
- Your system generates nonces randomly and the per-key encryption volume is well below 2^32 operations (birthday bound on 96-bit nonces is ~4 billion operations).
- You have a reliable monotonic counter for nonce generation.
- Hardware AES-NI acceleration is available and throughput is a primary concern.

### AES-GCM-SIV

AES-GCM-SIV (RFC 8452) is a **nonce-misuse-resistant** construction. If a
nonce is accidentally reused, confidentiality is *still* maintained (an
attacker learns only whether two encrypted values are identical, not their
content). Authentication still holds under nonce reuse.

Use AES-GCM-SIV when:
- You are running CRDT merge operations in a distributed system where two nodes might independently generate the same nonce (absence of a shared sequence number service).
- You cannot guarantee strict nonce uniqueness across all replicas (e.g., clock-based nonces with potential clock skew).
- Merging large numbers of field-level values where a birthday collision is statistically likely at scale.
- **This is the recommended default for crdt-merge production deployments.**

### Configuration

```python
# Recommended for distributed CRDT workloads
em = EncryptedMerge(key_provider=provider, backend="aes-256-gcm-siv")

# Acceptable when nonce uniqueness is strictly controlled
em = EncryptedMerge(key_provider=provider, backend="aes-256-gcm")

# Never use in production
em = EncryptedMerge(key_provider=provider, backend="xor-legacy")
```

---

## Merkle Tree Anti-Tamper: Why Chain Verification Matters

crdt-merge uses two independent hash-chaining mechanisms that reinforce each
other.

### Audit Log Hash Chain

The `AuditLog` maintains a SHA-256 hash chain where each entry includes the
hash of the previous entry (`prev_hash`). This is structurally identical to a
blockchain: modifying any historical entry invalidates every subsequent entry
hash.

Why this matters:
- An attacker who gains write access to the audit store cannot silently delete or modify a merge event without breaking `verify_chain()`.
- The chain provides non-repudiation: each `entry_hash` is a commitment to the exact state of the operation at the time it was recorded.
- Exporting the log and verifying it in a separate trust domain provides independent assurance.

### Merkle Tree Dataset Verification

The `MerkleTree` built over a dataset enables efficient detection of tampering
in record sets. A root hash is a commitment to the exact contents of the
entire dataset. If any record is changed, added, or removed, the root hash
changes.

Use `merkle compare` in your CI/CD pipeline or pre-merge validation to
assert that incoming datasets match an expected root hash:

```bash
# Build a trusted reference tree
crdt-merge merkle build reference.parquet --key id -o reference_tree.json

# Before merging, verify the incoming dataset matches the reference
crdt-merge merkle compare reference.parquet incoming.parquet --key id
```

### Cross-Layer Integrity

For maximum assurance, combine both mechanisms:

1. Before merging, compute and record Merkle root hashes of input datasets.
2. Perform the merge via `AuditedMerge` (which records input/output hashes in the audit log).
3. After merging, verify the audit chain.
4. Archive the audit log to append-only storage.

This creates a complete, verifiable record linking input datasets to merge
outputs, resistant to both external tampering and insider manipulation.

---

## RBAC Permission Design Patterns

### Principle of Least Privilege

Assign roles that grant only the permissions a node or user actually needs.
The permission hierarchy from least to most privileged is:

```
READER < WRITER < MERGER < ADMIN
```

A node that only reads merged results needs only `READ` and `AUDIT_READ`
(the `READER` role). A node that performs merges needs `READ`, `WRITE`, and
`MERGE` (the `MERGER` role). The `ADMIN` role grants all permissions including
`UNMERGE` and `ENCRYPT`; assign it only to human operators and dedicated admin
services.

### Sensitive Field Isolation

Always use `denied_fields` for columns that must never be exposed, even to
privileged roles. The deny list always wins over the allow list:

```python
# PII and secrets are always denied, even for ADMIN-level mergers
policy = Policy(
    role=MERGER,
    denied_fields={"ssn", "credit_card_number", "api_key", "password_hash"},
    max_record_count=50_000,
)
```

### Multi-Tenant Field Segmentation

In multi-tenant deployments, namespace field allowlists per tenant to prevent
cross-tenant data leakage:

```python
# Tenant A can only access their own fields
tenant_a_policy = Policy(
    role=MERGER,
    allowed_fields={"tenant_id", "record_id", "name", "email"},
    denied_fields={"internal_cost", "margin"},
    max_record_count=10_000,
)

# Internal analytics has broader read access but cannot merge
analytics_policy = Policy(
    role=READER,
    allowed_fields=None,  # All fields readable
    denied_fields={"ssn", "raw_pii"},
)
```

### Strategy Restrictions

Use `allowed_strategies` to prevent untrusted nodes from applying destructive
or expensive strategies:

```python
policy = Policy(
    role=MERGER,
    allowed_strategies={"LWW", "MaxWins", "MinWins"},
    # Prevents use of UnionSet (potentially unbounded growth)
    # and Custom (arbitrary code execution via merge strategy)
)
```

### Thread Safety

`RBACController` is thread-safe. All policy mutations are guarded by an
internal lock, making it safe to share a single controller instance across
async handlers, thread pools, and gRPC/Flight server coroutines.

---

## Network Security for Arrow Flight and Gossip Protocol

### Arrow Flight (Port 8815)

Arrow Flight exposes a gRPC-based merge server. Harden it as follows:

**TLS Configuration**

Always enable TLS in production. Generate a server certificate and key:

```bash
# Generate a self-signed cert for internal use (use a proper CA in production)
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt \
  -days 365 -nodes -subj "/CN=crdt-merge-flight"
```

Start the server with TLS:

```bash
crdt-merge accel flight serve \
  --host 0.0.0.0 --port 8815 \
  --tls-cert server.crt --tls-key server.key
```

**Mutual TLS (mTLS)**

For zero-trust environments, require client certificates:

```bash
crdt-merge accel flight serve \
  --host 0.0.0.0 --port 8815 \
  --tls-cert server.crt --tls-key server.key \
  --ca-cert ca.crt  # Clients must present certs signed by this CA
```

**Network Segmentation**

- Place the Flight server in a private subnet or VPC.
- Restrict inbound access to port 8815 to trusted CIDR ranges via firewall/security group rules.
- Do not expose the Flight server directly to the public internet.

**Authentication**

Integrate RBAC authentication via the Flight middleware layer to verify
node identities before processing merge requests.

### Gossip Protocol

The gossip anti-entropy protocol is designed for intra-cluster use.

- **Firewall**: Block gossip ports from external networks. Gossip should only
  be reachable within the cluster or VPN.
- **Rate limiting**: Implement rate limiting on `gossip sync` endpoints to
  prevent amplification. A single compromised node should not be able to
  trigger unbounded synchronization load.
- **State file validation**: Validate incoming gossip state payloads against
  a schema before applying them. Reject malformed or oversized payloads.
- **Node authentication**: Require signed gossip messages using each node's
  private key to prevent spoofed state injection.

---

## GDPR Compliance Checklist

crdt-merge's compliance module (`crdt_merge.compliance`) provides GDPR-specific
controls. Activate them alongside the standard security layers.

### Data Minimization

- [ ] Use `denied_fields` in RBAC policies to exclude fields containing personal data from nodes that do not require it.
- [ ] Apply `--strategy union` only to fields where accumulation is intentional; avoid unbounded growth in OR-Set fields containing PII.

### Right of Access (Article 15)

- [ ] Use `provenance show` to produce a record of all merge operations that touched a given subject's data.
- [ ] Export per-subject provenance with `crdt-merge provenance export --subject-id <id>`.

### Right to Erasure / Right to be Forgotten (Article 17)

- [ ] Use `crdt-merge unmerge forget` to remove a subject's records from CRDT state.
- [ ] After erasure, re-export and re-verify the audit log to confirm the operation was recorded.
- [ ] Note: hash-chained audit logs record the erasure event itself; the subject's data is removed from the operational dataset but the audit trail of the erasure is preserved (this is compliant — the log records *that* an erasure occurred, not the erased data).

### Data Transfers (Chapter V)

- [ ] Encrypt data at rest with AES-GCM-SIV before transferring to jurisdictions outside the EEA.
- [ ] Use the `--encrypt` flag on `merge` output when writing to cross-border storage.
- [ ] Document the legal transfer mechanism (SCC, adequacy decision) in your compliance records.

### Breach Notification (Article 33)

- [ ] Configure the audit log to forward `decrypt` and `key_rotate` events to your SIEM.
- [ ] Set up alerts for unexpected `ADMIN`-role operations outside business hours.
- [ ] The audit log's `verify_chain()` failure is itself an indicator of compromise requiring Article 33 assessment.

### Privacy by Design

- [ ] Run `crdt-merge compliance check --framework gdpr` as part of your deployment pipeline.
- [ ] Generate compliance reports with `crdt-merge compliance report --framework gdpr --output gdpr-report.json`.

---

## SOX and HIPAA Key Controls

### SOX (Sarbanes-Oxley)

SOX Section 302 and 404 require controls over financial data integrity and
access.

| Control | crdt-merge Implementation |
|---------|--------------------------|
| Change management | Use `AuditedMerge` for all financial data merges; every change is hash-chained and tamper-evident. |
| Access control | Assign `MERGER` role only to authorized systems; restrict `ADMIN` to named individuals with approval workflows. |
| Segregation of duties | Separate `MERGER` (operational) from `ADMIN` (key management) from `AUDIT_READ` (auditors) roles. |
| Data integrity | Run `merkle compare` before and after every merge to verify input/output dataset hashes. |
| Audit trail | Export audit logs daily; store in write-once, read-many (WORM) storage. |

**Compliance check**

```bash
crdt-merge compliance check --framework sox
crdt-merge compliance report --framework sox --output sox-report.json
```

### HIPAA (Protected Health Information)

HIPAA Security Rule requires technical safeguards for PHI access, transmission,
and storage.

| Safeguard | crdt-merge Implementation |
|-----------|--------------------------|
| Access control (§164.312(a)(1)) | RBAC `denied_fields` for PHI columns; `MERGER` role for clinical systems; `ADMIN` for system administrators only. |
| Audit controls (§164.312(b)) | `AuditedMerge` records every access; `AUDIT_READ` role for compliance officers. |
| Integrity (§164.312(c)(1)) | Merkle tree verification before and after merges involving PHI datasets. |
| Transmission security (§164.312(e)(1)) | TLS 1.3 on Arrow Flight; encrypt output with AES-GCM-SIV for at-rest PHI. |
| Encryption (§164.312(a)(2)(iv)) | Field-level AES-256-GCM-SIV encryption for PHI fields via `EncryptedMerge`. |

**PHI field encryption pattern**

```python
phi_fields = {"patient_id", "dob", "ssn", "diagnosis_code", "medication"}

policy = Policy(
    role=MERGER,
    denied_fields=phi_fields,  # PHI never exposed to MERGER nodes in plaintext
    allowed_strategies={"LWW", "MaxWins"},
    max_record_count=100_000,
)

# PHI is encrypted before entering the merge pipeline
em = EncryptedMerge(key_provider=provider, backend="aes-256-gcm-siv")
encrypted_records = em.encrypt_records(phi_records, fields=list(phi_fields), key="record_id")
```

**Compliance check**

```bash
crdt-merge compliance check --framework hipaa
crdt-merge compliance report --framework hipaa --output hipaa-report.json
```

---

## Incident Response: Using AuditLog for Forensics

When a security incident is suspected — unauthorized merge, data exfiltration,
or tampered records — the `AuditLog` is your primary forensic tool.

### Step 1: Verify Chain Integrity

```python
from crdt_merge.audit import AuditLog

log = AuditLog.import_log("/path/to/audit-log.json")
if not log.verify_chain():
    # CRITICAL: The chain is broken. The log may have been tampered with.
    # Immediately escalate to your incident response team.
    raise SecurityError("Audit log chain verification failed")
```

A broken chain means one or more entries have been added, modified, or removed.
This is a high-severity indicator of compromise.

### Step 2: Identify the Compromised Entries

If `verify_chain()` returns `False`, inspect entries around the break point to
identify what changed. The `prev_hash` of a corrupt entry will not match the
`entry_hash` of its predecessor.

### Step 3: Query for Suspicious Operations

```python
import time

# Find all decrypt operations in the last 24 hours
recent_decrypts = log.get_entries(
    operation="decrypt",
    since=time.time() - 86400,
)

# Find all admin operations
admin_ops = log.get_entries(operation="custom")  # custom includes admin actions

# Find merges that processed unusually large record counts
large_merges = [
    e for e in log.get_entries(operation="merge")
    if e.metadata.get("result_count", 0) > 1_000_000
]
```

### Step 4: Reconstruct the Timeline

Each `AuditEntry` contains:
- `timestamp` — wall-clock time of the operation
- `node_id` — which node performed the operation
- `input_hash` / `output_hash` — SHA-256 of inputs and outputs
- `metadata` — operation-specific details (record counts, schema, node IDs)
- `prev_hash` / `entry_hash` — chain linkage

Use these fields to reconstruct a timeline of all operations and identify:
- Which node performed the operation
- What data was involved (via hashes)
- Whether outputs match expected hashes (compare against your Merkle tree records)

### Step 5: Preserve Evidence

```python
# Export the full log immediately for external analysis
log.export_log(filepath="/secure/evidence/audit-log-incident-2026-04-02.json")

# Export only the relevant time window
incident_entries = log.get_entries(since=incident_start, until=incident_end)
```

### Step 6: Containment

- Revoke the compromised node's RBAC policy immediately: `rbac.remove_policy("compromised-node")`.
- Rotate encryption keys using `EncryptedMerge.rotate_key()`.
- If the master key is suspected to be compromised, treat all data encrypted
  under that key as potentially exposed and re-encrypt with a new key.

### Step 7: Notification

Use the audit log evidence to support:
- GDPR Article 33 breach notification (72-hour deadline to supervisory authority)
- HIPAA Breach Notification Rule (60-day deadline)
- SOX incident reporting to the audit committee

---

## Key Rotation Procedures

Key rotation should be a routine operational event, not an emergency procedure.
Schedule it and practice it in staging before performing it in production.

### Rotation Steps

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

# 1. Generate new key from a CSPRNG
new_key = secrets.token_bytes(32)

# 2. Load old key from secrets manager
old_key = vault.get_secret("crdt-merge/master-key")

old_provider = StaticKeyProvider(old_key)
new_provider = StaticKeyProvider(new_key)

# 3. Rotate records in batches
em = EncryptedMerge(key_provider=new_provider, backend="aes-256-gcm-siv")

for batch in load_encrypted_records_in_batches():
    rotated = em.rotate_key(
        records=batch,
        old_provider=old_provider,
        new_provider=new_provider,
        fields=["email", "ssn", "credit_card"],
    )
    write_batch(rotated)

# 4. Store new key in secrets manager
vault.put_secret("crdt-merge/master-key", new_key)
# Archive old key for a grace period (to decrypt any records missed in rotation)
vault.put_secret("crdt-merge/master-key-previous", old_key)

# 5. Log the rotation event
audit_log.log_operation(
    "key_rotate",
    input_data={"old_key_fingerprint": hmac_fingerprint(old_key)},
    output_data={"new_key_fingerprint": hmac_fingerprint(new_key)},
)
```

### Rotation Frequency Recommendations

| Environment | Rotation Frequency |
|-------------|-------------------|
| Production (financial/health) | Monthly |
| Production (general) | Quarterly |
| Staging / pre-production | On every deployment |
| After suspected compromise | Immediately |

### Cross-Backend Migration

`rotate_key()` automatically detects the cipher used for each encrypted value
from its metadata. You can rotate from AES-256-GCM to AES-256-GCM-SIV (or
any other backend combination) in a single pass:

```python
# Migrate from AES-GCM to AES-GCM-SIV at rotation time
em = EncryptedMerge(key_provider=new_provider, backend="aes-256-gcm-siv")
rotated = em.rotate_key(records=old_records, old_provider=old_provider, new_provider=new_provider)
# All records now encrypted with AES-GCM-SIV, regardless of their original cipher
```
