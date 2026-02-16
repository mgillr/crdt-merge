# Layer Map — Detailed Architecture

## Layer 1: Core CRDT Primitives (2,861 LOC)

### Responsibility
Provide mathematically proven conflict-free data types and composable merge strategies.

### Modules
| Module | LOC | Responsibility |
|--------|-----|----------------|
| `core.py` | 238 (321 total) | 5 CRDT types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap |
| `strategies.py` | 291 (378 total) | 8 strategies + MergeSchema: LWW, MaxWins, MinWins, UnionSet, Priority, Concat, LongestWins, Custom |
| `clocks.py` | 222 (325 total) | Causality tracking: VectorClock, DottedVersionVector, Ordering enum |
| `probabilistic.py` | 385 (503 total) | Probabilistic structures: MergeableHLL, MergeableBloom, MergeableCMS |
| `dedup.py` | 195 (261 total) | Deduplication: dedup(), DedupIndex, MinHashDedup |
| `provenance.py` | 301 (384 total) | Provenance tracking: merge_with_provenance(), ProvenanceTracker |
| `verify.py` | 358 (449 total) | CRDT verification: verify_crdt(), @verified_merge, CRDTVerifier |

### Notes
- **LOC updated 2026-03-31** from GDEPA + RREA engine re-analysis. Final count: **2,861 LOC** across 8 modules (415 total symbols, 140 public endpoints). Previous counts: 2,614 (wc -l estimate), 2,122 (AST-only LOC). The 2,861 figure includes docstrings and structural code.
- `__init__.py` (132 LOC) is the package facade — imports from ALL layers to provide flat namespace. Layer violations flagged by GDEPA are expected behavior.
- **0 circular dependencies** confirmed by GDEPA runtime analysis (previous report of 7 was from `__init__.py` facade re-exports, not true cycles).
- **MergeStrategy is the #1 entropy chokepoint** (combined H=0.722, 9 public endpoints converge). All 8 strategy subclasses + MergeSchema depend on it.
- **Dead code corrected:** Only 2 truly dead private functions (`_load_accelerators`, `_load_model`), not 378. The 378 figure from static analysis included 16 cross-layer symbols, 20 local variables, and 12 public methods used by Layers 2–6.

### Key Properties
- Zero external dependencies (stdlib only)
- All operations satisfy: commutative, associative, idempotent
- Deterministic tie-breaking on all strategies

---

## Layer 2: Merge Engines (2,573 LOC)

### Responsibility
Apply Layer 1 strategies to real-world data formats.

### Modules
| Module | LOC | Responsibility |
|--------|-----|----------------|
| `dataframe.py` | 355 | Pandas/Polars DataFrame merging: merge(), diff() |
| `streaming.py` | 288 | Stream merging: merge_stream(), merge_sorted_stream() |
| `arrow.py` | 728 | Apache Arrow engine: ArrowMerge, compute kernels |
| `parquet.py` | 476 | Parquet files: SelfMergingParquet |
| `parallel.py` | 175 | Distributed: parallel_merge() |
| `async_merge.py` | 140 | Async: amerge(), amerge_stream() |
| `json_merge.py` | 105 | JSON/dict: merge_dicts(), merge_json_lines() |
| `_polars_engine.py` | 306 | Internal Polars engine (**private** — underscore-prefixed, not public API; accessed via `dataframe.py` Polars backend) |

### Notes
- **LOC updated 2026-03-31** from Teams 1+2 (AST + Regex) re-analysis. Final count: **2,573 LOC** across 8 modules (73 total symbols: 7 classes, 56 functions). Previous inventory count: 3,984 (delta: -1,411 = 35.4% off). The 3,984 figure likely included docstrings, comments, blank lines, and wc -l overcounting.
- **Docstring coverage:** 93.8% (90/96 symbols have docstrings)
- **Missing `__all__`:** `parallel.py` and `async_merge.py` do not define `__all__` exports
- **4 `type: ignore` suppressions**, 1 `noqa` — minimal suppression count
- **0 TODOs/FIXMEs** — clean codebase
- **Layer 1 dependencies:** `crdt_merge.strategies`, `crdt_merge.schema_evolution`
- **0 inherited methods** in Layer 2 (correct — Layer 2 is mostly functional: 56 functions vs 7 classes with no deep inheritance)
- **15 runtime-only symbols** discovered by GDEPA across 8 modules
- **18 undocumented chokepoints** identified by RREA — `arrow._ensure_table` is #1 (H=0.6232)
- **41 dead code candidates** in `_polars_engine.py` — mostly local variable false positives from static analysis on Polars expressions

---

## Layer 3: Sync & Transport (2,626 LOC)

### Responsibility
Serialize, transmit, and synchronize merge state across networks.

### Modules
| Module | LOC | Responsibility |
|--------|-----|----------------|
| `wire.py` | 740 | Binary protocol: serialize(), deserialize(), peek() |
| `merkle.py` | 554 | Tree-based sync: MerkleTree, merkle_diff() |
| `gossip.py` | 546 | Gossip protocol: GossipState, anti_entropy() |
| `delta.py` | 367 | Delta compression: DeltaStore, compute_delta() |
| `schema_evolution.py` | 419 | Schema versioning: evolve_schema(), check_compatibility() |

---

## Layer 4: AI / Model / Agent (18,410 LOC)

### Responsibility
ML model merging, agentic AI state, and advanced tooling.

### Sub-packages
| Package/Module | LOC | Responsibility |
|--------|-----|----------------|
| `model/` | 15,464 | Model merging with 26+ strategies |
| `model/strategies/` | ~3,000 | Strategy implementations (9 modules) |
| `context/` | 1,535 | Agent context management (5 modules) |
| `hub/` | 726 | HuggingFace Hub integration (2 modules) |
| `agentic.py` | 402 | AgentState, SharedKnowledge |
| `mergeql.py` | 743 | MergeQL DSL |
| `viz.py` | 509 | Conflict visualization |
| `datasets_ext.py` | 106 | HF Datasets integration |
| `flower_plugin.py` | 500 | Flower FL plugin |

---

## Layer 5: Enterprise Wrappers (3,323 LOC)

### Responsibility
Production-grade security, auditing, and operations.

### Modules
| Module | LOC | Responsibility |
|--------|-----|----------------|
| `audit.py` | 430 | SHA-256 chained audit log |
| `encryption.py` | 669 | 4 crypto backends, key rotation |
| `rbac.py` | 357 | Role-based access control |
| `observability.py` | 1,034 | Metrics, tracing, Prometheus, Grafana |
| `unmerge.py` | 833 | Undo merges, GDPR forget |

---

## Layer 6: Verification & Compliance (932 LOC)

### Responsibility
Regulatory compliance auditing and reporting.

### Modules
| Module | LOC | Responsibility |
|--------|-----|----------------|
| `compliance.py` | 932 | ComplianceAuditor, EUAIActReport, GDPR/HIPAA/SOX |

---

*Layer Map v1.0*
