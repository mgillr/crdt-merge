# Privacy-Preserving Merge: Merge Without Seeing the Data

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Fundamental Tension in Data Collaboration

Every collaborative data system faces the same problem: two parties want to merge their data, but neither trusts the other enough to share the raw values.

**Today's workarounds:**
- Trusted third party (eliminates the problem by moving the trust problem to a third node)
- Differential privacy (adds noise — approximate results, not exact)
- Homomorphic encryption (computationally intractable at scale)
- Secure multi-party computation (round-trip overhead per operation)

None of these let you run a **full CRDT merge** — with conflict resolution, provenance tracking, and convergence guarantees — on data that remains encrypted throughout the operation.

crdt-merge's `EncryptedMerge` does.

---

## How It Works: The Two-Layer Architecture Applied to Encryption

The same two-layer pattern that makes model merging CRDT-compliant applies here:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: EncryptedValue (CRDT-capable encrypted record) │
│                                                          │
│  • ciphertext: AES-256-GCM encrypted payload             │
│  • nonce: unique per encryption call                     │
│  • order_tag: deterministic HMAC over plaintext value    │
│  • field_name: per-field key derivation context          │
│                                                          │
│  merge() compares order_tags — never touches ciphertext  │
│  Convergence: same order_tags → same winner, always      │
└──────────────────────┬──────────────────────────────────┘
                       │ winner selected by order_tag
                       ┌─────────────────────────────────────────────────────────┐
│  Layer 2: EncryptedMerge (strategy over encrypted set)   │
│                                                          │
│  • 4 AEAD backends: AES-256-GCM, AES-GCM-SIV,           │
│    ChaCha20-Poly1305, XOR-legacy                         │
│  • Per-field key derivation (StaticKeyProvider + HKDF)   │
│  • Key rotation without re-sharing data                  │
│  • merge_encrypted() → fully CRDT-compliant on ciphertext│
└─────────────────────────────────────────────────────────┘
```

**The key insight:** Conflict resolution in a LWW (Last-Write-Wins) merge requires only a **comparison** between values, not the values themselves. The `order_tag` — a deterministic HMAC of the plaintext using the derived field key — enables comparison without decryption. The winner is selected, the losing ciphertext is discarded. The decrypted value is never needed.

---

## Quick Start

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

# Generate a 32-byte master key — keep this secret
master_key = secrets.token_bytes(32)
provider = StaticKeyProvider(master_key)
em = EncryptedMerge(provider)  # defaults to AES-256-GCM

# Encrypt individual fields
enc_value = em.encrypt_field("classified_data", "field_name")
print(enc_value.ciphertext)   # bytes — unreadable without key
print(enc_value.order_tag)    # deterministic HMAC — for comparison only
print(enc_value.nonce)        # unique per call — authenticated

# Decrypt
original = em.decrypt_field(enc_value)
assert original == "classified_data"
```

---

## Cookbook: All Supported Types

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

# Strings
assert em.decrypt_field(em.encrypt_field("hello world", "f")) == "hello world"

# Numbers
assert em.decrypt_field(em.encrypt_field(42, "f")) == 42
assert em.decrypt_field(em.encrypt_field(3.14, "f")) == 3.14

# Booleans
assert em.decrypt_field(em.encrypt_field(True, "f")) is True

# None
assert em.decrypt_field(em.encrypt_field(None, "f")) is None

# Lists
assert em.decrypt_field(em.encrypt_field([1, 2, 3], "f")) == [1, 2, 3]

# Nested dicts
val = {"patient_id": "P001", "diagnosis": ["A01", "B12"], "age": 34}
assert em.decrypt_field(em.encrypt_field(val, "f")) == val

# Unicode
assert em.decrypt_field(em.encrypt_field("日本語 العربية ", "f")) == "日本語 العربية "

# Large payloads
large = "x" * 100_000
assert em.decrypt_field(em.encrypt_field(large, "f")) == large
```

---

## Cookbook: Encrypting Records

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import secrets

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

# Encrypt all fields except the key
records = [
    {"id": "P001", "name": "Alice Chen", "diagnosis": "hypertension", "salary": 95000},
    {"id": "P002", "name": "Bob Smith", "diagnosis": "diabetes", "salary": 87000},
]
encrypted = em.encrypt_records(records, key="id")

# id is plaintext (needed for merge operations)
assert encrypted[0]["id"] == "P001"
# All other fields are encrypted dicts
assert encrypted[0]["name"]["__encrypted__"] is True
assert encrypted[0]["diagnosis"]["__encrypted__"] is True

# Decrypt back
decrypted = em.decrypt_records(encrypted)
assert decrypted[0]["name"] == "Alice Chen"
assert decrypted[1]["diagnosis"] == "diabetes"
```

---

## Cookbook: Selective Field Encryption

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import secrets

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

records = [
    {"id": "E001", "name": "Alice", "department": "Engineering", "salary": 95000, "email": "alice@co.com"}
]

# Encrypt only PII fields — leave non-sensitive fields plaintext
encrypted = em.encrypt_records(records, fields=["salary", "email"], key="id")

# Non-sensitive fields remain plaintext and searchable
assert encrypted[0]["name"] == "Alice"
assert encrypted[0]["department"] == "Engineering"

# Sensitive fields are encrypted
assert isinstance(encrypted[0]["salary"], dict)
assert encrypted[0]["salary"]["__encrypted__"] is True
assert isinstance(encrypted[0]["email"], dict)

# Decrypt only sensitive fields
decrypted = em.decrypt_records(encrypted)
assert decrypted[0]["salary"] == 95000
assert decrypted[0]["email"] == "alice@co.com"
```

---

## Cookbook: Merging Encrypted Records Without Decryption

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import secrets

master_key = secrets.token_bytes(32)
em = EncryptedMerge(StaticKeyProvider(master_key))

# Org A's encrypted records
records_a = em.encrypt_records([
    {"id": "C001", "revenue": 4_200_000, "risk_score": 0.3},
    {"id": "C002", "revenue": 1_800_000, "risk_score": 0.7},
], key="id")

# Org B's encrypted records (different values for overlapping keys)
records_b = em.encrypt_records([
    {"id": "C001", "revenue": 4_350_000, "risk_score": 0.25},  # updated value
    {"id": "C003", "revenue": 950_000,   "risk_score": 0.5},   # new record
], key="id")

# Merge happens entirely on encrypted data — order_tags compared, not ciphertext
merged = em.merge_encrypted(records_a, records_b, key="id")

# Three records: C001 (conflict resolved), C002 (unique to A), C003 (unique to B)
decrypted = em.decrypt_records(merged)
ids = {r["id"] for r in decrypted}
assert ids == {"C001", "C002", "C003"}

# C001 had a conflict — winner determined by order_tag (deterministic, not order of merge call)
c001 = next(r for r in decrypted if r["id"] == "C001")
assert c001["revenue"] in (4_200_000, 4_350_000)  # one wins, deterministically
```

---

## Scenario: Cross-Organisation Financial Data Reconciliation

Two banks want to reconcile customer risk scores without sharing the raw scores.

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, EncryptedValue
from crdt_merge.wire import serialize, deserialize
import secrets

# Each bank has their own key — they share ONLY the encrypted records
bank_a_key = secrets.token_bytes(32)
bank_b_key = secrets.token_bytes(32)

em_a = EncryptedMerge(StaticKeyProvider(bank_a_key))
em_b = EncryptedMerge(StaticKeyProvider(bank_b_key))

# Bank A: encrypts their customer risk data
bank_a_records = em_a.encrypt_records([
    {"customer_id": "C001", "risk_score": 0.72, "credit_limit": 50000},
    {"customer_id": "C002", "risk_score": 0.31, "credit_limit": 85000},
], key="customer_id")

# Bank B: encrypts their overlapping customer data
bank_b_records = em_b.encrypt_records([
    {"customer_id": "C001", "risk_score": 0.68, "credit_limit": 55000},  # disagreement
    {"customer_id": "C003", "risk_score": 0.45, "credit_limit": 30000},
], key="customer_id")

# Bank A can merge Bank B's records — but can only decrypt with their own key
# Bank B's records remain encrypted with Bank B's key
# The merge resolves conflicts using order_tags without needing decryption

# Note: For cross-org merge to fully work, a shared derived key or
# a neutral coordinator with a shared key is needed for the merge step.
# crdt-merge's KeyProvider abstraction makes this pluggable:

class SharedKeyProvider:
    """Neutral coordinator provides keys for shared fields only."""
    def get_key(self, field_name: str) -> bytes:
        # In practice: fetch from key escrow / HSM for field_name
        return secrets.token_bytes(32)  # placeholder
```

---

## Scenario: Healthcare Data Federation — HIPAA Compliance

100 hospitals share patient outcome data for research. Patient records cannot leave hospital boundaries.

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, EncryptedValue
from crdt_merge.provenance import merge_with_provenance
import secrets

# Research consortium provides a shared master key to all hospitals
# (in production: distributed via HSM or key ceremony)
consortium_key = secrets.token_bytes(32)
em = EncryptedMerge(StaticKeyProvider(consortium_key))

# Each hospital encrypts their outcome data locally before sharing
hospital_boston = em.encrypt_records([
    {"trial_id": "T001", "outcome": "positive", "drug_response": 0.87, "adverse": False},
    {"trial_id": "T002", "outcome": "partial",  "drug_response": 0.54, "adverse": True},
], key="trial_id")

hospital_london = em.encrypt_records([
    {"trial_id": "T001", "outcome": "positive", "drug_response": 0.91, "adverse": False},
    {"trial_id": "T003", "outcome": "negative", "drug_response": 0.22, "adverse": True},
], key="trial_id")

# Central research server merges encrypted records
# Never decrypts — only uses order_tags to resolve conflicts
merged_encrypted = em.merge_encrypted(hospital_boston, hospital_london, key="trial_id")

# Research team decrypts the final merged dataset
# Patient-identifiable raw records never transmitted in plaintext
final_results = em.decrypt_records(merged_encrypted)

print(f"Merged {len(final_results)} trial results")
for result in final_results:
    print(f"  Trial {result['trial_id']}: {result['outcome']}, response={result['drug_response']}")
```

---

## Scenario: Multi-Party Salary Benchmarking

HR departments at 10 companies benchmark compensation data without revealing actual salaries.

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.strategies import MergeSchema, MaxWins, LWW
import secrets

# Neutral benchmarking firm provides the shared key
benchmark_key = secrets.token_bytes(32)
em = EncryptedMerge(StaticKeyProvider(benchmark_key))

def encrypt_company_data(company_data: list) -> list:
    """Each company calls this locally before submitting."""
    return em.encrypt_records(company_data, fields=["salary", "bonus"], key="role_id")

# Company A — tech company
company_a = encrypt_company_data([
    {"role_id": "SWE-L4", "salary": 145000, "bonus": 20000, "region": "SF"},
    {"role_id": "SWE-L5", "salary": 185000, "bonus": 35000, "region": "SF"},
])

# Company B — fintech
company_b = encrypt_company_data([
    {"role_id": "SWE-L4", "salary": 155000, "bonus": 25000, "region": "NYC"},
    {"role_id": "SWE-L6", "salary": 220000, "bonus": 50000, "region": "NYC"},
])

# Benchmarking firm merges — sees only encrypted salary values
merged = em.merge_encrypted(company_a, company_b, key="role_id")

# Benchmarking firm publishes decrypted medians/percentiles — not raw salaries
results = em.decrypt_records(merged)
# In practice: apply statistical aggregation here, not raw values
```

---

## Key Rotation: Changing Encryption Keys Without Data Loss

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, EncryptedValue
import secrets

# Current key
old_key = secrets.token_bytes(32)
old_provider = StaticKeyProvider(old_key)
em_old = EncryptedMerge(old_provider)

records = em_old.encrypt_records([
    {"id": "1", "secret": "classified", "value": 42},
    {"id": "2", "secret": "restricted", "value": 99},
], key="id")

# Rotate to new key — decrypt with old, re-encrypt with new
new_key = secrets.token_bytes(32)
new_provider = StaticKeyProvider(new_key)
em_new = EncryptedMerge(new_provider)

rotated = em_new.rotate_key(records, old_provider, new_provider)

# Old key no longer works
try:
    em_old.decrypt_records(rotated)
    assert False, "should have raised"
except ValueError as e:
    assert "Authentication failed" in str(e)

# New key works
decrypted = em_new.decrypt_records(rotated)
assert decrypted[0]["secret"] == "classified"
assert decrypted[1]["value"] == 99
```

---

## Cookbook: Selective Field Rotation

Rotate only the most sensitive fields while leaving others unchanged:

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, EncryptedValue
import secrets

old_provider = StaticKeyProvider(secrets.token_bytes(32))
new_provider = StaticKeyProvider(secrets.token_bytes(32))

records = EncryptedMerge(old_provider).encrypt_records(
    [{"id": "1", "ssn": "123-45-6789", "name": "Alice", "score": 95}],
    fields=["ssn", "name", "score"],
    key="id"
)

# Rotate only the SSN (most sensitive) — name and score keep old key
rotated = EncryptedMerge(new_provider).rotate_key(
    records, old_provider, new_provider, fields=["ssn"]
)

# SSN decrypts with new key
ssn_ev = EncryptedValue.from_dict(rotated[0]["ssn"])
assert EncryptedMerge(new_provider).decrypt_field(ssn_ev) == "123-45-6789"

# Name still requires old key
name_ev = EncryptedValue.from_dict(rotated[0]["name"])
assert EncryptedMerge(old_provider).decrypt_field(name_ev) == "Alice"
```

---

## Choosing an Encryption Backend

crdt-merge ships with four AEAD (Authenticated Encryption with Associated Data) backends:

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import secrets

key = secrets.token_bytes(32)
provider = StaticKeyProvider(key)

# AES-256-GCM — default, widely supported, hardware-accelerated on most CPUs
em_gcm = EncryptedMerge(provider, backend="aes-256-gcm")

# AES-GCM-SIV — nonce misuse resistant (safer if nonce reuse is a risk)
em_siv = EncryptedMerge(provider, backend="aes-gcm-siv")

# ChaCha20-Poly1305 — faster on systems without AES hardware acceleration
em_chacha = EncryptedMerge(provider, backend="chacha20-poly1305")

# XOR-legacy — for testing/interop only, NOT for production
em_xor = EncryptedMerge(provider, backend="xor-legacy")

# "auto" — selects AES-256-GCM if cryptography package is installed
em_auto = EncryptedMerge(provider)  # backend="auto" is default
```

| Backend | Best For | Notes |
|---|---|---|
| `aes-256-gcm` | General production use | Hardware-accelerated, standard |
| `aes-gcm-siv` | High-nonce-volume systems | Resistant to nonce reuse |
| `chacha20-poly1305` | Embedded / non-x86 | Fast in software |
| `xor-legacy` | Testing only | Never use in production |

**Install AEAD backends:**
```bash
pip install crdt-merge[crypto]
```

---

## Wire Protocol: Serializing Encrypted Values

`EncryptedValue` has a stable wire format for cross-system interop:

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider, EncryptedValue
import secrets, json

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

# Serialize to dict (JSON-safe)
ev = em.encrypt_field({"patient_data": [1, 2, 3]}, "payload")
wire = ev.to_dict()
# {
#   "__encrypted__": true,
#   "ciphertext": "base64...",
#   "nonce": "base64...",
#   "tag": "base64...",
#   "order_tag": "hex...",
#   "field_name": "payload",
#   "cipher": "aes-256-gcm",
#   "version": 2
# }

# Transmit as JSON
json_str = json.dumps(wire)

# Deserialize on the receiving side
restored = EncryptedValue.from_dict(json.loads(json_str))
decrypted = em.decrypt_field(restored)
assert decrypted == {"patient_data": [1, 2, 3]}
```

---

## Security Properties

| Property | Guarantee |
|---|---|
| **Authenticated encryption** | AES-256-GCM provides integrity + confidentiality — tampered ciphertext raises `ValueError("Authentication failed")` |
| **Per-field key isolation** | Each field gets its own derived key via HKDF — compromising one field's key does not compromise others |
| **Nonce uniqueness** | Fresh random nonce per `encrypt_field()` call — same value encrypted twice produces different ciphertext |
| **Deterministic order tags** | `order_tag` is HMAC(field_key, canonical_repr(value)) — same value always produces same tag, enabling CRDT comparison |
| **No cross-field decryption** | An `EncryptedValue` encrypted for field `"alpha"` cannot be decrypted as field `"beta"` |
| **Key rotation without downtime** | `rotate_key()` re-encrypts in place — no intermediate plaintext stored |

---

## Integration with Other crdt-merge Modules

### With ProvenanceLog

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.provenance import merge_with_provenance
import secrets

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

# Encrypt sensitive fields, leave provenance-trackable key plaintext
enc_a = em.encrypt_records([{"id": "1", "value": 100}], key="id")
enc_b = em.encrypt_records([{"id": "1", "value": 200}], key="id")

# Merge encrypted records — conflict resolved on order_tag
merged = em.merge_encrypted(enc_a, enc_b, key="id")

# Decrypt for provenance tracking
dec_a = em.decrypt_records(enc_a)
dec_b = em.decrypt_records(enc_b)
merged_plain, log = merge_with_provenance(dec_a, dec_b, key="id")
print(f"Conflicts resolved: {log.total_conflicts}")
```

### With AuditLog

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.audit import AuditLog, AuditedMerge
import secrets

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))
audit = AuditLog(node_id="hospital-node-1")

# Audit the encrypt/decrypt operations
enc = em.encrypt_field("patient_record", "data")
audit._append("encrypt", input_hash="hash_of_plain", output_hash=enc.order_tag)

# Tamper-evident chain — verify nothing was altered
assert audit.verify_chain()
```

### With GDPRForget

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.unmerge import GDPRForget
import secrets

# Encryption + GDPR unmerge = complete right-to-be-forgotten
em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))

records = em.encrypt_records([
    {"id": "user_42", "name": "Alice", "email": "alice@example.com", "score": 95}
], key="id")

# To forget: decrypt, remove from dataset, re-encrypt remainder
# See right-to-forget-in-ai.md for the full unmerge workflow
```

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [API Reference — EncryptedMerge](../api-reference/enterprise/encryption.md)
- [Security Guide](../guides/security-guide.md)
