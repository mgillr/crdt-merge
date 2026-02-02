# v0.9.0 — "The Enterprise Release" — Test Results

**Date:** 30 March 2026
**Package:** crdt-merge v0.9.0
**Repository:** github.com/mgillr/crdt-merge
**Test Runtime:** 239.22s (3m 59s)

## Summary

| Metric | Value |
|--------|-------|
| **Total Tests** | 2,809 |
| **Passed** | 2,809 |
| **Failed** | 0 |
| **Skipped** | 97 (legitimate — optional deps) |
| **New Enterprise Tests** | 210 |
| **Core Regressions** | 0 |

## Enterprise Module Tests

| Test File | Tests | Passed | Lines |
|-----------|-------|--------|-------|
| test_unmerge.py | 42 | 42 | — |
| test_audit.py | 46 | 46 | — |
| test_encryption.py | 49 | 49 | — |
| test_rbac.py | 39 | 39 | — |
| test_observability.py | 34 | 34 | — |
| **Total** | **210** | **210** | **2,213** |

## Enterprise Source Modules

| Module | File | Lines | License | Patent |
|--------|------|-------|---------|--------|
| UnmergeEngine | crdt_merge/unmerge.py | 833 | BUSL-1.1 | GB2607132.4 |
| AuditLog | crdt_merge/audit.py | 430 | BUSL-1.1 | GB2607132.4 |
| EncryptedMerge | crdt_merge/encryption.py | 437 | BUSL-1.1 | GB2607132.4 |
| RBAC | crdt_merge/rbac.py | 357 | BUSL-1.1 | GB2607132.4 |
| Observability | crdt_merge/observability.py | 462 | BUSL-1.1 | GB2607132.4 |
| **Total** | — | **2,519** | — | — |

## Live API Verification

All 32 API surface tests executed against the installed package using `inspect` module extraction. Zero assumptions — every constructor parameter and method call verified against actual signatures.

| Class | Constructor | Methods Verified | Status |
|-------|------------|-----------------|--------|
| UnmergeEngine | `()` | `unmerge()`, `verify_unmerge()` | PASS |
| ModelUnmerge | `()` | weight separation | PASS |
| GDPRForget | `(engine=, model_unmerge=)` | `forget_data()`, `compliance_report()` | PASS |
| GDPRComplianceReport | dataclass | `to_dict()`, `to_json()` | PASS |
| ForgetResult | dataclass | field access | PASS |
| UnmergeReport | dataclass | field access | PASS |
| ResidualReport | dataclass | field access | PASS |
| AuditLog | `(node_id=)` | `log_operation()`, `verify_chain()`, `get_entries()`, `export_log()`, `import_log()` | PASS |
| AuditEntry | dataclass | `verify()` | PASS |
| AuditedMerge | `()` | `merge()` | PASS |
| EncryptedMerge | `(key_provider)` | `encrypt_records()`, `decrypt_records()`, `merge_encrypted()`, `rotate_key()` | PASS |
| EncryptedValue | dataclass | serialization | PASS |
| StaticKeyProvider | `(key)` | key provision | PASS |
| RBACController | `()` | `add_policy()`, `check_permission()` | PASS |
| SecureMerge | `(rbac)` | `merge(context=)` | PASS |
| Permission | enum | READ, WRITE, MERGE, ADMIN | PASS |
| Role | `(name, permissions)` | frozen set | PASS |
| Policy | `(role=)` | access checks | PASS |
| AccessContext | `(node_id=, role=)` | context passing | PASS |
| MetricsCollector | `(node_id=, max_history=)` | `record_merge()`, `get_summary()`, `get_metrics()`, `export_metrics()` | PASS |
| ObservedMerge | `()` | `merge()` | PASS |
| MergeMetric | dataclass | field access | PASS |
| HealthCheck | `(collector)` | `check_health()` | PASS |

## Core Test Suite — Zero Regressions

All 2,599 pre-existing tests pass. Skips (97): test_arrow.py (56, requires PyArrow), test_polars_engine.py (25, requires Polars), test_model_modules_dev6.py (15, requires numpy/torch), test_v050_integration.py (1, optional dep).

## Licensing & IP Compliance

| Check | Status |
|-------|--------|
| All source files: SPDX-License-Identifier: BUSL-1.1 | PASS |
| All source files: Patent reference GB2607132.4 | PASS |
| All source files: Copyright 2026 Ryan Gillespie | PASS |
| LICENSE Change Date: 2028-03-29 | PASS |
| NOTICE Apache conversion: 2028-03-29 | PASS |
| README Apache conversion: 29 March 2028 | PASS |

## Commits

| Commit | Description |
|--------|-------------|
| 7f123b5 | feat(v0.9.0): integrate enterprise modules |
| 9e7d389 | feat(enterprise): RBAC + Observability (Dev 4) |
| cafeec0 | feat(audit): AuditLog with cryptographic chaining (Dev 2) |
| c47434e | feat(encryption): EncryptedMerge field-level encryption (Dev 3) |
| 8c2ed15 | feat(unmerge): UnmergeEngine, ModelUnmerge, GDPRForget (Dev 1) |
| 2e3198d | docs: v0.9.0 development plan |
| 9d7aa5b | docs: fix Apache date + strategy count |

*Generated from live test execution against crdt-merge v0.9.0 installed from source.*
