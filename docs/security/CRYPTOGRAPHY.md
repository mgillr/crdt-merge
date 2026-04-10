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

## Defined Backends (Not Yet Hardened)

### Ed25519

The Ed25519 adapter (`e4/resilience/signature_schemes.py`) provides
asymmetric signatures with per-peer keypairs. Each peer signs evidence
with their private key; other peers verify using the public key.

**Current status:** The interface is defined and the adapter compiles,
but it has not been hardened for production. Specifically:
- Key generation uses Python's `cryptography` library (adequate)
- Key storage and rotation are not implemented
- The adapter has unit tests but no adversarial testing

### Post-Quantum (Dilithium)

The post-quantum adapter provides lattice-based signatures resistant
to quantum computing attacks. It follows the NIST FIPS 204 standard.

**Current status:** Interface defined. Depends on a PQ cryptography
library that is not yet stable. This is a forward-looking placeholder.

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
