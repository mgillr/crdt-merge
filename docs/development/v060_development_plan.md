# crdt-merge v0.6.0 — Synchronized Development Plan

**"The Performance Release"**
**Date:** March 28, 2026
**Baseline:** v0.5.0 (commit 71930682680544b9ca09fe00a1a4431125d8b103)
**Target LOC:** ~6,200 (+2,172) · **Target Tests:** ~720 (+295)
**Breaking Changes:** 0
**Contact:** rgillespie83@icloud.com · data@optitransfer.ch
**Copyright:** Copyright 2026 Ryan Gillespie / Optitransfer

---

> **Purpose**: This document is the DEFINITIVE synchronized development plan for crdt-merge v0.6.0. It must be read alongside the **MASTER KEY** (`crdt_merge_master_key_v050.md`). Together they form the complete contract: the MASTER KEY defines what EXISTS, this plan defines what will BE BUILT, by whom, in what order, and with what constraints.

> **Golden Rule**: ZERO regressions. The 425 existing tests are sacred. Every new module is additive. Every new type obeys the CRDT trinity: `.merge()`, `.to_dict()`, `.from_dict()`.

---

## 1. BASELINE LOCK — SHA Registry

This section lists EVERY existing file in the codebase with its GitHub blob SHA. This is the "do not break" contract. Any modification to these files that breaks their public API or fails existing tests is a **blocking defect**.

### Source Files (`crdt_merge/`)

| File | SHA | Size |
|------|-----|------|
| `__init__.py` | `e3d8084d77c54875c6e241e36000b241eb4d1115` | 2,852 bytes |
| `core.py` | `4b871c57a5ebab0ba863c87508fc43392d6d4298` | 10,798 bytes |
| `strategies.py` | `7edbf31c4589f8483cd2db871018ea5281a7b81f` | 11,893 bytes |
| `dataframe.py` | `67a1ab63360d7de91aead43bf88ee86b4b7b50df` | 10,226 bytes |
| `datasets_ext.py` | `6fdbb86563f70846b12e2d5977c9bec426c51ab5` | 2,665 bytes |
| `dedup.py` | `ca40fefd958d2485e6c7acd890662d02e9d50859` | 7,241 bytes |
| `delta.py` | `4ad545ad80c003af255cbc0eccf129ffdd09876b` | 10,319 bytes |
| `json_merge.py` | `759696b543904ca9a5cdb063bc0f5f78d9a1e731` | 3,816 bytes |
| `probabilistic.py` | `4d94ed1fa2f7592c34a70bbb09e790a425c19965` | 18,155 bytes |
| `provenance.py` | `ae41ae7c533d0ae1725effd524cd49ae8bf46312` | 12,788 bytes |
| `streaming.py` | `9e09eecfd2f2b68bc4cac1c4a58e7a138f924c67` | 12,094 bytes |
| `verify.py` | `17c5eac6b5480dde91a6338dd303e7e2eac3886e` | 13,769 bytes |
| `wire.py` | `05aeaea241166b4f8ef30cf925ec81eda264207a` | 15,030 bytes |

### Test Files (`tests/`)

| File | SHA | Size |
|------|-----|------|
| `test_architect_360_validation.py` | `b55ddcca277bb19a1b6ac30539e5e402038acf6a` | 39,590 bytes |
| `test_benchmark.py` | `a4be97304a470249cbc1f89922a36e73798b6e30` | 2,776 bytes |
| `test_core.py` | `5633249fcb436f53fb80f5267f650840115f85d8` | 6,285 bytes |
| `test_dataframe.py` | `5777b740b736818608c1d56d0f757bbb062483c9` | 3,509 bytes |
| `test_dedup.py` | `d14e99e6e1dd7db4dd5cf18a9a7b44e9c66b99fc` | 3,767 bytes |
| `test_json_merge.py` | `a2969798806713ddb0c0f0ffc06feb818a5d6e7e` | 2,097 bytes |
| `test_longest_wins.py` | `02d3d91112b651276f93304f5eceb23d7eb12719` | 2,553 bytes |
| `test_probabilistic.py` | `e8878fb69b5a12c2ada2e2913918416ea931e8a6` | 13,140 bytes |
| `test_provenance.py` | `7cf7f8e73ceb7b361d68e67a99699198af2a30c9` | 11,162 bytes |
| `test_strategies.py` | `f01b46372b1554c0c417788b1bc4c732c6af6f8d` | 9,393 bytes |
| `test_streaming.py` | `b5dbfaaaadbcfa25b6327c2b4a4b4f1b5f50822d` | 8,680 bytes |
| `test_stress_v030.py` | `a82a56110e01255938097a33bef53141941af937` | 17,720 bytes |
| `test_v050_integration.py` | `d1d95e8ac2b937156cc995a3ae4c8ff606241ea7` | 52,887 bytes |
| `test_verified_merge.py` | `f1d141462d2c921349e7203bf2dd4e8c78039517` | 3,653 bytes |
| `test_wire.py` | `7333ff044e80e9f45d477a6fda4e7ca6eab4e578` | 11,062 bytes |

### Baseline Totals

- **13 source modules** — 3,957 LOC
- **15 test files** — 425 tests
- **All 425 tests MUST pass UNCHANGED** after v0.6.0 code is merged

---

## 2. NEW MODULES — v0.6.0 Scope

### New Modules to Create

| New Module | Est. Lines | Purpose | Dependencies |
|------------|-----------|---------|--------------|
| `clocks.py` | ~200 | Vector clocks, causality detection, dotted version vectors | `core.py` (CRDT pattern only) |
| `schema_evolution.py` | ~300 | Schema drift detection & resolution with 4 policies | `core.py` (types only) |
| `merkle.py` | ~400 | Merkle tree diff for efficient sync | `hashlib` (stdlib) |
| `arrow.py` | ~800 | Arrow-native merge engine with zero-copy ops | `pyarrow` (lazy import), `strategies.py`, `core.py`, `schema_evolution.py` |
| `gossip.py` | ~400 | Gossip state management (no networking) | `core.py`, `clocks.py` |
| `async_merge.py` | ~150 | Async wrappers for merge operations | `dataframe.py`, `streaming.py` |
| `parallel.py` | ~200 | Thread-pool parallel merge | `concurrent.futures` (stdlib), `dataframe.py` |

**Subtotal new modules: ~2,450 lines across 7 files**

### Modifications to Existing Modules

| Existing Module | Change | Est. Lines Added | Owner Restriction |
|----------------|--------|-----------------|-------------------|
| `dataframe.py` | Multi-key merge support (composite & hierarchical keys) | ~120 | Dev C ONLY |
| `wire.py` | New wire tags for VectorClock, MerkleTree, GossipState, SchemaEvolution | ~80 | Dev E ONLY |
| `__init__.py` | New exports for all v0.6.0 modules | ~40 | Dev E ONLY |

**Total estimated additions: ~2,172 lines → ~6,200 total LOC**

### Layer Diagram (v0.6.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                                │
│  __init__.py  ·  datasets_ext.py  ·  async_merge.py (NEW)       │
├─────────────────────────────────────────────────────────────────┤
│                    ORCHESTRATION LAYER                            │
│  dataframe.py (+multi-key)  ·  streaming.py  ·  provenance.py   │
│  parallel.py (NEW)  ·  arrow.py (NEW)                           │
├─────────────────────────────────────────────────────────────────┤
│                      ENGINE LAYER                                │
│  strategies.py  ·  delta.py  ·  json_merge.py  ·  dedup.py      │
│  verify.py  ·  gossip.py (NEW)  ·  schema_evolution.py (NEW)    │
├─────────────────────────────────────────────────────────────────┤
│                    FOUNDATION LAYER                               │
│  core.py  ·  probabilistic.py  ·  wire.py (+tags)               │
│  clocks.py (NEW)  ·  merkle.py (NEW)                            │
└─────────────────────────────────────────────────────────────────┘
```

### Internal Dependency Graph (new modules)

```
clocks.py ──────────► core.py (CRDT pattern: merge, to_dict, from_dict)

schema_evolution.py ─► (no internal deps, stdlib only)

merkle.py ──────────► hashlib (stdlib only)

arrow.py ───────────► strategies.py (existing), core.py (existing)
                    ► schema_evolution.py (NEW — Phase 1)
                    ► pyarrow (LAZY import, optional)

gossip.py ──────────► core.py (existing), clocks.py (NEW — Phase 1)

async_merge.py ─────► dataframe.py (existing), streaming.py (existing)
                    ► asyncio (stdlib)

parallel.py ────────► dataframe.py (existing)
                    ► concurrent.futures (stdlib)
```

---

## 3. BUILD ORDER — Dependency-Aware Sequence

### Phase 1 — Foundation (no dependencies on other new modules)

These three modules can be built **in parallel** — they have zero dependencies on each other or on any other new module.

| Order | Module | Depends On | Estimated Duration |
|-------|--------|-----------|-------------------|
| 1a | `clocks.py` | `core.py` (pattern only, read-only) | 1-2 weeks |
| 1b | `schema_evolution.py` | stdlib only | 1-2 weeks |
| 1c | `merkle.py` | `hashlib` (stdlib only) | 1-2 weeks |

**Phase 1 Gate**: All three modules pass unit tests + CRDT law verification (for `clocks.py`).

### Phase 2 — Engine (depends on Phase 1 outputs)

These modules depend on Phase 1 deliverables and/or existing modules.

| Order | Module | Depends On (new) | Depends On (existing) | Estimated Duration |
|-------|--------|------------------|----------------------|-------------------|
| 2a | `arrow.py` | `schema_evolution.py` (Phase 1b) | `strategies.py`, `core.py` | 3-4 weeks |
| 2b | `gossip.py` | `clocks.py` (Phase 1a) | `core.py` | 2-3 weeks |
| 2c | Multi-key merge in `dataframe.py` | — | `dataframe.py` (extend) | 1-2 weeks |

**Phase 2 Gate**: Arrow merge 10x benchmark target met, gossip convergence proven, multi-key tests pass.

### Phase 3 — Wrappers (depends on Phase 2 stability)

These are thin wrappers that depend on stable Phase 2 APIs.

| Order | Module | Wraps | Estimated Duration |
|-------|--------|-------|-------------------|
| 3a | `async_merge.py` | `dataframe.py`, `streaming.py` | 1 week |
| 3b | `parallel.py` | `dataframe.py` | 1 week |

**Phase 3 Gate**: Async and parallel tests pass, no deadlocks, proper fallback behavior.

### Phase 4 — Integration (depends on all previous phases)

| Order | Task | Modifies | Estimated Duration |
|-------|------|----------|-------------------|
| 4a | `wire.py` updates | Add tags 0x40-0x43 | 1 week |
| 4b | `__init__.py` updates | Add all new exports | 1 day |
| 4c | `test_v060_integration.py` | New file, cross-module tests | 1-2 weeks |
| 4d | Regression gate | Run full 720-test suite | 2-3 days |

**Phase 4 Gate**: All 720 tests pass. `crdt_merge.__version__` returns `0.6.0`.

### Critical Path

```
Phase 1a (clocks) ──► Phase 2b (gossip) ──┐
Phase 1b (schema) ──► Phase 2a (arrow)  ──┤
Phase 1c (merkle) ────────────────────────┤
                    Phase 2c (multi-key) ──┼──► Phase 3 (wrappers) ──► Phase 4 (integration)
```

---

## 4. MODULE OWNERSHIP MATRIX

### Assignment Rules

1. Each new module has ONE owner — that dev makes all decisions for that module
2. Existing modules are **read-only** unless explicitly granted modify rights
3. Only the assigned dev may commit to their owned modules
4. All other devs may READ any module but WRITE only to their assigned set

### Ownership Table

| Dev | v0.6.0 Modules (WRITE) | Existing Modules (access) | Phase | Estimated Effort |
|-----|------------------------|--------------------------|-------|-----------------|
| **Dev A** | `clocks.py`, `gossip.py` | `core.py` (READ) | 1a, 2b | 4-5 weeks |
| **Dev B** | `arrow.py`, `schema_evolution.py` | `strategies.py` (READ), `core.py` (READ), `dataframe.py` (READ) | 1b, 2a | 5-6 weeks |
| **Dev C** | `merkle.py`, multi-key in `dataframe.py` | `dataframe.py` (MODIFY §4.3 multi-key extension ONLY) | 1c, 2c | 3-4 weeks |
| **Dev D** | `async_merge.py`, `parallel.py` | `streaming.py` (READ), `dataframe.py` (READ) | 3 | 2-3 weeks |
| **Dev E** (Integration Lead) | `wire.py` updates, `__init__.py` updates, `test_v060_integration.py` | `wire.py` (MODIFY — new tags only), `__init__.py` (MODIFY — new exports only) | 4 | 2-3 weeks |

### Dev A — `clocks.py` + `gossip.py`

**Responsibilities:**
- Implement `VectorClock` with full CRDT compliance (merge returns NEW instance)
- Implement `DottedVersionVector` for scalable clock management
- Implement `Ordering` enum (BEFORE, AFTER, CONCURRENT, EQUAL)
- Implement `GossipState` with anti-entropy digest generation
- All types must pass CRDT law verification
- Wire serialization support (provide `to_dict`/`from_dict`; Dev E handles wire tags)

### Dev B — `arrow.py` + `schema_evolution.py`

**Responsibilities:**
- Implement `SchemaPolicy` enum (UNION, INTERSECTION, LEFT_PRIORITY, RIGHT_PRIORITY)
- Implement `evolve_schema()` with type widening and default injection
- Implement `ArrowMerge` class with zero-copy merge on `pa.Table` and `pa.RecordBatch`
- Implement columnar strategy application (vectorized, no row iteration)
- Implement streaming merge for Arrow IPC files
- Implement memory-mapped merge for datasets larger than RAM
- Implement automatic fallback to pure-Python when Arrow is unavailable
- PyArrow must be LAZY IMPORTED — `import pyarrow` only inside functions that need it
- Meet benchmark target: 10x faster than dict-of-dicts for 1M+ rows

### Dev C — `merkle.py` + multi-key in `dataframe.py`

**Responsibilities:**
- Implement `MerkleTree` with SHA-256 content hashing
- Implement incremental tree updates (insert/update/delete without full rebuild)
- Implement `merkle_diff()` with O(log n) comparison
- Configurable branching factor
- Extend `dataframe.py` with composite key support (tuple keys)
- Extend `dataframe.py` with hierarchical key resolution (primary + secondary)
- **CRITICAL**: Changes to `dataframe.py` must not alter any existing function signatures. Multi-key is ADDITIVE — the existing `key: Optional[str]` parameter now also accepts `List[str]`

### Dev D — `async_merge.py` + `parallel.py`

**Responsibilities:**
- Implement `amerge()` — async wrapper for `dataframe.merge()`
- Implement `amerge_stream()` — async generator wrapper for `streaming.merge_stream()`
- Implement `parallel_merge()` — thread-pool parallel merge with configurable chunk size
- Automatic fallback to sequential for small datasets (< 10,000 rows)
- Proper exception handling and cancellation support
- No new dependencies — uses `asyncio` and `concurrent.futures` (stdlib)

### Dev E — Integration Lead

**Responsibilities:**
- Add wire tags 0x40-0x43 for new types
- Update `__init__.py` with all new public exports
- Write `test_v060_integration.py` (~70 tests)
- Run and verify full regression suite (425 existing + ~295 new)
- Coordinate final merge order across all PRs
- Version bump to 0.6.0

---

## 5. COLLISION PREVENTION RULES

### Absolute Rules (violation = blocking PR rejection)

**Rule 1: API Preservation**
NEVER modify an existing module's public API signature. Parameters may not be removed or reordered. New parameters must have defaults. Return types must not change.

**Rule 2: Import-Only Access**
New modules may IMPORT from existing modules but NEVER modify them. Treat existing modules as read-only libraries.

**Rule 3: Exclusive Write Access**
- Only **Dev C** modifies `dataframe.py` (adding multi-key support)
- Only **Dev E** modifies `wire.py` (adding new tags) and `__init__.py` (adding exports)
- NO OTHER DEV touches these files

**Rule 4: CRDT Trinity**
All new CRDT types MUST implement the trinity pattern:
```python
class NewType:
    def merge(self, other: 'NewType') -> 'NewType':  # returns NEW instance
        ...
    def to_dict(self) -> dict:
        ...
    @classmethod
    def from_dict(cls, d: dict) -> 'NewType':
        ...
```

**Rule 5: Zero Required Dependencies**
All new modules must have zero required dependencies beyond the Python stdlib. Optional dependencies (PyArrow, etc.) MUST be lazy-imported:
```python
# CORRECT:
def merge_arrow(left, right):
    try:
        import pyarrow as pa
    except ImportError:
        raise ImportError("pyarrow required for Arrow merge: pip install pyarrow")
    ...

# WRONG:
import pyarrow as pa  # top-level import breaks zero-dep guarantee
```

**Rule 6: Regression Gate**
The existing 425 tests must pass **UNCHANGED** after all v0.6.0 code is added. Run `pytest tests/` — all green or the build is rejected. No test file in the baseline SHA registry may be modified.

### Advisory Rules (best practice)

**Rule 7: Immutable Merge**
All `.merge()` operations return a NEW instance. Never mutate `self` or `other`.

**Rule 8: None/Empty Handling**
All public functions must handle `None`, empty lists `[]`, empty dicts `{}`, and empty DataFrames gracefully. Never raise on empty input unless semantically invalid.

**Rule 9: Type Hints**
All public APIs must have complete type hints. Use `Optional[]` for nullable parameters.

**Rule 10: Docstrings**
All public classes and functions must have docstrings with at minimum: one-line summary, parameter descriptions, return type description, and one usage example.

---

## 6. TEST SPECIFICATIONS

### New Test Files

| New Test File | Min Tests | Coverage Requirements | Owner |
|---------------|-----------|----------------------|-------|
| `tests/test_clocks.py` | ~30 | VectorClock create/increment/merge/compare, DottedVersionVector, Ordering enum, serialization roundtrip, CRDT law verification, edge cases (empty clocks, single-node, 100-node) | Dev A |
| `tests/test_schema_evolution.py` | ~25 | All 4 policies (UNION, INTERSECTION, LEFT_PRIORITY, RIGHT_PRIORITY), type widening (int→float, int32→int64), missing column defaults, empty schemas, incompatible types, Arrow schema integration | Dev B |
| `tests/test_merkle.py` | ~35 | Build from records, diff identical trees, diff divergent trees, incremental update (insert/update/delete), serialization roundtrip, large datasets (10K+ records), configurable branching, edge cases (empty tree, single record) | Dev C |
| `tests/test_arrow.py` | ~50 | Zero-copy merge (pa.Table, pa.RecordBatch), all 8 strategies on Arrow, streaming Arrow IPC merge, memory-mapped merge, fallback to pure-Python, schema evolution during merge, benchmark assertions (10x target), edge cases (empty tables, mismatched schemas, null values) | Dev B |
| `tests/test_gossip.py` | ~30 | GossipState create/update/merge, anti_entropy digest generation, push/pull/push-pull modes, multi-node convergence (3, 5, 10 nodes), CRDT law verification, edge cases (empty state, single entry, concurrent updates) | Dev A |
| `tests/test_async_merge.py` | ~20 | amerge basic merge, amerge with schema, amerge_stream batched output, cancellation handling, error propagation, empty input, concurrent amerge calls | Dev D |
| `tests/test_parallel.py` | ~20 | parallel_merge basic, configurable chunk size, configurable worker count, fallback to sequential for small datasets, error handling in workers, thread safety, empty input | Dev D |
| `tests/test_multi_key.py` | ~15 | Composite key (2-col, 3-col), hierarchical key resolution, backward compatibility (single key string still works), edge cases (None in key columns, duplicate composite keys) | Dev C |
| `tests/test_v060_integration.py` | ~70 | Cross-module pipelines (see §6.2 below) | Dev E |

**Total new tests: ~295 → Combined total: ~720**

### 6.1 CRDT Law Tests (MANDATORY)

Every new type that implements `.merge()` MUST pass all four CRDT law verifications. These tests use the existing `verify.py` infrastructure.

**Types requiring CRDT law verification:**

| Type | Module | Generator Function |
|------|--------|--------------------|
| `VectorClock` | `clocks.py` | Random clock with 1-10 nodes, counts 0-100 |
| `DottedVersionVector` | `clocks.py` | Random DVV with 1-5 nodes |
| `MerkleTree` | `merkle.py` | Random tree with 10-100 records |
| `GossipState` | `gossip.py` | Random state with 1-20 keys |

**Required test pattern for each type:**
```python
from crdt_merge.verify import verify_commutative, verify_associative, verify_idempotent, verify_convergence

def gen_vector_clock():
    """Generate random VectorClock for property testing."""
    import random
    nodes = [f"node-{i}" for i in range(random.randint(1, 10))]
    vc = VectorClock()
    for node in nodes:
        for _ in range(random.randint(0, 20)):
            vc.increment(node)
    return vc

def test_vector_clock_commutative():
    result = verify_commutative(lambda a, b: a.merge(b), gen_vector_clock, trials=1000)
    assert result.passed, f"Commutativity failed: {result.first_failure}"

def test_vector_clock_associative():
    result = verify_associative(lambda a, b: a.merge(b), gen_vector_clock, trials=1000)
    assert result.passed, f"Associativity failed: {result.first_failure}"

def test_vector_clock_idempotent():
    result = verify_idempotent(lambda a, b: a.merge(b), gen_vector_clock, trials=1000)
    assert result.passed, f"Idempotency failed: {result.first_failure}"

def test_vector_clock_convergence():
    result = verify_convergence(lambda a, b: a.merge(b), gen_vector_clock, trials=500, num_replicas=5)
    assert result.passed, f"Convergence failed: {result.first_failure}"
```

### 6.2 Integration Test Scenarios (`test_v060_integration.py`)

The integration test file must cover these cross-module pipelines:

1. **Arrow + Schema Evolution Pipeline** (~10 tests)
   - Arrow merge with schema drift → automatic resolution
   - Arrow merge fallback when pyarrow not installed
   - Arrow merge with all 8 merge strategies

2. **Gossip + Vector Clock Pipeline** (~10 tests)
   - Multi-node gossip convergence using vector clocks for causality
   - Anti-entropy sync cycle: digest → diff → merge → converge
   - Concurrent update detection and resolution

3. **Merkle + Delta Pipeline** (~10 tests)
   - Merkle diff → Delta compute → Delta apply cycle
   - Incremental sync using Merkle trees to find divergent keys

4. **Arrow + Parallel Pipeline** (~8 tests)
   - Parallel merge using Arrow backend
   - Chunk-based parallel merge with schema evolution

5. **Async + Streaming Pipeline** (~8 tests)
   - Async streaming merge end-to-end
   - Async merge with provenance tracking

6. **Multi-Key + Existing Features Pipeline** (~8 tests)
   - Multi-key merge with schema strategies
   - Multi-key merge with provenance
   - Multi-key merge with streaming

7. **Wire Protocol v2 Roundtrip** (~8 tests)
   - Serialize/deserialize all new types (VectorClock, MerkleTree, GossipState, SchemaEvolution)
   - Batch serialize/deserialize mixed old + new types
   - Backward compatibility: v1 wire data still deserializes correctly

8. **Full End-to-End Scenarios** (~8 tests)
   - Complete distributed merge simulation: gossip → merkle diff → arrow merge → provenance
   - Large-scale regression: 100K records through Arrow merge → verify CRDT laws on output
   - Verify all v0.5.0 examples from MASTER KEY §14 still work exactly as documented

---

## 7. DETAILED MODULE SPECIFICATIONS

### 7.1 `clocks.py` — Vector Clocks & Causality Detection (~200 lines)

**Purpose:** Provide logical clock primitives for distributed causality tracking. These are pure CRDT types used by `gossip.py` and available independently.

#### Classes & Signatures

```python
"""Vector clocks and causality detection for distributed CRDT systems."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any


class Ordering(Enum):
    """Causal ordering between two vector clocks."""
    BEFORE = "before"           # a happened-before b
    AFTER = "after"             # b happened-before a
    CONCURRENT = "concurrent"   # neither happened-before the other
    EQUAL = "equal"             # identical clocks


@dataclass
class VectorClock:
    """
    Vector clock for tracking causality in distributed systems.
    
    Each node maintains a counter. Merge takes element-wise max.
    This is a CRDT: merge is commutative, associative, and idempotent.
    
    Example:
        vc1 = VectorClock({"a": 3, "b": 1})
        vc2 = VectorClock({"a": 2, "b": 4})
        merged = vc1.merge(vc2)  # VectorClock({"a": 3, "b": 4})
        print(vc1.compare(vc2))  # Ordering.CONCURRENT
    """
    _clocks: Dict[str, int] = field(default_factory=dict)
    
    def __init__(self, clocks: Optional[Dict[str, int]] = None):
        """
        Args:
            clocks: Initial clock values. Keys are node IDs, values are counters.
        """
        ...
    
    def increment(self, node_id: str) -> VectorClock:
        """
        Increment the counter for the given node. Returns NEW instance.
        
        Args:
            node_id: The node whose counter to increment.
        Returns:
            New VectorClock with incremented counter.
        """
        ...
    
    def get(self, node_id: str) -> int:
        """Get the counter value for a node (0 if not present)."""
        ...
    
    @property
    def value(self) -> Dict[str, int]:
        """Return a copy of the clock dictionary."""
        ...
    
    def compare(self, other: VectorClock) -> Ordering:
        """
        Compare two vector clocks for causal ordering.
        
        Returns:
            Ordering.BEFORE if self happened-before other.
            Ordering.AFTER if other happened-before self.
            Ordering.CONCURRENT if neither.
            Ordering.EQUAL if identical.
        """
        ...
    
    def merge(self, other: VectorClock) -> VectorClock:
        """
        Merge two vector clocks (element-wise max). Returns NEW instance.
        
        This is the CRDT merge operation — commutative, associative, idempotent.
        """
        ...
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        ...
    
    @classmethod
    def from_dict(cls, d: dict) -> VectorClock:
        """Deserialize from dictionary."""
        ...
    
    def __eq__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...


@dataclass
class DottedVersionVector:
    """
    Dotted version vector for scalable clock management.
    
    Extends VectorClock with a "dot" for the latest event,
    enabling more compact representation in large node sets.
    Implements the CRDT trinity: merge, to_dict, from_dict.
    """
    _base: VectorClock = field(default_factory=VectorClock)
    _dot: Optional[tuple] = None  # (node_id, counter)
    
    def __init__(self, base: Optional[VectorClock] = None, 
                 dot: Optional[tuple] = None): ...
    
    def advance(self, node_id: str) -> DottedVersionVector:
        """Advance the dot for this node. Returns NEW instance."""
        ...
    
    def merge(self, other: DottedVersionVector) -> DottedVersionVector:
        """Merge two dotted version vectors. Returns NEW instance."""
        ...
    
    def descends(self, other: DottedVersionVector) -> bool:
        """Check if self causally descends from (or equals) other."""
        ...
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, d: dict) -> DottedVersionVector: ...
```

#### Integration Points
- **Imports from existing:** `core.py` pattern only (no direct import needed, follows same design)
- **Consumed by:** `gossip.py` (Phase 2), `wire.py` (Phase 4)
- **Key invariant:** `merge()` always returns NEW instance, never mutates

#### Edge Cases
- Empty clocks: `VectorClock({})` — valid, represents "no events seen"
- Single-node: `VectorClock({"a": 5})` — common case in single-writer scenarios
- 100+ nodes: Must handle large node sets without performance degradation
- Zero counters: `VectorClock({"a": 0})` vs `VectorClock({})` — both valid, treat as equivalent
- Negative counters: Reject with `ValueError` (counters are monotonically increasing)

---

### 7.2 `schema_evolution.py` — Schema Drift Detection & Resolution (~300 lines)

**Purpose:** Automatically detect and resolve schema differences between datasets being merged. Supports 4 policies and integrates with Arrow schemas.

#### Classes & Signatures

```python
"""Schema drift detection and resolution for evolving datasets."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class SchemaPolicy(Enum):
    """Policy for resolving schema differences."""
    UNION = "union"                    # Keep all columns from both sides
    INTERSECTION = "intersection"      # Keep only common columns
    LEFT_PRIORITY = "left_priority"    # Keep left schema, add new from right
    RIGHT_PRIORITY = "right_priority"  # Keep right schema, add new from left


# Type widening rules: (from_type, to_type)
TYPE_WIDENING = {
    ("int32", "int64"): "int64",
    ("float32", "float64"): "float64",
    ("int32", "float32"): "float32",
    ("int32", "float64"): "float64",
    ("int64", "float64"): "float64",
    ("str", "str"): "str",
    ("int", "float"): "float",
}


@dataclass
class SchemaChange:
    """Represents a single schema change."""
    column: str
    change_type: str    # 'added', 'removed', 'type_changed', 'unchanged'
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    resolved_type: Optional[str] = None
    default_value: Any = None


@dataclass
class SchemaEvolutionResult:
    """Result of schema evolution."""
    resolved_schema: Dict[str, str]           # column -> type
    changes: List[SchemaChange]               # list of all changes
    defaults: Dict[str, Any]                  # column -> default value for missing
    policy_used: SchemaPolicy
    is_compatible: bool                       # True if no lossy changes
    warnings: List[str]                       # type narrowing warnings, etc.
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, d: dict) -> SchemaEvolutionResult: ...


def evolve_schema(
    old: Dict[str, str],
    new: Dict[str, str],
    policy: SchemaPolicy = SchemaPolicy.UNION,
    defaults: Optional[Dict[str, Any]] = None,
    allow_type_narrowing: bool = False
) -> SchemaEvolutionResult:
    """
    Detect and resolve schema drift between two schemas.
    
    Args:
        old: Current schema as {column: type} dict.
        new: Incoming schema as {column: type} dict.
        policy: Resolution policy.
        defaults: Default values for missing columns.
        allow_type_narrowing: If True, allow narrowing (e.g., float64→int32). Default False.
    
    Returns:
        SchemaEvolutionResult with resolved schema and change details.
    
    Example:
        result = evolve_schema(
            old={"id": "int", "name": "str"},
            new={"id": "int", "name": "str", "email": "str", "age": "int"},
            policy=SchemaPolicy.UNION
        )
        # result.resolved_schema = {"id": "int", "name": "str", "email": "str", "age": "int"}
    """
    ...


def check_compatibility(
    schema_a: Dict[str, str],
    schema_b: Dict[str, str]
) -> Tuple[bool, List[str]]:
    """
    Check if two schemas are compatible for merge without evolution.
    
    Returns:
        (is_compatible, list_of_issues)
    """
    ...


def widen_type(type_a: str, type_b: str) -> Optional[str]:
    """
    Find the widened type that can hold both types without loss.
    
    Returns None if types are incompatible.
    """
    ...
```

#### Integration Points
- **Imports from existing:** None (pure standalone)
- **Consumed by:** `arrow.py` (Phase 2) for Arrow schema reconciliation
- **Key invariant:** UNION policy never drops data; INTERSECTION may

#### Edge Cases
- Empty schema on one side: `{}` — valid, represents "no columns"
- Same schema: No changes → pass through
- Type narrowing: `float64` → `int32` — warn and reject unless `allow_type_narrowing=True`
- Unknown types: Treat as opaque strings, skip widening
- `None` in defaults: Valid — `None` is the default default

---

### 7.3 `merkle.py` — Merkle Tree Diff for Efficient Sync (~400 lines)

**Purpose:** Content-addressable hash trees for O(log n) comparison of record sets. Used to efficiently find which records differ between two replicas.

#### Classes & Signatures

```python
"""Merkle tree construction and diff for efficient dataset synchronization."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple


@dataclass
class MerkleNode:
    """A node in the Merkle tree."""
    hash: str                                    # SHA-256 hex digest
    children: Optional[List[MerkleNode]] = None  # None for leaf nodes
    key_range: Optional[Tuple[str, str]] = None  # (min_key, max_key) for this subtree
    count: int = 0                               # number of records in this subtree


class MerkleTree:
    """
    Merkle tree for efficient dataset diff and sync.
    
    Uses SHA-256 hashing. Supports incremental updates and O(log n) diff.
    Implements the CRDT trinity for serialization.
    
    Example:
        tree1 = MerkleTree.from_records(dataset_a, key="id")
        tree2 = MerkleTree.from_records(dataset_b, key="id")
        diff = merkle_diff(tree1, tree2)
        # diff.differing_keys = {"id-42", "id-99"}  — only these need sync
    """
    
    def __init__(self, branching_factor: int = 16):
        """
        Args:
            branching_factor: Number of children per internal node. Default 16.
        """
        ...
    
    @classmethod
    def from_records(cls, records: List[dict], key: str,
                     branching_factor: int = 16) -> MerkleTree:
        """
        Build a Merkle tree from a list of records.
        
        Args:
            records: List of dictionaries.
            key: The key field to use as record identifier.
            branching_factor: Children per internal node.
        Returns:
            MerkleTree built from the records.
        """
        ...
    
    @property
    def root_hash(self) -> str:
        """The root hash of the tree. If roots match, datasets are identical."""
        ...
    
    @property
    def size(self) -> int:
        """Number of records (leaf nodes) in the tree."""
        ...
    
    def insert(self, key: str, record: dict) -> None:
        """
        Insert or update a record. Incrementally rehashes affected path.
        O(log n) operation — does NOT rebuild the full tree.
        """
        ...
    
    def delete(self, key: str) -> bool:
        """
        Remove a record by key. Returns True if found and removed.
        O(log n) operation — does NOT rebuild the full tree.
        """
        ...
    
    def contains(self, key: str) -> bool:
        """Check if a key exists in the tree. O(log n)."""
        ...
    
    def get_hash(self, key: str) -> Optional[str]:
        """Get the hash for a specific key. O(log n)."""
        ...
    
    def merge(self, other: MerkleTree) -> MerkleTree:
        """
        Merge two Merkle trees. Records present in both use content hash
        to detect conflicts (higher hash wins for determinism).
        Returns NEW instance.
        """
        ...
    
    def to_dict(self) -> dict:
        """Serialize the tree structure to a dictionary."""
        ...
    
    @classmethod
    def from_dict(cls, d: dict) -> MerkleTree:
        """Deserialize from dictionary."""
        ...


@dataclass
class MerkleDiff:
    """Result of comparing two Merkle trees."""
    differing_keys: Set[str]    # keys that differ between trees
    only_in_left: Set[str]      # keys only in left tree
    only_in_right: Set[str]     # keys only in right tree
    common_different: Set[str]  # keys in both but with different content
    comparisons_made: int       # number of node comparisons (should be << total)
    
    @property
    def is_identical(self) -> bool:
        """True if trees have identical content."""
        return len(self.differing_keys) == 0


def merkle_diff(tree_a: MerkleTree, tree_b: MerkleTree) -> MerkleDiff:
    """
    Efficiently diff two Merkle trees.
    
    Compares root hashes first. If different, recursively descends only
    into subtrees with differing hashes. O(log n) when few differences.
    
    Args:
        tree_a: First Merkle tree.
        tree_b: Second Merkle tree.
    Returns:
        MerkleDiff with sets of differing keys.
    
    Example:
        diff = merkle_diff(tree1, tree2)
        if not diff.is_identical:
            for key in diff.differing_keys:
                sync_record(key)
    """
    ...
```

#### Integration Points
- **Imports from existing:** None (uses `hashlib` from stdlib)
- **Consumed by:** `wire.py` (Phase 4) for serialization, integration tests
- **Pairs with:** `delta.py` — Merkle diff finds WHICH keys differ, Delta computes WHAT changed

#### Edge Cases
- Empty tree: Valid, root_hash should be a deterministic "empty" hash
- Single record: Degenerates to a single-leaf tree
- 100K+ records: Must not exceed memory bounds; branching factor controls depth
- Identical trees: `merkle_diff` should short-circuit at root (0 comparisons)
- Hash collisions: Astronomically unlikely with SHA-256, but handle gracefully

---

### 7.4 `arrow.py` — Arrow-Native Merge Engine (~800 lines)

**Purpose:** High-performance merge engine using Apache Arrow's columnar format. Zero-copy operations where possible. 10x faster than dict-of-dicts for 1M+ rows.

#### Classes & Signatures

```python
"""Apache Arrow-native merge engine for high-performance CRDT merges."""

from __future__ import annotations
from typing import Any, Dict, Optional, Iterator, List, Union


def _import_pyarrow():
    """Lazy import of pyarrow with helpful error message."""
    try:
        import pyarrow as pa
        return pa
    except ImportError:
        raise ImportError(
            "pyarrow is required for Arrow merge operations. "
            "Install with: pip install pyarrow"
        )


class ArrowMerge:
    """
    Arrow-native merge engine with zero-copy operations.
    
    Uses columnar strategy application (vectorized, no row iteration)
    for massive performance gains on large datasets.
    
    Example:
        import pyarrow as pa
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, LWW, MaxWins
        
        schema = MergeSchema(default=LWW(), score=MaxWins())
        engine = ArrowMerge(schema)
        
        left = pa.table({"id": [1, 2], "score": [10, 20]})
        right = pa.table({"id": [2, 3], "score": [25, 30]})
        result = engine.merge(left, right, key="id")
        # result is a pa.Table — no pandas conversion overhead
    """
    
    def __init__(self, schema: Optional[Any] = None,
                 timestamp_col: Optional[str] = None):
        """
        Args:
            schema: MergeSchema for per-field strategies. If None, uses LWW default.
            timestamp_col: Column to use for LWW timestamps.
        """
        ...
    
    def merge(
        self,
        left: Any,    # pa.Table or pa.RecordBatch
        right: Any,   # pa.Table or pa.RecordBatch
        key: Optional[str] = None
    ) -> Any:  # pa.Table
        """
        Merge two Arrow tables using CRDT strategies.
        
        Args:
            left: Left Arrow table.
            right: Right Arrow table.
            key: Join key column.
        Returns:
            Merged pa.Table.
        """
        ...
    
    def merge_batches(
        self,
        batches: Iterator[Any],  # Iterator[pa.RecordBatch]
        key: Optional[str] = None,
        batch_size: int = 10000
    ) -> Iterator[Any]:  # Iterator[pa.RecordBatch]
        """
        Streaming merge for Arrow IPC record batches.
        
        Processes batches incrementally, yielding merged output batches.
        Constant memory usage regardless of total dataset size.
        """
        ...
    
    def merge_ipc(
        self,
        left_path: str,   # path to Arrow IPC file
        right_path: str,  # path to Arrow IPC file
        output_path: str, # output Arrow IPC file
        key: Optional[str] = None
    ) -> Dict[str, Any]:  # merge statistics
        """
        Merge two Arrow IPC files, writing result to a new file.
        
        Uses memory-mapped I/O for datasets larger than RAM.
        """
        ...
    
    def merge_memory_mapped(
        self,
        left_path: str,
        right_path: str,
        key: Optional[str] = None
    ) -> Any:  # pa.Table (memory-mapped)
        """
        Merge using memory-mapped files. Handles datasets larger than RAM.
        """
        ...


def arrow_merge(
    left: Any,
    right: Any,
    key: Optional[str] = None,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None
) -> Any:
    """
    Convenience function for one-shot Arrow merge.
    
    Falls back to pure-Python merge if pyarrow is not installed.
    
    Args:
        left: pa.Table, pa.RecordBatch, or list[dict] (auto-converts)
        right: pa.Table, pa.RecordBatch, or list[dict] (auto-converts)
        key: Join key column.
        schema: MergeSchema for strategies.
        timestamp_col: LWW timestamp column.
    Returns:
        pa.Table if pyarrow available, else list[dict].
    """
    ...
```

#### Integration Points
- **Imports from existing:** `strategies.MergeSchema`, `strategies.LWW`, `core.LWWRegister`
- **Imports from new:** `schema_evolution.evolve_schema` (for schema drift during merge)
- **External dependency:** `pyarrow` (LAZY IMPORT — never at module level)
- **Consumed by:** `parallel.py` (optional Arrow backend), integration tests

#### Performance Targets
- **1M rows**: 10x faster than `dataframe.merge()` with dict-of-dicts
- **Zero-copy**: Merge two Arrow tables without copying data where possible
- **Memory-mapped**: Merge datasets larger than available RAM
- **Streaming**: Constant-memory merge for Arrow IPC file streams

#### Edge Cases
- PyArrow not installed: `arrow_merge()` falls back to pure-Python; `ArrowMerge()` raises `ImportError`
- Schema mismatch: Use `schema_evolution.evolve_schema()` to reconcile before merge
- Null values: Arrow nulls must be handled (not the same as Python `None` in dicts)
- Empty tables: Valid — return empty table with correct schema
- Mixed types in column: Arrow is strictly typed — raise clear error

---

### 7.5 `gossip.py` — Gossip State Management (~400 lines)

**Purpose:** Gossip protocol state machine for distributed CRDT sync. Manages state, generates digests, computes anti-entropy diffs. Does NOT do networking — that's the user's responsibility.

#### Classes & Signatures

```python
"""Gossip protocol state management for distributed CRDT synchronization.

This module provides the STATE MACHINE for gossip-based sync.
You provide the transport (HTTP, TCP, UDP, message queue, etc.).
crdt-merge provides the merge logic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from crdt_merge.clocks import VectorClock


@dataclass
class GossipEntry:
    """A single entry in the gossip state."""
    key: str
    value: Any
    clock: VectorClock
    tombstone: bool = False  # True if this entry has been deleted
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, d: dict) -> GossipEntry: ...


class GossipState:
    """
    CRDT-aware gossip state manager.
    
    Tracks key-value pairs with vector clocks for causality.
    Supports push, pull, and push-pull anti-entropy.
    
    Example:
        state = GossipState(node_id="node-1")
        state.update("user:42", {"name": "Alice", "score": 100})
        
        # Generate digest for sync
        digest = state.digest()
        
        # Receive remote digest, compute what they're missing
        missing_keys = state.anti_entropy_push(remote_digest)
        
        # Send missing entries
        entries = state.get_entries(missing_keys)
    """
    
    def __init__(self, node_id: str, fanout: int = 3):
        """
        Args:
            node_id: Unique identifier for this node.
            fanout: Number of peers to sync with per round (state only, scheduling is yours).
        """
        ...
    
    @property
    def node_id(self) -> str: ...
    
    @property
    def size(self) -> int:
        """Number of entries (excluding tombstones)."""
        ...
    
    @property
    def clock(self) -> VectorClock:
        """This node's current vector clock."""
        ...
    
    def update(self, key: str, value: Any,
               clock: Optional[VectorClock] = None) -> VectorClock:
        """
        Update a key-value pair. Increments this node's clock.
        
        Args:
            key: The key to update.
            value: The new value.
            clock: Optional explicit clock (for replaying remote updates).
        Returns:
            The new VectorClock after this update.
        """
        ...
    
    def delete(self, key: str) -> VectorClock:
        """
        Delete a key (sets tombstone). Increments clock.
        Returns the new VectorClock.
        """
        ...
    
    def get(self, key: str) -> Optional[Any]:
        """Get the current value for a key (None if not present or tombstoned)."""
        ...
    
    def get_entry(self, key: str) -> Optional[GossipEntry]:
        """Get the full GossipEntry for a key."""
        ...
    
    def get_entries(self, keys: Set[str]) -> List[GossipEntry]:
        """Get entries for a set of keys."""
        ...
    
    def digest(self) -> Dict[str, str]:
        """
        Generate a compact digest of current state.
        Maps key → hash(value + clock). Used for efficient sync.
        """
        ...
    
    def anti_entropy_push(self, remote_digest: Dict[str, str]) -> Set[str]:
        """
        Compute keys that the remote is missing or has stale.
        Returns set of keys to push to remote.
        """
        ...
    
    def anti_entropy_pull(self, remote_digest: Dict[str, str]) -> Set[str]:
        """
        Compute keys that we are missing or have stale.
        Returns set of keys to request from remote.
        """
        ...
    
    def anti_entropy_push_pull(self, remote_digest: Dict[str, str]) -> Tuple[Set[str], Set[str]]:
        """
        Compute bidirectional sync diff.
        Returns (keys_to_push, keys_to_pull).
        """
        ...
    
    def apply_entries(self, entries: List[GossipEntry]) -> int:
        """
        Apply received entries from a remote node.
        Uses vector clock comparison for conflict resolution.
        Returns number of entries that caused updates.
        """
        ...
    
    def merge(self, other: GossipState) -> GossipState:
        """
        Merge two gossip states. Uses vector clocks for per-key resolution.
        Returns NEW GossipState instance.
        """
        ...
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, d: dict) -> GossipState: ...


def anti_entropy(local_digest: Dict[str, str],
                 remote_digest: Dict[str, str]) -> Dict[str, str]:
    """
    Standalone anti-entropy function.
    
    Compares two digests and returns a dict indicating what differs:
    {"missing_local": [...], "missing_remote": [...], "different": [...]}
    """
    ...
```

#### Integration Points
- **Imports from new:** `clocks.VectorClock` (Phase 1a)
- **Imports from existing:** `core.py` (CRDT pattern)
- **Consumed by:** `wire.py` (Phase 4), integration tests
- **Key design:** No networking. No scheduling. Pure state machine.

#### Edge Cases
- Empty state: Valid GossipState with no entries
- Tombstone GC: Not implemented in v0.6.0 (future work), but tombstones accumulate
- Concurrent updates to same key: Resolved by vector clock comparison; concurrent → deterministic tiebreaker (higher node_id)
- Single-node usage: Degenerates to a simple key-value store with version tracking
- Large state (100K+ entries): Digest must be efficient — hash-based, not full serialization

---

### 7.6 `async_merge.py` — Async Wrappers (~150 lines)

**Purpose:** Thin async wrappers around existing synchronous merge operations. Enables use in async/await codebases without blocking the event loop.

#### Functions & Signatures

```python
"""Async wrappers for crdt-merge operations.

Enables non-blocking merge in async applications.
Uses asyncio.to_thread for CPU-bound merge operations.
"""

from __future__ import annotations
import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional


async def amerge(
    left: Any,
    right: Any,
    key: Optional[str] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = 'latest',
    schema: Optional[Any] = None,
    **kwargs
) -> Any:
    """
    Async version of crdt_merge.dataframe.merge().
    
    Runs the merge in a thread pool to avoid blocking the event loop.
    
    Args:
        Same as dataframe.merge().
    Returns:
        Merged result (same type as input).
    
    Example:
        result = await amerge(left, right, key="id", schema=my_schema)
    """
    ...


async def amerge_stream(
    source_a: Any,  # AsyncIterator or Iterable of dicts
    source_b: Any,  # AsyncIterator or Iterable of dicts
    key: str = 'id',
    batch_size: int = 5000,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None
) -> AsyncIterator[List[dict]]:
    """
    Async streaming merge.
    
    Accepts both sync iterables and async iterators as input.
    Yields merged batches asynchronously.
    
    Example:
        async for batch in amerge_stream(source_a, source_b, key="id"):
            await process_batch(batch)
    """
    ...


async def amerge_sorted_stream(
    source_a: Any,
    source_b: Any,
    key: str = 'id',
    batch_size: int = 5000,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None
) -> AsyncIterator[List[dict]]:
    """
    Async sorted streaming merge. Sources MUST be pre-sorted by key.
    """
    ...
```

#### Integration Points
- **Imports from existing:** `dataframe.merge()`, `streaming.merge_stream()`, `streaming.merge_sorted_stream()`
- **External:** `asyncio` (stdlib)
- **Key design:** Uses `asyncio.to_thread()` for CPU-bound merge; async generators for streaming

#### Edge Cases
- Cancellation: Must handle `asyncio.CancelledError` gracefully
- Empty input: Same behavior as sync counterparts
- Mixed input types: Accept both sync iterables and async iterators
- Event loop: Must not create new event loops, use the running one
- Thread safety: `to_thread` handles this, but document that inputs must not be mutated concurrently

---

### 7.7 `parallel.py` — Thread-Pool Parallel Merge (~200 lines)

**Purpose:** Parallel merge for large datasets using thread pools. Splits data into chunks, merges each chunk in parallel, then combines results.

#### Functions & Signatures

```python
"""Thread-pool parallel merge for large datasets.

Splits datasets into chunks, merges each in parallel, then combines.
Automatic fallback to sequential for small datasets.
"""

from __future__ import annotations
import concurrent.futures
from typing import Any, Dict, List, Optional


def parallel_merge(
    left: Any,
    right: Any,
    key: Optional[str] = None,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
    chunk_size: int = 50000,
    max_workers: Optional[int] = None,
    prefer: str = 'latest'
) -> Any:
    """
    Parallel merge using thread pool.
    
    Splits left and right into chunks by key range, merges each chunk
    in parallel, then concatenates results.
    
    Automatically falls back to sequential merge if total rows < 10,000.
    
    Args:
        left: Dataset (DataFrame or list[dict]).
        right: Dataset (DataFrame or list[dict]).
        key: Join key column.
        schema: MergeSchema for per-field strategies.
        timestamp_col: LWW timestamp column.
        chunk_size: Records per chunk. Default 50,000.
        max_workers: Thread pool size. Default None (cpu_count).
        prefer: Preference for non-keyed merge ('latest', 'a', 'b').
    Returns:
        Merged dataset (same type as input).
    
    Example:
        result = parallel_merge(big_left, big_right, key="id", chunk_size=100000, max_workers=4)
    """
    ...


def parallel_merge_arrow(
    left: Any,    # pa.Table
    right: Any,   # pa.Table
    key: Optional[str] = None,
    schema: Optional[Any] = None,
    chunk_size: int = 100000,
    max_workers: Optional[int] = None
) -> Any:  # pa.Table
    """
    Parallel merge using Arrow backend for maximum performance.
    
    Requires pyarrow. Falls back to parallel_merge() if unavailable.
    """
    ...


def _compute_chunks(
    left: List[dict],
    right: List[dict],
    key: str,
    chunk_size: int
) -> List[tuple]:
    """
    Split datasets into key-aligned chunks for parallel processing.
    
    Ensures records with the same key end up in the same chunk.
    """
    ...
```

#### Integration Points
- **Imports from existing:** `dataframe.merge()`
- **Imports from new (optional):** `arrow.ArrowMerge` (lazy, for `parallel_merge_arrow`)
- **External:** `concurrent.futures` (stdlib)
- **Key design:** Fallback to sequential for small datasets; key-aligned chunking prevents split-key issues

#### Edge Cases
- Small datasets (< 10,000 rows): Automatic fallback to sequential (thread overhead > benefit)
- Worker errors: If any chunk fails, propagate the exception with clear error message
- Empty input: Return empty result (same type as input)
- Single-key dataset: All records share one key → degenerates to single-chunk merge
- Thread safety: Each worker gets its own data slice — no shared mutable state

---

### 7.8 Multi-Key Merge Extension in `dataframe.py` (~120 lines)

**Purpose:** Extend the existing `merge()` and `diff()` functions to support composite keys (multiple columns) and hierarchical keys (primary + secondary).

#### Changes to Existing Signatures

```python
# BEFORE (v0.5.0):
def merge(df_a, df_b, key: Optional[str] = None, ...) -> Any

# AFTER (v0.6.0) — BACKWARD COMPATIBLE:
def merge(df_a, df_b, key: Optional[Union[str, List[str]]] = None, ...) -> Any
#                      ^^^ Now accepts str OR List[str]

# BEFORE (v0.5.0):
def diff(df_a, df_b, key: str) -> Dict[str, Any]

# AFTER (v0.6.0) — BACKWARD COMPATIBLE:
def diff(df_a, df_b, key: Union[str, List[str]]) -> Dict[str, Any]
```

**CRITICAL**: The `key` parameter type is widened from `str` to `Union[str, List[str]]`. All existing code using `key="id"` (a string) continues to work identically. This is NOT a breaking change.

#### New Internal Functions

```python
def _normalize_key(key: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """Convert key to list form. 'id' → ['id'], ['id', 'name'] → ['id', 'name']."""
    ...

def _make_composite_key(record: dict, key_cols: List[str]) -> tuple:
    """Extract composite key as tuple from a record."""
    ...

def _validate_key_columns(records: List[dict], key_cols: List[str]) -> None:
    """Validate all key columns exist in records. Raises KeyError if not."""
    ...
```

#### Edge Cases
- Single string key: `key="id"` → behaves exactly as v0.5.0 (backward compatible)
- Two-column composite: `key=["tenant_id", "user_id"]` → tuple key `(tenant_id_val, user_id_val)`
- Three-column composite: `key=["a", "b", "c"]` → tuple key `(a_val, b_val, c_val)`
- `None` in key column: Raise `ValueError` — composite keys must not contain None
- Empty key list: `key=[]` → Raise `ValueError`
- Duplicate key columns: `key=["id", "id"]` → Raise `ValueError`

---

## 8. WIRE PROTOCOL v2 EXTENSIONS

### New Wire Tags

The wire protocol header format remains unchanged: `automatic(4) | VERSION(2) | FLAGS(1) | TAG(1) | PAYLOAD_LEN(4) | PAYLOAD`

The VERSION field will be bumped to `0x0002` for v0.6.0 wire messages containing new types. The deserializer MUST handle both v1 (0x0001) and v2 (0x0002) messages.

| Tag | Hex | Type | Module | Payload Format |
|-----|-----|------|--------|---------------|
| 64 | `0x40` | `VectorClock` | `clocks.py` | JSON: `{"type": "VectorClock", "clocks": {"node_id": counter, ...}}` |
| 65 | `0x41` | `MerkleTree` | `merkle.py` | JSON: `{"type": "MerkleTree", "branching_factor": int, "nodes": [...]}` |
| 66 | `0x42` | `GossipState` | `gossip.py` | JSON: `{"type": "GossipState", "node_id": str, "entries": [...], "clock": {...}}` |
| 67 | `0x43` | `SchemaEvolutionResult` | `schema_evolution.py` | JSON: `{"type": "SchemaEvolutionResult", "resolved_schema": {...}, ...}` |

### Existing Tags (unchanged)

| Tag | Hex | Type | Module |
|-----|-----|------|--------|
| 1 | `0x01` | `GCounter` | `core.py` |
| 2 | `0x02` | `PNCounter` | `core.py` |
| 3 | `0x03` | `LWWRegister` | `core.py` |
| 4 | `0x04` | `ORSet` | `core.py` |
| 5 | `0x05` | `LWWMap` | `core.py` |
| 16 | `0x10` | `Delta` | `delta.py` |
| 32 | `0x20` | `Generic` | (any JSON-serializable) |
| 48 | `0x30` | `MergeableHLL` | `probabilistic.py` |
| 49 | `0x31` | `MergeableBloom` | `probabilistic.py` |
| 50 | `0x32` | `MergeableCMS` | `probabilistic.py` |

### Implementation Notes for Dev E

1. Add tag constants to `wire.py`:
   ```python
   TAG_VECTOR_CLOCK = 0x40
   TAG_MERKLE_TREE = 0x41
   TAG_GOSSIP_STATE = 0x42
   TAG_SCHEMA_EVOLUTION = 0x43
   ```

2. Update `_TAG_TO_TYPE` and `_TYPE_TO_TAG` mappings

3. Add serialization handlers in `_serialize_payload()` and `_deserialize_payload()`

4. Update `peek_type()` to return human-readable names for new tags

5. **Backward compatibility**: Wire data produced by v0.5.0 (wire version 0x0001) MUST still deserialize correctly. The deserializer checks wire version and handles both.

---

## 9. `__init__.py` ADDITIONS

### Current Exports (v0.5.0 — DO NOT REMOVE)

```python
# core.py
from crdt_merge.core import GCounter, PNCounter, LWWRegister, LWWMap, ORSet

# strategies.py
from crdt_merge.strategies import (
    MergeStrategy, MergeSchema, LWW, MaxWins, MinWins,
    LongestWins, Priority, Concat, UnionSet, Custom
)

# dataframe.py
from crdt_merge.dataframe import merge, diff

# dedup.py
from crdt_merge.dedup import dedup_list, dedup_records, DedupIndex, MinHashDedup

# delta.py
from crdt_merge.delta import Delta, DeltaStore, compute_delta, compose_deltas, apply_delta

# json_merge.py
from crdt_merge.json_merge import merge_dicts, merge_json_lines

# probabilistic.py
from crdt_merge.probabilistic import MergeableHLL, MergeableBloom, MergeableCMS

# provenance.py
from crdt_merge.provenance import merge_with_provenance, export_provenance, ProvenanceLog

# streaming.py
from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats, count_stream

# datasets_ext.py
from crdt_merge.datasets_ext import merge_datasets, dedup_dataset

# verify.py
from crdt_merge.verify import (
    verify_crdt, verify_commutative, verify_associative,
    verify_idempotent, verify_convergence, verified_merge,
    CRDTVerification, VerificationResult, CRDTVerificationError
)

# wire.py
from crdt_merge.wire import serialize, deserialize, peek_type, wire_size, serialize_batch, deserialize_batch, WireError
```

### New Exports to Add (v0.6.0)

```python
# clocks.py (NEW)
from crdt_merge.clocks import VectorClock, DottedVersionVector, Ordering

# schema_evolution.py (NEW)
from crdt_merge.schema_evolution import (
    evolve_schema, check_compatibility, widen_type,
    SchemaPolicy, SchemaChange, SchemaEvolutionResult
)

# merkle.py (NEW)
from crdt_merge.merkle import MerkleTree, MerkleDiff, merkle_diff

# arrow.py (NEW)
from crdt_merge.arrow import ArrowMerge, arrow_merge

# gossip.py (NEW)
from crdt_merge.gossip import GossipState, GossipEntry, anti_entropy

# async_merge.py (NEW)
from crdt_merge.async_merge import amerge, amerge_stream, amerge_sorted_stream

# parallel.py (NEW)
from crdt_merge.parallel import parallel_merge, parallel_merge_arrow
```

### Version Bump

```python
__version__ = "0.6.0"  # was "0.5.0"
```

### Import Safety

All new imports in `__init__.py` must be wrapped to handle missing optional dependencies gracefully:

```python
# Arrow imports may fail if module references pyarrow at import time
# Solution: arrow.py must NOT import pyarrow at module level
# This way, `from crdt_merge.arrow import ArrowMerge` always works,
# and pyarrow is only needed when you CALL ArrowMerge methods.
```

---

## 10. REGRESSION GATE

### Pre-Merge Checklist (EVERY PR)

Before ANY PR is merged to main, the following must pass:

| Gate | Command | Expected |
|------|---------|----------|
| 1. Existing tests | `pytest tests/test_core.py tests/test_dataframe.py tests/test_dedup.py tests/test_json_merge.py tests/test_longest_wins.py tests/test_probabilistic.py tests/test_provenance.py tests/test_strategies.py tests/test_streaming.py tests/test_stress_v030.py tests/test_v050_integration.py tests/test_verified_merge.py tests/test_wire.py tests/test_benchmark.py tests/test_architect_360_validation.py` | **425 passed, 0 failed** |
| 2. New module tests | `pytest tests/test_clocks.py tests/test_schema_evolution.py tests/test_merkle.py tests/test_arrow.py tests/test_gossip.py tests/test_async_merge.py tests/test_parallel.py tests/test_multi_key.py` | **~225 passed** |
| 3. Integration tests | `pytest tests/test_v060_integration.py` | **~70 passed** |
| 4. CRDT law verification | Included in test files above | **All 4 laws × all new types = PASS** |
| 5. Version check | `python -c "import crdt_merge; print(crdt_merge.__version__)"` | `0.6.0` |
| 6. Import check | `python -c "from crdt_merge import VectorClock, MerkleTree, GossipState, ArrowMerge, amerge, parallel_merge, evolve_schema"` | No errors |
| 7. Zero-dep check | `python -c "import crdt_merge"` (on clean Python with NO optional deps installed) | No errors |

### CI Pipeline

```yaml
# Suggested GitHub Actions workflow
name: v0.6.0 Regression Gate
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e .
      - run: pytest tests/ -v --tb=short
      # Arrow tests only on 3.10+
      - run: pip install pyarrow
        if: matrix.python-version >= '3.10'
      - run: pytest tests/test_arrow.py -v --tb=short
        if: matrix.python-version >= '3.10'
```

---

## 11. RELEASE CHECKLIST

### Pre-Release

- [ ] All 7 new modules implemented (`clocks.py`, `schema_evolution.py`, `merkle.py`, `arrow.py`, `gossip.py`, `async_merge.py`, `parallel.py`)
- [ ] Multi-key merge added to `dataframe.py`
- [ ] Wire protocol updated with tags 0x40-0x43
- [ ] `__init__.py` exports updated with all new public API
- [ ] All 425 existing tests pass UNCHANGED (zero regressions)
- [ ] All ~295 new tests pass
- [ ] Total test count: ~720
- [ ] CRDT law verification passes for VectorClock, DottedVersionVector, MerkleTree, GossipState
- [ ] Arrow benchmark: 10x faster than dict-of-dicts for 1M rows
- [ ] `python -c "import crdt_merge; print(crdt_merge.__version__)"` → `0.6.0`
- [ ] Import works without optional deps: `python -c "import crdt_merge"` on clean env

### Documentation

- [ ] `CHANGELOG.md` updated with all v0.6.0 changes
- [ ] `README.md` updated with new features, examples, and installation extras
- [ ] Docstrings on all new public APIs
- [ ] Type hints on all new public APIs
- [ ] MASTER KEY file updated to v0.6.0 (post-release)

### Release

- [ ] Version bumped to `0.6.0` in `__init__.py` and `setup.py`/`pyproject.toml`
- [ ] Git tag: `v0.6.0`
- [ ] PyPI publish: `pip install crdt-merge==0.6.0`
- [ ] GitHub release with changelog
- [ ] Announce new features

### Post-Release

- [ ] Verify `pip install crdt-merge==0.6.0` works on clean environment
- [ ] Verify `pip install crdt-merge[arrow]==0.6.0` installs pyarrow
- [ ] Update MASTER KEY file to v0.6.0
- [ ] Update roadmap: mark v0.6.0 as complete
- [ ] Begin v0.7.0 planning

---

## 12. TIMELINE

### Phase Schedule

| Phase | Contents | Duration | Dependencies | Devs Active |
|-------|----------|----------|-------------|-------------|
| **Phase 1 — Foundation** | `clocks.py`, `schema_evolution.py`, `merkle.py` | Weeks 1-3 | None (parallel start) | Dev A, Dev B, Dev C |
| **Phase 2 — Engine** | `arrow.py`, `gossip.py`, multi-key in `dataframe.py` | Weeks 3-7 | Phase 1 complete | Dev A, Dev B, Dev C |
| **Phase 3 — Wrappers** | `async_merge.py`, `parallel.py` | Weeks 7-9 | Phase 2 stable | Dev D |
| **Phase 4 — Integration** | `wire.py` updates, `__init__.py`, integration tests | Weeks 8-10 | Phase 2+3 | Dev E |
| **Buffer** | Bug fixes, performance tuning, documentation | Week 11 | All phases | All devs |
| **Release** | Final testing, PyPI publish, GitHub release | Week 12 | Buffer complete | Dev E (lead) |

### Gantt View

```
Week:  1    2    3    4    5    6    7    8    9   10   11   12
       ├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Dev A: [==clocks===][=======gossip=======]                [buf]
Dev B: [=schema_ev=][===========arrow===============]     [buf]
Dev C: [==merkle===][=multi-key=]                         [buf]
Dev D:                                   [async][parallel][buf]
Dev E:                                        [wire][init][integ][REL]
```

**Total estimated duration: 10-12 weeks**

### Milestones

| Milestone | Target Date | Gate |
|-----------|------------|------|
| **M1: Phase 1 Complete** | End of Week 3 | `clocks.py`, `schema_evolution.py`, `merkle.py` — all unit tests pass, CRDT laws verified |
| **M2: Phase 2 Complete** | End of Week 7 | `arrow.py`, `gossip.py`, multi-key — all unit tests pass, benchmark targets met |
| **M3: Phase 3 Complete** | End of Week 9 | `async_merge.py`, `parallel.py` — all tests pass |
| **M4: Integration Complete** | End of Week 10 | Wire protocol updated, all 720 tests pass, zero regressions |
| **M5: Release** | End of Week 12 | PyPI publish, GitHub release tag |

### Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Arrow performance target (10x) not met | Medium | High | Start benchmarking in Week 4; pivot to columnar-numpy fallback if needed |
| Schema evolution edge cases | Low | Medium | Extensive property-based testing; start with strict policies |
| Multi-key backward compatibility break | Low | Critical | Dev C writes compatibility tests FIRST, before implementation |
| Async/parallel deadlocks | Medium | Medium | Dev D writes stress tests with 100 concurrent operations |
| Wire protocol v2 backward compat | Low | High | Dev E writes v1→v2 roundtrip tests before any code changes |

---

## Appendix A: File Inventory Summary

### v0.5.0 Baseline (13 source + 15 test = 28 files)

```
crdt_merge/
├── __init__.py          (88 LOC)    ← Dev E modifies (Phase 4)
├── core.py              (308 LOC)   ← READ-ONLY
├── strategies.py        (334 LOC)   ← READ-ONLY
├── dataframe.py         (302 LOC)   ← Dev C modifies (Phase 2, multi-key only)
├── datasets_ext.py      (94 LOC)    ← READ-ONLY
├── dedup.py             (235 LOC)   ← READ-ONLY
├── delta.py             (353 LOC)   ← READ-ONLY
├── json_merge.py        (126 LOC)   ← READ-ONLY
├── probabilistic.py     (505 LOC)   ← READ-ONLY
├── provenance.py        (363 LOC)   ← READ-ONLY
├── streaming.py         (353 LOC)   ← READ-ONLY
├── verify.py            (408 LOC)   ← READ-ONLY
└── wire.py              (488 LOC)   ← Dev E modifies (Phase 4, new tags only)

tests/
├── test_architect_360_validation.py  ← READ-ONLY (39,590 bytes)
├── test_benchmark.py                 ← READ-ONLY
├── test_core.py                      ← READ-ONLY
├── test_dataframe.py                 ← READ-ONLY
├── test_dedup.py                     ← READ-ONLY
├── test_json_merge.py                ← READ-ONLY
├── test_longest_wins.py              ← READ-ONLY
├── test_probabilistic.py             ← READ-ONLY
├── test_provenance.py                ← READ-ONLY
├── test_strategies.py                ← READ-ONLY
├── test_streaming.py                 ← READ-ONLY
├── test_stress_v030.py               ← READ-ONLY
├── test_v050_integration.py          ← READ-ONLY
├── test_verified_merge.py            ← READ-ONLY
└── test_wire.py                      ← READ-ONLY
```

### v0.6.0 Additions (7 source + 9 test = 16 new files)

```
crdt_merge/
├── clocks.py            (~200 LOC)  ← NEW (Dev A)
├── schema_evolution.py  (~300 LOC)  ← NEW (Dev B)
├── merkle.py            (~400 LOC)  ← NEW (Dev C)
├── arrow.py             (~800 LOC)  ← NEW (Dev B)
├── gossip.py            (~400 LOC)  ← NEW (Dev A)
├── async_merge.py       (~150 LOC)  ← NEW (Dev D)
└── parallel.py          (~200 LOC)  ← NEW (Dev D)

tests/
├── test_clocks.py               (~30 tests)  ← NEW (Dev A)
├── test_schema_evolution.py     (~25 tests)  ← NEW (Dev B)
├── test_merkle.py               (~35 tests)  ← NEW (Dev C)
├── test_arrow.py                (~50 tests)  ← NEW (Dev B)
├── test_gossip.py               (~30 tests)  ← NEW (Dev A)
├── test_async_merge.py          (~20 tests)  ← NEW (Dev D)
├── test_parallel.py             (~20 tests)  ← NEW (Dev D)
├── test_multi_key.py            (~15 tests)  ← NEW (Dev C)
└── test_v060_integration.py     (~70 tests)  ← NEW (Dev E)
```

### v0.6.0 Totals

- **20 source modules** (~6,200 LOC)
- **24 test files** (~720 tests)
- **0 breaking changes**

---

## Appendix B: Quick Reference — CRDT Laws

Every type with `.merge()` MUST satisfy:

| Law | Definition | Test |
|-----|-----------|------|
| **Commutativity** | `a.merge(b) == b.merge(a)` | `verify_commutative(merge_fn, gen_fn, trials=1000)` |
| **Associativity** | `a.merge(b).merge(c) == a.merge(b.merge(c))` | `verify_associative(merge_fn, gen_fn, trials=1000)` |
| **Idempotency** | `a.merge(a) == a` | `verify_idempotent(merge_fn, gen_fn, trials=1000)` |
| **Convergence** | All replicas converge to same state regardless of merge order | `verify_convergence(merge_fn, gen_fn, trials=500, num_replicas=5)` |

---

## Appendix C: Codebase Patterns (from MASTER KEY)

New modules MUST follow these established patterns:

1. **Merge returns NEW instance**: `merged = a.merge(b)` — `a` and `b` are unchanged
2. **to_dict / from_dict roundtrip**: `Type.from_dict(obj.to_dict()) == obj`
3. **Wire serialize/deserialize roundtrip**: `deserialize(serialize(obj)) == obj`
4. **Strategy resolution signature**: `strategy.resolve(val_a, val_b, ts_a, ts_b, node_a, node_b)`
5. **Generator-based streaming**: yield `List[dict]` batches
6. **Optional schema threading**: `schema=None` → use `LWW()` as default
7. **Zero deps**: No top-level imports of optional packages

---

*This development plan was generated from the crdt-merge v0.5.0 MASTER KEY and roadmap v2.0.*
*425 existing tests are the regression baseline. Zero tolerance for regressions.*
*Last updated: March 28, 2026*
