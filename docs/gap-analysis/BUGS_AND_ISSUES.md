# Bugs and Issues — Complete Registry

## Layer 1 Issues (Verified via Deep Analysis)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| LAY1-001 | 🟡 Medium | LWWRegister tie-break uses lexicographic node_id comparison, not numeric | `core.py:154` | Unintuitive: `"node9" > "node10"` lexicographically |
| LAY1-002 | 🟡 Medium | ORSet.remove() clears ALL tags — no selective removal API | `core.py:195` | Full remove only; can't remove specific concurrent add |
| LAY1-003 | 🟡 Medium | Custom strategy doesn't serialize — emits UserWarning, deserializes as LWW | `strategies.py:327` | Custom strategies lost on round-trip serialization |
| LAY1-004 | 🟡 Medium | VectorClock zero-counter stripping is implicit and undocumented | `clocks.py:92` | `VectorClock({"a": 0}) == VectorClock({})` is surprising |
| LAY1-005 | 🟡 Medium | `_safe_parse_ts()` silently returns 0.0 for invalid timestamps | `strategies.py:76` | Invalid timestamps silently become epoch, hard to debug |
| LAY1-006 | 🟡 Medium | `MergeSchema.resolve_row()` doesn't handle nested dicts | `strategies.py:306` | Nested/hierarchical data gets flattened |

## Layer 2 Issues (From Inventory Analysis)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| LAY2-001 | 🟡 Medium | `_polars_engine.py` is private but listed as public API in inventory | `_polars_engine.py` | Confusing public/private boundary |
| LAY2-002 | 🟢 Low | `json_merge.py` is smallest engine (145 LOC) with limited features | `json_merge.py` | May not handle all JSON edge cases |

## Architecture Issues

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| ARCH-001 | 🟠 High | LOC discrepancy: Inventory says 38,157, actual is 32,787 (-14.1%) | Codebase-wide | Inaccurate sizing estimates |
| ARCH-002 | 🟡 Medium | `targets/` directory location differs between inventory and actual | `model/targets/` | Incorrect import paths in docs |
| ARCH-003 | 🟡 Medium | Layer 4 is 56.2% of codebase — potential architectural concern | `model/` (15,464 LOC) | Suggests possible need for decomposition |

## Documentation Issues

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| DOC-001 | 🔴 Critical | Layer 5 (Enterprise) has ZERO documentation — 3,323 LOC | `audit.py`, `encryption.py`, `rbac.py`, `observability.py`, `unmerge.py` | Enterprise users have no guidance |
| DOC-002 | 🔴 Critical | Layer 6 (Compliance) has ZERO documentation — 932 LOC | `compliance.py` | Compliance features undiscoverable |
| DOC-003 | 🟠 High | No examples for concurrent conflict resolution | Layer 1 docs | Users can't learn CRDT add-wins behavior |
| DOC-004 | 🟠 High | No timestamp tie-breaking behavior documented | Layer 1 docs | Determinism guarantees unclear |
| DOC-005 | 🟡 Medium | Auto-generated API stubs have blank descriptions | `docs/api/` | Stubs exist but provide no value |
| DOC-006 | 🟡 Medium | No learning path in existing README | `docs/README.md` | Marketing-heavy, not tutorial-oriented |

---



## RREA Findings (Team 4 — 2026-03-31)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| RREA-001 | 🟠 High | 72 symbols have zero reachability in static call graph | Layer 1 (all modules) | Likely false positives (AST can't trace `obj.method()` calls), but needs runtime verification |
| RREA-002 | 🟡 Medium | 22 shadow dependencies (private helpers) undocumented | Layer 1 (all modules) | Private functions like `_safe_parse_ts`, `_hash128`, `_normalize` are critical internal code |
| RREA-003 | 🟠 High | verify module has highest entropy chokepoint | `verify.py` — VerificationResult | Entropy=0.5186, reachability=11.6 — most critical convergence point in Layer 1 |
| DOC-010 | 🟡 Medium | 42+ symbols missing from Layer 1 API docs | Layer 1 (all modules) | Magic methods, private helpers, and some public functions undocumented |
| METRIC-001 | 🟡 Medium | Layer 1 LOC count incorrect — 2,122 not 2,614 | Architecture docs | 19.2% discrepancy affects sizing estimates |

## Dead Code (GDEPA + RREA Validated — 2026-03-31)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| DEAD-001 | 🟡 Medium | `_load_accelerators` is truly dead code | `__init__.py` | Unreachable private function — candidate for removal |
| DEAD-002 | 🟡 Medium | `_load_model` is truly dead code | `__init__.py` | Unreachable private function — candidate for removal |

> **Methodology:** Confirmed via GDEPA runtime introspection + RREA cross-layer import tracing + dead code classification. These are the ONLY 2 truly dead symbols in Layer 1. All other "dead" candidates from static analysis were reclassified as cross-layer dependencies (16), local variables (20), or public API used by L2–L6 (12).

## Entropy Chokepoint Correction (RREA Ping Entropy — 2026-03-31)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| RREA-004 | 🟠 High | MergeStrategy is #1 chokepoint (combined H=0.722), not VerificationResult | `strategies.py` | 9 endpoints converge through single abstract base — highest risk point in Layer 1 |

> **Correction to RREA-003:** Previous analysis using Shannon entropy alone ranked VerificationResult as #1 chokepoint (H=0.5186). The RREA Ping Entropy metric (which models information flow attenuation) shows **MergeStrategy** (combined H=0.722) is the true #1 chokepoint. VerificationResult remains important but is secondary.

## Layer 2 Issues (From Teams 1-4 Deep Analysis — 2026-03-31)

| ID | Severity | Issue | Location | Impact |
|----|----------|-------|----------|--------|
| LAY2-003 | 🟠 High | LOC discrepancy — actual 2,573 vs documented 3,984 (35.4% off) | Layer 2 (all modules) | Inaccurate sizing, planning, and complexity estimates |
| LAY2-004 | 🟡 Medium | 2 modules missing `__all__` exports (parallel.py, async_merge.py) | `parallel.py`, `async_merge.py` | Ambiguous public API boundary, star imports unreliable |
| LAY2-005 | 🟠 High | 18 undocumented chokepoints — `arrow._ensure_table` is #1 (H=0.6232) | Layer 2 (arrow.py, dataframe.py, _polars_engine.py, json_merge.py) | Critical internal functions undocumented; maintenance risk |
| LAY2-006 | 🟡 Medium | 41 dead code candidates in _polars_engine.py (mostly local variable false positives) | `_polars_engine.py` | Needs manual triage to separate true dead code from Polars expression-builder patterns |

## Layer 2 RREA Chokepoint Summary (2026-03-31)

| Rank | Symbol | Module | Entropy (H) |
|------|--------|--------|-------------|
| 1 | `_ensure_table` | arrow.py | **0.6232** |
| 2–6 | `_to_records`, `_validate_key_columns`, `_make_composite_key`, `_normalize_key`, `_from_records` | dataframe.py | 0.5982 |
| 7 | `_import_pyarrow` | arrow.py | 0.5976 |
| 8 | `_get_field_strategy` | _polars_engine.py | 0.5597 |
| 9–10 | `_arrow_type_string`, `_schema_dict` | arrow.py | 0.5203 |

> **`arrow._ensure_table`** is the single highest-entropy chokepoint in Layer 2. All Arrow merge paths converge through this function.

## Issue Statistics

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 High | 8 |
| 🟡 Medium | 17 |
| 🟢 Low | 1 |
| **Total** | **28** |

---

*Bugs and Issues v1.2 — updated with Layer 2 Teams 1-4 deep analysis findings*
