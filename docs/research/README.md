# Research: Novel Code Analysis Methods

> **Version:** 2.0 (Hardened — engine mandates and validation gates added)

This directory documents the innovative analysis methods developed during the crdt-merge documentation project.

---

## ⛔ CRITICAL: USE THE ENGINES, NOT APPROXIMATIONS

Each method has a specific implementation that handles edge cases. **Do NOT write simplified inline scripts.** The engines exist for a reason — use them.

| Engine | File | Lines | Why it can't be simplified |
|--------|------|-------|---------------------------|
| GDEPA | `team3_gdepa_engine.py` | ~300 | Runtime `inspect` requires actual module importing; AST-only misses 1,600+ inherited/runtime symbols |
| RREA | `team4_rrea_engine.py` | 556 | Handles indirect calls, super(), decorators, Ping Entropy; simplified versions miss Phase 7+8 |

**Persistent copies** should be at `/agent/home/team3_gdepa_engine.py` and `/agent/home/team4_rrea_engine.py`.

---

## Methods (in execution order)

| # | Method | Team | File | Status |
|---|--------|------|------|--------|
| 1 | **AST Analysis** | Team 1 | (standard tooling) | ✅ Validated |
| 2 | **Regex Pattern Analysis** | Team 2 | (standard tooling) | ✅ Validated |
| 3 | **GDEPA** — Graph-Theoretic Dependency & Execution Path Analysis | Team 3 | [GDEPA_METHOD.md](GDEPA_METHOD.md) + [team3_gdepa_engine.py](team3_gdepa_engine.py) | ✅ Validated |
| 4 | **RREA** — Reverse Reachability Entropy Analysis | Team 4 | [RREA_METHOD.md](RREA_METHOD.md) + [team4_rrea_engine.py](team4_rrea_engine.py) | 🔄 Re-running with full engine |

## How They Work Together

```
Layer N source code
        │
        ▼
   ┌─────────┐     Finds: declared symbols, signatures, decorators
   │  Team 1  │     Method: Python AST parsing
   │   AST    │     Catches: 100% of syntactically declared code
   └────┬─────┘
        │
        ▼
   ┌─────────┐     Finds: code smells, pragmas, patterns
   │  Team 2  │     Method: Regex line-by-line scan
   │  Regex   │     Catches: non-syntactic patterns (type:ignore, noqa, bare except)
   └────┬─────┘
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  Team 3 — GDEPA                                                │
   │  Method: Import/inheritance graph + RUNTIME inspect             │
   │  Catches: everything invisible to static analysis               │
   │                                                                 │
   │  ⚠️ MUST use runtime inspect (import + inspect.getmembers())   │
   │  ⚠️ Static-only graph analysis is NOT GDEPA                    │
   │  ⚠️ If runtime-only symbols = 0, analysis is INCOMPLETE        │
   └────┬────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  Team 4 — RREA                                                  │
   │  Method: Reverse call graph + Shannon entropy + Ping entropy    │
   │  Catches: dead code, critical chokepoints, shadow deps          │
   │                                                                 │
   │  ⚠️ MUST use team4_rrea_engine.py (556 lines)                  │
   │  ⚠️ ALL 8 phases required (especially 7 + 8)                   │
   │  ⚠️ Both Shannon AND Ping entropy required                     │
   │  ⚠️ Do NOT write a simplified inline script                    │
   └────┬────────────────────────────────────────────────────────────┘
        │
        ▼
   Cross-validation & deduplication
        │
        ▼
   Documentation update + GitHub issues (no duplicates)
        │
        ▼
   Master Architect sign-off + Method Compliance Gate (Gate 6)
```

## Each Method's Unique Contribution

Understanding what each method uniquely catches is critical to understanding why **none can be skipped or simplified**:

| Finding | Only Team 1? | Only Team 2? | Only Team 3? | Only Team 4? |
|---------|-------------|-------------|-------------|-------------|
| Function signatures | ✅ | | | |
| Decorator analysis | ✅ | | | |
| Code smell counts | | ✅ | | |
| `type:ignore`/`noqa` pragmas | | ✅ | | |
| Docstring coverage % | | ✅ | | |
| **Inherited methods** | | | ✅ | |
| **Runtime properties** | | | ✅ | |
| **Metaclass-generated methods** | | | ✅ | |
| Circular dependencies | | | ✅ | |
| Layer boundary violations | | | ✅ | |
| **Dead code (unreachable)** | | | | ✅ |
| **Critical chokepoints** | | | | ✅ |
| **Shadow dependencies** | | | | ✅ |
| **Documentation priority** | | | | ✅ |
| **Propagation path issues** | | | | ✅ |

## Cumulative Results (Layer 1)

| Pass | New Symbols Found | New Issues Filed | Unique Contribution |
|------|-------------------|------------------|---------------------|
| Team 1 (AST) | ~640 | #1–#17 | Base inventory |
| Team 2 (Regex) | +549 | #18–#24 | Code smells, missing __all__, docstring gaps |
| Team 3 (GDEPA) | +409 properties, +1,244 inherited | #25–#31 | Circular deps, layer violations, runtime symbols |
| Team 4 (RREA) | 🔄 Re-running | 🔄 Re-running | Dead code, chokepoints, priority ordering |

## Applying to New Codebases

These methods are generic. To use on any Python codebase:
1. Clone the repo and `pip install` it (required for runtime analysis)
2. Run Team 1 AST analysis (standard `ast` module)
3. Run Team 2 regex scan (patterns in MASTER_SOP.md)
4. Run Team 3 GDEPA — **use the engine, ensure runtime inspect runs, verify non-zero runtime-only symbols**
5. Run Team 4 RREA — **use team4_rrea_engine.py, verify all 8 phases complete with non-empty Phase 7+8**
6. Cross-validate, deduplicate, document
7. Pass Method Compliance Gate (PROCESS_GATES.md Gate 6) before advancing

## Known Failure Modes

See `MASTER_SOP.md §2.1` for documented failure modes from past runs, including:
- Simplified GDEPA (static-only, no runtime inspect)
- Simplified RREA (inline script, missing Phase 7+8, no Ping Entropy)
- Zero-count acceptance (accepting 0 runtime symbols as valid)
- Missing persistent engines

---

*Version 2.0 — Hardened after discovering shortcut failures in Layer 1, Session 4.*
