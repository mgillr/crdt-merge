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

Used when no registry is configured + cryptography not available, or as an explicit shared-secret backend. Provides integrity but not non-repudiation.

### DilithiumLite (DEPRECATED for PQ)

**Not post-quantum despite the name.** This is a hash-based construction using SHAKE-256 that was kept for backward compatibility. Security level is 128 bits classical, and it would degrade under Grover's algorithm. Use `Dilithium3Scheme` for real PQ security.

## Selection Guide

| Deployment | Required level | Recommended backend |
|---|---|---|
| Closed federation, single org | Integrity only | HMAC-SHA256 (default) |
| Development / testing | Minimal | Stub (default, no configuration) |
| Multi-org production | Non-repudiation | Ed25519 (`[crypto]`) |
| Regulated industry | Non-repudiation | Ed25519 (`[crypto]`) |
| Long-lived attestations | PQ resistance | ML-DSA-65 (`[security]`) |
| Government / defense | FIPS / PQ | ML-DSA-65 (`[security]`) |

## Upgrade Path

Upgrading from HMAC-SHA256 to Ed25519 requires:

1. Generate a keypair per peer (one-time setup)
2. Set `CRDT_E4_SIGNATURE_SCHEME=ed25519` environment variable
3. Distribute public keys to all peers (out-of-band)

No E4 logic changes. No API changes. The trust lattice, evidence
records, and Merkle trees work identically regardless of backend.

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
| Single machine / local | HMAC-SHA256 (default) |
| Closed federation (trusted peers) | HMAC-SHA256 |
| Open federation | Ed25519 (when hardened) |
| Long-term archival / compliance | Ed25519 + key rotation |
| Post-quantum threat model | Dilithium (when stable) |
