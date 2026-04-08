# v0.9.0 Development Plan — "The Enterprise Release"

**Date:** March 30, 2026
**Target:** UnmergeEngine + EU AI Act Compliance + Encryption + RBAC + Observability
**Estimated New LOC:** ~3,000
**Estimated New Tests:** ~500
**Breaking Changes:** 0
**Contact:** rgillespie83@icloud.com · data@optitransfer.ch
**License:** BSL-1.1 (Business Source License 1.1)
**Copyright:** Copyright 2026 Ryan Gillespie

---

## Overview

v0.9.0 adds enterprise-grade features to crdt-merge: reversible merging (UnmergeEngine), regulatory compliance (EU AI Act, GDPR, HIPAA, SOX), encryption for sensitive merge operations, role-based access control, and observability integration.

This release is **time-critical** — the EU AI Act enforcement deadline is August 2, 2026. The compliance module enables companies to generate Article 13 traceability documentation directly from crdt-merge's existing provenance system.

### Guiding Principles

1. **Zero new dependencies** — all modules use stdlib only; optional integrations lazy-import
2. **Zero breaking changes** — all existing tests must continue to pass
3. **Correct licensing** — every new file carries BSL-1.1 header + patent reference
4. **Real-API testing** — all tests run against the live installed package
5. **CRDT compliance** — unmerge operations preserve CRDT guarantees on remaining data

---

## New Module Map

```
crdt_merge/
├── unmerge.py              ← Phase 1 (NEW — ~1,000 LOC)
├── encryption.py           ← Phase 3 (NEW — ~300 LOC)
├── rbac.py                 ← Phase 4 (NEW — ~250 LOC)
├── observability.py        ← Phase 4 (NEW — ~300 LOC)
├── compliance/             ← Phase 2 (NEW package — ~700 LOC)
│   ├── __init__.py
│   ├── auditor.py
│   └── eu_ai_act.py
└── __init__.py             ← Phase 5 (UPDATE — re-exports)
```

---

## Dev Team Assignments

### Phase 1 — UnmergeEngine (`crdt_merge/unmerge.py`)

**Owner:** `crdt_merge/unmerge.py`
**Dependencies:** Reads from `provenance.py`, `model/provenance.py`, `model/crdt_state.py`
**Est. LOC:** ~1,000 | **Est. Tests:** ~150

#### Classes

1. **`UnmergeEngine`** — Reverse tabular merges using provenance
   - `unmerge(merged_data, provenance, remove_source)` → unmerged records
   - `verify_unmerge(unmerged, removed_source)` → UnmergeReport
   - `unmerge_delta(delta, provenance, remove_source)` → filtered Delta

2. **`ModelUnmerge`** — Reverse model weight merges
   - `unmerge_model(merged_state, provenance, remove_model, method="negmerge")` → cleaned CRDTMergeState
   - `measure_residual(cleaned, removed_model)` → ResidualReport
   - Methods: `negmerge`, `surgical`, `proportional`

3. **`GDPRForget`** — Data + model contributor removal with compliance reports
   - `forget_data(merged_data, provenance, contributor)` → ForgetResult
   - `forget_training_data(model_state, provenance, data_to_forget)` → ForgetResult
   - `compliance_report()` → GDPRComplianceReport

4. **Dataclasses:** `UnmergeReport`, `ResidualReport`, `ForgetResult`, `GDPRComplianceReport`

#### Key Design Decisions
- Unmerge is **NOT** a CRDT operation itself — it's an administrative action that produces valid CRDT state
- All unmerge operations require provenance (no provenance = no unmerge)
- ModelUnmerge uses existing NegMerge strategy from `model/strategies/unlearning.py`
- GDPRForget wraps UnmergeEngine + ModelUnmerge with compliance metadata

#### Tests (`tests/test_unmerge.py`)
- Tabular unmerge: remove source B, verify only source A data remains
- Model unmerge: remove model contribution, verify residual < threshold
- GDPR forget: data-level + model-level removal
- Round-trip: merge(A, B) → unmerge(result, B) ≈ A
- Edge cases: empty provenance, unknown source, already-removed
- Verify remaining data still satisfies CRDT properties

---

### Phase 2 — Compliance Suite (`crdt_merge/compliance/`)

**Owner:** `crdt_merge/compliance/__init__.py`, `crdt_merge/compliance/auditor.py`, `crdt_merge/compliance/eu_ai_act.py`
**Dependencies:** Reads from `provenance.py`, `unmerge.py` (Phase 1), `context/manifest.py`
**Est. LOC:** ~700 | **Est. Tests:** ~120

#### Classes

1. **`ComplianceAuditor`** (`auditor.py`)
   - `__init__(framework="gdpr")` — supports `gdpr`, `hipaa`, `sox`, `eu_ai_act`
   - `audit(provenance)` → AuditResult
   - `generate_report(format="json", include_provenance=True, include_data_lineage=True)` → str
   - `check_retention(provenance, max_age_days)` → RetentionReport

2. **`EUAIActReport`** (`eu_ai_act.py`) — Time-critical (Aug 2, 2026)
   - `__init__(model_provenance, training_data_provenance=None, context_manifests=None)`
   - `generate(format="json", include_data_lineage=True, include_model_cards=True, include_merge_attestations=True)` → str
   - `validate()` → ValidationResult (checks Article 13 coverage)
   - Article 13 requirements mapping (traceability, transparency, human oversight)

3. **Dataclasses:** `AuditResult`, `RetentionReport`, `ValidationResult`, `ComplianceReport`

#### Key Design Decisions
- JSON output by default (PDF generation would require dependencies)
- EU AI Act module maps provenance fields to Article 13 requirements
- Framework-agnostic `ComplianceAuditor` + framework-specific report generators
- Uses existing `ProvenanceLog`, `MergeRecord`, `MergeDecision` from `provenance.py`
- Uses existing `ContextManifest` from `context/manifest.py` for end-to-end lineage

#### Tests (`tests/test_compliance.py`)
- Each framework: audit generates valid report
- EU AI Act: validation checks all Article 13 requirements
- Missing provenance: graceful degradation
- Coverage scoring: percentage of requirements met
- Report formats: JSON structure validation

---

### Phase 3 — Encryption (`crdt_merge/encryption.py`)

**Owner:** `crdt_merge/encryption.py`
**Dependencies:** stdlib only (`hashlib`, `secrets`, `struct`). Reads from `strategies.py`
**Est. LOC:** ~300 | **Est. Tests:** ~80

#### Classes

1. **`EncryptedMerge`**
   - `__init__(key_provider)` — `key_provider` is a callable returning bytes
   - `encrypt_field(value, field_name)` → EncryptedValue
   - `decrypt_field(encrypted, field_name)` → original value
   - `merge(encrypted_left, encrypted_right, schema)` → encrypted result
   - `rotate_key(records, old_key_provider, new_key_provider)` → re-encrypted records

2. **`EncryptedValue`** — Wrapper preserving order for LWW/Max/Min
   - `.ciphertext`, `.order_tag` (order-preserving hash for comparison)
   - `.to_dict()`, `EncryptedValue.from_dict(d)`

3. **`KeyProvider`** — Protocol/ABC for key management
   - `get_key(field_name)` → bytes
   - `StaticKeyProvider(key: bytes)` — simple implementation

#### Key Design Decisions
- Uses AES-GCM from stdlib (`hashlib` + `struct` for HMAC-based construction, no `cryptography` dep)
- Order-preserving tags enable LWW/Max/Min strategies on encrypted data
- Key rotation is a batch operation (re-encrypt all records)
- Encryption at field level, not record level

#### Tests (`tests/test_encryption.py`)
- Encrypt/decrypt round-trip
- Merge on encrypted data produces same result as merge on plaintext
- Key rotation preserves data integrity
- Order preservation for LWW strategy
- Edge cases: None values, empty strings, numeric fields

---

### Phase 4 — RBAC + Observability

**Owner:** `crdt_merge/rbac.py`, `crdt_merge/observability.py`
**Dependencies:** stdlib only. Reads from `dataframe.py` for merge hooks
**Est. LOC:** ~550 | **Est. Tests:** ~100

#### RBAC (`crdt_merge/rbac.py`, ~250 LOC)

1. **`Role`** — Enum: `ADMIN`, `ANALYST`, `VIEWER`, `CUSTOM`
2. **`Permission`** — Enum: `MERGE`, `UNMERGE`, `VIEW_PROVENANCE`, `ENCRYPT`, `EXPORT`
3. **`MergePolicy`**
   - `__init__(policies: dict)` — `{Role: {Permission: bool}}`
   - `check(role, permission)` → bool
   - `enforce(role, permission)` → raises `PermissionDenied` if denied
   - `to_dict()`, `MergePolicy.from_dict(d)`
4. **`PolicyEnforcer`**
   - `__init__(policy, role)` — wraps merge functions with policy checks
   - `wrap_merge(merge_fn)` → policy-checked merge function

#### Observability (`crdt_merge/observability.py`, ~300 LOC)

1. **`MergeMetrics`**
   - `__init__(namespace="crdt_merge")`
   - `trace_merge(operation_name)` → context manager yielding `MergeSpan`
   - `record_merge(operation, duration_ms, records, conflicts)` — log a metric
   - `export_prometheus()` → str (Prometheus text format)
   - `export_json()` → str
   - `reset()` — clear all metrics
2. **`MergeSpan`**
   - `set_attribute(key, value)`
   - `add_event(name, attributes=None)`
   - `.duration_ms`, `.attributes`
3. **`MetricsSummary`** — aggregated stats
   - `.total_merges`, `.total_conflicts`, `.avg_duration_ms`, `.p99_duration_ms`

#### Tests
- **RBAC:** Policy enforcement, permission denied, admin override, serialization
- **Observability:** Metric recording, Prometheus export format, span lifecycle, summary stats

---

### Phase 5 — Integration

**Owner:** `crdt_merge/__init__.py` (re-exports), README, CHANGELOG, version bump
**Dependencies:** All Phase 1-4 outputs must be complete
**Est. LOC:** ~500 (updates + integration tests) | **Est. Tests:** ~50

#### Tasks

1. **`__init__.py` updates:**
   - Lazy-import `unmerge`, `compliance`, `encryption`, `rbac`, `observability`
   - Add to `__all__` exports
   - Pattern: same as existing lazy imports (try/except blocks)

2. **Version bump:** `0.8.3` → `0.9.0` in `pyproject.toml`, `__init__.py`

3. **README updates:**
   - Badge: `pypi-v0.9.0`
   - "What's New in v0.9.0" section
   - Feature table updates
   - Strategy table (no changes — same 26)

4. **CHANGELOG:** v0.9.0 entry with all new features

5. **Integration tests (`tests/test_v090_integration.py`):**
   - End-to-end: merge → provenance → unmerge → verify
   - Compliance: merge → provenance → EU AI Act report → validate
   - Encryption: encrypt → merge → decrypt → verify
   - RBAC: policy → enforced merge → verify permissions
   - Observability: metrics → merge → export → verify format
   - Cross-module: all new modules work together

6. **License header audit:** Verify ALL new files have correct BSL-1.1 header

---

## File License Header (MANDATORY for all new files)

```python
# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
```

---

## Execution Order

```
Phase 1 (UnmergeEngine)    ──commit + push ──┐
Phase 3 (Encryption)       ──commit + push ──┤
Phase 4 (RBAC+Observ.)     ──commit + push ──┤ (parallel — no conflicts)
                                              │
Phase 2 (Compliance)       ────────────────────┘ (depends on Phase 1 for unmerge)
  └──commit + push ──┐
                        │
Phase 5 (Integration)     ┘ (depends on all)
  └──commit + push ──FINAL TEST SWEEP ──v0.9.0 TAG
```

**Sequential execution order (conservative):**
1. Phase 1 — UnmergeEngine (foundation for Phase 2)
2. Phase 3 — Encryption (independent)
3. Phase 4 — RBAC + Observability (independent)
4. Phase 2 — Compliance Suite (depends on Phase 1)
5. Phase 5 — Integration (depends on all)
6. Full test sweep + CRDT compliance verification
7. Push to GitHub + publish to PyPI

---

## Quality Gates

| Gate | Requirement |
|------|-------------|
| Unit tests | All new tests pass |
| Existing tests | 2,608+ existing tests still pass (zero regressions) |
| CRDT compliance | All 32 strategies verified (8 tabular + 26 model — after unmerge) |
| License headers | Every new `.py` file has BSL-1.1 header + patent |
| Zero dependencies | `pip install crdt-merge` works with stdlib only |
| API discovery | All new APIs verified against live installed package |
| Documentation | README, CHANGELOG, roadmap updated |

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| ModelUnmerge requires numpy | Lazy import — same pattern as model module |
| Encryption order-preservation is approximate | Document limitations; exact for integer types |
| EU AI Act requirements may change | Design for extensible requirement mapping |
| Compliance report PDF needs dependencies | Ship JSON/Markdown; PDF via optional `[compliance]` extra |
| RBAC adds overhead to merge path | PolicyEnforcer is opt-in wrapper, not embedded in core |

---

*This plan follows the established development methodology from v0.8.1–v0.8.3. Each dev has non-conflicting module ownership. All work is tested against the live installed package. All files carry correct BSL-1.1 licensing.*
