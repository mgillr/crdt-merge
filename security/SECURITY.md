# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.9.x   | Yes       |
| < 0.9   | No        |

## Reporting a Vulnerability

Report security vulnerabilities by emailing **security@optitransfer.ch**.

We commit to:
- Acknowledging receipt within 48 hours
- Providing an initial assessment within 5 business days
- Coordinating disclosure timelines collaboratively

Do not open public GitHub issues for security vulnerabilities.

## Security Scope

The following components are in scope for security review:

- **E4 Trust Lattice** (`crdt_merge/e4/`) -- trust scoring, evidence verification, delta propagation
- **CRDT merge operations** -- OR-Set, LWW-Register, MV-Register, G-Counter merge correctness
- **Merkle provenance** -- tree construction, root computation, path verification
- **Cryptographic primitives** -- HMAC-SHA256 signing, hash computations, proof serialization
- **Delta encoding/decoding** -- ProjectionDelta serialization, compression, validation

### Out of Scope

- Denial-of-service through resource exhaustion (rate limiting is application-level)
- Social engineering attacks
- Vulnerabilities in third-party dependencies (report upstream)

## Cryptographic Posture

The E4 subsystem uses HMAC-SHA256 as the production signing backend. Ed25519 and post-quantum
signature schemes are defined as pluggable backends behind the `SignatureScheme` interface but
are not yet hardened for production use. See `docs/security/CRYPTOGRAPHY.md` for the full
cryptographic architecture and upgrade path.

## Automated Security Tooling

This project runs the following automated security tools:

| Tool | Purpose | Integration |
|------|---------|-------------|
| Bandit | Python SAST | CI/CD + pre-commit |
| Semgrep | Custom security rules | CI/CD |
| Safety CLI | Dependency vulnerability scanning | CI/CD |
| CodeQL | Semantic analysis | GitHub Actions |
| Hypothesis | Property-based fuzz testing | Test suite |

Results from the latest audit are published in `security/reports/`.

## Patent Notice

Patent: UK Application No. GB 2607132.4, GB2608127.3
