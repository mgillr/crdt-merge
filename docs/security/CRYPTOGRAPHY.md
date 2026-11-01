# Cryptographic Architecture

## Overview

crdt-merge uses cryptographic primitives for two purposes:

1. **Merkle provenance:** SHA-256 hash trees that bind data records
   to their causal history, enabling tamper detection.
2. **Trust evidence authentication:** Signing observations about peer
   behaviour to prevent evidence forgery.

## SignatureScheme Interface

All cryptographic signing in E4 goes through the `SignatureScheme`
abstract interface:

```python
class SignatureScheme(ABC):
    @abstractmethod
    def sign(self, message: bytes) -> bytes: ...

    @abstractmethod
    def verify(self, message: bytes, signature: bytes) -> bool: ...

    @abstractmethod
    def public_key(self) -> bytes: ...
```

This abstraction allows the signing backend to be swapped without
changing any E4 logic.

## Current Backend: HMAC-SHA256

The default backend uses HMAC-SHA256 with a shared secret. This
provides message authentication (proof that a message was produced by
someone holding the secret) but not non-repudiation (any holder of the
secret can produce valid signatures).

**When HMAC-SHA256 is sufficient:**
- Closed federations where all peers share a deployment secret
- Single-organisation deployments
- Development and testing

**When HMAC-SHA256 is insufficient:**
- Open federations where peers do not share secrets
- Scenarios requiring non-repudiation (provable attribution)
- Multi-organisation deployments with trust boundaries

## Production Backends (v0.9.6)

### Ed25519 (Asymmetric, Production Ready)

Real Ed25519 signatures via the `cryptography` library. Available when `crdt-merge[crypto]` is installed and a peer key registry is configured.

**What it protects:**
- PCO signatures -- prevents forgery of operation attestations
- Observer signatures on `TrustEvidence` -- prevents spoofed accusations
- Revocation entries -- prevents unauthorized key revocation
- KeyPair sign/verify operations in the key manager

**How to enable:**

```python
from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification

class Registry:
    def __init__(self):
        self._keys = {}
    def register(self, peer_id, public_key):
        self._keys[peer_id] = public_key
    def get_public_key(self, peer_id):
        return self._keys.get(peer_id)

reg = Registry()
reg.register("alice", alice_public_key_32_bytes)
configure_ed25519_verification(reg)
configure_evidence_verification(reg)
```

Without a registry, behaviour falls back to v0.9.5 stub (length check only) for backward compatibility.

**Verification cost:**
- Ed25519 verify: ~100μs per signature on modern hardware
- Full PCO verification at level 0: signature + hash comparison
- Full PCO verification at level 2: signature + Merkle + clock + trust derivation

### ML-DSA-65 (Post-Quantum, Production Ready)

Real NIST-standardised Dilithium3 (aka ML-DSA-65) via liboqs. This is the lattice-based signature scheme selected by NIST for FIPS 204.

**What it protects:**
- Long-lived signatures that must survive the arrival of fault-tolerant quantum computers
- Trust evidence and revocations where non-repudiation must extend beyond ~15 years

**How to enable:**

```bash
pip install crdt-merge[security]
```

```python
from crdt_merge.e4.resilience.pq_signatures import Dilithium3Scheme, has_real_pq

if has_real_pq():
    scheme = Dilithium3Scheme()
    private_key, public_key = scheme.generate_keypair()
    signature = scheme.sign(private_key, message)
    assert scheme.verify(public_key, message, signature)
```

**Signature sizes:**
- Public key: 1952 bytes
- Signature: 3293 bytes
- Security level: 192 bits (NIST Level 3)

### HMAC-SHA256 (Symmetric, Fallback)

A shared-secret MAC (`HmacScheme`), available only by constructing it explicitly: it is not registered by default and is not the classical half of `HybridScheme` (Ed25519 is). No verification path falls back to HMAC. Provides integrity between holders of the secret, not non-repudiation.

`KeyPair` (E4 key manager) never selects HMAC implicitly. Keys are Ed25519 by default, and `cryptography` is a core dependency. `generate`, `sign` and `verify` still raise `Ed25519Unavailable` if it is missing, and `verify` on an Ed25519 key accepts only a valid Ed25519 signature. Every key carries its `scheme`, which is bound into its `key_id`. Exchange an Ed25519 key with `export_public()` and rebuild it with `KeyPair.from_public(public_key, scheme)`; building a key from public bytes without a scheme is refused, and `PeerKeyRegistry` refuses a key whose scheme differs from the one recorded for that peer.

HMAC mode (`scheme="hmac-sha256"`) is opt-in and is a shared-secret MAC, not a signature: whoever holds the key can create valid tags. An HMAC key must never be distributed as a public key, and `export_public()` refuses it. Both parties build it with `KeyPair.from_shared_secret(secret)` from a secret agreed out of band, so `KeyManager.verify_peer` for an HMAC peer uses that secret and never a key received from the peer.

### DilithiumLite (DEPRECATED for PQ)

**Not post-quantum despite the name.** This is a hash-based construction using SHAKE-256 that was kept for backward compatibility. Security level is 128 bits classical, and it would degrade under Grover's algorithm. Use `Dilithium3Scheme` for real PQ security.

## Selection Guide

| Deployment | Required level | Recommended backend |
|---|---|---|
| Closed federation, single org | Integrity only | Ed25519 with a key registry; HMAC-SHA256 only as an explicit shared secret |
| Development / testing | Minimal | Explicit unsigned mode (`allow_unsigned=True`, `allow_unauthenticated=True`) |
| Multi-org production | Non-repudiation | Ed25519 |
| Regulated industry | Non-repudiation | Ed25519 |
| Long-lived attestations | PQ resistance | ML-DSA-65 (`[security]`) |
| Government / defense | FIPS / PQ | ML-DSA-65 (`[security]`) |

## Upgrade Path

Ed25519 is the default and `cryptography` is a core dependency. To turn
verification on:

1. Generate a keypair per peer (one-time setup)
2. Distribute public keys to all peers out of band (`KeyPair.export_public()` / `KeyPair.from_public()`)
3. Call `configure_ed25519_verification(registry)` and `configure_evidence_verification(registry)`

Until step 3, verification raises `SignatureVerificationNotConfigured`
rather than accepting anything.

## Merkle Hashing

All Merkle tree operations use SHA-256 via Python's `hashlib`. This
is not configurable and does not use the `SignatureScheme` interface
(hashing is not signing).

Content fingerprinting in non-security contexts (gossip budget
deduplication, probabilistic set membership) uses MD5 with
`usedforsecurity=False` to document that these are not security-
critical hash computations.

## Recommendations for Production Deployment

| Deployment Type | Recommended Backend |
|-----------------|---------------------|
| Single machine / local | Ed25519 (default) |
| Closed federation (trusted peers) | Ed25519, or HMAC-SHA256 as an explicit shared secret |
| Open federation | Ed25519 |
| Long-term archival / compliance | Ed25519 + key rotation |
| Post-quantum threat model | Dilithium (when stable) |
