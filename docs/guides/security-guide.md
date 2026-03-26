# Security Guide

crdt-merge provides **defense-in-depth** security through three integrated layers:

1. **Field-Level Encryption** — pluggable AEAD backends with order-preserving tags
2. **Role-Based Access Control (RBAC)** — policy-driven permission enforcement
3. **Audit Trails** — SHA-256 hash-chained, tamper-evident logging

Each layer can be used independently or composed together. This guide covers
architecture, configuration, and runnable examples drawn from the real API.

---

## Field-Level Encryption

The `crdt_merge.encryption` module encrypts individual record fields while
preserving the ability to resolve merge conflicts (LWW, MaxWins, MinWins) on
ciphertext via **order-preserving HMAC tags** — no decryption required during
merge.

### Architecture

```
  Plaintext value
        │
          ┌─────────────┐      ┌──────────────┐
  │ KeyProvider  │─────│ Per-field key │  (HMAC-SHA256 derivation)
  └─────────────┘      └──────┬───────┘
                              │
               ┌──────────────┼──────────────┐
                                                 ┌────────────┐ ┌────────────┐ ┌───────────┐
        │ Encrypt    │ │ Auth tag   │ │ Order tag │
        │ (backend)  │ │ (backend)  │ │ HMAC(val) │
        └────────────┘ └────────────┘ └───────────┘
               │              │              │
                                                    EncryptedValue { ciphertext, nonce, tag, order_tag, field_name }
```

### Available Backends

| Backend | Registry Name | Library | Description |
|---------|--------------|---------|-------------|
| **AES-256-GCM** | `aes-256-gcm` | `cryptography` | Industry-standard AEAD. Default when `backend="auto"` and `cryptography` is installed. |
| **AES-256-GCM-SIV** | `aes-256-gcm-siv` | `cryptography` | Nonce-misuse-resistant AEAD — ideal for CRDTs where nonce reuse risk is elevated. |
| **ChaCha20-Poly1305** | `chacha20-poly1305` | `cryptography` | Modern AEAD, fast on CPUs without AES-NI hardware acceleration. |
| **XOR Legacy** | `xor-legacy` | stdlib only | HMAC-SHA256 derived keystream with HMAC auth tag. Zero external dependencies. **Not recommended for production with sensitive data.** |

> **Auto-detection:** When `backend="auto"` is passed, AES-256-GCM is selected
> if the `cryptography` package is available; otherwise XOR Legacy is used with
> a warning. When no `backend` argument is provided at all, XOR Legacy is used
> for backward compatibility.

### Installing Crypto Extras

The three AEAD backends (AES-256-GCM, AES-256-GCM-SIV, ChaCha20-Poly1305) require
the `cryptography` package. Install it via the optional extra:

```bash
pip install crdt-merge[crypto]
```

The XOR Legacy backend uses only the Python standard library and is always available.

### Key Providers and Per-Field Derivation

Encryption keys are supplied through a `KeyProvider` interface. The built-in
`StaticKeyProvider` accepts a 32-byte master key and derives unique per-field
keys using HMAC-SHA256:

```
field_key = HMAC-SHA256(master_key, field_name)
```

This ensures that each field is encrypted with a different key, so compromising
one field's ciphertext does not reveal others.

```python
import secrets
from crdt_merge.encryption import StaticKeyProvider

master_key = secrets.token_bytes(32)  # 256-bit master key
provider = StaticKeyProvider(master_key)

# Each call derives a unique key for the given field name
email_key = provider.get_key("email")     # HMAC(master, "email")
salary_key = provider.get_key("salary")   # HMAC(master, "salary")
```

You can implement the abstract `KeyProvider` base class for custom key management
(e.g., fetching keys from a vault or KMS):

```python
from crdt_merge.encryption import KeyProvider

class VaultKeyProvider(KeyProvider):
    def get_key(self, field_name: str) -> bytes:
        return my_vault.get_field_key(field_name)  # 32 bytes
```

### Basic Encrypt / Decrypt

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

key = secrets.token_bytes(32)
provider = StaticKeyProvider(key)
em = EncryptedMerge(key_provider=provider, backend="auto")

# Encrypt a single field value
encrypted = em.encrypt_field("sensitive@email.com", "email")
print(encrypted)  # EncryptedValue(field='email', ct=3a7f1b02...)

# Decrypt it back
decrypted = em.decrypt_field(encrypted)
assert decrypted == "sensitive@email.com"
```

### Order-Preserving Tags

Every `EncryptedValue` carries an `order_tag` computed as:

```
order_tag = HMAC-SHA256(field_key, canonical_json(value))
```

Because the tag is deterministic for a given (key, value) pair, the standard
comparison operators (`<`, `>`, `==`) work on `EncryptedValue` objects. This
allows LWW, MaxWins, and MinWins strategies to resolve conflicts on encrypted
data **without decryption**.

```python
ev_a = em.encrypt_field(100, "score")
ev_b = em.encrypt_field(200, "score")

# Comparison works on ciphertext via order tags
assert ev_a < ev_b
assert ev_b > ev_a
```

### Bulk Record Encryption

Encrypt or decrypt specific fields (or all non-key fields) across a list of
records:

```python
records = [
    {"id": 1, "email": "alice@example.com", "salary": 90000},
    {"id": 2, "email": "bob@example.com",   "salary": 85000},
]

# Encrypt all non-key fields
encrypted_records = em.encrypt_records(records, key="id")

# Or encrypt only specific fields
encrypted_records = em.encrypt_records(records, fields=["email"], key="id")

# Decrypt — auto-detects __encrypted__ markers
plain_records = em.decrypt_records(encrypted_records)
```

### Encrypted Merge

Merge two sets of encrypted records directly. The merge uses order tags for
conflict resolution without ever decrypting the data:

```python
merged = em.merge_encrypted(
    left=encrypted_left,
    right=encrypted_right,
    key="id",
    schema=my_schema,  # optional MergeSchema
)
```

### Wire Format Versioning

Serialized `EncryptedValue` dicts include a version indicator:

- **v1 (legacy):** No `cipher` or `version` field. Used by the XOR Legacy
  backend for backward compatibility.
- **v2 (named cipher):** Includes `"cipher": "<backend-name>"` and
  `"version": 2`. Used by all AEAD backends (AES-256-GCM, AES-256-GCM-SIV,
  ChaCha20-Poly1305).

On decryption, `decrypt_field` automatically routes to the correct backend
based on the `cipher` metadata — v1 payloads always use XOR Legacy, v2 payloads
use the named backend. This means you can safely upgrade backends without
breaking decryption of existing data.

```python
ev = em.encrypt_field("hello", "greeting")
serialized = ev.to_dict()
# {
#   "__encrypted__": True,
#   "ciphertext": "...",
#   "nonce": "...",
#   "tag": "...",
#   "order_tag": "...",
#   "field_name": "greeting",
#   "cipher": "aes-256-gcm",   # v2 field
#   "version": 2                # v2 field
# }
```

### Custom Backends

Register your own backend by subclassing `CryptoBackend` and calling
`register_backend`:

```python
from crdt_merge.encryption import CryptoBackend, register_backend

class MyCustomBackend(CryptoBackend):
    name = "my-custom"

    def encrypt(self, key, plaintext, associated_data=None):
        ...  # return (ciphertext, nonce, tag)

    def decrypt(self, key, ciphertext, nonce, tag, associated_data=None):
        ...  # return plaintext bytes

register_backend("my-custom", MyCustomBackend)
```

---

## Key Rotation

Re-encrypt records from an old key to a new key with `rotate_key`. The method
decrypts each encrypted field with the old provider, then re-encrypts with the
new provider using the current backend:

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

old_key = secrets.token_bytes(32)
new_key = secrets.token_bytes(32)

old_provider = StaticKeyProvider(old_key)
new_provider = StaticKeyProvider(new_key)

em = EncryptedMerge(key_provider=new_provider, backend="aes-256-gcm")

rotated_records = em.rotate_key(
    records=encrypted_records,
    old_provider=old_provider,
    new_provider=new_provider,
    fields=["email", "salary"],  # optional: rotate specific fields only
)
```

> **Note:** `rotate_key` automatically detects the original cipher from each
> encrypted value's metadata, so you can safely rotate records that were
> encrypted with a different backend (e.g., migrating from XOR Legacy to
> AES-256-GCM).

---

## Role-Based Access Control (RBAC)

The `crdt_merge.rbac` module provides policy-based access control for merge
operations. It governs which nodes can perform which operations, on which
fields, and using which strategies.

### Permissions

Permissions are defined as a `Flag` enum, allowing bitwise combination:

| Permission | Description |
|------------|-------------|
| `READ` | Read record fields |
| `WRITE` | Write / update record fields |
| `MERGE` | Execute merge operations |
| `ADMIN` | Administrative actions |
| `UNMERGE` | Reverse / undo merge operations |
| `ENCRYPT` | Encrypt and decrypt fields |
| `AUDIT_READ` | Read audit log entries |

### Pre-Defined Roles

Roles bundle permissions into named groups:

| Role | Permissions |
|------|-------------|
| `READER` | `READ`, `AUDIT_READ` |
| `WRITER` | `READ`, `WRITE` |
| `MERGER` | `READ`, `WRITE`, `MERGE` |
| `ADMIN` | All permissions (`READ`, `WRITE`, `MERGE`, `ADMIN`, `UNMERGE`, `ENCRYPT`, `AUDIT_READ`) |

```python
from crdt_merge.rbac import READER, WRITER, MERGER, ADMIN, Permission

assert MERGER.has_permission(Permission.MERGE)
assert not MERGER.has_permission(Permission.ADMIN)
assert ADMIN.has_permission(Permission.ENCRYPT)
```

### Policies

A `Policy` binds a role to fine-grained access controls:

- **`allowed_fields`** — whitelist of accessible fields (`None` = all fields)
- **`allowed_strategies`** — whitelist of strategy class names (`None` = all)
- **`denied_fields`** — explicit deny set (**always wins** over `allowed_fields`)
- **`max_record_count`** — maximum number of input records per merge

```python
from crdt_merge.rbac import Policy, MERGER

policy = Policy(
    role=MERGER,
    allowed_fields={"id", "name", "email"},
    denied_fields={"secret_field"},
    allowed_strategies={"LWW", "MaxWins"},
    max_record_count=10000,
)
```

### RBACController

The `RBACController` is the central policy store and enforcement engine.
It is **thread-safe** — all mutations are guarded by an internal lock.

```python
from crdt_merge.rbac import RBACController, Policy, AccessContext, MERGER, Permission

rbac = RBACController()

# Register a policy for a node
policy = Policy(role=MERGER, denied_fields={"secret_field"})
rbac.add_policy("node-1", policy)

# Create an access context for runtime checks
ctx = AccessContext(node_id="node-1", role=MERGER)

# Check permissions
assert rbac.check_permission(ctx, Permission.MERGE)
assert rbac.check_permission(ctx, Permission.READ)
assert not rbac.check_permission(ctx, Permission.ADMIN)

# Check field-level access (denied_fields always wins)
assert rbac.check_field_access(ctx, "email", Permission.READ)
assert not rbac.check_field_access(ctx, "secret_field", Permission.READ)

# Check strategy access
assert rbac.check_strategy_access(ctx, "LWW")
```

### Enforcement Methods

`RBACController.enforce_merge()` filters records according to the node's policy
and raises `PermissionError` for violations:

```python
# Raises PermissionError if node lacks MERGE permission
# Raises PermissionError if records exceed max_record_count
# Strips fields the node is not allowed to READ
filtered = rbac.enforce_merge(ctx, records, schema=my_schema)
```

---

## SecureMerge

`SecureMerge` wraps `crdt_merge.merge()` with full RBAC enforcement in a
single call. It enforces permission, record-count, and strategy gates before
merging, then filters the output fields.

```python
from crdt_merge.rbac import SecureMerge, RBACController, Policy, AccessContext, MERGER

rbac = RBACController()
policy = Policy(role=MERGER, denied_fields={"internal_notes"})
rbac.add_policy("node-1", policy)

secure = SecureMerge(rbac)
ctx = AccessContext(node_id="node-1", role=MERGER)

left = [{"id": 1, "name": "Alice", "internal_notes": "VIP"}]
right = [{"id": 1, "name": "Alice B.", "internal_notes": "Standard"}]

# Merge with RBAC enforcement
result = secure.merge(left, right, key="id", context=ctx)
# result rows will NOT contain "internal_notes" (denied field)
```

The enforcement pipeline inside `SecureMerge.merge()` is:

1. **Permission gate** — node must have `MERGE` permission
2. **Record-count gate** — total records must not exceed `max_record_count`
3. **Strategy gate** — each strategy in the schema must be in `allowed_strategies`
4. **Merge execution** — calls `crdt_merge.merge()`
5. **Output filtering** — strips denied / non-allowed fields from results

If no `context` is provided, the merge proceeds without access checks for
backward compatibility.

---

## Audit Trails

The `crdt_merge.audit` module provides an immutable, append-only audit log
with **SHA-256 hash chaining**. Each entry links to the previous via its hash,
forming a verifiable chain similar to a blockchain.

### How It Works

```
 ┌──────────┐     ┌──────────┐     ┌──────────┐
 │ Entry #0 │────│ Entry #1 │────│ Entry #2 │
 │ prev:    │     │ prev:    │     │ prev:    │
 │ "genesis"│     │ hash(#0) │     │ hash(#1) │
 │ hash: H0 │     │ hash: H1 │     │ hash: H2 │
 └──────────┘     └──────────┘     └──────────┘
```

Each `AuditEntry` is a frozen (immutable) dataclass containing:
- `entry_id` — unique UUID4 identifier
- `timestamp` — wall-clock time of creation
- `operation` — type of operation (`merge`, `encrypt`, `decrypt`, `unmerge`, `key_rotate`, `custom`)
- `node_id` — identifier of the node that performed the operation
- `input_hash` — SHA-256 of the operation's input data
- `output_hash` — SHA-256 of the operation's output data
- `metadata` — arbitrary operation-specific details (record counts, schema, etc.)
- `prev_hash` — hash of the preceding entry (`"genesis"` for the first)
- `entry_hash` — SHA-256 computed over all identity fields

### Basic Usage

```python
from crdt_merge.audit import AuditLog

log = AuditLog(node_id="prod-1")

# Log a custom operation
entry = log.log_operation(
    "encrypt",
    input_data={"field": "email"},
    output_data={"status": "ok"},
    backend="aes-256-gcm",
)

# Log a merge operation (records metadata automatically)
entry = log.log_merge(
    left_records=left,
    right_records=right,
    result_records=result,
    schema=my_schema,
)
```

### AuditedMerge

`AuditedMerge` wraps `crdt_merge.merge()` and automatically logs every
invocation. It returns both the merge result and the audit entry:

```python
from crdt_merge.audit import AuditLog, AuditedMerge

log = AuditLog(node_id="prod-1")
am = AuditedMerge(audit_log=log, node_id="prod-1")

left = [{"id": 1, "name": "Alice", "score": 100}]
right = [{"id": 1, "name": "Alice", "score": 150}]

result, entry = am.merge(left, right, key="id")

print(entry.operation)    # "merge"
print(entry.node_id)      # "prod-1"
print(entry.metadata)     # {"left_count": 1, "right_count": 1, "result_count": 1, ...}
```

### Chain Verification

Verify the integrity of the entire hash chain at any time. If any entry has
been tampered with, `verify_chain()` returns `False`:

```python
assert log.verify_chain()  # True — chain is intact

print(f"Audit log contains {len(log)} entries")
```

### Filtering Entries

Query entries by operation type and/or time range:

```python
# Get all merge entries
merge_entries = log.get_entries(operation="merge")

# Get entries in a time window
import time
recent = log.get_entries(since=time.time() - 3600)  # last hour
```

### Export and Import

Export the log to JSON for archival or transfer to external audit systems.
Imported logs are automatically verified:

```python
# Export
json_str = log.export_log()
log.export_log(filepath="/path/to/audit-log.json")  # also writes to file

# Import (raises ValueError if chain verification fails)
restored_log = AuditLog.import_log(json_str)
assert restored_log.verify_chain()
```

---

## Compliance Integration

For regulated environments, crdt-merge includes a **Layer 6 compliance module**
that extends audit trails with framework-specific controls:

- **GDPR** — data subject access requests, right-to-erasure tracking
- **HIPAA** — protected health information access logging
- **SOX** — financial data integrity controls
- **EU AI Act** — algorithmic decision audit trails

See the [Compliance Guide](compliance-guide.md) for full details on configuring
compliance policies and generating audit reports.

---

## Best Practices

### Encryption
1. **Use AES-256-GCM or AES-256-GCM-SIV in production** — install `crdt-merge[crypto]`. The XOR Legacy backend is provided for zero-dependency environments and testing only.
2. **Prefer AES-256-GCM-SIV for CRDT workloads** — its nonce-misuse resistance provides an extra safety margin in distributed systems where nonce coordination is difficult.
3. **Use `backend="auto"`** to automatically select the best available backend.
4. **Rotate keys periodically** using `rotate_key()` — it handles cross-backend migration transparently.

### RBAC
5. **Use `ADMIN` sparingly** — prefer `MERGER` for regular merge operations. `ADMIN` grants all permissions including `UNMERGE` and `ENCRYPT`.
6. **Always set `denied_fields`** for sensitive columns that should never be exposed, even to privileged roles. Explicit deny always wins over allow.
7. **Use `SecureMerge`** instead of bare `crdt_merge.merge()` in any multi-tenant or networked environment.
8. **Set `max_record_count`** to prevent resource-exhaustion attacks via oversized merge payloads.

### Audit
9. **Always use `AuditedMerge`** in production to maintain a verifiable record of every merge operation.
10. **Store audit logs in append-only storage** — write exported JSON to immutable blob storage or a write-ahead log.
11. **Verify chain integrity on a schedule** — call `verify_chain()` periodically (e.g., hourly or after import) to detect tampering early.
12. **Export logs regularly** for long-term archival and external compliance tools.

### Defense in Depth
13. **Compose all three layers** for maximum protection:

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, SecureMerge, Policy, AccessContext, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge

# Layer 1: Encryption
provider = StaticKeyProvider(secrets.token_bytes(32))
em = EncryptedMerge(key_provider=provider, backend="auto")

# Layer 2: RBAC
rbac = RBACController()
rbac.add_policy("node-1", Policy(role=MERGER, denied_fields={"ssn"}))
secure = SecureMerge(rbac)

# Layer 3: Audit
log = AuditLog(node_id="node-1")
am = AuditedMerge(audit_log=log, node_id="node-1")

# Workflow: encrypt → merge with RBAC → audit
encrypted_left = em.encrypt_records(left, key="id")
encrypted_right = em.encrypt_records(right, key="id")

ctx = AccessContext(node_id="node-1", role=MERGER)
result, entry = am.merge(encrypted_left, encrypted_right, key="id")

assert log.verify_chain()
```
