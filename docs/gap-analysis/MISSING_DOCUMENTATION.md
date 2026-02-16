# Missing Documentation — Complete Inventory

## Overview

The crdt-merge v0.9.2 codebase has significant documentation gaps, especially in the enterprise and compliance layers.

---

## Documentation Status by Layer

### Layer 1: Core CRDT Primitives — 🟡 Partial
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `core.py` | Auto-generated stub in `docs/api/core.md` | Signatures only, no behavior docs |
| `strategies.py` | Auto-generated stub in `docs/api/strategies.md` | Signatures only |
| `clocks.py` | Auto-generated stub in `docs/api/clocks.md` | Signatures only |
| `probabilistic.py` | Auto-generated stub in `docs/api/probabilistic.md` | Signatures only |
| `dedup.py` | None | ❌ Completely missing |
| `provenance.py` | None | ❌ Completely missing |
| `verify.py` | Auto-generated stub in `docs/api/verify.md` | Signatures only |

### Layer 2: Merge Engines — 🟡 Partial
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `dataframe.py` | Auto-generated stub | Signatures only |
| `streaming.py` | Auto-generated stub | Signatures only |
| `arrow.py` | None | ❌ Completely missing |
| `parquet.py` | None | ❌ Completely missing |
| `parallel.py` | None | ❌ Completely missing |
| `async_merge.py` | None | ❌ Completely missing |
| `json_merge.py` | None | ❌ Completely missing |
| `_polars_engine.py` | None | Internal module — docs not expected |

### Layer 3: Sync & Transport — 🟡 Partial
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `wire.py` | Auto-generated stub | Signatures only |
| `merkle.py` | None | ❌ Completely missing |
| `gossip.py` | None | ❌ Completely missing |
| `delta.py` | None | ❌ Completely missing |
| `schema_evolution.py` | None | ❌ Completely missing |

### Layer 4: AI / Model / Agent — 🟡 Partial
The `model/` subpackage has the best internal documentation, but most other Layer 4 modules are undocumented:
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `model/core.py` | Development docs exist | Partial |
| `model/strategies/` | Development docs exist | Partial |
| `agentic.py` | None | ❌ Completely missing |
| `mergeql.py` | None | ❌ Completely missing |
| `viz.py` | None | ❌ Completely missing |
| `context/` | None | ❌ Completely missing (5 files) |
| `hub/` | None | ❌ Completely missing (2 files) |
| `datasets_ext.py` | None | ❌ Completely missing |
| `flower_plugin.py` | None | ❌ Completely missing |

### Layer 5: Enterprise Wrappers — 🔴 ZERO DOCS
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `audit.py` | None | ❌ **Completely missing** |
| `encryption.py` | None | ❌ **Completely missing** |
| `rbac.py` | None | ❌ **Completely missing** |
| `observability.py` | None | ❌ **Completely missing** |
| `unmerge.py` | None | ❌ **Completely missing** |

> **Layer 5 has 3,323 LOC and ZERO documentation.** This is the most critical gap.

### Layer 6: Verification & Compliance — 🔴 ZERO DOCS
| Module | Existing Docs | Status |
|--------|--------------|--------|
| `compliance.py` | None | ❌ **Completely missing** |

> **Layer 6 has 932 LOC and ZERO documentation.** For a compliance module, this is a critical gap.

### Accelerators — 🟡 Partial
All 8 accelerator modules have auto-generated stubs with signatures only. None have behavioral documentation, usage guides, or examples.

---

## GDEPA + RREA Engine Findings (2026-03-31)

### Undocumented Inherited Methods (GDEPA Runtime Discovery)

| Class | Method | Inherited From | Status |
|-------|--------|---------------|--------|
| `CRDTVerificationError` | `add_note(note: str)` | `BaseException` (Python 3.11+) | ✅ Now documented in `verify.md` |
| `CRDTVerificationError` | `with_traceback(tb)` | `BaseException` | ✅ Now documented in `verify.md` |
| All 8 Strategy Subclasses | `.name` property | `MergeStrategy` | ✅ Now documented in `strategies.md` |

### Critical Chokepoint Needing Thorough Documentation

> ⚠️ **MergeStrategy is the highest-entropy chokepoint in Layer 1** (combined Ping Entropy H=0.722, 9 public endpoints converge). This abstract base class is the single point through which all merge strategy dispatch flows. Documentation must thoroughly cover:
> - The `resolve()` method contract and signature variants
> - The `.name` property inheritance chain
> - Subclassing protocol for custom strategies
> - Thread-safety guarantees (or lack thereof)
> - Serialization behavior (`to_dict()`/`from_dict()` round-trip)

### Dead Code Candidates

| Symbol | Classification | Notes |
|--------|---------------|-------|
| `crdt_merge._load_accelerators` | 🔴 Truly dead | Private function in `__init__.py`, unreachable from any call path |
| `crdt_merge._load_model` | 🔴 Truly dead | Private function in `__init__.py`, unreachable from any call path |

> These 2 functions are the ONLY truly dead code in Layer 1. The 378 "dead" symbols from static RREA were reclassified: 16 are cross-layer (used by L2–L6), 20 are local variables (false positives), and 12 are public methods with cross-layer dependencies.

---

## Summary Statistics

| Category | Modules | Documented | Undocumented | Coverage |
|----------|---------|------------|--------------|----------|
| Layer 1 | 7 | 5 (stubs) | 2 | 71% (stubs) |
| Layer 2 | 8 | 2 (stubs) | 6 | 25% (stubs) |
| Layer 3 | 5 | 1 (stub) | 4 | 20% (stubs) |
| Layer 4 | 16+ | 2 (partial) | 14+ | ~12% |
| Layer 5 | 5 | 0 | 5 | **0%** |
| Layer 6 | 1 | 0 | 1 | **0%** |
| Accelerators | 8 | 8 (stubs) | 0 | 100% (stubs) |
| **Total** | **50+** | **18** | **32+** | **~36%** |

---

---

## Layer 2 GDEPA + RREA Engine Findings (2026-03-31)

### 18 Undocumented Chokepoints (RREA Ping Entropy)

| Rank | Symbol | Module | Entropy (H) | Status |
|------|--------|--------|-------------|--------|
| 1 | `_ensure_table` | arrow.py | 0.6232 | 🔴 Undocumented — highest Layer 2 chokepoint |
| 2 | `_to_records` | dataframe.py | 0.5982 | 🔴 Undocumented |
| 3 | `_validate_key_columns` | dataframe.py | 0.5982 | 🔴 Undocumented |
| 4 | `_make_composite_key` | dataframe.py | 0.5982 | 🔴 Undocumented |
| 5 | `_normalize_key` | dataframe.py | 0.5982 | 🔴 Undocumented |
| 6 | `_from_records` | dataframe.py | 0.5982 | 🔴 Undocumented |
| 7 | `_import_pyarrow` | arrow.py | 0.5976 | 🔴 Undocumented |
| 8 | `_get_field_strategy` | _polars_engine.py | 0.5597 | 🔴 Undocumented |
| 9 | `_arrow_type_string` | arrow.py | 0.5203 | 🔴 Undocumented |
| 10 | `_schema_dict` | arrow.py | 0.5203 | 🔴 Undocumented |
| 11 | `ArrowMerge.timestamp_col` | arrow.py | 0.4547 | 🟡 Partial (signature only) |
| 12 | `ArrowMerge` | arrow.py | 0.4547 | 🟡 Partial (signature only) |
| 13 | `ArrowMerge.schema` | arrow.py | 0.4547 | 🟡 Partial (signature only) |
| 14 | `_list_item_key` | json_merge.py | 0.413 | 🔴 Undocumented |
| 15 | `_has_pyarrow` | arrow.py | 0.396 | 🔴 Undocumented |
| 16 | `merge` | dataframe.py | 0.3853 | ✅ Documented |
| 17 | `merge_dicts` | json_merge.py | 0.2593 | ✅ Documented |
| 18 | `strategy_to_expr` | _polars_engine.py | 0.231 | ✅ Documented |

> ⚠️ **13 of 18 chokepoints are undocumented or only partially documented.** The top 10 are all private helpers with no API docs. `arrow._ensure_table` (H=0.6232) is the single most critical undocumented symbol in Layer 2 — it validates and converts every input to the Arrow merge path.

### 15 Runtime-Only Symbols (GDEPA)

GDEPA runtime introspection discovered 15 symbols across Layer 2's 8 modules that are invisible to static AST analysis. These include dynamically created attributes, runtime-generated properties, and lazy-import artifacts.

### Layer 2 Documentation Coverage Update

| Module | Status | Change |
|--------|--------|--------|
| `dataframe.py` | 🟡 Partial → 🟢 Improved | LOC corrected, chokepoints added |
| `streaming.py` | 🟡 Partial → 🟢 Improved | LOC corrected |
| `arrow.py` | 🟡 Partial → 🟢 Improved | LOC corrected, 8 chokepoints documented |
| `parquet.py` | 🟡 Partial → 🟢 Improved | LOC corrected |
| `parallel.py` | 🟡 Partial → 🟢 Improved | LOC corrected, missing __all__ noted |
| `async_merge.py` | 🟡 Partial → 🟢 Improved | LOC corrected, missing __all__ noted |
| `json_merge.py` | 🟡 Partial → 🟢 Improved | LOC corrected, 2 chokepoints documented |
| `_polars_engine.py` | 🟡 Partial → 🟢 Improved | LOC corrected, dead code + chokepoints documented |

---

*Missing Documentation v1.1 — updated with Layer 2 GDEPA + RREA engine findings*
