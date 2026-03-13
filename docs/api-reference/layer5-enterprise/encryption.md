# crdt_merge.encryption — Field-Level Encryption with Pluggable Backends

> **Module**: `crdt_merge/encryption.py` | **Layer**: 5 — Enterprise | **Version**: 0.9.3

---

## Overview

Provides field-level authenticated encryption for CRDT merge operations with pluggable crypto backends. Encrypted fields carry HMAC-SHA256 order-preserving tags that enable LWW / MaxWins / MinWins strategy resolution on encrypted data without decryption. The module supports four backends: a zero-dependency XOR legacy backend (default), and three AEAD ciphers (AES-256-GCM, AES-256-GCM-SIV, ChaCha20-Poly1305) via the optional `cryptography` package.

---

## Quick Start

```python
import os
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

# Create a key provider with a 32-byte master key
key = os.urandom(32)
kp = StaticKeyProvider(key)

# Create the encrypted merge layer (uses XOR legacy backend by default)
em = EncryptedMerge(kp)

# Encrypt individual fields
encrypted = em.encrypt_field("Alice", "name")
print(encrypted)  # EncryptedValue(field='name', ct=...)

# Decrypt
decrypted = em.decrypt_field(encrypted)
print(decrypted)  # "Alice"

# Bulk encrypt/decrypt records
records = [{"id": 1, "name": "Alice", "salary": 100000}]
enc_records = em.encrypt_records(records, fields=["name", "salary"], key="id")
dec_records = em.decrypt_records(enc_records)
```

---

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `_NONCE_BYTES` | `16` | Nonce length in bytes for the XOR legacy backend. |
| `_KEY_BYTES` | `32` | Required key length in bytes. |
| `_BLOCK_BYTES` | `32` | HMAC-SHA256 output size (block size for keystream). |

---

## Classes

### `CryptoBackend` *(ABC)*

Abstract base class for cryptographic backends. All backends must implement `encrypt()` and `decrypt()`.

```python
class CryptoBackend(ABC):
    name: str  # e.g. "aes-256-gcm"

    @abstractmethod
    def encrypt(self, key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> Tuple[bytes, bytes, bytes]: ...

    @abstractmethod
    def decrypt(self, key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes, associated_data: bytes | None = None) -> bytes: ...
```

**Abstract Methods:**

#### `encrypt(key, plaintext, associated_data=None) → Tuple[bytes, bytes, bytes]`

Encrypt `plaintext` with `key`. Returns `(ciphertext, nonce, tag)`.

#### `decrypt(key, ciphertext, nonce, tag, associated_data=None) → bytes`

Decrypt `ciphertext` with `key`. Returns plaintext bytes. Raises `ValueError` on authentication failure.

---

### `XORLegacyBackend`

HMAC-SHA256 derived XOR keystream with HMAC auth tag. **Stdlib only — zero external dependencies.**

```python
class XORLegacyBackend(CryptoBackend):
    name = "xor-legacy"
```

> ⚠️ This is a non-standard construction. For production systems with sensitive data, use an AEAD backend (requires the `cryptography` package).

---

### `AES256GCMBackend`

AES-256-GCM via the `cryptography` package. Industry-standard AEAD cipher.

```python
class AES256GCMBackend(CryptoBackend):
    name = "aes-256-gcm"
```

Requires: `pip install crdt-merge[crypto]`

---

### `AESGCMSIVBackend`

AES-256-GCM-SIV — nonce-misuse-resistant AEAD, ideal for CRDTs where nonce reuse is a risk.

```python
class AESGCMSIVBackend(CryptoBackend):
    name = "aes-256-gcm-siv"
```

Requires: `pip install crdt-merge[crypto]`

---

### `ChaCha20Poly1305Backend`

ChaCha20-Poly1305 AEAD. Modern cipher, fast on CPUs without AES-NI hardware acceleration.

```python
class ChaCha20Poly1305Backend(CryptoBackend):
    name = "chacha20-poly1305"
```

Requires: `pip install crdt-merge[crypto]`

---

### `EncryptedValue`

Container for an encrypted field value with order-preserving comparison tag. Uses `__slots__` for memory efficiency.

```python
class EncryptedValue:
    __slots__ = ("ciphertext", "nonce", "tag", "order_tag", "field_name", "cipher")

    def __init__(
        self,
        ciphertext: bytes,
        nonce: bytes,
        tag: bytes,
        field_name: str,
        order_tag: bytes = b"",
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `ciphertext` | `bytes` | *(required)* | The encrypted payload bytes. |
| `nonce` | `bytes` | *(required)* | Nonce / IV used during encryption. |
| `tag` | `bytes` | *(required)* | Authentication tag produced by the cipher. |
| `field_name` | `str` | *(required)* | Name of the source field (used for key derivation on decrypt). |
| `order_tag` | `bytes` | `b""` | HMAC-based tag enabling order comparisons on ciphertext. |

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `cipher` | `Optional[str]` | Backend cipher name. `None` for v1/legacy wire format, set for v2. |

**Comparison operators:** `<`, `>`, `<=`, `>=`, `==` — all operate on `order_tag`, enabling LWW/MaxWins/MinWins on encrypted values.

**Methods:**

#### `to_dict() → Dict[str, str]`

Serialize to a JSON-safe dict with base64-encoded byte fields. Includes an `__encrypted__` marker for auto-detection.

**Returns:** `Dict[str, str]` — Serialized representation.

---

#### `from_dict(d: Dict[str, Any]) → EncryptedValue` *(classmethod)*

Deserialize from a dict produced by `to_dict()`.

**Parameters:**
- `d` (`Dict[str, Any]`): Dictionary with base64-encoded fields.

**Returns:** `EncryptedValue` — Reconstructed instance.

**Example:**
```python
ev = em.encrypt_field(42, "score")
serialized = ev.to_dict()
restored = EncryptedValue.from_dict(serialized)
assert em.decrypt_field(restored) == 42
```

---

### `KeyProvider` *(ABC)*

Abstract base class for key providers.

```python
class KeyProvider(ABC):
    @abstractmethod
    def get_key(self, field_name: str) -> bytes: ...
```

#### `get_key(field_name: str) → bytes`

Return a 32-byte encryption key for the given field name.

---

### `StaticKeyProvider`

Single master key with per-field key derivation via HMAC.

```python
class StaticKeyProvider(KeyProvider):
    def __init__(self, key: bytes) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `key` | `bytes` | *(required)* | Raw master key bytes. Must be at least 32 bytes; only the first 32 are used. |

**Raises:** `ValueError` if key is shorter than 32 bytes.

#### `get_key(field_name: str) → bytes`

Derive a field-specific 32-byte key: `HMAC(master_key, field_name)`.

**Example:**
```python
import os
from crdt_merge.encryption import StaticKeyProvider

master = os.urandom(32)
kp = StaticKeyProvider(master)
field_key = kp.get_key("salary")  # 32 bytes, deterministic per field
```

---

### `EncryptedMerge`

Field-level encryption layer for CRDT merge operations. Encrypts individual fields while preserving order-comparable tags so that strategies like LWW, MaxWins, and MinWins can resolve conflicts without decrypting the underlying data.

```python
class EncryptedMerge:
    def __init__(
        self,
        key_provider: KeyProvider,
        *,
        backend: str = _BACKEND_UNSET,
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `key_provider` | `KeyProvider` | *(required)* | A `KeyProvider` used to obtain per-field encryption keys. |
| `backend` | `str` | *(unset → xor-legacy)* | Crypto backend name. Use `"auto"` to select the best available backend. When omitted, XOR legacy is used for backward compatibility. |

**Backend selection logic:**
- **Omitted** (default): Uses `XORLegacyBackend` with a one-time `UserWarning`.
- `"auto"`: Uses `AES256GCMBackend` if `cryptography` is installed, otherwise falls back to XOR legacy with a warning.
- **Explicit name** (e.g. `"aes-256-gcm"`): Uses the named backend from the registry.

**Methods:**

#### `encrypt_field(value: Any, field_name: str) → EncryptedValue`

Encrypt a single field value with authenticated encryption.

**Parameters:**
- `value` (`Any`): The value to encrypt (JSON-serializable).
- `field_name` (`str`): Field name (used for per-field key derivation).

**Returns:** `EncryptedValue` — Carrying ciphertext, nonce, auth tag, and order-preserving comparison tag.

---

#### `decrypt_field(encrypted: EncryptedValue) → Any`

Decrypt and verify an `EncryptedValue`. Automatically routes to the correct backend based on the `cipher` metadata on the value.

**Parameters:**
- `encrypted` (`EncryptedValue`): The encrypted value to decrypt.

**Returns:** `Any` — The original plaintext value.

**Raises:** `ValueError` if the authentication tag does not match (tampered or wrong key).

---

#### `encrypt_records(records, fields=None, key="id") → List[Dict[str, Any]]`

Encrypt specified fields (or all non-key fields) in each record.

**Parameters:**
- `records` (`List[Dict[str, Any]]`): Input records.
- `fields` (`Optional[List[str]]`): Field names to encrypt. If `None`, all non-key fields are encrypted.
- `key` (`str`): Key field name to exclude from encryption. Default: `"id"`.

**Returns:** `List[Dict[str, Any]]` — New records with `EncryptedValue.to_dict()` representations replacing plaintext values.

---

#### `decrypt_records(records, fields=None) → List[Dict[str, Any]]`

Decrypt encrypted fields in each record. Automatically detects `EncryptedValue` dicts via the `__encrypted__` marker, or operates only on specified fields.

**Parameters:**
- `records` (`List[Dict[str, Any]]`): Records with encrypted fields.
- `fields` (`Optional[List[str]]`): Specific fields to decrypt. If `None`, all detected encrypted fields are decrypted.

**Returns:** `List[Dict[str, Any]]` — Records with plaintext values restored.

---

#### `merge_encrypted(left, right, key, schema=None) → List[Dict[str, Any]]`

Merge two sets of encrypted records using order-tags for strategy resolution. Records should already have encrypted fields (as `EncryptedValue` dicts).

**Parameters:**
- `left` (`List[Dict[str, Any]]`): Left encrypted records.
- `right` (`List[Dict[str, Any]]`): Right encrypted records.
- `key` (`str`): Key column name.
- `schema` (`Optional[MergeSchema]`): Optional merge schema.

**Returns:** `List[Dict[str, Any]]` — Merged encrypted records.

---

#### `rotate_key(records, old_provider, new_provider, fields=None) → List[Dict[str, Any]]`

Re-encrypt records from `old_provider` to `new_provider`. Decrypts each encrypted field with the old key, then re-encrypts with the new key.

**Parameters:**
- `records` (`List[Dict[str, Any]]`): Records with encrypted fields.
- `old_provider` (`KeyProvider`): Previous key provider for decryption.
- `new_provider` (`KeyProvider`): New key provider for re-encryption.
- `fields` (`Optional[List[str]]`): Specific fields to rotate. If `None`, all encrypted fields are rotated.

**Returns:** `List[Dict[str, Any]]` — Records re-encrypted with the new key.

**Example:**
```python
import os
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

old_key = os.urandom(32)
new_key = os.urandom(32)

em = EncryptedMerge(StaticKeyProvider(old_key))
records = [{"id": 1, "name": "Alice", "salary": 100000}]
encrypted = em.encrypt_records(records, key="id")

# Rotate to new key
rotated = em.rotate_key(
    encrypted,
    old_provider=StaticKeyProvider(old_key),
    new_provider=StaticKeyProvider(new_key),
)

# Decrypt with new key
em_new = EncryptedMerge(StaticKeyProvider(new_key))
decrypted = em_new.decrypt_records(rotated)
print(decrypted)  # [{"id": 1, "name": "Alice", "salary": 100000}]
```

---

## Module-Level Functions

### `register_backend(name: str, cls: type) → None`

Register a crypto backend class under the given name.

**Parameters:**
- `name` (`str`): Name to register (e.g. `"my-custom-aead"`).
- `cls` (`type`): A `CryptoBackend` subclass.

---

### `get_backend(name: str) → CryptoBackend`

Return a new instance of the backend registered under `name`.

**Parameters:**
- `name` (`str`): Registered backend name.

**Returns:** `CryptoBackend` — A new backend instance.

**Raises:** `ValueError` if `name` is not registered.

**Example:**
```python
from crdt_merge.encryption import get_backend

backend = get_backend("xor-legacy")  # always available
print(backend.name)  # "xor-legacy"
```

---

## Built-in Backend Registration

The following backends are registered at module load time:

| Name | Class | Dependency |
|------|-------|------------|
| `"xor-legacy"` | `XORLegacyBackend` | None (stdlib only) |
| `"aes-256-gcm"` | `AES256GCMBackend` | `cryptography` |
| `"aes-256-gcm-siv"` | `AESGCMSIVBackend` | `cryptography` |
| `"chacha20-poly1305"` | `ChaCha20Poly1305Backend` | `cryptography` |

AEAD backends are only registered if the `cryptography` package is installed. Install with:

```bash
pip install crdt-merge[crypto]
```
