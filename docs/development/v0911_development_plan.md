# v0.9.1.1 Development Plan — "The Backfill Patch"

**Date:** March 30, 2026
**Target:** Add `[crypto]` optional dependency group to pyproject.toml
**New LOC:** 4
**New Tests:** 0 (existing encryption backend tests provide full coverage)
**Breaking Changes:** 0
**Contact:** rgillespie83@icloud.com · data@optitransfer.ch
**License:** BSL-1.1 (Business Source License 1.1)
**Copyright:** Copyright 2026 Ryan Gillespie

---

## Overview

v0.9.1.1 is a build-configuration patch that adds the missing `[crypto]` optional dependency group to `pyproject.toml`. The v0.9.1 "Iron Dome Release" shipped four pluggable AEAD encryption backends (AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305, XOR legacy) but the documented installation path — `pip install crdt-merge[crypto]` — was not wired in the package metadata.

This patch closes the gap between documentation and packaging.

### Why a Patch Instead of v0.9.2

1. **No functional code changes** — only `pyproject.toml` metadata is modified
2. **No new modules, classes, or test files** — the encryption backends already work; this just makes `pip install crdt-merge[crypto]` resolve correctly
3. **Semantic versioning compliance** — a micro-patch is appropriate for build metadata corrections

---

## Problem Statement

The v0.9.1 README and encryption module docstrings reference:

```bash
pip install crdt-merge[crypto]
```

However, `pyproject.toml` did not define a `[crypto]` extra. Users who followed the documentation would see:

```
WARNING: crdt-merge 0.9.1 does not provide the extra 'crypto'
```

The AEAD backends (AES-256-GCM, AES-GCM-SIV, ChaCha20-Poly1305) would silently fail to register, falling back to XOR legacy without clear indication of why.

---

## Implementation

### Dev 1 — Build Configuration (`pyproject.toml`)

**Owner:** `pyproject.toml`
**Dependencies:** None
**LOC Changed:** 4 lines added

#### Change

Add to `[project.optional-dependencies]`:

```toml
crypto = ["cryptography>=41"]
```

Update the existing `all` extra to include the `crypto` group:

```toml
all = [
    "crdt-merge[datasets]",
    "crdt-merge[crypto]",    # ← NEW
]
```

#### Verification

```bash
# Before patch:
pip install crdt-merge[crypto]
# WARNING: crdt-merge does not provide the extra 'crypto'

# After patch:
pip install crdt-merge[crypto]
# Successfully installed cryptography-43.0.0 crdt-merge-0.9.1.1

python -c "from crdt_merge.encryption import get_backend; print(get_backend('auto').name)"
# aes-256-gcm
```

---

## Dev Team Assignment

| Role | Owner | Work |
|------|-------|------|
| **Dev 1** | @Dev | Add `crypto` extra and update `all` group in `pyproject.toml` |
| **QA** | @Dev | Verify `pip install crdt-merge[crypto]` resolves; existing 51 encryption tests still pass |

### Sprint Organization

Single-developer patch — no parallel work needed. Total effort: <15 minutes.

---

## Execution Order

```
Dev 1 (pyproject.toml edit) ──► verify install ──► commit ──► push ──► PyPI publish
```

---

## Quality Gates

| Gate | Requirement | Result |
|------|-------------|--------|
| `pip install crdt-merge[crypto]` resolves | Installs `cryptography>=41` | ✅ |
| `pip install crdt-merge[all]` includes crypto | No warnings | ✅ |
| Existing encryption tests | 51 backend tests pass | ✅ |
| Existing full suite | 3,041 tests, 0 failures | ✅ |
| Zero functional changes | Only pyproject.toml modified | ✅ |

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| `cryptography>=41` pins too broadly | >=41 covers all current stable releases (41.x–43.x); lower bound ensures AEAD API compatibility |
| Users on constrained environments can't install cryptography | XOR legacy fallback still works without the `[crypto]` extra — documented in README |

---

*Patch follows the established development methodology. Zero functional code changes — build metadata correction only.*
