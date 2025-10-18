# Changelog

All notable changes to this project will be documented in this file.

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
- Configurable `batch_size` controls the memory/throughput tradeoff

#### Optional Dependencies
- `pip install crdt-merge[fast]` — orjson + xxhash for heavy workloads
- Zero required dependencies preserved — pure Python, embeddable anywhere

#### New Tests
- 58 new tests covering all strategies + streaming
- CRDT property proofs: commutativity, associativity, idempotency verified
- Memory efficiency test using tracemalloc
- 133 total tests (was 75 in v0.2.0)

### Changed
- Updated project description to "The Merge Algebra Toolkit"
- Added Python 3.9–3.12 classifiers
- Added Changelog and Documentation URLs

### Fixed
- Version in `__init__.py` now matches `pyproject.toml`

## [0.2.0] — 2026-03-20

### Changed
- License changed from MIT to Apache-2.0 with patent protection
- Added NOTICE file (© 2024–2026 Ryan Gillespie / Optitransfer)
- Added PATENTS file with defensive patent termination clause

## [0.1.0] — 2026-03-15

### Added
- Initial release
- Core CRDT types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap
- DataFrame merge with key-based reconciliation
- JSON/dict deep merge with timestamp support
- Deduplication: exact, fuzzy (bigram), MinHash
- HuggingFace Datasets integration (optional)
- 75 tests, zero dependencies, 1,035 lines
