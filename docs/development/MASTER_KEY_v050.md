# crdt-merge v0.5.0 — MASTER KEY FILE

> **Purpose**: This file contains EVERYTHING a new agent or dev team needs to understand, work on, upgrade, debug, or extend the `crdt-merge` codebase. Pass this file to any agent to bootstrap a fully operational team.

> **Golden Rule**: ALWAYS use the REAL API from the installed package. NEVER assume function signatures. Run `inspect.signature()` or check this document first.

---

## 1. IDENTITY & INSTALLATION

```
Package:      crdt-merge
Version:      0.5.0
PyPI:         pip install crdt-merge==0.5.0
GitHub:       https://github.com/mgillr/crdt-merge
License:      (check repo)
Dependencies: ZERO (pure Python, stdlib only)
Python:       3.8+ (uses dataclasses, typing, struct, hashlib, zlib)
Total LOC:    ~3,957 lines across 13 modules
```

---

## 2. ARCHITECTURE OVERVIEW

```
crdt_merge/
├── __init__.py          (88 LOC)   — Public API surface, re-exports
├── core.py              (308 LOC)  — 5 CRDT primitives (the mathematical foundation)
├── strategies.py        (334 LOC)  — 8 merge strategies + MergeSchema
├── dataframe.py         (302 LOC)  — DataFrame merge/diff engine
├── datasets_ext.py      (94 LOC)   — HuggingFace datasets adapter
├── dedup.py             (235 LOC)  — Deduplication (exact, fuzzy, MinHash)
├── delta.py             (353 LOC)  — Delta computation, composition, application
├── json_merge.py        (126 LOC)  — Dict & JSON-lines merge
├── probabilistic.py     (505 LOC)  — HyperLogLog, Bloom filter, Count-Min Sketch
├── provenance.py        (363 LOC)  — Merge audit trail & conflict tracking
├── streaming.py         (353 LOC)  — Memory-efficient streaming merge (sorted/unsorted)
├── verify.py            (408 LOC)  — CRDT law verification (property-based testing)
└── wire.py              (488 LOC)  — Binary serialization protocol
```

### Layer Diagram
```
┌─────────────────────────────────────────────────┐
│                   USER LAYER                     │
│  __init__.py  ·  datasets_ext.py                │
├─────────────────────────────────────────────────┤
│               ORCHESTRATION LAYER                │
│  dataframe.py · streaming.py · provenance.py     │
├─────────────────────────────────────────────────┤
│                ENGINE LAYER                      │
│  strategies.py · delta.py · json_merge.py        │
│  dedup.py · verify.py                            │
├─────────────────────────────────────────────────┤
│              FOUNDATION LAYER                    │
│  core.py · probabilistic.py · wire.py            │
└─────────────────────────────────────────────────┘
```

---

## 3. INTERNAL DEPENDENCY GRAPH

```
__init__.py ──────► core, dataframe, dedup, json_merge, strategies,
                    streaming, datasets_ext, provenance, verify,
                    wire, probabilistic

dataframe.py ─────► core.LWWRegister
datasets_ext.py ──► dataframe.merge, dedup.dedup_records
dedup.py ─────────► core.ORSet
delta.py ─────────► strategies.MergeSchema, strategies.LWW
provenance.py ────► strategies.MergeSchema, strategies.MergeStrategy, strategies.LWW
streaming.py ─────► strategies.MergeSchema, strategies.MergeStrategy, strategies.LWW
wire.py ──────────► core.*, probabilistic.*
```

**Key Principle**: `core.py` and `probabilistic.py` have ZERO internal imports — they are pure foundations. Everything else builds upward.

---

## 4. COMPLETE REAL API REFERENCE

### 4.1 core.py — CRDT Primitives

#### GCounter (Grow-only Counter)
```python
from crdt_merge.core import GCounter

gc = GCounter(node_id: Optional[str] = None, initial: int = 0)
gc.increment(node_id: str, amount: int = 1) -> None
gc.value  # @property -> int (sum of all nodes)
gc.merge(other: GCounter) -> GCounter  # returns NEW instance
gc.to_dict() -> dict
GCounter.from_dict(d: dict) -> GCounter  # classmethod
```

#### PNCounter (Positive-Negative Counter)
```python
from crdt_merge.core import PNCounter

pn = PNCounter()
pn.increment(node_id: str, amount: int = 1) -> None
pn.decrement(node_id: str, amount: int = 1) -> None
pn.value  # @property -> int (P - N)
pn.merge(other: PNCounter) -> PNCounter
pn.to_dict() -> dict
PNCounter.from_dict(d: dict) -> PNCounter
```

#### LWWRegister (Last-Writer-Wins Register)
```python
from crdt_merge.core import LWWRegister

reg = LWWRegister(value: Any = None, timestamp: Optional[float] = None, node_id: str = '')
reg.set(value: Any, timestamp: Optional[float] = None, node_id: str = '') -> None
reg.value      # @property
reg.timestamp  # @property
reg.merge(other: LWWRegister) -> LWWRegister
reg.to_dict() -> dict
LWWRegister.from_dict(d: dict) -> LWWRegister
```

**IMPORTANT**: When timestamps are equal, merge uses `node_id` as tiebreaker (lexicographic, higher wins). This was a CRITICAL fix — the original code was non-deterministic on ties.

#### LWWMap (Last-Writer-Wins Map)
```python
from crdt_merge.core import LWWMap

m = LWWMap()
m.set(key: str, value: Any, timestamp: Optional[float] = None, node_id: str = '') -> None
m.delete(key: str, timestamp: Optional[float] = None) -> None
m.get(key: str, default: Any = None) -> Any
m.value  # @property -> dict
m.merge(other: LWWMap) -> LWWMap
m.to_dict() -> dict
LWWMap.from_dict(d: dict) -> LWWMap
```

#### ORSet (Observed-Remove Set)
```python
from crdt_merge.core import ORSet

s = ORSet()
s.add(element: Hashable) -> str       # returns unique tag
s.remove(element: Hashable) -> None
s.contains(element: Hashable) -> bool
s.value  # @property -> set
s.merge(other: ORSet) -> ORSet
s.to_dict() -> dict
ORSet.from_dict(d: dict) -> ORSet
```

### 4.2 strategies.py — Merge Strategies

All strategies implement the `MergeStrategy` base class:

```python
class MergeStrategy:
    def name(self) -> str
    def resolve(self, val_a, val_b, ts_a=0.0, ts_b=0.0, node_a='a', node_b='b') -> Any
```

#### Available Strategies

| Strategy | Constructor | Behavior |
|----------|-------------|----------|
| `LWW()` | no args | Last-Writer-Wins by timestamp; node_id tiebreaker |
| `MaxWins()` | no args | Picks the greater value |
| `MinWins()` | no args | Picks the lesser value |
| `LongestWins()` | no args | Picks the longer string/sequence |
| `Priority(levels: List[str])` | ordered priority list | Picks value matching highest priority level |
| `Concat(separator=' \| ', dedup=True)` | sep + dedup flag | Concatenates both values |
| `UnionSet(separator=',')` | separator | Splits strings into sets and unions them |
| `Custom(fn: Callable)` | function | Custom resolution: `fn(val_a, val_b, ts_a, ts_b, node_a, node_b)` |

#### MergeSchema
```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(
    default: Optional[MergeStrategy] = None,     # fallback strategy
    field_strategies: Dict[str, MergeStrategy]    # NOTE: this is **kwargs
)
# Example:
schema = MergeSchema(default=LWW(), score=MaxWins(), name=LongestWins())

schema.strategy_for(field: str) -> MergeStrategy
schema.set_strategy(field: str, strategy: MergeStrategy) -> None
schema.resolve_row(row_a: dict, row_b: dict, timestamp_col: Optional[str] = None,
                   node_a: str = 'a', node_b: str = 'b') -> dict
schema.default  # @property
schema.fields   # @property -> dict of field->strategy
schema.to_dict() -> dict
MergeSchema.from_dict(d: dict) -> MergeSchema
```

**CRITICAL NOTE**: `MergeSchema.__init__` uses `**kwargs` for field strategies. Usage:
```python
# CORRECT:
schema = MergeSchema(default=LWW(), score=MaxWins())
# WRONG:
schema = MergeSchema(default=LWW(), field_strategies={"score": MaxWins()})
```

### 4.3 dataframe.py — DataFrame Merge Engine

```python
from crdt_merge.dataframe import merge, diff

result_df = merge(
    df_a: Any,                              # pandas DataFrame or list of dicts
    df_b: Any,                              # pandas DataFrame or list of dicts
    key: Optional[str] = None,              # join key column
    timestamp_col: Optional[str] = None,    # LWW timestamp column
    prefer: str = 'latest',                 # 'latest', 'a', 'b'
    dedup: bool = True,                     # exact dedup
    fuzzy_dedup: bool = False,              # fuzzy dedup
    fuzzy_threshold: float = 0.85,          # fuzzy similarity threshold
    schema: Optional[MergeSchema] = None    # per-field strategies
) -> Any  # returns same type as input (DataFrame or list)

diff_result = diff(
    df_a: Any,
    df_b: Any,
    key: str
) -> Dict[str, Any]
# Returns: {"added": [...], "removed": [...], "modified": [...], "unchanged_count": int}
```

**Works with BOTH pandas DataFrames and plain `list[dict]`**. Auto-detects type and returns same type.

### 4.4 datasets_ext.py — HuggingFace Adapter

```python
from crdt_merge.datasets_ext import merge_datasets, dedup_dataset

result = merge_datasets(
    dataset_a: Any,                         # HuggingFace Dataset
    dataset_b: Any,
    key: Optional[str] = None,
    timestamp_col: Optional[str] = None,
    prefer: str = 'latest',
    dedup: bool = True
) -> Any  # HuggingFace Dataset

result = dedup_dataset(
    dataset: Any,
    columns: Optional[List[str]] = None,
    method: str = 'exact',                  # 'exact' or 'fuzzy'
    threshold: float = 0.85
) -> Any
```

### 4.5 dedup.py — Deduplication

```python
from crdt_merge.dedup import dedup_list, dedup_records, DedupIndex, MinHashDedup

# Simple list dedup
unique, removed_indices = dedup_list(
    items: List[str],
    method: str = 'exact',            # 'exact' or 'fuzzy'
    threshold: float = 0.85,
    key: Optional[Callable[[str], str]] = None
) -> Tuple[List[str], List[int]]

# Record dedup
unique_records, removed_count = dedup_records(
    records: List[dict],
    columns: Optional[List[str]] = None,  # columns to consider
    method: str = 'exact',
    threshold: float = 0.85
) -> Tuple[List[dict], int]

# CRDT-aware dedup index
idx = DedupIndex(node_id: str = 'default')
is_new = idx.add_exact(text: str) -> bool
is_new, match = idx.add_fuzzy(text: str, threshold: float = 0.85) -> Tuple[bool, Optional[str]]
idx.size  # @property -> int
idx.merge(other: DedupIndex) -> DedupIndex

# MinHash-based dedup
mh = MinHashDedup(num_hashes: int = 128, threshold: float = 0.5)
is_new = mh.add(item: Any, text: str) -> bool
unique = mh.dedup(items: List[Any], text_fn: Callable[[Any], str]) -> List[Any]
```

### 4.6 delta.py — Delta Engine

```python
from crdt_merge.delta import Delta, DeltaStore, compute_delta, compose_deltas, apply_delta

# Compute what changed
delta = compute_delta(
    old_records: List[dict],
    new_records: List[dict],
    key: str,
    version: int = 0,
    source_node: str = ''
) -> Delta

# Compose multiple deltas into one (KEY-AWARE dedup)
combined = compose_deltas(*deltas: Delta, key: Optional[str] = None) -> Delta

# Apply delta to records
updated = apply_delta(
    records: List[dict],
    delta: Delta,
    key: str,
    schema: Optional[MergeSchema] = None
) -> List[dict]

# Delta object
class Delta:
    added: List[dict]
    modified: List[dict]
    removed: List[str]       # list of key values
    version: int
    timestamp: float
    source_node: str
    is_empty  # @property -> bool
    size      # @property -> int
    to_dict() -> dict
    from_dict(d: dict) -> Delta  # classmethod

# Stateful delta tracking
store = DeltaStore(key: str, node_id: str = 'default')
delta = store.ingest(records: List[dict]) -> Optional[Delta]  # None if no changes
store.version   # @property
store.size      # @property
store.records   # @property -> current records
```

### 4.7 json_merge.py — Dict & JSON-Lines Merge

```python
from crdt_merge.json_merge import merge_dicts, merge_json_lines

# Deep dict merge with LWW timestamps
merged = merge_dicts(
    a: dict,
    b: dict,
    timestamps_a: Optional[Dict[str, float]] = None,
    timestamps_b: Optional[Dict[str, float]] = None,
    path: str = ''  # internal recursion path
) -> dict

# Merge two lists of JSON records
merged = merge_json_lines(
    lines_a: List[dict],
    lines_b: List[dict],
    key: Optional[str] = None  # if None, concatenates; if set, merges by key
) -> List[dict]
```

**IMPORTANT**: `merge_dicts` without timestamps uses deterministic tiebreaker (picks `a` on equal). With timestamps, per-key LWW applies.

### 4.8 probabilistic.py — Probabilistic Data Structures

All three implement `.merge()`, `.to_dict()`, `.from_dict()` — fully CRDT-compliant.

#### MergeableHLL (HyperLogLog — cardinality estimation)
```python
from crdt_merge.probabilistic import MergeableHLL

hll = MergeableHLL(precision: int = 14)  # precision 4-18
hll.add(item: Any) -> None
hll.add_all(items: Iterable) -> None
hll.cardinality() -> float         # estimated unique count
hll.standard_error() -> float      # 1.04 / sqrt(2^precision)
hll.merge(other: MergeableHLL) -> MergeableHLL
hll.size_bytes() -> int
hll.to_dict() -> dict
MergeableHLL.from_dict(d: dict) -> MergeableHLL
```

#### MergeableBloom (Bloom Filter — membership testing)
```python
from crdt_merge.probabilistic import MergeableBloom

bf = MergeableBloom(capacity: int = 10000, fp_rate: float = 0.01)
bf.add(item: Any) -> None
bf.add_all(items: Iterable) -> None
bf.contains(item: Any) -> bool
bf.estimated_fp_rate() -> float
bf.merge(other: MergeableBloom) -> MergeableBloom
bf.size_bytes() -> int
bf.to_dict() -> dict
MergeableBloom.from_dict(d: dict) -> MergeableBloom
```

#### MergeableCMS (Count-Min Sketch — frequency estimation)
```python
from crdt_merge.probabilistic import MergeableCMS

cms = MergeableCMS(width: int = 2000, depth: int = 7)
cms.add(item: Any, count: int = 1) -> None
cms.add_all(items: Iterable) -> None
cms.estimate(item: Any) -> int       # estimated frequency
cms.total  # @property -> int
cms.merge(other: MergeableCMS) -> MergeableCMS
cms.size_bytes() -> int
cms.to_dict() -> dict
MergeableCMS.from_dict(d: dict) -> MergeableCMS
```

### 4.9 provenance.py — Merge Audit Trail

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance
from crdt_merge.provenance import ProvenanceLog, MergeRecord, MergeDecision

# Merge with full audit trail
result_records, log = merge_with_provenance(
    df_a,                                       # DataFrame or list[dict]
    df_b,
    key: str = 'id',
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None
) -> Tuple[list, ProvenanceLog]

# Export log
json_str = export_provenance(log: ProvenanceLog, format: str = 'json') -> str
# format: 'json' or 'csv'

# ProvenanceLog
@dataclass
class ProvenanceLog:
    records: List[MergeRecord]
    total_rows: int = 0
    merged_rows: int = 0
    unique_a_rows: int = 0
    unique_b_rows: int = 0
    total_conflicts: int = 0
    duration_ms: float = 0.0
    def summary() -> str
    def to_dict() -> dict

# MergeRecord
@dataclass
class MergeRecord:
    key: Any
    origin: str                    # 'a', 'b', or 'merged'
    decisions: List[MergeDecision]
    conflict_count  # @property
    conflicts       # @property -> list of conflict decisions
    fields_from_a   # @property -> list
    fields_from_b   # @property -> list

# MergeDecision
@dataclass
class MergeDecision:
    field: str
    source: str         # 'a' or 'b'
    strategy: str       # strategy name
    value: Any
    alternative: Any = None
    def was_conflict() -> bool
    def to_dict() -> dict
```

### 4.10 streaming.py — Memory-Efficient Streaming Merge

```python
from crdt_merge.streaming import merge_stream, merge_sorted_stream, StreamStats, count_stream

# Unsorted streaming merge (uses batching)
for batch in merge_stream(
    source_a: Iterable[dict],
    source_b: Iterable[dict],
    key: str = 'id',
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None
) -> Generator[List[dict], None, None]:
    process(batch)

# Pre-sorted streaming merge (O(1) memory)
for batch in merge_sorted_stream(
    source_a: Iterable[dict],    # MUST be sorted by key
    source_b: Iterable[dict],    # MUST be sorted by key
    key: str = 'id',
    batch_size: int = 5000,
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
    stats: Optional[StreamStats] = None
) -> Generator[List[dict], None, None]:
    process(batch)

# Count records in a stream
n = count_stream(source: Iterable[dict]) -> int

# Stats tracker
@dataclass
class StreamStats:
    rows_processed: int = 0
    rows_merged: int = 0
    rows_unique_a: int = 0
    rows_unique_b: int = 0
    batches_processed: int = 0
    duration_ms: float = 0.0
    peak_batch_size: int = 0
    rows_per_sec  # @property -> float
```

### 4.11 verify.py — CRDT Law Verification

```python
from crdt_merge.verify import (
    verify_crdt, verify_commutative, verify_associative,
    verify_idempotent, verify_convergence,
    verified_merge, CRDTVerification, VerificationResult,
    CRDTVerificationError
)

# Full verification suite
result = verify_crdt(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],          # generates random instances
    trials: int = 1000,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
    include_convergence: bool = True
) -> CRDTVerification

# Individual property checks
result = verify_commutative(merge_fn, gen_fn, trials=1000, eq_fn=None) -> VerificationResult
result = verify_associative(merge_fn, gen_fn, trials=1000, eq_fn=None) -> VerificationResult
result = verify_idempotent(merge_fn, gen_fn, trials=1000, eq_fn=None) -> VerificationResult
result = verify_convergence(merge_fn, gen_fn, trials=500, num_replicas=5, eq_fn=None) -> VerificationResult

# Decorator — wraps a merge function with runtime verification
@verified_merge(gen_fn=my_gen, trials=100, on_fail='raise')
def my_merge(a, b):
    ...

# CRDTVerification
@dataclass
class CRDTVerification:
    commutativity: VerificationResult
    associativity: VerificationResult
    idempotency: VerificationResult
    convergence: Optional[VerificationResult] = None
    total_trials: int = 0
    total_duration_ms: float = 0.0
    passed  # @property -> bool (all passed)
    def summary() -> str

# VerificationResult
@dataclass
class VerificationResult:
    property_name: str
    passed: bool
    trials: int
    failures: int
    first_failure: Optional[dict] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
```

### 4.12 wire.py — Binary Serialization Protocol

```python
from crdt_merge.wire import (
    serialize, deserialize, peek_type, wire_size,
    serialize_batch, deserialize_batch, WireError
)

# Single object
data = serialize(obj: Any, compress: bool = False) -> bytes
obj = deserialize(data: bytes) -> Any
type_name = peek_type(data: bytes) -> str          # e.g. "GCounter"
info = wire_size(data: bytes) -> dict               # {"header": int, "payload": int, "total": int}

# Batch
data = serialize_batch(objects: list, compress: bool = False) -> bytes
objects = deserialize_batch(data: bytes) -> list
```

**Wire Format**: `MAGIC(4) | VERSION(2) | FLAGS(1) | TAG(1) | PAYLOAD_LEN(4) | PAYLOAD`

Supported types (tags):
| Tag | Type |
|-----|------|
| 0x01 | GCounter |
| 0x02 | PNCounter |
| 0x03 | LWWRegister |
| 0x04 | ORSet |
| 0x05 | LWWMap |
| 0x10 | Delta |
| 0x20 | Generic (any JSON-serializable) |
| 0x30 | MergeableHLL |
| 0x31 | MergeableBloom |
| 0x32 | MergeableCMS |

---

## 5. DATA STRUCTURES (dataclasses)

| Module | Class | Purpose |
|--------|-------|---------|
| provenance.py | `MergeDecision` | Single field-level merge decision |
| provenance.py | `MergeRecord` | Per-row merge audit record |
| provenance.py | `ProvenanceLog` | Full merge audit log |
| streaming.py | `StreamStats` | Streaming merge performance stats |
| verify.py | `VerificationResult` | Result of one CRDT property test |
| verify.py | `CRDTVerification` | Combined result of all property tests |

---

## 6. CUSTOM EXCEPTIONS

| Module | Exception | When |
|--------|-----------|------|
| verify.py | `CRDTVerificationError` | CRDT law violation detected (raised by `@verified_merge`) |
| wire.py | `WireError` | Serialization/deserialization failure (bad magic, unknown tag, corrupt data) |

---

## 7. AUDIT HISTORY — ALL 26 FIXES APPLIED (v0.5.0-fixed)

### 🔴 CRITICAL (4)

| ID | Module | Issue | Fix |
|----|--------|-------|-----|
| ISS-001 | strategies.py | Priority strategy breaks commutativity — `resolve('x','y') ≠ resolve('y','x')` for unknown values | Added deterministic fallback using `min(val_a, val_b)` for values not in priority list |
| ISS-002 | core.py | `merge()` doesn't accept MergeSchema — the API flagship can't use field-level strategies | Added `schema` parameter pass-through in `__init__.py` top-level merge + dataframe.merge |
| ISS-003 | delta.py | `compose_deltas` produces duplicates — no key-based identity tracking | Added key-aware dedup using `key` parameter in compose |
| ISS-004 | json_merge.py | `merge_dicts` breaks commutativity — always prefers B on equal timestamps | Fixed to prefer A (deterministic, lower node) on equal timestamps |

### 🟠 HIGH (8)

| ID | Module | Issue | Fix |
|----|--------|-------|-----|
| ISS-005 | streaming.py | `merge_stream` silently drops records on empty input | Added empty-input passthrough |
| ISS-006 | dataframe.py | No validation of key column existence | Added KeyError with clear message |
| ISS-007 | core.py | GCounter allows negative increment (violates grow-only) | Added `ValueError` on negative amount |
| ISS-008 | wire.py | No magic number validation on deserialize | Added check at deserialize entry |
| ISS-009 | dataframe.py | Schema parameter accepted but not passed to merge engine | Wired schema through to row resolution |
| ISS-010 | provenance.py | `export_provenance` CSV format crashes on missing fields | Added default values for missing fields |
| ISS-011 | streaming.py | `merge_sorted_stream` doesn't validate sort order | Added prev-key tracking with ValueError |
| ISS-012 | delta.py | `apply_delta` doesn't use schema for modified records | Wired schema.resolve_row into modification path |

### 🟡 MEDIUM (8)

| ID | Module | Issue | Fix |
|----|--------|-------|-----|
| ISS-013 | strategies.py | `Concat` doesn't handle None values | Added None guards |
| ISS-014 | strategies.py | `UnionSet` doesn't handle non-string values | Added str() coercion |
| ISS-015 | dedup.py | `dedup_list` fuzzy method O(n²) with no early termination | Added break-on-match optimization |
| ISS-016 | probabilistic.py | HLL precision not bounded | Added bounds check (4-18) |
| ISS-017 | probabilistic.py | Bloom/CMS merge doesn't validate compatible dimensions | Added dimension compatibility checks |
| ISS-018 | verify.py | `verified_merge` decorator loses function metadata | Added `functools.wraps` |
| ISS-019 | streaming.py | `merge_sorted_stream` drain loop doesn't validate order | Added sort validation to both drain loops |
| ISS-020 | core.py | LWWRegister node_id tiebreaker inconsistent | Standardized to higher node_id wins on equal timestamp |

### 🔵 LOW (6)

| ID | Module | Issue | Fix |
|----|--------|-------|-----|
| ISS-021 | dataframe.py | `diff()` returns lists not dicts for modified | Fixed to return proper diff format |
| ISS-022 | wire.py | `peek_type` returns raw tag on unknown type | Returns "unknown" string |
| ISS-023 | provenance.py | `MergeRecord.to_dict()` doesn't include computed properties | Added conflict_count, fields_from_a, fields_from_b |
| ISS-024 | delta.py | `Delta.to_dict()` omits source_node | Added source_node to serialization |
| ISS-025 | streaming.py | `StreamStats.rows_per_sec` divides by zero when duration=0 | Added zero-duration guard |
| ISS-026 | datasets_ext.py | `dedup_dataset` doesn't pass threshold properly | Fixed parameter threading |

---

## 8. VERIFIED OPTIMAL FEATURES (preserve these!)

| Feature | Why it's excellent |
|---------|--------------------|
| Zero dependencies | Pure stdlib — no supply-chain risk, instant install |
| `verify_crdt()` built-in | Property-based CRDT law testing in the library itself |
| `@verified_merge` decorator | Runtime CRDT compliance checking — unique in the market |
| Binary wire protocol | Custom `CRDT` magic, versioned, compressed, type-tagged |
| Probabilistic CRDTs | HLL + Bloom + CMS all mergeable — rare offering |
| DataFrame + list[dict] duality | Same API works for both pandas and plain Python |
| Streaming merge | Constant-memory merge for billion-row datasets |
| MergeSchema + strategies | Per-field merge strategies — enterprise-grade control |
| Provenance tracking | Full audit trail of every merge decision |
| Delta engine | Git-like diff/patch for record sets |
| DedupIndex as CRDT | Dedup state that is itself mergeable across nodes |
| HuggingFace adapter | First-class ML dataset merge support |
| `merge_dicts` with LWW | Deep nested dict merge with per-key timestamps |
| MinHash dedup | Locality-sensitive hashing for near-duplicate detection |

---

## 9. TEAM OPERATING RULES

### 9.1 Non-Conflicting Module Ownership
When assigning devs, use this ownership matrix to avoid merge conflicts:

| Dev | Primary Modules | Secondary (read-only) |
|-----|----------------|-----------------------|
| Dev 1 | core.py, strategies.py, __init__.py | — |
| Dev 2 | dataframe.py, datasets_ext.py, json_merge.py | strategies |
| Dev 3 | streaming.py, delta.py | strategies, core |
| Dev 4 | probabilistic.py, wire.py | core |
| Dev 5 | verify.py, provenance.py, dedup.py | strategies, core |

### 9.2 Fix Application Order
Always apply fixes in severity order: CRITICAL → HIGH → MEDIUM → LOW. Higher severity fixes may change APIs that lower severity fixes depend on.

### 9.3 Testing Protocol
1. **Every fix must be tested** with a targeted unit test
2. **CRDT law verification** must pass after every change to core/strategies
3. **Integration tests** must cover cross-module data flows
4. **Scale tests** at 10k+ records minimum
5. **Run the full 98-test architect validation suite**: `tests/test_architect_360_validation.py`

### 9.4 Code Standards
- Pure Python, zero new dependencies
- Type hints on all public APIs
- Dataclasses for structured return types
- All CRDT types must implement: `merge()`, `to_dict()`, `from_dict()`
- All merge operations must be commutative, associative, and idempotent
- Functions must handle `None`, empty lists, empty dicts gracefully

---

## 10. HOW TO SET UP THE WORKING ENVIRONMENT

```bash
# Install the package
pip install crdt-merge==0.5.0

# Clone the repo (with fixes already applied)
git clone https://github.com/mgillr/crdt-merge.git
cd crdt-merge

# The fixed source is in crdt_merge/
# The test suite is in tests/test_architect_360_validation.py

# Run tests
python tests/test_architect_360_validation.py

# To work on the source directly:
pip install -e .  # editable install
```

---

## 11. ROADMAP INTEGRATION POINTS

When adding new features, these are the integration points:

| New Feature | Must Integrate With |
|-------------|-------------------|
| New CRDT type | core.py (class), wire.py (tag + serde), verify.py (law tests) |
| New strategy | strategies.py (class), MergeSchema (registration) |
| New data source | datasets_ext.py (adapter), dataframe.py (merge engine) |
| New dedup method | dedup.py (algorithm), DedupIndex (merge support) |
| New probabilistic DS | probabilistic.py (class), wire.py (tag + serde) |
| Performance optimization | streaming.py (batching), delta.py (composition) |
| New export format | provenance.py (export_provenance format param) |

---

## 12. KEY PATTERNS IN THE CODEBASE

### Pattern: CRDT merge returns NEW instance
```python
# ALL .merge() calls return a NEW object — never mutate in place
merged = a.merge(b)  # a and b are unchanged
```

### Pattern: to_dict / from_dict roundtrip
```python
# Every CRDT + Delta + probabilistic type supports this
d = obj.to_dict()
restored = Type.from_dict(d)
# restored must be equivalent to obj
```

### Pattern: wire serialize/deserialize roundtrip
```python
data = serialize(obj)
restored = deserialize(data)
# restored must be equivalent to obj
```

### Pattern: Strategy resolution signature
```python
# ALL strategies use the same 6-parameter resolve signature
value = strategy.resolve(val_a, val_b, ts_a, ts_b, node_a, node_b)
```

### Pattern: Generator-based streaming
```python
# Streaming functions yield List[dict] batches
for batch in merge_stream(a, b, key='id'):
    for record in batch:
        process(record)
```

### Pattern: Optional schema threading
```python
# Many functions accept schema=None — they use LWW() as default
merge(a, b, key='id', schema=my_schema)
apply_delta(records, delta, key='id', schema=my_schema)
merge_sorted_stream(a, b, key='id', schema=my_schema)
```

---

## 13. KNOWN LIMITATIONS (not bugs, by design)

1. **No persistence** — all state is in-memory (use wire.py for serialization)
2. **No networking** — this is a merge engine, not a sync protocol
3. **No conflict resolution UI** — strategies resolve conflicts automatically
4. **DataFrame merge loads both sides** — only streaming.py is constant-memory
5. **Fuzzy dedup is O(n²)** — MinHash is the scalable alternative
6. **HLL precision range 4-18** — hardware/math constraint
7. **Wire protocol v1 only** — no backward-compat concerns yet

---

## 14. QUICK-START EXAMPLES

### Basic merge
```python
from crdt_merge import merge
result = merge([{"id": 1, "name": "Alice"}], [{"id": 1, "name": "Bob"}], key="id")
```

### CRDT counter
```python
from crdt_merge.core import GCounter
a = GCounter(); a.increment("node1", 5)
b = GCounter(); b.increment("node2", 3)
merged = a.merge(b)
print(merged.value)  # 8
```

### Schema-driven merge
```python
from crdt_merge.strategies import MergeSchema, MaxWins, LWW
schema = MergeSchema(default=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema)
```

### Streaming merge (constant memory)
```python
from crdt_merge.streaming import merge_stream, StreamStats
stats = StreamStats()
for batch in merge_stream(source_a, source_b, key="id", stats=stats):
    write_batch(batch)
print(f"{stats.rows_per_sec:.0f} rows/sec")
```

### Verify your custom CRDT
```python
from crdt_merge.verify import verify_crdt
result = verify_crdt(my_merge_fn, my_generator_fn, trials=1000)
print(result.summary())
```

---

*Generated from full codebase audit of crdt-merge v0.5.0 with 26 fixes applied.*
*98/98 architect validation tests passing.*
*Last updated: 2026-03-28*
