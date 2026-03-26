# crdt-merge v0.5.0 — Master Defect Register

> **Copyright © 2026 Ryan Gillespie / Optitransfer. All rights reserved.**
> Licensed under the Business Source License 1.1 (BSL-1.1).
> See [LICENSE](https://github.com/mgillr/crdt-merge/blob/main/LICENSE) for details.


**Package:** crdt-merge v0.5.0
**Date:** 2026-03-28
**Source:** 10-Developer Documentation Audit + Forensic Code Analysis
**Total Defects:** 24 (20 from doc audit + 4 from forensic analysis)
**Status:** Sequenced for resolution

---

## Severity Matrix

| Severity | Count | Definition |
|----------|-------|------------|
| CRITICAL | 3 | Silent data loss, crashes, or fundamentally broken API |
| HIGH | 6 | Significant API mismatches, misleading behavior, broken workflows |
| MEDIUM | 9 | Gotchas, inconsistencies, missing validation, doc gaps |
| LOW | 6 | Minor annoyances, cosmetic issues, undocumented edge cases |

---

## Fix Sequence (Ordered by Priority)

### Phase 1: SHIP-BLOCKERS (v0.5.1 — fix in 3 days)

These are embarrassing. They make us look amateur. Fix them before ANY new feature work.

| ID | Severity | Module | Title | Description | Fix | Lines | Status |
|----|----------|--------|-------|-------------|-----|-------|--------|
| **DEF-001** | CRITICAL | `core.py` | Silent empty result with bad key | `merge(df_a, df_b, key="ID")` where column is "id" returns empty DataFrame — ALL DATA SILENTLY LOST | Add `KeyError` validation: `if key not in df_a.columns: raise KeyError(...)` | ~5 | ⬜ TODO |
| **DEF-002** | CRITICAL | `core.py` | Invalid `prefer` silently defaults to B-wins | `merge(..., prefer="TYPO")` doesn't error — silently uses B-wins behavior | Add `ValueError`: `if prefer not in ("a", "b", "latest"): raise ValueError(...)` | ~3 | ⬜ TODO |
| **DEF-003** | CRITICAL | `core.py` | `merge()` doesn't accept MergeSchema | The flagship function ignores the flagship feature — `merge(..., schema=my_schema)` → `TypeError` | Add `schema` parameter, delegate to `merge_with_provenance()` when schema provided | ~20 | ⬜ TODO |
| **DEF-004** | HIGH | `json_merge.py` | `merge_dicts()` None handling inconsistent | B's None overwrites A's real value → DATA LOSS. `merge()` and `merge_with_provenance()` correctly treat None as missing | Add None-skip logic: `if val_b is None: use val_a` | ~8 | ⬜ TODO |
| **DEF-005** | MEDIUM | All modules | No `__all__` defined anywhere | `from crdt_merge.verify import *` imports `random`, `time`, `wraps`, `dataclass`, etc. | Add `__all__` to all 13 modules | ~50 | ⬜ TODO |

**Phase 1 Total: ~86 lines, ~5 fixes, ~15 new tests**

---

### Phase 2: API CONSISTENCY (v0.5.1 or v0.6.0)

These create confusion and downstream bugs when users switch between merge functions.

| ID | Severity | Module | Title | Description | Fix | Lines | Status |
|----|----------|--------|-------|-------------|-----|-------|--------|
| **DEF-006** | HIGH | `provenance.py` | `merge_with_provenance()` always returns list[dict] | Even with DataFrame input, returns `list[dict]` — breaks downstream code when migrating from `merge()` | Add `return_type` parameter or auto-detect input type and convert | ~15 | ⬜ TODO |
| **DEF-007** | HIGH | `delta.py` | `compose_deltas()` crashes with list argument | Variadic `*deltas` but passing `[d1, d2]` gives `AttributeError: 'list' object has no attribute 'removed'` | Add type check: `if len(deltas)==1 and isinstance(deltas[0], list): raise TypeError(...)` | ~5 | ⬜ TODO |
| **DEF-008** | HIGH | `streaming.py` | `merge_sorted_stream()` silently wrong with unsorted input | No validation that inputs are sorted — produces silently incorrect results | Add optional `verify_order=True` parameter that checks monotonic keys | ~20 | ⬜ TODO |
| **DEF-009** | MEDIUM | Multiple | Conflict resolution naming inconsistent | `merge()`: `prefer=`, `merge_stream()`: `schema=`, `merge_with_provenance()`: `schema=` — three different parameter names for same concept | Document the design rationale. Add `prefer` to `merge_stream()` as sugar. | ~10 | ⬜ TODO |
| **DEF-010** | MEDIUM | `strategies.py` | `MergeSchema.from_dict()` mutates input | Pops `__default__` from input dict — calling twice silently changes behavior | Use `d.get()` instead of `d.pop()`, or operate on a copy | ~3 | ⬜ TODO |
| **DEF-011** | MEDIUM | `strategies.py` | Custom strategy silently becomes LWW after roundtrip | `Custom(fn)` serializes to `{"strategy": "Custom"}`, deserializes as `LWW()` — silent behavior change | Raise `ValueError` on deserializing Custom instead of silent fallback | ~5 | ⬜ TODO |

**Phase 2 Total: ~58 lines, ~6 fixes, ~20 new tests**

---

### Phase 3: DOCUMENTATION GAPS (v0.5.1 docs update)

These don't require code changes — just documentation additions.

| ID | Severity | Module | Title | Description | Fix | Status |
|----|----------|--------|-------|-------------|-----|--------|
| **DEF-012** | MEDIUM | `datasets_ext.py` | `merge_datasets()`/`dedup_dataset()` undocumented | Exported at top level but require HuggingFace `datasets`. Passing plain lists gives confusing `AttributeError` | Add type checking + document or remove from top-level exports | ⬜ TODO |
| **DEF-013** | MEDIUM | `provenance.py` | `export_provenance()` returns string, not dict | Function name suggests dict but returns JSON string. `ProvenanceLog.to_dict()` returns dict — confusing | Add docstring clarification, cross-reference note | ⬜ TODO |
| **DEF-014** | MEDIUM | `verify.py` | `verified_merge` misleading name | Exported alongside `merge()` but it's a decorator, not a merge variant — users call it with data and get confused | Add prominent docstring hint, consider rename to `@verify_merge` | ⬜ TODO |
| **DEF-015** | MEDIUM | `streaming.py` | `merge_sorted_stream` doesn't populate all StreamStats | `rows_unique_a`, `rows_unique_b`, `peak_batch_size` stay at 0 — only `merge_stream()` populates them | Document which stats are populated by which function | ⬜ TODO |
| **DEF-016** | MEDIUM | `dataframe.py` | `dataframe` module exposed but undocumented | `crdt_merge.dataframe` accessible, leaks `hashlib`, `time`, `LWWRegister`, typing internals | Add `__all__`, document or hide | ⬜ TODO |
| **DEF-017** | — | All | Missing "Which merge function?" guide | Users don't know when to use `merge()` vs `merge_stream()` vs `merge_with_provenance()` | Create a decision guide in docs | ⬜ TODO |

**Phase 3 Total: Documentation only, ~30 lines of code for type checks**

---

### Phase 4: EDGE CASES (v0.6.0 or later)

These are correct CRDT behavior but surprise Python developers.

| ID | Severity | Module | Title | Description | Fix | Status |
|----|----------|--------|-------|-------------|-----|--------|
| **DEF-018** | LOW | `core.py` | `ORSet.remove()` silent on non-existent | Unlike Python `set.remove()` which raises `KeyError` | Document: "Intentional for CRDT idempotency" | ⬜ TODO |
| **DEF-019** | LOW | `core.py` | `LWWMap.delete()` creates phantom tombstone | Deleting non-existent key creates a tombstone for nothing | Document: "CRDT semantics — tombstones are valid" | ⬜ TODO |
| **DEF-020** | LOW | `core.py` | `diff()` undiscoverable | Useful function but buried — not in any overview | Add to function listing overview in docs | ⬜ TODO |
| **DEF-021** | LOW | `core.py` | `GCounter.increment(node, 0)` is a no-op | Accepted but has no effect — worth mentioning | Add docstring note | ⬜ TODO |

**Phase 4 Total: Documentation only**

---

### Phase 5: FORENSIC ANALYSIS FINDINGS (v0.5.1/v0.6.0)

These were found during the forensic code audit, NOT by the doc team.

| ID | Severity | Module | Title | Description | Fix | Lines | Status |
|----|----------|--------|-------|-------------|-----|-------|--------|
| **DEF-022** | HIGH | `dataframe.py` | `merge()` converts to dicts for ALL operations | Even simple LWW merge on DataFrames goes through dict conversion — O(n) Python iteration when it could be vectorized pandas operations | Optimize hot path: use pandas merge + vectorized conflict resolution for built-in strategies | ~50 | ⬜ TODO |
| **DEF-023** | LOW | `wire.py` | Wire format uses Python `json` internally, not msgpack | Docs/roadmap reference MessagePack but actual implementation uses JSON for some CRDT types | Align implementation with spec or update spec to reflect JSON | ~0 | ⬜ TODO |
| **DEF-024** | LOW | `__init__.py` | Top-level imports expose internal submodule references | `import crdt_merge; dir(crdt_merge)` shows `core`, `strategies`, `streaming` etc. as attributes | Add `__all__` (covered by DEF-005) | ~0 | ⬜ TODO |

**Phase 5 Total: ~50 lines of optimization**

---

## Summary Statistics

| Phase | Fixes | Lines | Tests | Target Release |
|-------|-------|-------|-------|----------------|
| **Phase 1: Ship-Blockers** | 5 | ~86 | ~15 | **v0.5.1** |
| **Phase 2: API Consistency** | 6 | ~58 | ~20 | **v0.5.1 / v0.6.0** |
| **Phase 3: Doc Gaps** | 6 | ~30 | ~0 | **v0.5.1 docs** |
| **Phase 4: Edge Cases** | 4 | ~0 | ~0 | **v0.6.0** |
| **Phase 5: Forensic Findings** | 3 | ~50 | ~5 | **v0.5.1 / v0.6.0** |
| **TOTAL** | **24** | **~224** | **~40** | |

---

## Cross-Cutting Concerns

### 1. Return Type Inconsistency (DEF-003, DEF-006, DEF-009)
The three merge entry points have different return behaviors:
- `merge()` → preserves input type (DataFrame in → DataFrame out)
- `merge_with_provenance()` → always `list[dict]`
- `merge_stream()` → yields `list[dict]` batches

**Resolution:** When DEF-003 adds `schema` to `merge()`, ensure it returns the same type as input. Consider adding `as_dataframe=True` to `merge_with_provenance()`.

### 2. None Handling Inconsistency (DEF-004)
`merge()` and `merge_with_provenance()` treat None as "missing" (keep real value). `merge_dicts()` treats None as "B wins" (overwrites real value with None).

**Resolution:** Align `merge_dicts()` with the others. None = missing is the correct CRDT semantic (absent value is the identity element).

### 3. Validation Gap (DEF-001, DEF-002, DEF-007, DEF-008, DEF-011, DEF-012)
Multiple functions accept invalid input silently instead of failing fast with clear errors.

**Resolution:** Add input validation to ALL public API entry points. Follow the principle: "If the user made a typo, tell them immediately. Never silently produce wrong results."

---

## Sequential Fix Plan

```
Day 1:  DEF-001 + DEF-002 (critical validation — 8 lines, ship as patch)
Day 1:  DEF-003 (merge() + MergeSchema — 20 lines, the big one)
Day 2:  DEF-004 (None handling — 8 lines)
Day 2:  DEF-005 (__all__ across 13 modules — 50 lines, tedious but critical)
Day 3:  DEF-006 + DEF-007 (return type + compose_deltas — 20 lines)
Day 3:  DEF-010 + DEF-011 (from_dict mutation + Custom roundtrip — 8 lines)
Day 4:  DEF-008 (sorted stream verification — 20 lines)
Day 4:  DEF-022 (pandas optimization hot path — 50 lines)
Day 5:  DEF-009 + DEF-012-017 (docs + guides)
Day 5:  Run FULL test suite (423 existing + ~40 new = ~463 tests)
Day 5:  Tag v0.5.1, publish to PyPI
```

**Total effort: ~5 working days to clear all 24 defects**

---

*Copyright 2026 Ryan Gillespie — Optitransfer AG*
*Contact: rgillespie83@icloud.com, data@optitransfer.ch*
