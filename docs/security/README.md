# Security Documentation

## Architecture Documents

- [THREAT-MODEL.md](THREAT-MODEL.md) -- Adversary model, assumptions, SLT vs classical BFT
- [CRYPTOGRAPHY.md](CRYPTOGRAPHY.md) -- Signing backends, Merkle hashing, upgrade path

## Audit Results

See [security/reports/](../../security/reports/) for scan results, formal
verification output, and the comprehensive audit report.

## Test Suite

See [security/tests/](../../security/tests/) for the Byzantine fault injection
test suite and property-based fuzz tests.

## Formal Specification

See [security/formal/](../../security/formal/) for the TLA+ formal specification
of the E4 trust lattice.

## Responsible Disclosure

See [security/SECURITY.md](../../security/SECURITY.md) for the vulnerability
reporting policy.
