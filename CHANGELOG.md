# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0] — 2026-03-28 — "The Architecture Release"

### 🏗️ New Modules (7)
- **clocks.py** (~200 LOC): Hybrid Logical Clocks (HLC) for distributed CRDT ordering. `HLClock`, `HLCTimestamp`, `hlc_now()`, full compare/merge semantics.
- **schema_evolution.py** (~300 LOC): Automatic schema evolution for CRDT merges. Column mapping, type coercion, missing-column policies. `SchemaEvolver`, `ColumnMapping`, `TypeCoercion`.
- **merkle.py** (~400 LOC): Merkle hash trees for efficient dataset comparison. `MerkleTree`, `MerkleNode`, incremental sync with `diff()` finding changed subtrees.
- **arrow.py** (~800 LOC): Apache Arrow-native merge engine for 10-50× speedup. `ArrowMergeEngine` with zero-copy operations, native Polars/DuckDB integration, columnar strategy application.
- **gossip.py** (~400 LOC): Gossip protocol state tracking for CRDT anti-entropy. `GossipState`, `GossipPeer`, version vector tracking, pull/push/pull-push sync modes.
- **async_merge.py** (~150 LOC): Async/await wrappers for non-blocking merge operations. `async_merge()`, `async_merge_dataframes()`, `AsyncMergeSession` for batch processing.
- **parallel.py** (~200 LOC): Parallel merge execution across CPU cores. `parallel_merge()`, `ParallelConfig`, chunk-based partitioning with automatic core detection.

### 🔧 Enhancements
- **Multi-key merge** in `dataframe.py`: `merge_dataframes()` now accepts `key` as a list for composite key merging.
- **Wire protocol v2**: New wire tags for all v0.6.0 types (HLC timestamps, Merkle trees, Arrow tables, gossip state).
- **Integration tests**: Cross-module pipeline tests verifying clocks→gossip→merkle→arrow→async→parallel flow.

### 🐛 Bug Fix
- **json_merge.py**: Fixed deterministic tiebreak — B now correctly wins on equal timestamps (LWW Register convention).

### 📊 Stats
- Source modules: 13 → **20** (+7)
- Source lines: 4,028 → **~7,300** (+3,272)
- Test files: 15 → **24** (+9)
- Tests passing: 406 → **705** (+299)
- Zero regressions against v0.5.0 baseline

## [0.5.0] — 2026-03-27 — "The Protocol Release"

### Added

#### Binary Wire Format (`crdt_merge.wire`)
- `serialize()` / `deserialize()` — compact binary serialization for all CRDT types
- `serialize_batch()` / `deserialize_batch()` — batch operations
- `peek_type()` — inspect type without full deserialization
- `wire_size()` — detailed size breakdown (header, payload, compression)
- Optional zlib compression (`compress=True`)
- Deterministic 12-byte header: magic, protocol version, type, flags, length
- Supported types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap, Delta, MergeableHLL, MergeableBloom, MergeableCMS

#### Probabilistic CRDTs (`crdt_merge.probabilistic`)
- `MergeableHLL` — HyperLogLog with register-max merge (±0.81% error at precision=14)
- `MergeableBloom` — Bloom filter with bitwise-OR merge
- `MergeableCMS` — Count-Min Sketch with element-wise max merge
- All three satisfy CRDT merge properties (C/A/I)
- Full wire format integration

#### New Tests
- 148 new tests (40 wire + 42 probabilistic + 66 integration)
- 425 total tests (was 277 in v0.4.0)

## [0.4.0] — 2026-03-26 — "The Audit Release"

### Added

#### Merge Provenance (`crdt_merge.provenance`)
- `merge_with_provenance()` — merge with complete per-field audit trail
- `ProvenanceLog` — structured log of all merge decisions
- `export_provenance()` — export to JSON or CSV string
- Per-entry tracking: field name, source A/B values, winner, strategy used
- Summary statistics: total conflicts, merged rows, unique rows per source

#### Verified Merge (`crdt_merge.verify`)
- `@verified_merge` decorator — property-based testing of merge functions
- Verifies commutativity, associativity, and idempotency
- `CRDTVerificationError` with detailed failure diagnostics
- Configurable sample count and key column

#### Performance Optimizations
- Streaming merge throughput stabilized at ~400K rows/s via column caching
- Efficient GC handling for stable throughput at scale

#### New Tests
- 144 new tests (24 provenance + 10 verified merge + 110 integration)
- 277 total tests (was 133 in v0.3.0)

## [0.3.0] — 2026-03-26 — "The Schema Release"

### Added

#### Composable Merge Strategies (`crdt_merge.strategies`)
- `MergeSchema` — declarative per-field strategy mapping DSL
- `LWW` — Last-Writer-Wins (timestamp + deterministic node tie-break)
- `MaxWins` — highest value wins (numbers, strings, any comparable)
- `MinWins` — lowest value wins
- `UnionSet` — merge delimited values as set union (sorted for determinism)
- `Priority` — ranked priority list (e.g., `["draft", "review", "published"]`)
- `Concat` — concatenate with dedup and sorting for commutativity
- `LongestWins` — longer string wins, LWW fallback on tie
- `Custom` — user-provided merge function with full kwargs support
- `MergeSchema.resolve_row()` — merge entire row pairs using per-field strategies
- `MergeSchema.to_dict()` / `MergeSchema.from_dict()` — serialization for storage/transmission

#### Streaming Merge Pipeline (`crdt_merge.streaming`)
- `merge_stream()` — O(batch_size) memory merge for unlimited scale
- `merge_sorted_stream()` — O(1) merge-join for pre-sorted sources
- `StreamStats` — live statistics tracking (rows/sec, batch count, peak size)
- `count_stream()` — count rows without loading into memory
- Generator-based processing: never loads entire datasets into memory

#### Delta Sync (`crdt_merge.delta`)
- `compute_delta()` — compute changes between two record sets
- `apply_delta()` — apply delta to bring records up to date
- `compose_deltas()` — compose multiple deltas into one (δ-CRDT composability)
- `DeltaStore` — automatic version tracking with delta computation
- `Delta.to_dict()` / `Delta.from_dict()` — serialization

#### Optional Dependencies
- `pip install crdt-merge[fast]` — orjson + xxhash for heavy workloads
- Zero required dependencies preserved

#### New Tests
- 58 new tests covering all strategies + streaming + delta
- 133 total tests (was 75 in v0.2.0)

### Changed
- Updated project description to "The Merge Algebra Toolkit"
- Added Python 3.9–3.12 classifiers

### Fixed
- Version in `__init__.py` now matches `pyproject.toml`

## [0.2.0] — 2026-03-20

### Changed
- License changed from MIT to Apache-2.0 with patent protection
- Added NOTICE file (© 2026 Ryan Gillespie)
- Added PATENTS file with defensive patent termination clause

## [0.1.0] — 2026-03-15

### Added
- Initial release
- Core CRDT types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap
- DataFrame merge with key-based reconciliation (`merge()`, `diff()`)
- JSON/dict deep merge with timestamp support (`merge_dicts()`, `merge_json_lines()`)
- Deduplication: exact, fuzzy (bigram), MinHash (`dedup_list()`, `dedup_records()`, `MinHashDedup`)
- HuggingFace Datasets integration (`merge_datasets()`, `dedup_dataset()`)
- 45 tests, zero dependencies, 1,035 lines
