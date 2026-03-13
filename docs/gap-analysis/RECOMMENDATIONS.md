# Recommendations — Prioritized Remediation Plan

## Priority 1: Critical (Do Immediately)

### R-001: Document Enterprise Layer (Layer 5)
**Issue**: DOC-001 — 3,323 LOC with ZERO documentation
**Action**: Run full AST analysis on `audit.py`, `encryption.py`, `rbac.py`, `observability.py`, `unmerge.py`. Create API reference files with complete signatures, behavior docs, and usage examples.
**Effort**: ~4 hours
**Impact**: Unblocks enterprise adoption

### R-002: Document Compliance Layer (Layer 6)
**Issue**: DOC-002 — 932 LOC with ZERO documentation
**Action**: Run full AST analysis on `compliance.py`. Document `ComplianceAuditor`, `EUAIActReport`, GDPR/HIPAA/SOX auditing capabilities.
**Effort**: ~2 hours
**Impact**: Required for regulated industry adoption

---

## Priority 2: High (Do This Week)

### R-003: Add Concurrent Conflict Examples
**Issue**: DOC-003 — No examples showing CRDT add-wins behavior
**Action**: Create runnable examples showing ORSet concurrent add/remove, LWWRegister tie-breaking, and VectorClock ordering in the cookbook.
**Effort**: ~2 hours

### R-004: Document Timestamp Determinism
**Issue**: DOC-004 — Tie-breaking behavior undocumented
**Action**: Add "Determinism Guarantees" section to every strategy and CRDT primitive documenting exact tie-break logic.
**Effort**: ~1 hour

### R-005: Fix LOC Discrepancy
**Issue**: ARCH-001 — 14.1% LOC discrepancy
**Action**: Re-run `wc -l` on all production files and compare with AST count. Document the exact difference methodology.
**Effort**: ~30 minutes

---

## Priority 3: Medium (Do This Sprint)

### R-006: Fix `targets/` Directory Reference
**Issue**: ARCH-002 — Incorrect directory location in inventory
**Action**: Update all references from `crdt_merge/targets/` to `crdt_merge/model/targets/`.
**Status**: ✅ Resolved — all documentation references corrected. Import path: `crdt_merge.model.targets`.

### R-007: Add Custom Strategy Serialization Warning
**Issue**: LAY1-003 — Custom strategies silently lost on serialization
**Action**: Add prominent warning in API docs and consider adding a `warnings.warn()` at merge time.

### R-008: Document `_safe_parse_ts()` Silent Behavior
**Issue**: LAY1-005 — Invalid timestamps silently become 0.0
**Action**: Add "Timestamp Parsing" section to guides explaining this behavior.

### R-009: Replace Auto-Generated Stubs
**Issue**: DOC-005 — API stubs have blank descriptions
**Action**: Replace all existing `docs/api/*.md` stubs with this repo's comprehensive API reference.

---

## Priority 4: Low (Backlog)

### R-010: Consider ORSet Selective Removal API
**Issue**: LAY1-002 — No selective tag removal
**Action**: File feature request for `remove_tag(element, tag)` method.

### R-011: Evaluate Layer 4 Decomposition
**Issue**: ARCH-003 — Layer 4 is 56.2% of codebase
**Action**: Assess whether `model/` should be extracted to a separate package.

---

## Priority 2 (cont.): Layer 2 Findings (Added 2026-03-31)

### R-012: Triage _polars_engine.py Dead Code Candidates
**Issue**: LAY2-006 — 41 dead code candidates, mostly local variable false positives
**Action**: Manual code review to separate true dead functions from Polars expression-builder patterns that appear dead to static analysis.
**Effort**: ~1 hour
**Impact**: Clean up confirmed dead code; document false positive patterns for future RREA runs

### R-013: Document 18 Layer 2 Chokepoints
**Issue**: LAY2-005 — 13 of 18 chokepoints are undocumented or partially documented
**Action**: Add docstrings to all 18 chokepoint symbols, prioritizing `arrow._ensure_table` (H=0.6232) as #1.
**Effort**: ~2 hours
**Impact**: Reduces maintenance risk on critical internal code paths

### R-014: Add `__all__` to parallel.py and async_merge.py
**Issue**: LAY2-004 — 2 modules missing `__all__` exports
**Action**: Define `__all__` in both modules to establish clear public API boundaries.
**Effort**: ~15 minutes
**Impact**: Enables reliable star imports and API documentation tooling

### R-015: Correct Layer 2 LOC in All References
**Issue**: LAY2-003 — 35.4% LOC discrepancy across all Layer 2 modules
**Action**: ✅ Already corrected in LAYER_MAP.md and all API reference files (2026-03-31). Remaining: update any external references.
**Effort**: ✅ Done
**Impact**: Accurate sizing estimates for project planning

---

*Recommendations v1.1 — updated with Layer 2 remediation items*
