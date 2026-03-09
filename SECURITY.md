# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.9.x   | Active             |
| 0.8.x   | Security fixes only |
| < 0.8   | End of life        |

## Reporting a Vulnerability

If you discover a security vulnerability in crdt-merge, please report it
responsibly. **Do not open a public GitHub issue.**

**Email:** rgillespie83@icloud.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Any potential impact assessment

## Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 5 business days
- **Fix or mitigation**: Dependent on severity
  - Critical: Patch within 72 hours
  - High: Patch within 7 days
  - Medium/Low: Next scheduled release

## Scope

The following are in scope for security reports:

- Cryptographic operations (EncryptedMerge, crypto backends)
- Audit log integrity (AuditLog, hash chain verification)
- Access control bypass (RBACController, SecureMerge)
- Deserialization vulnerabilities (wire.deserialize)
- Data leakage in merge provenance or compliance reports

## Disclosure Policy

We follow coordinated disclosure. Once a fix is released, we will:
1. Credit the reporter (unless anonymity is requested)
2. Publish a security advisory via GitHub Security Advisories
3. Update the CHANGELOG with the fix details

## Encryption

crdt-merge supports pluggable cryptographic backends (AES-256-GCM, AES-256-GCM-SIV,
ChaCha20-Poly1305). All AEAD backends require the cryptography package
(pip install crdt-merge[crypto]). The XOR legacy backend is provided for
zero-dependency environments and is not recommended for production use.

## Patent Notice

crdt-merge is covered by UK Patent Application No. 2607132.4.
See PATENTS for details.
