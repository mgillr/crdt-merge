# Layer 2 — Second Pass: Heightened Stochastic Sensitivity Report

> **Date:** 2026-03-31
> **Engines:** GDEPA Heightened + RREA Heightened (H > 0.15)
> **Scope:** Full source analysis, filtered to Layer 2 modules

---

## Configuration

| Parameter | Standard | Heightened |
|-----------|----------|------------|
| Shannon threshold | H > 0.5 | H > 0.15 |
| Ping threshold | H > 0.5 | H > 0.15 |
| Dunder inclusion | Excluded | Included (overridden dunders) |
| Source scope | Layer-isolated | Full package (runtime inspect needs full tree) |

---

## GDEPA Heightened Findings

| Module | Inherited Methods | Runtime-Only Symbols |
|--------|-------------------|---------------------|
| `crdt_merge.strategies` | **132** (↑ from 0) | 2 |
| `crdt_merge.schema_evolution` | **19** (↑ from 0) | 1 |
| `crdt_merge._polars_engine` | 0 | 1 |
| **Total Layer 2** | **151** | **4** |

### Key Finding
The 132 inherited methods in `strategies` are overwhelmingly dunder methods (`__eq__`, `__hash__`, `__repr__`, etc.) inherited across 14+ MergeStrategy subclasses. These form the implicit interface that users inherit when subclassing.

---

## RREA Heightened Findings

### Chokepoints (H > 0.15)

| Symbol | Combined H | Shannon | Ping | Status |
|--------|-----------|---------|------|--------|
| `strategies.MergeStrategy` | 0.6922 | 0.3850 | 0.9994 | Already caught by standard pass |
| `_polars_engine._get_field_strategy` | **0.5593** | **0.1215** | **0.9971** | **NEW — caught by Ping entropy** |

### Key Finding
`_get_field_strategy` has low Shannon entropy (0.1215) but near-maximum Ping entropy (0.9971). This means it has few direct callers but nearly ALL execution paths in the polars engine converge through it. Standard pass missed it because Shannon alone was below 0.5.

### Dead Code Analysis
- 41 candidates flagged
- **0 truly dead** — all are either:
  - Local variables inside functions (30): `both_mask`, `col_dtype`, `joined`, etc.
  - Conditional imports (3): `pa`, `pl`, `HAS_ARROW`
  - Logger instance (1): `_polars_engine.logger`
  - Function-scoped closures (7): `_resolve_row`, `_wrap_null`, etc.
- **Conclusion:** _polars_engine has no truly dead code; all "dead" signals are false positives from static analysis limitations

---

## Issues Filed

| Issue | Title | Type |
|-------|-------|------|
| #43 | `_get_field_strategy` Ping-entropy-dominant chokepoint | critical-path |
| #44 | 132 inherited dunder methods in strategies | documentation |
| #45 | 19 inherited methods in schema_evolution | documentation |

---

## False Positive Summary

| Pattern | Count | Reason |
|---------|-------|--------|
| Local variables | 30 | RREA can't trace intra-function usage |
| Conditional imports | 3 | Alive when polars/arrow installed |
| Logger instances | 1 | Used in except blocks |
| Function closures | 7 | Scoped to parent function |
| **Total FP** | **41** | Filtered from results |

---

## Validation Gate: ✅ PASSED

- [x] Both heightened engines ran on full source
- [x] Results filtered to Layer 2
- [x] All findings classified (3 genuine, 41 FP)
- [x] Issues filed for genuine findings (#43-#45)
- [x] False positive count documented (41)
- [x] Pushed to GitHub
