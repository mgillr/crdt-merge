# E4 Cryptographic Hardening Cookbook

> New in v0.9.6. Real Ed25519 and NIST ML-DSA-65 post-quantum signatures.

---

## 1. Install the crypto extras

```bash
pip install crdt-merge[crypto]    # Ed25519 via cryptography
pip install crdt-merge[security]  # Ed25519 + ML-DSA-65 post-quantum
```

---

## 2. Enable real Ed25519 verification

Verification is fail-closed. Without a peer key registry, verifying a PCO signature or a piece of evidence raises `SignatureVerificationNotConfigured`. Configure a registry to verify: PCO signatures, evidence observer signatures and the attestation signatures inside equivocation proofs are then all checked as Ed25519 under the registered key, and there is no HMAC or embedded-key fallback.

```python
from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification
from cryptography.hazmat.primitives.asymmetric import ed25519


class PeerRegistry:
    """Minimal in-memory registry -- replace with your production store."""

    def __init__(self):
        self._keys = {}

    def register(self, peer_id: str, public_key: bytes):
        self._keys[peer_id] = public_key

    def get_public_key(self, peer_id: str):
        return self._keys.get(peer_id)


# Each peer generates a real Ed25519 keypair
alice_key = ed25519.Ed25519PrivateKey.generate()
alice_pub = alice_key.public_key().public_bytes_raw()  # 32 bytes

registry = PeerRegistry()
registry.register("alice", alice_pub)
# ... register all peers ...

configure_ed25519_verification(registry)
configure_evidence_verification(registry)
```

Now every PCO signature and every evidence submission is verified cryptographically. Forged signatures are rejected.

---

## 3. Sign evidence as an observer

```python
from crdt_merge.e4.proof_evidence import TrustEvidence, pack_delta_proof

evidence = TrustEvidence.create(
    observer="alice",
    target="eve",
    evidence_type="invalid_delta",
    dimension="integrity",
    amount=0.1,
    proof=pack_delta_proof(expected_hash, delta_bytes),
    observer_signing_fn=lambda payload: alice_key.sign(payload),
)

# With registry configured, verification enforces observer signature
assert evidence.verify(require_observer_auth=True) is True

# Prevent replay -- reject evidence older than an hour
assert evidence.verify(max_age_seconds=3600) is True
```

---

## 4. Use real post-quantum (ML-DSA-65)

```python
from crdt_merge.e4.resilience.pq_signatures import Dilithium3Scheme, has_real_pq

if not has_real_pq():
    raise RuntimeError("Install crdt-merge[security] for post-quantum support")

scheme = Dilithium3Scheme()
private_key, public_key = scheme.generate_keypair()

signature = scheme.sign(private_key, b"critical attestation")
assert scheme.verify(public_key, b"critical attestation", signature) is True
assert scheme.verify(public_key, b"tampered attestation", signature) is False
```

Use ML-DSA-65 for signatures that must survive the arrival of fault-tolerant quantum computers (roughly 15+ year retention).

---

## 5. Key rotation

```python
from crdt_merge.e4.resilience.key_manager import KeyManager

mgr = KeyManager("alice")

# Rotate to a fresh key (old key self-signs the revocation)
new_keypair, revocation = mgr.rotate_key()
assert revocation.verify(registry=mgr.registry) is True

# Emergency revocation (suspected key compromise)
revoke_entry = mgr.emergency_revoke(reason="key leaked")
assert revoke_entry.verify(registry=mgr.registry) is True
```

---

## 6. Full adversarial example

This runs against the real crypto stack and proves every attack vector is blocked.

```python
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    configure_ed25519_verification,
)
from cryptography.hazmat.primitives.asymmetric import ed25519

alice_key = ed25519.Ed25519PrivateKey.generate()
registry = PeerRegistry()
registry.register("alice", alice_key.public_key().public_bytes_raw())
configure_ed25519_verification(registry)

# Attack: forge a PCO with a zero-bytes signature (old v0.9.5 stub trick)
fake_pco = AggregateProofCarryingOperation.build(
    originator_id="alice",
    signing_fn=lambda h: b"\x00" * 64,  # garbage
    merkle_root="r", clock_snapshot=b"c",
    trust_vector_hash="t", delta_bounds=[],
)
assert fake_pco.verify(None, None, verification_level=0) is False  # REJECTED

# Valid PCO with real signature
real_pco = AggregateProofCarryingOperation.build(
    originator_id="alice",
    signing_fn=lambda h: alice_key.sign(h),
    merkle_root="r", clock_snapshot=b"c",
    trust_vector_hash="t", delta_bounds=[],
)
assert real_pco.verify(None, None, verification_level=0) is True  # ACCEPTED
```

---

## 7. Legacy unsigned mode (explicit opt-in)

For tests that use unsigned fixtures, the old behaviour is available only by asking for it, and only when a test-mode guard is set:

```python
import os
os.environ["CRDT_MERGE_INSECURE_TEST_MODE"] = "1"   # the guard; exactly "1"

configure_ed25519_verification(None, allow_unsigned=True)       # any 64-byte value passes
configure_evidence_verification(None, allow_unauthenticated=True)  # observer not authenticated
```

**Nothing is authenticated in this mode, and it is not for production.**

- Without `CRDT_MERGE_INSECURE_TEST_MODE=1` in the environment, both calls raise `InsecureModeNotPermitted` and nothing is activated.
- With the guard set, each call emits an `InsecureConfigurationWarning` (a `UserWarning`) and a `logging.WARNING` record on the `crdt_merge.e4.security` logger.
- It cannot be combined with a registry (`ValueError`), and calling either function with `None` alone returns to the fail-closed default.
- The guard is read when the opt-in is configured. It does not stop code that sets the variable itself, so it is a safeguard against accidental use, not an access control.

---

## 8. What gets verified at each tier

| Operation | Default (no registry) | Explicit legacy opt-in | Registry configured |
|---|---|---|---|
| PCO signature check | Raises (not configured) | Length == 64 | Ed25519 under the registered key |
| Evidence observer auth | Raises (not configured) | None | Ed25519 under the registered key, always required |
| Equivocation attestations | Raises (not configured) | Length == 64 | Ed25519 under the accused peer's registered key |
| Revocation proof (`RevocationEntry.verify`) | Fails without a registry | n/a | Signature from the revoked key |

`HybridScheme` defaults to Ed25519 as its classical half. `HmacScheme` is a shared-secret MAC and is not registered by default.

---

*See also: [Integration Guide](../e4/E4-INTEGRATION-GUIDE.md#enabling-real-cryptography), [Security Model](../e4/E4-SECURITY-MODEL.md), [Cryptography Reference](../security/CRYPTOGRAPHY.md)*
